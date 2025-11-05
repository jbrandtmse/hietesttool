"""Main CLI entry point for IHE Test Utility.

This module provides the main Click command group for the ihe-test-util CLI.
"""

from typing import Optional

import click

from ihe_test_util import __version__
from ihe_test_util.cli.csv_commands import csv


@click.group()
@click.version_option(version=__version__, prog_name="ihe-test-util")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """IHE Test Utility - Testing tool for IHE transactions.
    
    Supports PIX Add (ITI-44) and ITI-41 (Provide and Register Document Set-b)
    transactions with mock endpoints for local testing.
    
    Use --help with any command for more information.
    """
    # Ensure context object exists for subcommands
    ctx.ensure_object(dict)


# Register command groups
cli.add_command(csv)


@cli.command()
def version() -> None:
    """Display version information."""
    click.echo(f"ihe-test-util version {__version__}")


if __name__ == "__main__":
    cli()
