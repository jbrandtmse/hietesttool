"""PIX Add CLI commands module.

This module provides Click-based CLI commands for PIX Add (ITI-44) patient
registration operations, including batch processing from CSV files.
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
from ihe_test_util.ihe_transactions.error_summary import (
    ErrorSummaryCollector,
    generate_error_report,
)
from ihe_test_util.ihe_transactions.workflows import (
    PIXAddWorkflow,
    save_registered_identifiers,
)
from ihe_test_util.models.batch import BatchProcessingResult
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.utils.exceptions import ConfigurationError, ValidationError

logger = logging.getLogger(__name__)


@click.group(name="pix-add")
def pix_add() -> None:
    """PIX Add patient registration commands.
    
    Use these commands to register patients via PIX Add (ITI-44) transactions.
    Supports batch registration from CSV files with comprehensive error handling.
    """
    pass


@pix_add.command(name="register")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--endpoint",
    "-e",
    type=str,
    default=None,
    help="PIX Add endpoint URL (overrides config)",
)
@click.option(
    "--cert",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Certificate path for SAML signing (overrides config)",
)
@click.option(
    "--http",
    is_flag=True,
    help="Use HTTP transport (displays security warning)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output JSON file path for registration results",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate configuration and CSV without submitting",
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file path (overrides default)",
)
@click.pass_context
def register(
    ctx: click.Context,
    csv_file: Path,
    endpoint: Optional[str],
    cert: Optional[Path],
    http: bool,
    output: Optional[Path],
    dry_run: bool,
    config: Optional[Path],
) -> None:
    """Register patients from CSV file via PIX Add transaction.
    
    Orchestrates the complete PIX Add workflow: CSV parsing, HL7v3 message
    construction, SAML signing, SOAP submission, and acknowledgment parsing.
    Displays real-time progress and color-coded results.
    
    Args:
        csv_file: Path to CSV file containing patient demographics
        endpoint: Optional PIX Add endpoint URL (overrides config)
        cert: Optional certificate path for SAML signing (overrides config)
        http: Use HTTP transport (displays security warning)
        output: Optional JSON file path for results
        dry_run: Validate without submitting
        config: Optional config file path
        
    Raises:
        SystemExit: With appropriate exit code based on error type
        
    Exit Codes:
        0: Success
        1: Validation error (CSV, config, certificates)
        2: Transaction error (network, endpoint)
        3: Critical error (SSL, missing config)
        
    Examples:
        # Basic registration with default config
        $ ihe-test-util pix-add register examples/patients_sample.csv
        
        # Override endpoint URL
        $ ihe-test-util pix-add register patients.csv --endpoint https://pix.example.com/add
        
        # Use custom certificate
        $ ihe-test-util pix-add register patients.csv --cert /path/to/cert.pem
        
        # HTTP mode for testing (with warning)
        $ ihe-test-util pix-add register patients.csv --http
        
        # Save results to JSON file
        $ ihe-test-util pix-add register patients.csv --output results.json
        
        # Dry-run validation
        $ ihe-test-util pix-add register patients.csv --dry-run
    """
    start_time = time.time()
    
    try:
        # Load configuration with overrides
        logger.info(f"Loading configuration for PIX Add registration")
        config_obj = _load_config_with_overrides(
            ctx=ctx,
            config_path=config,
            endpoint=endpoint,
            cert=cert,
            http_flag=http
        )
        
        # Display security warning for HTTP transport
        if http or (config_obj.endpoints.pix_add_url and 
                    config_obj.endpoints.pix_add_url.startswith("http://")):
            _display_http_security_warning()
        
        # Dry-run mode: validate without submitting
        if dry_run:
            logger.info("DRY RUN MODE - Validating without submission")
            _execute_dry_run(csv_file, config_obj)
            sys.exit(0)
        
        # Display header
        click.echo()
        click.echo(click.style("=" * 80, fg="cyan"))
        click.echo(click.style("PIX ADD PATIENT REGISTRATION", fg="cyan", bold=True))
        click.echo(click.style("=" * 80, fg="cyan"))
        click.echo()
        
        # Parse CSV to get patient count
        logger.info(f"Parsing CSV file: {csv_file}")
        df, validation_result = parse_csv(csv_file, validate=True)
        total_patients = len(df)
        
        click.echo(f"CSV File:       {csv_file}")
        click.echo(f"Total Patients: {total_patients}")
        click.echo(f"Endpoint:       {config_obj.endpoints.pix_add_url}")
        click.echo()
        
        # Initialize workflow
        logger.info("Initializing PIX Add workflow")
        workflow = PIXAddWorkflow(config_obj)
        
        # Process batch with real-time progress display
        click.echo(click.style("Processing patients...", fg="cyan"))
        click.echo()
        
        result = workflow.process_batch(csv_file)
        
        # Display per-patient results with color coding
        _display_patient_results(result)
        
        # Display summary report
        click.echo()
        _display_summary_report(result)
        
        # Save JSON output if requested
        if output:
            _save_json_output(result, output, config_obj, csv_file)
        
        # Determine exit code based on results
        elapsed_time = time.time() - start_time
        logger.info(
            f"PIX Add registration complete: {result.successful_patients}/{result.total_patients} "
            f"successful in {elapsed_time:.1f}s"
        )
        
        # Exit code 0 only if all patients succeeded
        if result.failed_patients > 0:
            sys.exit(2)  # Transaction errors occurred
        
        sys.exit(0)
        
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
            "\nRemediation: Check endpoint URL and network connectivity.",
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
    endpoint: Optional[str],
    cert: Optional[Path],
    http_flag: bool
) -> Config:
    """Load configuration with CLI option overrides.
    
    Applies configuration precedence: CLI flags > config file > defaults.
    
    Args:
        ctx: Click context with parent config
        config_path: Optional custom config file path
        endpoint: Optional endpoint URL override
        cert: Optional certificate path override
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
    
    # Apply CLI overrides
    if endpoint:
        logger.info(f"Overriding PIX Add endpoint: {endpoint}")
        config_obj.endpoints.pix_add_url = endpoint
    
    if cert:
        logger.info(f"Overriding certificate path: {cert}")
        config_obj.certificates.cert_path = str(cert)
        # Also update key path to use same directory (assume .key extension)
        cert_dir = cert.parent
        cert_stem = cert.stem
        key_path = cert_dir / f"{cert_stem}.key"
        if key_path.exists():
            config_obj.certificates.key_path = str(key_path)
    
    if http_flag:
        logger.info("Forcing HTTP transport (insecure)")
        # Update endpoint to use HTTP if it uses HTTPS
        if config_obj.endpoints.pix_add_url:
            config_obj.endpoints.pix_add_url = config_obj.endpoints.pix_add_url.replace(
                "https://", "http://"
            )
    
    # Validate required configuration
    if not config_obj.endpoints.pix_add_url:
        raise ConfigurationError(
            "Missing required configuration: endpoints.pix_add_url. "
            "Add PIX Add endpoint URL to config.json or use --endpoint flag."
        )
    
    if not config_obj.certificates.cert_path:
        raise ConfigurationError(
            "Missing required configuration: certificates.cert_path. "
            "Add certificate path to config.json, use --cert flag, or generate with: scripts/generate_cert.sh"
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


def _execute_dry_run(csv_file: Path, config_obj: Config) -> None:
    """Execute dry-run validation without submitting patients.
    
    Args:
        csv_file: Path to CSV file
        config_obj: Configuration object
        
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
        click.echo(
            click.style(
                f"✓ Config validated: endpoint {config_obj.endpoints.pix_add_url}",
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
        
        # Show sample validation (first 3 patients)
        click.echo()
        click.echo("Sample patient validation (first 3):")
        for idx, row in df.head(3).iterrows():
            patient_name = f"{row['first_name']} {row['last_name']}"
            click.echo(
                click.style(f"✓ {patient_name} - Ready for submission", fg="green")
            )
        
        if len(df) > 3:
            click.echo(f"... and {len(df) - 3} more patients")
        
        click.echo()
        click.echo(click.style("DRY RUN COMPLETE - No errors detected", fg="green", bold=True))
        
        logger.info(f"Dry-run validation passed for {len(df)} patients")
        
    except ValidationError as e:
        click.echo()
        click.echo(click.style(f"✗ Validation failed: {e}", fg="red"))
        logger.error(f"Dry-run validation failed: {e}")
        sys.exit(1)


def _display_patient_results(result: BatchProcessingResult) -> None:
    """Display per-patient results with color coding.
    
    Args:
        result: Batch processing result with patient details
    """
    for idx, patient_result in enumerate(result.patient_results, 1):
        patient_id = patient_result.patient_id
        
        if patient_result.is_success:
            # Green for success
            status = click.style("✓ Success", fg="green")
            enterprise_id = patient_result.enterprise_id or "N/A"
            message = f"PIX ID: {enterprise_id}"
        else:
            # Red for failure
            status = click.style("✗ Failed", fg="red")
            message = patient_result.pix_add_message
        
        click.echo(
            f"Patient {idx:3d}/{result.total_patients}: "
            f"{patient_id:20s} {status} ({message})"
        )


def _display_summary_report(result: BatchProcessingResult) -> None:
    """Display summary report with statistics and error breakdown.
    
    Args:
        result: Batch processing result
    """
    click.echo(click.style("=" * 80, fg="cyan"))
    click.echo(click.style("REGISTRATION SUMMARY", fg="cyan", bold=True))
    click.echo(click.style("=" * 80, fg="cyan"))
    click.echo()
    
    # Overall statistics
    click.echo("Processing Results")
    click.echo("-" * 80)
    click.echo(f"Total Patients:         {result.total_patients}")
    
    success_color = "green" if result.success_rate == 100 else "yellow"
    click.echo(
        f"Successful:             "
        + click.style(
            f"{result.successful_patients} ({result.success_rate:.1f}%)",
            fg=success_color
        )
    )
    
    if result.failed_patients > 0:
        click.echo(
            f"Failed:                 "
            + click.style(
                f"{result.failed_patients} ({100-result.success_rate:.1f}%)",
                fg="red"
            )
        )
    
    if result.duration_seconds:
        click.echo(f"Duration:               {result.duration_seconds:.1f}s")
    
    if result.average_processing_time_ms:
        click.echo(f"Avg Processing Time:    {result.average_processing_time_ms:.0f} ms/patient")
    
    click.echo()
    
    # Error summary if there were failures
    if result.failed_patients > 0 and "_error_report" in result.error_summary:
        error_report = result.error_summary["_error_report"]
        click.echo(error_report)
    
    click.echo(click.style("=" * 80, fg="cyan"))


def _save_json_output(
    result: BatchProcessingResult,
    output_path: Path,
    config_obj: Config,
    csv_file: Path
) -> None:
    """Save registration results to JSON file.
    
    Args:
        result: Batch processing result
        output_path: Path to output JSON file
        config_obj: Configuration used for registration
        csv_file: CSV file that was processed
    """
    logger.info(f"Saving results to JSON file: {output_path}")
    
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build JSON structure
    output_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "endpoint": config_obj.endpoints.pix_add_url,
            "csv_file": str(csv_file),
        },
        "summary": {
            "total_patients": result.total_patients,
            "successful": result.successful_patients,
            "failed": result.failed_patients,
            "success_rate": result.success_rate,
        },
        "patients": [
            {
                "patient_id": p.patient_id,
                "status": "success" if p.is_success else "failed",
                "pix_id": p.enterprise_id if p.is_success else None,
                "message": p.pix_add_message,
                "error": p.error_details if not p.is_success else None,
                "processing_time_ms": p.processing_time_ms,
            }
            for p in result.patient_results
        ],
    }
    
    # Add error statistics if available
    if "_error_statistics" in result.error_summary:
        output_data["error_summary"] = result.error_summary["_error_statistics"]
    
    # Write to file with pretty printing
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    
    click.echo()
    click.echo(
        click.style("✓ Results saved to: ", fg="green") + str(output_path)
    )
    
    logger.info(f"Results saved successfully to {output_path}")
