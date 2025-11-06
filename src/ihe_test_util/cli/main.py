"""Main CLI entry point for IHE Test Utility.

This module provides the main Click command group for the ihe-test-util CLI.
"""

from pathlib import Path
from typing import Optional

import click

from ihe_test_util import __version__
from ihe_test_util.cli.csv_commands import csv
from ihe_test_util.logging_audit import configure_logging


@click.group()
@click.version_option(version=__version__, prog_name="ihe-test-util")
@click.option("--verbose", is_flag=True, help="Enable verbose logging (DEBUG level)")
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to log file (default: ./logs/ihe-test-util.log)",
)
@click.option(
    "--redact-pii",
    is_flag=True,
    help="Redact PII (patient names, SSNs) from logs",
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    log_file: Optional[Path],
    redact_pii: bool,
) -> None:
    """IHE Test Utility - Testing tool for IHE transactions.
    
    Supports PIX Add (ITI-44) and ITI-41 (Provide and Register Document Set-b)
    transactions with mock endpoints for local testing.
    
    Common usage:
    
        # Validate a patient CSV file
        ihe-test-util csv validate patients.csv
        
        # Process CSV and display patient summary
        ihe-test-util csv process patients.csv
        
        # Enable verbose logging for debugging
        ihe-test-util --verbose csv validate patients.csv
    
    Use --help with any command for more information.
    """
    # Ensure context object exists for subcommands
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["redact_pii"] = redact_pii
    ctx.obj["log_file"] = log_file
    
    # Configure logging with comprehensive settings
    log_level = "DEBUG" if verbose else "INFO"
    configure_logging(level=log_level, log_file=log_file, redact_pii=redact_pii)


# Register command groups
cli.add_command(csv)


@cli.command()
def version() -> None:
    """Display version information."""
    click.echo(f"ihe-test-util version {__version__}")


if __name__ == "__main__":
    cli()
