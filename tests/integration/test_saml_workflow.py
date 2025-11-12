"""Integration tests for SAML template workflow.

Tests the complete SAML template personalization workflow including:
- Loading templates
- Personalizing with parameters
- Integration with certificate manager
- Multiple template usage
"""

import pytest
from pathlib import Path

from ihe_test_util.saml.template_loader import (
    SAMLTemplatePersonalizer,
    personalize_saml_template,
)
from ihe_test_util.saml.certificate_manager import load_certificate


# Fixtures

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
    """Path to extended SAML template."""
    return Path("templates/saml-with-attributes.xml")


@pytest.fixture
def test_cert_path():
    """Path to test certificate."""
    return Path("tests/fixtures/test_cert.p12")


# Integration tests


def test_saml_template_workflow_minimal(minimal_template_path):
    """Test complete workflow with minimal template."""
    personalizer = SAMLTemplatePersonalizer()
    
    parameters = {
        "issuer": "https://idp.example.com",
        "subject": "user@example.com",
        "audience": "https://sp.example.com",
    }
    
    saml_xml = personalizer.personalize(minimal_template_path, parameters)
    
    # Verify personalization
    assert "https://idp.example.com" in saml_xml
    assert "user@example.com" in saml_xml
    assert "https://sp.example.com" in saml_xml
    
    # Verify no placeholders remain
    assert "{{" not in saml_xml
    
    # Verify valid XML
    from lxml import etree
    root = etree.fromstring(saml_xml.encode("utf-8"))
    
    # Verify SAML structure
    assert root.tag.endswith("Assertion")
    assert root.get("ID").startswith("_")


def test_saml_template_workflow_standard(standard_template_path):
    """Test complete workflow with standard template."""
    personalizer = SAMLTemplatePersonalizer()
    
    parameters = {
        "issuer": "https://idp.hospital.org",
        "subject": "dr.smith@hospital.org",
        "audience": "https://xds.regional-hie.org",
        "attr_username": "dr.smith",
        "attr_role": "physician",
        "attr_organization": "General Hospital",
        "attr_purpose_of_use": "TREATMENT",
    }
    
    saml_xml = personalizer.personalize(
        standard_template_path, parameters, validity_minutes=5
    )
    
    # Verify personalization
    assert "https://idp.hospital.org" in saml_xml
    assert "dr.smith@hospital.org" in saml_xml
    assert "dr.smith" in saml_xml
    assert "physician" in saml_xml
    assert "General Hospital" in saml_xml
    assert "TREATMENT" in saml_xml
    
    # Verify timestamps
    assert "IssueInstant=" in saml_xml
    assert "NotBefore=" in saml_xml
    assert "NotOnOrAfter=" in saml_xml


def test_saml_template_workflow_extended(extended_template_path):
    """Test complete workflow with extended template."""
    personalizer = SAMLTemplatePersonalizer()
    
    parameters = {
        "issuer": "https://idp.hospital.org",
        "subject": "dr.jane.smith@hospital.org",
        "audience": "https://xds-repository.hie.org",
        "attr_username": "jsmith",
        "attr_given_name": "Jane",
        "attr_family_name": "Smith",
        "attr_email": "jane.smith@hospital.org",
        "attr_role": "physician",
        "attr_organization": "General Hospital",
        "attr_organization_id": "2.16.840.1.113883.4.6.12345",
        "attr_facility": "Cardiology Department",
        "attr_purpose_of_use": "TREATMENT",
        "attr_npi": "1234567890",
        "attr_specialty": "Cardiology",
    }
    
    saml_xml = personalizer.personalize(extended_template_path, parameters)
    
    # Verify extensive attributes
    assert "Jane" in saml_xml
    assert "Smith" in saml_xml
    assert "jane.smith@hospital.org" in saml_xml
    assert "Cardiology Department" in saml_xml
    assert "1234567890" in saml_xml
    assert "Cardiology" in saml_xml


def test_saml_template_caching_workflow(standard_template_path):
    """Test template caching in workflow."""
    personalizer = SAMLTemplatePersonalizer(template_cache_enabled=True)
    
    parameters = {
        "issuer": "https://idp.example.com",
        "subject": "user@example.com",
        "audience": "https://sp.example.com",
        "attr_username": "user",
        "attr_role": "physician",
        "attr_organization": "Hospital",
        "attr_purpose_of_use": "TREATMENT",
    }
    
    # First personalization (loads and caches template)
    saml1 = personalizer.personalize(standard_template_path, parameters)
    assert personalizer.cache_size == 1
    
    # Second personalization (uses cached template)
    saml2 = personalizer.personalize(standard_template_path, parameters)
    assert personalizer.cache_size == 1
    
    # Both should be similar (different assertion IDs but same structure)
    assert "https://idp.example.com" in saml1
    assert "https://idp.example.com" in saml2


def test_saml_template_multiple_templates_workflow(
    minimal_template_path, standard_template_path
):
    """Test workflow with multiple different templates."""
    personalizer = SAMLTemplatePersonalizer()
    
    minimal_params = {
        "issuer": "https://idp.example.com",
        "subject": "user1@example.com",
        "audience": "https://sp.example.com",
    }
    
    standard_params = {
        "issuer": "https://idp.example.com",
        "subject": "user2@example.com",
        "audience": "https://sp.example.com",
        "attr_username": "user2",
        "attr_role": "nurse",
        "attr_organization": "Clinic",
        "attr_purpose_of_use": "TREATMENT",
    }
    
    # Personalize minimal template
    saml_minimal = personalizer.personalize(minimal_template_path, minimal_params)
    
    # Personalize standard template
    saml_standard = personalizer.personalize(standard_template_path, standard_params)
    
    # Both should be valid but different
    assert "user1@example.com" in saml_minimal
    assert "user2@example.com" in saml_standard
    assert "nurse" in saml_standard
    assert "nurse" not in saml_minimal


def test_saml_template_batch_personalization(standard_template_path):
    """Test batch personalization workflow."""
    personalizer = SAMLTemplatePersonalizer()
    
    # Simulate batch processing multiple users
    users = [
        {
            "issuer": "https://idp.hospital.org",
            "subject": f"user{i}@hospital.org",
            "audience": "https://xds.hie.org",
            "attr_username": f"user{i}",
            "attr_role": "physician",
            "attr_organization": "Hospital",
            "attr_purpose_of_use": "TREATMENT",
        }
        for i in range(5)
    ]
    
    saml_assertions = []
    for params in users:
        saml_xml = personalizer.personalize(standard_template_path, params)
        saml_assertions.append(saml_xml)
    
    # Verify all assertions created
    assert len(saml_assertions) == 5
    
    # Verify each is unique (different subjects)
    for i, saml in enumerate(saml_assertions):
        assert f"user{i}@hospital.org" in saml
    
    # Template should be cached
    assert personalizer.cache_size == 1


@pytest.mark.skip(reason="Test certificate password unknown - integration tested in Story 4.1")
def test_saml_template_with_certificate_workflow(
    standard_template_path, test_cert_path
):
    """Test workflow integrating with certificate manager."""
    # Load certificate
    cert_bundle = load_certificate(test_cert_path, password=b"password")
    
    # Personalize with certificate info
    personalizer = SAMLTemplatePersonalizer()
    parameters = {
        "subject": "user@example.com",
        "audience": "https://xds-registry.example.com",
        "attr_username": "user",
        "attr_role": "physician",
        "attr_organization": "Hospital",
        "attr_purpose_of_use": "TREATMENT",
    }
    
    saml_xml = personalizer.personalize_with_certificate_info(
        standard_template_path, cert_bundle, parameters
    )
    
    # Verify personalization
    assert "user@example.com" in saml_xml
    
    # Issuer should be extracted from certificate
    # (actual value depends on test certificate)
    assert "{{issuer}}" not in saml_xml


def test_saml_template_pix_add_scenario(standard_template_path):
    """Test SAML generation for PIX Add transaction scenario."""
    personalizer = SAMLTemplatePersonalizer()
    
    # Typical PIX Add parameters
    parameters = {
        "issuer": "https://idp.hospital.org",
        "subject": "integration-user@hospital.org",
        "audience": "https://pix-manager.hie.org",
        "attr_username": "integration-user",
        "attr_role": "system",
        "attr_organization": "General Hospital",
        "attr_purpose_of_use": "SYSADMIN",
    }
    
    saml_xml = personalizer.personalize(
        standard_template_path, parameters, validity_minutes=5
    )
    
    # Verify PIX Add specific attributes
    assert "integration-user" in saml_xml
    assert "system" in saml_xml
    assert "SYSADMIN" in saml_xml
    
    # Verify valid XML
    from lxml import etree
    etree.fromstring(saml_xml.encode("utf-8"))


def test_saml_template_iti41_scenario(extended_template_path):
    """Test SAML generation for ITI-41 transaction scenario."""
    personalizer = SAMLTemplatePersonalizer()
    
    # Typical ITI-41 parameters with full provider context
    parameters = {
        "issuer": "https://idp.hospital.org",
        "subject": "dr.jane.smith@hospital.org",
        "audience": "https://xds-repository.hie.org",
        "attr_username": "jsmith",
        "attr_given_name": "Jane",
        "attr_family_name": "Smith",
        "attr_email": "jane.smith@hospital.org",
        "attr_role": "physician",
        "attr_organization": "General Hospital",
        "attr_organization_id": "2.16.840.1.113883.4.6.12345",
        "attr_facility": "Cardiology Department",
        "attr_purpose_of_use": "TREATMENT",
        "attr_npi": "1234567890",
        "attr_specialty": "Cardiology",
    }
    
    saml_xml = personalizer.personalize(
        extended_template_path, parameters, validity_minutes=5
    )
    
    # Verify ITI-41 specific attributes
    assert "Cardiology" in saml_xml
    assert "1234567890" in saml_xml
    assert "TREATMENT" in saml_xml
    
    # Verify valid XML
    from lxml import etree
    root = etree.fromstring(saml_xml.encode("utf-8"))
    
    # Verify attribute statement exists
    ns = {"saml": "urn:oasis:names:tc:SAML:2.0:assertion"}
    attrs = root.findall(".//saml:AttributeStatement/saml:Attribute", namespaces=ns)
    assert len(attrs) > 0


def test_saml_template_validity_periods(standard_template_path):
    """Test SAML generation with different validity periods."""
    personalizer = SAMLTemplatePersonalizer()
    
    parameters = {
        "issuer": "https://idp.example.com",
        "subject": "user@example.com",
        "audience": "https://sp.example.com",
        "attr_username": "user",
        "attr_role": "physician",
        "attr_organization": "Hospital",
        "attr_purpose_of_use": "TREATMENT",
    }
    
    # Test different validity periods
    for validity in [1, 5, 10, 30]:
        saml_xml = personalizer.personalize(
            standard_template_path, parameters, validity_minutes=validity
        )
        
        # Should contain timestamps
        assert "NotOnOrAfter=" in saml_xml
        
        # Should be valid XML
        from lxml import etree
        etree.fromstring(saml_xml.encode("utf-8"))


# WS-Security Integration Tests (Story 4.5)


def test_ws_security_end_to_end_workflow():
    """Test complete workflow: generate SAML → sign → embed in WS-Security → create SOAP envelope."""
    from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
    from ihe_test_util.saml.signer import SAMLSigner
    from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
    from ihe_test_util.saml.certificate_manager import load_certificate
    from lxml import etree
    
    # Generate SAML assertion
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="dr.smith@hospital.org",
        issuer="https://idp.hospital.org",
        audience="https://pix.regional-hie.org"
    )
    
    # Sign assertion
    cert_path = Path("tests/fixtures/test_cert.pem")
    key_path = Path("tests/fixtures/test_key.pem")
    cert_bundle = load_certificate(cert_path, key_path=key_path)
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    
    # Build WS-Security header
    builder = WSSecurityHeaderBuilder()
    ws_security = builder.build_ws_security_header(signed_assertion)
    
    # Verify WS-Security header structure
    assert ws_security is not None
    assert "Security" in ws_security.tag
    
    # Create SOAP envelope
    body = etree.Element("TestBody")
    envelope = builder.embed_in_soap_envelope(body, ws_security)
    
    # Verify envelope structure
    assert "Envelope" in envelope.tag
    
    # Verify can serialize and parse
    envelope_str = etree.tostring(envelope, encoding='unicode')
    parsed = etree.fromstring(envelope_str.encode('utf-8'))
    assert parsed is not None


@pytest.mark.skip(reason="Template workflow produces XML strings, not SAMLAssertion models. No XML-to-model parser exists. Use programmatic generation for WS-Security (tested in test_ws_security_with_programmatic_saml).")
def test_ws_security_with_template_based_saml(standard_template_path):
    """Test WS-Security header with template-based SAML.
    
    NOTE: This test is skipped because SAMLTemplatePersonalizer.personalize() returns
    XML strings, not SAMLAssertion model objects. SAMLSigner requires model objects.
    There is no XML-to-model parser in the codebase.
    
    The proper workflows are:
    1. Template → XML string (tested in template tests)
    2. Programmatic → Model → Sign → WS-Security (tested in test_ws_security_with_programmatic_saml)
    
    This test attempted to call non-existent method: personalizer.personalize_to_model()
    """
    from ihe_test_util.saml.template_loader import SAMLTemplatePersonalizer
    from ihe_test_util.saml.signer import SAMLSigner
    from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
    from ihe_test_util.saml.certificate_manager import load_certificate
    from lxml import etree
    
    # This test is skipped - see docstring for explanation
    pass


def test_ws_security_with_programmatic_saml():
    """Test WS-Security header with programmatic SAML."""
    from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
    from ihe_test_util.saml.signer import SAMLSigner
    from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
    from ihe_test_util.saml.certificate_manager import load_certificate
    from lxml import etree
    
    # Generate SAML programmatically
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="integration-user@hospital.org",
        issuer="https://idp.hospital.org",
        audience="https://pix-manager.hie.org"
    )
    
    # Sign assertion
    cert_path = Path("tests/fixtures/test_cert.pem")
    key_path = Path("tests/fixtures/test_key.pem")
    cert_bundle = load_certificate(cert_path, key_path=key_path)
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    
    # Build WS-Security header
    builder = WSSecurityHeaderBuilder()
    ws_security = builder.build_ws_security_header(signed_assertion)
    
    # Validate header
    assert builder.validate_ws_security_header(ws_security) is True


def test_complete_pix_add_soap_envelope_workflow():
    """Test complete PIX Add workflow: signed SAML → WS-Security header → SOAP envelope."""
    from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
    from ihe_test_util.saml.signer import SAMLSigner
    from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
    from ihe_test_util.saml.certificate_manager import load_certificate
    from lxml import etree
    
    # Generate and sign SAML
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="integration-user@hospital.org",
        issuer="https://idp.hospital.org",
        audience="https://pix.regional-hie.org"
    )
    
    cert_path = Path("tests/fixtures/test_cert.pem")
    key_path = Path("tests/fixtures/test_key.pem")
    cert_bundle = load_certificate(cert_path, key_path=key_path)
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    
    # Create PIX Add message (dummy)
    pix_message = etree.Element("PRPA_IN201301UV02")
    pix_message.text = "PIX Add message content"
    
    # Create complete SOAP envelope
    builder = WSSecurityHeaderBuilder()
    envelope_str = builder.create_pix_add_soap_envelope(
        signed_assertion,
        pix_message,
        "http://pix.example.com/pix/add"
    )
    
    # Verify envelope is valid XML
    parsed = etree.fromstring(envelope_str.encode('utf-8'))
    assert parsed is not None
    
    # Verify structure
    assert "Envelope" in parsed.tag
    
    # Verify WS-Addressing action for PIX Add
    ns = {'wsa': 'http://www.w3.org/2005/08/addressing'}
    action = parsed.find(".//wsa:Action", namespaces=ns)
    assert action is not None
    assert action.text == "urn:hl7-org:v3:PRPA_IN201301UV02"
    
    # Verify WS-Security header present
    ns_wsse = {'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'}
    security = parsed.find(".//wsse:Security", namespaces=ns_wsse)
    assert security is not None


def test_complete_iti41_soap_envelope_workflow():
    """Test complete ITI-41 workflow: signed SAML → WS-Security header → SOAP envelope."""
    from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
    from ihe_test_util.saml.signer import SAMLSigner
    from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
    from ihe_test_util.saml.certificate_manager import load_certificate
    from lxml import etree
    
    # Generate and sign SAML
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="dr.jane.smith@hospital.org",
        issuer="https://idp.hospital.org",
        audience="https://xds-repository.hie.org"
    )
    
    cert_path = Path("tests/fixtures/test_cert.pem")
    key_path = Path("tests/fixtures/test_key.pem")
    cert_bundle = load_certificate(cert_path, key_path=key_path)
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    
    # Create ITI-41 request (dummy)
    iti41_request = etree.Element("ProvideAndRegisterDocumentSetRequest")
    iti41_request.text = "ITI-41 request content"
    
    # Create complete SOAP envelope
    builder = WSSecurityHeaderBuilder()
    envelope_str = builder.create_iti41_soap_envelope(
        signed_assertion,
        iti41_request,
        "http://xds.example.com/iti41/submit"
    )
    
    # Verify envelope is valid XML
    parsed = etree.fromstring(envelope_str.encode('utf-8'))
    assert parsed is not None
    
    # Verify structure
    assert "Envelope" in parsed.tag
    
    # Verify WS-Addressing action for ITI-41
    ns = {'wsa': 'http://www.w3.org/2005/08/addressing'}
    action = parsed.find(".//wsa:Action", namespaces=ns)
    assert action is not None
    assert action.text == "urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b"
    
    # Verify WS-Security header present
    ns_wsse = {'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'}
    security = parsed.find(".//wsse:Security", namespaces=ns_wsse)
    assert security is not None


def test_ws_security_serialization_and_parsing():
    """Test that WS-Security SOAP envelopes can be serialized and parsed correctly."""
    from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
    from ihe_test_util.saml.signer import SAMLSigner
    from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
    from ihe_test_util.saml.certificate_manager import load_certificate
    from lxml import etree
    
    # Generate and sign SAML
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="test@example.com",
        issuer="https://idp.example.com",
        audience="https://sp.example.com"
    )
    
    cert_path = Path("tests/fixtures/test_cert.pem")
    key_path = Path("tests/fixtures/test_key.pem")
    cert_bundle = load_certificate(cert_path, key_path=key_path)
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    
    # Create SOAP envelope
    builder = WSSecurityHeaderBuilder()
    ws_security = builder.build_ws_security_header(signed_assertion)
    body = etree.Element("TestBody")
    envelope = builder.embed_in_soap_envelope(body, ws_security)
    
    # Serialize
    envelope_str = etree.tostring(envelope, encoding='unicode', pretty_print=True)
    
    # Parse back
    parsed = etree.fromstring(envelope_str.encode('utf-8'))
    
    # Verify structure preserved
    ns_soap = {'SOAP-ENV': 'http://www.w3.org/2003/05/soap-envelope'}
    header = parsed.find(".//SOAP-ENV:Header", namespaces=ns_soap)
    body_elem = parsed.find(".//SOAP-ENV:Body", namespaces=ns_soap)
    
    assert header is not None
    assert body_elem is not None
    
    # Verify WS-Security still valid after round-trip
    ns_wsse = {'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'}
    security = header.find(".//wsse:Security", namespaces=ns_wsse)
    assert security is not None
    
    # Validate header structure
    assert builder.validate_ws_security_header(security) is True


def test_ws_security_batch_processing():
    """Test WS-Security header generation for batch processing scenario."""
    from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
    from ihe_test_util.saml.signer import SAMLSigner
    from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
    from ihe_test_util.saml.certificate_manager import load_certificate
    from lxml import etree
    
    # Load certificate once
    cert_path = Path("tests/fixtures/test_cert.pem")
    key_path = Path("tests/fixtures/test_key.pem")
    cert_bundle = load_certificate(cert_path, key_path=key_path)
    
    # Create builder and signer once
    generator = SAMLProgrammaticGenerator()
    signer = SAMLSigner(cert_bundle)
    builder = WSSecurityHeaderBuilder()
    
    # Process batch of 10 requests
    envelopes = []
    for i in range(10):
        # Generate and sign SAML
        assertion = generator.generate(
            subject=f"user{i}@hospital.org",
            issuer="https://idp.hospital.org",
            audience="https://xds.hie.org"
        )
        signed_assertion = signer.sign_assertion(assertion)
        
        # Create SOAP envelope
        body = etree.Element("TestBody")
        body.text = f"Request {i}"
        ws_security = builder.build_ws_security_header(signed_assertion)
        envelope = builder.embed_in_soap_envelope(body, ws_security)
        
        envelopes.append(envelope)
    
    # Verify all envelopes created
    assert len(envelopes) == 10
    
    # Verify each is valid
    for envelope in envelopes:
        envelope_str = etree.tostring(envelope, encoding='unicode')
        parsed = etree.fromstring(envelope_str.encode('utf-8'))
        assert parsed is not None
