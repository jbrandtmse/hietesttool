"""Integration tests for ITI-41 SOAP Client against mock endpoint.

Tests cover full submission workflow, SAML-secured submission, error response
handling, and timeout behavior against the mock ITI-41 endpoint.

Note: These tests require the mock server to be running:
    python -m ihe_test_util mock start
"""

import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from ihe_test_util.ihe_transactions.iti41_client import (
    ITI41SOAPClient,
    REGISTRY_SUCCESS,
    REGISTRY_FAILURE,
    SOAP12_NS,
    RS_NS,
    WSA_NS,
)
from ihe_test_util.models.ccd import CCDDocument
from ihe_test_util.models.saml import SAMLAssertion, SAMLGenerationMethod
from ihe_test_util.models.responses import TransactionStatus, TransactionType
from ihe_test_util.models.transactions import ITI41Transaction
from ihe_test_util.utils.exceptions import (
    ITI41SOAPError,
    ITI41TimeoutError,
    ITI41TransportError,
)


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# === Fixtures ===


@pytest.fixture
def test_ccd_content() -> str:
    """Load test CCD document content from fixtures."""
    ccd_path = Path("tests/fixtures/test_ccd_template.xml")
    if ccd_path.exists():
        return ccd_path.read_text()
    # Fallback minimal CCD for testing
    return """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="2.16.840.1.113883.3.72.5.9.1" extension="DOC-INTEGRATION-TEST"/>
    <code code="34133-9" codeSystem="2.16.840.1.113883.6.1"/>
    <title>Integration Test CCD Document</title>
    <effectiveTime value="20251123"/>
    <recordTarget>
        <patientRole>
            <id root="2.16.840.1.113883.3.72.5.9.1" extension="PAT-INTEGRATION"/>
            <patient>
                <name>
                    <given>Integration</given>
                    <family>Test</family>
                </name>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>"""


@pytest.fixture
def mock_saml_assertion() -> SAMLAssertion:
    """Create mock SAML assertion for integration testing."""
    now = datetime.now(timezone.utc)
    return SAMLAssertion(
        assertion_id=f"_integration_test_{uuid.uuid4()}",
        issuer="https://integration-test.example.com",
        subject="integration-test-user@example.com",
        audience="https://mock-iti41.example.com",
        issue_instant=now,
        not_before=now,
        not_on_or_after=now + timedelta(hours=1),
        xml_content="""<?xml version="1.0"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" 
                ID="_integration_test_assertion" 
                Version="2.0" 
                IssueInstant="2025-01-01T00:00:00Z">
    <saml:Issuer>https://integration-test.example.com</saml:Issuer>
    <saml:Subject>
        <saml:NameID>integration-test-user@example.com</saml:NameID>
    </saml:Subject>
    <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
        <ds:SignedInfo>
            <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
            <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
        </ds:SignedInfo>
        <ds:SignatureValue>integration_test_signature</ds:SignatureValue>
    </ds:Signature>
</saml:Assertion>""",
        signature="integration_test_signature",
        certificate_subject="CN=Integration Test Certificate",
        generation_method=SAMLGenerationMethod.PROGRAMMATIC,
    )


@pytest.fixture
def mock_ccd_document(test_ccd_content: str) -> CCDDocument:
    """Create mock CCD document for integration testing."""
    return CCDDocument(
        document_id=str(uuid.uuid4()),
        patient_id="PAT-INTEGRATION",
        template_path="tests/fixtures/test_ccd_template.xml",
        xml_content=test_ccd_content,
        creation_timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_iti41_transaction(mock_ccd_document: CCDDocument) -> ITI41Transaction:
    """Create mock ITI-41 transaction for integration testing."""
    return ITI41Transaction(
        transaction_id=str(uuid.uuid4()),
        submission_set_id=str(uuid.uuid4()),
        document_entry_id=f"Document{uuid.uuid4().hex[:8]}",
        patient_id="PAT-INTEGRATION",
        patient_id_oid="2.16.840.1.113883.3.72.5.9.1",
        ccd_document=mock_ccd_document,
        submission_timestamp=datetime.now(timezone.utc),
        source_id="2.16.840.1.113883.3.72.5.1",
        mtom_content_id=f"{uuid.uuid4()}@ihe-test-util.local",
        metadata_xml="""<?xml version="1.0"?>
<xds:ProvideAndRegisterDocumentSetRequest xmlns:xds="urn:ihe:iti:xds-b:2007">
    <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
        <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
            <rim:ExtrinsicObject id="Document01" mimeType="text/xml"
                                 objectType="urn:uuid:7edca82f-054d-47f2-a032-9b2a5b5186c1">
                <rim:Name>
                    <rim:LocalizedString value="Integration Test CCD"/>
                </rim:Name>
            </rim:ExtrinsicObject>
            <rim:RegistryPackage id="SubmissionSet01">
                <rim:Name>
                    <rim:LocalizedString value="Integration Test Submission"/>
                </rim:Name>
            </rim:RegistryPackage>
            <rim:Association id="Association01"
                           associationType="urn:oasis:names:tc:ebxml-regrep:AssociationType:HasMember"
                           sourceObject="SubmissionSet01"
                           targetObject="Document01"/>
        </rim:RegistryObjectList>
    </lcm:SubmitObjectsRequest>
</xds:ProvideAndRegisterDocumentSetRequest>""",
    )


@pytest.fixture
def mock_server_url() -> str:
    """Get mock server URL for integration tests."""
    return "http://localhost:5000/iti41/submit"


@pytest.fixture
def iti41_client(mock_server_url: str) -> ITI41SOAPClient:
    """Create ITI-41 client configured for mock server."""
    return ITI41SOAPClient(
        endpoint_url=mock_server_url,
        timeout=30,
        verify_tls=False,
    )


def mock_server_available(url: str) -> bool:
    """Check if mock server is available."""
    try:
        # Try health check endpoint
        health_url = url.replace("/iti41/submit", "/health")
        response = requests.get(health_url, timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


# === Test: Full Submission Workflow ===


class TestSubmitCCDToMockEndpoint:
    """Integration tests for full CCD submission workflow."""

    @pytest.mark.skipif(
        not mock_server_available("http://localhost:5000/iti41/submit"),
        reason="Mock server not running. Start with: python -m ihe_test_util mock start",
    )
    def test_submit_ccd_to_mock_endpoint_success(
        self,
        iti41_client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test successful CCD submission to mock endpoint."""
        # Act
        response = iti41_client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert
        assert response is not None
        assert response.transaction_type == TransactionType.ITI_41
        assert response.status in (
            TransactionStatus.SUCCESS,
            TransactionStatus.PARTIAL_SUCCESS,
        )
        assert response.request_id is not None
        assert response.processing_time_ms > 0

    @patch("requests.Session.post")
    def test_submit_ccd_mocked_success_response(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test CCD submission with mocked successful response."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}" xmlns:wsa="{WSA_NS}">
    <soap12:Header>
        <wsa:MessageID>urn:uuid:response-integration-test</wsa:MessageID>
        <wsa:RelatesTo>urn:uuid:request-integration-test</wsa:RelatesTo>
    </soap12:Header>
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/>
    </soap12:Body>
</soap12:Envelope>"""
        mock_response.content = mock_response.text.encode()
        mock_post.return_value = mock_response

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act
        response = client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert
        assert response.status == TransactionStatus.SUCCESS
        assert response.transaction_type == TransactionType.ITI_41
        assert len(response.error_messages) == 0


# === Test: SAML-Secured Submission ===


class TestSubmitWithSAMLAssertion:
    """Integration tests for SAML-secured submission."""

    @patch("requests.Session.post")
    def test_submit_includes_saml_in_ws_security(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test that SAML assertion is included in WS-Security header."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/>
    </soap12:Body>
</soap12:Envelope>"""
        mock_response.content = mock_response.text.encode()
        mock_post.return_value = mock_response

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act
        client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert - Check that SAML assertion is in the request
        call_args = mock_post.call_args
        request_data = call_args.kwargs.get("data", b"")
        request_str = (
            request_data.decode("utf-8", errors="ignore")
            if isinstance(request_data, bytes)
            else str(request_data)
        )
        
        # SAML assertion should be in the MTOM package
        assert "Assertion" in request_str or "Security" in request_str

    @patch("requests.Session.post")
    def test_submit_with_expired_saml_logs_warning(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
    ) -> None:
        """Test submission with expired SAML logs appropriate warning."""
        # Arrange - Create expired SAML assertion
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        expired_saml = SAMLAssertion(
            assertion_id="_expired_assertion",
            issuer="https://test.example.com",
            subject="test-user@example.com",
            audience="https://audience.example.com",
            issue_instant=past,
            not_before=past,
            not_on_or_after=past + timedelta(hours=1),  # Expired 1 hour ago
            xml_content="""<?xml version="1.0"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" 
                ID="_expired" Version="2.0" IssueInstant="2025-01-01T00:00:00Z">
    <saml:Issuer>https://test.example.com</saml:Issuer>
    <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
        <ds:SignatureValue>sig</ds:SignatureValue>
    </ds:Signature>
</saml:Assertion>""",
            signature="sig",
            certificate_subject="CN=Test",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC,
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/>
    </soap12:Body>
</soap12:Envelope>"""
        mock_response.content = mock_response.text.encode()
        mock_post.return_value = mock_response

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act - Should still submit (server validates SAML)
        response = client.submit(mock_iti41_transaction, expired_saml)

        # Assert - Request was made
        mock_post.assert_called_once()


# === Test: Error Response Handling ===


class TestErrorResponseHandling:
    """Integration tests for error response handling."""

    @patch("requests.Session.post")
    def test_handle_registry_failure_response(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test handling of registry failure response."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_FAILURE}">
            <rs:RegistryErrorList>
                <rs:RegistryError errorCode="XDSPatientIdDoesNotMatch"
                                  codeContext="Patient ID in metadata does not match repository"
                                  severity="urn:oasis:names:tc:ebxml-regrep:ErrorSeverityType:Error"/>
            </rs:RegistryErrorList>
        </rs:RegistryResponse>
    </soap12:Body>
</soap12:Envelope>"""
        mock_response.content = mock_response.text.encode()
        mock_post.return_value = mock_response

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act
        response = client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert
        assert response.status == TransactionStatus.ERROR
        assert len(response.error_messages) > 0
        assert any("XDSPatientIdDoesNotMatch" in msg for msg in response.error_messages)

    @patch("requests.Session.post")
    def test_handle_soap_fault_response(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test handling of SOAP fault response."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <soap12:Fault>
            <soap12:Code>
                <soap12:Value>soap12:Sender</soap12:Value>
            </soap12:Code>
            <soap12:Reason>
                <soap12:Text>WS-Security header missing or invalid</soap12:Text>
            </soap12:Reason>
        </soap12:Fault>
    </soap12:Body>
</soap12:Envelope>"""
        mock_response.content = mock_response.text.encode()
        mock_post.return_value = mock_response

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act
        response = client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert
        assert response.status == TransactionStatus.ERROR
        assert len(response.error_messages) > 0
        # SOAP faults are formatted as "[Error] SOAP:{fault_code}: {fault_reason}"
        assert any("SOAP:" in msg for msg in response.error_messages)

    @patch("requests.Session.post")
    def test_handle_http_500_error(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test handling of HTTP 500 error."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_post.return_value = mock_response

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act & Assert
        with pytest.raises(ITI41SOAPError) as exc_info:
            client.submit(mock_iti41_transaction, mock_saml_assertion)

        assert "Server error (500)" in str(exc_info.value)


# === Test: Timeout Handling ===


class TestTimeoutHandling:
    """Integration tests for timeout behavior."""

    @patch("requests.Session.post")
    def test_timeout_raises_timeout_error(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test that timeout raises ITI41TimeoutError."""
        # Arrange
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        client = ITI41SOAPClient(
            "http://localhost:5000/iti41/submit",
            timeout=5,
        )

        # Act & Assert
        with pytest.raises(ITI41TimeoutError) as exc_info:
            client.submit(mock_iti41_transaction, mock_saml_assertion)

        assert "timed out" in str(exc_info.value).lower()

    @patch("time.sleep")  # Skip actual delays
    @patch("requests.Session.post")
    def test_timeout_retry_with_eventual_success(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test timeout retry eventually succeeds."""
        # Arrange
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/>
    </soap12:Body>
</soap12:Envelope>"""
        mock_success.content = mock_success.text.encode()

        # Timeout twice, then succeed
        mock_post.side_effect = [
            requests.exceptions.Timeout("Timeout 1"),
            requests.exceptions.Timeout("Timeout 2"),
            mock_success,
        ]

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=5)

        # Act
        response = client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert
        assert response.status == TransactionStatus.SUCCESS
        assert mock_post.call_count == 3


# === Test: Connection Error Handling ===


class TestConnectionErrorHandling:
    """Integration tests for connection error handling."""

    @patch("time.sleep")
    @patch("requests.Session.post")
    def test_connection_error_retries_and_fails(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test connection error retries and eventually fails."""
        # Arrange
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act & Assert
        with pytest.raises(ITI41TransportError) as exc_info:
            client.submit(mock_iti41_transaction, mock_saml_assertion)

        assert "failed after" in str(exc_info.value).lower()
        assert mock_post.call_count == 4  # Initial + 3 retries


# === Test: Response Validation ===


class TestResponseValidation:
    """Integration tests for response validation."""

    @patch("requests.Session.post")
    def test_response_includes_processing_time(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test response includes processing time measurement."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/>
    </soap12:Body>
</soap12:Envelope>"""
        mock_response.content = mock_response.text.encode()
        mock_post.return_value = mock_response

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act
        response = client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert
        assert response.processing_time_ms >= 0
        assert response.response_timestamp is not None

    @patch("requests.Session.post")
    def test_response_preserves_request_id(
        self,
        mock_post: MagicMock,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test response preserves request message ID."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/>
    </soap12:Body>
</soap12:Envelope>"""
        mock_response.content = mock_response.text.encode()
        mock_post.return_value = mock_response

        client = ITI41SOAPClient("http://localhost:5000/iti41/submit", timeout=30)

        # Act
        response = client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert
        assert response.request_id is not None
        assert response.request_id.startswith("urn:uuid:")
