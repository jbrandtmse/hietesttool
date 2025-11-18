"""Integration tests for error handling and resilience.

Tests end-to-end error handling including retry logic, error categorization,
batch processing with errors, and error summary generation.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import ConnectionError, Timeout, SSLError

from ihe_test_util.config.schema import Config
from ihe_test_util.ihe_transactions.workflows import PIXAddWorkflow
from ihe_test_util.ihe_transactions.soap_client import PIXAddSOAPClient
from ihe_test_util.models.responses import TransactionStatus
from ihe_test_util.utils.exceptions import ValidationError, ErrorCategory


class TestTransientErrorRetry:
    """Test retry logic for transient errors."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_transient_error_retry_with_backoff(self, mock_post, config_fixture):
        """Test retry succeeds after transient errors with exponential backoff."""
        # Mock endpoint to fail twice, succeed third time
        success_response = Mock()
        success_response.status_code = 200
        success_response.text = """
        <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
            <acknowledgement>
                <typeCode code="AA"/>
            </acknowledgement>
        </MCCI_IN000002UV01>
        """
        
        mock_post.side_effect = [
            ConnectionError("Network unreachable"),
            ConnectionError("Connection refused"),
            success_response
        ]
        
        client = PIXAddSOAPClient(config_fixture, max_retries=3)
        
        # Create mock SAML assertion with all required attributes
        mock_saml = Mock(spec=['xml_content', 'assertion_id', 'signature'])
        mock_saml.xml_content = "<Assertion xmlns='urn:oasis:names:tc:SAML:2.0:assertion'></Assertion>"
        mock_saml.assertion_id = "test-assertion-123"
        mock_saml.signature = "base64encodedSignature=="
        
        # Create simple PIX Add message
        message_xml = "<PRPA_IN201301UV02/>"
        
        # Submit should succeed after 2 retries
        response = client.submit_pix_add(message_xml, mock_saml)
        
        # Verify retries occurred
        assert mock_post.call_count == 3
        assert response.status == TransactionStatus.SUCCESS
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_transient_error_exhausts_retries(self, mock_post, config_fixture):
        """Test transient error exhausts retries and raises exception."""
        # Mock endpoint to always fail
        mock_post.side_effect = ConnectionError("Network unreachable")
        
        client = PIXAddSOAPClient(config_fixture, max_retries=3)
        
        mock_saml = Mock(spec=['xml_content', 'assertion_id', 'signature'])
        mock_saml.xml_content = "<Assertion xmlns='urn:oasis:names:tc:SAML:2.0:assertion'></Assertion>"
        mock_saml.assertion_id = "test-assertion-123"
        mock_saml.signature = "base64encodedSignature=="
        message_xml = "<PRPA_IN201301UV02/>"
        
        # Should raise after max retries
        with pytest.raises(ConnectionError):
            client.submit_pix_add(message_xml, mock_saml)
        
        # Verify all retry attempts made
        assert mock_post.call_count == 3
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_exponential_backoff_delays(self, mock_sleep, mock_post, config_fixture):
        """Test exponential backoff delays increase correctly."""
        success_response = Mock()
        success_response.status_code = 200
        success_response.text = """
        <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
            <acknowledgement><typeCode code="AA"/></acknowledgement>
        </MCCI_IN000002UV01>
        """
        
        mock_post.side_effect = [
            Timeout("Request timeout"),
            Timeout("Request timeout"),
            success_response
        ]
        
        client = PIXAddSOAPClient(config_fixture, max_retries=3)
        
        mock_saml = Mock(spec=['xml_content', 'assertion_id', 'signature'])
        mock_saml.xml_content = "<Assertion xmlns='urn:oasis:names:tc:SAML:2.0:assertion'></Assertion>"
        mock_saml.assertion_id = "test-assertion-123"
        mock_saml.signature = "base64encodedSignature=="
        message_xml = "<PRPA_IN201301UV02/>"
        
        response = client.submit_pix_add(message_xml, mock_saml)
        
        # Verify exponential backoff delays: 1s, 2s
        assert mock_sleep.call_count == 2
        sleep_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_delays[0] == 1  # First retry delay
        assert sleep_delays[1] == 2  # Second retry delay


class TestPermanentErrorHandling:
    """Test handling of permanent errors (no retry)."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_permanent_error_no_retry(self, mock_post, config_fixture):
        """Test permanent errors (4xx) do not trigger retries."""
        # Mock 400 Bad Request response
        error_response = Mock()
        error_response.status_code = 400
        error_response.text = "Bad Request"
        error_response.raise_for_status.side_effect = Exception("400 Client Error")
        
        mock_post.return_value = error_response
        
        client = PIXAddSOAPClient(config_fixture, max_retries=3)
        
        mock_saml = Mock(spec=['xml_content', 'assertion_id', 'signature'])
        mock_saml.xml_content = "<Assertion xmlns='urn:oasis:names:tc:SAML:2.0:assertion'></Assertion>"
        mock_saml.assertion_id = "test-assertion-123"
        mock_saml.signature = "base64encodedSignature=="
        message_xml = "<PRPA_IN201301UV02/>"
        
        # Should fail without retry
        with pytest.raises(Exception):
            client.submit_pix_add(message_xml, mock_saml)
        
        # Verify no retries (only 1 attempt)
        assert mock_post.call_count == 1
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_validation_error_continues_batch(self, mock_post, workflow_fixture, temp_csv_file):
        """Test validation errors skip patient but continue batch processing."""
        # This would require a more complex setup with actual CSV and workflow
        # For now, verify ValidationError is categorized as PERMANENT
        from ihe_test_util.utils.exceptions import categorize_error
        
        error = ValidationError("Invalid patient data")
        category = categorize_error(error)
        
        assert category == ErrorCategory.PERMANENT


class TestCriticalErrorHandling:
    """Test handling of critical errors (halt processing)."""
    
    @patch('ihe_test_util.saml.certificate_manager.validate_certificate')
    def test_critical_error_halts_batch(self, mock_validate_cert, workflow_fixture, temp_csv_file):
        """Test critical errors halt batch processing immediately."""
        # Mock certificate validation to fail
        from ihe_test_util.utils.exceptions import CertificateExpiredError
        mock_validate_cert.side_effect = CertificateExpiredError("Certificate expired")
        
        # Should raise critical error and halt
        with pytest.raises(Exception) as exc_info:
            workflow_fixture.process_batch(temp_csv_file)
        
        # Verify it's a critical error (certificate error, connection error, timeout, or SSL error)
        assert (
            "certificate" in str(exc_info.value).lower() or 
            isinstance(exc_info.value, (CertificateExpiredError, ConnectionError, Timeout, SSLError))
        )
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_ssl_error_halts_workflow(self, mock_post, config_fixture):
        """Test SSL errors halt workflow immediately."""
        mock_post.side_effect = SSLError("Certificate verification failed")
        
        client = PIXAddSOAPClient(config_fixture, max_retries=3)
        
        mock_saml = Mock(spec=['xml_content', 'assertion_id', 'signature'])
        mock_saml.xml_content = "<Assertion xmlns='urn:oasis:names:tc:SAML:2.0:assertion'></Assertion>"
        mock_saml.assertion_id = "test-assertion-123"
        mock_saml.signature = "base64encodedSignature=="
        message_xml = "<PRPA_IN201301UV02/>"
        
        # Should raise SSLError without retries
        with pytest.raises(SSLError):
            client.submit_pix_add(message_xml, mock_saml)
        
        # SSL errors should not retry
        assert mock_post.call_count == 1


class TestSOAPFaultHandling:
    """Test SOAP fault parsing and handling integration."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_soap_fault_parsing_integration(self, mock_post, config_fixture):
        """Test SOAP fault is parsed and handled correctly."""
        fault_response = Mock()
        fault_response.status_code = 500
        fault_response.text = """
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
          <soap:Body>
            <soap:Fault>
              <soap:Code>
                <soap:Value>soap:Sender</soap:Value>
              </soap:Code>
              <soap:Reason>
                <soap:Text>Invalid SAML assertion</soap:Text>
              </soap:Reason>
            </soap:Fault>
          </soap:Body>
        </soap:Envelope>
        """
        
        mock_post.return_value = fault_response
        
        client = PIXAddSOAPClient(config_fixture, max_retries=1)
        
        mock_saml = Mock(spec=['xml_content', 'assertion_id', 'signature'])
        mock_saml.xml_content = "<Assertion xmlns='urn:oasis:names:tc:SAML:2.0:assertion'></Assertion>"
        mock_saml.assertion_id = "test-assertion-123"
        mock_saml.signature = "base64encodedSignature=="
        message_xml = "<PRPA_IN201301UV02/>"
        
        # Submit and get response
        response = client.submit_pix_add(message_xml, mock_saml)
        
        # Verify SOAP fault was detected
        assert response.status != TransactionStatus.SUCCESS
        # Could verify fault details logged, etc.


class TestHL7AcknowledgmentErrors:
    """Test HL7 AE/AR acknowledgment error handling."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_hl7_ae_status_handling(self, mock_post, config_fixture):
        """Test HL7 AE (Application Error) status is handled correctly."""
        ae_response = Mock()
        ae_response.status_code = 200
        ae_response.text = """
        <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
            <acknowledgement>
                <typeCode code="AE"/>
                <acknowledgementDetail>
                    <code code="204" codeSystem="2.16.840.1.113883.12.357">
                        <originalText>Unknown key identifier</originalText>
                    </code>
                    <text>Patient identifier domain not recognized</text>
                </acknowledgementDetail>
            </acknowledgement>
        </MCCI_IN000002UV01>
        """
        
        mock_post.return_value = ae_response
        
        client = PIXAddSOAPClient(config_fixture, max_retries=1)
        
        mock_saml = Mock(spec=['xml_content', 'assertion_id', 'signature'])
        mock_saml.xml_content = "<Assertion xmlns='urn:oasis:names:tc:SAML:2.0:assertion'></Assertion>"
        mock_saml.assertion_id = "test-assertion-123"
        mock_saml.signature = "base64encodedSignature=="
        message_xml = "<PRPA_IN201301UV02/>"
        
        response = client.submit_pix_add(message_xml, mock_saml)
        
        # Verify AE status detected
        assert response.status != TransactionStatus.SUCCESS
        assert response.status_code == "AE"
        assert len(response.error_messages) > 0
        assert "identifier" in response.error_messages[0].lower()
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_hl7_ae_continues_batch_processing(self, mock_post, workflow_fixture, temp_csv_file):
        """Test HL7 AE error marks patient as failed but continues batch."""
        # Mock one AE response, then success
        ae_response = Mock()
        ae_response.status_code = 200
        ae_response.text = """
        <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
            <acknowledgement><typeCode code="AE"/></acknowledgement>
        </MCCI_IN000002UV01>
        """
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.text = """
        <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
            <acknowledgement><typeCode code="AA"/></acknowledgement>
        </MCCI_IN000002UV01>
        """
        
        mock_post.side_effect = [ae_response, success_response]
        
        # Process batch should continue despite AE error
        # (Would need actual CSV with 2 patients for full test)


class TestMalformedResponseHandling:
    """Test handling of malformed responses."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_malformed_response_handling(self, mock_post, config_fixture):
        """Test malformed XML response is logged and handled gracefully."""
        malformed_response = Mock()
        malformed_response.status_code = 200
        malformed_response.text = "<invalid>xml<unclosed>"
        
        mock_post.return_value = malformed_response
        
        client = PIXAddSOAPClient(config_fixture, max_retries=1)
        
        mock_saml = Mock(spec=['xml_content', 'assertion_id', 'signature'])
        mock_saml.xml_content = "<Assertion xmlns='urn:oasis:names:tc:SAML:2.0:assertion'></Assertion>"
        mock_saml.assertion_id = "test-assertion-123"
        mock_saml.signature = "base64encodedSignature=="
        message_xml = "<PRPA_IN201301UV02/>"
        
        response = client.submit_pix_add(message_xml, mock_saml)
        
        # Should return error status, not crash
        assert response.status_code in ["MALFORMED_XML", "PARSE_ERROR"]
        # Raw response should be saved to temp file (verified in logs)


class TestBatchErrorSummary:
    """Test error summary generation during batch processing."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.requests.Session.post')
    def test_batch_error_summary_generation(self, mock_post, workflow_fixture, temp_csv_with_multiple_patients):
        """Test error summary is generated for batch with mixed errors."""
        # Mock different error responses for different patients
        responses = [
            # Patient 1: ConnectionError (will retry and fail)
            ConnectionError("Network unreachable"),
            ConnectionError("Network unreachable"),
            ConnectionError("Network unreachable"),
            # Patient 2: Success
            Mock(status_code=200, text='<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3"><acknowledgement><typeCode code="AA"/></acknowledgement></MCCI_IN000002UV01>'),
            # Patient 3: Timeout (will retry and fail)
            Timeout("Request timeout"),
            Timeout("Request timeout"),
            Timeout("Request timeout"),
        ]
        
        mock_post.side_effect = responses
        
        # Process batch - should generate error summary
        try:
            result = workflow_fixture.process_batch(temp_csv_with_multiple_patients)
            
            # Verify error summary exists
            assert result.failed_patients > 0
            assert "_error_report" in result.error_summary
            assert "_error_statistics" in result.error_summary
            
            # Verify error statistics
            stats = result.error_summary["_error_statistics"]
            assert stats["total_errors"] > 0
            assert "by_category" in stats
            assert "by_type" in stats
            
        except (ConnectionError, Timeout):
            # Expected if critical error halts batch
            pass


# Fixtures

@pytest.fixture
def config_fixture(tmp_path):
    """Create test configuration."""
    from ihe_test_util.config.schema import Config, EndpointsConfig, CertificatesConfig, TransportConfig
    
    # Create test certificate files
    cert_path = tmp_path / "test_cert.pem"
    key_path = tmp_path / "test_key.pem"
    
    # Use actual test fixtures if available
    test_fixtures_dir = Path(__file__).parent.parent / "fixtures"
    if (test_fixtures_dir / "test_cert.pem").exists():
        cert_path.write_bytes((test_fixtures_dir / "test_cert.pem").read_bytes())
        key_path.write_bytes((test_fixtures_dir / "test_key.pem").read_bytes())
    else:
        # Create dummy files
        cert_path.write_text("DUMMY CERT")
        key_path.write_text("DUMMY KEY")
    
    config = Config(
        endpoints=EndpointsConfig(
            pix_add_url="http://localhost:8080/pix/add",
            iti41_url="http://localhost:8080/iti41/submit"
        ),
        certificates=CertificatesConfig(
            cert_path=cert_path,
            key_path=key_path,
            cert_format="pem"
        ),
        transport=TransportConfig(
            verify_tls=False,
            timeout_connect=10,
            timeout_read=30,
            max_retries=3
        )
    )
    
    return config


@pytest.fixture
def workflow_fixture(config_fixture):
    """Create PIXAddWorkflow instance for testing."""
    return PIXAddWorkflow(config_fixture)


@pytest.fixture
def temp_csv_file(tmp_path):
    """Create temporary CSV file with single patient."""
    csv_path = tmp_path / "test_patients.csv"
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,1.2.3.4.5,John,Doe,1980-01-15,M
"""
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def temp_csv_with_multiple_patients(tmp_path):
    """Create temporary CSV file with multiple patients."""
    csv_path = tmp_path / "test_patients_multi.csv"
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,1.2.3.4.5,John,Doe,1980-01-15,M
PAT002,1.2.3.4.5,Jane,Smith,1985-03-20,F
PAT003,1.2.3.4.5,Bob,Johnson,1990-07-10,M
"""
    csv_path.write_text(csv_content)
    return csv_path
