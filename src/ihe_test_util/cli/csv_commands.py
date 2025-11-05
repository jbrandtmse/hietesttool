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
    - Field format validation (phone, email, SSN, ZIP)
    - Date validation (future dates, unreasonable ages)
    - Batch validation (duplicate patient IDs, duplicate names)

    Exits with code 0 for success (warnings are OK), code 1 for validation errors.

    Example:
        ihe-test-util csv validate patients.csv
        ihe-test-util csv validate patients.csv --export-errors errors.csv
        ihe-test-util csv validate patients.csv --json
    """
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
