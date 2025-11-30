"""Submit CLI commands module for integrated PIX Add + ITI-41 workflow.

This module provides Click-based CLI commands for the complete patient
submission workflow: CSV parsing → CCD generation → PIX Add → ITI-41.

Examples:
    # Basic batch submission (direct syntax)
    $ ihe-test-util submit patients.csv

    # PIX-only registration (no ITI-41)
    $ ihe-test-util submit patients.csv --pix-only

    # ITI-41 only with prior PIX results
    $ ihe-test-util submit patients.csv --iti41-only --pix-results pix-results.json

    # Custom CCD template and config
    $ ihe-test-util submit patients.csv --ccd-template templates/ccd-custom.xml --config config/batch-testing.json

    # Resume from checkpoint
    $ ihe-test-util submit patients.csv --resume output/checkpoint.json

    # Development mode with HTTP transport
    $ ihe-test-util submit patients.csv --http --dry-run
"""

import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import click
from requests import ConnectionError, Timeout
from requests.exceptions import SSLError

from ihe_test_util.config.manager import load_config
from ihe_test_util.config.schema import BatchConfig, Config
from ihe_test_util.csv_parser.parser import parse_csv
from ihe_test_util.ihe_transactions.workflows import (
    IntegratedWorkflow,
    generate_integrated_workflow_summary,
    save_workflow_results_to_json,
)
from ihe_test_util.models.batch import BatchWorkflowResult, PatientWorkflowResult
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.utils.exceptions import ConfigurationError, ValidationError
from ihe_test_util.utils.output_manager import OutputManager, setup_output_directories

logger = logging.getLogger(__name__)


# =============================================================================
# Error Category Enum for Categorization (AC: 7)
# =============================================================================

class ErrorCategory(Enum):
    """Error categories for grouping and reporting errors."""
    NETWORK = "Network/Connection"
    VALIDATION = "Validation/Data"
    SERVER = "Server/Response"
    CERTIFICATE = "Certificate/Security"
    CONFIGURATION = "Configuration"
    UNKNOWN = "Unknown"


def categorize_cli_error(error: Exception) -> ErrorCategory:
    """Categorize an error for reporting purposes.
    
    Args:
        error: The exception to categorize
        
    Returns:
        ErrorCategory enum value
    """
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # SSL/Certificate errors (check BEFORE ConnectionError since SSLError inherits from it)
    if isinstance(error, SSLError):
        return ErrorCategory.CERTIFICATE
    if "ssl" in error_str or "certificate" in error_str or "tls" in error_str:
        return ErrorCategory.CERTIFICATE
    
    # Network errors
    if isinstance(error, (ConnectionError, Timeout)):
        return ErrorCategory.NETWORK
    if "connection" in error_str or "timeout" in error_str or "refused" in error_str:
        return ErrorCategory.NETWORK
    
    # Server errors
    if "500" in error_str or "503" in error_str or "server" in error_str:
        return ErrorCategory.SERVER
    if "soap" in error_str or "response" in error_str:
        return ErrorCategory.SERVER
    
    # Validation errors
    if isinstance(error, ValidationError):
        return ErrorCategory.VALIDATION
    if "validation" in error_str or "invalid" in error_str or "format" in error_str:
        return ErrorCategory.VALIDATION
    
    # Configuration errors
    if isinstance(error, ConfigurationError):
        return ErrorCategory.CONFIGURATION
    if "config" in error_str or "missing" in error_str:
        return ErrorCategory.CONFIGURATION
    
    return ErrorCategory.UNKNOWN


# =============================================================================
# PIX Results File Format for --iti41-only Mode (AC: 5)
# =============================================================================

def save_pix_results(result: BatchWorkflowResult, output_path: Path) -> None:
    """Save PIX Add results to JSON file for later ITI-41 processing.
    
    Creates a JSON file with PIX Add results that can be used with --iti41-only.
    
    Args:
        result: Batch workflow result containing PIX Add results
        output_path: Path to output JSON file
    """
    logger.info(f"Saving PIX results to {output_path}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    pix_results = {
        "batch_id": result.batch_id,
        "csv_file": result.csv_file,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patient_results": [
            {
                "patient_id": pr.patient_id,
                "pix_add_status": pr.pix_add_status,
                "pix_enterprise_id": pr.pix_enterprise_id,
                "pix_enterprise_id_oid": pr.pix_enterprise_id_oid,
                "pix_add_message": pr.pix_add_message,
            }
            for pr in result.patient_results
        ]
    }
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(pix_results, f, indent=2)
    
    logger.info(f"Saved PIX results for {len(result.patient_results)} patients")


def load_pix_results(pix_results_path: Path) -> dict:
    """Load PIX results from JSON file for ITI-41 only mode.
    
    Args:
        pix_results_path: Path to PIX results JSON file
        
    Returns:
        Dictionary with PIX results data
        
    Raises:
        ValidationError: If file format is invalid
    """
    logger.info(f"Loading PIX results from {pix_results_path}")
    
    if not pix_results_path.exists():
        raise ValidationError(
            f"PIX results file not found: {pix_results_path}. "
            "Run with --pix-only first to generate PIX results file."
        )
    
    with pix_results_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Validate required fields
    required_fields = ["batch_id", "csv_file", "patient_results"]
    for field in required_fields:
        if field not in data:
            raise ValidationError(
                f"Invalid PIX results file format: missing '{field}'. "
                "File may be corrupted or from incompatible version."
            )
    
    # Validate patient_results structure
    for idx, pr in enumerate(data.get("patient_results", [])):
        if "patient_id" not in pr or "pix_add_status" not in pr:
            raise ValidationError(
                f"Invalid PIX results file format: patient {idx} missing required fields. "
                "File may be corrupted."
            )
    
    logger.info(f"Loaded PIX results for {len(data['patient_results'])} patients")
    return data


# =============================================================================
# Submit CLI Group with Default Command (AC: 1)
# =============================================================================

@click.group(name="submit", invoke_without_command=True)
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path), required=False)
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
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for organized results (logs/, results/, documents/, audit/)",
)
@click.option(
    "--checkpoint-interval",
    type=int,
    default=None,
    help="Save checkpoint every N patients (enables resume capability)",
)
@click.option(
    "--resume",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Resume from checkpoint file",
)
@click.option(
    "--fail-fast",
    is_flag=True,
    help="Stop processing on first patient failure",
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
@click.option(
    "--pix-only",
    is_flag=True,
    help="Execute only PIX Add registration (skip ITI-41)",
)
@click.option(
    "--iti41-only",
    is_flag=True,
    help="Execute only ITI-41 submission (requires --pix-results)",
)
@click.option(
    "--pix-results",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="PIX results file from prior --pix-only run (required with --iti41-only)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress real-time progress output",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed per-operation logging",
)
@click.option(
    "--show-errors",
    is_flag=True,
    help="Display full error details at end of batch",
)
@click.pass_context
def submit(
    ctx: click.Context,
    csv_file: Optional[Path],
    config: Optional[Path],
    ccd_template: Optional[Path],
    output: Optional[Path],
    output_dir: Optional[Path],
    checkpoint_interval: Optional[int],
    resume: Optional[Path],
    fail_fast: bool,
    dry_run: bool,
    http: bool,
    pix_only: bool,
    iti41_only: bool,
    pix_results: Optional[Path],
    quiet: bool,
    verbose: bool,
    show_errors: bool,
) -> None:
    """Process patients through complete PIX Add + ITI-41 workflow.
    
    Execute the complete patient submission workflow: CSV parsing → CCD generation 
    → PIX Add registration → ITI-41 document submission.
    
    \b
    USAGE EXAMPLES:
    
    \b
    Basic batch submission:
      $ ihe-test-util submit patients.csv
    
    \b
    PIX-only registration (no ITI-41):
      $ ihe-test-util submit patients.csv --pix-only
    
    \b
    ITI-41 only with prior PIX results:
      $ ihe-test-util submit patients.csv --iti41-only --pix-results pix-results.json
    
    \b
    Use custom CCD template:
      $ ihe-test-util submit patients.csv --ccd-template templates/ccd-custom.xml
    
    \b
    Save results and enable checkpoints:
      $ ihe-test-util submit patients.csv --output results.json --checkpoint-interval 10
    
    \b
    Resume from checkpoint:
      $ ihe-test-util submit patients.csv --resume output/checkpoint.json
    
    \b
    Dry-run validation:
      $ ihe-test-util submit patients.csv --dry-run
    
    \b
    Development mode with HTTP:
      $ ihe-test-util submit patients.csv --http --config config/batch-development.json
    
    \b
    EXIT CODES:
        0: All patients processed successfully
        1: Validation error (CSV, config, certificates)
        2: Some transactions failed (partial success)
        3: Critical error (SSL, missing config)
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # If csv_file provided directly (not via subcommand), run the workflow
    if csv_file is not None and ctx.invoked_subcommand is None:
        # Validate mutually exclusive options
        if pix_only and iti41_only:
            raise click.UsageError(
                "Cannot use --pix-only and --iti41-only together. "
                "Choose one workflow mode."
            )
        
        if iti41_only and not pix_results:
            raise click.UsageError(
                "--iti41-only requires --pix-results. "
                "Run with --pix-only first to generate PIX results file."
            )
        
        if pix_results and not iti41_only:
            raise click.UsageError(
                "--pix-results can only be used with --iti41-only."
            )
        
        # Invoke the batch command with all options
        ctx.invoke(
            batch,
            csv_file=csv_file,
            config=config,
            ccd_template=ccd_template,
            output=output,
            output_dir=output_dir,
            checkpoint_interval=checkpoint_interval,
            resume=resume,
            fail_fast=fail_fast,
            dry_run=dry_run,
            http=http,
            pix_only=pix_only,
            iti41_only=iti41_only,
            pix_results=pix_results,
            quiet=quiet,
            verbose=verbose,
            show_errors=show_errors,
        )
    elif ctx.invoked_subcommand is None:
        # No csv_file and no subcommand - show help
        click.echo(ctx.get_help())


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
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for organized results (logs/, results/, documents/, audit/)",
)
@click.option(
    "--checkpoint-interval",
    type=int,
    default=None,
    help="Save checkpoint every N patients (enables resume capability)",
)
@click.option(
    "--resume",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Resume from checkpoint file",
)
@click.option(
    "--fail-fast",
    is_flag=True,
    help="Stop processing on first patient failure",
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
@click.option(
    "--pix-only",
    is_flag=True,
    help="Execute only PIX Add registration (skip ITI-41)",
)
@click.option(
    "--iti41-only",
    is_flag=True,
    help="Execute only ITI-41 submission (requires --pix-results)",
)
@click.option(
    "--pix-results",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="PIX results file from prior --pix-only run (required with --iti41-only)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress real-time progress output",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed per-operation logging",
)
@click.option(
    "--show-errors",
    is_flag=True,
    help="Display full error details at end of batch",
)
@click.pass_context
def batch(
    ctx: click.Context,
    csv_file: Path,
    config: Optional[Path],
    ccd_template: Optional[Path],
    output: Optional[Path],
    output_dir: Optional[Path],
    checkpoint_interval: Optional[int],
    resume: Optional[Path],
    fail_fast: bool,
    dry_run: bool,
    http: bool,
    pix_only: bool,
    iti41_only: bool,
    pix_results: Optional[Path],
    quiet: bool,
    verbose: bool,
    show_errors: bool,
) -> None:
    """Process patients through complete PIX Add + ITI-41 workflow.
    
    Orchestrates the complete patient submission workflow:
    1. Parse CSV file for patient demographics
    2. Generate personalized CCD documents
    3. Register patients via PIX Add (ITI-44)
    4. Submit documents via ITI-41 (Provide and Register)
    
    Displays real-time progress with color-coded results. Patients are processed
    sequentially, and PIX Add must succeed before ITI-41 submission.
    
    \b
    WORKFLOW MODES:
    
    \b
    Full Workflow (default):
      Executes PIX Add + ITI-41 for each patient.
    
    \b
    PIX-Only Mode (--pix-only):
      Only executes PIX Add registration. ITI-41 is skipped.
      Saves PIX results to JSON for later ITI-41 processing.
    
    \b
    ITI-41 Only Mode (--iti41-only --pix-results <file>):
      Only executes ITI-41 submission using prior PIX Add results.
      Skips patients that failed PIX Add in prior run.
    """
    start_time = time.time()
    
    # Validate mutually exclusive options
    if pix_only and iti41_only:
        raise click.UsageError(
            "Cannot use --pix-only and --iti41-only together. "
            "Choose one workflow mode."
        )
    
    if iti41_only and not pix_results:
        raise click.UsageError(
            "--iti41-only requires --pix-results. "
            "Run with --pix-only first to generate PIX results file."
        )
    
    if pix_results and not iti41_only:
        raise click.UsageError(
            "--pix-results can only be used with --iti41-only."
        )
    
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
        
        # Build batch configuration from CLI options
        batch_config = _build_batch_config(
            checkpoint_interval=checkpoint_interval,
            fail_fast=fail_fast,
            output_dir=output_dir,
        )
        
        # Set up output directories if output_dir specified
        output_manager: Optional[OutputManager] = None
        if output_dir:
            output_manager = OutputManager(output_dir)
            output_paths = output_manager.setup_directories()
            logger.info(f"Output directories created at: {output_dir}")
        
        # Determine checkpoint file path
        checkpoint_file: Optional[Path] = None
        if checkpoint_interval or resume:
            if output_manager:
                checkpoint_file = output_manager.get_checkpoint_path(
                    f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
                )
            elif output:
                checkpoint_file = output.parent / f"checkpoint-{output.stem}.json"
            else:
                checkpoint_file = Path("output") / "checkpoint.json"
        
        # If resuming, use the specified checkpoint file
        if resume:
            checkpoint_file = resume
            click.echo(click.style(f"Resuming from checkpoint: {resume}", fg="yellow"))
        
        # Display header
        if not quiet:
            _display_header(pix_only=pix_only, iti41_only=iti41_only)
        
        # Parse CSV to get patient count
        logger.info(f"Parsing CSV file: {csv_file}")
        df, validation_result = parse_csv(csv_file, validate=True)
        total_patients = len(df)
        
        if not quiet:
            click.echo(f"CSV File:           {csv_file}")
            click.echo(f"Total Patients:     {total_patients}")
            click.echo(f"PIX Add Endpoint:   {config_obj.endpoints.pix_add_url}")
            if not pix_only:
                click.echo(f"ITI-41 Endpoint:    {config_obj.endpoints.iti41_url}")
            click.echo()
        
        # Determine CCD template path
        template_path = ccd_template or _get_default_ccd_template()
        if not quiet:
            click.echo(f"CCD Template:       {template_path}")
        
        # Display workflow mode
        if not quiet:
            if pix_only:
                click.echo(
                    click.style("Workflow Mode:      ", fg="cyan") +
                    click.style("PIX-ONLY", fg="yellow", bold=True) +
                    " (ITI-41 will be skipped)"
                )
            elif iti41_only:
                click.echo(
                    click.style("Workflow Mode:      ", fg="cyan") +
                    click.style("ITI-41 ONLY", fg="yellow", bold=True) +
                    f" (using PIX results from {pix_results})"
                )
            else:
                click.echo(
                    click.style("Workflow Mode:      ", fg="cyan") +
                    click.style("FULL WORKFLOW", fg="green", bold=True) +
                    " (PIX Add + ITI-41)"
                )
        
        # Display batch configuration
        if not quiet and (batch_config.checkpoint_interval != 50 or batch_config.fail_fast):
            click.echo()
            click.echo("Batch Configuration:")
            if checkpoint_interval:
                click.echo(f"  Checkpoint Interval: Every {checkpoint_interval} patients")
            if batch_config.fail_fast:
                click.echo(f"  Fail-Fast Mode:      {click.style('ENABLED', fg='yellow')}")
            if output_dir:
                click.echo(f"  Output Directory:    {output_dir}")
        click.echo()
        
        # Initialize workflow with batch config
        logger.info("Initializing integrated workflow")
        workflow = IntegratedWorkflow(config_obj, template_path, batch_config)
        
        # Load PIX results if ITI-41 only mode
        prior_pix_results: Optional[dict] = None
        if iti41_only and pix_results:
            prior_pix_results = load_pix_results(pix_results)
        
        # Process batch with real-time progress display
        if not quiet:
            click.echo(click.style("Processing patients...", fg="cyan"))
            click.echo()
        
        # Execute workflow based on mode
        if pix_only:
            result = _execute_pix_only_workflow(
                workflow=workflow,
                csv_file=csv_file,
                checkpoint_file=checkpoint_file,
                total_patients=total_patients,
                quiet=quiet,
                verbose=verbose,
            )
        elif iti41_only:
            result = _execute_iti41_only_workflow(
                workflow=workflow,
                csv_file=csv_file,
                pix_results_data=prior_pix_results,
                checkpoint_file=checkpoint_file,
                total_patients=total_patients,
                quiet=quiet,
                verbose=verbose,
            )
        else:
            result = _execute_full_workflow(
                workflow=workflow,
                csv_file=csv_file,
                checkpoint_file=checkpoint_file,
                total_patients=total_patients,
                quiet=quiet,
                verbose=verbose,
            )
        
        # Display per-patient results with color coding
        if not quiet:
            _display_patient_results(result, verbose=verbose)
        
        # Display summary report with stage breakdown
        click.echo()
        summary = generate_integrated_workflow_summary(result)
        _display_summary_report_with_stages(result, pix_only=pix_only, iti41_only=iti41_only)
        
        # Display error details if requested
        if show_errors and result.pix_add_failed_count + result.iti41_failed_count > 0:
            _display_error_details(result)
        
        # Save JSON output if requested
        if output:
            save_workflow_results_to_json(result, output)
            click.echo()
            click.echo(
                click.style("✓ Results saved to: ", fg="green") + str(output)
            )
        
        # Save PIX results if pix-only mode
        if pix_only:
            pix_output_path = output or Path("output") / f"pix-results-{result.batch_id}.json"
            save_pix_results(result, pix_output_path)
            click.echo(
                click.style("✓ PIX results saved to: ", fg="green") + str(pix_output_path)
            )
            click.echo(
                click.style("  Use with: ", fg="cyan") +
                f"ihe-test-util submit {csv_file} --iti41-only --pix-results {pix_output_path}"
            )
        
        # Save to organized output directory if specified
        if output_manager and result:
            # Save results JSON
            results_path = output_manager.write_result_file(
                result.to_dict(),
                f"batch-{result.batch_id}-results.json"
            )
            click.echo(
                click.style("✓ Results saved to: ", fg="green") + str(results_path)
            )
            
            # Save summary text
            summary_path = output_manager.write_summary_file(
                summary,
                result.batch_id
            )
            click.echo(
                click.style("✓ Summary saved to: ", fg="green") + str(summary_path)
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


# =============================================================================
# Workflow Execution Functions
# =============================================================================

def _execute_full_workflow(
    workflow: IntegratedWorkflow,
    csv_file: Path,
    checkpoint_file: Optional[Path],
    total_patients: int,
    quiet: bool,
    verbose: bool,
) -> BatchWorkflowResult:
    """Execute full PIX Add + ITI-41 workflow with progress display.
    
    Args:
        workflow: Initialized IntegratedWorkflow instance
        csv_file: Path to CSV file
        checkpoint_file: Optional checkpoint file path
        total_patients: Total number of patients in CSV
        quiet: Suppress progress output
        verbose: Show detailed logging
        
    Returns:
        BatchWorkflowResult with processing results
    """
    if not quiet:
        # Use click progressbar for real-time progress
        with click.progressbar(
            length=total_patients,
            label="Processing",
            show_eta=True,
            show_percent=True,
            item_show_func=lambda x: f"Patient {x}" if x else "",
        ) as bar:
            # Custom progress callback
            def progress_callback(patient_idx: int, patient_id: str, status: str) -> None:
                bar.update(1)
                if verbose:
                    click.echo(f"\n  → Patient {patient_idx + 1}/{total_patients}: {patient_id} - {status}")
            
            # Process batch with progress tracking
            result = workflow.process_batch(csv_file, checkpoint_file=checkpoint_file)
            
            # Update progress bar to completion
            remaining = total_patients - bar.pos
            if remaining > 0:
                bar.update(remaining)
    else:
        # Silent processing
        result = workflow.process_batch(csv_file, checkpoint_file=checkpoint_file)
    
    return result


def _execute_pix_only_workflow(
    workflow: IntegratedWorkflow,
    csv_file: Path,
    checkpoint_file: Optional[Path],
    total_patients: int,
    quiet: bool,
    verbose: bool,
) -> BatchWorkflowResult:
    """Execute PIX Add only workflow (skip ITI-41).
    
    Args:
        workflow: Initialized IntegratedWorkflow instance
        csv_file: Path to CSV file
        checkpoint_file: Optional checkpoint file path
        total_patients: Total number of patients in CSV
        quiet: Suppress progress output
        verbose: Show detailed logging
        
    Returns:
        BatchWorkflowResult with PIX Add results (ITI-41 marked as skipped)
    """
    # For PIX-only, we use the standard workflow but mark all ITI-41 as skipped
    # The workflow class handles this based on a pix_only flag
    
    # Set pix_only mode on the workflow's batch config
    workflow._batch_config.pix_only_mode = True
    
    return _execute_full_workflow(
        workflow=workflow,
        csv_file=csv_file,
        checkpoint_file=checkpoint_file,
        total_patients=total_patients,
        quiet=quiet,
        verbose=verbose,
    )


def _execute_iti41_only_workflow(
    workflow: IntegratedWorkflow,
    csv_file: Path,
    pix_results_data: dict,
    checkpoint_file: Optional[Path],
    total_patients: int,
    quiet: bool,
    verbose: bool,
) -> BatchWorkflowResult:
    """Execute ITI-41 only workflow using prior PIX results.
    
    Args:
        workflow: Initialized IntegratedWorkflow instance
        csv_file: Path to CSV file
        pix_results_data: PIX results from prior run
        checkpoint_file: Optional checkpoint file path
        total_patients: Total number of patients in CSV
        quiet: Suppress progress output
        verbose: Show detailed logging
        
    Returns:
        BatchWorkflowResult with ITI-41 results
    """
    # Build PIX results lookup for the workflow
    pix_lookup = {
        pr["patient_id"]: pr
        for pr in pix_results_data.get("patient_results", [])
    }
    
    # Set ITI-41 only mode with PIX results
    workflow._batch_config.iti41_only_mode = True
    workflow._batch_config.pix_results_lookup = pix_lookup
    
    return _execute_full_workflow(
        workflow=workflow,
        csv_file=csv_file,
        checkpoint_file=checkpoint_file,
        total_patients=total_patients,
        quiet=quiet,
        verbose=verbose,
    )


# =============================================================================
# Display Functions
# =============================================================================

def _display_header(pix_only: bool = False, iti41_only: bool = False) -> None:
    """Display workflow header."""
    click.echo()
    click.echo(click.style("=" * 80, fg="cyan"))
    
    if pix_only:
        title = "PIX ADD ONLY WORKFLOW"
    elif iti41_only:
        title = "ITI-41 ONLY WORKFLOW"
    else:
        title = "INTEGRATED PIX ADD + ITI-41 WORKFLOW"
    
    click.echo(click.style(title, fg="cyan", bold=True))
    click.echo(click.style("=" * 80, fg="cyan"))
    click.echo()


def _display_patient_results(result: BatchWorkflowResult, verbose: bool = False) -> None:
    """Display per-patient results with color coding.
    
    Args:
        result: Batch workflow result with patient details
        verbose: Show detailed per-operation timing
    """
    for idx, patient_result in enumerate(result.patient_results, 1):
        patient_id = patient_result.patient_id
        
        # Determine status color and message
        if patient_result.is_fully_successful:
            # Green for full success
            status = click.style("✓ Complete", fg="green")
            message = f"PIX ID: {patient_result.pix_enterprise_id or 'N/A'}, Doc: {patient_result.document_id or 'N/A'}"
        elif patient_result.pix_add_status == "success" and patient_result.iti41_status == "skipped":
            # Yellow for PIX-only success
            status = click.style("✓ PIX Only", fg="yellow")
            message = f"PIX ID: {patient_result.pix_enterprise_id or 'N/A'} (ITI-41 skipped)"
        elif patient_result.pix_add_status == "success" and patient_result.iti41_status != "success":
            # Yellow for partial success (PIX succeeded, ITI-41 failed)
            status = click.style("⚠ Partial", fg="yellow")
            message = f"PIX OK, ITI-41: {patient_result.iti41_message or 'failed'}"
        elif patient_result.pix_add_status == "skipped":
            # Cyan for PIX skipped (ITI-41 only mode)
            status = click.style("→ ITI-41", fg="cyan")
            iti41_status = "✓" if patient_result.iti41_status == "success" else "✗"
            message = f"PIX skipped, ITI-41: {iti41_status} {patient_result.iti41_message or ''}"
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
        
        # Verbose: show timing breakdown
        if verbose and patient_result.total_time_ms:
            click.echo(f"    Timing: CCD={patient_result.pix_add_time_ms or 0}ms, "
                      f"PIX={patient_result.pix_add_time_ms or 0}ms, "
                      f"ITI-41={patient_result.iti41_time_ms or 0}ms, "
                      f"Total={patient_result.total_time_ms}ms")


def _display_summary_report_with_stages(
    result: BatchWorkflowResult,
    pix_only: bool = False,
    iti41_only: bool = False,
) -> None:
    """Display summary report with stage-by-stage breakdown.
    
    Args:
        result: Batch workflow result
        pix_only: Whether this was a PIX-only run
        iti41_only: Whether this was an ITI-41 only run
    """
    click.echo(click.style("=" * 80, fg="cyan"))
    click.echo(click.style("WORKFLOW SUMMARY", fg="cyan", bold=True))
    click.echo(click.style("=" * 80, fg="cyan"))
    click.echo()
    
    # Stage 1: CSV Parsing
    click.echo(click.style("Stage 1: CSV Parsing", bold=True))
    click.echo("-" * 40)
    csv_count = len([pr for pr in result.patient_results if pr.csv_parsed])
    csv_errors = result.total_patients - csv_count
    click.echo(f"  Patients Parsed:    {csv_count}")
    if csv_errors > 0:
        click.echo(click.style(f"  Parse Errors:       {csv_errors}", fg="red"))
    click.echo()
    
    # Stage 2: CCD Generation
    click.echo(click.style("Stage 2: CCD Generation", bold=True))
    click.echo("-" * 40)
    ccd_count = len([pr for pr in result.patient_results if pr.ccd_generated])
    ccd_errors = csv_count - ccd_count
    click.echo(f"  Documents Generated: {ccd_count}")
    if ccd_errors > 0:
        click.echo(click.style(f"  Generation Errors:   {ccd_errors}", fg="red"))
    click.echo()
    
    # Stage 3: PIX Add
    if not iti41_only:
        click.echo(click.style("Stage 3: PIX Add Registration", bold=True))
        click.echo("-" * 40)
        pix_success_color = "green" if result.pix_add_success_count == result.total_patients else "yellow"
        click.echo(
            f"  Successful:         " +
            click.style(f"{result.pix_add_success_count} ({result.pix_add_success_rate:.1f}%)", fg=pix_success_color)
        )
        if result.pix_add_failed_count > 0:
            click.echo(
                f"  Failed:             " +
                click.style(f"{result.pix_add_failed_count}", fg="red")
            )
        click.echo()
    else:
        click.echo(click.style("Stage 3: PIX Add (from prior run)", bold=True))
        click.echo("-" * 40)
        click.echo(f"  Status:             Using prior PIX results")
        click.echo()
    
    # Stage 4: ITI-41
    if not pix_only:
        click.echo(click.style("Stage 4: ITI-41 Document Submission", bold=True))
        click.echo("-" * 40)
        iti41_success_color = "green" if result.iti41_success_count == result.total_patients else "yellow"
        click.echo(
            f"  Successful:         " +
            click.style(f"{result.iti41_success_count} ({result.iti41_success_rate:.1f}%)", fg=iti41_success_color)
        )
        if result.iti41_failed_count > 0:
            click.echo(
                f"  Failed:             " +
                click.style(f"{result.iti41_failed_count}", fg="red")
            )
        if result.iti41_skipped_count > 0:
            click.echo(
                f"  Skipped:            " +
                click.style(f"{result.iti41_skipped_count}", fg="yellow") +
                " (PIX Add failed)"
            )
        click.echo()
    else:
        click.echo(click.style("Stage 4: ITI-41 (skipped - PIX-only mode)", bold=True))
        click.echo("-" * 40)
        click.echo(f"  Status:             Skipped (--pix-only)")
        click.echo()
    
    # Overall Results
    click.echo(click.style("Overall Results", bold=True))
    click.echo("-" * 40)
    click.echo(f"  Total Patients:     {result.total_patients}")
    
    full_success_color = "green" if result.fully_successful_count == result.total_patients else "yellow"
    click.echo(
        f"  Fully Successful:   " +
        click.style(f"{result.fully_successful_count} ({result.full_success_rate:.1f}%)", fg=full_success_color)
    )
    
    # Timing
    if result.total_duration_seconds:
        click.echo(f"  Duration:           {result.total_duration_seconds:.1f}s")
    
    if result.average_patient_time_seconds:
        click.echo(f"  Avg Time/Patient:   {result.average_patient_time_seconds:.2f}s")
    
    # Throughput
    if result.throughput_per_minute:
        click.echo(f"  Throughput:         {result.throughput_per_minute:.1f} patients/minute")
    
    click.echo()
    click.echo(click.style("=" * 80, fg="cyan"))


def _display_error_details(result: BatchWorkflowResult) -> None:
    """Display detailed error information with categorization.
    
    Args:
        result: Batch workflow result with error details
    """
    click.echo()
    click.echo(click.style("Error Details", fg="red", bold=True))
    click.echo(click.style("-" * 80, fg="red"))
    
    # Collect and categorize errors
    error_categories: dict[str, list[tuple[str, str]]] = {
        cat.value: [] for cat in ErrorCategory
    }
    
    for pr in result.patient_results:
        if pr.error_message:
            # Simple categorization based on error message
            if "connection" in pr.error_message.lower() or "timeout" in pr.error_message.lower():
                category = ErrorCategory.NETWORK.value
            elif "ssl" in pr.error_message.lower() or "certificate" in pr.error_message.lower():
                category = ErrorCategory.CERTIFICATE.value
            elif "500" in pr.error_message or "server" in pr.error_message.lower():
                category = ErrorCategory.SERVER.value
            elif "validation" in pr.error_message.lower() or "invalid" in pr.error_message.lower():
                category = ErrorCategory.VALIDATION.value
            elif "config" in pr.error_message.lower():
                category = ErrorCategory.CONFIGURATION.value
            else:
                category = ErrorCategory.UNKNOWN.value
            
            error_categories[category].append((pr.patient_id, pr.error_message))
    
    # Display errors by category
    for category, errors in error_categories.items():
        if errors:
            click.echo()
            click.echo(click.style(f"{category} ({len(errors)} errors):", fg="yellow", bold=True))
            for patient_id, error_msg in errors[:5]:  # Show first 5
                click.echo(f"  • {patient_id}: {error_msg[:100]}...")
            if len(errors) > 5:
                click.echo(f"  ... and {len(errors) - 5} more")
    
    # Top 3 most common errors
    click.echo()
    click.echo(click.style("Top 3 Most Common Errors:", fg="yellow", bold=True))
    all_errors = [pr.error_message for pr in result.patient_results if pr.error_message]
    error_counts = Counter(all_errors)
    for idx, (error, count) in enumerate(error_counts.most_common(3), 1):
        click.echo(f"  {idx}. ({count} patients) {error[:80]}...")
    
    click.echo()


# =============================================================================
# Helper Functions
# =============================================================================

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


def _build_batch_config(
    checkpoint_interval: Optional[int],
    fail_fast: bool,
    output_dir: Optional[Path],
) -> BatchConfig:
    """Build BatchConfig from CLI options.
    
    Args:
        checkpoint_interval: Checkpoint interval from CLI
        fail_fast: Fail-fast flag from CLI
        output_dir: Output directory from CLI
        
    Returns:
        BatchConfig instance with CLI options applied
    """
    config_kwargs = {}
    
    if checkpoint_interval is not None:
        config_kwargs["checkpoint_interval"] = checkpoint_interval
    
    if fail_fast:
        config_kwargs["fail_fast"] = True
    
    if output_dir:
        config_kwargs["output_dir"] = output_dir
    
    return BatchConfig(**config_kwargs)
