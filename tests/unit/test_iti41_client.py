"""Unit tests for ITI-41 SOAP Client.

Tests cover SOAP envelope construction, WS-Addressing headers, SAML embedding,
MTOM packaging, timeout configuration, retry logic, TLS enforcement, and
response correlation.
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from ihe_test_util.ihe_transactions.iti41_client import (
    ITI41SOAPClient,
    ITI41_ACTION,
    WSA_ANONYMOUS,
    SOAP12_NS,
    WSA_NS,
    RS_NS,
    REGISTRY_SUCCESS,
    REGISTRY_FAILURE,
    REGISTRY_PARTIAL_SUCCESS,
    MAX_RETRIES,
    RETRY_DELAYS,
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


# === Fixtures ===


@pytest.fixture
def mock_saml_assertion() -> SAMLAssertion:
    """Create mock SAML assertion for testing."""
    now = datetime.now(timezone.utc)
    return SAMLAssertion(
        assertion_id=f"_assertion_{uuid.uuid4()}",
        issuer="https://test-issuer.example.com",
        subject="test-user@example.com",
        audience="https://test-audience.example.com",
        issue_instant=now,
        not_before=now,
        not_on_or_after=now + timedelta(hours=1),
        xml_content="""<?xml version="1.0"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" 
                ID="_test_assertion" 
                Version="2.0" 
                IssueInstant="2025-01-01T00:00:00Z">
    <saml:Issuer>https://test-issuer.example.com</saml:Issuer>
    <saml:Subject>
        <saml:NameID>test-user@example.com</saml:NameID>
    </saml:Subject>
    <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
        <ds:SignedInfo>
            <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
            <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
        </ds:SignedInfo>
        <ds:SignatureValue>mock_signature</ds:SignatureValue>
    </ds:Signature>
</saml:Assertion>""",
        signature="mock_signature",
        certificate_subject="CN=Test Certificate",
        generation_method=SAMLGenerationMethod.PROGRAMMATIC,
    )


@pytest.fixture
def mock_ccd_document() -> CCDDocument:
    """Create mock CCD document for testing."""
    return CCDDocument(
        document_id=str(uuid.uuid4()),
        patient_id="PAT123456",
        template_path="templates/ccd-template.xml",
        xml_content="""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="2.16.840.1.113883.3.72.5.9.1" extension="DOC123"/>
    <code code="34133-9" codeSystem="2.16.840.1.113883.6.1"/>
    <title>Test CCD Document</title>
    <recordTarget>
        <patientRole>
            <id root="2.16.840.1.113883.3.72.5.9.1" extension="PAT123456"/>
        </patientRole>
    </recordTarget>
</ClinicalDocument>""",
        creation_timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_iti41_transaction(mock_ccd_document: CCDDocument) -> ITI41Transaction:
    """Create mock ITI-41 transaction for testing."""
    return ITI41Transaction(
        transaction_id=str(uuid.uuid4()),
        submission_set_id=str(uuid.uuid4()),
        document_entry_id=f"Document{uuid.uuid4().hex[:8]}",
        patient_id="PAT123456",
        patient_id_oid="2.16.840.1.113883.3.72.5.9.1",
        ccd_document=mock_ccd_document,
        submission_timestamp=datetime.now(timezone.utc),
        source_id="2.16.840.1.113883.3.72.5.1",
        mtom_content_id=f"{uuid.uuid4()}@ihe-test-util.local",
        metadata_xml="""<?xml version="1.0"?>
<xds:ProvideAndRegisterDocumentSetRequest xmlns:xds="urn:ihe:iti:xds-b:2007">
    <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
        <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
            <rim:ExtrinsicObject id="Document01" mimeType="text/xml"/>
        </rim:RegistryObjectList>
    </lcm:SubmitObjectsRequest>
</xds:ProvideAndRegisterDocumentSetRequest>""",
    )


@pytest.fixture
def client() -> ITI41SOAPClient:
    """Create ITI-41 client for testing."""
    return ITI41SOAPClient(
        endpoint_url="http://localhost:8080/iti41/submit",
        timeout=60,
        verify_tls=False,
    )


@pytest.fixture
def https_client() -> ITI41SOAPClient:
    """Create ITI-41 client with HTTPS for testing."""
    return ITI41SOAPClient(
        endpoint_url="https://test.example.com/iti41/submit",
        timeout=30,
        verify_tls=True,
    )


# === Test: SOAP Envelope Construction ===


class TestSOAPEnvelopeConstruction:
    """Tests for SOAP envelope construction."""

    def test_soap_envelope_has_correct_namespaces(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test that SOAP envelope contains correct namespaces."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert "http://www.w3.org/2003/05/soap-envelope" in envelope_str
        assert "http://www.w3.org/2005/08/addressing" in envelope_str

    def test_soap_envelope_has_header_and_body(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test that SOAP envelope contains Header and Body elements."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert "Header" in envelope_str
        assert "Body" in envelope_str

    def test_soap_envelope_contains_xdsb_metadata_in_body(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test that XDSb metadata is in SOAP Body."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert "ProvideAndRegisterDocumentSetRequest" in envelope_str

    def test_soap_envelope_rejects_invalid_xml(
        self,
        client: ITI41SOAPClient,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test that invalid XML metadata raises ITI41SOAPError."""
        # Arrange
        invalid_xml = "<invalid><unclosed>"
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act & Assert
        with pytest.raises(ITI41SOAPError) as exc_info:
            client._build_soap_envelope(
                xdsb_metadata=invalid_xml,
                message_id=message_id,
                saml_assertion=mock_saml_assertion,
            )

        assert "Invalid XDSb metadata XML" in str(exc_info.value)


# === Test: WS-Addressing Headers ===


class TestWSAddressingHeaders:
    """Tests for WS-Addressing headers."""

    def test_ws_addressing_action_is_iti41(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test wsa:Action is set to ITI-41 action URI."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert ITI41_ACTION in envelope_str

    def test_ws_addressing_message_id_is_included(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test wsa:MessageID is included in envelope."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert message_id in envelope_str

    def test_ws_addressing_to_is_endpoint_url(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test wsa:To contains endpoint URL."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert client.endpoint_url in envelope_str

    def test_ws_addressing_reply_to_is_anonymous(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test wsa:ReplyTo contains anonymous address."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert WSA_ANONYMOUS in envelope_str


# === Test: SAML Embedding ===


class TestSAMLEmbedding:
    """Tests for WS-Security SAML embedding."""

    def test_saml_assertion_is_in_ws_security_header(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test SAML assertion is embedded in WS-Security header."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert "Security" in envelope_str
        assert "Assertion" in envelope_str

    def test_ws_security_has_must_understand_attribute(
        self,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test wsse:Security has mustUnderstand='1'."""
        # Arrange
        message_id = f"urn:uuid:{uuid.uuid4()}"

        # Act
        envelope = client._build_soap_envelope(
            xdsb_metadata=mock_iti41_transaction.metadata_xml,
            message_id=message_id,
            saml_assertion=mock_saml_assertion,
        )

        # Assert
        envelope_str = envelope.decode("utf-8")
        assert 'mustUnderstand="1"' in envelope_str or "mustUnderstand='1'" in envelope_str


# === Test: MTOM Packaging ===


class TestMTOMPackaging:
    """Tests for MTOM multipart packaging."""

    @patch.object(ITI41SOAPClient, "_submit_with_retry")
    def test_mtom_package_is_created(
        self,
        mock_submit: MagicMock,
        client: ITI41SOAPClient,
        mock_iti41_transaction: ITI41Transaction,
        mock_saml_assertion: SAMLAssertion,
    ) -> None:
        """Test MTOM package is created with SOAP envelope and attachment."""
        # Arrange
        mock_response = Mock()
        mock_response.text = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/>
    </soap12:Body>
</soap12:Envelope>"""
        mock_submit.return_value = mock_response

        # Act
        response = client.submit(mock_iti41_transaction, mock_saml_assertion)

        # Assert
        mock_submit.assert_called_once()
        call_args = mock_submit.call_args
        # Check Content-Type includes multipart/related
        headers = call_args.kwargs.get("headers", {})
        assert "multipart/related" in headers.get("Content-Type", "")


# === Test: Timeout Configuration ===


class TestTimeoutConfiguration:
    """Tests for timeout configuration."""

    def test_default_timeout_is_60_seconds(self) -> None:
        """Test default timeout is 60 seconds."""
        # Arrange & Act
        client = ITI41SOAPClient("http://localhost:8080/iti41/submit")

        # Assert
        assert client.timeout == 60

    def test_custom_timeout_is_applied(self) -> None:
        """Test custom timeout value is applied."""
        # Arrange & Act
        client = ITI41SOAPClient(
            "http://localhost:8080/iti41/submit",
            timeout=120,
        )

        # Assert
        assert client.timeout == 120

    def test_timeout_property_returns_correct_value(
        self, client: ITI41SOAPClient
    ) -> None:
        """Test timeout property returns configured value."""
        # Assert
        assert client.timeout == 60


# === Test: Retry Logic ===


class TestRetryLogic:
    """Tests for exponential backoff retry logic."""

    @patch("time.sleep")
    @patch("requests.Session.post")
    def test_retry_on_connection_error(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
        client: ITI41SOAPClient,
    ) -> None:
        """Test retry on ConnectionError with exponential backoff."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"""<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
            <soap12:Body><rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/></soap12:Body>
        </soap12:Envelope>"""
        mock_response.content = mock_response.text.encode()

        # Fail twice, then succeed
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.ConnectionError("Connection failed"),
            mock_response,
        ]

        # Act
        response = client._submit_with_retry(
            url="http://localhost:8080/test",
            data=b"<test/>",
            headers={"Content-Type": "text/xml"},
            max_retries=3,
        )

        # Assert
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2
        # Check backoff delays
        mock_sleep.assert_any_call(RETRY_DELAYS[0])
        mock_sleep.assert_any_call(RETRY_DELAYS[1])

    @patch("time.sleep")
    @patch("requests.Session.post")
    def test_retry_on_503_service_unavailable(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
        client: ITI41SOAPClient,
    ) -> None:
        """Test retry on 503 Service Unavailable."""
        # Arrange
        mock_503_response = Mock()
        mock_503_response.status_code = 503
        mock_503_response.text = "Service Unavailable"

        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.text = f"""<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
            <soap12:Body><rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/></soap12:Body>
        </soap12:Envelope>"""
        mock_success_response.content = mock_success_response.text.encode()

        mock_post.side_effect = [mock_503_response, mock_success_response]

        # Act
        response = client._submit_with_retry(
            url="http://localhost:8080/test",
            data=b"<test/>",
            headers={"Content-Type": "text/xml"},
            max_retries=3,
        )

        # Assert
        assert mock_post.call_count == 2

    @patch("time.sleep")
    @patch("requests.Session.post")
    def test_no_retry_on_400_bad_request(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
        client: ITI41SOAPClient,
    ) -> None:
        """Test no retry on 400 Bad Request."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_post.return_value = mock_response

        # Act & Assert
        with pytest.raises(ITI41SOAPError) as exc_info:
            client._submit_with_retry(
                url="http://localhost:8080/test",
                data=b"<test/>",
                headers={"Content-Type": "text/xml"},
                max_retries=3,
            )

        assert mock_post.call_count == 1  # No retries
        assert "Client error (400)" in str(exc_info.value)

    @patch("time.sleep")
    @patch("requests.Session.post")
    def test_no_retry_on_500_internal_server_error(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
        client: ITI41SOAPClient,
    ) -> None:
        """Test no retry on 500 Internal Server Error."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_post.return_value = mock_response

        # Act & Assert
        with pytest.raises(ITI41SOAPError) as exc_info:
            client._submit_with_retry(
                url="http://localhost:8080/test",
                data=b"<test/>",
                headers={"Content-Type": "text/xml"},
                max_retries=3,
            )

        assert mock_post.call_count == 1  # No retries
        assert "Server error (500)" in str(exc_info.value)

    @patch("time.sleep")
    @patch("requests.Session.post")
    def test_max_retries_exceeded_raises_transport_error(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
        client: ITI41SOAPClient,
    ) -> None:
        """Test ITI41TransportError raised after max retries exceeded."""
        # Arrange
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        # Act & Assert
        with pytest.raises(ITI41TransportError) as exc_info:
            client._submit_with_retry(
                url="http://localhost:8080/test",
                data=b"<test/>",
                headers={"Content-Type": "text/xml"},
                max_retries=3,
            )

        assert mock_post.call_count == 4  # Initial + 3 retries
        assert "failed after 3 retries" in str(exc_info.value)


# === Test: TLS Enforcement ===


class TestTLSEnforcement:
    """Tests for TLS 1.2+ enforcement."""

    def test_http_endpoint_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test HTTP endpoint logs security warning."""
        # Arrange & Act
        with caplog.at_level("WARNING"):
            client = ITI41SOAPClient("http://localhost:8080/iti41/submit")

        # Assert
        assert any("HTTP transport" in record.message for record in caplog.records)
        assert any("HTTPS recommended" in record.message for record in caplog.records)

    def test_https_endpoint_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test HTTPS endpoint does not log HTTP warning."""
        # Arrange & Act
        with caplog.at_level("WARNING"):
            client = ITI41SOAPClient("https://test.example.com/iti41/submit")

        # Assert
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        http_warnings = [m for m in warning_messages if "HTTP transport" in m]
        assert len(http_warnings) == 0


# === Test: Response Correlation ===


class TestResponseCorrelation:
    """Tests for message ID correlation."""

    def test_correlation_matches_relates_to(
        self, client: ITI41SOAPClient
    ) -> None:
        """Test correlation matches when RelatesTo equals MessageID."""
        # Arrange
        message_id = "urn:uuid:12345678-1234-1234-1234-123456789012"
        response_xml = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}" xmlns:wsa="{WSA_NS}">
    <soap12:Header>
        <wsa:RelatesTo>{message_id}</wsa:RelatesTo>
    </soap12:Header>
    <soap12:Body/>
</soap12:Envelope>"""

        # Act
        matched = client._correlate_response(response_xml, message_id)

        # Assert
        assert matched is True

    def test_correlation_fails_when_mismatch(
        self, client: ITI41SOAPClient
    ) -> None:
        """Test correlation fails when RelatesTo doesn't match."""
        # Arrange
        request_id = "urn:uuid:12345678-1234-1234-1234-123456789012"
        different_id = "urn:uuid:99999999-9999-9999-9999-999999999999"
        response_xml = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}" xmlns:wsa="{WSA_NS}">
    <soap12:Header>
        <wsa:RelatesTo>{different_id}</wsa:RelatesTo>
    </soap12:Header>
    <soap12:Body/>
</soap12:Envelope>"""

        # Act
        matched = client._correlate_response(response_xml, request_id)

        # Assert
        assert matched is False

    def test_correlation_handles_missing_relates_to(
        self, client: ITI41SOAPClient
    ) -> None:
        """Test correlation handles missing RelatesTo gracefully."""
        # Arrange
        message_id = "urn:uuid:12345678-1234-1234-1234-123456789012"
        response_xml = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Header/>
    <soap12:Body/>
</soap12:Envelope>"""

        # Act
        matched = client._correlate_response(response_xml, message_id)

        # Assert
        assert matched is False


# === Test: Response Parsing ===


class TestResponseParsing:
    """Tests for registry response parsing using parsers module."""

    def test_parse_success_response(self) -> None:
        """Test parsing successful registry response using parsers module."""
        from ihe_test_util.ihe_transactions.parsers import parse_registry_response

        # Arrange
        response_xml = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}" xmlns:wsa="{WSA_NS}">
    <soap12:Header>
        <wsa:MessageID>urn:uuid:response-123</wsa:MessageID>
    </soap12:Header>
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_SUCCESS}"/>
    </soap12:Body>
</soap12:Envelope>"""

        # Act
        result = parse_registry_response(response_xml)

        # Assert
        assert result.is_success is True
        assert len(result.errors) == 0

    def test_parse_failure_response_with_errors(self) -> None:
        """Test parsing failure response with error list using parsers module."""
        from ihe_test_util.ihe_transactions.parsers import parse_registry_response

        # Arrange
        response_xml = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <rs:RegistryResponse xmlns:rs="{RS_NS}" status="{REGISTRY_FAILURE}">
            <rs:RegistryErrorList>
                <rs:RegistryError errorCode="XDSPatientIdDoesNotMatch" 
                                  codeContext="Patient ID mismatch"
                                  severity="urn:oasis:names:tc:ebxml-regrep:ErrorSeverityType:Error"/>
            </rs:RegistryErrorList>
        </rs:RegistryResponse>
    </soap12:Body>
</soap12:Envelope>"""

        # Act
        result = parse_registry_response(response_xml)

        # Assert
        assert result.is_success is False
        assert len(result.errors) >= 1
        assert any("XDSPatientIdDoesNotMatch" in e.error_code for e in result.errors)

    def test_parse_soap_fault(self) -> None:
        """Test parsing SOAP fault response using parsers module."""
        from ihe_test_util.ihe_transactions.parsers import parse_registry_response

        # Arrange
        response_xml = f"""<?xml version="1.0"?>
<soap12:Envelope xmlns:soap12="{SOAP12_NS}">
    <soap12:Body>
        <soap12:Fault>
            <soap12:Code>
                <soap12:Value>soap12:Sender</soap12:Value>
            </soap12:Code>
            <soap12:Reason>
                <soap12:Text>Invalid request format</soap12:Text>
            </soap12:Reason>
        </soap12:Fault>
    </soap12:Body>
</soap12:Envelope>"""

        # Act
        result = parse_registry_response(response_xml)

        # Assert
        assert result.is_success is False

    def test_map_registry_status_from_parsed_success(
        self, client: ITI41SOAPClient
    ) -> None:
        """Test mapping Success status from parsed response."""
        from ihe_test_util.ihe_transactions.parsers import RegistryResponse

        # Arrange
        parsed = RegistryResponse(
            status="Success",
            is_success=True,
            errors=[],
            warnings=[],
            response_id="test-id",
            request_id=None,
            document_ids=[],
            submission_set_id=None,
        )

        # Act
        status = client._map_registry_status_from_parsed(parsed)

        # Assert
        assert status == TransactionStatus.SUCCESS

    def test_map_registry_status_from_parsed_partial_success(
        self, client: ITI41SOAPClient
    ) -> None:
        """Test mapping PartialSuccess status from parsed response."""
        from ihe_test_util.ihe_transactions.parsers import RegistryResponse

        # Arrange
        parsed = RegistryResponse(
            status="PartialSuccess",
            is_success=False,
            errors=[],
            warnings=[],
            response_id="test-id",
            request_id=None,
            document_ids=[],
            submission_set_id=None,
        )

        # Act
        status = client._map_registry_status_from_parsed(parsed)

        # Assert
        assert status == TransactionStatus.PARTIAL_SUCCESS

    def test_map_registry_status_from_parsed_failure(
        self, client: ITI41SOAPClient
    ) -> None:
        """Test mapping Failure status from parsed response."""
        from ihe_test_util.ihe_transactions.parsers import RegistryResponse

        # Arrange
        parsed = RegistryResponse(
            status="Failure",
            is_success=False,
            errors=[],
            warnings=[],
            response_id="test-id",
            request_id=None,
            document_ids=[],
            submission_set_id=None,
        )

        # Act
        status = client._map_registry_status_from_parsed(parsed)

        # Assert
        assert status == TransactionStatus.ERROR

    def test_map_registry_status_from_parsed_unknown(
        self, client: ITI41SOAPClient
    ) -> None:
        """Test mapping unknown status defaults to ERROR."""
        from ihe_test_util.ihe_transactions.parsers import RegistryResponse

        # Arrange
        parsed = RegistryResponse(
            status="UnknownStatus",
            is_success=False,
            errors=[],
            warnings=[],
            response_id="test-id",
            request_id=None,
            document_ids=[],
            submission_set_id=None,
        )

        # Act
        status = client._map_registry_status_from_parsed(parsed)

        # Assert
        assert status == TransactionStatus.ERROR


# === Test: Properties ===


class TestProperties:
    """Tests for client properties."""

    def test_endpoint_url_property(self) -> None:
        """Test endpoint_url property returns configured URL."""
        # Arrange
        url = "http://test.example.com/iti41/submit"

        # Act
        client = ITI41SOAPClient(url)

        # Assert
        assert client.endpoint_url == url

    def test_timeout_property(self) -> None:
        """Test timeout property returns configured value."""
        # Arrange & Act
        client = ITI41SOAPClient(
            "http://localhost:8080/iti41/submit",
            timeout=90,
        )

        # Assert
        assert client.timeout == 90
