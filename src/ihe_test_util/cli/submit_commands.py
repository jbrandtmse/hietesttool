"""Submit CLI commands module for integrated PIX Add + ITI-41 workflow.

This module provides Click-based CLI commands for the complete patient
submission workflow: CSV parsing → CCD generation → PIX Add → ITI-41.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from requests import ConnectionError, Timeout
from requests.exceptions import SSLError

from ihe_test_util.config.manager import load_config
from ihe_test_util.config.schema import Config
from ihe_test_util.csv_parser.parser import parse_csv
from ihe_test_util.ihe_transactions.workflows import (
    IntegratedWorkflow,
    generate_integrated_workflow_summary,
    save_workflow_results_to_json,
)
from ihe_test_util.models.batch import BatchWorkflowResult, PatientWorkflowResult
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.utils.exceptions import ConfigurationError, ValidationError

logger = logging.getLogger(__name__)


@click.group(name="submit")
def submit() -> None:
    """Patient submission workflow commands.
    
    Use these commands to process patients through the complete PIX Add + ITI-41
    workflow: CSV parsing → CCD generation → PIX Add registration → ITI-41
    document submission.
    """
    pass


@submit.command(name="batch")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file path (overrides default)",
)
@click.option(
    "--ccd-template",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="CCD template file path (overrides config)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output JSON file path for workflow results",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate configuration and CSV without submitting",
)
@click.option(
    "--http",
    is_flag=True,
    help="Use HTTP transport (displays security warning)",
)
@click.pass_context
def batch(
    ctx: click.Context,
    csv_file: Path,
    config: Optional[Path],
    ccd_template: Optional[Path],
    output: Optional[Path],
    dry_run: bool,
    http: bool,
) -> None:
    """Process patients through complete PIX Add + ITI-41 workflow.
    
    Orchestrates the complete patient submission workflow:
    1. Parse CSV file for patient demographics
    2. Generate personalized CCD documents
    3. Register patients via PIX Add (ITI-44)
    4. Submit documents via ITI-41 (Provide and Register)
    
    Displays real-time progress with color-coded results. Patients are processed
    sequentially, and PIX Add must succeed before ITI-41 submission.
    
    Args:
        csv_file: Path to CSV file containing patient demographics
        config: Optional config file path
        ccd_template: Optional CCD template file path
        output: Optional JSON file path for results
        dry_run: Validate without submitting
        http: Use HTTP transport (displays security warning)
        
    Exit Codes:
        0: All patients processed successfully
        1: Validation error (CSV, config, certificates)
        2: Some transactions failed (partial success)
        3: Critical error (SSL, missing config)
        
    Examples:
        # Basic batch submission with default config
        $ ihe-test-util submit batch examples/patients_sample.csv
        
        # Use custom CCD template
        $ ihe-test-util submit batch patients.csv --ccd-template templates/ccd-custom.xml
        
        # Save results to JSON file
        $ ihe-test-util submit batch patients.csv --output results.json
        
        # Dry-run validation
        $ ihe-test-util submit batch patients.csv --dry-run
    """
    start_time = time.time()
    
    try:
        # Load configuration with overrides
        logger.info("Loading configuration for integrated workflow")
        config_obj = _load_config_with_overrides(
            ctx=ctx,
            config_path=config,
            ccd_template=ccd_template,
            http_flag=http
        )
        
        # Display security warning for HTTP transport
        if http or _is_http_endpoint(config_obj):
            _display_http_security_warning()
        
        # Dry-run mode: validate without submitting
        if dry_run:
            logger.info("DRY RUN MODE - Validating without submission")
            _execute_dry_run(csv_file, config_obj, ccd_template)
            sys.exit(0)
        
        # Display header
        click.echo()
        click.echo(click.style("=" * 80, fg="cyan"))
        click.echo(click.style("INTEGRATED PIX ADD + ITI-41 WORKFLOW", fg="cyan", bold=True))
        click.echo(click.style("=" * 80, fg="cyan"))
        click.echo()
        
        # Parse CSV to get patient count
        logger.info(f"Parsing CSV file: {csv_file}")
        df, validation_result = parse_csv(csv_file, validate=True)
        total_patients = len(df)
        
        click.echo(f"CSV File:           {csv_file}")
        click.echo(f"Total Patients:     {total_patients}")
        click.echo(f"PIX Add Endpoint:   {config_obj.endpoints.pix_add_url}")
        click.echo(f"ITI-41 Endpoint:    {config_obj.endpoints.iti41_url}")
        click.echo()
        
        # Determine CCD template path
        template_path = ccd_template or _get_default_ccd_template()
        click.echo(f"CCD Template:       {template_path}")
        click.echo()
        
        # Initialize workflow
        logger.info("Initializing integrated workflow")
        workflow = IntegratedWorkflow(config_obj, str(template_path))
        
        # Process batch with real-time progress display
        click.echo(click.style("Processing patients...", fg="cyan"))
        click.echo()
        
        result = workflow.process_batch(csv_file)
        
        # Display per-patient results with color coding
        _display_patient_results(result)
        
        # Display summary report
        click.echo()
        summary = generate_integrated_workflow_summary(result)
        _display_summary_report(result, summary)
        
        # Save JSON output if requested
        if output:
            save_workflow_results_to_json(result, str(output))
            click.echo()
            click.echo(
                click.style("✓ Results saved to: ", fg="green") + str(output)
            )
        
        # Determine exit code based on results
        elapsed_time = time.time() - start_time
        logger.info(
            f"Integrated workflow complete: {result.fully_successful_count}/{result.total_patients} "
            f"fully successful in {elapsed_time:.1f}s"
        )
        
        # Exit code based on results
        if result.fully_successful_count == result.total_patients:
            sys.exit(0)  # All patients fully processed
        else:
            sys.exit(2)  # Some transactions failed
        
    except ValidationError as e:
        # Validation errors (CSV, config, certificates)
        logger.error(f"Validation error: {e}")
        click.echo(
            click.style("✗ Validation Error: ", fg="red", bold=True) + str(e),
            err=True
        )
        sys.exit(1)
        
    except (ConnectionError, Timeout) as e:
        # Transaction errors (network, endpoint)
        logger.error(f"Transaction error: {e}")
        click.echo(
            click.style("✗ Transaction Error: ", fg="red", bold=True) + str(e),
            err=True
        )
        click.echo(
            "\nRemediation: Check endpoint URLs and network connectivity.",
            err=True
        )
        sys.exit(2)
        
    except SSLError as e:
        # Critical SSL errors
        logger.error(f"SSL error: {e}")
        click.echo(
            click.style("✗ SSL Error: ", fg="red", bold=True) + str(e),
            err=True
        )
        click.echo(
            "\nRemediation: For development, set verify_tls=false in config.json. "
            "For production, ensure valid certificate chain.",
            err=True
        )
        sys.exit(3)
        
    except ConfigurationError as e:
        # Critical configuration errors
        logger.error(f"Configuration error: {e}")
        click.echo(
            click.style("✗ Configuration Error: ", fg="red", bold=True) + str(e),
            err=True
        )
        sys.exit(3)
        
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error: {e}", exc_info=True)
        click.echo(
            click.style("✗ Unexpected Error: ", fg="red", bold=True) + str(e),
            err=True
        )
        sys.exit(3)


def _load_config_with_overrides(
    ctx: click.Context,
    config_path: Optional[Path],
    ccd_template: Optional[Path],
    http_flag: bool
) -> Config:
    """Load configuration with CLI option overrides.
    
    Applies configuration precedence: CLI flags > config file > defaults.
    
    Args:
        ctx: Click context with parent config
        config_path: Optional custom config file path
        ccd_template: Optional CCD template path override
        http_flag: HTTP transport flag
        
    Returns:
        Configuration object with overrides applied
        
    Raises:
        ConfigurationError: If configuration is invalid or missing required fields
        ValidationError: If certificate file is invalid or missing
    """
    # Load base configuration
    if config_path:
        logger.info(f"Loading configuration from: {config_path}")
        config_obj = load_config(config_path)
    elif ctx.obj and "config" in ctx.obj:
        logger.info("Using configuration from parent context")
        config_obj = ctx.obj["config"]
    else:
        logger.info("Loading default configuration")
        config_obj = load_config()
    
    # Apply HTTP flag to endpoints
    if http_flag:
        logger.info("Forcing HTTP transport (insecure)")
        if config_obj.endpoints.pix_add_url:
            config_obj.endpoints.pix_add_url = config_obj.endpoints.pix_add_url.replace(
                "https://", "http://"
            )
        if config_obj.endpoints.iti41_url:
            config_obj.endpoints.iti41_url = config_obj.endpoints.iti41_url.replace(
                "https://", "http://"
            )
    
    # Validate required configuration
    if not config_obj.endpoints.pix_add_url:
        raise ConfigurationError(
            "Missing required configuration: endpoints.pix_add_url. "
            "Add PIX Add endpoint URL to config.json or use --config flag."
        )
    
    if not config_obj.endpoints.iti41_url:
        raise ConfigurationError(
            "Missing required configuration: endpoints.iti41_url. "
            "Add ITI-41 endpoint URL to config.json or use --config flag."
        )
    
    if not config_obj.certificates.cert_path:
        raise ConfigurationError(
            "Missing required configuration: certificates.cert_path. "
            "Add certificate path to config.json or generate with: scripts/generate_cert.sh"
        )
    
    if not Path(config_obj.certificates.cert_path).exists():
        raise ValidationError(
            f"Certificate file not found: {config_obj.certificates.cert_path}. "
            "Generate certificate with: scripts/generate_cert.sh"
        )
    
    if not config_obj.certificates.key_path:
        raise ConfigurationError(
            "Missing required configuration: certificates.key_path. "
            "Add private key path to config.json."
        )
    
    if not Path(config_obj.certificates.key_path).exists():
        raise ValidationError(
            f"Private key file not found: {config_obj.certificates.key_path}. "
            "Ensure private key exists alongside certificate."
        )
    
    logger.info("Configuration loaded and validated successfully")
    
    return config_obj


def _is_http_endpoint(config_obj: Config) -> bool:
    """Check if any endpoint uses HTTP (insecure) transport."""
    pix_http = config_obj.endpoints.pix_add_url and config_obj.endpoints.pix_add_url.startswith("http://")
    iti41_http = config_obj.endpoints.iti41_url and config_obj.endpoints.iti41_url.startswith("http://")
    return pix_http or iti41_http


def _display_http_security_warning() -> None:
    """Display security warning for HTTP transport and prompt for confirmation."""
    warning = click.style(
        "⚠️  WARNING: Using insecure HTTP transport. "
        "Patient data will be transmitted unencrypted.",
        fg="yellow",
        bold=True
    )
    click.echo()
    click.echo(warning)
    click.echo()
    
    logger.warning("HTTP transport enabled - data will be transmitted unencrypted")
    
    if not click.confirm("Continue with HTTP?", default=False):
        click.echo("Aborted.")
        logger.info("User declined to use HTTP transport")
        sys.exit(1)
    
    logger.warning("User confirmed HTTP transport usage")


def _get_default_ccd_template() -> Path:
    """Get the default CCD template path."""
    # Check common template locations
    candidates = [
        Path("templates/ccd-template.xml"),
        Path("templates/ccd-minimal.xml"),
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    # Return first candidate as default (will fail with clear error if missing)
    return candidates[0]


def _execute_dry_run(csv_file: Path, config_obj: Config, ccd_template: Optional[Path]) -> None:
    """Execute dry-run validation without submitting patients.
    
    Args:
        csv_file: Path to CSV file
        config_obj: Configuration object
        ccd_template: Optional CCD template path
        
    Raises:
        ValidationError: If validation fails
        SystemExit: Always exits with code 0 (success) or 1 (failure)
    """
    click.echo()
    click.echo(click.style("DRY RUN MODE - Validation Only", fg="yellow", bold=True))
    click.echo(click.style("=" * 80, fg="yellow"))
    click.echo()
    
    try:
        # Validate CSV
        click.echo("Validating CSV file...")
        df, validation_result = parse_csv(csv_file, validate=True)
        click.echo(
            click.style(f"✓ CSV validated: {len(df)} patients", fg="green")
        )
        
        # Validate configuration
        click.echo("Validating configuration...")
        if not config_obj.endpoints.pix_add_url:
            raise ValidationError("Missing PIX Add endpoint URL in configuration")
        if not config_obj.endpoints.iti41_url:
            raise ValidationError("Missing ITI-41 endpoint URL in configuration")
        click.echo(
            click.style(
                f"✓ Config validated: PIX Add @ {config_obj.endpoints.pix_add_url}",
                fg="green"
            )
        )
        click.echo(
            click.style(
                f"✓ Config validated: ITI-41 @ {config_obj.endpoints.iti41_url}",
                fg="green"
            )
        )
        
        # Validate certificate
        click.echo("Validating certificate...")
        cert_bundle = load_certificate(
            cert_source=Path(config_obj.certificates.cert_path),
            key_path=Path(config_obj.certificates.key_path)
        )
        expiry = cert_bundle.certificate.not_valid_after_utc
        click.echo(
            click.style(
                f"✓ Certificate validated: expires {expiry.strftime('%Y-%m-%d')}",
                fg="green"
            )
        )
        
        # Validate CCD template
        click.echo("Validating CCD template...")
        template_path = ccd_template or _get_default_ccd_template()
        if not template_path.exists():
            raise ValidationError(f"CCD template not found: {template_path}")
        click.echo(
            click.style(
                f"✓ CCD template validated: {template_path}",
                fg="green"
            )
        )
        
        # Show sample validation (first 3 patients)
        click.echo()
        click.echo("Sample patient validation (first 3):")
        for idx, row in df.head(3).iterrows():
            patient_name = f"{row['first_name']} {row['last_name']}"
            click.echo(
                click.style(f"✓ {patient_name} - Ready for workflow", fg="green")
            )
        
        if len(df) > 3:
            click.echo(f"... and {len(df) - 3} more patients")
        
        click.echo()
        click.echo(click.style("DRY RUN COMPLETE - No errors detected", fg="green", bold=True))
        click.echo()
        click.echo("Workflow steps for each patient:")
        click.echo("  1. Parse patient from CSV")
        click.echo("  2. Generate personalized CCD document")
        click.echo("  3. Register patient via PIX Add (ITI-44)")
        click.echo("  4. Submit document via ITI-41 (Provide and Register)")
        
        logger.info(f"Dry-run validation passed for {len(df)} patients")
        
    except ValidationError as e:
        click.echo()
        click.echo(click.style(f"✗ Validation failed: {e}", fg="red"))
        logger.error(f"Dry-run validation failed: {e}")
        sys.exit(1)


def _display_patient_results(result: BatchWorkflowResult) -> None:
    """Display per-patient results with color coding.
    
    Args:
        result: Batch workflow result with patient details
    """
    for idx, patient_result in enumerate(result.patient_results, 1):
        patient_id = patient_result.patient_id
        
        # Determine status color and message
        if patient_result.is_fully_successful:
            # Green for full success
            status = click.style("✓ Complete", fg="green")
            message = f"PIX ID: {patient_result.pix_enterprise_id or 'N/A'}, Doc: {patient_result.document_id or 'N/A'}"
        elif patient_result.pix_add_status == "success" and patient_result.iti41_status != "success":
            # Yellow for partial success (PIX succeeded, ITI-41 failed)
            status = click.style("⚠ Partial", fg="yellow")
            message = f"PIX OK, ITI-41: {patient_result.iti41_message or 'failed'}"
        elif patient_result.pix_add_status == "failed":
            # Red for PIX Add failure (ITI-41 skipped)
            status = click.style("✗ Failed", fg="red")
            message = f"PIX Add: {patient_result.pix_add_message or 'failed'} (ITI-41 skipped)"
        else:
            # Red for other failures
            status = click.style("✗ Failed", fg="red")
            message = patient_result.error_message or "Unknown error"
        
        click.echo(
            f"Patient {idx:3d}/{result.total_patients}: "
            f"{patient_id:20s} {status} ({message})"
        )


def _display_summary_report(result: BatchWorkflowResult, summary: str) -> None:
    """Display summary report with statistics.
    
    Args:
        result: Batch workflow result
        summary: Pre-generated summary string
    """
    click.echo(click.style("=" * 80, fg="cyan"))
    click.echo(click.style("WORKFLOW SUMMARY", fg="cyan", bold=True))
    click.echo(click.style("=" * 80, fg="cyan"))
    click.echo()
    
    # Overall statistics
    click.echo("Processing Results")
    click.echo("-" * 80)
    click.echo(f"Total Patients:         {result.total_patients}")
    
    # Full success
    full_success_color = "green" if result.fully_successful_count == result.total_patients else "yellow"
    click.echo(
        f"Fully Successful:       "
        + click.style(
            f"{result.fully_successful_count} ({result.full_success_rate:.1f}%)",
            fg=full_success_color
        )
    )
    
    # PIX Add success
    pix_success_color = "green" if result.pix_add_success_count == result.total_patients else "yellow"
    click.echo(
        f"PIX Add Success:        "
        + click.style(
            f"{result.pix_add_success_count} ({result.pix_add_success_rate:.1f}%)",
            fg=pix_success_color
        )
    )
    
    # ITI-41 success
    iti41_success_color = "green" if result.iti41_success_count == result.total_patients else "yellow"
    click.echo(
        f"ITI-41 Success:         "
        + click.style(
            f"{result.iti41_success_count} ({result.iti41_success_rate:.1f}%)",
            fg=iti41_success_color
        )
    )
    
    # Failed counts
    if result.pix_add_failed_count > 0:
        click.echo(
            f"PIX Add Failed:         "
            + click.style(f"{result.pix_add_failed_count}", fg="red")
        )
    
    if result.iti41_failed_count > 0:
        click.echo(
            f"ITI-41 Failed:          "
            + click.style(f"{result.iti41_failed_count}", fg="red")
        )
    
    if result.iti41_skipped_count > 0:
        click.echo(
            f"ITI-41 Skipped:         "
            + click.style(f"{result.iti41_skipped_count}", fg="yellow")
            + " (PIX Add failed)"
        )
    
    # Timing
    if result.total_duration_seconds:
        click.echo(f"Duration:               {result.total_duration_seconds:.1f}s")
    
    if result.average_patient_time_seconds:
        click.echo(f"Avg Time/Patient:       {result.average_patient_time_seconds:.2f}s")
    
    click.echo()
    click.echo(click.style("=" * 80, fg="cyan"))
