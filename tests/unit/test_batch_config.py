"""Unit tests for batch processing configuration.

Tests for Story 6.6: Batch Processing & Configuration Management.

This module tests:
- BatchConfig, TemplateConfig, OperationLoggingConfig schema validation
- Environment variable overrides for batch settings
- BatchCheckpoint serialization/deserialization
- BatchStatistics calculation
- OutputManager directory organization
- ConnectionPool configuration
- Per-operation logging configuration
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ihe_test_util.config.schema import (
    BatchConfig,
    Config,
    OperationLoggingConfig,
    TemplateConfig,
)
from ihe_test_util.config.manager import (
    get_batch_config,
    get_operation_logging_config,
    get_template_config,
    load_config,
)
from ihe_test_util.models.batch import (
    BatchCheckpoint,
    BatchStatistics,
    BatchWorkflowResult,
    PatientWorkflowResult,
)
from ihe_test_util.transport.http_client import (
    ConnectionPool,
    ConnectionPoolConfig,
    create_session_with_pool,
    get_default_pool,
    reset_default_pool,
)
from ihe_test_util.logging_audit.logger import (
    configure_operation_logging,
    configure_operation_logging_from_config,
    get_operation_logger,
    set_operation_log_level,
)
from ihe_test_util.utils.output_manager import OutputManager, OutputPaths


class TestBatchConfigValidation:
    """Tests for BatchConfig pydantic model validation."""

    def test_batch_config_defaults(self):
        """Test that BatchConfig has correct default values."""
        # Arrange & Act
        config = BatchConfig()

        # Assert
        assert config.batch_size == 100
        assert config.checkpoint_interval == 50
        assert config.fail_fast is False
        assert config.concurrent_connections == 10
        assert config.output_dir == Path("output")
        assert config.resume_enabled is True
        assert config.checkpoint_file is None

    def test_batch_config_custom_values(self):
        """Test BatchConfig with custom values."""
        # Arrange & Act
        config = BatchConfig(
            batch_size=500,
            checkpoint_interval=100,
            fail_fast=True,
            concurrent_connections=20,
            output_dir=Path("custom/output"),
            resume_enabled=False,
        )

        # Assert
        assert config.batch_size == 500
        assert config.checkpoint_interval == 100
        assert config.fail_fast is True
        assert config.concurrent_connections == 20
        assert config.output_dir == Path("custom/output")
        assert config.resume_enabled is False

    def test_batch_config_validation_batch_size_minimum(self):
        """Test that batch_size must be at least 1."""
        # Arrange, Act & Assert
        with pytest.raises(ValueError):
            BatchConfig(batch_size=0)

    def test_batch_config_validation_checkpoint_interval_minimum(self):
        """Test that checkpoint_interval must be at least 1."""
        # Arrange, Act & Assert
        with pytest.raises(ValueError):
            BatchConfig(checkpoint_interval=0)

    def test_batch_config_validation_concurrent_connections_range(self):
        """Test that concurrent_connections must be between 1 and 50."""
        # Arrange, Act & Assert
        with pytest.raises(ValueError):
            BatchConfig(concurrent_connections=0)

        with pytest.raises(ValueError):
            BatchConfig(concurrent_connections=51)


class TestTemplateConfigValidation:
    """Tests for TemplateConfig pydantic model validation."""

    def test_template_config_defaults(self):
        """Test that TemplateConfig has correct default values."""
        # Arrange & Act
        config = TemplateConfig()

        # Assert
        assert config.ccd_template_path is None
        assert config.saml_template_path is None

    def test_template_config_custom_paths(self):
        """Test TemplateConfig with custom paths."""
        # Arrange & Act
        config = TemplateConfig(
            ccd_template_path=Path("templates/custom-ccd.xml"),
            saml_template_path=Path("templates/custom-saml.xml"),
        )

        # Assert
        assert config.ccd_template_path == Path("templates/custom-ccd.xml")
        assert config.saml_template_path == Path("templates/custom-saml.xml")


class TestOperationLoggingConfigValidation:
    """Tests for OperationLoggingConfig pydantic model validation."""

    def test_operation_logging_config_defaults(self):
        """Test that OperationLoggingConfig has correct default values."""
        # Arrange & Act
        config = OperationLoggingConfig()

        # Assert
        assert config.csv_log_level == "INFO"
        assert config.pix_add_log_level == "INFO"
        assert config.iti41_log_level == "INFO"
        assert config.saml_log_level == "WARNING"

    def test_operation_logging_config_custom_levels(self):
        """Test OperationLoggingConfig with custom log levels."""
        # Arrange & Act
        config = OperationLoggingConfig(
            csv_log_level="DEBUG",
            pix_add_log_level="DEBUG",
            iti41_log_level="WARNING",
            saml_log_level="ERROR",
        )

        # Assert
        assert config.csv_log_level == "DEBUG"
        assert config.pix_add_log_level == "DEBUG"
        assert config.iti41_log_level == "WARNING"
        assert config.saml_log_level == "ERROR"


class TestEnvOverrideBatchSettings:
    """Tests for environment variable overrides of batch settings."""

    @pytest.fixture
    def base_config(self):
        """Return base config with required fields."""
        return {
            "endpoints": {
                "pix_add_url": "http://localhost:8080/pix/add",
                "iti41_url": "http://localhost:8080/iti41/submit"
            }
        }

    def test_env_override_batch_size(self, tmp_path, monkeypatch, base_config):
        """Test IHE_TEST_BATCH_SIZE environment variable override."""
        # Arrange
        config_file = tmp_path / "config.json"
        base_config["batch"] = {"batch_size": 100}
        config_file.write_text(json.dumps(base_config))
        monkeypatch.setenv("IHE_TEST_BATCH_SIZE", "250")

        # Act
        config = load_config(config_file)
        batch_config = get_batch_config(config)

        # Assert
        assert batch_config.batch_size == 250

    def test_env_override_checkpoint_interval(self, tmp_path, monkeypatch, base_config):
        """Test IHE_TEST_BATCH_CHECKPOINT_INTERVAL environment variable override."""
        # Arrange
        config_file = tmp_path / "config.json"
        base_config["batch"] = {"checkpoint_interval": 50}
        config_file.write_text(json.dumps(base_config))
        monkeypatch.setenv("IHE_TEST_BATCH_CHECKPOINT_INTERVAL", "75")

        # Act
        config = load_config(config_file)
        batch_config = get_batch_config(config)

        # Assert
        assert batch_config.checkpoint_interval == 75

    def test_env_override_fail_fast(self, tmp_path, monkeypatch, base_config):
        """Test IHE_TEST_BATCH_FAIL_FAST environment variable override."""
        # Arrange
        config_file = tmp_path / "config.json"
        base_config["batch"] = {"fail_fast": False}
        config_file.write_text(json.dumps(base_config))
        monkeypatch.setenv("IHE_TEST_BATCH_FAIL_FAST", "true")

        # Act
        config = load_config(config_file)
        batch_config = get_batch_config(config)

        # Assert
        assert batch_config.fail_fast is True

    def test_env_override_concurrent_connections(self, tmp_path, monkeypatch, base_config):
        """Test IHE_TEST_BATCH_CONCURRENT_CONNECTIONS environment variable override."""
        # Arrange
        config_file = tmp_path / "config.json"
        base_config["batch"] = {"concurrent_connections": 10}
        config_file.write_text(json.dumps(base_config))
        monkeypatch.setenv("IHE_TEST_BATCH_CONCURRENT_CONNECTIONS", "25")

        # Act
        config = load_config(config_file)
        batch_config = get_batch_config(config)

        # Assert
        assert batch_config.concurrent_connections == 25

    def test_env_override_output_dir(self, tmp_path, monkeypatch, base_config):
        """Test IHE_TEST_BATCH_OUTPUT_DIR environment variable override."""
        # Arrange
        config_file = tmp_path / "config.json"
        base_config["batch"] = {"output_dir": "output/default"}
        config_file.write_text(json.dumps(base_config))
        monkeypatch.setenv("IHE_TEST_BATCH_OUTPUT_DIR", "output/env-override")

        # Act
        config = load_config(config_file)
        batch_config = get_batch_config(config)

        # Assert
        assert batch_config.output_dir == Path("output/env-override")


class TestCheckpointSerialization:
    """Tests for BatchCheckpoint JSON serialization and deserialization."""

    def test_checkpoint_to_json(self):
        """Test BatchCheckpoint serialization to JSON."""
        # Arrange
        checkpoint = BatchCheckpoint(
            batch_id="batch-123",
            csv_file_path="/path/to/patients.csv",
            last_processed_index=49,
            timestamp=datetime(2025, 11, 28, 20, 30, 0),
            completed_patient_ids=["P001", "P002", "P003"],
            failed_patient_ids=["P004"],
        )

        # Act
        json_str = checkpoint.to_json()
        data = json.loads(json_str)

        # Assert
        assert data["batch_id"] == "batch-123"
        assert data["csv_file_path"] == "/path/to/patients.csv"
        assert data["last_processed_index"] == 49
        assert data["completed_patient_ids"] == ["P001", "P002", "P003"]
        assert data["failed_patient_ids"] == ["P004"]
        assert "timestamp" in data

    def test_checkpoint_from_json(self):
        """Test BatchCheckpoint deserialization from JSON."""
        # Arrange
        json_data = {
            "batch_id": "batch-456",
            "csv_file_path": "/path/to/data.csv",
            "last_processed_index": 99,
            "timestamp": "2025-11-28T21:00:00",
            "completed_patient_ids": ["P010", "P011"],
            "failed_patient_ids": [],
        }
        json_str = json.dumps(json_data)

        # Act
        checkpoint = BatchCheckpoint.from_json(json_str)

        # Assert
        assert checkpoint.batch_id == "batch-456"
        assert checkpoint.csv_file_path == "/path/to/data.csv"
        assert checkpoint.last_processed_index == 99
        assert checkpoint.completed_patient_ids == ["P010", "P011"]
        assert checkpoint.failed_patient_ids == []

    def test_checkpoint_round_trip(self):
        """Test BatchCheckpoint serialization round trip."""
        # Arrange
        original = BatchCheckpoint(
            batch_id="batch-789",
            csv_file_path="/data/patients.csv",
            last_processed_index=150,
            timestamp=datetime(2025, 11, 28, 22, 0, 0),
            completed_patient_ids=["P100", "P101", "P102"],
            failed_patient_ids=["P103", "P104"],
        )

        # Act
        json_str = original.to_json()
        restored = BatchCheckpoint.from_json(json_str)

        # Assert
        assert restored.batch_id == original.batch_id
        assert restored.csv_file_path == original.csv_file_path
        assert restored.last_processed_index == original.last_processed_index
        assert restored.completed_patient_ids == original.completed_patient_ids
        assert restored.failed_patient_ids == original.failed_patient_ids

    def test_checkpoint_to_dict(self):
        """Test BatchCheckpoint to_dict method."""
        # Arrange
        checkpoint = BatchCheckpoint(
            batch_id="batch-dict",
            csv_file_path="/test/file.csv",
            last_processed_index=25,
            timestamp=datetime(2025, 11, 28, 23, 0, 0),
            completed_patient_ids=["A", "B"],
            failed_patient_ids=["C"],
        )

        # Act
        result = checkpoint.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["batch_id"] == "batch-dict"
        assert result["last_processed_index"] == 25

    def test_checkpoint_progress_percentage(self):
        """Test BatchCheckpoint progress_percentage property."""
        # Arrange
        checkpoint = BatchCheckpoint(
            batch_id="batch-progress",
            csv_file_path="/test/file.csv",
            last_processed_index=50,
            timestamp=datetime.now(),
            completed_patient_ids=["P" + str(i) for i in range(45)],
            failed_patient_ids=["F" + str(i) for i in range(5)],
            total_patients=100,
        )

        # Act
        progress = checkpoint.progress_percentage

        # Assert
        assert progress == 50.0


class TestBatchStatisticsCalculation:
    """Tests for BatchStatistics calculation accuracy."""

    def test_batch_statistics_calculate_from_results(self):
        """Test BatchStatistics.calculate_from_results method."""
        # Arrange
        patient_results = [
            PatientWorkflowResult(
                patient_id="P001",
                pix_add_status="success",
                iti41_status="success",
                pix_add_time_ms=100,
                iti41_time_ms=200,
                total_time_ms=300,
            ),
            PatientWorkflowResult(
                patient_id="P002",
                pix_add_status="success",
                iti41_status="success",
                pix_add_time_ms=150,
                iti41_time_ms=250,
                total_time_ms=400,
            ),
            PatientWorkflowResult(
                patient_id="P003",
                pix_add_status="failed",
                iti41_status="skipped",
                pix_add_time_ms=120,
                iti41_time_ms=0,
                total_time_ms=120,
                error_message="Connection timeout",
            ),
        ]

        # Total time is 60 seconds = 60000 ms
        total_time_ms = 60000

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert
        assert stats is not None
        # Error rate: 1 out of 3 failed (P003 is not fully successful)
        assert stats.error_rate == pytest.approx(1 / 3, rel=0.01)
        assert stats.avg_latency_ms > 0
        assert stats.pix_add_avg_latency_ms > 0

    def test_batch_statistics_throughput_calculation(self):
        """Test throughput calculation in BatchStatistics."""
        # Arrange
        patient_results = [
            PatientWorkflowResult(
                patient_id=f"P{i:03d}",
                pix_add_status="success",
                iti41_status="success",
                pix_add_time_ms=100,
                iti41_time_ms=200,
                total_time_ms=300,
            )
            for i in range(60)
        ]

        # 1 minute = 60000 ms
        total_time_ms = 60000

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert - 60 patients in 1 minute = 60 patients/minute
        assert stats.throughput_patients_per_minute == pytest.approx(60.0, rel=0.1)

    def test_batch_statistics_empty_results(self):
        """Test BatchStatistics with empty results."""
        # Arrange
        patient_results = []
        total_time_ms = 30000  # 30 seconds

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert
        assert stats.error_rate == 0.0
        assert stats.avg_latency_ms == 0.0
        assert stats.throughput_patients_per_minute == 0.0


class TestOutputDirectoryCreation:
    """Tests for OutputManager directory organization."""

    def test_output_manager_setup_directories(self, tmp_path):
        """Test OutputManager creates correct directory structure."""
        # Arrange
        base_dir = tmp_path / "output"
        manager = OutputManager(base_dir)

        # Act
        paths = manager.setup_directories()

        # Assert
        assert isinstance(paths, OutputPaths)
        assert paths.logs_dir.exists()
        assert paths.documents_dir.exists()
        assert paths.ccds_dir.exists()
        assert paths.results_dir.exists()
        assert paths.audit_dir.exists()

    def test_output_manager_directory_structure(self, tmp_path):
        """Test correct directory structure is created."""
        # Arrange
        base_dir = tmp_path / "test_output"
        manager = OutputManager(base_dir)

        # Act
        paths = manager.setup_directories()

        # Assert
        assert paths.logs_dir == base_dir / "logs"
        assert paths.documents_dir == base_dir / "documents"
        assert paths.ccds_dir == base_dir / "documents" / "ccds"
        assert paths.results_dir == base_dir / "results"
        assert paths.audit_dir == base_dir / "audit"

    def test_output_manager_write_result_file(self, tmp_path):
        """Test OutputManager.write_result_file method."""
        # Arrange
        base_dir = tmp_path / "output"
        manager = OutputManager(base_dir)
        manager.setup_directories()

        result_data = {
            "batch_id": "write-test",
            "csv_file": "/test/patients.csv",
            "status": "success",
        }

        # Act
        result_path = manager.write_result_file(result_data, "write-test-results.json")

        # Assert
        assert result_path.exists()
        assert "write-test" in result_path.name

    def test_output_manager_write_checkpoint_file(self, tmp_path):
        """Test OutputManager.write_checkpoint_file method."""
        # Arrange
        base_dir = tmp_path / "output"
        manager = OutputManager(base_dir)
        manager.setup_directories()

        checkpoint_data = {
            "batch_id": "checkpoint-write-test",
            "csv_file_path": "/test/patients.csv",
            "last_processed_index": 50,
            "completed_patient_ids": ["P001", "P002"],
            "failed_patient_ids": [],
        }

        # Act
        checkpoint_path = manager.write_checkpoint_file(checkpoint_data, "checkpoint-write-test")

        # Assert
        assert checkpoint_path.exists()
        assert "checkpoint" in checkpoint_path.name

    def test_output_manager_idempotent_setup(self, tmp_path):
        """Test that setup_directories is idempotent."""
        # Arrange
        base_dir = tmp_path / "output"
        manager = OutputManager(base_dir)

        # Act - call setup twice
        paths1 = manager.setup_directories()
        paths2 = manager.setup_directories()

        # Assert - should not raise and paths should be same
        assert paths1.logs_dir == paths2.logs_dir
        assert paths1.results_dir == paths2.results_dir


class TestConnectionPoolConfiguration:
    """Tests for ConnectionPool configuration and settings."""

    def test_connection_pool_config_defaults(self):
        """Test ConnectionPoolConfig has correct default values."""
        # Arrange & Act
        config = ConnectionPoolConfig()

        # Assert
        assert config.max_connections == 10
        assert config.pool_block is True
        assert config.retry_count == 3
        assert config.backoff_factor == 0.3
        assert config.timeout == 30

    def test_connection_pool_config_custom_values(self):
        """Test ConnectionPoolConfig with custom values."""
        # Arrange & Act
        config = ConnectionPoolConfig(
            max_connections=25,
            pool_block=False,
            retry_count=5,
        )

        # Assert
        assert config.max_connections == 25
        assert config.pool_block is False
        assert config.retry_count == 5

    def test_connection_pool_creation(self):
        """Test ConnectionPool creation with config."""
        # Arrange
        config = ConnectionPoolConfig(max_connections=20)

        # Act
        pool = ConnectionPool(config)

        # Assert
        assert pool is not None
        assert pool.config.max_connections == 20

    def test_connection_pool_get_session(self):
        """Test ConnectionPool.get_session returns a session."""
        # Arrange
        config = ConnectionPoolConfig(max_connections=10)
        pool = ConnectionPool(config)

        # Act
        session = pool.get_session()

        # Assert
        assert session is not None
        # Session should have adapters mounted
        assert "http://" in session.adapters or "https://" in session.adapters

    def test_create_session_with_pool(self):
        """Test create_session_with_pool helper function."""
        # Arrange & Act
        session = create_session_with_pool(max_connections=15)

        # Assert
        assert session is not None

    def test_get_default_pool(self):
        """Test get_default_pool returns singleton pool."""
        # Arrange
        reset_default_pool()  # Ensure clean state

        # Act
        pool1 = get_default_pool()
        pool2 = get_default_pool()

        # Assert
        assert pool1 is pool2  # Same instance

    def test_reset_default_pool(self):
        """Test reset_default_pool clears the singleton."""
        # Arrange
        pool1 = get_default_pool()

        # Act
        reset_default_pool()
        pool2 = get_default_pool()

        # Assert
        assert pool1 is not pool2  # New instance after reset


class TestPerOperationLogging:
    """Tests for per-operation logging configuration."""

    @pytest.fixture
    def base_config(self):
        """Return base config with required fields."""
        return {
            "endpoints": {
                "pix_add_url": "http://localhost:8080/pix/add",
                "iti41_url": "http://localhost:8080/iti41/submit"
            }
        }

    def test_get_operation_logger(self):
        """Test get_operation_logger returns named logger."""
        # Arrange & Act
        csv_logger = get_operation_logger("csv")
        pix_logger = get_operation_logger("pix_add")
        iti41_logger = get_operation_logger("iti41")
        saml_logger = get_operation_logger("saml")

        # Assert
        assert csv_logger is not None
        assert pix_logger is not None
        assert iti41_logger is not None
        assert saml_logger is not None
        assert csv_logger.name == "ihe_test_util.csv"
        assert pix_logger.name == "ihe_test_util.pix_add"

    def test_set_operation_log_level(self):
        """Test set_operation_log_level changes logger level."""
        # Arrange
        import logging

        logger = get_operation_logger("csv")

        # Act
        set_operation_log_level("csv", "DEBUG")

        # Assert
        assert logger.level == logging.DEBUG

    def test_configure_operation_logging(self):
        """Test configure_operation_logging sets multiple levels."""
        # Arrange
        import logging

        # Act - configure_operation_logging takes individual string parameters
        configure_operation_logging(
            csv_log_level="DEBUG",
            pix_add_log_level="WARNING",
            iti41_log_level="ERROR",
            saml_log_level="INFO",
        )

        # Assert
        assert get_operation_logger("csv").level == logging.DEBUG
        assert get_operation_logger("pix_add").level == logging.WARNING
        assert get_operation_logger("iti41").level == logging.ERROR
        assert get_operation_logger("saml").level == logging.INFO

    def test_configure_operation_logging_from_config(self, tmp_path, base_config):
        """Test configure_operation_logging_from_config with OperationLoggingConfig."""
        # Arrange
        import logging

        config_file = tmp_path / "config.json"
        base_config["operation_logging"] = {
            "csv_log_level": "DEBUG",
            "pix_add_log_level": "INFO",
            "iti41_log_level": "WARNING",
            "saml_log_level": "ERROR",
        }
        config_file.write_text(json.dumps(base_config))

        config = load_config(config_file)
        # Get the operation_logging config from the full Config
        op_logging_config = get_operation_logging_config(config)

        # Act - pass OperationLoggingConfig, not full Config
        configure_operation_logging_from_config(op_logging_config)

        # Assert
        assert get_operation_logger("csv").level == logging.DEBUG
        assert get_operation_logger("pix_add").level == logging.INFO


class TestConfigHelperFunctions:
    """Tests for configuration helper functions."""

    @pytest.fixture
    def base_config(self):
        """Return base config with required fields."""
        return {
            "endpoints": {
                "pix_add_url": "http://localhost:8080/pix/add",
                "iti41_url": "http://localhost:8080/iti41/submit"
            }
        }

    def test_get_batch_config_returns_batch_config(self, tmp_path, base_config):
        """Test get_batch_config returns BatchConfig object."""
        # Arrange
        config_file = tmp_path / "config.json"
        base_config["batch"] = {
            "batch_size": 200,
            "checkpoint_interval": 25,
        }
        config_file.write_text(json.dumps(base_config))

        config = load_config(config_file)

        # Act
        batch_config = get_batch_config(config)

        # Assert
        assert isinstance(batch_config, BatchConfig)
        assert batch_config.batch_size == 200
        assert batch_config.checkpoint_interval == 25

    def test_get_template_config_returns_template_config(self, tmp_path, base_config):
        """Test get_template_config returns TemplateConfig object."""
        # Arrange
        config_file = tmp_path / "config.json"
        base_config["templates"] = {
            "ccd_template_path": "templates/ccd.xml",
            "saml_template_path": "templates/saml.xml",
        }
        config_file.write_text(json.dumps(base_config))

        config = load_config(config_file)

        # Act
        template_config = get_template_config(config)

        # Assert
        assert isinstance(template_config, TemplateConfig)
        assert template_config.ccd_template_path == Path("templates/ccd.xml")

    def test_get_operation_logging_config_returns_config(self, tmp_path, base_config):
        """Test get_operation_logging_config returns OperationLoggingConfig."""
        # Arrange
        config_file = tmp_path / "config.json"
        base_config["operation_logging"] = {
            "csv_log_level": "DEBUG",
            "pix_add_log_level": "INFO",
        }
        config_file.write_text(json.dumps(base_config))

        config = load_config(config_file)

        # Act
        op_logging_config = get_operation_logging_config(config)

        # Assert
        assert isinstance(op_logging_config, OperationLoggingConfig)
        assert op_logging_config.csv_log_level == "DEBUG"
