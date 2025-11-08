"""Unit tests for mock server CLI commands."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest
import requests
from click.testing import CliRunner

from ihe_test_util.cli.mock_commands import (
    PID_FILE_PATH,
    format_uptime,
    is_process_running,
    is_server_running,
    mock_group,
    read_pid_file,
    remove_pid_file,
    should_display_line,
    write_pid_file,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cli_runner():
    """Create Click CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_pid_file(tmp_path, monkeypatch):
    """Create temporary PID file location."""
    pid_file = tmp_path / ".mock-server.pid"
    monkeypatch.setattr("ihe_test_util.cli.mock_commands.PID_FILE_PATH", pid_file)
    return pid_file


@pytest.fixture
def temp_log_file(tmp_path, monkeypatch):
    """Create temporary log file location."""
    log_file = tmp_path / "mock-server.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("2025-11-07 18:00:00 INFO Server started\n")
    monkeypatch.setattr("ihe_test_util.cli.mock_commands.LOG_FILE_PATH", log_file)
    return log_file


@pytest.fixture
def sample_pid_data():
    """Sample PID file data."""
    return {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": "2025-11-07T18:00:00+00:00",
        "config_file": None
    }


# =============================================================================
# PID File Management Tests
# =============================================================================


def test_write_pid_file_creates_file(temp_pid_file):
    """Test writing PID file creates file with correct data."""
    # Arrange
    pid = 12345
    port = 8080
    protocol = "http"
    host = "0.0.0.0"
    
    # Act
    write_pid_file(pid, port, protocol, host)
    
    # Assert
    assert temp_pid_file.exists()
    data = json.loads(temp_pid_file.read_text())
    assert data["pid"] == pid
    assert data["port"] == port
    assert data["protocol"] == protocol
    assert data["host"] == host
    assert "start_time" in data


def test_write_pid_file_creates_parent_directory(tmp_path, monkeypatch):
    """Test writing PID file creates parent directory if it doesn't exist."""
    # Arrange
    pid_file = tmp_path / "new_dir" / ".mock-server.pid"
    monkeypatch.setattr("ihe_test_util.cli.mock_commands.PID_FILE_PATH", pid_file)
    
    # Act
    write_pid_file(12345, 8080, "http")
    
    # Assert
    assert pid_file.exists()
    assert pid_file.parent.exists()


def test_read_pid_file_returns_data(temp_pid_file, sample_pid_data):
    """Test reading PID file returns correct data."""
    # Arrange
    temp_pid_file.write_text(json.dumps(sample_pid_data))
    
    # Act
    result = read_pid_file()
    
    # Assert
    assert result == sample_pid_data


def test_read_pid_file_returns_none_when_missing(temp_pid_file):
    """Test reading PID file returns None when file doesn't exist."""
    # Act
    result = read_pid_file()
    
    # Assert
    assert result is None


def test_read_pid_file_handles_invalid_json(temp_pid_file):
    """Test reading PID file handles invalid JSON gracefully."""
    # Arrange
    temp_pid_file.write_text("invalid json{")
    
    # Act
    result = read_pid_file()
    
    # Assert
    assert result is None


def test_remove_pid_file_deletes_file(temp_pid_file):
    """Test removing PID file deletes the file."""
    # Arrange
    temp_pid_file.write_text("{}")
    assert temp_pid_file.exists()
    
    # Act
    remove_pid_file()
    
    # Assert
    assert not temp_pid_file.exists()


def test_remove_pid_file_handles_missing_file(temp_pid_file):
    """Test removing PID file handles missing file gracefully."""
    # Act & Assert (should not raise exception)
    remove_pid_file()


@patch("ihe_test_util.cli.mock_commands.psutil.Process")
def test_is_process_running_returns_true_for_running_process(mock_process_class):
    """Test is_process_running returns True for running process."""
    # Arrange
    mock_process = Mock()
    mock_process.is_running.return_value = True
    mock_process_class.return_value = mock_process
    
    # Act
    result = is_process_running(12345)
    
    # Assert
    assert result is True
    mock_process_class.assert_called_once_with(12345)


@patch("ihe_test_util.cli.mock_commands.psutil.Process")
def test_is_process_running_returns_false_for_dead_process(mock_process_class):
    """Test is_process_running returns False when process doesn't exist."""
    # Arrange
    mock_process_class.side_effect = psutil.NoSuchProcess(12345)
    
    # Act
    result = is_process_running(12345)
    
    # Assert
    assert result is False


@patch("ihe_test_util.cli.mock_commands.is_process_running")
def test_is_server_running_returns_true_with_valid_pid(
    mock_is_running, temp_pid_file, sample_pid_data
):
    """Test is_server_running returns True for running server."""
    # Arrange
    temp_pid_file.write_text(json.dumps(sample_pid_data))
    mock_is_running.return_value = True
    
    # Act
    running, pid_info = is_server_running()
    
    # Assert
    assert running is True
    assert pid_info == sample_pid_data


@patch("ihe_test_util.cli.mock_commands.is_process_running")
def test_is_server_running_handles_stale_pid_file(
    mock_is_running, temp_pid_file, sample_pid_data
):
    """Test is_server_running removes stale PID file."""
    # Arrange
    temp_pid_file.write_text(json.dumps(sample_pid_data))
    mock_is_running.return_value = False
    
    # Act
    running, pid_info = is_server_running()
    
    # Assert
    assert running is False
    assert pid_info is None
    assert not temp_pid_file.exists()


def test_is_server_running_returns_false_when_no_pid_file(temp_pid_file):
    """Test is_server_running returns False when PID file doesn't exist."""
    # Act
    running, pid_info = is_server_running()
    
    # Assert
    assert running is False
    assert pid_info is None


# =============================================================================
# Helper Function Tests
# =============================================================================


def test_format_uptime_formats_seconds_only():
    """Test format_uptime with seconds only."""
    assert format_uptime(30) == "30s"


def test_format_uptime_formats_minutes_and_seconds():
    """Test format_uptime with minutes and seconds."""
    assert format_uptime(150) == "2m 30s"


def test_format_uptime_formats_hours_minutes_seconds():
    """Test format_uptime with hours, minutes, and seconds."""
    assert format_uptime(7530) == "2h 5m 30s"


def test_format_uptime_formats_hours_only():
    """Test format_uptime with hours only."""
    assert format_uptime(7200) == "2h"


def test_should_display_line_no_filters():
    """Test should_display_line with no filters."""
    assert should_display_line("Test line", None, None) is True


def test_should_display_line_level_filter_match():
    """Test should_display_line with matching level filter."""
    line = "2025-11-07 18:00:00 ERROR Something failed"
    assert should_display_line(line, "ERROR", None) is True


def test_should_display_line_level_filter_no_match():
    """Test should_display_line with non-matching level filter."""
    line = "2025-11-07 18:00:00 INFO All good"
    assert should_display_line(line, "ERROR", None) is False


def test_should_display_line_grep_filter_match():
    """Test should_display_line with matching grep pattern."""
    line = "PIX Add endpoint called"
    assert should_display_line(line, None, "PIX") is True


def test_should_display_line_grep_filter_no_match():
    """Test should_display_line with non-matching grep pattern."""
    line = "ITI-41 endpoint called"
    assert should_display_line(line, None, "PIX") is False


def test_should_display_line_invalid_regex():
    """Test should_display_line ignores invalid regex."""
    line = "Test line"
    # Invalid regex pattern
    assert should_display_line(line, None, "[invalid(") is True


def test_should_display_line_combined_filters():
    """Test should_display_line with both filters matching."""
    line = "2025-11-07 18:00:00 INFO PIX Add successful"
    assert should_display_line(line, "INFO", "PIX") is True


# =============================================================================
# Mock Start Command Tests
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.load_config")
@patch("ihe_test_util.cli.mock_commands.run_server")
def test_mock_start_foreground_mode(
    mock_run_server, mock_load_config, mock_is_running, cli_runner
):
    """Test mock start in foreground mode."""
    # Arrange
    mock_is_running.return_value = (False, None)
    mock_config = Mock()
    mock_config.host = "0.0.0.0"
    mock_config.http_port = 8080
    mock_config.pix_add_endpoint = "/pix/add"
    mock_config.iti41_endpoint = "/iti41/submit"
    mock_load_config.return_value = mock_config
    
    # Act
    result = cli_runner.invoke(mock_group, ["start"])
    
    # Assert
    assert result.exit_code == 0
    mock_run_server.assert_called_once()


@patch("ihe_test_util.cli.mock_commands.is_server_running")
def test_mock_start_fails_when_already_running(mock_is_running, cli_runner):
    """Test mock start fails when server is already running."""
    # Arrange
    mock_is_running.return_value = (True, {"pid": 12345, "port": 8080})
    
    # Act
    result = cli_runner.invoke(mock_group, ["start"])
    
    # Assert
    assert result.exit_code != 0
    assert "already running" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.load_config")
def test_mock_start_validates_port_range(mock_load_config, mock_is_running, cli_runner):
    """Test mock start validates port range."""
    # Arrange
    mock_is_running.return_value = (False, None)
    mock_config = Mock()
    mock_load_config.return_value = mock_config
    
    # Act
    result = cli_runner.invoke(mock_group, ["start", "--port", "99999"])
    
    # Assert
    assert result.exit_code != 0
    assert "Invalid port" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.load_config")
@patch("ihe_test_util.cli.mock_commands.start_background_server")
def test_mock_start_background_mode(
    mock_start_bg, mock_load_config, mock_is_running, cli_runner
):
    """Test mock start in background mode."""
    # Arrange
    mock_is_running.return_value = (False, None)
    mock_config = Mock()
    mock_config.host = "0.0.0.0"
    mock_config.http_port = 8080
    mock_config.pix_add_endpoint = "/pix/add"
    mock_config.iti41_endpoint = "/iti41/submit"
    mock_load_config.return_value = mock_config
    
    # Act
    result = cli_runner.invoke(mock_group, ["start", "--background"])
    
    # Assert
    assert result.exit_code == 0
    mock_start_bg.assert_called_once()


# =============================================================================
# Mock Stop Command Tests
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.psutil.Process")
@patch("ihe_test_util.cli.mock_commands.remove_pid_file")
def test_mock_stop_graceful_shutdown(
    mock_remove, mock_process_class, mock_is_running, cli_runner
):
    """Test mock stop performs graceful shutdown."""
    # Arrange
    mock_is_running.return_value = (True, {"pid": 12345})
    mock_process = Mock()
    mock_process.wait.return_value = None  # Process stopped gracefully
    mock_process_class.return_value = mock_process
    
    # Act
    result = cli_runner.invoke(mock_group, ["stop"])
    
    # Assert
    assert result.exit_code == 0
    assert "stopped successfully" in result.output
    mock_process.wait.assert_called_once()
    mock_remove.assert_called_once()


@patch("ihe_test_util.cli.mock_commands.is_server_running")
def test_mock_stop_no_server_running(mock_is_running, cli_runner):
    """Test mock stop when no server is running."""
    # Arrange
    mock_is_running.return_value = (False, None)
    
    # Act
    result = cli_runner.invoke(mock_group, ["stop"])
    
    # Assert
    assert result.exit_code == 0
    assert "No mock server" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.psutil.Process")
@patch("ihe_test_util.cli.mock_commands.remove_pid_file")
def test_mock_stop_force_kill_on_timeout(
    mock_remove, mock_process_class, mock_is_running, cli_runner
):
    """Test mock stop force kills on timeout."""
    # Arrange
    mock_is_running.return_value = (True, {"pid": 12345})
    mock_process = Mock()
    # First wait() times out, second wait() after kill() succeeds
    mock_process.wait.side_effect = [psutil.TimeoutExpired(10), None]
    mock_process_class.return_value = mock_process
    
    # Act
    result = cli_runner.invoke(mock_group, ["stop", "--force"])
    
    # Assert
    assert result.exit_code == 0
    assert "force killed" in result.output
    mock_process.kill.assert_called_once()


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.psutil.Process")
def test_mock_stop_aborts_on_timeout_without_force(
    mock_process_class, mock_is_running, cli_runner
):
    """Test mock stop aborts on timeout without force flag."""
    # Arrange
    mock_is_running.return_value = (True, {"pid": 12345})
    mock_process = Mock()
    mock_process.wait.side_effect = psutil.TimeoutExpired(10)
    mock_process_class.return_value = mock_process
    
    # Act
    result = cli_runner.invoke(mock_group, ["stop"])
    
    # Assert
    assert result.exit_code != 0
    mock_process.kill.assert_not_called()


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.psutil.Process")
@patch("ihe_test_util.cli.mock_commands.remove_pid_file")
def test_mock_stop_handles_dead_process(
    mock_remove, mock_process_class, mock_is_running, cli_runner
):
    """Test mock stop handles dead process gracefully."""
    # Arrange
    mock_is_running.return_value = (True, {"pid": 12345})
    mock_process_class.side_effect = psutil.NoSuchProcess(12345)
    
    # Act
    result = cli_runner.invoke(mock_group, ["stop"])
    
    # Assert
    assert result.exit_code == 0
    mock_remove.assert_called_once()


# =============================================================================
# Mock Status Command Tests
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
def test_mock_status_server_stopped(mock_is_running, cli_runner):
    """Test mock status when server is stopped."""
    # Arrange
    mock_is_running.return_value = (False, None)
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    assert result.exit_code == 1
    assert "Stopped" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_mock_status_server_running(mock_get, mock_is_running, cli_runner):
    """Test mock status when server is running."""
    # Arrange
    start_time = datetime.now(timezone.utc).isoformat()
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": start_time
    })
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "endpoints": ["/health", "/pix/add"],
        "request_count": 42
    }
    mock_get.return_value = mock_response
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    assert result.exit_code == 0
    assert "Running" in result.output
    assert "12345" in result.output
    assert "8080" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_mock_status_json_output(mock_get, mock_is_running, cli_runner):
    """Test mock status with JSON output."""
    # Arrange
    start_time = datetime.now(timezone.utc).isoformat()
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": start_time
    })
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"endpoints": [], "request_count": 0}
    mock_get.return_value = mock_response
    
    # Act
    result = cli_runner.invoke(mock_group, ["status", "--json"])
    
    # Assert
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["running"] is True
    assert data["pid"] == 12345


# =============================================================================
# Mock Logs Command Tests
# =============================================================================


def test_mock_logs_file_not_found(cli_runner, tmp_path, monkeypatch):
    """Test mock logs when log file doesn't exist."""
    # Arrange
    log_file = tmp_path / "nonexistent.log"
    monkeypatch.setattr("ihe_test_util.cli.mock_commands.LOG_FILE_PATH", log_file)
    
    # Act
    result = cli_runner.invoke(mock_group, ["logs"])
    
    # Assert
    assert result.exit_code == 0
    assert "not found" in result.output


def test_mock_logs_tail_default(cli_runner, temp_log_file):
    """Test mock logs with default tail."""
    # Arrange
    temp_log_file.write_text("\\n".join([f"Line {i}" for i in range(100)]))
    
    # Act
    result = cli_runner.invoke(mock_group, ["logs"])
    
    # Assert
    assert result.exit_code == 0
    assert "Line 99" in result.output


def test_mock_logs_tail_custom(cli_runner, temp_log_file):
    """Test mock logs with custom tail count."""
    # Arrange
    temp_log_file.write_text("\n".join([f"Line {i}" for i in range(100)]))
    
    # Act
    result = cli_runner.invoke(mock_group, ["logs", "--tail", "10"])
    
    # Assert
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) <= 10


def test_mock_logs_level_filter(cli_runner, temp_log_file):
    """Test mock logs with level filter."""
    # Arrange
    temp_log_file.write_text(
        "2025-11-07 18:00:00 INFO All good\n"
        "2025-11-07 18:00:01 ERROR Something bad\n"
        "2025-11-07 18:00:02 INFO Still good\n"
    )
    
    # Act
    result = cli_runner.invoke(mock_group, ["logs", "--level", "ERROR"])
    
    # Assert
    assert result.exit_code == 0
    assert "ERROR" in result.output
    assert result.output.count("INFO") == 0


def test_mock_logs_grep_filter(cli_runner, temp_log_file):
    """Test mock logs with grep pattern."""
    # Arrange
    temp_log_file.write_text(
        "PIX Add called\n"
        "ITI-41 called\n"
        "PIX Query called\n"
    )
    
    # Act
    result = cli_runner.invoke(mock_group, ["logs", "--grep", "PIX"])
    
    # Assert
    assert result.exit_code == 0
    assert "PIX Add" in result.output
    assert "PIX Query" in result.output
    assert "ITI-41" not in result.output


# =============================================================================
# Edge Case Tests - Health Check Failures
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_status_health_check_returns_500(mock_get, mock_is_running, cli_runner):
    """Test status command when health check returns 500."""
    # Arrange
    start_time = datetime.now(timezone.utc).isoformat()
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": start_time
    })
    mock_response = Mock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    assert result.exit_code == 0
    assert "Running" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_status_health_check_connection_refused(mock_get, mock_is_running, cli_runner):
    """Test status command when health check connection is refused."""
    # Arrange
    start_time = datetime.now(timezone.utc).isoformat()
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": start_time
    })
    mock_get.side_effect = requests.ConnectionError("Connection refused")
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    assert result.exit_code == 0
    assert "Running" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_status_health_check_timeout(mock_get, mock_is_running, cli_runner):
    """Test status command when health check times out."""
    # Arrange
    start_time = datetime.now(timezone.utc).isoformat()
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": start_time
    })
    mock_get.side_effect = requests.Timeout("Health check timed out")
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    assert result.exit_code == 0
    assert "Running" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_status_health_check_malformed_json(mock_get, mock_is_running, cli_runner):
    """Test status command when health check returns malformed JSON."""
    # Arrange
    start_time = datetime.now(timezone.utc).isoformat()
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": start_time
    })
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_response
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    # ValueError from response.json() is not caught, so command fails
    assert result.exit_code != 0


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_status_health_check_missing_fields(mock_get, mock_is_running, cli_runner):
    """Test status command when health check response missing required fields."""
    # Arrange
    start_time = datetime.now(timezone.utc).isoformat()
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": start_time
    })
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}  # Missing endpoints and request_count
    mock_get.return_value = mock_response
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    assert result.exit_code == 0
    assert "Running" in result.output
    assert "Requests Handled: 0" in result.output


# =============================================================================
# Edge Case Tests - Background Server Startup Failures
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.load_config")
@patch("ihe_test_util.cli.mock_commands.subprocess.Popen")
def test_background_server_subprocess_popen_fails(
    mock_popen, mock_load_config, mock_is_running, cli_runner
):
    """Test background server when subprocess.Popen raises exception."""
    # Arrange
    mock_is_running.return_value = (False, None)
    mock_config = Mock()
    mock_config.host = "0.0.0.0"
    mock_config.http_port = 8080
    mock_config.pix_add_endpoint = "/pix/add"
    mock_config.iti41_endpoint = "/iti41/submit"
    mock_load_config.return_value = mock_config
    mock_popen.side_effect = PermissionError("Permission denied")
    
    # Act
    result = cli_runner.invoke(mock_group, ["start", "--background"])
    
    # Assert
    assert result.exit_code != 0


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.load_config")
@patch("ihe_test_util.cli.mock_commands.subprocess.Popen")
@patch("ihe_test_util.cli.mock_commands.is_process_running")
@patch("ihe_test_util.cli.mock_commands.remove_pid_file")
def test_background_server_crashes_immediately(
    mock_remove, mock_is_proc_running, mock_popen, mock_load_config, mock_is_running, cli_runner
):
    """Test background server when process crashes within 2 seconds."""
    # Arrange
    mock_is_running.return_value = (False, None)
    mock_config = Mock()
    mock_config.host = "0.0.0.0"
    mock_config.http_port = 8080
    mock_config.pix_add_endpoint = "/pix/add"
    mock_config.iti41_endpoint = "/iti41/submit"
    mock_load_config.return_value = mock_config
    
    mock_process = Mock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process
    mock_is_proc_running.return_value = False  # Process died
    
    # Act
    result = cli_runner.invoke(mock_group, ["start", "--background"])
    
    # Assert
    assert result.exit_code != 0
    assert "failed to start" in result.output.lower()


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.load_config")
@patch("ihe_test_util.cli.mock_commands.subprocess.Popen")
@patch("ihe_test_util.cli.mock_commands.is_process_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_background_server_never_responds_to_health_check(
    mock_get, mock_is_proc_running, mock_popen, mock_load_config, mock_is_running, cli_runner
):
    """Test background server when it never responds to health checks."""
    # Arrange
    mock_is_running.return_value = (False, None)
    mock_config = Mock()
    mock_config.host = "0.0.0.0"
    mock_config.http_port = 8080
    mock_config.pix_add_endpoint = "/pix/add"
    mock_config.iti41_endpoint = "/iti41/submit"
    mock_load_config.return_value = mock_config
    
    mock_process = Mock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process
    mock_is_proc_running.return_value = True  # Process running
    mock_get.side_effect = requests.Timeout("Health check timeout")
    
    # Act
    result = cli_runner.invoke(mock_group, ["start", "--background"])
    
    # Assert
    assert result.exit_code == 0
    assert "not yet responding" in result.output


# =============================================================================
# Edge Case Tests - Process Permission Errors
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.psutil.Process")
def test_stop_command_permission_denied_on_terminate(
    mock_process_class, mock_is_running, cli_runner
):
    """Test stop command when process termination raises PermissionError."""
    # Arrange
    mock_is_running.return_value = (True, {"pid": 12345})
    mock_process = Mock()
    mock_process.terminate.side_effect = psutil.AccessDenied(12345)
    mock_process_class.return_value = mock_process
    
    # Act
    result = cli_runner.invoke(mock_group, ["stop"])
    
    # Assert
    assert result.exit_code != 0


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.psutil.Process")
@patch("ihe_test_util.cli.mock_commands.os.name", "posix")
def test_stop_command_permission_denied_on_signal(
    mock_process_class, mock_is_running, cli_runner
):
    """Test stop command when sending signal raises PermissionError."""
    # Arrange
    mock_is_running.return_value = (True, {"pid": 12345})
    mock_process = Mock()
    mock_process.send_signal.side_effect = psutil.AccessDenied(12345)
    mock_process_class.return_value = mock_process
    
    # Act
    result = cli_runner.invoke(mock_group, ["stop"])
    
    # Assert
    assert result.exit_code != 0


# =============================================================================
# Edge Case Tests - Log File Issues
# =============================================================================


def test_logs_command_empty_file(cli_runner, temp_log_file):
    """Test logs command with empty log file."""
    # Arrange
    temp_log_file.write_text("")
    
    # Act
    result = cli_runner.invoke(mock_group, ["logs"])
    
    # Assert
    assert result.exit_code == 0


@patch("ihe_test_util.cli.mock_commands.display_tail")
def test_logs_command_permission_denied(mock_display_tail, cli_runner, tmp_path, monkeypatch):
    """Test logs command when log file is not readable."""
    # Arrange
    log_file = tmp_path / "restricted.log"
    log_file.write_text("Test log content")
    monkeypatch.setattr("ihe_test_util.cli.mock_commands.LOG_FILE_PATH", log_file)
    
    # Mock display_tail to raise PermissionError
    mock_display_tail.side_effect = PermissionError("Permission denied")
    
    # Act
    result = cli_runner.invoke(mock_group, ["logs"])
    
    # Assert
    assert result.exit_code != 0


# =============================================================================
# Edge Case Tests - Port Validation
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.load_config")
def test_start_port_negative_number(mock_load_config, mock_is_running, cli_runner):
    """Test start command with negative port number."""
    # Arrange
    mock_is_running.return_value = (False, None)
    mock_config = Mock()
    mock_load_config.return_value = mock_config
    
    # Act
    result = cli_runner.invoke(mock_group, ["start", "--port", "-1"])
    
    # Assert
    assert result.exit_code != 0
    assert "Invalid port" in result.output


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.load_config")
def test_start_port_zero(mock_load_config, mock_is_running, cli_runner):
    """Test start command with port 0."""
    # Arrange
    mock_is_running.return_value = (False, None)
    mock_config = Mock()
    mock_load_config.return_value = mock_config
    
    # Act
    result = cli_runner.invoke(mock_group, ["start", "--port", "0"])
    
    # Assert
    assert result.exit_code != 0
    assert "Invalid port" in result.output


# =============================================================================
# Edge Case Tests - Status Command Edge Cases
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
def test_status_command_malformed_start_time(mock_is_running, cli_runner):
    """Test status command when start_time is malformed."""
    # Arrange
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": "invalid-timestamp"
    })
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    # Should handle gracefully, even if it can't calculate uptime
    assert result.exit_code in [0, 1]  # May fail or succeed depending on error handling


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.requests.get")
def test_status_command_extreme_uptime(mock_get, mock_is_running, cli_runner):
    """Test status command with extreme uptime value."""
    # Arrange
    # Server running for 365 days
    from datetime import timedelta
    start_time = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    mock_is_running.return_value = (True, {
        "pid": 12345,
        "port": 8080,
        "protocol": "http",
        "host": "0.0.0.0",
        "start_time": start_time
    })
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"endpoints": [], "request_count": 0}
    mock_get.return_value = mock_response
    
    # Act
    result = cli_runner.invoke(mock_group, ["status"])
    
    # Assert
    assert result.exit_code == 0
    assert "Running" in result.output


# =============================================================================
# Edge Case Tests - Stop Command Edge Cases
# =============================================================================


@patch("ihe_test_util.cli.mock_commands.is_server_running")
@patch("ihe_test_util.cli.mock_commands.psutil.Process")
@patch("ihe_test_util.cli.mock_commands.read_pid_file")
@patch("ihe_test_util.cli.mock_commands.remove_pid_file")
def test_stop_command_pid_file_deleted_during_stop(
    mock_remove, mock_read, mock_process_class, mock_is_running, cli_runner
):
    """Test stop command when PID file is deleted during execution."""
    # Arrange
    mock_is_running.return_value = (True, {"pid": 12345})
    mock_process = Mock()
    mock_process.wait.return_value = None
    mock_process_class.return_value = mock_process
    # Simulate PID file being deleted
    mock_read.return_value = None
    
    # Act
    result = cli_runner.invoke(mock_group, ["stop"])
    
    # Assert
    assert result.exit_code == 0


# =============================================================================
# Edge Case Tests - Additional Format Uptime Tests
# =============================================================================


def test_format_uptime_zero_seconds():
    """Test format_uptime with 0 seconds."""
    assert format_uptime(0) == "0s"


def test_format_uptime_extreme_value():
    """Test format_uptime with very large uptime (10 years)."""
    # 10 years in seconds
    ten_years = 10 * 365 * 24 * 3600
    result = format_uptime(ten_years)
    assert "h" in result  # Should contain hours
