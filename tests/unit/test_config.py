"""Unit tests for configuration management.

Tests cover configuration loading, validation, environment variable overrides,
and error handling.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ihe_test_util.config import (
    Config,
    EndpointsConfig,
    get_certificate_paths,
    get_endpoint,
    get_logging_config,
    get_transport_config,
    load_config,
)
from ihe_test_util.config.defaults import DEFAULT_CONFIG
from ihe_test_util.utils.exceptions import ConfigurationError


class TestConfigurationSchema:
    """Test pydantic configuration models validation."""

    def test_endpoints_config_valid(self) -> None:
        """Test EndpointsConfig with valid URLs."""
        # Arrange & Act
        config = EndpointsConfig(
            pix_add_url="http://localhost:8080/pix/add",
            iti41_url="https://example.com/iti41/submit",
        )

        # Assert
        assert config.pix_add_url == "http://localhost:8080/pix/add"
        assert config.iti41_url == "https://example.com/iti41/submit"

    def test_endpoints_config_invalid_url(self) -> None:
        """Test EndpointsConfig rejects invalid URLs."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            EndpointsConfig(
                pix_add_url="ftp://invalid.com/pix",
                iti41_url="http://valid.com/iti41",
            )

        assert "Invalid URL" in str(exc_info.value)
        assert "Must start with http:// or https://" in str(exc_info.value)

    def test_certificates_config_valid_format(self) -> None:
        """Test CertificatesConfig with valid certificate format."""
        # Arrange & Act
        from ihe_test_util.config.schema import CertificatesConfig

        config = CertificatesConfig(
            cert_path=Path("cert.pem"),
            key_path=Path("key.pem"),
            cert_format="pem",
        )

        # Assert
        assert config.cert_path == Path("cert.pem")
        assert config.cert_format == "pem"

    def test_certificates_config_invalid_format(self) -> None:
        """Test CertificatesConfig rejects invalid certificate format."""
        # Arrange & Act & Assert
        from ihe_test_util.config.schema import CertificatesConfig

        with pytest.raises(ValidationError) as exc_info:
            CertificatesConfig(cert_format="invalid")

        assert "Invalid cert_format" in str(exc_info.value)
        assert "Must be one of: pem, pkcs12, der" in str(exc_info.value)

    def test_logging_config_valid_level(self) -> None:
        """Test LoggingConfig with valid log level."""
        # Arrange & Act
        from ihe_test_util.config.schema import LoggingConfig

        config = LoggingConfig(level="DEBUG")

        # Assert
        assert config.level == "DEBUG"

    def test_logging_config_case_insensitive(self) -> None:
        """Test LoggingConfig accepts case-insensitive log levels."""
        # Arrange & Act
        from ihe_test_util.config.schema import LoggingConfig

        config = LoggingConfig(level="info")

        # Assert
        assert config.level == "INFO"

    def test_logging_config_invalid_level(self) -> None:
        """Test LoggingConfig rejects invalid log level."""
        # Arrange & Act & Assert
        from ihe_test_util.config.schema import LoggingConfig

        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(level="INVALID")

        assert "Invalid log level" in str(exc_info.value)

    def test_transport_config_valid_timeouts(self) -> None:
        """Test TransportConfig with valid timeout values."""
        # Arrange & Act
        from ihe_test_util.config.schema import TransportConfig

        config = TransportConfig(timeout_connect=15, timeout_read=60)

        # Assert
        assert config.timeout_connect == 15
        assert config.timeout_read == 60

    def test_transport_config_invalid_timeout(self) -> None:
        """Test TransportConfig rejects invalid timeout values."""
        # Arrange & Act & Assert
        from ihe_test_util.config.schema import TransportConfig

        with pytest.raises(ValidationError):
            TransportConfig(timeout_connect=0)  # Must be >= 1


class TestConfigurationLoading:
    """Test configuration file loading."""

    def test_load_config_with_valid_file(self, tmp_path: Path) -> None:
        """Test loading valid configuration file."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)

        # Assert
        assert config.endpoints.pix_add_url == "http://test.com/pix"
        assert config.endpoints.iti41_url == "http://test.com/iti41"

    def test_load_config_missing_file_uses_defaults(self, tmp_path: Path) -> None:
        """Test loading missing configuration file uses defaults."""
        # Arrange
        missing_file = tmp_path / "nonexistent.json"

        # Act
        config = load_config(missing_file)

        # Assert - should use defaults
        assert config.endpoints.pix_add_url == DEFAULT_CONFIG["endpoints"]["pix_add_url"]
        assert config.endpoints.iti41_url == DEFAULT_CONFIG["endpoints"]["iti41_url"]

    def test_load_config_malformed_json(self, tmp_path: Path) -> None:
        """Test loading malformed JSON raises ConfigurationError."""
        # Arrange
        config_file = tmp_path / "bad.json"
        config_file.write_text("{invalid json")

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)

        assert "Invalid JSON" in str(exc_info.value)
        assert "Check JSON syntax" in str(exc_info.value)

    def test_load_config_with_validation_error(self, tmp_path: Path) -> None:
        """Test loading configuration with validation errors."""
        # Arrange
        config_file = tmp_path / "invalid.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "ftp://invalid.com/pix",  # Invalid protocol
                "iti41_url": "http://valid.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)

        assert "Configuration validation failed" in str(exc_info.value)


class TestEnvironmentVariableOverrides:
    """Test environment variable override functionality."""

    def test_env_override_pix_add_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test environment variable overrides PIX Add URL."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://config-file.com/pix",
                "iti41_url": "http://config-file.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))
        monkeypatch.setenv("IHE_TEST_PIX_ADD_URL", "http://env-override.com/pix")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.endpoints.pix_add_url == "http://env-override.com/pix"
        assert config.endpoints.iti41_url == "http://config-file.com/iti41"

    def test_env_override_log_level(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test environment variable overrides log level."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"endpoints": {"pix_add_url": "http://test.com/pix", "iti41_url": "http://test.com/iti41"}}
        config_file.write_text(json.dumps(config_data))
        monkeypatch.setenv("IHE_TEST_LOG_LEVEL", "DEBUG")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.logging.level == "DEBUG"

    def test_env_override_boolean_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test environment variable overrides boolean values correctly."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"endpoints": {"pix_add_url": "http://test.com/pix", "iti41_url": "http://test.com/iti41"}}
        config_file.write_text(json.dumps(config_data))
        monkeypatch.setenv("IHE_TEST_VERIFY_TLS", "false")
        monkeypatch.setenv("IHE_TEST_REDACT_PII", "true")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.transport.verify_tls is False
        assert config.logging.redact_pii is True

    def test_env_override_numeric_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test environment variable overrides numeric values."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"endpoints": {"pix_add_url": "http://test.com/pix", "iti41_url": "http://test.com/iti41"}}
        config_file.write_text(json.dumps(config_data))
        monkeypatch.setenv("IHE_TEST_TIMEOUT_CONNECT", "20")
        monkeypatch.setenv("IHE_TEST_MAX_RETRIES", "5")
        monkeypatch.setenv("IHE_TEST_BACKOFF_FACTOR", "2.5")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.transport.timeout_connect == 20
        assert config.transport.max_retries == 5
        assert config.transport.backoff_factor == 2.5


class TestConfigurationHelpers:
    """Test configuration helper functions."""

    def test_get_endpoint_pix_add(self, tmp_path: Path) -> None:
        """Test get_endpoint returns PIX Add URL."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)

        # Act
        url = get_endpoint(config, "pix_add")

        # Assert
        assert url == "http://test.com/pix"

    def test_get_endpoint_iti41(self, tmp_path: Path) -> None:
        """Test get_endpoint returns ITI-41 URL."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)

        # Act
        url = get_endpoint(config, "iti41")

        # Assert
        assert url == "http://test.com/iti41"

    def test_get_endpoint_invalid_name(self, tmp_path: Path) -> None:
        """Test get_endpoint raises error for invalid endpoint name."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            get_endpoint(config, "invalid")

        assert "Invalid endpoint name" in str(exc_info.value)

    def test_get_certificate_paths(self, tmp_path: Path) -> None:
        """Test get_certificate_paths returns Path objects."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            },
            "certificates": {
                "cert_path": "cert.pem",
                "key_path": "key.pem",
            },
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)

        # Act
        cert_path, key_path = get_certificate_paths(config)

        # Assert
        assert cert_path == Path("cert.pem")
        assert key_path == Path("key.pem")

    def test_get_transport_config(self, tmp_path: Path) -> None:
        """Test get_transport_config returns TransportConfig instance."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)

        # Act
        transport = get_transport_config(config)

        # Assert
        assert transport.verify_tls is True
        assert transport.timeout_connect == 10
        assert transport.timeout_read == 30

    def test_get_logging_config(self, tmp_path: Path) -> None:
        """Test get_logging_config returns LoggingConfig instance."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)

        # Act
        logging_cfg = get_logging_config(config)

        # Assert
        assert logging_cfg.level == "INFO"
        assert logging_cfg.redact_pii is False


class TestConfigurationPrecedence:
    """Test configuration precedence order."""

    def test_precedence_env_over_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test environment variables override config file values."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://file.com/pix",
                "iti41_url": "http://file.com/iti41",
            },
            "logging": {"level": "INFO"},
        }
        config_file.write_text(json.dumps(config_data))
        monkeypatch.setenv("IHE_TEST_PIX_ADD_URL", "http://env.com/pix")
        monkeypatch.setenv("IHE_TEST_LOG_LEVEL", "DEBUG")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.endpoints.pix_add_url == "http://env.com/pix"
        assert config.logging.level == "DEBUG"

    def test_precedence_file_over_defaults(self, tmp_path: Path) -> None:
        """Test config file values override defaults."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://custom.com/pix",
                "iti41_url": "http://custom.com/iti41",
            },
            "logging": {"level": "WARNING"},
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)

        # Assert
        assert config.endpoints.pix_add_url == "http://custom.com/pix"
        assert config.logging.level == "WARNING"


class TestDefaultConfiguration:
    """Test default configuration values."""

    def test_default_config_used_when_no_file(self, tmp_path: Path) -> None:
        """Test default configuration is used when file doesn't exist."""
        # Arrange
        missing_file = tmp_path / "nonexistent.json"

        # Act
        config = load_config(missing_file)

        # Assert
        assert config.endpoints.pix_add_url == "http://localhost:8080/pix/add"
        assert config.endpoints.iti41_url == "http://localhost:8080/iti41/submit"
        assert config.transport.verify_tls is True
        assert config.logging.level == "INFO"


class TestSensitiveValueWarnings:
    """Test warnings for sensitive values in configuration."""

    def test_warn_pkcs12_password_in_config(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test warning when PKCS12 password found in config file."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            },
            "certificates": {"pkcs12_password": "secret"},  # Should not be here!
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        with caplog.at_level("WARNING"):
            load_config(config_file)

        # Assert
        assert any("PKCS12 password" in record.message for record in caplog.records)
        assert any("environment variable" in record.message for record in caplog.records)


class TestDebugLogging:
    """Test debug logging for environment variable overrides."""

    def test_env_override_debug_logs_all_variables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test debug logs are produced for all environment variable overrides."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))
        
        # Set all possible environment variables
        monkeypatch.setenv("IHE_TEST_PIX_ADD_URL", "http://env.com/pix")
        monkeypatch.setenv("IHE_TEST_ITI41_URL", "http://env.com/iti41")
        monkeypatch.setenv("IHE_TEST_CERT_PATH", "/path/to/cert.pem")
        monkeypatch.setenv("IHE_TEST_KEY_PATH", "/path/to/key.pem")
        monkeypatch.setenv("IHE_TEST_CERT_FORMAT", "pkcs12")
        monkeypatch.setenv("IHE_TEST_VERIFY_TLS", "false")
        monkeypatch.setenv("IHE_TEST_TIMEOUT_CONNECT", "20")
        monkeypatch.setenv("IHE_TEST_TIMEOUT_READ", "60")
        monkeypatch.setenv("IHE_TEST_MAX_RETRIES", "5")
        monkeypatch.setenv("IHE_TEST_BACKOFF_FACTOR", "2.0")
        monkeypatch.setenv("IHE_TEST_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("IHE_TEST_LOG_FILE", "/var/log/test.log")
        monkeypatch.setenv("IHE_TEST_REDACT_PII", "true")

        # Act
        with caplog.at_level("DEBUG"):
            config = load_config(config_file)

        # Assert - Verify all debug messages for overrides
        debug_messages = [record.message for record in caplog.records if record.levelname == "DEBUG"]
        
        # Check that debug logs mention the overrides
        assert any("pix_add_url" in msg for msg in debug_messages)
        assert any("iti41_url" in msg for msg in debug_messages)
        assert any("cert_path" in msg for msg in debug_messages)
        assert any("key_path" in msg for msg in debug_messages)
        assert any("cert_format" in msg for msg in debug_messages)
        assert any("verify_tls" in msg for msg in debug_messages)
        assert any("timeout_connect" in msg for msg in debug_messages)
        assert any("timeout_read" in msg for msg in debug_messages)
        assert any("max_retries" in msg for msg in debug_messages)
        assert any("backoff_factor" in msg for msg in debug_messages)
        assert any("log_level" in msg for msg in debug_messages)
        assert any("log_file" in msg for msg in debug_messages)
        assert any("redact_pii" in msg for msg in debug_messages)

        # Verify the config has the environment values
        assert config.endpoints.pix_add_url == "http://env.com/pix"
        assert config.endpoints.iti41_url == "http://env.com/iti41"
        assert config.certificates.cert_path == Path("/path/to/cert.pem")
        assert config.certificates.key_path == Path("/path/to/key.pem")
        assert config.certificates.cert_format == "pkcs12"
        assert config.transport.verify_tls is False
        assert config.transport.timeout_connect == 20
        assert config.transport.timeout_read == 60
        assert config.transport.max_retries == 5
        assert config.transport.backoff_factor == 2.0
        assert config.logging.level == "DEBUG"
        assert config.logging.log_file == Path("/var/log/test.log")
        assert config.logging.redact_pii is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_json_file(self, tmp_path: Path) -> None:
        """Test handling of empty JSON file."""
        # Arrange
        config_file = tmp_path / "empty.json"
        config_file.write_text("{}")

        # Act & Assert - Should fail validation (missing required endpoints)
        with pytest.raises(ConfigurationError):
            load_config(config_file)

    def test_url_with_query_parameters(self) -> None:
        """Test URL validation with query parameters."""
        # Arrange & Act
        config = EndpointsConfig(
            pix_add_url="http://test.com/pix?param=value",
            iti41_url="https://test.com/iti41?key=123&other=456",
        )

        # Assert
        assert "?param=value" in config.pix_add_url
        assert "?key=123" in config.iti41_url

    def test_url_with_port(self) -> None:
        """Test URL validation with explicit port."""
        # Arrange & Act
        config = EndpointsConfig(
            pix_add_url="http://localhost:8080/pix",
            iti41_url="https://example.com:443/iti41",
        )

        # Assert
        assert ":8080" in config.pix_add_url
        assert ":443" in config.iti41_url

    def test_certificate_formats_all_valid(self) -> None:
        """Test all valid certificate formats."""
        # Arrange & Act
        from ihe_test_util.config.schema import CertificatesConfig

        for fmt in ["pem", "pkcs12", "der"]:
            config = CertificatesConfig(cert_format=fmt)
            assert config.cert_format == fmt

    def test_certificate_format_case_sensitive(self) -> None:
        """Test certificate format is case-sensitive."""
        # Arrange & Act & Assert
        from ihe_test_util.config.schema import CertificatesConfig

        with pytest.raises(ValidationError):
            CertificatesConfig(cert_format="PEM")  # Should be lowercase

    def test_boolean_parsing_variations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test various boolean string values."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Test truthy values
        for truthy in ["true", "True", "TRUE", "1", "yes", "Yes", "on", "ON"]:
            monkeypatch.setenv("IHE_TEST_VERIFY_TLS", truthy)
            config = load_config(config_file)
            assert config.transport.verify_tls is True, f"Failed for: {truthy}"

        # Test falsy values
        for falsy in ["false", "False", "FALSE", "0", "no", "No", "off", "OFF", "random"]:
            monkeypatch.setenv("IHE_TEST_VERIFY_TLS", falsy)
            config = load_config(config_file)
            assert config.transport.verify_tls is False, f"Failed for: {falsy}"

    def test_negative_timeout_rejected(self) -> None:
        """Test negative timeout values are rejected."""
        # Arrange & Act & Assert
        from ihe_test_util.config.schema import TransportConfig

        with pytest.raises(ValidationError):
            TransportConfig(timeout_connect=-1)

        with pytest.raises(ValidationError):
            TransportConfig(timeout_read=-5)

    def test_zero_retries_allowed(self) -> None:
        """Test zero retries is valid (no retries)."""
        # Arrange & Act
        from ihe_test_util.config.schema import TransportConfig

        config = TransportConfig(max_retries=0)

        # Assert
        assert config.max_retries == 0

    def test_negative_retries_rejected(self) -> None:
        """Test negative retries is rejected."""
        # Arrange & Act & Assert
        from ihe_test_util.config.schema import TransportConfig

        with pytest.raises(ValidationError):
            TransportConfig(max_retries=-1)

    def test_partial_configuration_uses_defaults(self, tmp_path: Path) -> None:
        """Test partial configuration fills in defaults."""
        # Arrange
        config_file = tmp_path / "partial.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://custom.com/pix",
                "iti41_url": "http://custom.com/iti41",
            }
            # Missing: certificates, transport, logging
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)

        # Assert - Should use defaults for missing sections
        assert config.transport.verify_tls is True  # Default
        assert config.transport.timeout_connect == 10  # Default
        assert config.logging.level == "INFO"  # Default
        assert config.certificates.cert_format == "pem"  # Default

    def test_null_certificate_paths_allowed(self) -> None:
        """Test null certificate paths are valid."""
        # Arrange & Act
        from ihe_test_util.config.schema import CertificatesConfig

        config = CertificatesConfig(cert_path=None, key_path=None)

        # Assert
        assert config.cert_path is None
        assert config.key_path is None

    def test_get_certificate_paths_returns_none(self, tmp_path: Path) -> None:
        """Test get_certificate_paths when paths are not configured."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)

        # Act
        cert_path, key_path = get_certificate_paths(config)

        # Assert
        assert cert_path is None
        assert key_path is None

    def test_log_level_all_valid_values(self) -> None:
        """Test all valid log levels."""
        # Arrange & Act
        from ihe_test_util.config.schema import LoggingConfig

        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            config = LoggingConfig(level=level)
            assert config.level == level

    def test_log_level_mixed_case(self) -> None:
        """Test log level accepts mixed case and normalizes to uppercase."""
        # Arrange & Act
        from ihe_test_util.config.schema import LoggingConfig

        config = LoggingConfig(level="WaRnInG")

        # Assert
        assert config.level == "WARNING"

    def test_multiple_env_overrides_simultaneously(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test multiple environment variable overrides at once."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://file.com/pix",
                "iti41_url": "http://file.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Set multiple env vars
        monkeypatch.setenv("IHE_TEST_PIX_ADD_URL", "http://env.com/pix")
        monkeypatch.setenv("IHE_TEST_ITI41_URL", "http://env.com/iti41")
        monkeypatch.setenv("IHE_TEST_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("IHE_TEST_VERIFY_TLS", "false")
        monkeypatch.setenv("IHE_TEST_TIMEOUT_CONNECT", "20")

        # Act
        config = load_config(config_file)

        # Assert - All env vars should be applied
        assert config.endpoints.pix_add_url == "http://env.com/pix"
        assert config.endpoints.iti41_url == "http://env.com/iti41"
        assert config.logging.level == "DEBUG"
        assert config.transport.verify_tls is False
        assert config.transport.timeout_connect == 20

    def test_very_large_timeout_values(self) -> None:
        """Test very large timeout values are accepted."""
        # Arrange & Act
        from ihe_test_util.config.schema import TransportConfig

        config = TransportConfig(
            timeout_connect=999999,
            timeout_read=999999,
            max_retries=1000,
        )

        # Assert
        assert config.timeout_connect == 999999
        assert config.timeout_read == 999999
        assert config.max_retries == 1000

    def test_float_backoff_factor(self) -> None:
        """Test float backoff factor with decimal precision."""
        # Arrange & Act
        from ihe_test_util.config.schema import TransportConfig

        config = TransportConfig(backoff_factor=0.5)
        assert config.backoff_factor == 0.5

        config = TransportConfig(backoff_factor=2.5)
        assert config.backoff_factor == 2.5

    def test_zero_backoff_factor(self) -> None:
        """Test zero backoff factor is valid."""
        # Arrange & Act
        from ihe_test_util.config.schema import TransportConfig

        config = TransportConfig(backoff_factor=0.0)

        # Assert
        assert config.backoff_factor == 0.0

    def test_path_object_conversion(self, tmp_path: Path) -> None:
        """Test that string paths are converted to Path objects."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            },
            "certificates": {
                "cert_path": "relative/path/cert.pem",
                "key_path": "/absolute/path/key.pem",
            },
            "logging": {
                "log_file": "logs/app.log",
            },
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)

        # Assert
        assert isinstance(config.certificates.cert_path, Path)
        assert isinstance(config.certificates.key_path, Path)
        assert isinstance(config.logging.log_file, Path)

    def test_urls_with_special_characters(self) -> None:
        """Test URLs with special characters in path."""
        # Arrange & Act
        config = EndpointsConfig(
            pix_add_url="http://test.com/pix-add/v1",
            iti41_url="https://test.com/iti_41/submit",
        )

        # Assert
        assert config.pix_add_url == "http://test.com/pix-add/v1"
        assert config.iti41_url == "https://test.com/iti_41/submit"

    def test_empty_string_url_rejected(self) -> None:
        """Test empty string URL is rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            EndpointsConfig(
                pix_add_url="",
                iti41_url="http://test.com/iti41",
            )

    def test_whitespace_only_url_rejected(self) -> None:
        """Test whitespace-only URL is rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            EndpointsConfig(
                pix_add_url="   ",
                iti41_url="http://test.com/iti41",
            )

    def test_config_immutability(self, tmp_path: Path) -> None:
        """Test that Config objects can be used multiple times."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)

        # Multiple accesses should return same values
        url1 = get_endpoint(config, "pix_add")
        url2 = get_endpoint(config, "pix_add")

        # Assert
        assert url1 == url2 == "http://test.com/pix"

    def test_invalid_json_special_characters(self, tmp_path: Path) -> None:
        """Test handling of invalid JSON with special characters."""
        # Arrange
        config_file = tmp_path / "invalid.json"
        config_file.write_text('{"endpoints": {"pix_add_url": "test"}}')  # Missing closing quote

        # Act & Assert
        # Note: This is actually valid JSON, let me create truly invalid JSON
        config_file.write_text('{"endpoints": {pix_add_url: "test"}}')  # Missing quotes on key

        with pytest.raises(ConfigurationError):
            load_config(config_file)
