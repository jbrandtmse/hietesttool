"""Unit tests for WS-Security header construction."""

import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from lxml import etree

from ihe_test_util.models.saml import SAMLAssertion, SAMLGenerationMethod
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
from ihe_test_util.saml.signer import SAMLSigner
from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder


@pytest.fixture
def cert_bundle():
    """Load test certificate bundle with private key."""
    cert_path = Path("tests/fixtures/test_cert.pem")
    key_path = Path("tests/fixtures/test_key.pem")
    return load_certificate(cert_path, key_path=key_path)


@pytest.fixture
def unsigned_saml_assertion():
    """Generate unsigned SAML assertion for testing."""
    generator = SAMLProgrammaticGenerator()
    return generator.generate(
        subject="test-user@example.com",
        issuer="https://test-idp.example.com",
        audience="https://test-sp.example.com"
    )


@pytest.fixture
def signed_saml_assertion(cert_bundle, unsigned_saml_assertion):
    """Generate and sign SAML assertion for testing."""
    signer = SAMLSigner(cert_bundle)
    return signer.sign_assertion(unsigned_saml_assertion)


class TestWSSecurityHeaderBuilderInitialization:
    """Test WSSecurityHeaderBuilder initialization."""

    def test_initialization_success(self):
        """Test WSSecurityHeaderBuilder initializes correctly."""
        builder = WSSecurityHeaderBuilder()
        assert builder is not None
        assert builder.WSSE_NS is not None
        assert builder.WSU_NS is not None
        assert builder.WSA_NS is not None
        assert builder.SOAP_NS is not None


class TestBuildWSSecurityHeader:
    """Test build_ws_security_header method."""

    def test_build_with_signed_saml(self, signed_saml_assertion):
        """Test building WS-Security header with signed SAML."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)

        # Verify element is wsse:Security
        assert ws_security.tag == f"{{{builder.WSSE_NS}}}Security"

        # Verify mustUnderstand attribute
        assert ws_security.get(f"{{{builder.SOAP_NS}}}mustUnderstand") == "1"

        # Verify timestamp present
        timestamp = ws_security.find(f".//{{{builder.WSU_NS}}}Timestamp")
        assert timestamp is not None

        # Verify SAML assertion present
        saml_assertion = ws_security.find(f".//{{{builder.SAML_NS}}}Assertion")
        assert saml_assertion is not None

        # Verify signature present in SAML
        signature = saml_assertion.find(f".//{{{builder.DS_NS}}}Signature")
        assert signature is not None

    def test_build_with_unsigned_saml(self, unsigned_saml_assertion):
        """Test building WS-Security header with unsigned SAML."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(unsigned_saml_assertion)

        # Should still work, just embed as-is
        assert ws_security is not None
        saml_assertion = ws_security.find(f".//{{{builder.SAML_NS}}}Assertion")
        assert saml_assertion is not None

    def test_build_with_custom_timestamp_validity(self, signed_saml_assertion):
        """Test building WS-Security header with custom timestamp validity."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(
            signed_saml_assertion,
            timestamp_validity_minutes=10
        )

        timestamp = ws_security.find(f".//{{{builder.WSU_NS}}}Timestamp")
        assert timestamp is not None

        created = timestamp.find(f".//{{{builder.WSU_NS}}}Created")
        expires = timestamp.find(f".//{{{builder.WSU_NS}}}Expires")

        # Parse timestamps
        created_dt = datetime.strptime(created.text, '%Y-%m-%dT%H:%M:%S.%fZ')
        expires_dt = datetime.strptime(expires.text, '%Y-%m-%dT%H:%M:%S.%fZ')

        # Verify 10 minute difference (allow 1 second tolerance)
        diff = (expires_dt - created_dt).total_seconds()
        assert 599 <= diff <= 601  # 10 minutes ± 1 second

    def test_build_with_none_saml_raises_error(self):
        """Test building WS-Security header with None SAML raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        with pytest.raises(ValueError, match="signed_saml parameter is required"):
            builder.build_ws_security_header(None)

    def test_build_with_empty_xml_content_raises_error(self):
        """Test building WS-Security header with empty xml_content raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        
        # Create assertion with empty xml_content
        assertion = SAMLAssertion(
            assertion_id="_test123",
            issuer="https://test.com",
            subject="test@test.com",
            audience="https://sp.test.com",
            issue_instant=datetime.utcnow(),
            not_before=datetime.utcnow(),
            not_on_or_after=datetime.utcnow() + timedelta(hours=1),
            xml_content="",  # Empty
            signature="",
            certificate_subject="CN=Test",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC
        )
        
        with pytest.raises(ValueError, match="xml_content is empty"):
            builder.build_ws_security_header(assertion)

    def test_build_with_malformed_xml_raises_error(self):
        """Test building WS-Security header with malformed XML raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        
        # Create assertion with malformed xml_content
        assertion = SAMLAssertion(
            assertion_id="_test123",
            issuer="https://test.com",
            subject="test@test.com",
            audience="https://sp.test.com",
            issue_instant=datetime.utcnow(),
            not_before=datetime.utcnow(),
            not_on_or_after=datetime.utcnow() + timedelta(hours=1),
            xml_content="<invalid>xml<without>closing</tags>",
            signature="",
            certificate_subject="CN=Test",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC
        )
        
        with pytest.raises(ValueError, match="Invalid SAML XML structure"):
            builder.build_ws_security_header(assertion)


class TestCreateTimestamp:
    """Test _create_timestamp method."""

    def test_create_timestamp_default_validity(self):
        """Test creating timestamp with default validity (5 minutes)."""
        builder = WSSecurityHeaderBuilder()
        timestamp = builder._create_timestamp(5)

        # Verify element is wsu:Timestamp
        assert timestamp.tag == f"{{{builder.WSU_NS}}}Timestamp"

        # Verify wsu:Id attribute present
        timestamp_id = timestamp.get(f"{{{builder.WSU_NS}}}Id")
        assert timestamp_id is not None
        assert timestamp_id.startswith("TS-")

        # Verify Created and Expires elements
        created = timestamp.find(f".//{{{builder.WSU_NS}}}Created")
        expires = timestamp.find(f".//{{{builder.WSU_NS}}}Expires")
        assert created is not None
        assert expires is not None

    def test_create_timestamp_format(self):
        """Test timestamp format is ISO 8601 with Z timezone."""
        builder = WSSecurityHeaderBuilder()
        timestamp = builder._create_timestamp(5)

        created = timestamp.find(f".//{{{builder.WSU_NS}}}Created")
        expires = timestamp.find(f".//{{{builder.WSU_NS}}}Expires")

        # Verify format ends with Z
        assert created.text.endswith('Z')
        assert expires.text.endswith('Z')

        # Verify can parse as ISO 8601
        created_dt = datetime.strptime(created.text, '%Y-%m-%dT%H:%M:%S.%fZ')
        expires_dt = datetime.strptime(expires.text, '%Y-%m-%dT%H:%M:%S.%fZ')
        assert created_dt < expires_dt

    def test_create_timestamp_custom_validity(self):
        """Test creating timestamp with custom validity period."""
        builder = WSSecurityHeaderBuilder()
        timestamp = builder._create_timestamp(10)

        created = timestamp.find(f".//{{{builder.WSU_NS}}}Created")
        expires = timestamp.find(f".//{{{builder.WSU_NS}}}Expires")

        created_dt = datetime.strptime(created.text, '%Y-%m-%dT%H:%M:%S.%fZ')
        expires_dt = datetime.strptime(expires.text, '%Y-%m-%dT%H:%M:%S.%fZ')

        # Verify 10 minute difference
        diff = (expires_dt - created_dt).total_seconds()
        assert 599 <= diff <= 601

    def test_create_timestamp_invalid_validity_raises_error(self):
        """Test creating timestamp with invalid validity raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        
        with pytest.raises(ValueError, match="Must be a positive integer"):
            builder._create_timestamp(0)
        
        with pytest.raises(ValueError, match="Must be a positive integer"):
            builder._create_timestamp(-5)


class TestEmbedInSOAPEnvelope:
    """Test embed_in_soap_envelope method."""

    def test_embed_success(self, signed_saml_assertion):
        """Test embedding WS-Security header in SOAP envelope."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)

        # Create dummy body
        body = etree.Element("TestBody")
        body.text = "Test content"

        envelope = builder.embed_in_soap_envelope(body, ws_security)

        # Verify envelope is SOAP-ENV:Envelope
        assert envelope.tag == f"{{{builder.SOAP_NS}}}Envelope"

        # Verify Header and Body present
        header = envelope.find(f".//{{{builder.SOAP_NS}}}Header")
        soap_body = envelope.find(f".//{{{builder.SOAP_NS}}}Body")
        assert header is not None
        assert soap_body is not None

        # Verify wsse:Security is first child of Header
        first_child = header[0]
        assert first_child.tag == f"{{{builder.WSSE_NS}}}Security"

        # Verify body content is in SOAP:Body
        body_content = soap_body[0]
        assert body_content.tag == "TestBody"
        assert body_content.text == "Test content"

    def test_embed_with_none_body_raises_error(self, signed_saml_assertion):
        """Test embedding with None body raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)

        with pytest.raises(ValueError, match="body parameter is required"):
            builder.embed_in_soap_envelope(None, ws_security)

    def test_embed_with_none_header_raises_error(self):
        """Test embedding with None header raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        body = etree.Element("TestBody")

        with pytest.raises(ValueError, match="ws_security_header parameter is required"):
            builder.embed_in_soap_envelope(body, None)


class TestAddWSAddressingHeaders:
    """Test add_ws_addressing_headers method."""

    def test_add_ws_addressing_headers_success(self, signed_saml_assertion):
        """Test adding WS-Addressing headers to SOAP header."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)
        body = etree.Element("TestBody")
        envelope = builder.embed_in_soap_envelope(body, ws_security)

        header = envelope.find(f".//{{{builder.SOAP_NS}}}Header")

        builder.add_ws_addressing_headers(
            header,
            action="urn:hl7-org:v3:PRPA_IN201301UV02",
            to="http://pix.example.com/pix/add"
        )

        # Verify Action element
        action_elem = header.find(f".//{{{builder.WSA_NS}}}Action")
        assert action_elem is not None
        assert action_elem.text == "urn:hl7-org:v3:PRPA_IN201301UV02"

        # Verify To element
        to_elem = header.find(f".//{{{builder.WSA_NS}}}To")
        assert to_elem is not None
        assert to_elem.text == "http://pix.example.com/pix/add"

        # Verify MessageID element
        message_id_elem = header.find(f".//{{{builder.WSA_NS}}}MessageID")
        assert message_id_elem is not None
        assert message_id_elem.text.startswith("urn:uuid:")

        # Verify ReplyTo element
        reply_to = header.find(f".//{{{builder.WSA_NS}}}ReplyTo")
        assert reply_to is not None
        address = reply_to.find(f".//{{{builder.WSA_NS}}}Address")
        assert address.text == "http://www.w3.org/2005/08/addressing/anonymous"

    def test_add_ws_addressing_headers_with_custom_message_id(self, signed_saml_assertion):
        """Test adding WS-Addressing headers with custom message ID."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)
        body = etree.Element("TestBody")
        envelope = builder.embed_in_soap_envelope(body, ws_security)

        header = envelope.find(f".//{{{builder.SOAP_NS}}}Header")

        custom_id = f"urn:uuid:{uuid.uuid4()}"
        builder.add_ws_addressing_headers(
            header,
            action="urn:test:action",
            to="http://test.com",
            message_id=custom_id
        )

        message_id_elem = header.find(f".//{{{builder.WSA_NS}}}MessageID")
        assert message_id_elem.text == custom_id

    def test_add_ws_addressing_headers_missing_action_raises_error(self, signed_saml_assertion):
        """Test adding WS-Addressing headers without action raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)
        body = etree.Element("TestBody")
        envelope = builder.embed_in_soap_envelope(body, ws_security)

        header = envelope.find(f".//{{{builder.SOAP_NS}}}Header")

        with pytest.raises(ValueError, match="action parameter is required"):
            builder.add_ws_addressing_headers(header, action="", to="http://test.com")

    def test_add_ws_addressing_headers_missing_to_raises_error(self, signed_saml_assertion):
        """Test adding WS-Addressing headers without 'to' raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)
        body = etree.Element("TestBody")
        envelope = builder.embed_in_soap_envelope(body, ws_security)

        header = envelope.find(f".//{{{builder.SOAP_NS}}}Header")

        with pytest.raises(ValueError, match="to parameter is required"):
            builder.add_ws_addressing_headers(header, action="urn:test", to="")


class TestCreatePIXAddSOAPEnvelope:
    """Test create_pix_add_soap_envelope method."""

    def test_create_pix_add_envelope_success(self, signed_saml_assertion):
        """Test creating complete PIX Add SOAP envelope."""
        builder = WSSecurityHeaderBuilder()

        # Create dummy PIX message
        pix_message = etree.Element("PRPA_IN201301UV02")
        pix_message.text = "PIX Add content"

        envelope_str = builder.create_pix_add_soap_envelope(
            signed_saml_assertion,
            pix_message,
            "http://pix.example.com/pix/add"
        )

        # Verify envelope is valid XML
        parsed = etree.fromstring(envelope_str.encode('utf-8'))
        assert parsed is not None

        # Verify structure
        assert 'Envelope' in parsed.tag

        # Verify WS-Addressing action for PIX Add
        action = parsed.find(f".//{{{builder.WSA_NS}}}Action")
        assert action.text == "urn:hl7-org:v3:PRPA_IN201301UV02"

    def test_create_pix_add_envelope_default_endpoint(self, signed_saml_assertion):
        """Test creating PIX Add envelope with default endpoint."""
        builder = WSSecurityHeaderBuilder()
        pix_message = etree.Element("PRPA_IN201301UV02")

        envelope_str = builder.create_pix_add_soap_envelope(
            signed_saml_assertion,
            pix_message
        )

        parsed = etree.fromstring(envelope_str.encode('utf-8'))
        to_elem = parsed.find(f".//{{{builder.WSA_NS}}}To")
        assert to_elem.text == "http://localhost:5000/pix/add"


class TestCreateITI41SOAPEnvelope:
    """Test create_iti41_soap_envelope method."""

    def test_create_iti41_envelope_success(self, signed_saml_assertion):
        """Test creating complete ITI-41 SOAP envelope."""
        builder = WSSecurityHeaderBuilder()

        # Create dummy ITI-41 request
        iti41_request = etree.Element("ProvideAndRegisterDocumentSetRequest")
        iti41_request.text = "ITI-41 content"

        envelope_str = builder.create_iti41_soap_envelope(
            signed_saml_assertion,
            iti41_request,
            "http://xds.example.com/iti41/submit"
        )

        # Verify envelope is valid XML
        parsed = etree.fromstring(envelope_str.encode('utf-8'))
        assert parsed is not None

        # Verify structure
        assert 'Envelope' in parsed.tag

        # Verify WS-Addressing action for ITI-41
        action = parsed.find(f".//{{{builder.WSA_NS}}}Action")
        assert action.text == "urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b"

    def test_create_iti41_envelope_default_endpoint(self, signed_saml_assertion):
        """Test creating ITI-41 envelope with default endpoint."""
        builder = WSSecurityHeaderBuilder()
        iti41_request = etree.Element("ProvideAndRegisterDocumentSetRequest")

        envelope_str = builder.create_iti41_soap_envelope(
            signed_saml_assertion,
            iti41_request
        )

        parsed = etree.fromstring(envelope_str.encode('utf-8'))
        to_elem = parsed.find(f".//{{{builder.WSA_NS}}}To")
        assert to_elem.text == "http://localhost:5000/iti41/submit"


class TestValidateWSSecurityHeader:
    """Test validate_ws_security_header method."""

    def test_validate_valid_header(self, signed_saml_assertion):
        """Test validating a valid WS-Security header returns True."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)

        result = builder.validate_ws_security_header(ws_security)
        assert result is True

    def test_validate_none_header_raises_error(self):
        """Test validating None header raises ValueError."""
        builder = WSSecurityHeaderBuilder()

        with pytest.raises(ValueError, match="Header is None"):
            builder.validate_ws_security_header(None)

    def test_validate_wrong_element_raises_error(self):
        """Test validating wrong element type raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        wrong_element = etree.Element("InvalidElement")

        with pytest.raises(ValueError, match="Invalid root element"):
            builder.validate_ws_security_header(wrong_element)

    def test_validate_missing_must_understand_raises_error(self, signed_saml_assertion):
        """Test validating header without mustUnderstand raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        
        # Create header without mustUnderstand
        security = etree.Element(f"{{{builder.WSSE_NS}}}Security")
        timestamp = builder._create_timestamp(5)
        security.append(timestamp)
        
        saml_assertion = etree.fromstring(signed_saml_assertion.xml_content.encode('utf-8'))
        security.append(saml_assertion)

        with pytest.raises(ValueError, match="mustUnderstand"):
            builder.validate_ws_security_header(security)

    def test_validate_missing_timestamp_raises_error(self, signed_saml_assertion):
        """Test validating header without timestamp raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        
        # Create header without timestamp
        security = etree.Element(
            f"{{{builder.WSSE_NS}}}Security",
            attrib={f"{{{builder.SOAP_NS}}}mustUnderstand": "1"}
        )
        
        saml_assertion = etree.fromstring(signed_saml_assertion.xml_content.encode('utf-8'))
        security.append(saml_assertion)

        with pytest.raises(ValueError, match="Missing wsu:Timestamp"):
            builder.validate_ws_security_header(security)

    def test_validate_missing_saml_raises_error(self):
        """Test validating header without SAML assertion raises ValueError."""
        builder = WSSecurityHeaderBuilder()
        
        # Create header without SAML
        security = etree.Element(
            f"{{{builder.WSSE_NS}}}Security",
            attrib={f"{{{builder.SOAP_NS}}}mustUnderstand": "1"}
        )
        timestamp = builder._create_timestamp(5)
        security.append(timestamp)

        with pytest.raises(ValueError, match="Missing saml:Assertion"):
            builder.validate_ws_security_header(security)

    def test_validate_unsigned_saml_warns(self, unsigned_saml_assertion):
        """Test validating header with unsigned SAML logs warning but passes."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(unsigned_saml_assertion)

        # Should still pass validation (warning logged)
        result = builder.validate_ws_security_header(ws_security)
        assert result is True


class TestNamespaceDeclarations:
    """Test proper namespace declarations in generated XML."""

    def test_namespace_constants(self):
        """Test namespace constants are defined correctly."""
        builder = WSSecurityHeaderBuilder()
        
        assert builder.WSSE_NS == "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
        assert builder.WSU_NS == "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
        assert builder.WSA_NS == "http://www.w3.org/2005/08/addressing"
        assert builder.SOAP_NS == "http://www.w3.org/2003/05/soap-envelope"
        assert builder.SAML_NS == "urn:oasis:names:tc:SAML:2.0:assertion"
        assert builder.DS_NS == "http://www.w3.org/2000/09/xmldsig#"

    def test_envelope_namespace_declarations(self, signed_saml_assertion):
        """Test SOAP envelope has correct namespace declarations."""
        builder = WSSecurityHeaderBuilder()
        ws_security = builder.build_ws_security_header(signed_saml_assertion)
        body = etree.Element("TestBody")
        envelope = builder.embed_in_soap_envelope(body, ws_security)

        # Serialize and check namespace prefixes are present
        envelope_str = etree.tostring(envelope, encoding='unicode')
        
        assert 'xmlns:SOAP-ENV' in envelope_str or 'SOAP-ENV:' in envelope_str
        assert 'xmlns:wsse' in envelope_str or 'wsse:' in envelope_str
        assert 'xmlns:wsu' in envelope_str or 'wsu:' in envelope_str
