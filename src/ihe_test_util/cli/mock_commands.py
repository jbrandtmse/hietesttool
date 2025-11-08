"""CLI commands for mock server management."""

import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import psutil
import requests

from ..mock_server.app import run_server
from ..mock_server.config import load_config


logger = logging.getLogger(__name__)

# PID file location
PID_FILE_PATH = Path("mocks") / ".mock-server.pid"
LOG_FILE_PATH = Path("mocks") / "logs" / "mock-server.log"


# =============================================================================
# PID File Management
# =============================================================================


def write_pid_file(
    pid: int,
    port: int,
    protocol: str,
    host: str = "0.0.0.0",
    config_file: str | None = None
) -> None:
    """Write PID file with server metadata.
    
    Args:
        pid: Process ID of the running server
        port: Server port number
        protocol: Protocol (http or https)
        host: Server host address
        config_file: Path to configuration file if used
    """
    pid_data = {
        "pid": pid,
        "port": port,
        "protocol": protocol,
        "host": host,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "config_file": config_file
    }
    
    # Ensure mocks directory exists
    PID_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Write PID file
    PID_FILE_PATH.write_text(json.dumps(pid_data, indent=2))
    logger.debug(f"PID file written: {PID_FILE_PATH}")


def read_pid_file() -> dict[str, Any] | None:
    """Read PID file and return server metadata.
    
    Returns:
        Dictionary with server metadata or None if file doesn't exist
    """
    if not PID_FILE_PATH.exists():
        return None
    
    try:
        return json.loads(PID_FILE_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read PID file: {e}")
        return None


def remove_pid_file() -> None:
    """Remove PID file."""
    if PID_FILE_PATH.exists():
        PID_FILE_PATH.unlink()
        logger.debug(f"PID file removed: {PID_FILE_PATH}")


def is_process_running(pid: int) -> bool:
    """Check if process with given PID is still running.
    
    Args:
        pid: Process ID to check
        
    Returns:
        True if process is running, False otherwise
    """
    try:
        process = psutil.Process(pid)
        return process.is_running()
    except psutil.NoSuchProcess:
        return False


def is_server_running() -> tuple[bool, dict[str, Any] | None]:
    """Check if mock server is currently running.
    
    Returns:
        Tuple of (is_running, pid_info)
    """
    pid_info = read_pid_file()
    
    if pid_info is None:
        return False, None
    
    # Check if process is still running
    if not is_process_running(pid_info["pid"]):
        # Stale PID file - remove it
        click.echo("⚠️  Found stale PID file (process not running). Cleaning up...")
        remove_pid_file()
        return False, None
    
    return True, pid_info


# =============================================================================
# Mock Server Commands
# =============================================================================


@click.group(name="mock")
def mock_group():
    """Manage IHE mock server.
    
    The mock server provides IHE endpoints for testing:
    - /health - Health check endpoint
    - /pix/add - PIX Add (ITI-8) endpoint
    - /iti41/submit - ITI-41 (Provide and Register Document Set) endpoint
    
    Available commands:
    - start: Start the mock server
    - stop: Stop a running mock server
    - status: Check server status
    - logs: View server logs
    """


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
    "--background",
    "-b",
    is_flag=True,
    help="Run server in background"
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
    background: bool,
    debug: bool
):
    """Start the mock IHE server.
    
    Examples:
    
        # Start HTTP server in foreground\n
        ihe-test-util mock start
        
        # Start HTTPS server in background\n
        ihe-test-util mock start --https --background
        
        # Start on custom port\n
        ihe-test-util mock start --port 9090 --background
        
        # Start with custom config file\n
        ihe-test-util mock start --config path/to/config.json
    """
    try:
        # Check if server is already running
        is_running, pid_info = is_server_running()
        if is_running:
            click.echo(
                f"❌ Mock server is already running (PID: {pid_info['pid']}, "
                f"Port: {pid_info['port']})"
            )
            click.echo("   Stop it first with: ihe-test-util mock stop")
            raise click.Abort()
        
        # Load configuration
        server_config = load_config(config)

        # Determine port
        if port is None:
            port = server_config.https_port if protocol == "https" else server_config.http_port
        
        # Validate port range
        if not 1 <= port <= 65535:
            raise click.ClickException(
                f"Invalid port {port}. Port must be between 1 and 65535."
            )

        # Display startup information
        click.echo("=" * 50)
        click.echo("IHE Mock Server")
        click.echo("=" * 50)
        click.echo(f"Protocol: {protocol.upper()}")
        click.echo(f"Host: {server_config.host}")
        click.echo(f"Port: {port}")
        click.echo(f"Mode: {'Background' if background else 'Foreground'}")
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
        
        if background:
            # Start server in background
            start_background_server(
                protocol=protocol,
                port=port,
                config_path=config,
                debug=debug,
                server_config=server_config
            )
        else:
            # Start server in foreground
            click.echo("Starting server... (Press Ctrl+C to stop)")
            click.echo("")
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


def start_background_server(
    protocol: str,
    port: int,
    config_path: Path | None,
    debug: bool,
    server_config: Any
) -> None:
    """Start mock server as background process.
    
    Args:
        protocol: Server protocol (http or https)
        port: Server port number
        config_path: Path to configuration file
        debug: Enable debug mode
        server_config: Loaded server configuration
    """
    # Build command to execute
    cmd = [
        sys.executable,
        "-m", "ihe_test_util.cli.main",
        "mock", "start-foreground",
        f"--{protocol}",
        "--port", str(port)
    ]
    
    if config_path:
        cmd.extend(["--config", str(config_path)])
    
    if debug:
        cmd.append("--debug")
    
    # Start process in background
    click.echo("Starting server in background...")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )
        
        # Write PID file
        write_pid_file(
            pid=process.pid,
            port=port,
            protocol=protocol,
            host=server_config.host,
            config_file=str(config_path) if config_path else None
        )
        
        # Wait briefly and check if server started
        time.sleep(2)
        
        # Verify process is still running
        if not is_process_running(process.pid):
            remove_pid_file()
            raise click.ClickException(
                "Server failed to start. Check logs at mocks/logs/mock-server.log"
            )
        
        # Verify server is responding
        # Use 127.0.0.1 for HTTP requests if host is 0.0.0.0 (Windows limitation)
        request_host = "127.0.0.1" if server_config.host == "0.0.0.0" else server_config.host
        health_url = f"{protocol}://{request_host}:{port}/health"
        try:
            response = requests.get(health_url, timeout=3, verify=False)
            if response.status_code == 200:
                click.echo(f"✓ Server started successfully (PID: {process.pid})")
                click.echo(f"✓ Health check: {health_url}")
                click.echo("")
                click.echo("Use 'ihe-test-util mock status' to check server status")
                click.echo("Use 'ihe-test-util mock logs --follow' to stream logs")
                click.echo("Use 'ihe-test-util mock stop' to stop the server")
            else:
                click.echo(f"⚠️  Server started (PID: {process.pid}) but health check returned {response.status_code}")
        except requests.RequestException:
            click.echo(f"⚠️  Server started (PID: {process.pid}) but health check is not yet responding")
            click.echo("   It may take a few seconds for the server to be ready")
        
    except Exception as e:
        logger.exception("Failed to start background server")
        raise click.ClickException(f"Failed to start background server: {e}")


@mock_group.command(name="start-foreground", hidden=True)
@click.option("--http", "protocol", flag_value="http", default=True)
@click.option("--https", "protocol", flag_value="https")
@click.option("--port", type=int, required=True)
@click.option("--config", type=click.Path(exists=True, path_type=Path))
@click.option("--debug", is_flag=True)
def start_foreground(
    protocol: str,
    port: int,
    config: Path | None,
    debug: bool
):
    """Internal command to start server in foreground (used by background mode)."""
    try:
        server_config = load_config(config)
        run_server(
            host=server_config.host,
            port=port,
            protocol=protocol,
            config=server_config,
            debug=debug
        )
    except Exception as e:
        logger.exception("Server crashed")
        raise


@mock_group.command(name="stop")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force kill if graceful shutdown fails"
)
@click.option(
    "--timeout",
    type=int,
    default=10,
    help="Shutdown timeout in seconds (default: 10)"
)
def stop_server(force: bool, timeout: int):
    """Stop the running mock server gracefully.
    
    Examples:
    
        # Stop running server gracefully\n
        ihe-test-util mock stop
        
        # Force stop with shorter timeout\n
        ihe-test-util mock stop --force --timeout 5
    """
    is_running, pid_info = is_server_running()
    
    if not is_running:
        click.echo("No mock server is currently running.")
        return
    
    pid = pid_info["pid"]
    
    try:
        process = psutil.Process(pid)
        
        click.echo(f"Stopping mock server (PID: {pid})...")
        
        # Send graceful shutdown signal
        if os.name == 'nt':  # Windows
            process.terminate()
        else:  # Unix/Linux/Mac
            process.send_signal(signal.SIGTERM)
        
        # Wait for graceful shutdown
        try:
            process.wait(timeout=timeout)
            click.echo("✓ Server stopped successfully")
        except psutil.TimeoutExpired:
            if force:
                click.echo(f"⚠️  Graceful shutdown timed out after {timeout}s. Force killing...")
                process.kill()
                process.wait()
                click.echo("✓ Server force killed")
            else:
                click.echo(
                    f"⚠️  Server did not stop after {timeout}s. "
                    "Use --force to kill it forcefully.",
                    err=True
                )
                raise click.Abort()
        
        # Remove PID file
        remove_pid_file()
        
    except psutil.NoSuchProcess:
        click.echo("⚠️  Process no longer exists. Cleaning up PID file...")
        remove_pid_file()
    except Exception as e:
        logger.exception("Failed to stop server")
        raise click.ClickException(f"Failed to stop server: {e}")


@mock_group.command(name="status")
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output status as JSON"
)
def server_status(output_json: bool):
    """Display mock server running status and details.
    
    Examples:
    
        # Check server status (human-readable)\n
        ihe-test-util mock status
        
        # Get status as JSON for scripting\n
        ihe-test-util mock status --json
    """
    is_running, pid_info = is_server_running()
    
    if not is_running:
        if output_json:
            click.echo(json.dumps({"running": False}))
        else:
            click.echo("Mock Server Status")
            click.echo("=" * 50)
            click.echo("Status: Stopped")
            click.echo("")
            click.echo("Start the server with: ihe-test-util mock start --background")
        sys.exit(1)
        return
    
    # Get detailed status from health check
    protocol = pid_info["protocol"]
    host = pid_info["host"]
    port = pid_info["port"]
    pid = pid_info["pid"]
    start_time_str = pid_info["start_time"]
    
    # Use 127.0.0.1 for HTTP requests if host is 0.0.0.0 (Windows limitation)
    request_host = "127.0.0.1" if host == "0.0.0.0" else host
    health_url = f"{protocol}://{request_host}:{port}/health"
    
    try:
        response = requests.get(health_url, timeout=5, verify=False)
        health_data = response.json() if response.status_code == 200 else {}
    except requests.RequestException as e:
        health_data = {"error": str(e)}
    
    # Calculate uptime
    start_time = datetime.fromisoformat(start_time_str)
    uptime_seconds = int((datetime.now(timezone.utc) - start_time).total_seconds())
    uptime_str = format_uptime(uptime_seconds)
    
    # Get endpoints from health data
    endpoints = health_data.get("endpoints", [])
    request_count = health_data.get("request_count", 0)
    
    if output_json:
        status_data = {
            "running": True,
            "pid": pid,
            "protocol": protocol,
            "host": host,
            "port": port,
            "url": f"{protocol}://{host}:{port}",
            "uptime_seconds": uptime_seconds,
            "endpoints": endpoints,
            "request_count": request_count
        }
        click.echo(json.dumps(status_data, indent=2))
    else:
        click.echo("Mock Server Status")
        click.echo("=" * 50)
        click.echo("Status: Running ✓")
        click.echo(f"PID: {pid}")
        click.echo(f"Protocol: {protocol.upper()}")
        click.echo(f"URL: {protocol}://{host}:{port}")
        click.echo(f"Uptime: {uptime_str}")
        click.echo(f"Requests Handled: {request_count}")
        click.echo("")
        click.echo("Available Endpoints:")
        for endpoint in endpoints:
            click.echo(f"  - {endpoint}")
    
    sys.exit(0)


def format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format.
    
    Args:
        seconds: Uptime in seconds
        
    Returns:
        Formatted uptime string (e.g., "2h 15m 30s")
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


@mock_group.command(name="logs")
@click.option(
    "--tail",
    type=int,
    default=50,
    help="Show last N lines (default: 50)"
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Stream logs in real-time"
)
@click.option(
    "--level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Filter by log level"
)
@click.option(
    "--grep",
    type=str,
    help="Filter lines matching regex pattern"
)
def view_logs(tail: int, follow: bool, level: str | None, grep: str | None):
    """Display mock server logs with filtering options.
    
    Examples:
    
        # Show last 50 lines\n
        ihe-test-util mock logs
        
        # Show last 100 lines\n
        ihe-test-util mock logs --tail 100
        
        # Stream logs in real-time\n
        ihe-test-util mock logs --follow
        
        # Show only errors\n
        ihe-test-util mock logs --level ERROR
        
        # Search for pattern\n
        ihe-test-util mock logs --grep "PIX Add"
        
        # Combine filters\n
        ihe-test-util mock logs --follow --level INFO --grep "endpoint"
    """
    if not LOG_FILE_PATH.exists():
        click.echo(
            f"Log file not found: {LOG_FILE_PATH}\n"
            "Start the server to generate logs.",
            err=True
        )
        return
    
    try:
        if follow:
            follow_log_file(LOG_FILE_PATH, level, grep)
        else:
            display_tail(LOG_FILE_PATH, tail, level, grep)
    except KeyboardInterrupt:
        click.echo("\n\nLog viewing stopped.")
    except Exception as e:
        logger.exception("Failed to read logs")
        raise click.ClickException(f"Failed to read logs: {e}")


def display_tail(
    file_path: Path,
    num_lines: int,
    level_filter: str | None,
    grep_pattern: str | None
) -> None:
    """Display last N lines from log file.
    
    Args:
        file_path: Path to log file
        num_lines: Number of lines to display
        level_filter: Filter by log level
        grep_pattern: Regex pattern to match
    """
    with file_path.open('r', encoding='utf-8', errors='ignore') as f:
        # Read all lines into deque with maxlen
        lines = deque(f, maxlen=num_lines * 10)  # Read more to account for filtering
    
    # Apply filters and display
    displayed = 0
    for line in lines:
        if should_display_line(line, level_filter, grep_pattern):
            click.echo(line.rstrip())
            displayed += 1
            if displayed >= num_lines:
                break


def follow_log_file(
    file_path: Path,
    level_filter: str | None,
    grep_pattern: str | None
) -> None:
    """Stream log file in real-time (like tail -f).
    
    Args:
        file_path: Path to log file
        level_filter: Filter by log level
        grep_pattern: Regex pattern to match
    """
    with file_path.open('r', encoding='utf-8', errors='ignore') as f:
        # Seek to end of file
        f.seek(0, 2)
        
        click.echo("Streaming logs... (Press Ctrl+C to stop)")
        click.echo("")
        
        while True:
            line = f.readline()
            if line:
                if should_display_line(line, level_filter, grep_pattern):
                    click.echo(line.rstrip())
            else:
                time.sleep(0.1)  # Sleep briefly before checking again


def should_display_line(
    line: str,
    level_filter: str | None,
    grep_pattern: str | None
) -> bool:
    """Determine if log line should be displayed based on filters.
    
    Args:
        line: Log line to check
        level_filter: Filter by log level (DEBUG, INFO, WARNING, ERROR)
        grep_pattern: Regex pattern to match
        
    Returns:
        True if line should be displayed, False otherwise
    """
    if level_filter and level_filter.upper() not in line:
        return False
    
    if grep_pattern:
        try:
            if not re.search(grep_pattern, line, re.IGNORECASE):
                return False
        except re.error:
            # Invalid regex, ignore filter
            pass
    
    return True
