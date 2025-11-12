"""Unit tests for programmatic SAML generation module.

Tests the SAMLProgrammaticGenerator class and related functions for generating
SAML 2.0 assertions programmatically without templates.
"""

import pytest
from datetime import datetime, timezone
from lxml import etree
from pathlib import Path

from ihe_test_util.saml.programmatic_generator import (
    SAMLProgrammaticGenerator,
    generate_assertion_id,
    generate_saml_timestamps,
    _validate_required_parameters,
    _build_assertion_element,
    _add_subject_element,
    _add_conditions_element,
    _add_authn_statement,
    _add_attribute_statement,
    _canonicalize_assertion,
)
from ihe_test_util.models.saml import SAMLGenerationMethod
from ihe_test_util.saml.certificate_manager import load_certificate


class TestGenerateAssertionId:
    """Tests for generate_assertion_id function."""

    def test_assertion_id_format(self):
        """Test assertion ID has correct format."""
        assertion_id = generate_assertion_id()
        assert assertion_id.startswith("_")
        assert len(assertion_id) == 33  # _ + 32 hex chars

    def test_assertion_id_uniqueness(self):
        """Test assertion IDs are unique across multiple generations."""
        ids = set()
        for _ in range(100):
            assertion_id = generate_assertion_id()
            ids.add(assertion_id)
        
        assert len(ids) == 100  # All unique

    def test_assertion_id_valid_xml_id(self):
        """Test assertion ID is valid XML ID type."""
        assertion_id = generate_assertion_id()
        # XML ID must start with letter or underscore
        assert assertion_id[0] in "_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class TestGenerateSamlTimestamps:
    """Tests for generate_saml_timestamps function."""

    def test_timestamp_keys(self):
        """Test timestamp dict has all required keys."""
        timestamps = generate_saml_timestamps()
        assert "issue_instant" in timestamps
        assert "not_before" in timestamps
        assert "not_on_or_after" in timestamps

    def test_timestamp_format(self):
        """Test timestamps are in ISO 8601 format with Z suffix."""
        timestamps = generate_saml_timestamps()
        for key, value in timestamps.items():
            assert value.endswith("Z")
            # Verify parseable as ISO 8601
            datetime.fromisoformat(value.replace("Z", "+00:00"))

    def test_default_validity_period(self):
        """Test default validity period is 5 minutes."""
        timestamps = generate_saml_timestamps()
        issue_instant = datetime.fromisoformat(
            timestamps["issue_instant"].replace("Z", "+00:00")
        )
        not_on_or_after = datetime.fromisoformat(
            timestamps["not_on_or_after"].replace("Z", "+00:00")
        )
        
        delta = not_on_or_after - issue_instant
        assert delta.total_seconds() == 300  # 5 minutes

    def test_custom_validity_period(self):
        """Test custom validity period works correctly."""
        timestamps = generate_saml_timestamps(validity_minutes=10)
        issue_instant = datetime.fromisoformat(
            timestamps["issue_instant"].replace("Z", "+00:00")
        )
        not_on_or_after = datetime.fromisoformat(
            timestamps["not_on_or_after"].replace("Z", "+00:00")
        )
        
        delta = not_on_or_after - issue_instant
        assert delta.total_seconds() == 600  # 10 minutes

    def test_not_before_equals_issue_instant(self):
        """Test not_before equals issue_instant."""
        timestamps = generate_saml_timestamps()
        assert timestamps["not_before"] == timestamps["issue_instant"]


class TestValidateRequiredParameters:
    """Tests for _validate_required_parameters function."""

    def test_valid_parameters(self):
        """Test validation passes for valid parameters."""
        # Should not raise
        _validate_required_parameters(
            "user@example.com", "https://idp.example.com", "https://sp.example.com"
        )

    def test_empty_subject_raises(self):
        """Test empty subject raises ValueError."""
        with pytest.raises(ValueError, match="Subject must be a non-empty string"):
            _validate_required_parameters("", "https://idp.example.com", "https://sp.example.com")

    def test_empty_issuer_raises(self):
        """Test empty issuer raises ValueError."""
        with pytest.raises(ValueError, match="Issuer must be a non-empty string"):
            _validate_required_parameters("user@example.com", "", "https://sp.example.com")

    def test_empty_audience_raises(self):
        """Test empty audience raises ValueError."""
        with pytest.raises(ValueError, match="Audience must be a non-empty string"):
            _validate_required_parameters("user@example.com", "https://idp.example.com", "")

    def test_none_subject_raises(self):
        """Test None subject raises ValueError."""
        with pytest.raises(ValueError, match="Subject must be a non-empty string"):
            _validate_required_parameters(None, "https://idp.example.com", "https://sp.example.com")


class TestBuildAssertionElement:
    """Tests for _build_assertion_element function."""

    def test_creates_assertion_element(self):
        """Test creates Assertion element with correct attributes."""
        assertion = _build_assertion_element(
            "_abc123", "2025-11-11T12:00:00Z", "https://idp.example.com"
        )
        
        assert assertion.tag.endswith("}Assertion")
        assert assertion.get("ID") == "_abc123"
        assert assertion.get("Version") == "2.0"
        assert assertion.get("IssueInstant") == "2025-11-11T12:00:00Z"

    def test_includes_issuer_element(self):
        """Test Issuer element is included."""
        assertion = _build_assertion_element(
            "_abc123", "2025-11-11T12:00:00Z", "https://idp.example.com"
        )
        
        issuer_elem = assertion.find(".//{*}Issuer")
        assert issuer_elem is not None
        assert issuer_elem.text == "https://idp.example.com"

    def test_saml_namespace_declared(self):
        """Test SAML namespace is properly declared."""
        assertion = _build_assertion_element(
            "_abc123", "2025-11-11T12:00:00Z", "https://idp.example.com"
        )
        
        assert "urn:oasis:names:tc:SAML:2.0:assertion" in assertion.nsmap.values()


class TestAddSubjectElement:
    """Tests for _add_subject_element function."""

    def test_adds_subject_element(self):
        """Test Subject element is added."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_subject_element(assertion, "user@example.com", "2025-11-11T12:05:00Z")
        
        subject_elem = assertion.find(".//{*}Subject")
        assert subject_elem is not None

    def test_includes_name_id(self):
        """Test NameID element is included with correct value."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_subject_element(assertion, "user@example.com", "2025-11-11T12:05:00Z")
        
        name_id = assertion.find(".//{*}NameID")
        assert name_id is not None
        assert name_id.text == "user@example.com"

    def test_includes_subject_confirmation(self):
        """Test SubjectConfirmation with bearer method is included."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_subject_element(assertion, "user@example.com", "2025-11-11T12:05:00Z")
        
        subject_confirmation = assertion.find(".//{*}SubjectConfirmation")
        assert subject_confirmation is not None
        assert subject_confirmation.get("Method") == "urn:oasis:names:tc:SAML:2.0:cm:bearer"

    def test_includes_subject_confirmation_data(self):
        """Test SubjectConfirmationData with NotOnOrAfter is included."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_subject_element(assertion, "user@example.com", "2025-11-11T12:05:00Z")
        
        subject_conf_data = assertion.find(".//{*}SubjectConfirmationData")
        assert subject_conf_data is not None
        assert subject_conf_data.get("NotOnOrAfter") == "2025-11-11T12:05:00Z"


class TestAddConditionsElement:
    """Tests for _add_conditions_element function."""

    def test_adds_conditions_element(self):
        """Test Conditions element is added with timestamps."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_conditions_element(
            assertion, "2025-11-11T12:00:00Z", "2025-11-11T12:05:00Z", "https://sp.example.com"
        )
        
        conditions = assertion.find(".//{*}Conditions")
        assert conditions is not None
        assert conditions.get("NotBefore") == "2025-11-11T12:00:00Z"
        assert conditions.get("NotOnOrAfter") == "2025-11-11T12:05:00Z"

    def test_includes_audience_restriction(self):
        """Test AudienceRestriction is included."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_conditions_element(
            assertion, "2025-11-11T12:00:00Z", "2025-11-11T12:05:00Z", "https://sp.example.com"
        )
        
        audience_restriction = assertion.find(".//{*}AudienceRestriction")
        assert audience_restriction is not None

    def test_includes_audience(self):
        """Test Audience element with correct value is included."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_conditions_element(
            assertion, "2025-11-11T12:00:00Z", "2025-11-11T12:05:00Z", "https://sp.example.com"
        )
        
        audience = assertion.find(".//{*}Audience")
        assert audience is not None
        assert audience.text == "https://sp.example.com"


class TestAddAuthnStatement:
    """Tests for _add_authn_statement function."""

    def test_adds_authn_statement(self):
        """Test AuthnStatement element is added."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_authn_statement(assertion, "2025-11-11T12:00:00Z", "_abc123")
        
        authn_stmt = assertion.find(".//{*}AuthnStatement")
        assert authn_stmt is not None
        assert authn_stmt.get("AuthnInstant") == "2025-11-11T12:00:00Z"
        assert authn_stmt.get("SessionIndex") == "_abc123"

    def test_includes_authn_context(self):
        """Test AuthnContext is included."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_authn_statement(assertion, "2025-11-11T12:00:00Z", "_abc123")
        
        authn_context = assertion.find(".//{*}AuthnContext")
        assert authn_context is not None

    def test_includes_authn_context_class_ref(self):
        """Test AuthnContextClassRef with PasswordProtectedTransport is included."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_authn_statement(assertion, "2025-11-11T12:00:00Z", "_abc123")
        
        authn_context_class_ref = assertion.find(".//{*}AuthnContextClassRef")
        assert authn_context_class_ref is not None
        assert authn_context_class_ref.text == "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"


class TestAddAttributeStatement:
    """Tests for _add_attribute_statement function."""

    def test_no_attributes_skips_statement(self):
        """Test AttributeStatement is not added when no attributes provided."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_attribute_statement(assertion, {})
        
        attr_stmt = assertion.find(".//{*}AttributeStatement")
        assert attr_stmt is None

    def test_adds_single_valued_attribute(self):
        """Test single-valued attribute is added correctly."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_attribute_statement(assertion, {"username": "jsmith"})
        
        attr_stmt = assertion.find(".//{*}AttributeStatement")
        assert attr_stmt is not None
        
        attr = attr_stmt.find(".//{*}Attribute[@Name='username']")
        assert attr is not None
        
        attr_value = attr.find(".//{*}AttributeValue")
        assert attr_value is not None
        assert attr_value.text == "jsmith"

    def test_adds_multi_valued_attribute(self):
        """Test multi-valued attribute is added correctly."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_attribute_statement(assertion, {"roles": ["physician", "admin"]})
        
        attr_stmt = assertion.find(".//{*}AttributeStatement")
        assert attr_stmt is not None
        
        attr = attr_stmt.find(".//{*}Attribute[@Name='roles']")
        assert attr is not None
        
        attr_values = attr.findall(".//{*}AttributeValue")
        assert len(attr_values) == 2
        assert attr_values[0].text == "physician"
        assert attr_values[1].text == "admin"

    def test_adds_multiple_attributes(self):
        """Test multiple attributes are added correctly."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        _add_attribute_statement(assertion, {
            "username": "jsmith",
            "organization": "Hospital A",
            "department": "Cardiology"
        })
        
        attr_stmt = assertion.find(".//{*}AttributeStatement")
        assert attr_stmt is not None
        
        attrs = attr_stmt.findall(".//{*}Attribute")
        assert len(attrs) == 3


class TestCanonicalizeAssertion:
    """Tests for _canonicalize_assertion function."""

    def test_returns_string(self):
        """Test canonicalization returns string."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        canonical = _canonicalize_assertion(assertion)
        assert isinstance(canonical, str)

    def test_canonical_xml_parseable(self):
        """Test canonicalized XML is parseable."""
        assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        canonical = _canonicalize_assertion(assertion)
        
        # Should be parseable
        tree = etree.fromstring(canonical.encode("utf-8"))
        assert tree.tag.endswith("}Assertion")


class TestSAMLProgrammaticGenerator:
    """Tests for SAMLProgrammaticGenerator class."""

    def test_initialization_without_certificate(self):
        """Test generator can be initialized without certificate."""
        generator = SAMLProgrammaticGenerator()
        assert generator.cert_bundle is None

    def test_initialization_with_certificate(self):
        """Test generator can be initialized with certificate."""
        cert_bundle = load_certificate(Path("tests/fixtures/test_cert.pem"))
        generator = SAMLProgrammaticGenerator(cert_bundle=cert_bundle)
        assert generator.cert_bundle is not None

    def test_generate_with_required_params_only(self):
        """Test SAML generation with only required parameters."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com"
        )
        
        assert assertion.subject == "user@example.com"
        assert assertion.issuer == "https://idp.example.com"
        assert assertion.audience == "https://sp.example.com"
        assert assertion.generation_method == SAMLGenerationMethod.PROGRAMMATIC
        assert assertion.assertion_id.startswith("_")
        assert len(assertion.assertion_id) == 33

    def test_generate_with_all_params(self):
        """Test SAML generation with all optional parameters."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com",
            attributes={"role": "physician", "organization": "Hospital A"},
            validity_minutes=10
        )
        
        assert assertion.subject == "user@example.com"
        assert assertion.generation_method == SAMLGenerationMethod.PROGRAMMATIC
        assert "<saml:AttributeStatement>" in assertion.xml_content
        assert "physician" in assertion.xml_content

    def test_generate_xml_content_valid(self):
        """Test generated XML content is well-formed."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com"
        )
        
        # Parse to verify well-formed
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        assert tree.tag.endswith("}Assertion")

    def test_generate_includes_required_elements(self):
        """Test generated SAML includes all required elements."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com"
        )
        
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        
        # Check required elements
        assert tree.find(".//{*}Issuer") is not None
        assert tree.find(".//{*}Subject") is not None
        assert tree.find(".//{*}Conditions") is not None
        assert tree.find(".//{*}AuthnStatement") is not None

    def test_generate_validity_period(self):
        """Test custom validity period is applied."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com",
            validity_minutes=10
        )
        
        delta = assertion.not_on_or_after - assertion.issue_instant
        assert delta.total_seconds() == 600  # 10 minutes

    def test_generate_invalid_validity_minutes_raises(self):
        """Test invalid validity_minutes raises ValueError."""
        generator = SAMLProgrammaticGenerator()
        
        with pytest.raises(ValueError, match="validity_minutes must be a positive integer"):
            generator.generate(
                subject="user@example.com",
                issuer="https://idp.example.com",
                audience="https://sp.example.com",
                validity_minutes=0
            )

    def test_generate_empty_subject_raises(self):
        """Test empty subject raises ValueError."""
        generator = SAMLProgrammaticGenerator()
        
        with pytest.raises(ValueError, match="Subject must be a non-empty string"):
            generator.generate(
                subject="",
                issuer="https://idp.example.com",
                audience="https://sp.example.com"
            )

    def test_generate_with_certificate_auto_extracts_issuer(self):
        """Test generate_with_certificate extracts issuer from certificate."""
        cert_bundle = load_certificate(Path("tests/fixtures/test_cert.pem"))
        generator = SAMLProgrammaticGenerator(cert_bundle=cert_bundle)
        
        assertion = generator.generate_with_certificate(
            subject="user@example.com",
            audience="https://sp.example.com"
        )
        
        # Issuer should be from certificate
        assert assertion.issuer == cert_bundle.info.subject
        assert assertion.certificate_subject == cert_bundle.info.subject

    def test_generate_with_certificate_no_bundle_raises(self):
        """Test generate_with_certificate without bundle raises ValueError."""
        generator = SAMLProgrammaticGenerator()
        
        with pytest.raises(ValueError, match="No certificate bundle provided"):
            generator.generate_with_certificate(
                subject="user@example.com",
                audience="https://sp.example.com"
            )

    def test_generate_with_certificate_provided_bundle(self):
        """Test generate_with_certificate with provided bundle parameter."""
        cert_bundle = load_certificate(Path("tests/fixtures/test_cert.pem"))
        generator = SAMLProgrammaticGenerator()
        
        assertion = generator.generate_with_certificate(
            subject="user@example.com",
            audience="https://sp.example.com",
            cert_bundle=cert_bundle
        )
        
        assert assertion.issuer == cert_bundle.info.subject

    def test_generate_signature_empty(self):
        """Test signature field is empty (signing is Story 4.4)."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com"
        )
        
        assert assertion.signature == ""

    def test_generate_multi_valued_attributes(self):
        """Test multi-valued attributes are handled correctly."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com",
            attributes={"roles": ["physician", "admin", "researcher"]}
        )
        
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        attr_values = tree.findall(".//{*}Attribute[@Name='roles']/{*}AttributeValue")
        assert len(attr_values) == 3
        assert attr_values[0].text == "physician"
        assert attr_values[1].text == "admin"
        assert attr_values[2].text == "researcher"

    def test_generate_timestamps_are_datetime_objects(self):
        """Test returned timestamps are datetime objects."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com"
        )
        
        assert isinstance(assertion.issue_instant, datetime)
        assert isinstance(assertion.not_before, datetime)
        assert isinstance(assertion.not_on_or_after, datetime)

    def test_generate_timestamps_are_utc(self):
        """Test timestamps are in UTC timezone."""
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com"
        )
        
        assert assertion.issue_instant.tzinfo == timezone.utc
        assert assertion.not_before.tzinfo == timezone.utc
        assert assertion.not_on_or_after.tzinfo == timezone.utc
