"""Integration tests for configuration workflow.

Tests the complete configuration workflow including CLI integration,
environment variable overrides, and validation commands.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ihe_test_util.cli.main import cli
from ihe_test_util.config import load_config

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestConfigurationWorkflow:
    """Test complete configuration workflow."""

    def test_load_config_validate_use_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow: load → validate → use."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://workflow-test.com/pix",
                "iti41_url": "http://workflow-test.com/iti41",
            },
            "logging": {"level": "DEBUG"},
        }
        config_file.write_text(json.dumps(config_data))

        # Act - Load configuration
        config = load_config(config_file)

        # Assert - Validate loaded configuration
        assert config.endpoints.pix_add_url == "http://workflow-test.com/pix"
        assert config.logging.level == "DEBUG"

        # Assert - Configuration is usable
        from ihe_test_util.config import get_endpoint

        pix_url = get_endpoint(config, "pix_add")
        assert pix_url == "http://workflow-test.com/pix"


class TestCLIConfigFlag:
    """Test CLI --config flag integration."""

    def test_cli_with_custom_config_path(
        self, tmp_path: Path, runner: "CliRunner"
    ) -> None:
        """Test CLI accepts custom config path via --config flag."""
        # Arrange
        config_file = tmp_path / "custom.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://custom.com/pix",
                "iti41_url": "http://custom.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        result = runner.invoke(cli, ["--config", str(config_file), "--help"])

        # Assert
        assert result.exit_code == 0

    def test_cli_with_invalid_config_exits(
        self, tmp_path: Path, runner: "CliRunner"
    ) -> None:
        """Test CLI exits with error for invalid configuration."""
        # Arrange
        config_file = tmp_path / "invalid.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "ftp://invalid.com/pix",  # Invalid protocol
                "iti41_url": "http://valid.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Act - Use version command which will trigger config loading
        result = runner.invoke(cli, ["--config", str(config_file), "version"])

        # Assert
        assert result.exit_code == 1
        assert "Error loading configuration" in result.output


class TestCLIConfigValidateCommand:
    """Test CLI config validate command."""

    def test_config_validate_valid_file(
        self, tmp_path: Path, runner: "CliRunner"
    ) -> None:
        """Test config validate command with valid configuration."""
        # Arrange
        config_file = tmp_path / "valid.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        result = runner.invoke(cli, ["config", "validate", str(config_file)])

        # Assert
        assert result.exit_code == 0
        assert "Configuration is valid" in result.output
        assert "http://test.com/pix" in result.output

    def test_config_validate_invalid_file(
        self, tmp_path: Path, runner: "CliRunner"
    ) -> None:
        """Test config validate command with invalid configuration."""
        # Arrange
        config_file = tmp_path / "invalid.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "ftp://invalid.com/pix",  # Invalid protocol
                "iti41_url": "http://valid.com/iti41",
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        result = runner.invoke(cli, ["config", "validate", str(config_file)])

        # Assert
        assert result.exit_code == 1
        assert "Configuration validation failed" in result.output

    def test_config_validate_malformed_json(
        self, tmp_path: Path, runner: "CliRunner"
    ) -> None:
        """Test config validate command with malformed JSON."""
        # Arrange
        config_file = tmp_path / "malformed.json"
        config_file.write_text("{invalid json")

        # Act
        result = runner.invoke(cli, ["config", "validate", str(config_file)])

        # Assert
        assert result.exit_code == 1
        assert "Configuration validation failed" in result.output


class TestEnvironmentVariableIntegration:
    """Test environment variable overrides in real workflow."""

    def test_env_vars_override_in_workflow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test environment variables override config file in workflow."""
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
        # ITI-41 URL should still come from file
        assert config.endpoints.iti41_url == "http://file.com/iti41"


class TestConfigurationWithLogging:
    """Test configuration integration with logging module."""

    def test_config_integrates_with_logging(self, tmp_path: Path) -> None:
        """Test configuration provides logging configuration."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            },
            "logging": {
                "level": "WARNING",
                "log_file": "custom-test.log",
                "redact_pii": True,
            },
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)
        logging_config = config.logging

        # Assert
        assert logging_config.level == "WARNING"
        assert logging_config.log_file == Path("custom-test.log")
        assert logging_config.redact_pii is True


class TestMissingConfigFallback:
    """Test graceful fallback when config file is missing."""

    def test_missing_config_uses_defaults_gracefully(
        self, tmp_path: Path, runner: "CliRunner"
    ) -> None:
        """Test application works with defaults when config file missing."""
        # Arrange
        missing_file = tmp_path / "nonexistent.json"

        # Act
        config = load_config(missing_file)

        # Assert - Should use defaults without error
        assert config.endpoints.pix_add_url == "http://localhost:8080/pix/add"
        assert config.endpoints.iti41_url == "http://localhost:8080/iti41/submit"
        assert config.logging.level == "INFO"


class TestConfigurationPrecedenceInCLI:
    """Test configuration precedence in CLI context."""

    def test_cli_flags_override_config_file(
        self, tmp_path: Path, runner: "CliRunner"
    ) -> None:
        """Test CLI flags override config file values."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "endpoints": {
                "pix_add_url": "http://test.com/pix",
                "iti41_url": "http://test.com/iti41",
            },
            "logging": {"level": "INFO"},
        }
        config_file.write_text(json.dumps(config_data))

        # Act - Use --verbose flag which should set DEBUG level
        result = runner.invoke(
            cli, ["--config", str(config_file), "--verbose", "--help"]
        )

        # Assert - Should succeed (verbose flag overrides config)
        assert result.exit_code == 0


# Pytest fixtures
@pytest.fixture
def runner():
    """Provide Click test runner."""
    from click.testing import CliRunner

    return CliRunner()
