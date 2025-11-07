"""CLI commands for mock server management."""

import logging
from pathlib import Path

import click

from ..mock_server.app import run_server
from ..mock_server.config import load_config


logger = logging.getLogger(__name__)


@click.group(name="mock")
def mock_group():
    """Manage IHE mock server."""


@mock_group.command(name="start")
@click.option(
    "--http",
    "protocol",
    flag_value="http",
    default=True,
    help="Start HTTP server (default)"
)
@click.option(
    "--https",
    "protocol",
    flag_value="https",
    help="Start HTTPS server (requires certificates)"
)
@click.option(
    "--port",
    type=int,
    help="Server port (overrides config file)"
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file (default: mocks/config.json)"
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode"
)
def start_server(
    protocol: str,
    port: int | None,
    config: Path | None,
    debug: bool
):
    """Start the mock IHE server.
    
    Examples:
    
        # Start HTTP server on default port (8080)
        ihe-test-util mock start
        
        # Start HTTPS server on default port (8443)
        ihe-test-util mock start --https
        
        # Start HTTP server on custom port
        ihe-test-util mock start --port 9090
        
        # Start with custom config file
        ihe-test-util mock start --config path/to/config.json
    """
    try:
        # Load configuration
        server_config = load_config(config)

        # Determine port
        if port is None:
            port = server_config.https_port if protocol == "https" else server_config.http_port

        # Display startup information
        click.echo("=" * 50)
        click.echo("IHE Mock Server")
        click.echo("=" * 50)
        click.echo(f"Protocol: {protocol.upper()}")
        click.echo(f"Host: {server_config.host}")
        click.echo(f"Port: {port}")
        click.echo(f"Health Check: {protocol}://{server_config.host}:{port}/health")
        click.echo(f"PIX Add: {protocol}://{server_config.host}:{port}{server_config.pix_add_endpoint}")
        click.echo(f"ITI-41: {protocol}://{server_config.host}:{port}{server_config.iti41_endpoint}")
        click.echo("=" * 50)

        if protocol == "https":
            cert_path = Path(server_config.cert_path)
            if not cert_path.exists():
                click.echo("")
                click.echo(
                    "⚠️  HTTPS certificates not found. Run the following command to generate them:",
                    err=True
                )
                click.echo("   bash scripts/generate_cert.sh", err=True)
                click.echo("")
                raise click.ClickException("HTTPS certificates not found")

        click.echo("")
        click.echo("Starting server... (Press Ctrl+C to stop)")
        click.echo("")

        # Run server (this blocks until shutdown)
        run_server(
            host=server_config.host,
            port=port,
            protocol=protocol,
            config=server_config,
            debug=debug
        )

    except FileNotFoundError as e:
        raise click.ClickException(str(e))
    except ValueError as e:
        raise click.ClickException(f"Configuration error: {e}")
    except KeyboardInterrupt:
        click.echo("\n\nServer stopped by user.")
    except Exception as e:
        logger.exception("Failed to start mock server")
        raise click.ClickException(f"Failed to start server: {e}")


# Note: mock stop and mock status commands will be implemented in Story 2.4
