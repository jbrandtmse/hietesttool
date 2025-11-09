"""Unit tests for mock server configuration models and validation.

Tests cover:
- MockServerConfig validation with endpoint behaviors
- PIXAddBehavior and ITI41Behavior validation
- ValidationMode enum
- ConfigWatcher hot-reload functionality
"""

import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from ihe_test_util.mock_server.config import (
    ConfigWatcher,
    ITI41Behavior,
    MockServerConfig,
    PIXAddBehavior,
    ValidationMode,
    load_config,
)


class TestValidationMode:
    """Test ValidationMode enum."""

    def test_validation_mode_enum_values(self) -> None:
        """Test ValidationMode has correct enum values."""
        # Arrange & Act & Assert
        assert ValidationMode.STRICT == "strict"
        assert ValidationMode.LENIENT == "lenient"

    def test_validation_mode_enum_members(self) -> None:
        """Test ValidationMode has only expected members."""
        # Arrange & Act
        members = list(ValidationMode)

        # Assert
        assert len(members) == 2
        assert ValidationMode.STRICT in members
        assert ValidationMode.LENIENT in members

    def test_validation_mode_string_comparison(self) -> None:
        """Test ValidationMode can be compared to strings."""
        # Arrange & Act & Assert
        assert ValidationMode.STRICT == "strict"
        assert ValidationMode.LENIENT == "lenient"
        assert ValidationMode.STRICT != "lenient"


class TestPIXAddBehavior:
    """Test PIXAddBehavior configuration model."""

    def test_pix_add_behavior_defaults(self) -> None:
        """Test PIXAddBehavior default values."""
        # Arrange & Act
        behavior = PIXAddBehavior()

        # Assert
        assert behavior.response_delay_ms == 0
        assert behavior.failure_rate == 0.0
        assert behavior.custom_patient_id is None
        assert behavior.custom_fault_message is None
        assert behavior.validation_mode == ValidationMode.LENIENT

    def test_pix_add_behavior_custom_values(self) -> None:
        """Test PIXAddBehavior with custom values."""
        # Arrange & Act
        behavior = PIXAddBehavior(
            response_delay_ms=500,
            failure_rate=0.2,
            custom_patient_id="TEST-123",
            custom_fault_message="Custom error",
            validation_mode=ValidationMode.STRICT,
        )

        # Assert
        assert behavior.response_delay_ms == 500
        assert behavior.failure_rate == 0.2
        assert behavior.custom_patient_id == "TEST-123"
        assert behavior.custom_fault_message == "Custom error"
        assert behavior.validation_mode == ValidationMode.STRICT

    def test_response_delay_ms_validation_valid_range(self) -> None:
        """Test response_delay_ms accepts valid values (0-5000)."""
        # Arrange & Act & Assert
        behavior = PIXAddBehavior(response_delay_ms=0)
        assert behavior.response_delay_ms == 0

        behavior = PIXAddBehavior(response_delay_ms=2500)
        assert behavior.response_delay_ms == 2500

        behavior = PIXAddBehavior(response_delay_ms=5000)
        assert behavior.response_delay_ms == 5000

    def test_response_delay_ms_validation_negative(self) -> None:
        """Test response_delay_ms rejects negative values."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PIXAddBehavior(response_delay_ms=-1)

        assert "greater than or equal to 0" in str(exc_info.value)

    def test_response_delay_ms_validation_exceeds_max(self) -> None:
        """Test response_delay_ms rejects values > 5000."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PIXAddBehavior(response_delay_ms=5001)

        assert "less than or equal to 5000" in str(exc_info.value)

    def test_failure_rate_validation_valid_range(self) -> None:
        """Test failure_rate accepts valid values (0.0-1.0)."""
        # Arrange & Act & Assert
        behavior = PIXAddBehavior(failure_rate=0.0)
        assert behavior.failure_rate == 0.0

        behavior = PIXAddBehavior(failure_rate=0.5)
        assert behavior.failure_rate == 0.5

        behavior = PIXAddBehavior(failure_rate=1.0)
        assert behavior.failure_rate == 1.0

    def test_failure_rate_validation_negative(self) -> None:
        """Test failure_rate rejects negative values."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PIXAddBehavior(failure_rate=-0.1)

        assert "greater than or equal to 0" in str(exc_info.value)

    def test_failure_rate_validation_exceeds_max(self) -> None:
        """Test failure_rate rejects values > 1.0."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PIXAddBehavior(failure_rate=1.1)

        assert "less than or equal to 1" in str(exc_info.value)

    def test_validation_mode_accepts_enum(self) -> None:
        """Test validation_mode accepts ValidationMode enum."""
        # Arrange & Act
        behavior = PIXAddBehavior(validation_mode=ValidationMode.STRICT)

        # Assert
        assert behavior.validation_mode == ValidationMode.STRICT

    def test_validation_mode_accepts_string(self) -> None:
        """Test validation_mode accepts string values."""
        # Arrange & Act
        behavior = PIXAddBehavior(validation_mode="strict")

        # Assert
        assert behavior.validation_mode == ValidationMode.STRICT


class TestITI41Behavior:
    """Test ITI41Behavior configuration model."""

    def test_iti41_behavior_defaults(self) -> None:
        """Test ITI41Behavior default values."""
        # Arrange & Act
        behavior = ITI41Behavior()

        # Assert
        assert behavior.response_delay_ms == 0
        assert behavior.failure_rate == 0.0
        assert behavior.custom_submission_set_id is None
        assert behavior.custom_document_id is None
        assert behavior.custom_fault_message is None
        assert behavior.validation_mode == ValidationMode.LENIENT

    def test_iti41_behavior_custom_values(self) -> None:
        """Test ITI41Behavior with custom values."""
        # Arrange & Act
        behavior = ITI41Behavior(
            response_delay_ms=1000,
            failure_rate=0.15,
            custom_submission_set_id="SS-999",
            custom_document_id="DOC-999",
            custom_fault_message="Test fault",
            validation_mode=ValidationMode.STRICT,
        )

        # Assert
        assert behavior.response_delay_ms == 1000
        assert behavior.failure_rate == 0.15
        assert behavior.custom_submission_set_id == "SS-999"
        assert behavior.custom_document_id == "DOC-999"
        assert behavior.custom_fault_message == "Test fault"
        assert behavior.validation_mode == ValidationMode.STRICT

    def test_response_delay_ms_validation_valid_range(self) -> None:
        """Test response_delay_ms accepts valid values (0-5000)."""
        # Arrange & Act & Assert
        behavior = ITI41Behavior(response_delay_ms=0)
        assert behavior.response_delay_ms == 0

        behavior = ITI41Behavior(response_delay_ms=3000)
        assert behavior.response_delay_ms == 3000

        behavior = ITI41Behavior(response_delay_ms=5000)
        assert behavior.response_delay_ms == 5000

    def test_response_delay_ms_validation_negative(self) -> None:
        """Test response_delay_ms rejects negative values."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ITI41Behavior(response_delay_ms=-100)

        assert "greater than or equal to 0" in str(exc_info.value)

    def test_response_delay_ms_validation_exceeds_max(self) -> None:
        """Test response_delay_ms rejects values > 5000."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ITI41Behavior(response_delay_ms=6000)

        assert "less than or equal to 5000" in str(exc_info.value)

    def test_failure_rate_validation_valid_range(self) -> None:
        """Test failure_rate accepts valid values (0.0-1.0)."""
        # Arrange & Act & Assert
        behavior = ITI41Behavior(failure_rate=0.0)
        assert behavior.failure_rate == 0.0

        behavior = ITI41Behavior(failure_rate=0.25)
        assert behavior.failure_rate == 0.25

        behavior = ITI41Behavior(failure_rate=1.0)
        assert behavior.failure_rate == 1.0

    def test_failure_rate_validation_negative(self) -> None:
        """Test failure_rate rejects negative values."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ITI41Behavior(failure_rate=-0.5)

        assert "greater than or equal to 0" in str(exc_info.value)

    def test_failure_rate_validation_exceeds_max(self) -> None:
        """Test failure_rate rejects values > 1.0."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ITI41Behavior(failure_rate=2.0)

        assert "less than or equal to 1" in str(exc_info.value)


class TestMockServerConfigWithBehaviors:
    """Test MockServerConfig with endpoint behaviors."""

    def test_mock_server_config_behavior_defaults(self) -> None:
        """Test MockServerConfig creates default behaviors."""
        # Arrange & Act
        config = MockServerConfig()

        # Assert
        assert isinstance(config.pix_add_behavior, PIXAddBehavior)
        assert isinstance(config.iti41_behavior, ITI41Behavior)
        assert config.pix_add_behavior.response_delay_ms == 0
        assert config.iti41_behavior.response_delay_ms == 0

    def test_mock_server_config_with_custom_behaviors(self) -> None:
        """Test MockServerConfig with custom endpoint behaviors."""
        # Arrange
        pix_behavior = PIXAddBehavior(
            response_delay_ms=500,
            failure_rate=0.1,
            validation_mode=ValidationMode.STRICT,
        )
        iti41_behavior = ITI41Behavior(
            response_delay_ms=1000,
            failure_rate=0.2,
            custom_document_id="DOC-123",
        )

        # Act
        config = MockServerConfig(
            pix_add_behavior=pix_behavior,
            iti41_behavior=iti41_behavior,
        )

        # Assert
        assert config.pix_add_behavior.response_delay_ms == 500
        assert config.pix_add_behavior.failure_rate == 0.1
        assert config.pix_add_behavior.validation_mode == ValidationMode.STRICT
        assert config.iti41_behavior.response_delay_ms == 1000
        assert config.iti41_behavior.failure_rate == 0.2
        assert config.iti41_behavior.custom_document_id == "DOC-123"

    def test_load_config_with_behaviors_from_json(self, tmp_path: Path) -> None:
        """Test loading configuration with endpoint behaviors from JSON."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {
                "response_delay_ms": 500,
                "failure_rate": 0.2,
                "custom_patient_id": "PID-999",
                "validation_mode": "strict",
            },
            "iti41_behavior": {
                "response_delay_ms": 1000,
                "failure_rate": 0.15,
                "custom_submission_set_id": "SS-888",
                "custom_document_id": "DOC-888",
                "validation_mode": "lenient",
            },
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)

        # Assert
        assert config.pix_add_behavior.response_delay_ms == 500
        assert config.pix_add_behavior.failure_rate == 0.2
        assert config.pix_add_behavior.custom_patient_id == "PID-999"
        assert config.pix_add_behavior.validation_mode == ValidationMode.STRICT

        assert config.iti41_behavior.response_delay_ms == 1000
        assert config.iti41_behavior.failure_rate == 0.15
        assert config.iti41_behavior.custom_submission_set_id == "SS-888"
        assert config.iti41_behavior.custom_document_id == "DOC-888"
        assert config.iti41_behavior.validation_mode == ValidationMode.LENIENT

    def test_load_config_validates_behavior_constraints(self, tmp_path: Path) -> None:
        """Test load_config validates behavior field constraints."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {
                "response_delay_ms": 6000,  # Exceeds max
                "failure_rate": 0.5,
            },
        }
        config_file.write_text(json.dumps(config_data))

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_config(config_file)

        assert "Configuration validation failed" in str(exc_info.value)


class TestConfigWatcher:
    """Test ConfigWatcher hot-reload functionality."""

    def test_config_watcher_initialization(self, tmp_path: Path) -> None:
        """Test ConfigWatcher initializes with config path and instance."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"host": "localhost", "http_port": 8080}
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)

        # Act
        watcher = ConfigWatcher(config_file, config)

        # Assert
        assert watcher.config_path == config_file
        assert watcher.config == config
        assert watcher.last_modified > 0

    def test_config_watcher_detects_no_change(self, tmp_path: Path) -> None:
        """Test ConfigWatcher detects when file hasn't changed."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"host": "localhost", "http_port": 8080}
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # Act
        reloaded = watcher.check_reload()

        # Assert
        assert reloaded is False
        assert watcher.config.host == "localhost"

    def test_config_watcher_detects_file_change(self, tmp_path: Path) -> None:
        """Test ConfigWatcher detects file modification and reloads."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"host": "localhost", "http_port": 8080}
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # Wait briefly to ensure different modification time
        time.sleep(0.1)

        # Modify file
        new_config_data = {"host": "0.0.0.0", "http_port": 9090}
        config_file.write_text(json.dumps(new_config_data))

        # Act
        reloaded = watcher.check_reload()

        # Assert
        assert reloaded is True
        assert watcher.config.host == "0.0.0.0"
        assert watcher.config.http_port == 9090

    def test_config_watcher_updates_modification_time(self, tmp_path: Path) -> None:
        """Test ConfigWatcher updates last_modified after reload."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"host": "localhost", "http_port": 8080}
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)
        initial_mtime = watcher.last_modified

        # Wait and modify
        time.sleep(0.1)
        config_file.write_text(json.dumps({"host": "0.0.0.0", "http_port": 8080}))

        # Act
        watcher.check_reload()

        # Assert
        assert watcher.last_modified > initial_mtime

    def test_config_watcher_keeps_old_config_on_invalid_reload(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test ConfigWatcher keeps existing config when reload fails."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"host": "localhost", "http_port": 8080}
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)
        original_config = watcher.config

        # Wait and write invalid JSON
        time.sleep(0.1)
        config_file.write_text("{invalid json")

        # Act
        with caplog.at_level("WARNING"):
            reloaded = watcher.check_reload()

        # Assert
        assert reloaded is False
        assert watcher.config == original_config
        assert watcher.config.host == "localhost"
        assert any("Failed to reload configuration" in record.message for record in caplog.records)
        assert any("Keeping existing config" in record.message for record in caplog.records)

    def test_config_watcher_keeps_old_config_on_validation_failure(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test ConfigWatcher keeps existing config when new config is invalid."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"host": "localhost", "http_port": 8080}
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)
        original_host = watcher.config.host

        # Wait and write invalid config (bad port)
        time.sleep(0.1)
        invalid_config = {"host": "0.0.0.0", "http_port": 99999}
        config_file.write_text(json.dumps(invalid_config))

        # Act
        with caplog.at_level("WARNING"):
            reloaded = watcher.check_reload()

        # Assert
        assert reloaded is False
        assert watcher.config.host == original_host
        assert any("Failed to reload configuration" in record.message for record in caplog.records)

    def test_config_watcher_handles_missing_file(self, tmp_path: Path) -> None:
        """Test ConfigWatcher handles when config file is deleted."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"host": "localhost", "http_port": 8080}
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # Delete file
        config_file.unlink()

        # Act
        reloaded = watcher.check_reload()

        # Assert
        assert reloaded is False
        # Should keep existing config
        assert watcher.config.host == "localhost"

    def test_config_watcher_logs_successful_reload(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test ConfigWatcher logs INFO message on successful reload."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {"host": "localhost", "http_port": 8080}
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # Wait and modify
        time.sleep(0.1)
        config_file.write_text(json.dumps({"host": "0.0.0.0", "http_port": 8080}))

        # Act
        with caplog.at_level("INFO"):
            watcher.check_reload()

        # Assert
        assert any("Configuration reloaded" in record.message for record in caplog.records)

    def test_config_watcher_reloads_behavior_changes(self, tmp_path: Path) -> None:
        """Test ConfigWatcher reloads endpoint behavior changes."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {"response_delay_ms": 100, "failure_rate": 0.1},
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # Wait and update behaviors
        time.sleep(0.1)
        new_config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {"response_delay_ms": 500, "failure_rate": 0.5},
        }
        config_file.write_text(json.dumps(new_config_data))

        # Act
        reloaded = watcher.check_reload()

        # Assert
        assert reloaded is True
        assert watcher.config.pix_add_behavior.response_delay_ms == 500
        assert watcher.config.pix_add_behavior.failure_rate == 0.5

    def test_config_watcher_multiple_reloads(self, tmp_path: Path) -> None:
        """Test ConfigWatcher handles multiple successive reloads."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"host": "host1", "http_port": 8080}))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # First reload
        time.sleep(0.1)
        config_file.write_text(json.dumps({"host": "host2", "http_port": 8080}))
        assert watcher.check_reload() is True
        assert watcher.config.host == "host2"

        # Second reload
        time.sleep(0.1)
        config_file.write_text(json.dumps({"host": "host3", "http_port": 8080}))
        assert watcher.check_reload() is True
        assert watcher.config.host == "host3"

        # Third reload
        time.sleep(0.1)
        config_file.write_text(json.dumps({"host": "host4", "http_port": 8080}))
        assert watcher.check_reload() is True
        assert watcher.config.host == "host4"


class TestDeprecatedFields:
    """Test deprecated configuration fields."""

    def test_deprecated_response_delay_ms_field_still_works(self) -> None:
        """Test deprecated global response_delay_ms field is still accepted."""
        # Arrange & Act
        config = MockServerConfig(response_delay_ms=100)

        # Assert
        assert config.response_delay_ms == 100

    def test_deprecated_field_validation_still_enforced(self) -> None:
        """Test deprecated response_delay_ms validation still works."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            MockServerConfig(response_delay_ms=-1)

        with pytest.raises(ValidationError):
            MockServerConfig(response_delay_ms=6000)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_delay_zero_failure_rate(self) -> None:
        """Test behaviors with zero delay and zero failure rate."""
        # Arrange & Act
        pix_behavior = PIXAddBehavior(response_delay_ms=0, failure_rate=0.0)
        iti41_behavior = ITI41Behavior(response_delay_ms=0, failure_rate=0.0)

        # Assert
        assert pix_behavior.response_delay_ms == 0
        assert pix_behavior.failure_rate == 0.0
        assert iti41_behavior.response_delay_ms == 0
        assert iti41_behavior.failure_rate == 0.0

    def test_max_delay_max_failure_rate(self) -> None:
        """Test behaviors with maximum allowed values."""
        # Arrange & Act
        pix_behavior = PIXAddBehavior(response_delay_ms=5000, failure_rate=1.0)
        iti41_behavior = ITI41Behavior(response_delay_ms=5000, failure_rate=1.0)

        # Assert
        assert pix_behavior.response_delay_ms == 5000
        assert pix_behavior.failure_rate == 1.0
        assert iti41_behavior.response_delay_ms == 5000
        assert iti41_behavior.failure_rate == 1.0

    def test_empty_optional_fields(self) -> None:
        """Test behaviors with all optional fields as None."""
        # Arrange & Act
        pix_behavior = PIXAddBehavior(
            custom_patient_id=None,
            custom_fault_message=None,
        )
        iti41_behavior = ITI41Behavior(
            custom_submission_set_id=None,
            custom_document_id=None,
            custom_fault_message=None,
        )

        # Assert
        assert pix_behavior.custom_patient_id is None
        assert pix_behavior.custom_fault_message is None
        assert iti41_behavior.custom_submission_set_id is None
        assert iti41_behavior.custom_document_id is None
        assert iti41_behavior.custom_fault_message is None

    def test_fractional_failure_rates(self) -> None:
        """Test behaviors accept fractional failure rates."""
        # Arrange & Act & Assert
        for rate in [0.01, 0.05, 0.25, 0.33, 0.67, 0.95, 0.99]:
            pix_behavior = PIXAddBehavior(failure_rate=rate)
            assert pix_behavior.failure_rate == rate

            iti41_behavior = ITI41Behavior(failure_rate=rate)
            assert iti41_behavior.failure_rate == rate

    def test_config_watcher_with_nonexistent_initial_file(self, tmp_path: Path) -> None:
        """Test ConfigWatcher initialization with file that doesn't exist."""
        # Arrange
        config_file = tmp_path / "nonexistent.json"
        config = MockServerConfig()  # Use defaults

        # Act
        watcher = ConfigWatcher(config_file, config)

        # Assert
        assert watcher.config_path == config_file
        assert watcher.last_modified == 0.0
        assert watcher.check_reload() is False
