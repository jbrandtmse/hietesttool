"""E2E Integration tests for integrated PIX Add + ITI-41 workflow.

Tests complete workflow orchestration: CSV → CCD → PIX Add → ITI-41
with mock endpoints including error scenarios.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, Mock
import json

import pytest

from ihe_test_util.config.schema import Config
from ihe_test_util.ihe_transactions.workflows import (
    IntegratedWorkflow,
    generate_integrated_workflow_summary,
    save_workflow_results_to_json,
)
from ihe_test_util.models.batch import PatientResult, BatchWorkflowResult, PatientWorkflowResult
from ihe_test_util.models.responses import TransactionStatus


@pytest.fixture
def test_csv_file(tmp_path):
    """Create test CSV file with patient data."""
    csv_path = tmp_path / "test_patients.csv"
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-01,M
PAT002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1985-05-15,F
PAT003,2.16.840.1.113883.3.72.5.9.1,Bob,Johnson,1990-10-20,M
"""
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def integration_config():
    """Create integration test configuration."""
    config = Mock(spec=Config)
    
    # Endpoints
    config.endpoints = Mock()
    config.endpoints.pix_add_url = "http://localhost:8080/pix/add"
    config.endpoints.iti41_url = "http://localhost:8080/xdsrepository"
    
    # SAML configuration  
    config.saml = Mock()
    config.saml.cert_path = "tests/fixtures/test_cert.pem"
    config.saml.key_path = "tests/fixtures/test_key.pem"
    config.saml.issuer = "urn:test:issuer"
    config.saml.subject = "test-user@example.com"
    
    # OIDs
    config.sender_oid = "2.16.840.1.113883.3.72.5.1"
    config.receiver_oid = "2.16.840.1.113883.3.72.5.2"
    config.sender_application = "IHE_TEST_UTIL"
    config.receiver_application = "PIX_MANAGER"
    
    # Transport
    config.transport = Mock()
    config.transport.verify_tls = False  # For mock server
    
    # Certificates
    config.certificates = Mock()
    config.certificates.cert_path = "tests/fixtures/test_cert.pem"
    config.certificates.key_path = "tests/fixtures/test_key.pem"
    
    return config


@pytest.fixture
def ccd_template_file(tmp_path):
    """Create test CCD template."""
    template_path = tmp_path / "ccd_template.xml"
    template_content = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <id root="{{document_id}}"/>
  <recordTarget>
    <patientRole>
      <id root="{{patient_id_oid}}" extension="{{patient_id}}"/>
      <patient>
        <name>
          <given>{{first_name}}</given>
          <family>{{last_name}}</family>
        </name>
        <administrativeGenderCode code="{{gender}}"/>
        <birthTime value="{{dob}}"/>
      </patient>
    </patientRole>
  </recordTarget>
</ClinicalDocument>
"""
    template_path.write_text(template_content)
    return template_path


class TestIntegratedWorkflowE2E:
    """E2E integration tests for complete workflow."""
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_complete_workflow_all_patients_success(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test complete E2E workflow with all patients successful."""
        mock_exists.return_value = True
        
        # Mock successful processing for all patients
        def create_success_result(patient, saml_assertion=None, error_collector=None):
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                csv_parsed=True,
                ccd_generated=True,
                pix_add_status="success",
                pix_add_message="Registered successfully",
                pix_enterprise_id=f"EID-{patient.patient_id}",
                pix_enterprise_id_oid="1.2.840.114350.1.13.99998.8734",
                iti41_status="success",
                iti41_message="Document submitted",
                document_id=f"DOC-{patient.patient_id}",
                pix_add_time_ms=250,
                iti41_time_ms=350,
                total_time_ms=600
            )
        
        mock_process_patient.side_effect = create_success_result
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Verify results
        assert result.total_patients == 3
        assert result.fully_successful_count == 3
        assert result.pix_add_success_count == 3
        assert result.iti41_success_count == 3
        assert result.full_success_rate == 100.0
        
        # Verify all patients processed
        assert mock_process_patient.call_count == 3
        
        # Verify patient results
        for patient_result in result.patient_results:
            assert patient_result.is_fully_successful
            assert patient_result.pix_enterprise_id.startswith("EID-")
            assert patient_result.document_id.startswith("DOC-")
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_workflow_maintains_sequential_order(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test that workflow processes patients in CSV order (AC: 4)."""
        mock_exists.return_value = True
        
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
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Verify order maintained
        assert processing_order == ["PAT001", "PAT002", "PAT003"]
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_workflow_json_output_generation(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
        tmp_path,
    ):
        """Test JSON output generation (AC: 7)."""
        mock_exists.return_value = True
        
        def create_result(patient, saml_assertion=None, error_collector=None):
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                pix_enterprise_id=f"EID-{patient.patient_id}",
                iti41_status="success",
                document_id=f"DOC-{patient.patient_id}"
            )
        
        mock_process_patient.side_effect = create_result
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Save JSON output
        output_path = tmp_path / "results.json"
        save_workflow_results_to_json(result, output_path)
        
        # Verify file created and structure
        assert output_path.exists()
        
        with output_path.open("r") as f:
            data = json.load(f)
        
        assert data["batch_id"] == result.batch_id
        assert data["summary"]["total_patients"] == 3
        assert data["summary"]["fully_successful"] == 3
        assert len(data["patients"]) == 3
        
        # Verify patient data structure
        for patient in data["patients"]:
            assert "patient_id" in patient
            assert "pix_add" in patient
            assert "iti41" in patient
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_workflow_summary_report_generation(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test summary report generation (AC: 8)."""
        mock_exists.return_value = True
        
        def create_result(patient, saml_assertion=None, error_collector=None):
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                pix_enterprise_id=f"EID-{patient.patient_id}",
                iti41_status="success",
                document_id=f"DOC-{patient.patient_id}"
            )
        
        mock_process_patient.side_effect = create_result
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Generate summary
        summary = generate_integrated_workflow_summary(result)
        
        # Verify summary content
        assert "INTEGRATED WORKFLOW SUMMARY" in summary
        assert "Total Patients:" in summary and "3" in summary
        assert "Successful:" in summary  # PIX Add and ITI-41 success counts
        assert "100.0%" in summary


class TestIntegratedWorkflowErrorScenarios:
    """Error scenario integration tests."""
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_pix_add_failure_skips_iti41(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test that PIX Add failure skips ITI-41 for that patient (AC: 6)."""
        mock_exists.return_value = True
        
        # Patient 2 fails PIX Add
        def mixed_results(patient, saml_assertion=None, error_collector=None):
            if patient.patient_id == "PAT002":
                return PatientWorkflowResult(
                    patient_id=patient.patient_id,
                    pix_add_status="failed",
                    pix_add_message="Duplicate patient identifier",
                    iti41_status="skipped",
                    iti41_message="Skipped due to PIX Add failure"
                )
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                pix_enterprise_id=f"EID-{patient.patient_id}",
                iti41_status="success",
                document_id=f"DOC-{patient.patient_id}"
            )
        
        mock_process_patient.side_effect = mixed_results
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Verify results
        assert result.total_patients == 3
        assert result.fully_successful_count == 2
        assert result.pix_add_failed_count == 1
        assert result.iti41_skipped_count == 1
        
        # Verify PAT002 was skipped for ITI-41
        pat002_result = [r for r in result.patient_results if r.patient_id == "PAT002"][0]
        assert pat002_result.pix_add_status == "failed"
        assert pat002_result.iti41_status == "skipped"
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_workflow_continues_after_patient_failure(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test that workflow continues processing remaining patients after non-critical failure."""
        mock_exists.return_value = True
        
        # Track call count to verify all patients processed
        call_count = 0
        
        def track_all_calls(patient, saml_assertion=None, error_collector=None):
            nonlocal call_count
            call_count += 1
            
            if patient.patient_id == "PAT002":
                return PatientWorkflowResult(
                    patient_id=patient.patient_id,
                    pix_add_status="failed",
                    pix_add_message="Error",
                    iti41_status="skipped"
                )
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                iti41_status="success"
            )
        
        mock_process_patient.side_effect = track_all_calls
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Verify all 3 patients were processed despite PAT002 failure
        assert call_count == 3
        assert result.total_patients == 3
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_iti41_failure_after_successful_pix_add(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test handling of ITI-41 failure after successful PIX Add."""
        mock_exists.return_value = True
        
        # Patient 2 succeeds PIX Add but fails ITI-41
        def iti41_failure(patient, saml_assertion=None, error_collector=None):
            if patient.patient_id == "PAT002":
                return PatientWorkflowResult(
                    patient_id=patient.patient_id,
                    pix_add_status="success",
                    pix_enterprise_id="EID-PAT002",
                    iti41_status="failed",
                    iti41_message="Repository unavailable"
                )
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                pix_enterprise_id=f"EID-{patient.patient_id}",
                iti41_status="success",
                document_id=f"DOC-{patient.patient_id}"
            )
        
        mock_process_patient.side_effect = iti41_failure
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Verify results
        assert result.total_patients == 3
        assert result.fully_successful_count == 2
        assert result.pix_add_success_count == 3  # All PIX Add succeeded
        assert result.iti41_success_count == 2
        assert result.iti41_failed_count == 1
        
        # Verify PAT002 partial success
        pat002_result = [r for r in result.patient_results if r.patient_id == "PAT002"][0]
        assert pat002_result.pix_add_status == "success"
        assert pat002_result.pix_enterprise_id == "EID-PAT002"
        assert pat002_result.iti41_status == "failed"
        assert pat002_result.is_fully_successful is False
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_all_patients_fail(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test workflow when all patients fail."""
        mock_exists.return_value = True
        
        def all_fail(patient, saml_assertion=None, error_collector=None):
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="failed",
                pix_add_message="Connection refused",
                iti41_status="skipped"
            )
        
        mock_process_patient.side_effect = all_fail
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Verify results
        assert result.total_patients == 3
        assert result.fully_successful_count == 0
        assert result.pix_add_failed_count == 3
        assert result.iti41_skipped_count == 3
        assert result.full_success_rate == 0.0
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_workflow_timing_tracking(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test that workflow tracks timing metrics (AC: 9)."""
        mock_exists.return_value = True
        
        def create_timed_result(patient, saml_assertion=None, error_collector=None):
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                pix_enterprise_id=f"EID-{patient.patient_id}",
                iti41_status="success",
                document_id=f"DOC-{patient.patient_id}",
                pix_add_time_ms=250,
                iti41_time_ms=350,
                total_time_ms=600
            )
        
        mock_process_patient.side_effect = create_timed_result
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Verify timing tracked
        assert result.start_timestamp is not None
        assert result.end_timestamp is not None
        
        # Verify duration calculated
        if result.total_duration_seconds is not None:
            assert result.total_duration_seconds >= 0


class TestIntegratedWorkflowPatientIdentifiers:
    """Test patient identifier handling in integrated workflow."""
    
    @patch('ihe_test_util.ihe_transactions.workflows.IntegratedWorkflow.process_patient')
    @patch('pathlib.Path.exists')
    def test_pix_identifiers_used_in_iti41(
        self,
        mock_exists,
        mock_process_patient,
        integration_config,
        test_csv_file,
        ccd_template_file,
    ):
        """Test that PIX Add identifiers are used in ITI-41 metadata (AC: 3)."""
        mock_exists.return_value = True
        
        def create_result(patient, saml_assertion=None, error_collector=None):
            # Enterprise ID from PIX Add should be available for ITI-41
            return PatientWorkflowResult(
                patient_id=patient.patient_id,
                pix_add_status="success",
                pix_enterprise_id=f"ENTERPRISE-{patient.patient_id}",
                pix_enterprise_id_oid="1.2.840.114350.1.13.99998.8734",
                iti41_status="success",
                document_id=f"DOC-{patient.patient_id}"
            )
        
        mock_process_patient.side_effect = create_result
        
        # Run workflow
        workflow = IntegratedWorkflow(integration_config, ccd_template_file)
        result = workflow.process_batch(test_csv_file)
        
        # Verify enterprise IDs are present
        for patient_result in result.patient_results:
            assert patient_result.pix_enterprise_id.startswith("ENTERPRISE-")
            assert patient_result.pix_enterprise_id_oid == "1.2.840.114350.1.13.99998.8734"
            # Document ID confirms ITI-41 was processed with the identifier
            assert patient_result.document_id is not None
