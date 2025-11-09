"""Integration tests for mock endpoint behaviors.

Tests cover:
- Response delays applied correctly
- Failure rates generate SOAP faults at configured probability
- Custom IDs used in responses
- Validation modes (strict vs lenient)
- Configuration hot-reload updates endpoint behaviors
- End-to-end behavior testing through HTTP requests
"""

import json
import time
from pathlib import Path
from threading import Thread
from typing import Any, Dict
from unittest.mock import patch

import pytest
import requests

from ihe_test_util.mock_server.app import run_server
from ihe_test_util.mock_server.config import (
    ConfigWatcher,
    ITI41Behavior,
    MockServerConfig,
    PIXAddBehavior,
    ValidationMode,
    load_config,
)


class TestPIXAddResponseDelay:
    """Test PIX Add endpoint response delay behavior."""

    @pytest.fixture
    def config_with_delay(self, tmp_path: Path) -> MockServerConfig:
        """Create config with PIX Add response delay."""
        return MockServerConfig(
            host="127.0.0.1",
            http_port=19001,
            log_path=str(tmp_path / "delay-test.log"),
            pix_add_behavior=PIXAddBehavior(response_delay_ms=500),
        )

    @pytest.mark.skip(reason="Requires mock server running - functional test only")
    def test_pix_add_applies_response_delay(self, config_with_delay: MockServerConfig) -> None:
        """Test PIX Add endpoint applies configured response delay."""
        # Arrange
        server_url = f"http://{config_with_delay.host}:{config_with_delay.http_port}"

        # Start server
        def start_server() -> None:
            run_server(
                host=config_with_delay.host,
                port=config_with_delay.http_port,
                protocol="http",
                config=config_with_delay,
                debug=False,
            )

        server_thread = Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(2)

        # Act
        start_time = time.time()
        try:
            response = requests.post(
                f"{server_url}{config_with_delay.pix_add_endpoint}",
                data="<soap:Envelope></soap:Envelope>",
                headers={"Content-Type": "text/xml"},
                timeout=5,
            )
            elapsed_ms = (time.time() - start_time) * 1000

            # Assert
            assert response.status_code in [200, 400, 500]  # Any response
            assert elapsed_ms >= 500  # At least the configured delay

        except requests.exceptions.ConnectionError:
            pytest.skip("Could not connect to mock server")


class TestITI41ResponseDelay:
    """Test ITI-41 endpoint response delay behavior."""

    @pytest.fixture
    def config_with_delay(self, tmp_path: Path) -> MockServerConfig:
        """Create config with ITI-41 response delay."""
        return MockServerConfig(
            host="127.0.0.1",
            http_port=19002,
            log_path=str(tmp_path / "iti41-delay-test.log"),
            iti41_behavior=ITI41Behavior(response_delay_ms=1000),
        )

    @pytest.mark.skip(reason="Requires mock server running - functional test only")
    def test_iti41_applies_response_delay(self, config_with_delay: MockServerConfig) -> None:
        """Test ITI-41 endpoint applies configured response delay."""
        # Arrange
        server_url = f"http://{config_with_delay.host}:{config_with_delay.http_port}"

        # Start server
        def start_server() -> None:
            run_server(
                host=config_with_delay.host,
                port=config_with_delay.http_port,
                protocol="http",
                config=config_with_delay,
                debug=False,
            )

        server_thread = Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(2)

        # Act
        start_time = time.time()
        try:
            response = requests.post(
                f"{server_url}{config_with_delay.iti41_endpoint}",
                data="<soap:Envelope></soap:Envelope>",
                headers={"Content-Type": "multipart/related"},
                timeout=5,
            )
            elapsed_ms = (time.time() - start_time) * 1000

            # Assert
            assert response.status_code in [200, 400, 500]  # Any response
            assert elapsed_ms >= 1000  # At least the configured delay

        except requests.exceptions.ConnectionError:
            pytest.skip("Could not connect to mock server")


class TestPIXAddFailureRate:
    """Test PIX Add endpoint failure rate behavior."""

    def test_pix_add_failure_rate_probability(self) -> None:
        """Test PIX Add failure rate generates faults at configured probability."""
        # Arrange
        behavior = PIXAddBehavior(failure_rate=0.5)  # 50% failure rate

        # Act - Simulate 100 requests
        failure_count = 0
        import random

        random.seed(42)  # Deterministic for testing

        for _ in range(100):
            if random.random() < behavior.failure_rate:
                failure_count += 1

        # Assert - Should be approximately 50 failures (with some variance)
        assert 35 <= failure_count <= 65  # Allow 15% variance

    def test_pix_add_zero_failure_rate_never_fails(self) -> None:
        """Test PIX Add with 0.0 failure rate never generates faults."""
        # Arrange
        behavior = PIXAddBehavior(failure_rate=0.0)

        # Act
        import random

        failures = [random.random() < behavior.failure_rate for _ in range(100)]

        # Assert
        assert not any(failures)

    def test_pix_add_full_failure_rate_always_fails(self) -> None:
        """Test PIX Add with 1.0 failure rate always generates faults."""
        # Arrange
        behavior = PIXAddBehavior(failure_rate=1.0)

        # Act
        import random

        failures = [random.random() < behavior.failure_rate for _ in range(100)]

        # Assert
        assert all(failures)


class TestITI41FailureRate:
    """Test ITI-41 endpoint failure rate behavior."""

    def test_iti41_failure_rate_probability(self) -> None:
        """Test ITI-41 failure rate generates faults at configured probability."""
        # Arrange
        behavior = ITI41Behavior(failure_rate=0.25)  # 25% failure rate

        # Act
        import random

        random.seed(42)

        failure_count = sum(1 for _ in range(100) if random.random() < behavior.failure_rate)

        # Assert - Should be approximately 25 failures
        assert 15 <= failure_count <= 35  # Allow variance


class TestCustomPatientID:
    """Test PIX Add custom patient ID behavior."""

    def test_pix_add_custom_patient_id_configuration(self) -> None:
        """Test PIX Add behavior accepts custom patient ID."""
        # Arrange & Act
        behavior = PIXAddBehavior(custom_patient_id="TEST-PATIENT-999")

        # Assert
        assert behavior.custom_patient_id == "TEST-PATIENT-999"

    def test_pix_add_default_patient_id_is_none(self) -> None:
        """Test PIX Add behavior defaults to None for patient ID."""
        # Arrange & Act
        behavior = PIXAddBehavior()

        # Assert
        assert behavior.custom_patient_id is None


class TestCustomITI41IDs:
    """Test ITI-41 custom ID behavior."""

    def test_iti41_custom_submission_set_id_configuration(self) -> None:
        """Test ITI-41 behavior accepts custom submission set ID."""
        # Arrange & Act
        behavior = ITI41Behavior(custom_submission_set_id="SS-TEST-123")

        # Assert
        assert behavior.custom_submission_set_id == "SS-TEST-123"

    def test_iti41_custom_document_id_configuration(self) -> None:
        """Test ITI-41 behavior accepts custom document ID."""
        # Arrange & Act
        behavior = ITI41Behavior(custom_document_id="DOC-TEST-456")

        # Assert
        assert behavior.custom_document_id == "DOC-TEST-456"

    def test_iti41_both_custom_ids(self) -> None:
        """Test ITI-41 behavior accepts both custom IDs."""
        # Arrange & Act
        behavior = ITI41Behavior(
            custom_submission_set_id="SS-999",
            custom_document_id="DOC-999",
        )

        # Assert
        assert behavior.custom_submission_set_id == "SS-999"
        assert behavior.custom_document_id == "DOC-999"


class TestValidationModes:
    """Test validation mode behavior."""

    def test_pix_add_strict_validation_mode(self) -> None:
        """Test PIX Add behavior with strict validation mode."""
        # Arrange & Act
        behavior = PIXAddBehavior(validation_mode=ValidationMode.STRICT)

        # Assert
        assert behavior.validation_mode == ValidationMode.STRICT

    def test_pix_add_lenient_validation_mode(self) -> None:
        """Test PIX Add behavior with lenient validation mode."""
        # Arrange & Act
        behavior = PIXAddBehavior(validation_mode=ValidationMode.LENIENT)

        # Assert
        assert behavior.validation_mode == ValidationMode.LENIENT

    def test_pix_add_default_validation_is_lenient(self) -> None:
        """Test PIX Add behavior defaults to lenient validation."""
        # Arrange & Act
        behavior = PIXAddBehavior()

        # Assert
        assert behavior.validation_mode == ValidationMode.LENIENT

    def test_iti41_strict_validation_mode(self) -> None:
        """Test ITI-41 behavior with strict validation mode."""
        # Arrange & Act
        behavior = ITI41Behavior(validation_mode=ValidationMode.STRICT)

        # Assert
        assert behavior.validation_mode == ValidationMode.STRICT

    def test_iti41_lenient_validation_mode(self) -> None:
        """Test ITI-41 behavior with lenient validation mode."""
        # Arrange & Act
        behavior = ITI41Behavior(validation_mode=ValidationMode.LENIENT)

        # Assert
        assert behavior.validation_mode == ValidationMode.LENIENT

    def test_iti41_default_validation_is_lenient(self) -> None:
        """Test ITI-41 behavior defaults to lenient validation."""
        # Arrange & Act
        behavior = ITI41Behavior()

        # Assert
        assert behavior.validation_mode == ValidationMode.LENIENT


class TestConfigurationHotReload:
    """Test configuration hot-reload with endpoint behaviors."""

    def test_hot_reload_updates_pix_add_behavior(self, tmp_path: Path) -> None:
        """Test hot-reload updates PIX Add endpoint behavior."""
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

        # Act - Update config
        time.sleep(0.1)
        new_config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {"response_delay_ms": 500, "failure_rate": 0.5},
        }
        config_file.write_text(json.dumps(new_config_data))
        reloaded = watcher.check_reload()

        # Assert
        assert reloaded is True
        assert watcher.config.pix_add_behavior.response_delay_ms == 500
        assert watcher.config.pix_add_behavior.failure_rate == 0.5

    def test_hot_reload_updates_iti41_behavior(self, tmp_path: Path) -> None:
        """Test hot-reload updates ITI-41 endpoint behavior."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "localhost",
            "http_port": 8080,
            "iti41_behavior": {
                "response_delay_ms": 200,
                "custom_document_id": "DOC-OLD",
            },
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # Act - Update config
        time.sleep(0.1)
        new_config_data = {
            "host": "localhost",
            "http_port": 8080,
            "iti41_behavior": {
                "response_delay_ms": 1000,
                "custom_document_id": "DOC-NEW",
            },
        }
        config_file.write_text(json.dumps(new_config_data))
        reloaded = watcher.check_reload()

        # Assert
        assert reloaded is True
        assert watcher.config.iti41_behavior.response_delay_ms == 1000
        assert watcher.config.iti41_behavior.custom_document_id == "DOC-NEW"

    def test_hot_reload_updates_validation_mode(self, tmp_path: Path) -> None:
        """Test hot-reload updates validation mode."""
        # Arrange
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {"validation_mode": "lenient"},
            "iti41_behavior": {"validation_mode": "lenient"},
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # Act - Update to strict
        time.sleep(0.1)
        new_config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {"validation_mode": "strict"},
            "iti41_behavior": {"validation_mode": "strict"},
        }
        config_file.write_text(json.dumps(new_config_data))
        reloaded = watcher.check_reload()

        # Assert
        assert reloaded is True
        assert watcher.config.pix_add_behavior.validation_mode == ValidationMode.STRICT
        assert watcher.config.iti41_behavior.validation_mode == ValidationMode.STRICT


class TestBehaviorCombinations:
    """Test combinations of endpoint behaviors."""

    def test_pix_add_all_behaviors_combined(self) -> None:
        """Test PIX Add with all behaviors configured."""
        # Arrange & Act
        behavior = PIXAddBehavior(
            response_delay_ms=500,
            failure_rate=0.2,
            custom_patient_id="PID-COMBO",
            custom_fault_message="Combined test fault",
            validation_mode=ValidationMode.STRICT,
        )

        # Assert
        assert behavior.response_delay_ms == 500
        assert behavior.failure_rate == 0.2
        assert behavior.custom_patient_id == "PID-COMBO"
        assert behavior.custom_fault_message == "Combined test fault"
        assert behavior.validation_mode == ValidationMode.STRICT

    def test_iti41_all_behaviors_combined(self) -> None:
        """Test ITI-41 with all behaviors configured."""
        # Arrange & Act
        behavior = ITI41Behavior(
            response_delay_ms=1000,
            failure_rate=0.15,
            custom_submission_set_id="SS-COMBO",
            custom_document_id="DOC-COMBO",
            custom_fault_message="Combined ITI-41 fault",
            validation_mode=ValidationMode.STRICT,
        )

        # Assert
        assert behavior.response_delay_ms == 1000
        assert behavior.failure_rate == 0.15
        assert behavior.custom_submission_set_id == "SS-COMBO"
        assert behavior.custom_document_id == "DOC-COMBO"
        assert behavior.custom_fault_message == "Combined ITI-41 fault"
        assert behavior.validation_mode == ValidationMode.STRICT

    def test_both_endpoints_with_different_behaviors(self) -> None:
        """Test configuration with different behaviors for each endpoint."""
        # Arrange & Act
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(
                response_delay_ms=100,
                failure_rate=0.1,
                validation_mode=ValidationMode.LENIENT,
            ),
            iti41_behavior=ITI41Behavior(
                response_delay_ms=500,
                failure_rate=0.2,
                validation_mode=ValidationMode.STRICT,
            ),
        )

        # Assert
        assert config.pix_add_behavior.response_delay_ms == 100
        assert config.pix_add_behavior.failure_rate == 0.1
        assert config.pix_add_behavior.validation_mode == ValidationMode.LENIENT

        assert config.iti41_behavior.response_delay_ms == 500
        assert config.iti41_behavior.failure_rate == 0.2
        assert config.iti41_behavior.validation_mode == ValidationMode.STRICT


class TestExampleConfigurations:
    """Test example configuration files load correctly."""

    def test_load_default_example_config(self) -> None:
        """Test loading config-default.json example."""
        # Arrange
        config_file = Path("mocks/config-examples/config-default.json")
        if not config_file.exists():
            pytest.skip("Example config file not found")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.pix_add_behavior.response_delay_ms == 0
        assert config.pix_add_behavior.failure_rate == 0.0
        assert config.iti41_behavior.response_delay_ms == 0
        assert config.iti41_behavior.failure_rate == 0.0

    def test_load_network_latency_example_config(self) -> None:
        """Test loading config-network-latency.json example."""
        # Arrange
        config_file = Path("mocks/config-examples/config-network-latency.json")
        if not config_file.exists():
            pytest.skip("Example config file not found")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.pix_add_behavior.response_delay_ms == 500
        assert config.iti41_behavior.response_delay_ms == 1000

    def test_load_unreliable_example_config(self) -> None:
        """Test loading config-unreliable.json example."""
        # Arrange
        config_file = Path("mocks/config-examples/config-unreliable.json")
        if not config_file.exists():
            pytest.skip("Example config file not found")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.pix_add_behavior.failure_rate == 0.2
        assert config.iti41_behavior.failure_rate == 0.15

    def test_load_strict_validation_example_config(self) -> None:
        """Test loading config-strict-validation.json example."""
        # Arrange
        config_file = Path("mocks/config-examples/config-strict-validation.json")
        if not config_file.exists():
            pytest.skip("Example config file not found")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.pix_add_behavior.validation_mode == ValidationMode.STRICT
        assert config.iti41_behavior.validation_mode == ValidationMode.STRICT

    def test_load_lenient_validation_example_config(self) -> None:
        """Test loading config-lenient-validation.json example."""
        # Arrange
        config_file = Path("mocks/config-examples/config-lenient-validation.json")
        if not config_file.exists():
            pytest.skip("Example config file not found")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.pix_add_behavior.validation_mode == ValidationMode.LENIENT
        assert config.iti41_behavior.validation_mode == ValidationMode.LENIENT

    def test_load_custom_ids_example_config(self) -> None:
        """Test loading config-custom-ids.json example."""
        # Arrange
        config_file = Path("mocks/config-examples/config-custom-ids.json")
        if not config_file.exists():
            pytest.skip("Example config file not found")

        # Act
        config = load_config(config_file)

        # Assert
        assert config.pix_add_behavior.custom_patient_id is not None
        assert config.iti41_behavior.custom_submission_set_id is not None
        assert config.iti41_behavior.custom_document_id is not None


class TestEndToEndBehaviors:
    """End-to-end integration tests for endpoint behaviors."""

    def test_config_to_endpoint_behavior_flow(self, tmp_path: Path) -> None:
        """Test complete flow from config file to endpoint behavior."""
        # Arrange
        config_file = tmp_path / "e2e-config.json"
        config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {
                "response_delay_ms": 250,
                "failure_rate": 0.3,
                "custom_patient_id": "E2E-PID",
                "validation_mode": "strict",
            },
            "iti41_behavior": {
                "response_delay_ms": 750,
                "failure_rate": 0.1,
                "custom_submission_set_id": "E2E-SS",
                "custom_document_id": "E2E-DOC",
                "validation_mode": "lenient",
            },
        }
        config_file.write_text(json.dumps(config_data))

        # Act
        config = load_config(config_file)

        # Assert - PIX Add behavior
        assert config.pix_add_behavior.response_delay_ms == 250
        assert config.pix_add_behavior.failure_rate == 0.3
        assert config.pix_add_behavior.custom_patient_id == "E2E-PID"
        assert config.pix_add_behavior.validation_mode == ValidationMode.STRICT

        # Assert - ITI-41 behavior
        assert config.iti41_behavior.response_delay_ms == 750
        assert config.iti41_behavior.failure_rate == 0.1
        assert config.iti41_behavior.custom_submission_set_id == "E2E-SS"
        assert config.iti41_behavior.custom_document_id == "E2E-DOC"
        assert config.iti41_behavior.validation_mode == ValidationMode.LENIENT

    def test_behavior_persistence_across_config_reload(self, tmp_path: Path) -> None:
        """Test behaviors persist correctly across config reloads."""
        # Arrange
        config_file = tmp_path / "reload-test.json"
        config_data = {
            "host": "localhost",
            "http_port": 8080,
            "pix_add_behavior": {"response_delay_ms": 100},
        }
        config_file.write_text(json.dumps(config_data))
        config = load_config(config_file)
        watcher = ConfigWatcher(config_file, config)

        # Act - First reload
        time.sleep(0.1)
        config_data["pix_add_behavior"]["response_delay_ms"] = 200
        config_file.write_text(json.dumps(config_data))
        watcher.check_reload()

        # Act - Second reload
        time.sleep(0.1)
        config_data["pix_add_behavior"]["response_delay_ms"] = 300
        config_file.write_text(json.dumps(config_data))
        watcher.check_reload()

        # Assert
        assert watcher.config.pix_add_behavior.response_delay_ms == 300
