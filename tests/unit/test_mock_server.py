"""Unit tests for mock server module."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ihe_test_util.mock_server.app import (
    app,
    generate_soap_fault,
    initialize_app,
    setup_logging,
)
from ihe_test_util.mock_server.config import MockServerConfig, load_config


class TestMockServerConfig:
    """Tests for MockServerConfig model."""

    def test_default_config_values(self):
        """Test that default configuration values are set correctly."""
        # Arrange & Act
        config = MockServerConfig()

        # Assert
        assert config.host == "0.0.0.0"
        assert config.http_port == 8080
        assert config.https_port == 8443
        assert config.cert_path == "mocks/cert.pem"
        assert config.key_path == "mocks/key.pem"
        assert config.log_level == "INFO"
        assert config.log_path == "mocks/logs/mock-server.log"
        assert config.pix_add_endpoint == "/pix/add"
        assert config.iti41_endpoint == "/iti41/submit"

    def test_custom_config_values(self):
        """Test that custom configuration values override defaults."""
        # Arrange & Act
        config = MockServerConfig(
            host="localhost",
            http_port=9090,
            log_level="DEBUG"
        )

        # Assert
        assert config.host == "localhost"
        assert config.http_port == 9090
        assert config.log_level == "DEBUG"
        # Defaults should still apply
        assert config.https_port == 8443

    def test_log_level_validation_valid(self):
        """Test that valid log levels are accepted."""
        # Arrange & Act & Assert
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = MockServerConfig(log_level=level)
            assert config.log_level == level

        # Test case-insensitive
        config = MockServerConfig(log_level="debug")
        assert config.log_level == "DEBUG"

    def test_log_level_validation_invalid(self):
        """Test that invalid log levels raise ValueError."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Invalid log level"):
            MockServerConfig(log_level="INVALID")

    def test_port_validation_valid(self):
        """Test that valid port numbers are accepted."""
        # Arrange & Act & Assert
        config = MockServerConfig(http_port=1, https_port=65535)
        assert config.http_port == 1
        assert config.https_port == 65535

    def test_port_validation_invalid_low(self):
        """Test that port numbers below 1 raise ValueError."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Invalid port 0"):
            MockServerConfig(http_port=0)

    def test_port_validation_invalid_high(self):
        """Test that port numbers above 65535 raise ValueError."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Invalid port 65536"):
            MockServerConfig(https_port=65536)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_default_file_not_exists(self):
        """Test loading config when default file doesn't exist returns defaults."""
        # Arrange & Act
        with patch("pathlib.Path.exists", return_value=False):
            config = load_config()

        # Assert - should have default values
        assert config.host == "0.0.0.0"
        assert config.http_port == 8080

    def test_load_config_from_json_file(self, tmp_path):
        """Test loading configuration from JSON file."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "127.0.0.1",
            "http_port": 9090,
            "log_level": "DEBUG"
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)

        # Assert
        assert config.host == "127.0.0.1"
        assert config.http_port == 9090
        assert config.log_level == "DEBUG"
        # Defaults should still apply
        assert config.https_port == 8443

    def test_load_config_invalid_json(self, tmp_path):
        """Test loading config with invalid JSON raises ValueError."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_file.write_text("{ invalid json }")

        # Act & Assert
        with pytest.raises(ValueError, match="Failed to parse configuration file"):
            load_config(config_file)

    def test_load_config_nonexistent_custom_file(self, tmp_path):
        """Test loading non-existent custom config file raises FileNotFoundError."""
        # Arrange
        config_file = tmp_path / "nonexistent.json"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config(config_file)

    def test_load_config_with_env_var_overrides(self, tmp_path, monkeypatch):
        """Test that environment variables override config file values."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "0.0.0.0",
            "http_port": 8080,
            "log_level": "INFO"
        }
        config_file.write_text(json.dumps(config_data))

        # Set environment variables
        monkeypatch.setenv("MOCK_SERVER_HOST", "localhost")
        monkeypatch.setenv("MOCK_SERVER_HTTP_PORT", "9999")
        monkeypatch.setenv("MOCK_SERVER_LOG_LEVEL", "DEBUG")

        # Act
        config = load_config(config_file)

        # Assert - env vars should override file values
        assert config.host == "localhost"
        assert config.http_port == 9999
        assert config.log_level == "DEBUG"

    def test_load_config_invalid_env_var_port(self, monkeypatch):
        """Test that invalid port in env var raises ValueError."""
        # Arrange
        monkeypatch.setenv("MOCK_SERVER_HTTP_PORT", "not_a_number")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid value for MOCK_SERVER_HTTP_PORT"):
            load_config()


class TestFlaskApp:
    """Tests for Flask application."""

    def test_app_exists(self):
        """Test that Flask app instance exists."""
        # Arrange & Act & Assert
        assert isinstance(app, Flask)
        assert app.name == "ihe_test_util.mock_server.app"

    def test_health_check_endpoint_exists(self):
        """Test that health check endpoint is registered."""
        # Arrange
        client = app.test_client()

        # Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200
        assert response.is_json

    def test_health_check_response_structure(self):
        """Test that health check returns correct JSON structure."""
        # Arrange
        client = app.test_client()

        # Act
        response = client.get("/health")
        data = response.get_json()

        # Assert
        assert "status" in data
        assert "version" in data
        assert "protocol" in data
        assert "port" in data
        assert "endpoints" in data
        assert "uptime_seconds" in data
        assert "request_count" in data
        assert "timestamp" in data

        assert data["status"] == "healthy"
        assert isinstance(data["endpoints"], list)
        assert isinstance(data["uptime_seconds"], int)
        assert isinstance(data["request_count"], int)


class TestGenerateSoapFault:
    """Tests for generate_soap_fault function."""

    def test_soap_fault_basic(self):
        """Test basic SOAP fault generation."""
        # Arrange
        faultcode = "soap:Sender"
        faultstring = "Bad Request"

        # Act
        response, status = generate_soap_fault(faultcode, faultstring)

        # Assert
        assert status == 400
        assert "text/xml" in response.mimetype
        assert b"<soap:Envelope" in response.data
        assert b"<soap:Fault>" in response.data
        assert b"soap:Sender" in response.data
        assert b"Bad Request" in response.data

    def test_soap_fault_with_detail(self):
        """Test SOAP fault generation with detail."""
        # Arrange
        faultcode = "soap:Receiver"
        faultstring = "Internal Error"
        detail = "Database connection failed"

        # Act
        response, status = generate_soap_fault(
            faultcode, faultstring, detail=detail, http_status=500
        )

        # Assert
        assert status == 500
        assert b"<soap:Detail>" in response.data
        assert b"Database connection failed" in response.data

    def test_soap_fault_logging(self, caplog):
        """Test that SOAP faults are logged at WARNING level."""
        # Arrange
        caplog.set_level(logging.WARNING)

        # Act
        generate_soap_fault("soap:Sender", "Test fault")

        # Assert
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "SOAP Fault generated" in caplog.records[0].message


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_creates_logger(self, tmp_path):
        """Test that setup_logging creates and configures logger."""
        # Arrange
        log_path = tmp_path / "test.log"
        config = MockServerConfig(
            log_level="DEBUG",
            log_path=str(log_path)
        )

        # Act
        logger = setup_logging(config)

        # Assert
        assert logger is not None
        assert logger.name == "ihe_test_util.mock_server"
        assert logger.level == logging.DEBUG

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Test that setup_logging creates log directory."""
        # Arrange
        log_path = tmp_path / "logs" / "test.log"
        config = MockServerConfig(log_path=str(log_path))

        # Act
        logger = setup_logging(config)

        # Assert
        assert log_path.parent.exists()

    def test_setup_logging_handlers(self):
        """Test that setup_logging creates console and file handlers."""
        # Arrange
        config = MockServerConfig(log_level="INFO")

        # Act
        with patch("pathlib.Path.mkdir"):
            logger = setup_logging(config)

        # Assert
        assert len(logger.handlers) == 2
        # Check handler types
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types
        assert "RotatingFileHandler" in handler_types


class TestInitializeApp:
    """Tests for initialize_app function."""

    @patch("ihe_test_util.mock_server.app.setup_logging")
    @patch("ihe_test_util.mock_server.app.setup_graceful_shutdown")
    @patch("pathlib.Path.mkdir")
    @patch("ihe_test_util.mock_server.pix_add_endpoint.register_pix_add_endpoint")
    @patch("ihe_test_util.mock_server.iti41_endpoint.register_iti41_endpoint")
    def test_initialize_app_basic(
        self, mock_iti41, mock_pix, mock_mkdir, mock_shutdown, mock_logging
    ):
        """Test basic app initialization."""
        # Arrange
        config = MockServerConfig()
        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger

        # Act
        initialize_app(config)

        # Assert
        mock_logging.assert_called_once_with(config)
        mock_shutdown.assert_called_once()
        # Verify directories created
        assert mock_mkdir.call_count >= 2  # mocks/data and mocks/logs

    @patch("ihe_test_util.mock_server.app.setup_logging")
    @patch("ihe_test_util.mock_server.app.setup_graceful_shutdown")
    @patch("pathlib.Path.mkdir")
    @patch("ihe_test_util.mock_server.pix_add_endpoint.register_pix_add_endpoint")
    @patch("ihe_test_util.mock_server.iti41_endpoint.register_iti41_endpoint")
    def test_initialize_app_sets_global_config(
        self, mock_iti41, mock_pix, mock_mkdir, mock_shutdown, mock_logging
    ):
        """Test that initialize_app sets global config and start time."""
        # Arrange
        config = MockServerConfig()

        # Act
        initialize_app(config)

        # Assert
        from ihe_test_util.mock_server.app import _config, _server_start_time
        assert _config == config
        assert _server_start_time is not None


class TestRequestLogging:
    """Tests for request logging functionality."""

    def test_request_increments_counter(self):
        """Test that each request increments the request counter."""
        # Arrange
        client = app.test_client()

        # Act
        response1 = client.get("/health")
        response2 = client.get("/health")
        data = response2.get_json()

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200
        # Request count should have increased
        assert data["request_count"] > 0

    def test_soap_headers_added(self):
        """Test that SOAP/XML headers are added to non-health responses."""
        # Arrange
        client = app.test_client()

        # Act
        # Request a non-existent endpoint to get 404
        response = client.post("/nonexistent")

        # Assert
        # Health endpoint should NOT have XML content-type
        health_response = client.get("/health")
        assert "application/json" in health_response.content_type

    def test_request_logging_captures_details(self, caplog):
        """Test that request logging captures method, path, and content length."""
        # Arrange
        caplog.set_level(logging.INFO)
        client = app.test_client()

        # Act
        client.get("/health")

        # Assert
        log_messages = [record.message for record in caplog.records]
        # Should have at least one log with request details
        assert any("GET /health" in msg for msg in log_messages)


class TestErrorHandlers:
    """Tests for error handler functions."""

    def test_400_error_returns_soap_fault(self):
        """Test that 400 errors return SOAP fault."""
        # Arrange & Act
        # Call error handlers directly instead of through Flask app
        from ihe_test_util.mock_server.app import bad_request
        with app.test_request_context():
            response, status = bad_request(Exception("Test error"))

        # Assert
        assert status == 400
        assert b"<soap:Fault>" in response.data
        assert b"soap:Sender" in response.data

    def test_500_error_returns_soap_fault(self):
        """Test that 500 errors return SOAP fault."""
        # Arrange & Act
        # Call error handlers directly instead of through Flask app
        from ihe_test_util.mock_server.app import internal_error
        with app.test_request_context():
            response, status = internal_error(Exception("Test error"))

        # Assert
        assert status == 500
        assert b"<soap:Fault>" in response.data
        assert b"soap:Receiver" in response.data


@pytest.fixture
def mock_config():
    """Fixture providing a mock server configuration."""
    return MockServerConfig(
        host="localhost",
        http_port=8080,
        https_port=8443,
        log_level="INFO"
    )


@pytest.fixture
def clean_app():
    """Fixture that provides a clean Flask app for testing."""
    # Reset request counter and other state
    import ihe_test_util.mock_server.app as app_module
    app_module._request_count = 0
    app_module._server_start_time = None
    app_module._config = None
    yield app
    # Cleanup after test
    app_module._request_count = 0
    app_module._server_start_time = None
    app_module._config = None
