"""Unit tests for PIX Add workflow orchestration.

Tests workflow orchestration including single patient processing, batch processing,
error handling, and result aggregation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open

import pandas as pd
import pytest
from requests import ConnectionError, Timeout
from requests.exceptions import SSLError

from ihe_test_util.config.schema import Config
from ihe_test_util.ihe_transactions.workflows import (
    PIXAddWorkflow,
    ErrorCategory,
    categorize_error,
    get_remediation_message,
    save_registered_identifiers,
    generate_summary_report
)
from ihe_test_util.models.batch import BatchProcessingResult, PatientResult
from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.models.responses import TransactionResponse, TransactionStatus, TransactionType
from ihe_test_util.models.saml import SAMLAssertion, SAMLGenerationMethod
from ihe_test_util.utils.exceptions import ValidationError


@pytest.fixture
def mock_config():
    """Create mock configuration for testing."""
    config = Mock(spec=Config)
    
    # Endpoints
    config.endpoints = Mock()
    config.endpoints.pix_add_url = "https://pix.example.com/pix/add"
    
    # SAML configuration
    config.saml = Mock()
    config.saml.cert_path = "tests/fixtures/test_cert.pem"
    config.saml.key_path = "tests/fixtures/test_key.pem"
    config.saml.issuer = "test-issuer"
    config.saml.subject = "test-subject"
    
    # OIDs
    config.sender_oid = "2.16.840.1.113883.3.72.5.1"
    config.receiver_oid = "2.16.840.1.113883.3.72.5.2"
    config.sender_application = "IHE_TEST_UTIL"
    config.receiver_application = "PIX_MANAGER"
    
    # Transport
    config.transport = Mock()
    config.transport.verify_tls = True
    
    return config


@pytest.fixture
def sample_patient():
    """Create sample patient demographics."""
    return PatientDemographics(
        patient_id="PAT001",
        patient_id_oid="2.16.840.1.113883.3.72.5.9.1",
        first_name="John",
        last_name="Doe",
        dob=datetime(1980, 1, 1).date(),
        gender="M",
        address="123 Main St",
        city="Boston",
        state="MA",
        zip="02101"
    )


@pytest.fixture
def sample_saml_assertion():
    """Create sample SAML assertion."""
    return SAMLAssertion(
        assertion_id="_12345",
        issuer="test-issuer",
        subject="test-subject",
        audience="https://pix.example.com",
        issue_instant=datetime.now(timezone.utc),
        not_before=datetime.now(timezone.utc),
        not_on_or_after=datetime.now(timezone.utc),
        xml_content="<saml:Assertion>...</saml:Assertion>",
        signature="<ds:Signature>...</ds:Signature>",
        certificate_subject="CN=Test",
        generation_method=SAMLGenerationMethod.PROGRAMMATIC
    )


@pytest.fixture
def successful_transaction_response():
    """Create successful transaction response."""
    return TransactionResponse(
        response_id="ACK-123",
        request_id="MSG-456",
        transaction_type=TransactionType.PIX_ADD,
        status=TransactionStatus.SUCCESS,
        status_code="AA",
        response_timestamp=datetime.now(timezone.utc),
        response_xml="<SOAP>...</SOAP>",
        extracted_identifiers={
            "patient_id": "EID123456",
            "patient_id_root": "1.2.840.114350.1.13.99998.8734"
        },
        processing_time_ms=250
    )


@pytest.fixture
def error_transaction_response():
    """Create error transaction response."""
    return TransactionResponse(
        response_id="ACK-789",
        request_id="MSG-012",
        transaction_type=TransactionType.PIX_ADD,
        status=TransactionStatus.ERROR,
        status_code="AE",
        response_timestamp=datetime.now(timezone.utc),
        response_xml="<SOAP>...</SOAP>",
        error_messages=["Duplicate patient identifier"],
        processing_time_ms=150
    )


class TestErrorCategorization:
    """Test error categorization logic."""
    
    def test_categorize_error_connection_error(self):
        """Test ConnectionError categorized as CRITICAL."""
        error = ConnectionError("Network unreachable")
        category = categorize_error(error)
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_error_timeout(self):
        """Test Timeout categorized as CRITICAL."""
        error = Timeout("Request timed out")
        category = categorize_error(error)
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_error_ssl_error(self):
        """Test SSLError categorized as CRITICAL."""
        error = SSLError("Certificate verification failed")
        category = categorize_error(error)
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_error_validation_error(self):
        """Test ValidationError categorized as NON_CRITICAL."""
        error = ValidationError("Invalid gender code")
        category = categorize_error(error)
        assert category == ErrorCategory.NON_CRITICAL
    
    def test_categorize_error_certificate_string(self):
        """Test error with 'certificate' in message as CRITICAL."""
        error = Exception("Certificate expired")
        category = categorize_error(error)
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_error_configuration_string(self):
        """Test error with 'configuration' in message as CRITICAL."""
        error = Exception("Configuration missing")
        category = categorize_error(error)
        assert category == ErrorCategory.CRITICAL


class TestRemediationMessages:
    """Test remediation message generation."""
    
    def test_remediation_connection_error(self):
        """Test remediation for ConnectionError."""
        error = ConnectionError("Network unreachable")
        message = get_remediation_message(error)
        assert "network connectivity" in message.lower()
        assert "endpoint url" in message.lower()
    
    def test_remediation_timeout(self):
        """Test remediation for Timeout."""
        error = Timeout("Request timed out")
        message = get_remediation_message(error)
        assert "timeout" in message.lower()
        assert "config" in message.lower()
    
    def test_remediation_ssl_error(self):
        """Test remediation for SSLError."""
        error = SSLError("Certificate validation failed")
        message = get_remediation_message(error)
        assert "certificate" in message.lower()
        assert "verify_tls" in message.lower()
    
    def test_remediation_validation_error(self):
        """Test remediation for ValidationError."""
        error = ValidationError("Invalid data")
        message = get_remediation_message(error)
        assert "csv" in message.lower()
        assert "fix" in message.lower()


class TestProcessPatient:
    """Test single patient processing."""
    
    @patch('ihe_test_util.ihe_transactions.workflows.build_pix_add_message')
    def test_process_patient_success(
        self,
        mock_build_message,
        mock_config,
        sample_patient,
        sample_saml_assertion,
        successful_transaction_response
    ):
        """Test successful patient processing."""
        # Setup mocks
        mock_build_message.return_value = "<HL7v3>...</HL7v3>"
        
        workflow = PIXAddWorkflow(mock_config)
        workflow.soap_client = Mock()
        workflow.soap_client.submit_pix_add.return_value = successful_transaction_response
        
        # Process patient
        result = workflow.process_patient(sample_patient, sample_saml_assertion)
        
        # Verify result
        assert result.patient_id == "PAT001"
        assert result.pix_add_status == TransactionStatus.SUCCESS
        assert result.enterprise_id == "EID123456"
        assert result.enterprise_id_oid == "1.2.840.114350.1.13.99998.8734"
        assert result.processing_time_ms >= 0  # Can be 0 with mocks (no actual network delay)
        assert result.is_success
        
        # Verify calls
        mock_build_message.assert_called_once()
        workflow.soap_client.submit_pix_add.assert_called_once()
    
    @patch('ihe_test_util.ihe_transactions.workflows.build_pix_add_message')
    def test_process_patient_ae_status(
        self,
        mock_build_message,
        mock_config,
        sample_patient,
        sample_saml_assertion,
        error_transaction_response
    ):
        """Test patient processing with AE status (non-critical error)."""
        # Setup mocks
        mock_build_message.return_value = "<HL7v3>...</HL7v3>"
        
        workflow = PIXAddWorkflow(mock_config)
        workflow.soap_client = Mock()
        workflow.soap_client.submit_pix_add.return_value = error_transaction_response
        
        # Process patient
        result = workflow.process_patient(sample_patient, sample_saml_assertion)
        
        # Verify result
        assert result.patient_id == "PAT001"
        assert result.pix_add_status == TransactionStatus.ERROR
        assert not result.is_success
        assert "Duplicate patient identifier" in result.pix_add_message
        assert result.enterprise_id is None
    
    @patch('ihe_test_util.ihe_transactions.workflows.build_pix_add_message')
    def test_process_patient_critical_error_connection(
        self,
        mock_build_message,
        mock_config,
        sample_patient,
        sample_saml_assertion
    ):
        """Test patient processing with critical ConnectionError."""
        # Setup mocks
        mock_build_message.return_value = "<HL7v3>...</HL7v3>"
        
        workflow = PIXAddWorkflow(mock_config)
        workflow.soap_client = Mock()
        workflow.soap_client.submit_pix_add.side_effect = ConnectionError("Network unreachable")
        
        # Should raise ConnectionError (critical)
        with pytest.raises(ConnectionError):
            workflow.process_patient(sample_patient, sample_saml_assertion)
    
    @patch('ihe_test_util.ihe_transactions.workflows.build_pix_add_message')
    def test_process_patient_non_critical_error_validation(
        self,
        mock_build_message,
        mock_config,
        sample_patient,
        sample_saml_assertion
    ):
        """Test patient processing with non-critical ValidationError."""
        # Setup mocks
        mock_build_message.side_effect = ValidationError("Invalid gender code 'X'")
        
        workflow = PIXAddWorkflow(mock_config)
        workflow.soap_client = Mock()
        
        # Should NOT raise (non-critical), return error result
        result = workflow.process_patient(sample_patient, sample_saml_assertion)
        
        assert result.patient_id == "PAT001"
        assert result.pix_add_status == TransactionStatus.ERROR
        assert not result.is_success
        assert "Invalid gender code" in result.pix_add_message


class TestProcessBatch:
    """Test batch processing."""
    
    @patch('ihe_test_util.ihe_transactions.workflows.parse_csv')
    @patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow._generate_saml_assertion')
    @patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_process_batch_all_success(
        self,
        mock_exists,
        mock_process_patient,
        mock_generate_saml,
        mock_parse_csv,
        mock_config,
        sample_saml_assertion,
        tmp_path
    ):
        """Test batch processing with all patients successful."""
        # Setup mocks
        mock_exists.return_value = True
        
        # Create test CSV data
        df = pd.DataFrame({
            'patient_id': ['PAT001', 'PAT002', 'PAT003'],
            'patient_id_oid': ['2.16.840.1'] * 3,
            'first_name': ['John', 'Jane', 'Bob'],
            'last_name': ['Doe', 'Smith', 'Johnson'],
            'dob': ['1980-01-01', '1985-05-15', '1990-10-20'],
            'gender': ['M', 'F', 'M']
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_generate_saml.return_value = sample_saml_assertion
        
        # Mock successful patient results
        def create_success_result(patient, saml):
            return PatientResult(
                patient_id=patient.patient_id,
                pix_add_status=TransactionStatus.SUCCESS,
                pix_add_message="Registered successfully",
                processing_time_ms=250,
                enterprise_id=f"EID-{patient.patient_id}",
                enterprise_id_oid="1.2.840.114350.1.13.99998.8734",
                registration_timestamp=datetime.now(timezone.utc)
            )
        
        mock_process_patient.side_effect = create_success_result
        
        # Process batch
        workflow = PIXAddWorkflow(mock_config)
        csv_path = tmp_path / "patients.csv"
        result = workflow.process_batch(csv_path)
        
        # Verify results
        assert result.total_patients == 3
        assert result.successful_patients == 3
        assert result.failed_patients == 0
        assert result.pix_add_success_count == 3
        assert len(result.patient_results) == 3
        assert result.success_rate == 100.0
        assert result.end_timestamp is not None
        
        # Verify all patients processed
        assert mock_process_patient.call_count == 3
    
    @patch('ihe_test_util.ihe_transactions.workflows.parse_csv')
    @patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow._generate_saml_assertion')
    @patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_process_batch_partial_success(
        self,
        mock_exists,
        mock_process_patient,
        mock_generate_saml,
        mock_parse_csv,
        mock_config,
        sample_saml_assertion,
        tmp_path
    ):
        """Test batch processing with mixed success/failure."""
        # Setup mocks
        mock_exists.return_value = True
        
        # Create test CSV data
        df = pd.DataFrame({
            'patient_id': ['PAT001', 'PAT002', 'PAT003'],
            'patient_id_oid': ['2.16.840.1'] * 3,
            'first_name': ['John', 'Jane', 'Bob'],
            'last_name': ['Doe', 'Smith', 'Johnson'],
            'dob': ['1980-01-01', '1985-05-15', '1990-10-20'],
            'gender': ['M', 'F', 'M']
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_generate_saml.return_value = sample_saml_assertion
        
        # Mock mixed results (patient 2 fails)
        def create_mixed_result(patient, saml):
            if patient.patient_id == "PAT002":
                return PatientResult(
                    patient_id=patient.patient_id,
                    pix_add_status=TransactionStatus.ERROR,
                    pix_add_message="PIX Add rejected: Duplicate patient",
                    processing_time_ms=150,
                    error_details="Duplicate error"
                )
            else:
                return PatientResult(
                    patient_id=patient.patient_id,
                    pix_add_status=TransactionStatus.SUCCESS,
                    pix_add_message="Registered successfully",
                    processing_time_ms=250,
                    enterprise_id=f"EID-{patient.patient_id}",
                    enterprise_id_oid="1.2.840.114350.1.13.99998.8734",
                    registration_timestamp=datetime.now(timezone.utc)
                )
        
        mock_process_patient.side_effect = create_mixed_result
        
        # Process batch
        workflow = PIXAddWorkflow(mock_config)
        csv_path = tmp_path / "patients.csv"
        result = workflow.process_batch(csv_path)
        
        # Verify results
        assert result.total_patients == 3
        assert result.successful_patients == 2
        assert result.failed_patients == 1
        assert result.pix_add_success_count == 2
        assert result.success_rate == pytest.approx(66.67, rel=0.1)
        
        # Verify workflow continued after failure
        assert mock_process_patient.call_count == 3
    
    @patch('ihe_test_util.ihe_transactions.workflows.parse_csv')
    @patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow._generate_saml_assertion')
    @patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_process_batch_critical_error_halts_workflow(
        self,
        mock_exists,
        mock_process_patient,
        mock_generate_saml,
        mock_parse_csv,
        mock_config,
        sample_saml_assertion,
        tmp_path
    ):
        """Test batch processing halts on critical error."""
        # Setup mocks
        mock_exists.return_value = True
        
        # Create test CSV data
        df = pd.DataFrame({
            'patient_id': ['PAT001', 'PAT002', 'PAT003'],
            'patient_id_oid': ['2.16.840.1'] * 3,
            'first_name': ['John', 'Jane', 'Bob'],
            'last_name': ['Doe', 'Smith', 'Johnson'],
            'dob': ['1980-01-01', '1985-05-15', '1990-10-20'],
            'gender': ['M', 'F', 'M']
        })
        mock_parse_csv.return_value = (df, None)
        
        mock_generate_saml.return_value = sample_saml_assertion
        
        # Mock critical error on patient 2
        call_count = 0
        def raise_on_second_call(patient, saml):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ConnectionError("Endpoint unreachable")
            return PatientResult(
                patient_id=patient.patient_id,
                pix_add_status=TransactionStatus.SUCCESS,
                pix_add_message="Registered successfully",
                processing_time_ms=250,
                enterprise_id=f"EID-{patient.patient_id}",
                enterprise_id_oid="1.2.840.114350.1.13.99998.8734",
                registration_timestamp=datetime.now(timezone.utc)
            )
        
        mock_process_patient.side_effect = raise_on_second_call
        
        # Process batch - should raise ConnectionError
        workflow = PIXAddWorkflow(mock_config)
        csv_path = tmp_path / "patients.csv"
        
        with pytest.raises(ConnectionError):
            workflow.process_batch(csv_path)
        
        # Verify workflow halted after patient 1
        assert mock_process_patient.call_count == 2  # Stopped at patient 2


class TestSaveRegisteredIdentifiers:
    """Test saving registered identifiers to JSON."""
    
    def test_save_registered_identifiers(self, tmp_path):
        """Test saving registered identifiers to file."""
        # Create batch result with mixed success/failure
        batch_result = BatchProcessingResult(
            batch_id="550e8400-e29b-41d4-a716-446655440000",
            csv_file_path="patients.csv",
            start_timestamp=datetime(2025, 11, 17, 2, 30, 0, tzinfo=timezone.utc),
            end_timestamp=datetime(2025, 11, 17, 2, 31, 45, tzinfo=timezone.utc),
            total_patients=3,
            successful_patients=2,
            failed_patients=1,
            patient_results=[
                PatientResult(
                    patient_id="PAT001",
                    pix_add_status=TransactionStatus.SUCCESS,
                    pix_add_message="Success",
                    processing_time_ms=250,
                    enterprise_id="EID123456",
                    enterprise_id_oid="1.2.840.114350.1.13.99998.8734",
                    registration_timestamp=datetime(2025, 11, 17, 2, 30, 10, tzinfo=timezone.utc)
                ),
                PatientResult(
                    patient_id="PAT002",
                    pix_add_status=TransactionStatus.ERROR,
                    pix_add_message="Failed",
                    processing_time_ms=150
                ),
                PatientResult(
                    patient_id="PAT003",
                    pix_add_status=TransactionStatus.SUCCESS,
                    pix_add_message="Success",
                    processing_time_ms=300,
                    enterprise_id="EID123457",
                    enterprise_id_oid="1.2.840.114350.1.13.99998.8734",
                    registration_timestamp=datetime(2025, 11, 17, 2, 30, 15, tzinfo=timezone.utc)
                )
            ]
        )
        
        # Save to file
        output_path = tmp_path / "registered.json"
        save_registered_identifiers(batch_result, output_path)
        
        # Verify file created
        assert output_path.exists()
        
        # Verify content
        with output_path.open("r") as f:
            data = json.load(f)
        
        assert data["batch_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert data["total_registered"] == 2
        assert len(data["patients"]) == 2
        
        # Verify only successful patients included
        patient_ids = [p["patient_id"] for p in data["patients"]]
        assert "PAT001" in patient_ids
        assert "PAT003" in patient_ids
        assert "PAT002" not in patient_ids  # Failed patient excluded
        
        # Verify enterprise IDs present
        assert data["patients"][0]["enterprise_id"] == "EID123456"
        assert data["patients"][1]["enterprise_id"] == "EID123457"


class TestGenerateSummaryReport:
    """Test summary report generation."""
    
    def test_generate_summary_report(self):
        """Test generating summary report."""
        # Create batch result
        batch_result = BatchProcessingResult(
            batch_id="550e8400-e29b-41d4-a716-446655440000",
            csv_file_path="patients.csv",
            start_timestamp=datetime(2025, 11, 17, 2, 30, 0, tzinfo=timezone.utc),
            end_timestamp=datetime(2025, 11, 17, 2, 31, 45, tzinfo=timezone.utc),
            total_patients=10,
            successful_patients=8,
            failed_patients=2,
            patient_results=[
                PatientResult(
                    patient_id="PAT001",
                    pix_add_status=TransactionStatus.SUCCESS,
                    pix_add_message="Success",
                    processing_time_ms=250,
                    enterprise_id="EID001"
                ),
                PatientResult(
                    patient_id="PAT009",
                    pix_add_status=TransactionStatus.ERROR,
                    pix_add_message="Validation Error: Invalid gender",
                    processing_time_ms=50,
                    error_details="Fix patient data in CSV"
                )
            ]
        )
        
        # Generate report
        report = generate_summary_report(batch_result)
        
        # Verify report content
        assert "PIX ADD WORKFLOW SUMMARY" in report
        assert "550e8400" in report
        assert "patients.csv" in report
        assert "Total Patients:       10" in report
        assert "✓ Successful:         8" in report
        assert "✗ Failed:             2" in report
        assert "SUCCESSFUL REGISTRATIONS" in report
        assert "FAILED REGISTRATIONS" in report
        assert "PAT001" in report
        assert "PAT009" in report
        assert "OUTPUT FILES" in report
