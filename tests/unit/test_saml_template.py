"""Unit tests for SAML template loading and personalization.

Tests the SAML template loader module including:
- Template loading and validation
- Placeholder extraction
- Timestamp generation
- Assertion ID generation
- Template personalization
- Canonicalization
- SAMLTemplatePersonalizer class
"""

import pytest
from datetime import datetime
from pathlib import Path

from ihe_test_util.saml.template_loader import (
    load_saml_template,
    validate_saml_template,
    extract_saml_placeholders,
    generate_saml_timestamps,
    generate_assertion_id,
    personalize_saml_template,
    canonicalize_saml,
    SAMLTemplatePersonalizer,
    ValidationResult,
)
from ihe_test_util.utils.exceptions import (
    MalformedXMLError,
    MissingPlaceholderValueError,
    TemplateLoadError,
)


# Fixtures

@pytest.fixture
def test_template_path():
    """Path to test SAML template fixture."""
    return Path("tests/fixtures/test_saml_template.xml")


@pytest.fixture
def minimal_template_path():
    """Path to minimal SAML template."""
    return Path("templates/saml-minimal.xml")


@pytest.fixture
def standard_template_path():
    """Path to standard SAML template."""
    return Path("templates/saml-template.xml")


@pytest.fixture
def extended_template_path():
    """Path to extended SAML template with attributes."""
    return Path("templates/saml-with-attributes.xml")


@pytest.fixture
def valid_saml_xml():
    """Valid SAML assertion XML."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_abc123"
                IssueInstant="2025-11-11T12:00:00Z"
                Version="2.0">
    <saml:Issuer>https://idp.example.com</saml:Issuer>
    <saml:Subject>
        <saml:NameID>user@example.com</saml:NameID>
    </saml:Subject>
</saml:Assertion>"""


@pytest.fixture
def invalid_saml_xml():
    """Invalid SAML assertion XML (missing required elements)."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_abc123"
                IssueInstant="2025-11-11T12:00:00Z"
                Version="2.0">
    <saml:Issuer>https://idp.example.com</saml:Issuer>
    <!-- Missing Subject element -->
</saml:Assertion>"""


@pytest.fixture
def basic_parameters():
    """Basic SAML parameters for personalization."""
    return {
        "issuer": "https://idp.example.com",
        "subject": "user@example.com",
        "audience": "https://sp.example.com",
        "attr_username": "testuser",
        "attr_role": "physician",
    }


# Test load_saml_template


def test_load_saml_template_valid(test_template_path):
    """Test loading a valid SAML template."""
    template = load_saml_template(test_template_path)
    
    assert template is not None
    assert isinstance(template, str)
    assert "{{assertion_id}}" in template
    assert "{{issuer}}" in template
    assert "{{subject}}" in template
    assert "saml:Assertion" in template


def test_load_saml_template_file_not_found():
    """Test loading non-existent template file."""
    with pytest.raises(TemplateLoadError) as exc_info:
        load_saml_template(Path("nonexistent/template.xml"))
    
    assert "not found" in str(exc_info.value).lower()


def test_load_saml_template_malformed_xml(tmp_path):
    """Test loading malformed XML template."""
    malformed_file = tmp_path / "malformed.xml"
    malformed_file.write_text("<saml:Assertion>unclosed tag")
    
    with pytest.raises(MalformedXMLError) as exc_info:
        load_saml_template(malformed_file)
    
    assert "malformed" in str(exc_info.value).lower()


# Test validate_saml_template


def test_validate_saml_template_valid(valid_saml_xml):
    """Test validating a valid SAML template."""
    result = validate_saml_template(valid_saml_xml)
    
    assert isinstance(result, ValidationResult)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_saml_template_missing_subject(invalid_saml_xml):
    """Test validating SAML template with missing required element."""
    result = validate_saml_template(invalid_saml_xml)
    
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert any("Subject" in error for error in result.errors)


def test_validate_saml_template_missing_namespace():
    """Test validating SAML template without SAML namespace."""
    xml_without_ns = """<?xml version="1.0" encoding="UTF-8"?>
<Assertion ID="_abc123" IssueInstant="2025-11-11T12:00:00Z" Version="2.0">
    <Issuer>https://idp.example.com</Issuer>
    <Subject><NameID>user</NameID></Subject>
</Assertion>"""
    
    result = validate_saml_template(xml_without_ns)
    
    assert result.is_valid is False
    assert any("namespace" in error.lower() for error in result.errors)


def test_validate_saml_template_with_placeholders(test_template_path):
    """Test validating SAML template with placeholders."""
    template = load_saml_template(test_template_path)
    result = validate_saml_template(template)
    
    # Should be valid even with placeholders
    assert result.is_valid is True


# Test extract_saml_placeholders


def test_extract_saml_placeholders(test_template_path):
    """Test extracting placeholders from SAML template."""
    template = load_saml_template(test_template_path)
    placeholders = extract_saml_placeholders(template)
    
    assert isinstance(placeholders, set)
    assert "assertion_id" in placeholders
    assert "issuer" in placeholders
    assert "subject" in placeholders
    assert "audience" in placeholders
    assert "issue_instant" in placeholders
    assert "not_before" in placeholders
    assert "not_on_or_after" in placeholders
    assert "attr_username" in placeholders
    assert "attr_role" in placeholders


def test_extract_saml_placeholders_empty():
    """Test extracting placeholders from XML without placeholders."""
    xml_without_placeholders = """<?xml version="1.0" encoding="UTF-8"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_abc123"
                IssueInstant="2025-11-11T12:00:00Z"
                Version="2.0">
    <saml:Issuer>https://idp.example.com</saml:Issuer>
</saml:Assertion>"""
    
    placeholders = extract_saml_placeholders(xml_without_placeholders)
    
    assert isinstance(placeholders, set)
    assert len(placeholders) == 0


def test_extract_saml_placeholders_duplicates():
    """Test that duplicate placeholders are deduplicated."""
    xml_with_duplicates = """<root>
        {{field1}} {{field2}} {{field1}} {{field3}} {{field2}}
    </root>"""
    
    placeholders = extract_saml_placeholders(xml_with_duplicates)
    
    assert len(placeholders) == 3
    assert placeholders == {"field1", "field2", "field3"}


# Test generate_saml_timestamps


def test_generate_saml_timestamps_default():
    """Test generating SAML timestamps with default validity."""
    timestamps = generate_saml_timestamps()
    
    assert isinstance(timestamps, dict)
    assert "issue_instant" in timestamps
    assert "not_before" in timestamps
    assert "not_on_or_after" in timestamps
    
    # Check format (ISO 8601 with Z suffix)
    assert timestamps["issue_instant"].endswith("Z")
    assert timestamps["not_before"].endswith("Z")
    assert timestamps["not_on_or_after"].endswith("Z")
    
    # Verify format can be parsed
    issue_instant = datetime.fromisoformat(
        timestamps["issue_instant"].replace("Z", "+00:00")
    )
    not_before = datetime.fromisoformat(
        timestamps["not_before"].replace("Z", "+00:00")
    )
    not_on_or_after = datetime.fromisoformat(
        timestamps["not_on_or_after"].replace("Z", "+00:00")
    )
    
    # Check validity period (default 5 minutes = 300 seconds)
    delta = (not_on_or_after - issue_instant).total_seconds()
    assert 299 <= delta <= 301  # Allow 1 second tolerance


def test_generate_saml_timestamps_custom_validity():
    """Test generating SAML timestamps with custom validity period."""
    timestamps = generate_saml_timestamps(validity_minutes=10)
    
    issue_instant = datetime.fromisoformat(
        timestamps["issue_instant"].replace("Z", "+00:00")
    )
    not_on_or_after = datetime.fromisoformat(
        timestamps["not_on_or_after"].replace("Z", "+00:00")
    )
    
    # Check validity period (10 minutes = 600 seconds)
    delta = (not_on_or_after - issue_instant).total_seconds()
    assert 599 <= delta <= 601  # Allow 1 second tolerance


def test_generate_saml_timestamps_issue_instant_equals_not_before():
    """Test that issue_instant equals not_before."""
    timestamps = generate_saml_timestamps()
    
    assert timestamps["issue_instant"] == timestamps["not_before"]


# Test generate_assertion_id


def test_generate_assertion_id_format():
    """Test that assertion ID has correct format."""
    assertion_id = generate_assertion_id()
    
    assert isinstance(assertion_id, str)
    assert assertion_id.startswith("_")
    assert len(assertion_id) == 33  # _ + 32 hex characters


def test_generate_assertion_id_uniqueness():
    """Test that assertion IDs are unique."""
    ids = set()
    for _ in range(100):
        assertion_id = generate_assertion_id()
        ids.add(assertion_id)
    
    # All 100 IDs should be unique
    assert len(ids) == 100


def test_generate_assertion_id_valid_xml_id():
    """Test that assertion ID is valid XML ID type."""
    assertion_id = generate_assertion_id()
    
    # XML ID must start with letter or underscore
    assert assertion_id[0] in "_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    
    # Rest should be alphanumeric or underscore/hyphen
    for char in assertion_id[1:]:
        assert char.isalnum() or char in "_-"


# Test personalize_saml_template


def test_personalize_saml_template_basic(test_template_path, basic_parameters):
    """Test basic SAML template personalization."""
    saml_xml = personalize_saml_template(test_template_path, basic_parameters)
    
    assert isinstance(saml_xml, str)
    assert "https://idp.example.com" in saml_xml
    assert "user@example.com" in saml_xml
    assert "https://sp.example.com" in saml_xml
    assert "testuser" in saml_xml
    assert "physician" in saml_xml
    
    # Placeholders should be replaced
    assert "{{issuer}}" not in saml_xml
    assert "{{subject}}" not in saml_xml
    assert "{{audience}}" not in saml_xml


def test_personalize_saml_template_auto_generates_assertion_id(
    test_template_path, basic_parameters
):
    """Test that assertion ID is auto-generated if not provided."""
    saml_xml = personalize_saml_template(test_template_path, basic_parameters)
    
    # Should contain an assertion ID starting with _
    assert 'ID="_' in saml_xml
    assert "{{assertion_id}}" not in saml_xml


def test_personalize_saml_template_auto_generates_timestamps(
    test_template_path, basic_parameters
):
    """Test that timestamps are auto-generated if not provided."""
    saml_xml = personalize_saml_template(test_template_path, basic_parameters)
    
    # Should contain ISO 8601 timestamps with Z suffix
    assert "IssueInstant=" in saml_xml
    assert "NotBefore=" in saml_xml
    assert "NotOnOrAfter=" in saml_xml
    
    # Placeholders should be replaced
    assert "{{issue_instant}}" not in saml_xml
    assert "{{not_before}}" not in saml_xml
    assert "{{not_on_or_after}}" not in saml_xml


def test_personalize_saml_template_uses_provided_timestamps(
    test_template_path, basic_parameters
):
    """Test that provided timestamps are used instead of auto-generation."""
    basic_parameters.update({
        "assertion_id": "_custom123",
        "issue_instant": "2025-01-01T00:00:00Z",
        "not_before": "2025-01-01T00:00:00Z",
        "not_on_or_after": "2025-01-01T00:05:00Z",
    })
    
    saml_xml = personalize_saml_template(test_template_path, basic_parameters)
    
    assert 'ID="_custom123"' in saml_xml
    assert 'IssueInstant="2025-01-01T00:00:00Z"' in saml_xml
    assert 'NotBefore="2025-01-01T00:00:00Z"' in saml_xml
    assert 'NotOnOrAfter="2025-01-01T00:05:00Z"' in saml_xml


def test_personalize_saml_template_custom_validity(
    test_template_path, basic_parameters
):
    """Test personalization with custom validity period."""
    saml_xml = personalize_saml_template(
        test_template_path, basic_parameters, validity_minutes=10
    )
    
    # Extract timestamps (simplified check)
    assert "NotOnOrAfter=" in saml_xml


def test_personalize_saml_template_missing_required_parameter(test_template_path):
    """Test that missing required parameters raise error."""
    incomplete_params = {
        "issuer": "https://idp.example.com",
        # Missing subject and audience
    }
    
    with pytest.raises(MissingPlaceholderValueError) as exc_info:
        personalize_saml_template(test_template_path, incomplete_params)
    
    error_msg = str(exc_info.value)
    assert "missing" in error_msg.lower()
    # Should mention the missing fields
    assert "subject" in error_msg or "audience" in error_msg


def test_personalize_saml_template_invalid_template(tmp_path):
    """Test personalizing invalid template raises error."""
    invalid_template = tmp_path / "invalid.xml"
    invalid_template.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="{{assertion_id}}"
                IssueInstant="{{issue_instant}}"
                Version="2.0">
    <saml:Issuer>{{issuer}}</saml:Issuer>
    <!-- Missing Subject element -->
</saml:Assertion>""")
    
    params = {
        "issuer": "https://idp.example.com",
        "assertion_id": "_abc123",
        "issue_instant": "2025-11-11T12:00:00Z",
    }
    
    with pytest.raises(TemplateLoadError) as exc_info:
        personalize_saml_template(invalid_template, params)
    
    assert "invalid" in str(exc_info.value).lower()


# Test canonicalize_saml


def test_canonicalize_saml_valid(valid_saml_xml):
    """Test canonicalizing valid SAML XML."""
    canonical = canonicalize_saml(valid_saml_xml)
    
    assert isinstance(canonical, str)
    assert len(canonical) > 0
    # Canonical XML should still contain the main elements
    assert "<saml:Assertion" in canonical
    assert "<saml:Issuer>" in canonical


def test_canonicalize_saml_removes_whitespace():
    """Test that canonicalization normalizes whitespace."""
    xml_with_whitespace = """<?xml version="1.0" encoding="UTF-8"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
    
    <saml:Issuer>    https://idp.example.com    </saml:Issuer>
    
    <saml:Subject>
        <saml:NameID>user</saml:NameID>
    </saml:Subject>
</saml:Assertion>"""
    
    canonical = canonicalize_saml(xml_with_whitespace)
    
    # Canonical form should normalize whitespace
    assert canonical is not None


def test_canonicalize_saml_malformed():
    """Test that canonicalizing malformed XML raises error."""
    malformed_xml = "<saml:Assertion>unclosed tag"
    
    with pytest.raises(MalformedXMLError):
        canonicalize_saml(malformed_xml)


# Test SAMLTemplatePersonalizer class


def test_saml_template_personalizer_init():
    """Test SAMLTemplatePersonalizer initialization."""
    personalizer = SAMLTemplatePersonalizer()
    
    assert personalizer is not None
    assert personalizer.cache_size == 0


def test_saml_template_personalizer_init_cache_disabled():
    """Test SAMLTemplatePersonalizer with caching disabled."""
    personalizer = SAMLTemplatePersonalizer(template_cache_enabled=False)
    
    assert personalizer is not None


def test_saml_template_personalizer_load_template(
    test_template_path,
):
    """Test loading template with personalizer."""
    personalizer = SAMLTemplatePersonalizer()
    template = personalizer.load_template(test_template_path)
    
    assert isinstance(template, str)
    assert "{{assertion_id}}" in template


def test_saml_template_personalizer_caching(test_template_path):
    """Test that templates are cached."""
    personalizer = SAMLTemplatePersonalizer(template_cache_enabled=True)
    
    # First load
    template1 = personalizer.load_template(test_template_path)
    assert personalizer.cache_size == 1
    
    # Second load (should hit cache)
    template2 = personalizer.load_template(test_template_path)
    assert personalizer.cache_size == 1
    
    # Templates should be identical
    assert template1 == template2


def test_saml_template_personalizer_no_caching(test_template_path):
    """Test that caching can be disabled."""
    personalizer = SAMLTemplatePersonalizer(template_cache_enabled=False)
    
    # Load twice
    personalizer.load_template(test_template_path)
    personalizer.load_template(test_template_path)
    
    # Cache should remain empty
    assert personalizer.cache_size == 0


def test_saml_template_personalizer_personalize(
    test_template_path, basic_parameters
):
    """Test personalize method."""
    personalizer = SAMLTemplatePersonalizer()
    saml_xml = personalizer.personalize(test_template_path, basic_parameters)
    
    assert isinstance(saml_xml, str)
    assert "https://idp.example.com" in saml_xml
    assert "user@example.com" in saml_xml


def test_saml_template_personalizer_clear_cache(test_template_path):
    """Test clearing the template cache."""
    personalizer = SAMLTemplatePersonalizer()
    
    # Load template to populate cache
    personalizer.load_template(test_template_path)
    assert personalizer.cache_size == 1
    
    # Clear cache
    personalizer.clear_cache()
    assert personalizer.cache_size == 0


def test_saml_template_personalizer_multiple_templates(
    test_template_path, minimal_template_path
):
    """Test caching multiple templates."""
    personalizer = SAMLTemplatePersonalizer()
    
    # Load multiple templates
    personalizer.load_template(test_template_path)
    personalizer.load_template(minimal_template_path)
    
    assert personalizer.cache_size == 2


# Integration-style tests


def test_full_personalization_workflow(test_template_path):
    """Test complete personalization workflow."""
    personalizer = SAMLTemplatePersonalizer()
    
    parameters = {
        "issuer": "https://idp.hospital.org",
        "subject": "dr.smith@hospital.org",
        "audience": "https://xds.regional-hie.org",
        "attr_username": "dr.smith",
        "attr_role": "physician",
    }
    
    # Personalize
    saml_xml = personalizer.personalize(
        test_template_path, parameters, validity_minutes=5
    )
    
    # Verify result
    assert "https://idp.hospital.org" in saml_xml
    assert "dr.smith@hospital.org" in saml_xml
    assert "https://xds.regional-hie.org" in saml_xml
    assert "dr.smith" in saml_xml
    assert "physician" in saml_xml
    
    # Verify no placeholders remain
    assert "{{" not in saml_xml
    assert "}}" not in saml_xml
    
    # Verify valid XML
    from lxml import etree
    etree.fromstring(saml_xml.encode("utf-8"))


def test_all_example_templates_valid(
    minimal_template_path, standard_template_path, extended_template_path
):
    """Test that all example templates are valid and can be personalized."""
    templates = [
        minimal_template_path,
        standard_template_path,
        extended_template_path,
    ]
    
    for template_path in templates:
        # Load template
        template = load_saml_template(template_path)
        
        # Validate
        result = validate_saml_template(template)
        assert result.is_valid, f"Template {template_path} is invalid: {result.errors}"
        
        # Extract placeholders
        placeholders = extract_saml_placeholders(template)
        assert len(placeholders) > 0


def test_personalize_all_example_templates(
    minimal_template_path, standard_template_path
):
    """Test personalizing all example templates."""
    # Minimal parameters (for minimal template)
    minimal_params = {
        "issuer": "https://idp.example.com",
        "subject": "user@example.com",
        "audience": "https://sp.example.com",
    }
    
    # Standard parameters (for standard template)
    # Make a fresh copy to avoid mutation
    standard_params = {
        "issuer": "https://idp.example.com",
        "subject": "user@example.com",
        "audience": "https://sp.example.com",
        "attr_username": "user",
        "attr_role": "physician",
        "attr_organization": "Hospital",
        "attr_purpose_of_use": "TREATMENT",
    }
    
    personalizer = SAMLTemplatePersonalizer()
    
    # Personalize minimal template
    saml_minimal = personalizer.personalize(minimal_template_path, minimal_params)
    assert "https://idp.example.com" in saml_minimal
    
    # Personalize standard template
    saml_standard = personalizer.personalize(standard_template_path, standard_params)
    assert "physician" in saml_standard
