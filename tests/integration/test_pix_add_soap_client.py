"""Integration tests for PIX Add SOAP client complete workflow."""

import pytest
from lxml import etree
from unittest.mock import Mock, patch

from src.ihe_test_util.config.schema import Config, EndpointsConfig, TransportConfig
from ihe_test_util.utils.exceptions import ValidationError
from src.ihe_test_util.ihe_transactions.pix_add import build_pix_add_message
from src.ihe_test_util.ihe_transactions.soap_client import PIXAddSOAPClient
from src.ihe_test_util.models.patient import PatientDemographics
from src.ihe_test_util.models.responses import TransactionStatus
from src.ihe_test_util.models.saml import SAMLAssertion, SAMLGenerationMethod
from src.ihe_test_util.mock_server.app import app, initialize_app
from src.ihe_test_util.mock_server.config import MockServerConfig


@pytest.fixture
def mock_server_config():
    """Create mock server configuration."""
    return MockServerConfig(
        host="127.0.0.1",
        http_port=8080,
        log_level="DEBUG",
        log_path="mocks/logs/test-pix-soap-client.log",
        response_delay_ms=0  # No delay for tests
    )


@pytest.fixture
def flask_client(mock_server_config):
    """Create Flask test client with initialized mock server."""
    initialize_app(mock_server_config)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_requests(flask_client):
    """Mock requests.Session.post to use Flask test client."""
    def mock_post(url, data=None, **kwargs):
        # Extract path from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path
        
        # Make request through Flask test client
        response = flask_client.post(
            path,
            data=data,
            headers=kwargs.get('headers', {}),
            content_type='application/soap+xml'
        )
        
        # Create mock response object that mimics requests.Response
        mock_response = Mock()
        mock_response.status_code = response.status_code
        mock_response.text = response.get_data(as_text=True)
        mock_response.content = response.get_data()
        mock_response.headers = dict(response.headers)
        
        return mock_response
    
    with patch('requests.Session.post', side_effect=mock_post):
        yield


@pytest.fixture
def test_config():
    """Create test configuration for SOAP client."""
    return Config(
        endpoints=EndpointsConfig(
            pix_add_url="http://127.0.0.1:8080/pix/add",
            iti41_url="http://127.0.0.1:8080/iti41"
        ),
        transport=TransportConfig(
            verify_tls=False,
            timeout_connect=30,
            timeout_read=30,
            max_retries=3
        )
    )


@pytest.fixture
def sample_patient():
    """Create sample patient demographics."""
    from datetime import date
    return PatientDemographics(
        patient_id="INT-TEST-001",
        patient_id_oid="1.2.3.4.5.6",
        first_name="John",
        last_name="Doe",
        dob=date(1980, 1, 1),
        gender="M",
        address="123 Test Street",
        city="Springfield",
        state="IL",
        zip="62701"
    )


@pytest.fixture
def signed_saml_assertion():
    """Create signed SAML assertion for testing.
    
    Note: This is a mock signed assertion. In production, use
    SAMLSigner.sign_assertion() from Story 4.4.
    """
    return SAMLAssertion(
        assertion_id="saml-test-001",
        issuer="urn:test:issuer",
        subject="test-user",
        audience="urn:test:audience",
        issue_instant="2025-01-15T12:00:00Z",
        not_before="2025-01-15T12:00:00Z",
        not_on_or_after="2025-01-15T13:00:00Z",
        xml_content="""<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="saml-test-001">
  <saml:Issuer>urn:test:issuer</saml:Issuer>
  <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <ds:SignedInfo>
      <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
      <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
      <ds:Reference URI="#saml-test-001">
        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
        <ds:DigestValue>mock-digest-value</ds:DigestValue>
      </ds:Reference>
    </ds:SignedInfo>
    <ds:SignatureValue>mock-signature-value</ds:SignatureValue>
  </ds:Signature>
  <saml:Subject>
    <saml:NameID>test-user</saml:NameID>
  </saml:Subject>
  <saml:Conditions NotBefore="2025-01-15T12:00:00Z" NotOnOrAfter="2025-01-15T13:00:00Z">
    <saml:AudienceRestriction>
      <saml:Audience>urn:test:audience</saml:Audience>
    </saml:AudienceRestriction>
  </saml:Conditions>
</saml:Assertion>""",
        signature="""<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
  <ds:SignedInfo>
    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
  </ds:SignedInfo>
  <ds:SignatureValue>mock-signature-value</ds:SignatureValue>
</ds:Signature>""",
        certificate_subject="CN=Test Certificate",
        generation_method=SAMLGenerationMethod.PROGRAMMATIC
    )


class TestPIXAddSOAPClientIntegration:
    """Integration tests for PIX Add SOAP client with mock endpoint."""

    def test_pix_add_against_mock_endpoint(
        self,
        flask_client,
        mock_requests,
        test_config,
        sample_patient,
        signed_saml_assertion
    ):
        """Test complete PIX Add workflow against mock endpoint.
        
        Verifies:
        - SOAP client builds correct envelope
        - Mock endpoint receives and validates request
        - Response is parsed correctly
        - Transaction completes successfully
        """
        # Build HL7v3 PIX Add message
        hl7v3_message = build_pix_add_message(
            demographics=sample_patient,
            sending_facility="1.2.3.4.5.6",
            receiver_facility="1.2.840.114350"
        )
        
        # Create SOAP client
        client = PIXAddSOAPClient(test_config)
        
        # Submit PIX Add transaction
        response = client.submit_pix_add(hl7v3_message, signed_saml_assertion)
        
        # Verify response
        assert response is not None
        assert response.is_success is True
        assert response.status_code == "AA"
        assert response.transaction_type.value == "PIX_ADD"
        assert response.request_id is not None
        assert response.response_id is not None
        assert response.processing_time_ms > 0
        assert response.is_success is True
        assert response.has_errors is False
        
        # Verify response XML contains MCCI acknowledgment
        assert "MCCI_IN000002UV01" in response.response_xml
        
        # Parse response to verify structure
        tree = etree.fromstring(response.response_xml.encode('utf-8'))
        ns = {"hl7": "urn:hl7-org:v3"}
        
        # Verify acknowledgment status
        type_code = tree.find(".//hl7:acknowledgement/hl7:typeCode", namespaces=ns)
        assert type_code is not None
        assert type_code.get("code") == "AA"
        
        # Verify patient ID is echoed back
        patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
        assert patient_id is not None
        assert patient_id.get("extension") == "INT-TEST-001"

    def test_pix_add_with_custom_timeout_and_retries(
        self,
        flask_client,
        mock_requests,
        test_config,
        sample_patient,
        signed_saml_assertion
    ):
        """Test PIX Add submission with custom timeout and retry configuration."""
        # Build HL7v3 message
        hl7v3_message = build_pix_add_message(
            demographics=sample_patient,
            sending_facility="1.2.3.4.5.6",
            receiver_facility="1.2.840.114350"
        )
        
        # Create client with custom timeout and retries
        client = PIXAddSOAPClient(
            test_config,
            timeout=60,
            max_retries=5
        )
        
        # Verify configuration
        assert client.timeout == 60
        assert client.max_retries == 5
        
        # Submit transaction
        response = client.submit_pix_add(hl7v3_message, signed_saml_assertion)
        
        # Verify success
        assert response.is_success is True

    def test_pix_add_with_minimal_patient_data(
        self,
        flask_client,
        mock_requests,
        test_config,
        signed_saml_assertion
    ):
        """Test PIX Add with minimal patient data (only ID required)."""
        # Create minimal patient
        from datetime import date
        minimal_patient = PatientDemographics(
            patient_id="MIN-TEST-002",
            patient_id_oid="1.2.3.4.5.6",
            first_name="Jane",
            last_name="Smith",
            dob=date(1990, 5, 15),
            gender="F"
        )
        
        # Build HL7v3 message
        hl7v3_message = build_pix_add_message(
            demographics=minimal_patient,
            sending_facility="1.2.3.4.5.6",
            receiver_facility="1.2.840.114350"
        )
        
        # Create client and submit
        client = PIXAddSOAPClient(test_config)
        response = client.submit_pix_add(hl7v3_message, signed_saml_assertion)
        
        # Verify success
        assert response.is_success is True
        assert response.status_code == "AA"

    def test_pix_add_error_handling_unsigned_saml(
        self,
        test_config,
        sample_patient
    ):
        """Test that unsigned SAML assertion raises ValidationError."""
        # Create unsigned SAML assertion (no signature)
        unsigned_saml = SAMLAssertion(
            assertion_id="unsigned-001",
            issuer="urn:test:issuer",
            subject="test-user",
            audience="urn:test:audience",
            issue_instant="2025-01-15T12:00:00Z",
            not_before="2025-01-15T12:00:00Z",
            not_on_or_after="2025-01-15T13:00:00Z",
            xml_content="<saml:Assertion>unsigned</saml:Assertion>",
            signature="",  # No signature
            certificate_subject="CN=Test",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC
        )
        
        # Build message
        hl7v3_message = build_pix_add_message(
            demographics=sample_patient,
            sending_facility="1.2.3.4.5.6",
            receiver_facility="1.2.840.114350"
        )
        
        # Create client
        client = PIXAddSOAPClient(test_config)
        
        # Verify ValidationError is raised
        with pytest.raises(ValidationError) as exc_info:
            client.submit_pix_add(hl7v3_message, unsigned_saml)
        
        assert "not signed" in str(exc_info.value).lower()

    def test_complete_pix_add_workflow(
        self,
        flask_client,
        mock_requests,
        test_config,
        signed_saml_assertion
    ):
        """Test complete end-to-end PIX Add workflow.
        
        Simulates complete workflow:
        1. Create patient demographics (could be from CSV in production)
        2. Build HL7v3 PIX Add message
        3. Submit via SOAP client with SAML
        4. Verify acknowledgment received
        """
        # Step 1: Create patient demographics
        # In production, this would come from CSV parser (Story 1.5)
        from datetime import date
        patient = PatientDemographics(
            patient_id="E2E-TEST-003",
            patient_id_oid="1.2.3.4.5.6.7",
            first_name="Alice",
            last_name="Johnson",
            dob=date(1975, 3, 20),
            gender="F",
            address="456 Oak Avenue",
            city="Portland",
            state="OR",
            zip="97201"
        )
        
        # Step 2: Build HL7v3 message (Story 5.1)
        hl7v3_message = build_pix_add_message(
            demographics=patient,
            sending_facility="1.2.3.4.5.6.7",
            receiver_facility="1.2.840.114350.1.13"
        )
        
        # Verify message structure
        assert "PRPA_IN201301UV02" in hl7v3_message
        assert "E2E-TEST-003" in hl7v3_message
        
        # Step 3: Submit via SOAP client (Story 5.2)
        client = PIXAddSOAPClient(test_config)
        response = client.submit_pix_add(hl7v3_message, signed_saml_assertion)
        
        # Step 4: Verify acknowledgment
        assert response.is_success is True
        assert response.status_code == "AA"
        assert len(response.error_messages) == 0
        
        # Verify response contains expected elements
        tree = etree.fromstring(response.response_xml.encode('utf-8'))
        ns = {"hl7": "urn:hl7-org:v3"}
        
        # Verify MCCI acknowledgment structure
        mcci = tree.find(".//hl7:MCCI_IN000002UV01", namespaces=ns)
        assert mcci is not None
        
        # Verify acknowledgment element
        ack = tree.find(".//hl7:acknowledgement", namespaces=ns)
        assert ack is not None
        
        # Verify patient ID echoed correctly
        patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
        assert patient_id is not None
        assert patient_id.get("extension") == "E2E-TEST-003"

    def test_pix_add_audit_logging(
        self,
        flask_client,
        mock_requests,
        test_config,
        sample_patient,
        signed_saml_assertion,
        caplog
    ):
        """Test that PIX Add transaction is logged to audit trail."""
        import logging
        
        caplog.set_level(logging.DEBUG, logger="ihe_test_util.audit.pix_add")
        
        # Build and submit transaction
        hl7v3_message = build_pix_add_message(
            demographics=sample_patient,
            sending_facility="1.2.3.4.5.6",
            receiver_facility="1.2.840.114350"
        )
        
        client = PIXAddSOAPClient(test_config)
        response = client.submit_pix_add(hl7v3_message, signed_saml_assertion)
        
        # Verify audit logging occurred
        audit_records = [r for r in caplog.records if "audit.pix_add" in r.name]
        
        # Should have logged transaction details
        assert len(audit_records) > 0
        
        # Check for key audit log messages
        log_messages = [r.message for r in audit_records]
        log_text = " ".join(log_messages)
        
        # Verify transaction status logged
        assert "PIX Add Transaction" in log_text or "Status: SUCCESS" in log_text

    def test_pix_add_connection_error_handling(self, test_config, sample_patient, signed_saml_assertion):
        """Test handling of connection errors to unreachable endpoint."""
        import requests
        
        # Configure client with unreachable endpoint
        unreachable_config = Config(
            endpoints=EndpointsConfig(
                pix_add_url="http://invalid-endpoint-does-not-exist.local:9999/pix/add",
                iti41_url="http://localhost:8080/iti41"
            ),
            transport=TransportConfig(
                verify_tls=False,
                timeout_connect=1,  # Short timeout for test
                timeout_read=1,
                max_retries=2  # Fewer retries for test speed
            )
        )
        
        # Build message
        hl7v3_message = build_pix_add_message(
            demographics=sample_patient,
            sending_facility="1.2.3.4.5.6",
            receiver_facility="1.2.840.114350"
        )
        
        # Create client
        client = PIXAddSOAPClient(unreachable_config, timeout=1, max_retries=2)
        
        # Verify ConnectionError raised
        with pytest.raises(requests.ConnectionError) as exc_info:
            client.submit_pix_add(hl7v3_message, signed_saml_assertion)
        
        # Verify error message is actionable
        error_msg = str(exc_info.value).lower()
        assert "connect" in error_msg or "endpoint" in error_msg

    def test_pix_add_http_security_warning(self, test_config, sample_patient, signed_saml_assertion, caplog):
        """Test that HTTP endpoint triggers security warning."""
        import logging
        
        caplog.set_level(logging.WARNING)
        
        # HTTP endpoint should trigger warning during client initialization
        http_config = Config(
            endpoints=EndpointsConfig(
                pix_add_url="http://localhost:8080/pix/add",  # HTTP not HTTPS
                iti41_url="http://localhost:8080/iti41"
            ),
            transport=TransportConfig(verify_tls=False)
        )
        
        # Create client (should log warning)
        client = PIXAddSOAPClient(http_config)
        
        # Check for security warning
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        
        # Verify security warning logged
        assert any("SECURITY WARNING" in msg and "HTTP" in msg for msg in warning_messages)

    def test_pix_add_response_parsing_error_handling(
        self,
        test_config,
        sample_patient,
        signed_saml_assertion,
        mocker
    ):
        """Test handling of malformed response from endpoint."""
        # Mock session.post to return malformed response
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "This is not valid XML"
        
        mocker.patch('requests.Session.post', return_value=mock_response)
        
        # Build message
        hl7v3_message = build_pix_add_message(
            demographics=sample_patient,
            sending_facility="1.2.3.4.5.6",
            receiver_facility="1.2.840.114350"
        )
        
        # Create client
        client = PIXAddSOAPClient(test_config)
        
        # Submit transaction
        response = client.submit_pix_add(hl7v3_message, signed_saml_assertion)
        
        # Should return error response (not raise exception)
        assert response.has_errors is True
        assert response.status_code == "PARSE_ERROR"
        assert len(response.error_messages) > 0
        assert "parse" in response.error_messages[0].lower()
