"""Integration tests for PIX Add workflow with mock server.

Tests complete workflow orchestration against mock PIX Add endpoint including
SOAP communication, acknowledgment parsing, and error handling.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock
import tempfile

import pytest

from ihe_test_util.config.schema import Config
from ihe_test_util.ihe_transactions.workflows import (
    PIXAddWorkflow,
    save_registered_identifiers,
    generate_summary_report
)
from ihe_test_util.models.responses import TransactionStatus


@pytest.fixture
def test_csv_file(tmp_path):
    """Create test CSV file with patient data."""
    csv_path = tmp_path / "test_patients.csv"
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-01,M
PAT002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1985-05-15,F
PAT003,2.16.840.1.113883.3.72.5.9.1,Bob,Johnson,1990-10-20,M
PAT004,2.16.840.1.113883.3.72.5.9.1,Alice,Williams,1975-03-08,F
PAT005,2.16.840.1.113883.3.72.5.9.1,Charlie,Brown,1988-12-25,O
"""
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def integration_config(tmp_path):
    """Create integration test configuration."""
    config = Mock(spec=Config)
    
    # Endpoints
    config.endpoints = Mock()
    config.endpoints.pix_add_url = "http://localhost:8080/pix/add"
    
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
    
    return config


@patch('ihe_test_util.ihe_transactions.workflows.PIXAddSOAPClient')
@patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow._generate_saml_assertion')
@patch('pathlib.Path.exists')
def test_complete_workflow_single_patient_mock_endpoint(
    mock_exists,
    mock_generate_saml,
    mock_soap_client_class,
    integration_config,
    tmp_path
):
    """Test complete workflow with single patient against mock endpoint."""
    # Setup mocks
    mock_exists.return_value = True
    
    # Mock SAML assertion
    mock_saml = Mock()
    mock_saml.xml_content = "<saml:Assertion>...</saml:Assertion>"
    mock_saml.signature = "<ds:Signature>...</ds:Signature>"
    mock_generate_saml.return_value = mock_saml
    
    # Mock SOAP client
    mock_soap_client = Mock()
    mock_soap_response = Mock()
    mock_soap_response.is_success = True
    mock_soap_response.status = TransactionStatus.SUCCESS
    mock_soap_response.status_code = "AA"
    mock_soap_response.extracted_identifiers = {
        "patient_id": "EID123456",
        "patient_id_root": "1.2.840.114350.1.13.99998.8734"
    }
    mock_soap_response.error_messages = []
    mock_soap_response.processing_time_ms = 250
    
    mock_soap_client.submit_pix_add.return_value = mock_soap_response
    mock_soap_client_class.return_value = mock_soap_client
    
    # Create single patient CSV
    csv_path = tmp_path / "single_patient.csv"
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-01,M
"""
    csv_path.write_text(csv_content)
    
    # Run workflow
    workflow = PIXAddWorkflow(integration_config)
    result = workflow.process_batch(csv_path)
    
    # Verify results
    assert result.total_patients == 1
    assert result.successful_patients == 1
    assert result.failed_patients == 0
    assert result.success_rate == 100.0
    assert len(result.patient_results) == 1
    
    patient_result = result.patient_results[0]
    assert patient_result.patient_id == "PAT001"
    assert patient_result.is_success
    assert patient_result.enterprise_id == "EID123456"


@patch('ihe_test_util.ihe_transactions.workflows.PIXAddSOAPClient')
@patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow._generate_saml_assertion')
@patch('pathlib.Path.exists')
def test_complete_workflow_multiple_patients_mock_endpoint(
    mock_exists,
    mock_generate_saml,
    mock_soap_client_class,
    integration_config,
    test_csv_file
):
    """Test complete workflow with multiple patients against mock endpoint."""
    # Setup mocks
    mock_exists.return_value = True
    
    # Mock SAML assertion
    mock_saml = Mock()
    mock_saml.xml_content = "<saml:Assertion>...</saml:Assertion>"
    mock_saml.signature = "<ds:Signature>...</ds:Signature>"
    mock_generate_saml.return_value = mock_saml
    
    # Mock SOAP client with sequential responses
    mock_soap_client = Mock()
    
    def mock_submit(message, saml):
        # Extract patient ID from message to generate unique enterprise ID
        import re
        match = re.search(r'PAT\d+', message)
        patient_id = match.group(0) if match else "UNKNOWN"
        
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.status = TransactionStatus.SUCCESS
        mock_response.status_code = "AA"
        mock_response.extracted_identifiers = {
            "patient_id": f"EID-{patient_id}",
            "patient_id_root": "1.2.840.114350.1.13.99998.8734"
        }
        mock_response.error_messages = []
        mock_response.processing_time_ms = 250
        return mock_response
    
    mock_soap_client.submit_pix_add.side_effect = mock_submit
    mock_soap_client_class.return_value = mock_soap_client
    
    # Run workflow
    workflow = PIXAddWorkflow(integration_config)
    result = workflow.process_batch(test_csv_file)
    
    # Verify results
    assert result.total_patients == 5
    assert result.successful_patients == 5
    assert result.failed_patients == 0
    assert result.success_rate == 100.0
    assert len(result.patient_results) == 5
    
    # Verify sequential processing
    assert mock_soap_client.submit_pix_add.call_count == 5
    
    # Verify all patients have enterprise IDs
    for patient_result in result.patient_results:
        assert patient_result.is_success
        assert patient_result.enterprise_id is not None
        assert patient_result.enterprise_id.startswith("EID-")


@patch('ihe_test_util.ihe_transactions.workflows.PIXAddSOAPClient')
@patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow._generate_saml_assertion')
@patch('pathlib.Path.exists')
def test_workflow_with_mock_endpoint_failures(
    mock_exists,
    mock_generate_saml,
    mock_soap_client_class,
    integration_config,
    tmp_path
):
    """Test workflow with mock endpoint returning AE for some patients."""
    # Setup mocks
    mock_exists.return_value = True
    
    # Mock SAML assertion
    mock_saml = Mock()
    mock_saml.xml_content = "<saml:Assertion>...</saml:Assertion>"
    mock_saml.signature = "<ds:Signature>...</ds:Signature>"
    mock_generate_saml.return_value = mock_saml
    
    # Mock SOAP client with mixed responses
    mock_soap_client = Mock()
    
    call_count = 0
    def mock_submit_with_failure(message, saml):
        nonlocal call_count
        call_count += 1
        
        mock_response = Mock()
        
        # Second patient fails (PAT002)
        if call_count == 2:
            mock_response.is_success = False
            mock_response.status = TransactionStatus.ERROR
            mock_response.status_code = "AE"
            mock_response.extracted_identifiers = {}
            mock_response.error_messages = ["Duplicate patient identifier"]
            mock_response.processing_time_ms = 150
        else:
            mock_response.is_success = True
            mock_response.status = TransactionStatus.SUCCESS
            mock_response.status_code = "AA"
            mock_response.extracted_identifiers = {
                "patient_id": f"EID-{call_count}",
                "patient_id_root": "1.2.840.114350.1.13.99998.8734"
            }
            mock_response.error_messages = []
            mock_response.processing_time_ms = 250
        
        return mock_response
    
    mock_soap_client.submit_pix_add.side_effect = mock_submit_with_failure
    mock_soap_client_class.return_value = mock_soap_client
    
    # Create CSV with 3 patients
    csv_path = tmp_path / "patients.csv"
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-01,M
PAT002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1985-05-15,F
PAT003,2.16.840.1.113883.3.72.5.9.1,Bob,Johnson,1990-10-20,M
"""
    csv_path.write_text(csv_content)
    
    # Run workflow
    workflow = PIXAddWorkflow(integration_config)
    result = workflow.process_batch(csv_path)
    
    # Verify results
    assert result.total_patients == 3
    assert result.successful_patients == 2
    assert result.failed_patients == 1
    
    # Verify workflow continued after failure
    assert mock_soap_client.submit_pix_add.call_count == 3
    
    # Verify failed patient
    failed_patient = [r for r in result.patient_results if not r.is_success][0]
    assert failed_patient.patient_id == "PAT002"
    assert "Duplicate" in failed_patient.pix_add_message


@patch('ihe_test_util.ihe_transactions.workflows.PIXAddSOAPClient')
@patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow._generate_saml_assertion')
@patch('pathlib.Path.exists')
def test_workflow_output_file_generation(
    mock_exists,
    mock_generate_saml,
    mock_soap_client_class,
    integration_config,
    tmp_path
):
    """Test registered identifiers output file generation."""
    # Setup mocks
    mock_exists.return_value = True
    
    # Mock SAML assertion
    mock_saml = Mock()
    mock_generate_saml.return_value = mock_saml
    
    # Mock SOAP client
    mock_soap_client = Mock()
    mock_response = Mock()
    mock_response.is_success = True
    mock_response.status = TransactionStatus.SUCCESS
    mock_response.status_code = "AA"
    mock_response.extracted_identifiers = {
        "patient_id": "EID123456",
        "patient_id_root": "1.2.840.114350.1.13.99998.8734"
    }
    mock_response.error_messages = []
    mock_response.processing_time_ms = 250
    
    mock_soap_client.submit_pix_add.return_value = mock_response
    mock_soap_client_class.return_value = mock_soap_client
    
    # Create CSV
    csv_path = tmp_path / "patients.csv"
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-01,M
PAT002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1985-05-15,F
"""
    csv_path.write_text(csv_content)
    
    # Run workflow
    workflow = PIXAddWorkflow(integration_config)
    result = workflow.process_batch(csv_path)
    
    # Save identifiers
    output_path = tmp_path / "registered.json"
    save_registered_identifiers(result, output_path)
    
    # Verify file created
    assert output_path.exists()
    
    # Verify content
    import json
    with output_path.open("r") as f:
        data = json.load(f)
    
    assert data["total_registered"] == 2
    assert len(data["patients"]) == 2


@patch('ihe_test_util.ihe_transactions.workflows.PIXAddSOAPClient')
@patch('ihe_test_util.ihe_transactions.workflows.PIXAddWorkflow._generate_saml_assertion')
@patch('pathlib.Path.exists')
def test_workflow_summary_report_generation(
    mock_exists,
    mock_generate_saml,
    mock_soap_client_class,
    integration_config,
    tmp_path
):
    """Test summary report generation."""
    # Setup mocks
    mock_exists.return_value = True
    
    # Mock SAML assertion
    mock_saml = Mock()
    mock_generate_saml.return_value = mock_saml
    
    # Mock SOAP client
    mock_soap_client = Mock()
    mock_response = Mock()
    mock_response.is_success = True
    mock_response.status = TransactionStatus.SUCCESS
    mock_response.status_code = "AA"
    mock_response.extracted_identifiers = {
        "patient_id": "EID123456",
        "patient_id_root": "1.2.840.114350.1.13.99998.8734"
    }
    mock_response.error_messages = []
    mock_response.processing_time_ms = 250
    
    mock_soap_client.submit_pix_add.return_value = mock_response
    mock_soap_client_class.return_value = mock_soap_client
    
    # Create CSV
    csv_path = tmp_path / "patients.csv"
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-01,M
PAT002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1985-05-15,F
"""
    csv_path.write_text(csv_content)
    
    # Run workflow
    workflow = PIXAddWorkflow(integration_config)
    result = workflow.process_batch(csv_path)
    
    # Generate report
    report = generate_summary_report(result)
    
    # Verify report content
    assert "PIX ADD WORKFLOW SUMMARY" in report
    assert "Total Patients:       2" in report
    assert "✓ Successful:         2" in report
    assert "SUCCESSFUL REGISTRATIONS" in report
    assert "PAT001" in report
    assert "PAT002" in report
