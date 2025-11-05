"""Main CLI entry point for IHE Test Utility.

This module provides the main Click command group for the ihe-test-util CLI.
"""

import logging
from typing import Optional

import click

from ihe_test_util import __version__
from ihe_test_util.cli.csv_commands import csv


def configure_logging(verbose: bool) -> None:
    """Configure logging for CLI.
    
    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )


@click.group()
@click.version_option(version=__version__, prog_name="ihe-test-util")
@click.option("--verbose", is_flag=True, help="Enable verbose logging (DEBUG level)")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
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
    
    # Configure logging based on verbose flag
    configure_logging(verbose)


# Register command groups
cli.add_command(csv)


@cli.command()
def version() -> None:
    """Display version information."""
    click.echo(f"ihe-test-util version {__version__}")


if __name__ == "__main__":
    cli()
