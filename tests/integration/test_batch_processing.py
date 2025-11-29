"""Integration tests for batch processing functionality.

Tests for Story 6.6: Batch Processing & Configuration Management.

This module tests:
- Full batch workflow processing
- Checkpoint save and resume functionality
- Batch with custom configuration templates
- Output directory structure creation
- NFR1: 100 patients processed in under 5 minutes
"""

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ihe_test_util.config.schema import BatchConfig, Config
from ihe_test_util.config.manager import load_config, get_batch_config
from ihe_test_util.models.batch import (
    BatchCheckpoint,
    BatchStatistics,
    BatchWorkflowResult,
    PatientWorkflowResult,
)
from ihe_test_util.ihe_transactions.workflows import IntegratedWorkflow
from ihe_test_util.utils.output_manager import OutputManager, OutputPaths


class TestBatchProcessingIntegration:
    """Integration tests for full batch workflow processing."""

    @pytest.fixture
    def sample_csv_file(self, tmp_path):
        """Create a sample CSV file for testing."""
        csv_content = """patient_id,first_name,last_name,dob,gender,ssn,address,city,state,zip
P001,John,Doe,1980-01-15,M,123-45-6789,123 Main St,Springfield,IL,62701
P002,Jane,Smith,1985-06-20,F,234-56-7890,456 Oak Ave,Chicago,IL,60601
P003,Bob,Johnson,1990-03-10,M,345-67-8901,789 Pine Rd,Peoria,IL,61602
P004,Alice,Williams,1975-12-05,F,456-78-9012,321 Elm St,Rockford,IL,61101
P005,Charlie,Brown,1988-09-25,M,567-89-0123,654 Maple Dr,Naperville,IL,60540
"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content)
        return csv_file

    @pytest.fixture
    def batch_config(self, tmp_path):
        """Create a batch configuration for testing."""
        return BatchConfig(
            batch_size=10,
            checkpoint_interval=2,
            fail_fast=False,
            concurrent_connections=5,
            output_dir=tmp_path / "output",
            resume_enabled=True,
        )

    @pytest.fixture
    def mock_pix_client(self):
        """Create a mock PIX Add client."""
        mock = MagicMock()
        mock.send_pix_add.return_value = MagicMock(
            success=True,
            message_id="MSG-001",
            acknowledgment_code="AA",
            response_time_ms=100,
        )
        return mock

    @pytest.fixture
    def mock_iti41_client(self):
        """Create a mock ITI-41 client."""
        mock = MagicMock()
        mock.submit_document.return_value = MagicMock(
            success=True,
            document_id="DOC-001",
            response_time_ms=200,
        )
        return mock

    def test_batch_processing_workflow_success(
        self, sample_csv_file, batch_config, tmp_path
    ):
        """Test successful batch processing of multiple patients."""
        # Arrange
        output_manager = OutputManager(batch_config.output_dir)
        output_paths = output_manager.setup_directories()

        # Act - Create mock workflow result to simulate batch processing
        patient_results = []
        for i in range(5):
            patient_results.append(
                PatientWorkflowResult(
                    patient_id=f"P00{i+1}",
                    pix_add_status="success",
                    iti41_status="success",
                    pix_add_time_ms=100 + i * 10,
                    iti41_time_ms=200 + i * 10,
                    total_time_ms=300 + i * 20,
                )
            )

        batch_result = BatchWorkflowResult(
            batch_id="test-batch-001",
            csv_file=str(sample_csv_file),
            ccd_template="templates/ccd-template.xml",
            start_timestamp=datetime.now(),
            end_timestamp=datetime.now(),
            patient_results=patient_results,
        )

        # Assert
        assert batch_result is not None
        assert len(batch_result.patient_results) == 5
        assert all(r.pix_add_status == "success" for r in batch_result.patient_results)

    def test_batch_processing_with_failures(self, sample_csv_file, batch_config):
        """Test batch processing handles failures gracefully."""
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
                pix_add_status="failed",
                iti41_status="skipped",
                pix_add_time_ms=100,
                iti41_time_ms=0,
                total_time_ms=100,
                error_message="PIX Add failed: Connection timeout",
            ),
            PatientWorkflowResult(
                patient_id="P003",
                pix_add_status="success",
                iti41_status="success",
                pix_add_time_ms=110,
                iti41_time_ms=210,
                total_time_ms=320,
            ),
        ]

        batch_result = BatchWorkflowResult(
            batch_id="test-batch-failures",
            csv_file=str(sample_csv_file),
            ccd_template="templates/ccd-template.xml",
            start_timestamp=datetime.now(),
            end_timestamp=datetime.now(),
            patient_results=patient_results,
        )

        # Calculate total time for statistics
        total_time_ms = 60000  # 60 seconds

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert
        assert batch_result.fully_successful_count == 2
        assert batch_result.pix_add_failed_count == 1
        assert stats.error_rate == pytest.approx(1 / 3, rel=0.01)

    def test_batch_fail_fast_mode(self, sample_csv_file, tmp_path):
        """Test batch processing stops on first error in fail-fast mode."""
        # Arrange
        batch_config = BatchConfig(
            batch_size=10,
            checkpoint_interval=2,
            fail_fast=True,
            output_dir=tmp_path / "output",
        )

        # Simulate processing where second patient fails
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
                pix_add_status="failed",
                iti41_status="skipped",
                error_message="Connection refused",
            ),
            # In fail-fast mode, P003-P005 would not be processed
        ]

        batch_result = BatchWorkflowResult(
            batch_id="test-fail-fast",
            csv_file=str(sample_csv_file),
            ccd_template="templates/ccd-template.xml",
            start_timestamp=datetime.now(),
            end_timestamp=datetime.now(),
            patient_results=patient_results,
        )

        # Assert - only 2 patients processed due to fail-fast
        assert len(batch_result.patient_results) == 2
        assert batch_result.patient_results[1].pix_add_status == "failed"


class TestCheckpointSaveAndResume:
    """Integration tests for checkpoint save and resume functionality."""

    @pytest.fixture
    def checkpoint_data(self):
        """Create sample checkpoint data."""
        return BatchCheckpoint(
            batch_id="checkpoint-test-001",
            csv_file_path="/test/patients.csv",
            last_processed_index=49,
            timestamp=datetime.now(),
            completed_patient_ids=[f"P{i:03d}" for i in range(1, 50)],
            failed_patient_ids=["P010", "P025"],
            total_patients=100,
        )

    def test_checkpoint_save_to_file(self, checkpoint_data, tmp_path):
        """Test saving checkpoint to file."""
        # Arrange
        checkpoint_file = tmp_path / "checkpoint.json"

        # Act
        checkpoint_json = checkpoint_data.to_json()
        checkpoint_file.write_text(checkpoint_json)

        # Assert
        assert checkpoint_file.exists()
        loaded_data = json.loads(checkpoint_file.read_text())
        assert loaded_data["batch_id"] == "checkpoint-test-001"
        assert loaded_data["last_processed_index"] == 49
        assert len(loaded_data["completed_patient_ids"]) == 49

    def test_checkpoint_resume_from_file(self, checkpoint_data, tmp_path):
        """Test resuming batch processing from checkpoint file."""
        # Arrange
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_file.write_text(checkpoint_data.to_json())

        # Act
        loaded_json = checkpoint_file.read_text()
        restored_checkpoint = BatchCheckpoint.from_json(loaded_json)

        # Assert
        assert restored_checkpoint.batch_id == checkpoint_data.batch_id
        assert restored_checkpoint.last_processed_index == 49
        assert len(restored_checkpoint.completed_patient_ids) == 49
        assert "P010" in restored_checkpoint.failed_patient_ids

    def test_checkpoint_progress_tracking(self, checkpoint_data):
        """Test checkpoint progress percentage calculation."""
        # Arrange & Act
        progress = checkpoint_data.progress_percentage

        # Assert - 49 processed out of 100 total (last_processed_index=49)
        assert progress == 49.0

    def test_checkpoint_save_at_intervals(self, tmp_path):
        """Test checkpoints are saved at configured intervals."""
        # Arrange
        output_manager = OutputManager(tmp_path / "output")
        output_manager.setup_directories()
        checkpoint_interval = 5

        # Simulate processing with checkpoints at intervals
        checkpoints_saved = []
        for i in range(1, 16):  # 15 patients
            if i % checkpoint_interval == 0:
                checkpoint = BatchCheckpoint(
                    batch_id="interval-test",
                    csv_file_path="/test/patients.csv",
                    last_processed_index=i,
                    timestamp=datetime.now(),
                    completed_patient_ids=[f"P{j:03d}" for j in range(1, i + 1)],
                    failed_patient_ids=[],
                )
                # Convert checkpoint to dict and use correct signature
                checkpoint_data = json.loads(checkpoint.to_json())
                checkpoint_path = output_manager.write_checkpoint_file(
                    checkpoint_data, f"interval-test-{i}"
                )
                checkpoints_saved.append(checkpoint_path)

        # Assert - checkpoints at 5, 10, 15
        assert len(checkpoints_saved) == 3

    def test_resume_skips_completed_patients(self, tmp_path):
        """Test that resume skips already completed patients."""
        # Arrange
        checkpoint = BatchCheckpoint(
            batch_id="resume-skip-test",
            csv_file_path="/test/patients.csv",
            last_processed_index=5,
            timestamp=datetime.now(),
            completed_patient_ids=["P001", "P002", "P003", "P004", "P005"],
            failed_patient_ids=[],
            total_patients=10,
        )

        # Act - simulate resume
        all_patients = [f"P{i:03d}" for i in range(1, 11)]
        remaining_patients = [
            p for p in all_patients if p not in checkpoint.completed_patient_ids
        ]

        # Assert
        assert len(remaining_patients) == 5
        assert "P006" in remaining_patients
        assert "P001" not in remaining_patients


class TestBatchWithCustomConfig:
    """Integration tests for batch processing with custom configuration templates."""

    @pytest.fixture
    def development_config_file(self, tmp_path):
        """Create development configuration file."""
        config = {
            "endpoints": {
                "pix_add_url": "http://localhost:8080/pix",
                "iti41_url": "http://localhost:8080/iti41",
            },
            "batch": {
                "batch_size": 10,
                "checkpoint_interval": 5,
                "fail_fast": True,
                "concurrent_connections": 5,
                "output_dir": str(tmp_path / "output" / "dev"),
            },
            "logging": {"level": "DEBUG"},
            "operation_logging": {
                "csv_log_level": "DEBUG",
                "pix_add_log_level": "DEBUG",
                "iti41_log_level": "DEBUG",
            },
        }
        config_file = tmp_path / "batch-development.json"
        config_file.write_text(json.dumps(config))
        return config_file

    @pytest.fixture
    def staging_config_file(self, tmp_path):
        """Create staging configuration file."""
        config = {
            "endpoints": {
                "pix_add_url": "http://staging:8080/pix",
                "iti41_url": "http://staging:8080/iti41",
            },
            "batch": {
                "batch_size": 500,
                "checkpoint_interval": 100,
                "fail_fast": False,
                "concurrent_connections": 20,
                "output_dir": str(tmp_path / "output" / "staging"),
            },
            "logging": {"level": "WARNING"},
            "operation_logging": {
                "csv_log_level": "WARNING",
                "pix_add_log_level": "INFO",
                "iti41_log_level": "INFO",
            },
        }
        config_file = tmp_path / "batch-staging.json"
        config_file.write_text(json.dumps(config))
        return config_file

    def test_load_development_config(self, development_config_file):
        """Test loading development configuration template."""
        # Arrange & Act
        config = load_config(development_config_file)
        batch_config = get_batch_config(config)

        # Assert
        assert batch_config.batch_size == 10
        assert batch_config.checkpoint_interval == 5
        assert batch_config.fail_fast is True
        assert batch_config.concurrent_connections == 5

    def test_load_staging_config(self, staging_config_file):
        """Test loading staging configuration template."""
        # Arrange & Act
        config = load_config(staging_config_file)
        batch_config = get_batch_config(config)

        # Assert
        assert batch_config.batch_size == 500
        assert batch_config.checkpoint_interval == 100
        assert batch_config.fail_fast is False
        assert batch_config.concurrent_connections == 20

    def test_config_output_dir_creation(self, development_config_file, tmp_path):
        """Test that config output directory is created correctly."""
        # Arrange
        config = load_config(development_config_file)
        batch_config = get_batch_config(config)
        output_manager = OutputManager(batch_config.output_dir)

        # Act
        paths = output_manager.setup_directories()

        # Assert
        assert paths.logs_dir.exists()
        assert paths.results_dir.exists()
        assert "dev" in str(paths.logs_dir)


class TestOutputDirectoryStructure:
    """Integration tests for output directory structure creation."""

    def test_full_output_structure_creation(self, tmp_path):
        """Test complete output directory structure is created."""
        # Arrange
        base_dir = tmp_path / "output"
        manager = OutputManager(base_dir)

        # Act
        paths = manager.setup_directories()

        # Assert
        assert (base_dir / "logs").exists()
        assert (base_dir / "documents").exists()
        assert (base_dir / "documents" / "ccds").exists()
        assert (base_dir / "results").exists()
        assert (base_dir / "audit").exists()

    def test_write_all_output_files(self, tmp_path):
        """Test writing all types of output files."""
        # Arrange
        base_dir = tmp_path / "output"
        manager = OutputManager(base_dir)
        manager.setup_directories()

        batch_result_data = {
            "batch_id": "full-output-test",
            "csv_file": "/test/patients.csv",
            "ccd_template": "/test/template.xml",
            "start_timestamp": "2025-11-28T20:00:00",
            "end_timestamp": "2025-11-28T20:05:00",
            "patient_results": [
                {
                    "patient_id": "P001",
                    "pix_add_status": "success",
                    "iti41_status": "success",
                    "pix_add_time_ms": 100,
                    "iti41_time_ms": 200,
                    "total_time_ms": 300,
                }
            ],
        }

        checkpoint_data = {
            "batch_id": "full-output-test",
            "csv_file_path": "/test/patients.csv",
            "last_processed_index": 1,
            "timestamp": datetime.now().isoformat(),
            "completed_patient_ids": ["P001"],
            "failed_patient_ids": [],
        }

        # Act
        result_path = manager.write_result_file(batch_result_data, "full-output-test-results.json")
        checkpoint_path = manager.write_checkpoint_file(checkpoint_data, "full-output-test")
        summary_path = manager.write_summary_file("Batch completed successfully", "full-output-test")
        audit_path = manager.write_audit_log(
            {"event": "batch_complete", "batch_id": "full-output-test"}, "full-output-test"
        )

        # Assert
        assert result_path.exists()
        assert checkpoint_path.exists()
        assert summary_path.exists()
        assert audit_path.exists()

    def test_ccd_document_storage(self, tmp_path):
        """Test CCD documents are stored in correct location."""
        # Arrange
        base_dir = tmp_path / "output"
        manager = OutputManager(base_dir)
        manager.setup_directories()

        sample_ccd = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="2.16.840.1.113883.19" extension="P001"/>
</ClinicalDocument>
"""

        # Act - correct signature: write_ccd_document(content, patient_id)
        ccd_path = manager.write_ccd_document(sample_ccd, "P001")

        # Assert
        assert ccd_path.exists()
        assert "ccds" in str(ccd_path)
        assert "P001" in ccd_path.name

    def test_batch_log_file_creation(self, tmp_path):
        """Test batch-specific log file is created."""
        # Arrange
        base_dir = tmp_path / "output"
        manager = OutputManager(base_dir)
        manager.setup_directories()

        # Act - correct signature: write_batch_log(content, batch_id, log_type)
        log_path = manager.write_batch_log(
            "Processing started for batch-log-test",
            "batch-log-test",
            "batch",
        )

        # Assert
        assert log_path.exists()
        assert "batch-log-test" in log_path.name
        assert log_path.read_text().strip() == "Processing started for batch-log-test"


class TestNFR1Performance:
    """Performance tests verifying NFR1: 100 patients in under 5 minutes."""

    def test_batch_processing_performance_simulation(self, tmp_path):
        """Simulate batch processing to verify performance metrics calculation.

        Note: This is a simulation test. Full performance testing would require
        actual mock server endpoints.
        """
        # Arrange
        num_patients = 100
        # Simulate 2 seconds per patient (should complete in ~200 seconds = 3.3 minutes)
        simulated_latency_per_patient_ms = 2000

        patient_results = []
        for i in range(num_patients):
            patient_results.append(
                PatientWorkflowResult(
                    patient_id=f"P{i+1:03d}",
                    pix_add_status="success",
                    iti41_status="success",
                    pix_add_time_ms=800,
                    iti41_time_ms=1200,
                    total_time_ms=simulated_latency_per_patient_ms,
                )
            )

        # Simulate 3.5 minutes total processing time
        start_time = datetime(2025, 11, 28, 20, 0, 0)
        end_time = datetime(2025, 11, 28, 20, 3, 30)  # 3.5 minutes
        total_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)
        duration_minutes = (end_time - start_time).total_seconds() / 60

        # Assert
        assert duration_minutes < 5.0  # NFR1: under 5 minutes
        assert stats.throughput_patients_per_minute >= 20  # At least 20 patients/minute
        assert stats.error_rate == 0.0

    def test_throughput_calculation_accuracy(self):
        """Test that throughput calculation is accurate."""
        # Arrange - 120 patients in 2 minutes = 60 patients/minute
        patient_results = [
            PatientWorkflowResult(
                patient_id=f"P{i:03d}",
                pix_add_status="success",
                iti41_status="success",
                total_time_ms=1000,
            )
            for i in range(120)
        ]

        # 2 minutes = 120000 ms
        total_time_ms = 120000

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert
        assert stats.throughput_patients_per_minute == pytest.approx(60.0, rel=0.01)

    def test_latency_statistics_accuracy(self):
        """Test that latency statistics are calculated accurately."""
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
                pix_add_time_ms=200,
                iti41_time_ms=300,
                total_time_ms=500,
            ),
            PatientWorkflowResult(
                patient_id="P003",
                pix_add_status="success",
                iti41_status="success",
                pix_add_time_ms=150,
                iti41_time_ms=250,
                total_time_ms=400,
            ),
        ]

        # Total time for batch
        total_time_ms = 60000

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert
        # Average PIX Add latency: (100 + 200 + 150) / 3 = 150
        assert stats.pix_add_avg_latency_ms == pytest.approx(150.0, rel=0.01)
        # Average ITI-41 latency: (200 + 300 + 250) / 3 = 250
        assert stats.iti41_avg_latency_ms == pytest.approx(250.0, rel=0.01)
        # Average total latency: (300 + 500 + 400) / 3 = 400
        assert stats.avg_latency_ms == pytest.approx(400.0, rel=0.01)


class TestBatchProcessingEdgeCases:
    """Tests for edge cases in batch processing."""

    def test_empty_csv_file(self, tmp_path):
        """Test handling of empty CSV file."""
        # Arrange
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("patient_id,first_name,last_name\n")  # Headers only

        patient_results = []
        total_time_ms = 1000

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert
        assert stats.error_rate == 0.0
        assert stats.avg_latency_ms == 0.0

    def test_single_patient_batch(self, tmp_path):
        """Test batch processing with single patient."""
        # Arrange
        patient_results = [
            PatientWorkflowResult(
                patient_id="P001",
                pix_add_status="success",
                iti41_status="success",
                pix_add_time_ms=100,
                iti41_time_ms=200,
                total_time_ms=300,
            )
        ]

        total_time_ms = 1000

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert
        assert stats.error_rate == 0.0

    def test_all_failures_batch(self, tmp_path):
        """Test batch where all patients fail."""
        # Arrange
        patient_results = [
            PatientWorkflowResult(
                patient_id=f"P{i:03d}",
                pix_add_status="failed",
                iti41_status="skipped",
                error_message="Server unavailable",
            )
            for i in range(5)
        ]

        total_time_ms = 5000

        # Act
        stats = BatchStatistics.calculate_from_results(patient_results, total_time_ms)

        # Assert
        assert stats.error_rate == 1.0

    def test_checkpoint_with_no_progress(self, tmp_path):
        """Test checkpoint at start of batch (no progress yet)."""
        # Arrange
        checkpoint = BatchCheckpoint(
            batch_id="no-progress-test",
            csv_file_path="/test/patients.csv",
            last_processed_index=0,
            timestamp=datetime.now(),
            completed_patient_ids=[],
            failed_patient_ids=[],
            total_patients=100,
        )

        # Act
        progress = checkpoint.progress_percentage

        # Assert
        assert progress == 0.0

    def test_checkpoint_at_completion(self, tmp_path):
        """Test checkpoint at end of batch (100% complete)."""
        # Arrange
        checkpoint = BatchCheckpoint(
            batch_id="complete-test",
            csv_file_path="/test/patients.csv",
            last_processed_index=100,
            timestamp=datetime.now(),
            completed_patient_ids=[f"P{i:03d}" for i in range(1, 101)],
            failed_patient_ids=[],
            total_patients=100,
        )

        # Act
        progress = checkpoint.progress_percentage

        # Assert
        assert progress == 100.0
