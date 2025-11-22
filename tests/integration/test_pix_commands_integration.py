"""Integration tests for PIX Add CLI commands.

These tests run the complete PIX Add CLI workflow with mock endpoints
to verify end-to-end functionality.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from ihe_test_util.cli.pix_commands import register
from ihe_test_util.models.batch import BatchProcessingResult, PatientResult
from ihe_test_util.models.responses import TransactionStatus


@pytest.fixture
def sample_csv_file(tmp_path):
    """Create sample CSV file for testing."""
    csv_file = tmp_path / "test_patients.csv"
    csv_file.write_text(
        "first_name,last_name,dob,gender,patient_id,patient_id_oid,mrn\n"
        "John,Doe,1980-01-01,M,PAT001,1.2.3.4,MRN001\n"
        "Jane,Smith,1990-02-02,F,PAT002,1.2.3.4,MRN002\n"
        "Bob,Johnson,1975-05-15,M,PAT003,1.2.3.4,MRN003\n"
    )
    return csv_file


@pytest.fixture
def config_file(tmp_path):
    """Create test configuration file."""
    config_path = tmp_path / "config.json"
    config_data = {
        "endpoints": {
            "pix_add_url": "https://localhost:8081/pix/add",
            "iti41_url": "https://localhost:8081/iti41/submit"
        },
        "certificates": {
            "cert_path": "tests/fixtures/test_cert.pem",
            "key_path": "tests/fixtures/test_key.pem",
            "cert_format": "pem"
        },
        "transport": {
            "verify_tls": False,
            "timeout_connect": 10,
            "timeout_read": 30,
            "max_retries": 3
        },
        "logging": {
            "level": "INFO",
            "log_file": "logs/test.log",
            "redact_pii": False
        },
        "sender_oid": "1.2.3.4.5",
        "receiver_oid": "1.2.3.4.6",
        "sender_application": "TestApp",
        "receiver_application": "PIXManager"
    }
    config_path.write_text(json.dumps(config_data, indent=2))
    return config_path


class TestPIXAddRegisterCompleteWorkflow:
    """Test complete PIX Add registration workflow."""
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_complete_workflow(
        self,
        mock_parse_csv,
        mock_workflow_class,
        sample_csv_file,
        config_file,
        tmp_path
    ):
        """Test complete registration workflow with mock endpoint."""
        # Arrange
        runner = CliRunner()
        
        # Mock parse_csv
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John", "Jane", "Bob"],
            "last_name": ["Doe", "Smith", "Johnson"],
            "dob": ["1980-01-01", "1990-02-02", "1975-05-15"],
            "gender": ["M", "F", "M"],
            "patient_id": ["PAT001", "PAT002", "PAT003"],
            "patient_id_oid": ["1.2.3.4", "1.2.3.4", "1.2.3.4"],
            "mrn": ["MRN001", "MRN002", "MRN003"]
        })
        mock_parse_csv.return_value = (df, None)
        
        # Create successful batch result
        patient1 = PatientResult(
            patient_id="PAT001",
            pix_add_status=TransactionStatus.SUCCESS,
            pix_add_message="Patient registered successfully",
            processing_time_ms=100,
            enterprise_id="ENT001^^^1.2.3.4.5&ISO",
            enterprise_id_oid="1.2.3.4.5",
            registration_timestamp=datetime.now(timezone.utc)
        )
        
        patient2 = PatientResult(
            patient_id="PAT002",
            pix_add_status=TransactionStatus.SUCCESS,
            pix_add_message="Patient registered successfully",
            processing_time_ms=150,
            enterprise_id="ENT002^^^1.2.3.4.5&ISO",
            enterprise_id_oid="1.2.3.4.5",
            registration_timestamp=datetime.now(timezone.utc)
        )
        
        patient3 = PatientResult(
            patient_id="PAT003",
            pix_add_status=TransactionStatus.SUCCESS,
            pix_add_message="Patient registered successfully",
            processing_time_ms=120,
            enterprise_id="ENT003^^^1.2.3.4.5&ISO",
            enterprise_id_oid="1.2.3.4.5",
            registration_timestamp=datetime.now(timezone.utc)
        )
        
        result = BatchProcessingResult(
            batch_id="batch-integration-test",
            csv_file_path=str(sample_csv_file),
            start_timestamp=datetime.now(timezone.utc),
            total_patients=3
        )
        result.patient_results = [patient1, patient2, patient3]
        result.successful_patients = 3
        result.failed_patients = 0
        result.pix_add_success_count = 3
        result.end_timestamp = datetime.now(timezone.utc)
        
        # Mock workflow
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = result
        mock_workflow_class.return_value = mock_workflow
        
        output_file = tmp_path / "results.json"
        
        # Act
        result = runner.invoke(
            register,
            [
                str(sample_csv_file),
                "--config", str(config_file),
                "--output", str(output_file)
            ],
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        assert "PIX ADD PATIENT REGISTRATION" in result.output
        assert "Total Patients: 3" in result.output
        assert "✓ Success" in result.output
        assert "REGISTRATION SUMMARY" in result.output
        
        # Verify output file created
        assert output_file.exists()
        
        # Verify JSON structure
        with output_file.open() as f:
            data = json.load(f)
        
        assert data["summary"]["total_patients"] == 3
        assert data["summary"]["successful"] == 3
        assert data["summary"]["failed"] == 0
        assert len(data["patients"]) == 3
        
        # Verify all patients have PIX IDs
        for patient in data["patients"]:
            assert patient["status"] == "success"
            assert patient["pix_id"] is not None
            assert "ENT" in patient["pix_id"]


class TestPIXAddRegisterWithErrors:
    """Test PIX Add registration with error conditions."""
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_with_errors(
        self,
        mock_parse_csv,
        mock_workflow_class,
        sample_csv_file,
        config_file,
        tmp_path
    ):
        """Test registration with mixed success and failure."""
        # Arrange
        runner = CliRunner()
        
        # Mock parse_csv
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John", "Jane", "Bob"],
            "last_name": ["Doe", "Smith", "Johnson"],
            "dob": ["1980-01-01", "1990-02-02", "1975-05-15"],
            "gender": ["M", "F", "M"],
            "patient_id": ["PAT001", "PAT002", "PAT003"],
            "patient_id_oid": ["1.2.3.4", "1.2.3.4", "1.2.3.4"],
            "mrn": ["MRN001", "MRN002", "MRN003"]
        })
        mock_parse_csv.return_value = (df, None)
        
        # Create mixed result (some success, some failure)
        patient1 = PatientResult(
            patient_id="PAT001",
            pix_add_status=TransactionStatus.SUCCESS,
            pix_add_message="Patient registered successfully",
            processing_time_ms=100,
            enterprise_id="ENT001^^^1.2.3.4.5&ISO",
            enterprise_id_oid="1.2.3.4.5",
            registration_timestamp=datetime.now(timezone.utc)
        )
        
        patient2 = PatientResult(
            patient_id="PAT002",
            pix_add_status=TransactionStatus.ERROR,
            pix_add_message="PIX Add rejected: Duplicate patient",
            processing_time_ms=50,
            error_details="Validation error: Patient already exists"
        )
        
        patient3 = PatientResult(
            patient_id="PAT003",
            pix_add_status=TransactionStatus.SUCCESS,
            pix_add_message="Patient registered successfully",
            processing_time_ms=120,
            enterprise_id="ENT003^^^1.2.3.4.5&ISO",
            enterprise_id_oid="1.2.3.4.5",
            registration_timestamp=datetime.now(timezone.utc)
        )
        
        batch_result = BatchProcessingResult(
            batch_id="batch-with-errors",
            csv_file_path=str(sample_csv_file),
            start_timestamp=datetime.now(timezone.utc),
            total_patients=3
        )
        batch_result.patient_results = [patient1, patient2, patient3]
        batch_result.successful_patients = 2
        batch_result.failed_patients = 1
        batch_result.pix_add_success_count = 2
        batch_result.error_summary = {
            "_error_report": "Error Summary Report\nDuplicate patient errors: 1",
            "_error_statistics": {
                "total_errors": 1,
                "by_category": {"PERMANENT": 1},
                "by_type": {"ValidationError": 1},
                "error_rate": 33.3
            }
        }
        batch_result.end_timestamp = datetime.now(timezone.utc)
        
        # Mock workflow
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = batch_result
        mock_workflow_class.return_value = mock_workflow
        
        output_file = tmp_path / "results_with_errors.json"
        
        # Act
        result = runner.invoke(
            register,
            [
                str(sample_csv_file),
                "--config", str(config_file),
                "--output", str(output_file)
            ],
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 2  # Transaction errors
        assert "✓ Success" in result.output
        assert "✗ Failed" in result.output
        assert "REGISTRATION SUMMARY" in result.output
        assert "Successful:" in result.output
        assert "Failed:" in result.output
        
        # Verify output file
        assert output_file.exists()
        
        with output_file.open() as f:
            data = json.load(f)
        
        assert data["summary"]["successful"] == 2
        assert data["summary"]["failed"] == 1
        
        # Verify error details in JSON
        failed_patients = [p for p in data["patients"] if p["status"] == "failed"]
        assert len(failed_patients) == 1
        assert failed_patients[0]["patient_id"] == "PAT002"
        assert "Duplicate" in failed_patients[0]["message"]


class TestPIXAddRegisterDryRunIntegration:
    """Test dry-run mode integration."""
    
    @patch('ihe_test_util.cli.pix_commands.load_certificate')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_dry_run_integration(
        self,
        mock_parse_csv,
        mock_load_cert,
        sample_csv_file,
        config_file
    ):
        """Test dry-run mode with real CSV file."""
        # Arrange
        runner = CliRunner()
        
        # Mock parse_csv
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John", "Jane", "Bob"],
            "last_name": ["Doe", "Smith", "Johnson"],
            "dob": ["1980-01-01", "1990-02-02", "1975-05-15"],
            "gender": ["M", "F", "M"],
            "patient_id": ["PAT001", "PAT002", "PAT003"],
            "patient_id_oid": ["1.2.3.4", "1.2.3.4", "1.2.3.4"],
            "mrn": ["MRN001", "MRN002", "MRN003"]
        })
        mock_parse_csv.return_value = (df, None)
        
        # Mock certificate
        mock_cert_bundle = Mock()
        mock_cert = Mock()
        mock_cert.not_valid_after_utc = datetime(2026, 12, 31, tzinfo=timezone.utc)
        mock_cert_bundle.certificate = mock_cert
        mock_load_cert.return_value = mock_cert_bundle
        
        # Act
        result = runner.invoke(
            register,
            [
                str(sample_csv_file),
                "--config", str(config_file),
                "--dry-run"
            ],
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.output
        assert "CSV validated: 3 patients" in result.output
        assert "Config validated" in result.output
        assert "Certificate validated" in result.output
        assert "John Doe" in result.output
        assert "Jane Smith" in result.output
        assert "Bob Johnson" in result.output
        assert "DRY RUN COMPLETE" in result.output


class TestPIXAddRegisterEndpointOverride:
    """Test endpoint override functionality."""
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_endpoint_override_integration(
        self,
        mock_parse_csv,
        mock_workflow_class,
        sample_csv_file,
        config_file
    ):
        """Test that --endpoint option correctly overrides config."""
        # Arrange
        runner = CliRunner()
        
        # Mock parse_csv
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John"],
            "last_name": ["Doe"],
            "dob": ["1980-01-01"],
            "gender": ["M"],
            "patient_id": ["PAT001"],
            "patient_id_oid": ["1.2.3.4"],
            "mrn": ["MRN001"]
        })
        mock_parse_csv.return_value = (df, None)
        
        # Create successful result
        patient1 = PatientResult(
            patient_id="PAT001",
            pix_add_status=TransactionStatus.SUCCESS,
            pix_add_message="Patient registered successfully",
            processing_time_ms=100,
            enterprise_id="ENT001^^^1.2.3.4.5&ISO",
            enterprise_id_oid="1.2.3.4.5",
            registration_timestamp=datetime.now(timezone.utc)
        )
        
        result = BatchProcessingResult(
            batch_id="batch-override-test",
            csv_file_path=str(sample_csv_file),
            start_timestamp=datetime.now(timezone.utc),
            total_patients=1
        )
        result.patient_results = [patient1]
        result.successful_patients = 1
        result.failed_patients = 0
        result.pix_add_success_count = 1
        result.end_timestamp = datetime.now(timezone.utc)
        
        # Mock workflow
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = result
        mock_workflow_class.return_value = mock_workflow
        
        custom_endpoint = "https://custom.pix.server.com/add"
        
        # Act
        result = runner.invoke(
            register,
            [
                str(sample_csv_file),
                "--config", str(config_file),
                "--endpoint", custom_endpoint
            ],
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        assert custom_endpoint in result.output
        
        # Verify workflow was called with correct endpoint
        call_args = mock_workflow_class.call_args
        config_used = call_args[0][0]
        assert config_used.endpoints.pix_add_url == custom_endpoint
