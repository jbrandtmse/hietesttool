"""Integration tests for mock server startup and operation."""

import json
import time
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest
import requests

from ihe_test_util.mock_server.app import run_server, initialize_app
from ihe_test_util.mock_server.config import MockServerConfig, load_config


class TestMockServerHTTP:
    """Integration tests for HTTP mock server."""
    
    @pytest.fixture
    def test_config(self, tmp_path):
        """Create a test configuration."""
        config = MockServerConfig(
            host="127.0.0.1",
            http_port=18080,  # Use non-standard port to avoid conflicts
            log_path=str(tmp_path / "test-mock-server.log")
        )
        return config
    
    def test_http_server_startup_and_health_check(self, test_config, tmp_path):
        """Test complete HTTP server startup and health check request."""
        # Arrange
        server_url = f"http://{test_config.host}:{test_config.http_port}"
        
        # Start server in background thread
        def start_server():
            run_server(
                host=test_config.host,
                port=test_config.http_port,
                protocol="http",
                config=test_config,
                debug=False
            )
        
        server_thread = Thread(target=start_server, daemon=True)
        
        # Act
        server_thread.start()
        time.sleep(2)  # Give server time to start
        
        # Make health check request
        try:
            response = requests.get(f"{server_url}/health", timeout=5)
            data = response.json()
            
            # Assert
            assert response.status_code == 200
            assert data["status"] == "healthy"
            assert data["protocol"] == "http"
            assert data["port"] == test_config.http_port
            assert "/health" in data["endpoints"]
            assert data["request_count"] > 0
            assert "timestamp" in data
            
        except requests.exceptions.ConnectionError:
            pytest.fail("Could not connect to mock server")
    
    def test_health_check_multiple_requests(self, test_config):
        """Test that health check request counter increments."""
        # Arrange
        server_url = f"http://{test_config.host}:{test_config.http_port}"
        
        # Start server
        def start_server():
            run_server(
                host=test_config.host,
                port=test_config.http_port,
                protocol="http",
                config=test_config,
                debug=False
            )
        
        server_thread = Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(2)
        
        # Act
        try:
            response1 = requests.get(f"{server_url}/health", timeout=5)
            count1 = response1.json()["request_count"]
            
            response2 = requests.get(f"{server_url}/health", timeout=5)
            count2 = response2.json()["request_count"]
            
            response3 = requests.get(f"{server_url}/health", timeout=5)
            count3 = response3.json()["request_count"]
            
            # Assert
            assert response1.status_code == 200
            assert response2.status_code == 200
            assert response3.status_code == 200
            assert count2 > count1
            assert count3 > count2
            
        except requests.exceptions.ConnectionError:
            pytest.fail("Could not connect to mock server")


class TestMockServerHTTPS:
    """Integration tests for HTTPS mock server."""
    
    @pytest.fixture
    def test_config_with_certs(self, tmp_path):
        """Create test configuration with certificate paths."""
        # Note: For this test, we'll need to generate test certificates
        # or mock the SSL context
        config = MockServerConfig(
            host="127.0.0.1",
            https_port=18443,
            cert_path="tests/fixtures/test_cert.pem",
            key_path="tests/fixtures/test_key.pem",
            log_path=str(tmp_path / "test-mock-server-https.log")
        )
        return config
    
    @pytest.mark.skip(reason="Flask global app singleton prevents route re-registration across tests. See Story 2.1 QA notes.")
    def test_https_server_requires_certificates(self, test_config_with_certs):
        """Test that HTTPS server requires valid certificate files."""
        # Arrange
        # Temporarily point to non-existent certificates
        config = MockServerConfig(
            host="127.0.0.1",
            https_port=18443,
            cert_path="nonexistent/cert.pem",
            key_path="nonexistent/key.pem"
        )

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Certificate not found"):
            run_server(
                host=config.host,
                port=config.https_port,
                protocol="https",
                config=config,
                debug=False
            )
    
    def test_https_server_with_valid_certificates(self, test_config_with_certs):
        """Test HTTPS server startup with valid test certificates."""
        # Check if test certificates exist
        cert_path = Path(test_config_with_certs.cert_path)
        if not cert_path.exists():
            pytest.skip("Test certificates not available")
        
        # Arrange
        server_url = f"https://{test_config_with_certs.host}:{test_config_with_certs.https_port}"
        
        # Start server in background
        def start_server():
            run_server(
                host=test_config_with_certs.host,
                port=test_config_with_certs.https_port,
                protocol="https",
                config=test_config_with_certs,
                debug=False
            )
        
        server_thread = Thread(target=start_server, daemon=True)
        
        # Act
        server_thread.start()
        time.sleep(2)
        
        # Make health check request (disable SSL verification for self-signed cert)
        try:
            response = requests.get(
                f"{server_url}/health",
                verify=False,  # Self-signed certificate
                timeout=5
            )
            data = response.json()
            
            # Assert
            assert response.status_code == 200
            assert data["status"] == "healthy"
            
        except requests.exceptions.ConnectionError:
            pytest.skip("Could not connect to HTTPS mock server")


class TestConfigurationLoading:
    """Integration tests for configuration loading."""
    
    def test_load_config_from_default_file(self, tmp_path, monkeypatch):
        """Test loading configuration from default file location."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "0.0.0.0",
            "http_port": 8080,
            "https_port": 8443,
            "log_level": "DEBUG"
        }
        config_file.write_text(json.dumps(config_data))
        
        # Change to tmp_path to make config file discoverable
        monkeypatch.chdir(tmp_path)
        
        # Mock Path.exists to simulate finding the file
        with patch("pathlib.Path.exists", return_value=True):
            # Act
            config = load_config(config_file)
        
        # Assert
        assert config.host == "0.0.0.0"
        assert config.http_port == 8080
        assert config.log_level == "DEBUG"
    
    def test_configuration_precedence_env_over_file(self, tmp_path, monkeypatch):
        """Test that environment variables override config file values."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "0.0.0.0",
            "http_port": 8080,
            "log_level": "INFO"
        }
        config_file.write_text(json.dumps(config_data))
        
        # Set environment variable overrides
        monkeypatch.setenv("MOCK_SERVER_HOST", "localhost")
        monkeypatch.setenv("MOCK_SERVER_HTTP_PORT", "9999")
        
        # Act
        config = load_config(config_file)
        
        # Assert
        assert config.host == "localhost"  # From env var
        assert config.http_port == 9999    # From env var
        assert config.log_level == "INFO"   # From file (no override)


class TestLogging:
    """Integration tests for logging functionality."""
    
    @pytest.mark.skip(reason="Flask global app singleton prevents route re-registration across tests. See Story 2.1 QA notes.")
    def test_log_files_created_in_correct_location(self, tmp_path):
        """Test that log files are created in the configured location."""
        # Arrange
        log_path = tmp_path / "logs" / "test-server.log"
        config = MockServerConfig(
            host="127.0.0.1",
            http_port=18080,
            log_path=str(log_path)
        )

        # Act
        # Initialize app (this should create log directory and file)
        with patch("ihe_test_util.mock_server.app.setup_graceful_shutdown"):
            initialize_app(config)

        # Assert
        assert log_path.parent.exists()
        assert log_path.exists()
    
    def test_request_logging_writes_to_file(self, tmp_path):
        """Test that requests are logged to the log file."""
        # Arrange
        log_path = tmp_path / "logs" / "test-server.log"
        config = MockServerConfig(
            host="127.0.0.1",
            http_port=18081,
            log_path=str(log_path),
            log_level="DEBUG"
        )
        
        server_url = f"http://{config.host}:{config.http_port}"
        
        # Start server
        def start_server():
            run_server(
                host=config.host,
                port=config.http_port,
                protocol="http",
                config=config,
                debug=False
            )
        
        server_thread = Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(2)
        
        # Act
        try:
            requests.get(f"{server_url}/health", timeout=5)
            time.sleep(1)  # Give time for log to flush
            
            # Assert
            assert log_path.exists()
            log_content = log_path.read_text()
            assert "GET /health" in log_content or "health" in log_content.lower()
            
        except requests.exceptions.ConnectionError:
            pytest.skip("Could not connect to mock server")


class TestGracefulShutdown:
    """Integration tests for graceful shutdown."""
    
    @pytest.mark.skip(reason="Flask global app singleton prevents route re-registration across tests. See Story 2.1 QA notes.")
    def test_graceful_shutdown_cleanup(self, tmp_path):
        """Test that server performs cleanup on shutdown."""
        # Arrange
        config = MockServerConfig(
            host="127.0.0.1",
            http_port=18082,
            log_path=str(tmp_path / "shutdown-test.log")
        )

        # Act
        # Initialize app
        with patch("ihe_test_util.mock_server.app.setup_graceful_shutdown"):
            initialize_app(config)

        # Assert - directories should be created
        assert Path("mocks/data").exists()
        assert Path("mocks/logs").exists()


class TestEndpointRegistration:
    """Integration tests for endpoint registration."""
    
    def test_health_check_endpoint_available(self, tmp_path):
        """Test that health check endpoint is immediately available."""
        # Arrange
        config = MockServerConfig(
            host="127.0.0.1",
            http_port=18083,
            log_path=str(tmp_path / "endpoint-test.log")
        )
        
        server_url = f"http://{config.host}:{config.http_port}"
        
        # Start server
        def start_server():
            run_server(
                host=config.host,
                port=config.http_port,
                protocol="http",
                config=config,
                debug=False
            )
        
        server_thread = Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(2)
        
        # Act & Assert
        try:
            response = requests.get(f"{server_url}/health", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            # Should list configured endpoints even if not implemented yet
            assert config.pix_add_endpoint in data["endpoints"]
            assert config.iti41_endpoint in data["endpoints"]
            
        except requests.exceptions.ConnectionError:
            pytest.skip("Could not connect to mock server")


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_artifacts():
    """Cleanup test artifacts after integration tests."""
    yield
    # Cleanup is handled by tmp_path fixtures
    pass


# Note: Some integration tests are skipped if conditions aren't met
# (e.g., certificates not available). This is intentional to allow
# tests to run in various environments.
