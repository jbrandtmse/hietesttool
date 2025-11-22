"""Main CLI entry point for IHE Test Utility.

This module provides the main Click command group for the ihe-test-util CLI.
"""

from pathlib import Path
from typing import Optional

import click

from ihe_test_util import __version__
from ihe_test_util.cli.csv_commands import csv
from ihe_test_util.cli.mock_commands import mock_group
from ihe_test_util.cli.pix_commands import pix_add
from ihe_test_util.cli.saml_commands import saml_group
from ihe_test_util.cli.template_commands import template_group
from ihe_test_util.config import load_config
from ihe_test_util.logging_audit import configure_logging
from ihe_test_util.utils.exceptions import ConfigurationError


@click.group()
@click.version_option(version=__version__, prog_name="ihe-test-util")
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file (default: ./config/config.json)",
)
@click.option("--verbose", is_flag=True, help="Enable verbose logging (DEBUG level)")
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to log file (overrides config file)",
)
@click.option(
    "--redact-pii",
    is_flag=True,
    help="Redact PII (patient names, SSNs) from logs",
)
@click.pass_context
def cli(
    ctx: click.Context,
    config: Optional[Path],
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
        
        # Use custom configuration file
        ihe-test-util --config custom/config.json csv validate patients.csv
        
        # Enable verbose logging for debugging
        ihe-test-util --verbose csv validate patients.csv
    
    Use --help with any command for more information.
    """
    # Ensure context object exists for subcommands
    ctx.ensure_object(dict)
    
    # Load configuration
    try:
        config_obj = load_config(config)
        ctx.obj["config"] = config_obj
    except ConfigurationError as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        ctx.exit(1)
    
    # Store CLI flags in context
    ctx.obj["verbose"] = verbose
    ctx.obj["redact_pii"] = redact_pii
    ctx.obj["log_file"] = log_file
    
    # Configure logging with precedence: CLI flags > config file > defaults
    log_level = "DEBUG" if verbose else config_obj.logging.level
    log_file_path = log_file if log_file else config_obj.logging.log_file
    redact_pii_setting = redact_pii if redact_pii else config_obj.logging.redact_pii
    
    configure_logging(
        level=log_level, log_file=log_file_path, redact_pii=redact_pii_setting
    )


# Register command groups
cli.add_command(csv)
cli.add_command(mock_group)
cli.add_command(pix_add)
cli.add_command(saml_group)
cli.add_command(template_group)


@cli.group()
def config() -> None:
    """Configuration management commands."""
    pass


@config.command()
@click.argument("config_file", type=click.Path(exists=True, path_type=Path))
def validate(config_file: Path) -> None:
    """Validate a configuration file.
    
    Args:
        config_file: Path to configuration file to validate
        
    Example:
        ihe-test-util config validate config/config.json
    """
    try:
        # Try to load and validate the configuration
        config_obj = load_config(config_file)
        
        # If we get here, validation succeeded
        click.echo(click.style("✓", fg="green", bold=True) + " Configuration is valid")
        click.echo(f"\nConfiguration file: {config_file}")
        click.echo(f"\nEndpoints:")
        click.echo(f"  PIX Add URL: {config_obj.endpoints.pix_add_url}")
        click.echo(f"  ITI-41 URL:  {config_obj.endpoints.iti41_url}")
        
        click.echo(f"\nCertificates:")
        click.echo(f"  Cert path:   {config_obj.certificates.cert_path or 'Not configured'}")
        click.echo(f"  Key path:    {config_obj.certificates.key_path or 'Not configured'}")
        click.echo(f"  Format:      {config_obj.certificates.cert_format}")
        
        click.echo(f"\nTransport:")
        click.echo(f"  Verify TLS:  {config_obj.transport.verify_tls}")
        click.echo(f"  Timeouts:    {config_obj.transport.timeout_connect}s connect, {config_obj.transport.timeout_read}s read")
        click.echo(f"  Retries:     {config_obj.transport.max_retries}")
        
        click.echo(f"\nLogging:")
        click.echo(f"  Level:       {config_obj.logging.level}")
        click.echo(f"  Log file:    {config_obj.logging.log_file}")
        click.echo(f"  Redact PII:  {config_obj.logging.redact_pii}")
        
    except ConfigurationError as e:
        click.echo(click.style("✗", fg="red", bold=True) + " Configuration validation failed")
        click.echo(f"\n{e}", err=True)
        raise click.exceptions.Exit(1)


cli.add_command(config)


@cli.command()
def version() -> None:
    """Display version information."""
    click.echo(f"ihe-test-util version {__version__}")


if __name__ == "__main__":
    cli()
