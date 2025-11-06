"""CSV-related CLI commands for IHE Test Utility.

This module provides CLI commands for CSV file operations including validation
and error reporting.
"""

import json as json_lib
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from ihe_test_util.csv_parser.parser import parse_csv
from ihe_test_util.csv_parser.validator import export_invalid_rows
from ihe_test_util.utils.exceptions import ValidationError

logger = logging.getLogger(__name__)


@click.group()
def csv() -> None:
    """CSV file operations and validation commands."""
    pass


@csv.command("validate")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--export-errors",
    type=click.Path(path_type=Path),
    help="Export invalid rows to CSV file",
)
@click.option("--json", "json_output", is_flag=True, help="Output results as JSON")
def validate_csv_command(
    file: Path, export_errors: Optional[Path], json_output: bool
) -> None:
    """Validate patient demographics CSV file.

    Performs comprehensive validation including:
    - Required field validation (first_name, last_name, dob, gender, patient_id_oid)
    - Field format validation (phone, email, SSN, ZIP)
    - Date validation (future dates, unreasonable ages)
    - Batch validation (duplicate patient IDs, duplicate names)

    Exits with code 0 for success (warnings are OK), code 1 for validation errors.

    Examples:

        # Basic validation with color-coded output
        ihe-test-util csv validate patients.csv

        # Validate and export invalid rows to a separate file
        ihe-test-util csv validate patients.csv --export-errors invalid_rows.csv

        # Output validation results in JSON format for automation
        ihe-test-util csv validate patients.csv --json

        # Validate with verbose logging for debugging
        ihe-test-util --verbose csv validate patients.csv

        # Capture output to log file
        ihe-test-util csv validate patients.csv > validation.log 2>&1
    """
    # Suppress console logging when JSON output is requested
    root_logger = logging.getLogger()
    console_handler = None
    original_level = None
    
    if json_output:
        # Find and disable console handler
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not hasattr(handler, 'baseFilename'):
                console_handler = handler
                original_level = handler.level
                handler.setLevel(logging.CRITICAL + 1)  # Effectively disable
                break
    
    try:
        logger.info(f"Validating CSV file: {file}")
        df, result = parse_csv(file, validate=True)

        if result is None:
            # Should not happen with validate=True, but handle gracefully
            click.secho("Validation skipped (no result returned)", fg="yellow")
            sys.exit(0)

        # Check for validation errors and fail if present
        if result.has_errors:
            if json_output:
                # Output JSON even on error for machine consumption
                output_dict = result.to_dict()
                click.echo(json_lib.dumps(output_dict, indent=2))
            else:
                # Output human-readable report
                report = result.format_report()
                click.secho(report, fg="red", err=True)

            # Export errors if requested
            if export_errors:
                export_invalid_rows(df, result, export_errors)
                if not json_output:
                    click.echo(f"\nInvalid rows exported to: {export_errors}")

            logger.error("Validation failed with errors")
            sys.exit(1)

        # No errors - output success report
        if json_output:
            # Output JSON format for machine consumption
            output_dict = result.to_dict()
            click.echo(json_lib.dumps(output_dict, indent=2))
        else:
            # Output human-readable report
            report = result.format_report()

            # Color-coded output based on validation status
            if result.has_warnings:
                click.secho(report, fg="yellow")
            else:
                click.secho(report, fg="green")

        # Success - exit with code 0
        logger.info("Validation complete. Exit code: 0")
        sys.exit(0)

    except ValidationError as e:
        # ValidationError raised when basic parsing fails
        click.secho(f"Validation Error: {e}", fg="red", err=True)
        logger.error(f"Validation error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        click.secho(f"File not found: {e}", fg="red", err=True)
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Unexpected error: {e}", fg="red", err=True)
        logger.exception("Unexpected error during CSV validation")
        sys.exit(1)
    finally:
        # Restore console handler if it was disabled
        if json_output and console_handler and original_level is not None:
            console_handler.setLevel(original_level)


@csv.command("process")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output directory (default: current directory)",
)
@click.option("--seed", type=int, help="Seed for reproducible patient ID generation")
def process_csv_command(
    file: Path, output: Optional[Path], seed: Optional[int]
) -> None:
    """Process and display patient demographics from CSV file.

    Validates the CSV file and displays a summary of parsed patient records.
    Automatically generates patient IDs for rows with missing IDs.

    With --seed option, ID generation is reproducible across runs, enabling
    consistent test data generation.

    Examples:

        # Process CSV and display patient summary
        ihe-test-util csv process patients.csv

        # Process with reproducible ID generation
        ihe-test-util csv process patients.csv --seed 42

        # Process and specify output directory
        ihe-test-util csv process patients.csv --output ./output

        # Process with verbose logging
        ihe-test-util --verbose csv process patients.csv
    """
    try:
        click.echo(f"Processing CSV file: {file}")
        logger.info(f"Processing CSV file: {file}")

        # Parse and validate CSV
        df, result = parse_csv(file, seed=seed, validate=True)

        if result is None:
            # Should not happen with validate=True, but handle gracefully
            click.secho(
                "Warning: Validation was not performed", fg="yellow", err=True
            )
            logger.warning("Validation result is None")

        # Check for validation errors
        if result and result.has_errors:
            click.secho("Validation failed with errors:", fg="red", err=True)
            report = result.format_report()
            click.secho(report, fg="red", err=True)
            logger.error("Processing failed due to validation errors")
            sys.exit(1)

        # Count auto-generated vs provided IDs
        generated_count = 0
        provided_count = 0

        for patient_id in df["patient_id"]:
            if patient_id.startswith("TEST-"):
                generated_count += 1
            else:
                provided_count += 1

        # Display summary
        click.echo(f"Total patients: {len(df)}")
        click.echo(f"  - Auto-generated IDs: {generated_count}")
        click.echo(f"  - Provided IDs: {provided_count}")

        # Display patient records
        click.echo("\nPatient Summary:")
        for idx, row in df.iterrows():
            patient_num = idx + 1
            patient_id = row["patient_id"]
            last_name = row["last_name"]
            first_name = row["first_name"]
            dob = row["dob"]
            gender = row["gender"]

            click.echo(
                f"  {patient_num}. {patient_id} | {last_name}, {first_name} | {dob} | {gender}"
            )

        # Display warnings if any
        if result and result.has_warnings:
            click.echo()
            click.secho(
                f"Note: {len(result.all_warnings)} warning(s) found during validation",
                fg="yellow",
            )
            click.echo("Use 'csv validate' command for detailed validation report")

        click.echo()
        click.secho("Processing complete", fg="green")
        logger.info("CSV processing complete. Exit code: 0")
        sys.exit(0)

    except ValidationError as e:
        click.secho(f"Validation Error: {e}", fg="red", err=True)
        logger.error(f"Validation error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        click.secho(
            f"Error: File not found: {file}. Ensure file path is correct.",
            fg="red",
            err=True,
        )
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Unexpected error: {e}", fg="red", err=True)
        logger.exception("Unexpected error during CSV processing")
        sys.exit(1)
