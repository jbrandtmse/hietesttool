"""Unit tests for integrated PIX Add + ITI-41 workflow.

Tests the IntegratedWorkflow class that orchestrates CSV → CCD → PIX Add → ITI-41.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from lxml import etree
import pandas as pd
import pytest
from requests import ConnectionError, Timeout
from requests.exceptions import SSLError

from ihe_test_util.config.schema import Config
from ihe_test_util.ihe_transactions.workflows import (
    IntegratedWorkflow,
    generate_integrated_workflow_summary,
    save_workflow_results_to_json,
)
from ihe_test_util.models.batch import (
    BatchWorkflowResult,
    PatientWorkflowResult,
    BatchProcessingResult,
    PatientResult,
)
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
    config.endpoints.iti41_url = "https://xds.example.com/xdsrepository"
    
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
    
    # Certificates
    config.certificates = Mock()
    config.certificates.cert_path = "tests/fixtures/test_cert.pem"
    config.certificates.key_path = "tests/fixtures/test_key.pem"
    
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
def successful_pix_response():
    """Create successful PIX Add transaction response."""
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
def successful_iti41_response():
    """Create successful ITI-41 transaction response."""
    return TransactionResponse(
        response_id="REG-789",
        request_id="DOC-012",
        transaction_type=TransactionType.ITI41,
        status=TransactionStatus.SUCCESS,
        status_code="Success",
        response_timestamp=datetime.now(timezone.utc),
        response_xml="<SOAP>...</SOAP>",
        extracted_identifiers={
            "document_id": "1.2.3.4.5.6.7890"
        },
        processing_time_ms=350
    )


@pytest.fixture
def error_pix_response():
    """Create error PIX Add transaction response."""
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


class TestPatientWorkflowResult:
    """Test PatientWorkflowResult dataclass."""
    
    def test_is_fully_successful_both_success(self):
        """Test is_fully_successful returns True when both transactions succeed."""
        result = PatientWorkflowResult(
            patient_id="PAT001",
            csv_parsed=True,
            ccd_generated=True,
            pix_add_status="success",
            pix_add_message="Registered",
            pix_enterprise_id="EID123",
            iti41_status="success",
            iti41_message="Document submitted",
            document_id="DOC123"
        )
        assert result.is_fully_successful is True
    
    def test_is_fully_successful_pix_failed(self):
        """Test is_fully_successful returns False when PIX Add fails."""
        result = PatientWorkflowResult(
            patient_id="PAT001",
            csv_parsed=True,
            ccd_generated=True,
            pix_add_status="failed",
            pix_add_message="Registration failed",
            iti41_status="skipped",
            iti41_message="Skipped due to PIX Add failure"
        )
        assert result.is_fully_successful is False
    
    def test_is_fully_successful_iti41_failed(self):
        """Test is_fully_successful returns False when ITI-41 fails."""
        result = PatientWorkflowResult(
            patient_id="PAT001",
            csv_parsed=True,
            ccd_generated=True,
            pix_add_status="success",
            pix_add_message="Registered",
            pix_enterprise_id="EID123",
            iti41_status="failed",
            iti41_message="Document submission failed"
        )
        assert result.is_fully_successful is False


class TestBatchWorkflowResult:
    """Test BatchWorkflowResult dataclass."""
    
    def test_computed_counts_all_success(self):
        """Test computed counts when all patients succeed."""
        result = BatchWorkflowResult(
            batch_id="batch-001",
            csv_file="patients.csv",
            ccd_template="template.xml",
            start_timestamp=datetime.now(timezone.utc),
            patient_results=[
                PatientWorkflowResult(
                    patient_id="PAT001",
                    pix_add_status="success",
                    iti41_status="success"
                ),
                PatientWorkflowResult(
                    patient_id="PAT002",
                    pix_add_status="success",
                    iti41_status="success"
                ),
            ]
        )
        
        assert result.total_patients == 2
        assert result.fully_successful_count == 2
        assert result.pix_add_success_count == 2
        assert result.pix_add_failed_count == 0
        assert result.iti41_success_count == 2
        assert result.iti41_failed_count == 0
        assert result.iti41_skipped_count == 0
        assert result.full_success_rate == 100.0
        assert result.pix_add_success_rate == 100.0
        assert result.iti41_success_rate == 100.0
    
    def test_computed_counts_partial_success(self):
        """Test computed counts with mixed success/failure."""
        result = BatchWorkflowResult(
            batch_id="batch-001",
            csv_file="patients.csv",
            ccd_template="template.xml",
            start_timestamp=datetime.now(timezone.utc),
            patient_results=[
                PatientWorkflowResult(
                    patient_id="PAT001",
                    pix_add_status="success",
                    iti41_status="success"
                ),
                PatientWorkflowResult(
                    patient_id="PAT002",
                    pix_add_status="failed",
                    iti41_status="skipped"
                ),
                PatientWorkflowResult(
                    patient_id="PAT003",
                    pix_add_status="success",
                    iti41_status="failed"
                ),
            ]
        )
        
        assert result.total_patients == 3
        assert result.fully_successful_count == 1
        assert result.pix_add_success_count == 2
        assert result.pix_add_failed_count == 1
        assert result.iti41_success_count == 1
        assert result.iti41_failed_count == 1
        assert result.iti41_skipped_count == 1
        assert result.full_success_rate == pytest.approx(33.33, rel=0.1)
        assert result.pix_add_success_rate == pytest.approx(66.67, rel=0.1)
    
    def test_computed_counts_empty_results(self):
        """Test computed counts with no patients."""
        result = BatchWorkflowResult(
            batch_id="batch-001",
            csv_file="patients.csv",
            ccd_template="template.xml",
            start_timestamp=datetime.now(timezone.utc),
            patient_results=[]
        )
        
        assert result.total_patients == 0
        assert result.fully_successful_count == 0
        assert result.full_success_rate == 0.0


class TestIntegratedWorkflowProcessPatient:
    """Test IntegratedWorkflow.process_patient method."""
    
    @patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow')
    @patch('ihe_test_util.ihe_transactions.workflows.ITI41SOAPClient')
    @patch('ihe_test_util.ihe_transactions.workflows.TemplatePersonalizer')
    @patch('ihe_test_util.ihe_transactions.workflows.XDSbMetadataBuilder')
    @patch('pathlib.Path.exists')
    def test_process_patient_full_success(
        self,
        mock_exists,
        mock_metadata_builder,
        mock_personalizer,
        mock_iti41_client,
        mock_pix_workflow,
        mock_config,
        sample_patient,
        sample_saml_assertion,
    ):
        """Test successful processing of single patient through full workflow."""
        mock_exists.return_value = True
        
        # Mock PIX Add workflow
        mock_pix_instance = Mock()
        mock_pix_workflow.return_value = mock_pix_instance
        mock_pix_result = PatientResult(
            patient_id="PAT001",
            pix_add_status=TransactionStatus.SUCCESS,
            pix_add_message="Registered",
            processing_time_ms=250,
            enterprise_id="EID123456",
            enterprise_id_oid="1.2.840.114350.1.13.99998.8734"
        )
        mock_pix_instance.process_patient.return_value = mock_pix_result
        
        # Mock CCD personalizer
        mock_personalizer_instance = Mock()
        mock_personalizer.return_value = mock_personalizer_instance
        mock_personalizer_instance.personalize.return_value = "<ClinicalDocument>...</ClinicalDocument>"
        
        # Mock metadata builder - return an lxml Element that can be serialized
        mock_metadata_instance = Mock()
        mock_metadata_builder.return_value = mock_metadata_instance
        mock_metadata_element = etree.Element("SubmitObjectsRequest")
        mock_metadata_instance.build.return_value = mock_metadata_element
        
        # Mock ITI-41 client - use submit() method and proper response structure
        mock_iti41_instance = Mock()
        mock_iti41_client.return_value = mock_iti41_instance
        mock_iti41_response = Mock()
        mock_iti41_response.is_success = True
        mock_iti41_response.extracted_identifiers = {"document_ids": ["1.2.3.4.5"]}
        mock_iti41_response.error_messages = []
        mock_iti41_response.status_code = "Success"
        mock_iti41_instance.submit.return_value = mock_iti41_response
        
        # Create workflow and process patient
        workflow = IntegratedWorkflow(mock_config, Path("templates/ccd-template.xml"))
        result = workflow.process_patient(sample_patient, sample_saml_assertion)
        
        # Verify result
        assert result.patient_id == "PAT001"
        assert result.pix_add_status == "success"
        assert result.pix_enterprise_id == "EID123456"
        assert result.iti41_status == "success"
        assert result.document_id == "1.2.3.4.5"
        assert result.is_fully_successful is True
    
    @patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow')
    @patch('ihe_test_util.ihe_transactions.workflows.ITI41SOAPClient')
    @patch('ihe_test_util.ihe_transactions.workflows.TemplatePersonalizer')
    @patch('pathlib.Path.exists')
    def test_process_patient_pix_failure_skips_iti41(
        self,
        mock_exists,
        mock_personalizer,
        mock_iti41_client,
        mock_pix_workflow,
        mock_config,
        sample_patient,
        sample_saml_assertion,
    ):
        """Test that PIX Add failure skips ITI-41 submission."""
        mock_exists.return_value = True
        
        # Mock PIX Add workflow failure
        mock_pix_instance = Mock()
        mock_pix_workflow.return_value = mock_pix_instance
        mock_pix_result = PatientResult(
            patient_id="PAT001",
            pix_add_status=TransactionStatus.ERROR,
            pix_add_message="Duplicate patient identifier",
            processing_time_ms=150,
            error_details="Patient already exists"
        )
        mock_pix_instance.process_patient.return_value = mock_pix_result
        
        # Mock CCD personalizer
        mock_personalizer_instance = Mock()
        mock_personalizer.return_value = mock_personalizer_instance
        mock_personalizer_instance.personalize.return_value = "<ClinicalDocument>...</ClinicalDocument>"
        
        # Create workflow and process patient
        workflow = IntegratedWorkflow(mock_config, Path("templates/ccd-template.xml"))
        result = workflow.process_patient(sample_patient, sample_saml_assertion)
        
        # Verify result
        assert result.patient_id == "PAT001"
        assert result.pix_add_status == "failed"
        assert result.iti41_status == "skipped"
        assert "PIX Add failure" in result.iti41_message
        assert result.is_fully_successful is False
        
        # Verify ITI-41 client was never called
        mock_iti41_client.return_value.submit_document.assert_not_called()


class TestIntegratedWorkflowProcessBatch:
    """Test IntegratedWorkflow.process_batch method."""
    
    @patch('ihe_test_util.ihe_transactions.workflows.parse_csv')
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow._generate_saml_assertion')
    @patch('pathlib.Path.exists')
    def test_process_batch_maintains_order(
        self,
        mock_exists,
        mock_generate_saml,
        mock_process_patient,
        mock_parse_csv,
        mock_config,
        sample_saml_assertion,
        tmp_path
    ):
        """Test batch processing maintains patient order (AC: 4)."""
        mock_exists.return_value = True
        mock_generate_saml.return_value = sample_saml_assertion
        
        # Create test CSV data with 3 patients
        df = pd.DataFrame({
            'patient_id': ['PAT001', 'PAT002', 'PAT003'],
            'patient_id_oid': ['2.16.840.1'] * 3,
            'first_name': ['John', 'Jane', 'Bob'],
            'last_name': ['Doe', 'Smith', 'Johnson'],
            'dob': ['1980-01-01', '1985-05-15', '1990-10-20'],
            'gender': ['M', 'F', 'M']
        })
        mock_parse_csv.return_value = (df, None)
        
        # Track processing order
        processing_order = []
        
        def track_order(patient, saml_assertion=None, error_collector=None):
            processing_order.append(patient.patient_id)
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                iti41_status="success"
            )
        
        mock_process_patient.side_effect = track_order
        
        # Process batch
        workflow = IntegratedWorkflow(mock_config, Path("templates/ccd-template.xml"))
        csv_path = tmp_path / "patients.csv"
        result = workflow.process_batch(csv_path)
        
        # Verify order maintained
        assert processing_order == ['PAT001', 'PAT002', 'PAT003']
        assert result.total_patients == 3
    
    @patch('ihe_test_util.ihe_transactions.workflows.parse_csv')
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow._generate_saml_assertion')
    @patch('pathlib.Path.exists')
    def test_process_batch_continues_after_patient_failure(
        self,
        mock_exists,
        mock_generate_saml,
        mock_process_patient,
        mock_parse_csv,
        mock_config,
        sample_saml_assertion,
        tmp_path
    ):
        """Test batch continues processing after non-critical patient failure (AC: 6)."""
        mock_exists.return_value = True
        mock_generate_saml.return_value = sample_saml_assertion
        
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
        
        # Patient 2 fails PIX Add, others succeed
        def mixed_results(patient, saml_assertion=None, error_collector=None):
            if patient.patient_id == "PAT002":
                return PatientWorkflowResult(
                    patient_id=patient.patient_id,
                    pix_add_status="failed",
                    pix_add_message="Duplicate patient",
                    iti41_status="skipped"
                )
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                pix_enterprise_id=f"EID-{patient.patient_id}",
                iti41_status="success",
                document_id=f"DOC-{patient.patient_id}"
            )
        
        mock_process_patient.side_effect = mixed_results
        
        # Process batch
        workflow = IntegratedWorkflow(mock_config, Path("templates/ccd-template.xml"))
        csv_path = tmp_path / "patients.csv"
        result = workflow.process_batch(csv_path)
        
        # Verify all patients processed
        assert mock_process_patient.call_count == 3
        assert result.total_patients == 3
        assert result.fully_successful_count == 2
        assert result.pix_add_failed_count == 1
        assert result.iti41_skipped_count == 1


class TestGenerateIntegratedWorkflowSummary:
    """Test summary report generation."""
    
    def test_generate_summary_all_success(self):
        """Test summary generation with all patients successful."""
        result = BatchWorkflowResult(
            batch_id="batch-001",
            csv_file="patients.csv",
            ccd_template="template.xml",
            start_timestamp=datetime(2025, 11, 26, 10, 0, 0, tzinfo=timezone.utc),
            end_timestamp=datetime(2025, 11, 26, 10, 5, 0, tzinfo=timezone.utc),
            patient_results=[
                PatientWorkflowResult(
                    patient_id="PAT001",
                    pix_add_status="success",
                    pix_enterprise_id="EID001",
                    iti41_status="success",
                    document_id="DOC001"
                ),
                PatientWorkflowResult(
                    patient_id="PAT002",
                    pix_add_status="success",
                    pix_enterprise_id="EID002",
                    iti41_status="success",
                    document_id="DOC002"
                ),
            ]
        )
        
        summary = generate_integrated_workflow_summary(result)
        
        assert "INTEGRATED WORKFLOW SUMMARY" in summary
        assert "batch-001" in summary
        assert "Total Patients:" in summary
        assert "2" in summary  # Patient count
        assert "100.0%" in summary
    
    def test_generate_summary_partial_failure(self):
        """Test summary generation with failures."""
        result = BatchWorkflowResult(
            batch_id="batch-002",
            csv_file="patients.csv",
            ccd_template="template.xml",
            start_timestamp=datetime(2025, 11, 26, 10, 0, 0, tzinfo=timezone.utc),
            end_timestamp=datetime(2025, 11, 26, 10, 5, 0, tzinfo=timezone.utc),
            patient_results=[
                PatientWorkflowResult(
                    patient_id="PAT001",
                    pix_add_status="success",
                    pix_enterprise_id="EID001",
                    iti41_status="success",
                    document_id="DOC001"
                ),
                PatientWorkflowResult(
                    patient_id="PAT002",
                    pix_add_status="failed",
                    pix_add_message="Duplicate patient",
                    iti41_status="skipped"
                ),
                PatientWorkflowResult(
                    patient_id="PAT003",
                    pix_add_status="success",
                    pix_enterprise_id="EID003",
                    iti41_status="failed",
                    iti41_message="Repository error"
                ),
            ]
        )
        
        summary = generate_integrated_workflow_summary(result)
        
        assert "INTEGRATED WORKFLOW SUMMARY" in summary
        assert "Total Patients:" in summary
        assert "3" in summary  # Patient count
        assert "Failed:" in summary
        assert "Skipped:" in summary


class TestSaveWorkflowResultsToJson:
    """Test JSON output generation."""
    
    def test_save_workflow_results_creates_file(self, tmp_path):
        """Test that JSON output file is created with correct structure (AC: 7)."""
        result = BatchWorkflowResult(
            batch_id="batch-001",
            csv_file="patients.csv",
            ccd_template="template.xml",
            start_timestamp=datetime(2025, 11, 26, 10, 0, 0, tzinfo=timezone.utc),
            end_timestamp=datetime(2025, 11, 26, 10, 5, 0, tzinfo=timezone.utc),
            patient_results=[
                PatientWorkflowResult(
                    patient_id="PAT001",
                    pix_add_status="success",
                    pix_enterprise_id="EID001",
                    pix_enterprise_id_oid="1.2.3.4",
                    iti41_status="success",
                    document_id="DOC001"
                ),
                PatientWorkflowResult(
                    patient_id="PAT002",
                    pix_add_status="failed",
                    pix_add_message="Duplicate",
                    iti41_status="skipped"
                ),
            ]
        )
        
        output_path = tmp_path / "results.json"
        save_workflow_results_to_json(result, output_path)
        
        # Verify file created
        assert output_path.exists()
        
        # Verify content structure
        with output_path.open("r") as f:
            data = json.load(f)
        
        assert data["batch_id"] == "batch-001"
        assert data["csv_file"] == "patients.csv"
        assert data["ccd_template"] == "template.xml"
        assert "summary" in data
        assert data["summary"]["total_patients"] == 2
        assert data["summary"]["fully_successful"] == 1
        assert data["summary"]["pix_add_success"] == 1
        assert data["summary"]["iti41_success"] == 1
        
        # Verify patient results
        assert len(data["patients"]) == 2
        assert data["patients"][0]["patient_id"] == "PAT001"
        assert data["patients"][0]["pix_add"]["status"] == "success"
        assert data["patients"][0]["pix_add"]["enterprise_id"] == "EID001"
        assert data["patients"][0]["iti41"]["status"] == "success"
        assert data["patients"][0]["iti41"]["document_id"] == "DOC001"
        
        assert data["patients"][1]["patient_id"] == "PAT002"
        assert data["patients"][1]["pix_add"]["status"] == "failed"
        assert data["patients"][1]["iti41"]["status"] == "skipped"
    
    def test_save_workflow_results_creates_directories(self, tmp_path):
        """Test that JSON output creates parent directories if needed."""
        result = BatchWorkflowResult(
            batch_id="batch-001",
            csv_file="patients.csv",
            ccd_template="template.xml",
            start_timestamp=datetime.now(timezone.utc),
            patient_results=[]
        )
        
        output_path = tmp_path / "subdir" / "nested" / "results.json"
        save_workflow_results_to_json(result, output_path)
        
        assert output_path.exists()
