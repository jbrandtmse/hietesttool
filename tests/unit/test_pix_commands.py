"""Unit tests for PIX Add CLI commands."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import click
import pytest
from click.testing import CliRunner

from ihe_test_util.cli.pix_commands import pix_add, register
from ihe_test_util.config.schema import (
    CertificatesConfig,
    Config,
    EndpointsConfig,
    LoggingConfig,
    TransportConfig,
)
from ihe_test_util.models.batch import BatchProcessingResult, PatientResult
from ihe_test_util.models.responses import TransactionStatus
from ihe_test_util.utils.exceptions import ConfigurationError, ValidationError


@pytest.fixture
def mock_config():
    """Create mock configuration object."""
    return Config(
        endpoints=EndpointsConfig(
            pix_add_url="https://pix.example.com/add",
            iti41_url="https://iti41.example.com/submit"
        ),
        certificates=CertificatesConfig(
            cert_path="tests/fixtures/test_cert.pem",
            key_path="tests/fixtures/test_key.pem",
            cert_format="pem"
        ),
        transport=TransportConfig(
            verify_tls=True,
            timeout_connect=10,
            timeout_read=30,
            max_retries=3
        ),
        logging=LoggingConfig(
            level="INFO",
            log_file="logs/ihe-test-util.log",
            redact_pii=False
        ),
        sender_oid="1.2.3.4.5",
        receiver_oid="1.2.3.4.6",
        sender_application="TestApp",
        receiver_application="PIXManager"
    )


@pytest.fixture
def mock_batch_result_success():
    """Create successful batch processing result."""
    patient1 = PatientResult(
        patient_id="PAT001",
        pix_add_status=TransactionStatus.SUCCESS,
        pix_add_message="Patient registered successfully",
        processing_time_ms=150,
        enterprise_id="12345^^^1.2.3.4.5&ISO",
        enterprise_id_oid="1.2.3.4.5",
        registration_timestamp=datetime.now(timezone.utc)
    )
    
    patient2 = PatientResult(
        patient_id="PAT002",
        pix_add_status=TransactionStatus.SUCCESS,
        pix_add_message="Patient registered successfully",
        processing_time_ms=200,
        enterprise_id="12346^^^1.2.3.4.5&ISO",
        enterprise_id_oid="1.2.3.4.5",
        registration_timestamp=datetime.now(timezone.utc)
    )
    
    result = BatchProcessingResult(
        batch_id="batch-123",
        csv_file_path="patients.csv",
        start_timestamp=datetime.now(timezone.utc),
        total_patients=2
    )
    result.patient_results = [patient1, patient2]
    result.successful_patients = 2
    result.failed_patients = 0
    result.pix_add_success_count = 2
    result.end_timestamp = datetime.now(timezone.utc)
    
    return result


@pytest.fixture
def mock_batch_result_mixed():
    """Create batch processing result with mixed success/failure."""
    patient1 = PatientResult(
        patient_id="PAT001",
        pix_add_status=TransactionStatus.SUCCESS,
        pix_add_message="Patient registered successfully",
        processing_time_ms=150,
        enterprise_id="12345^^^1.2.3.4.5&ISO",
        enterprise_id_oid="1.2.3.4.5",
        registration_timestamp=datetime.now(timezone.utc)
    )
    
    patient2 = PatientResult(
        patient_id="PAT002",
        pix_add_status=TransactionStatus.ERROR,
        pix_add_message="PIX Add rejected: Invalid data",
        processing_time_ms=100,
        error_details="Validation error: Missing required field"
    )
    
    result = BatchProcessingResult(
        batch_id="batch-456",
        csv_file_path="patients.csv",
        start_timestamp=datetime.now(timezone.utc),
        total_patients=2
    )
    result.patient_results = [patient1, patient2]
    result.successful_patients = 1
    result.failed_patients = 1
    result.pix_add_success_count = 1
    result.error_summary = {
        "_error_report": "Error Summary Report...",
        "_error_statistics": {
            "total_errors": 1,
            "by_category": {"PERMANENT": 1},
            "by_type": {"ValidationError": 1},
            "error_rate": 50.0
        }
    }
    result.end_timestamp = datetime.now(timezone.utc)
    
    return result


class TestPIXAddRegisterBasicUsage:
    """Test basic PIX Add register command usage."""
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_basic_usage(
        self,
        mock_parse_csv,
        mock_workflow_class,
        tmp_path,
        mock_config,
        mock_batch_result_success
    ):
        """Test basic registration with default config."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
            "Jane,Smith,1990-02-02,F,PAT002,1.2.3.4\n"
        )
        
        # Mock parse_csv to return DataFrame
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John", "Jane"],
            "last_name": ["Doe", "Smith"],
            "dob": ["1980-01-01", "1990-02-02"],
            "gender": ["M", "F"],
            "patient_id": ["PAT001", "PAT002"],
            "patient_id_oid": ["1.2.3.4", "1.2.3.4"]
        })
        mock_parse_csv.return_value = (df, None)
        
        # Mock workflow
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = mock_batch_result_success
        mock_workflow_class.return_value = mock_workflow
        
        # Create context with config
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file)],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        assert "PIX ADD PATIENT REGISTRATION" in result.output
        assert "✓ Success" in result.output
        mock_workflow.process_batch.assert_called_once()


class TestPIXAddRegisterOptions:
    """Test PIX Add register command with various options."""
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_endpoint_override(
        self,
        mock_parse_csv,
        mock_workflow_class,
        tmp_path,
        mock_config,
        mock_batch_result_success
    ):
        """Test --endpoint option overrides config."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
        )
        
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John"],
            "last_name": ["Doe"],
            "dob": ["1980-01-01"],
            "gender": ["M"],
            "patient_id": ["PAT001"],
            "patient_id_oid": ["1.2.3.4"]
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = mock_batch_result_success
        mock_workflow_class.return_value = mock_workflow
        
        custom_endpoint = "https://custom.example.com/pix"
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file), "--endpoint", custom_endpoint],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        assert custom_endpoint in result.output
        
        # Verify workflow was initialized with updated config
        call_args = mock_workflow_class.call_args
        config_used = call_args[0][0]
        assert config_used.endpoints.pix_add_url == custom_endpoint
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_cert_override(
        self,
        mock_parse_csv,
        mock_workflow_class,
        tmp_path,
        mock_config,
        mock_batch_result_success
    ):
        """Test --cert option overrides config."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
        )
        
        # Create custom cert file
        custom_cert = tmp_path / "custom_cert.pem"
        custom_cert.write_text("FAKE CERT")
        custom_key = tmp_path / "custom_cert.key"
        custom_key.write_text("FAKE KEY")
        
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John"],
            "last_name": ["Doe"],
            "dob": ["1980-01-01"],
            "gender": ["M"],
            "patient_id": ["PAT001"],
            "patient_id_oid": ["1.2.3.4"]
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = mock_batch_result_success
        mock_workflow_class.return_value = mock_workflow
        
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file), "--cert", str(custom_cert)],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        
        # Verify workflow was initialized with updated cert
        call_args = mock_workflow_class.call_args
        config_used = call_args[0][0]
        assert config_used.certificates.cert_path == str(custom_cert)
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_http_warning(
        self,
        mock_parse_csv,
        mock_workflow_class,
        tmp_path,
        mock_config
    ):
        """Test --http flag displays security warning."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
        )
        
        ctx_obj = {"config": mock_config}
        
        # Act - User declines HTTP
        result = runner.invoke(
            register,
            [str(csv_file), "--http"],
            obj=ctx_obj,
            input="n\n",  # Decline HTTP
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 1
        assert "WARNING" in result.output
        assert "insecure HTTP transport" in result.output
        assert "Continue with HTTP?" in result.output
        assert "Aborted" in result.output


class TestPIXAddRegisterOutputAndDryRun:
    """Test output generation and dry-run mode."""
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_output_json(
        self,
        mock_parse_csv,
        mock_workflow_class,
        tmp_path,
        mock_config,
        mock_batch_result_success
    ):
        """Test --output option creates JSON file."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
        )
        
        output_file = tmp_path / "results.json"
        
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John"],
            "last_name": ["Doe"],
            "dob": ["1980-01-01"],
            "gender": ["M"],
            "patient_id": ["PAT001"],
            "patient_id_oid": ["1.2.3.4"]
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = mock_batch_result_success
        mock_workflow_class.return_value = mock_workflow
        
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file), "--output", str(output_file)],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        assert output_file.exists()
        assert "Results saved to" in result.output
        
        # Verify JSON structure
        with output_file.open() as f:
            data = json.load(f)
        
        assert "timestamp" in data
        assert "config" in data
        assert "summary" in data
        assert "patients" in data
        assert data["summary"]["total_patients"] == 2
        assert data["summary"]["successful"] == 2
    
    @patch('ihe_test_util.cli.pix_commands.load_certificate')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_dry_run(
        self,
        mock_parse_csv,
        mock_load_cert,
        tmp_path,
        mock_config
    ):
        """Test --dry-run validates without submitting."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
            "Jane,Smith,1990-02-02,F,PAT002,1.2.3.4\n"
        )
        
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John", "Jane"],
            "last_name": ["Doe", "Smith"],
            "dob": ["1980-01-01", "1990-02-02"],
            "gender": ["M", "F"],
            "patient_id": ["PAT001", "PAT002"],
            "patient_id_oid": ["1.2.3.4", "1.2.3.4"]
        })
        mock_parse_csv.return_value = (df, None)
        
        # Mock certificate
        mock_cert_bundle = Mock()
        mock_cert = Mock()
        mock_cert.not_valid_after_utc = datetime(2026, 12, 31, tzinfo=timezone.utc)
        mock_cert_bundle.certificate = mock_cert
        mock_load_cert.return_value = mock_cert_bundle
        
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file), "--dry-run"],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.output
        assert "Validation Only" in result.output
        assert "CSV validated: 2 patients" in result.output
        assert "Config validated" in result.output
        assert "Certificate validated" in result.output
        assert "DRY RUN COMPLETE" in result.output


class TestPIXAddRegisterDisplay:
    """Test progress display and color-coded output."""
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_progress_display(
        self,
        mock_parse_csv,
        mock_workflow_class,
        tmp_path,
        mock_config,
        mock_batch_result_success
    ):
        """Test real-time progress display for each patient."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
            "Jane,Smith,1990-02-02,F,PAT002,1.2.3.4\n"
        )
        
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John", "Jane"],
            "last_name": ["Doe", "Smith"],
            "dob": ["1980-01-01", "1990-02-02"],
            "gender": ["M", "F"],
            "patient_id": ["PAT001", "PAT002"],
            "patient_id_oid": ["1.2.3.4", "1.2.3.4"]
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = mock_batch_result_success
        mock_workflow_class.return_value = mock_workflow
        
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file)],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 0
        assert "Processing patients..." in result.output
        assert "Patient   1/2" in result.output
        assert "Patient   2/2" in result.output
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_color_output(
        self,
        mock_parse_csv,
        mock_workflow_class,
        tmp_path,
        mock_config,
        mock_batch_result_mixed
    ):
        """Test color-coded output for success and failure."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
            "Jane,Smith,1990-02-02,F,PAT002,1.2.3.4\n"
        )
        
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John", "Jane"],
            "last_name": ["Doe", "Smith"],
            "dob": ["1980-01-01", "1990-02-02"],
            "gender": ["M", "F"],
            "patient_id": ["PAT001", "PAT002"],
            "patient_id_oid": ["1.2.3.4", "1.2.3.4"]
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = mock_batch_result_mixed
        mock_workflow_class.return_value = mock_workflow
        
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file)],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 2  # Transaction errors occurred
        assert "✓ Success" in result.output
        assert "✗ Failed" in result.output


class TestPIXAddRegisterSummary:
    """Test summary report generation."""
    
    @patch('ihe_test_util.cli.pix_commands.PIXAddWorkflow')
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_summary_report(
        self,
        mock_parse_csv,
        mock_workflow_class,
        tmp_path,
        mock_config,
        mock_batch_result_mixed
    ):
        """Test summary report displays statistics."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
            "Jane,Smith,1990-02-02,F,PAT002,1.2.3.4\n"
        )
        
        import pandas as pd
        df = pd.DataFrame({
            "first_name": ["John", "Jane"],
            "last_name": ["Doe", "Smith"],
            "dob": ["1980-01-01", "1990-02-02"],
            "gender": ["M", "F"],
            "patient_id": ["PAT001", "PAT002"],
            "patient_id_oid": ["1.2.3.4", "1.2.3.4"]
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_workflow = Mock()
        mock_workflow.process_batch.return_value = mock_batch_result_mixed
        mock_workflow_class.return_value = mock_workflow
        
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file)],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert "REGISTRATION SUMMARY" in result.output
        assert "Total Patients:" in result.output
        assert "Successful:" in result.output
        assert "Failed:" in result.output


class TestPIXAddRegisterErrorHandling:
    """Test error handling and exit codes."""
    
    @patch('ihe_test_util.cli.pix_commands.parse_csv')
    def test_pix_add_register_validation_error_exit_code(
        self,
        mock_parse_csv,
        tmp_path,
        mock_config
    ):
        """Test validation error returns exit code 1."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text("invalid csv")
        
        mock_parse_csv.side_effect = ValidationError("Invalid CSV format")
        
        ctx_obj = {"config": mock_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file)],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 1
        assert "Validation Error" in result.output
    
    def test_pix_add_register_missing_config_error(
        self,
        tmp_path
    ):
        """Test missing configuration returns exit code 3."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id,patient_id_oid\n"
            "John,Doe,1980-01-01,M,PAT001,1.2.3.4\n"
        )
        
        # Create config with missing certificate path (None triggers ConfigurationError)
        bad_config = Config(
            endpoints=EndpointsConfig(
                pix_add_url="https://example.com/pix",  # Use HTTPS to avoid HTTP warning
                iti41_url="https://example.com/iti41"
            ),
            certificates=CertificatesConfig(
                cert_path=None,  # None triggers ConfigurationError
                key_path="tests/fixtures/test_key.pem",
                cert_format="pem"
            ),
            transport=TransportConfig(),
            logging=LoggingConfig(),
            sender_oid="1.2.3.4",
            receiver_oid="1.2.3.4",
            sender_application="Test",
            receiver_application="Test"
        )
        
        ctx_obj = {"config": bad_config}
        
        # Act
        result = runner.invoke(
            register,
            [str(csv_file)],
            obj=ctx_obj,
            catch_exceptions=False
        )
        
        # Assert
        assert result.exit_code == 3
        assert "Configuration Error" in result.output


class TestPIXAddRegisterHelp:
    """Test help documentation."""
    
    def test_pix_add_help_documentation(self):
        """Test --help displays complete documentation."""
        # Arrange
        runner = CliRunner()
        
        # Act
        result = runner.invoke(pix_add, ["--help"])
        
        # Assert
        assert result.exit_code == 0
        assert "PIX Add patient registration commands" in result.output
    
    def test_pix_add_register_help_documentation(self):
        """Test register --help displays all options."""
        # Arrange
        runner = CliRunner()
        
        # Act
        result = runner.invoke(register, ["--help"])
        
        # Assert
        assert result.exit_code == 0
        assert "--endpoint" in result.output
        assert "--cert" in result.output
        assert "--http" in result.output
        assert "--output" in result.output
        assert "--dry-run" in result.output
        assert "--config" in result.output
        assert "Examples:" in result.output
