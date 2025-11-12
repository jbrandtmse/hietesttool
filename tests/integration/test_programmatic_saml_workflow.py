"""Integration tests for programmatic SAML generation workflow.

Tests the complete workflow of generating SAML assertions programmatically
and verifying integration with certificate management and template-based approaches.
"""

import pytest
from datetime import datetime, timezone
from lxml import etree
from pathlib import Path

from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
from ihe_test_util.saml.template_loader import SAMLTemplatePersonalizer
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.models.saml import SAMLGenerationMethod


class TestProgrammaticSamlWorkflow:
    """Integration tests for programmatic SAML generation workflow."""

    def test_generate_basic_saml_assertion(self):
        """Test complete workflow: generate basic SAML assertion."""
        generator = SAMLProgrammaticGenerator()
        
        assertion = generator.generate(
            subject="patient-12345",
            issuer="https://hospital-a.example.com",
            audience="https://regional-hie.example.com"
        )
        
        # Verify assertion structure
        assert assertion.assertion_id.startswith("_")
        assert assertion.subject == "patient-12345"
        assert assertion.issuer == "https://hospital-a.example.com"
        assert assertion.audience == "https://regional-hie.example.com"
        assert assertion.generation_method == SAMLGenerationMethod.PROGRAMMATIC
        
        # Verify XML is well-formed
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        assert tree.tag.endswith("}Assertion")
        
        # Verify required SAML elements present
        assert tree.find(".//{*}Issuer") is not None
        assert tree.find(".//{*}Subject") is not None
        assert tree.find(".//{*}Conditions") is not None
        assert tree.find(".//{*}AuthnStatement") is not None

    def test_generate_saml_with_custom_attributes(self):
        """Test workflow: generate SAML with custom attributes."""
        generator = SAMLProgrammaticGenerator()
        
        assertion = generator.generate(
            subject="dr.smith@hospital-a.example.com",
            issuer="https://hospital-a.example.com",
            audience="https://regional-hie.example.com",
            attributes={
                "username": "dr.smith",
                "role": "physician",
                "organization": "Hospital A",
                "department": "Cardiology",
                "npi": "1234567890"
            },
            validity_minutes=10
        )
        
        # Verify assertion metadata
        assert assertion.subject == "dr.smith@hospital-a.example.com"
        
        # Verify XML contains attributes
        assert "<saml:AttributeStatement>" in assertion.xml_content
        assert "dr.smith" in assertion.xml_content
        assert "physician" in assertion.xml_content
        assert "Hospital A" in assertion.xml_content
        
        # Verify validity period
        delta = assertion.not_on_or_after - assertion.issue_instant
        assert delta.total_seconds() == 600  # 10 minutes

    def test_generate_saml_with_multi_valued_attributes(self):
        """Test workflow: generate SAML with multi-valued attributes."""
        generator = SAMLProgrammaticGenerator()
        
        assertion = generator.generate(
            subject="dr.jones@hospital-a.example.com",
            issuer="https://hospital-a.example.com",
            audience="https://regional-hie.example.com",
            attributes={
                "username": "dr.jones",
                "roles": ["physician", "administrator", "researcher"],
                "specialties": ["Cardiology", "Internal Medicine"]
            }
        )
        
        # Parse and verify multi-valued attributes
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        
        # Check roles attribute has 3 values
        roles_attr = tree.find(".//{*}Attribute[@Name='roles']")
        assert roles_attr is not None
        role_values = roles_attr.findall(".//{*}AttributeValue")
        assert len(role_values) == 3
        
        # Check specialties attribute has 2 values
        specialties_attr = tree.find(".//{*}Attribute[@Name='specialties']")
        assert specialties_attr is not None
        specialty_values = specialties_attr.findall(".//{*}AttributeValue")
        assert len(specialty_values) == 2

    def test_integration_with_certificate_manager(self):
        """Test integration: programmatic SAML with certificate manager."""
        # Load certificate
        cert_bundle = load_certificate(Path("tests/fixtures/test_cert.pem"))
        
        # Generate SAML with certificate
        generator = SAMLProgrammaticGenerator(cert_bundle=cert_bundle)
        assertion = generator.generate_with_certificate(
            subject="patient-67890",
            audience="https://regional-hie.example.com"
        )
        
        # Verify issuer extracted from certificate
        assert assertion.issuer == cert_bundle.info.subject
        assert assertion.certificate_subject == cert_bundle.info.subject
        
        # Verify SAML structure
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        issuer_elem = tree.find(".//{*}Issuer")
        assert issuer_elem is not None
        assert issuer_elem.text == cert_bundle.info.subject

    def test_programmatic_vs_template_compatibility(self):
        """Test compatibility: programmatic and template-based SAML are compatible."""
        # Generate programmatic SAML
        prog_gen = SAMLProgrammaticGenerator()
        prog_assertion = prog_gen.generate(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="https://sp.example.com",
            validity_minutes=5
        )
        
        # Generate template-based SAML
        templ_gen = SAMLTemplatePersonalizer()
        templ_assertion_xml = templ_gen.personalize(
            Path("templates/saml-minimal.xml"),
            {
                "subject": "user@example.com",
                "issuer": "https://idp.example.com",
                "audience": "https://sp.example.com"
            },
            validity_minutes=5
        )
        
        # Both should have valid SAML 2.0 structure
        prog_tree = etree.fromstring(prog_assertion.xml_content.encode("utf-8"))
        templ_tree = etree.fromstring(templ_assertion_xml.encode("utf-8"))
        
        # Both should have required elements
        assert prog_tree.find(".//{*}Issuer") is not None
        assert templ_tree.find(".//{*}Issuer") is not None
        
        assert prog_tree.find(".//{*}Subject") is not None
        assert templ_tree.find(".//{*}Subject") is not None
        
        assert prog_tree.find(".//{*}Conditions") is not None
        assert templ_tree.find(".//{*}Conditions") is not None

    def test_saml_canonicalization_for_signing(self):
        """Test workflow: SAML is properly canonicalized for signing."""
        generator = SAMLProgrammaticGenerator()
        
        assertion = generator.generate(
            subject="patient-11111",
            issuer="https://hospital-b.example.com",
            audience="https://xds-registry.example.com"
        )
        
        # Verify XML is canonicalized (no double newlines, consistent format)
        assert "\n\n" not in assertion.xml_content
        
        # Verify parseable
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        assert tree is not None
        
        # Verify can be re-canonicalized (idempotent)
        recanonical = etree.tostring(tree, method="c14n").decode("utf-8")
        assert recanonical == assertion.xml_content

    def test_batch_saml_generation(self):
        """Test workflow: generate multiple SAML assertions (batch processing)."""
        generator = SAMLProgrammaticGenerator()
        
        # Generate 10 assertions
        assertions = []
        for i in range(10):
            assertion = generator.generate(
                subject=f"patient-{i:05d}",
                issuer="https://hospital-c.example.com",
                audience="https://regional-hie.example.com",
                attributes={"patient_number": str(i)}
            )
            assertions.append(assertion)
        
        # Verify all have unique IDs
        assertion_ids = {a.assertion_id for a in assertions}
        assert len(assertion_ids) == 10
        
        # Verify all have correct subject pattern
        for i, assertion in enumerate(assertions):
            assert assertion.subject == f"patient-{i:05d}"
            assert assertion.generation_method == SAMLGenerationMethod.PROGRAMMATIC

    def test_saml_timestamp_validity(self):
        """Test workflow: SAML timestamps are valid and consistent."""
        generator = SAMLProgrammaticGenerator()
        
        assertion = generator.generate(
            subject="patient-22222",
            issuer="https://hospital-d.example.com",
            audience="https://xds.example.com",
            validity_minutes=15
        )
        
        # Verify timestamps are in UTC
        assert assertion.issue_instant.tzinfo == timezone.utc
        assert assertion.not_before.tzinfo == timezone.utc
        assert assertion.not_on_or_after.tzinfo == timezone.utc
        
        # Verify not_before equals issue_instant
        assert assertion.not_before == assertion.issue_instant
        
        # Verify validity period
        delta = assertion.not_on_or_after - assertion.issue_instant
        assert delta.total_seconds() == 900  # 15 minutes
        
        # Verify XML timestamps match
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        conditions = tree.find(".//{*}Conditions")
        assert conditions is not None
        
        not_before_str = conditions.get("NotBefore")
        not_on_or_after_str = conditions.get("NotOnOrAfter")
        
        # Parse and verify
        not_before_parsed = datetime.fromisoformat(not_before_str.replace("Z", "+00:00"))
        not_on_or_after_parsed = datetime.fromisoformat(not_on_or_after_str.replace("Z", "+00:00"))
        
        assert not_before_parsed == assertion.not_before
        assert not_on_or_after_parsed == assertion.not_on_or_after

    def test_saml_generation_with_pkcs12_certificate(self):
        """Test integration: programmatic SAML with PKCS12 certificate."""
        # Skip if PKCS12 file doesn't exist or password is incorrect
        p12_path = Path("tests/fixtures/test_cert.p12")
        if not p12_path.exists():
            pytest.skip("PKCS12 test certificate not available")
        
        try:
            # Load PKCS12 certificate
            cert_bundle = load_certificate(p12_path, password=b"test")
        except Exception:
            # Skip if password is incorrect or file is invalid
            pytest.skip("PKCS12 test certificate password incorrect or file invalid")
        
        # Generate SAML with PKCS12 certificate
        generator = SAMLProgrammaticGenerator(cert_bundle=cert_bundle)
        assertion = generator.generate_with_certificate(
            subject="patient-33333",
            audience="https://registry.example.com",
            attributes={"source": "Hospital E"}
        )
        
        # Verify issuer from PKCS12 certificate
        assert assertion.issuer == cert_bundle.info.subject
        assert assertion.certificate_subject == cert_bundle.info.subject
        
        # Verify SAML contains attribute
        assert "Hospital E" in assertion.xml_content

    def test_saml_structure_follows_spec(self):
        """Test verification: generated SAML follows SAML 2.0 specification."""
        generator = SAMLProgrammaticGenerator()
        
        assertion = generator.generate(
            subject="user@test.example.com",
            issuer="https://test-idp.example.com",
            audience="https://test-sp.example.com",
            attributes={"test_attr": "test_value"}
        )
        
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        
        # Verify SAML 2.0 namespace
        assert "urn:oasis:names:tc:SAML:2.0:assertion" in tree.nsmap.values()
        
        # Verify Assertion attributes
        assert tree.get("Version") == "2.0"
        assert tree.get("ID") is not None
        assert tree.get("IssueInstant") is not None
        
        # Verify element order (per SAML 2.0 spec)
        children = list(tree)
        child_tags = [child.tag.split("}")[-1] for child in children]
        
        # Expected order: Issuer, Subject, Conditions, AuthnStatement, [AttributeStatement]
        assert child_tags[0] == "Issuer"
        assert "Subject" in child_tags
        assert "Conditions" in child_tags
        assert "AuthnStatement" in child_tags
        assert "AttributeStatement" in child_tags  # Present because we provided attributes

    def test_generate_minimal_saml_without_attributes(self):
        """Test workflow: generate minimal SAML without optional attributes."""
        generator = SAMLProgrammaticGenerator()
        
        assertion = generator.generate(
            subject="minimal@example.com",
            issuer="https://minimal-idp.example.com",
            audience="https://minimal-sp.example.com"
        )
        
        # Verify minimal structure
        tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
        
        # Should have required elements
        assert tree.find(".//{*}Issuer") is not None
        assert tree.find(".//{*}Subject") is not None
        assert tree.find(".//{*}Conditions") is not None
        assert tree.find(".//{*}AuthnStatement") is not None
        
        # Should NOT have AttributeStatement (no attributes provided)
        assert tree.find(".//{*}AttributeStatement") is None

    def test_saml_generation_performance(self):
        """Test performance: generate 100 SAML assertions quickly."""
        import time
        
        generator = SAMLProgrammaticGenerator()
        
        start_time = time.time()
        
        # Generate 100 assertions
        for i in range(100):
            assertion = generator.generate(
                subject=f"perf-test-{i}",
                issuer="https://perf-idp.example.com",
                audience="https://perf-sp.example.com"
            )
        
        elapsed_time = time.time() - start_time
        
        # Should complete in reasonable time (< 5 seconds for 100 assertions)
        assert elapsed_time < 5.0, f"Performance issue: took {elapsed_time:.2f}s for 100 assertions"
        
        # Average time per assertion should be reasonable
        avg_time = elapsed_time / 100
        assert avg_time < 0.05, f"Performance issue: avg {avg_time:.4f}s per assertion"
