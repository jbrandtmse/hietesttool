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
