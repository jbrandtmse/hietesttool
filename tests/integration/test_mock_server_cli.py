"""Integration tests for mock server CLI workflow."""

import json
import time
from pathlib import Path

import pytest
import requests
from click.testing import CliRunner

from ihe_test_util.cli.mock_commands import mock_group


@pytest.fixture
def cli_runner():
    """Create Click CLI runner."""
    return CliRunner()


@pytest.fixture
def cleanup_server():
    """Ensure server is stopped after test."""
    yield
    # Cleanup: Try to stop server if running
    runner = CliRunner()
    runner.invoke(mock_group, ["stop", "--force"])


@pytest.mark.integration
def test_mock_server_complete_workflow(cli_runner, cleanup_server):
    """Test complete workflow: start → status → logs → stop.
    
    This test verifies the full lifecycle of the mock server:
    1. Start server in background
    2. Check status (should be running)
    3. Verify logs command works
    4. Stop server gracefully
    5. Check status (should be stopped)
    """
    # Step 1: Start server in background
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8888"])
    assert result.exit_code == 0
    assert "started successfully" in result.output.lower() or "pid" in result.output.lower()
    
    # Wait for server to fully start
    time.sleep(3)
    
    try:
        # Step 2: Check status - should be running
        result = cli_runner.invoke(mock_group, ["status"])
        assert result.exit_code == 0
        assert "Running" in result.output
        assert "8888" in result.output
        
        # Step 3: Verify health endpoint is accessible
        try:
            response = requests.get("http://127.0.0.1:8888/health", timeout=5)
            assert response.status_code == 200
            health_data = response.json()
            assert health_data["status"] == "healthy"
        except requests.RequestException as e:
            pytest.fail(f"Health check failed: {e}")
        
        # Step 4: Check logs command works (may be empty)
        result = cli_runner.invoke(mock_group, ["logs", "--tail", "10"])
        assert result.exit_code == 0
        
    finally:
        # Step 5: Stop server
        result = cli_runner.invoke(mock_group, ["stop"])
        assert result.exit_code == 0
        assert "stopped" in result.output.lower()
        
        # Step 6: Verify status shows stopped
        result = cli_runner.invoke(mock_group, ["status"])
        assert result.exit_code == 1
        assert "Stopped" in result.output


@pytest.mark.integration
def test_background_server_creates_pid_file(cli_runner, cleanup_server):
    """Test that starting server in background creates PID file."""
    # Start server
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8889"])
    assert result.exit_code == 0
    
    # Wait for server to start
    time.sleep(2)
    
    try:
        # Check PID file exists
        pid_file = Path("mocks") / ".mock-server.pid"
        assert pid_file.exists()
        
        # Verify PID file contains valid data
        pid_data = json.loads(pid_file.read_text())
        assert "pid" in pid_data
        assert "port" in pid_data
        assert pid_data["port"] == 8889
        assert "protocol" in pid_data
        assert "start_time" in pid_data
        
    finally:
        # Cleanup
        cli_runner.invoke(mock_group, ["stop"])


@pytest.mark.integration
def test_graceful_shutdown_removes_pid_file(cli_runner, cleanup_server):
    """Test that graceful shutdown removes PID file."""
    pid_file = Path("mocks") / ".mock-server.pid"
    
    # Start server
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8890"])
    assert result.exit_code == 0
    
    time.sleep(2)
    
    # Verify PID file exists
    assert pid_file.exists()
    
    # Stop server
    result = cli_runner.invoke(mock_group, ["stop"])
    assert result.exit_code == 0
    
    # Verify PID file is removed
    assert not pid_file.exists()


@pytest.mark.integration
def test_status_command_shows_endpoints(cli_runner, cleanup_server):
    """Test that status command displays available endpoints."""
    # Start server
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8891"])
    assert result.exit_code == 0
    
    time.sleep(2)
    
    try:
        # Check status
        result = cli_runner.invoke(mock_group, ["status"])
        assert result.exit_code == 0
        
        # Verify endpoints are listed
        assert "/health" in result.output
        assert "/pix/add" in result.output
        assert "/iti41/submit" in result.output
        
    finally:
        cli_runner.invoke(mock_group, ["stop"])


@pytest.mark.integration
def test_status_json_output(cli_runner, cleanup_server):
    """Test that status command provides valid JSON output."""
    # Start server
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8892"])
    assert result.exit_code == 0
    
    time.sleep(2)
    
    try:
        # Get status as JSON
        result = cli_runner.invoke(mock_group, ["status", "--json"])
        assert result.exit_code == 0
        
        # Parse JSON output
        status_data = json.loads(result.output)
        assert status_data["running"] is True
        assert status_data["port"] == 8892
        assert status_data["protocol"] == "http"
        assert "pid" in status_data
        assert "uptime_seconds" in status_data
        assert "endpoints" in status_data
        
    finally:
        cli_runner.invoke(mock_group, ["stop"])


@pytest.mark.integration
def test_cannot_start_server_twice(cli_runner, cleanup_server):
    """Test that starting server twice fails with clear error message."""
    # Start first server
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8893"])
    assert result.exit_code == 0
    
    time.sleep(2)
    
    try:
        # Try to start second server
        result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8894"])
        assert result.exit_code != 0
        assert "already running" in result.output
        
    finally:
        cli_runner.invoke(mock_group, ["stop"])


@pytest.mark.integration
def test_stop_command_when_not_running(cli_runner):
    """Test that stop command handles no running server gracefully."""
    # Ensure no server is running
    cli_runner.invoke(mock_group, ["stop"])
    
    # Try to stop non-existent server
    result = cli_runner.invoke(mock_group, ["stop"])
    assert result.exit_code == 0
    assert "No mock server" in result.output


@pytest.mark.integration
def test_logs_command_reads_actual_log_file(cli_runner, cleanup_server):
    """Test that logs command reads actual server log file."""
    # Start server
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8895"])
    assert result.exit_code == 0
    
    time.sleep(2)
    
    try:
        # Make a request to generate log entries
        try:
            requests.get("http://127.0.0.1:8895/health", timeout=5)
        except requests.RequestException:
            pass
        
        time.sleep(1)
        
        # Read logs
        result = cli_runner.invoke(mock_group, ["logs", "--tail", "20"])
        assert result.exit_code == 0
        # Should contain some log output (server startup messages at minimum)
        
    finally:
        cli_runner.invoke(mock_group, ["stop"])


@pytest.mark.integration
def test_server_responds_after_background_start(cli_runner, cleanup_server):
    """Test that server is actually responding after background startup."""
    # Start server
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8896"])
    assert result.exit_code == 0
    
    time.sleep(3)
    
    try:
        # Test health endpoint
        response = requests.get("http://127.0.0.1:8896/health", timeout=5, verify=False)
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert "endpoints" in health_data
        assert "/health" in health_data["endpoints"]
        
    finally:
        cli_runner.invoke(mock_group, ["stop"])


@pytest.mark.integration
def test_uptime_increases_over_time(cli_runner, cleanup_server):
    """Test that uptime counter increases as server runs."""
    # Start server
    result = cli_runner.invoke(mock_group, ["start", "--background", "--port", "8897"])
    assert result.exit_code == 0
    
    time.sleep(2)
    
    try:
        # Get initial status
        result1 = cli_runner.invoke(mock_group, ["status", "--json"])
        status1 = json.loads(result1.output)
        uptime1 = status1["uptime_seconds"]
        
        # Wait a few seconds
        time.sleep(3)
        
        # Get status again
        result2 = cli_runner.invoke(mock_group, ["status", "--json"])
        status2 = json.loads(result2.output)
        uptime2 = status2["uptime_seconds"]
        
        # Uptime should have increased
        assert uptime2 > uptime1
        assert uptime2 - uptime1 >= 2  # At least 2 seconds difference
        
    finally:
        cli_runner.invoke(mock_group, ["stop"])


@pytest.mark.integration
def test_port_validation_rejects_invalid_ports(cli_runner):
    """Test that invalid port numbers are rejected."""
    # Test port 0
    result = cli_runner.invoke(mock_group, ["start", "--port", "0"])
    assert result.exit_code != 0
    assert "Invalid port" in result.output
    
    # Test port > 65535
    result = cli_runner.invoke(mock_group, ["start", "--port", "99999"])
    assert result.exit_code != 0
    assert "Invalid port" in result.output
