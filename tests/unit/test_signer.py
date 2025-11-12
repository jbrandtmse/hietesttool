"""Unit tests for SAML signer module.

Tests XML signing functionality using signxml library, covering:
- SAMLSigner initialization
- Single assertion signing
- Batch assertion signing
- Error handling
- Signature structure validation
"""

import pytest
from pathlib import Path
from lxml import etree
from signxml.exceptions import InvalidInput

from ihe_test_util.saml.signer import SAMLSigner
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
from ihe_test_util.models.saml import SAMLAssertion, SAMLGenerationMethod
from ihe_test_util.utils.exceptions import CertificateLoadError


@pytest.fixture
def cert_bundle():
    """Load test certificate bundle."""
    cert_path = Path("tests/fixtures/test_cert.p12")
    return load_certificate(cert_path, password=b"testpass")


@pytest.fixture
def unsigned_assertion():
    """Generate unsigned SAML assertion for testing."""
    generator = SAMLProgrammaticGenerator()
    return generator.generate(
        subject="test-user@example.com",
        issuer="https://test-idp.example.com",
        audience="https://test-sp.example.com",
        validity_minutes=5
    )


@pytest.fixture
def unsigned_assertion_with_attributes():
    """Generate unsigned SAML assertion with attributes."""
    generator = SAMLProgrammaticGenerator()
    return generator.generate(
        subject="test-user@example.com",
        issuer="https://test-idp.example.com",
        audience="https://test-sp.example.com",
        attributes={
            "role": "physician",
            "department": "cardiology",
            "permissions": ["read", "write", "admin"]
        },
        validity_minutes=5
    )


class TestSAMLSignerInitialization:
    """Test SAMLSigner initialization."""
    
    def test_signer_initialization_success(self, cert_bundle):
        """Test SAMLSigner initializes with valid certificate bundle."""
        signer = SAMLSigner(cert_bundle)
        
        assert signer is not None
        assert signer.cert_bundle == cert_bundle
        assert signer.signature_algorithm == "RSA-SHA256"
        assert signer.signer is not None
    
    def test_signer_initialization_custom_algorithm(self, cert_bundle):
        """Test SAMLSigner initializes with RSA-SHA512 algorithm."""
        signer = SAMLSigner(cert_bundle, signature_algorithm="RSA-SHA512")
        
        assert signer.signature_algorithm == "RSA-SHA512"
    
    def test_signer_initialization_invalid_algorithm(self, cert_bundle):
        """Test SAMLSigner rejects invalid signature algorithm."""
        with pytest.raises(ValueError, match="Unsupported signature algorithm"):
            SAMLSigner(cert_bundle, signature_algorithm="MD5")
    
    def test_signer_initialization_no_certificate(self):
        """Test SAMLSigner rejects bundle without certificate."""
        from ihe_test_util.models.saml import CertificateBundle, CertificateInfo
        
        invalid_bundle = CertificateBundle(
            certificate=None,
            private_key=None,
            chain=[],
            info=CertificateInfo(
                subject="CN=Test",
                issuer="CN=Test",
                not_before=None,
                not_after=None,
                serial_number=0,
                key_size=None
            )
        )
        
        with pytest.raises(CertificateLoadError, match="must contain a valid certificate"):
            SAMLSigner(invalid_bundle)
    
    def test_signer_initialization_no_private_key(self):
        """Test SAMLSigner rejects bundle without private key."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        cert_only_bundle = load_certificate(cert_path)
        
        with pytest.raises(CertificateLoadError, match="must contain a private key"):
            SAMLSigner(cert_only_bundle)


class TestSignAssertion:
    """Test SAML assertion signing."""
    
    def test_sign_assertion_success(self, cert_bundle, unsigned_assertion):
        """Test signing SAML assertion adds signature element."""
        signer = SAMLSigner(cert_bundle)
        signed_assertion = signer.sign_assertion(unsigned_assertion)
        
        # Verify signature element added
        assert "<ds:Signature" in signed_assertion.xml_content
        assert signed_assertion.signature != ""
        assert signed_assertion.assertion_id == unsigned_assertion.assertion_id
        assert signed_assertion.certificate_subject == cert_bundle.info.subject
        
        # Parse and verify structure
        tree = etree.fromstring(signed_assertion.xml_content.encode('utf-8'))
        ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
        sig_element = tree.find('.//ds:Signature', ns)
        
        assert sig_element is not None
    
    def test_sign_assertion_with_attributes(self, cert_bundle, unsigned_assertion_with_attributes):
        """Test signing SAML assertion with attributes."""
        signer = SAMLSigner(cert_bundle)
        signed_assertion = signer.sign_assertion(unsigned_assertion_with_attributes)
        
        assert "<ds:Signature" in signed_assertion.xml_content
        assert signed_assertion.signature != ""
        
        # Verify attributes preserved
        assert "physician" in signed_assertion.xml_content
        assert "cardiology" in signed_assertion.xml_content
    
    def test_sign_assertion_signature_structure(self, cert_bundle, unsigned_assertion):
        """Test signed assertion contains correct signature structure."""
        signer = SAMLSigner(cert_bundle)
        signed_assertion = signer.sign_assertion(unsigned_assertion)
        
        tree = etree.fromstring(signed_assertion.xml_content.encode('utf-8'))
        ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
        
        # Verify SignedInfo
        signed_info = tree.find('.//ds:SignedInfo', ns)
        assert signed_info is not None
        
        # Verify CanonicalizationMethod
        canon_method = tree.find('.//ds:CanonicalizationMethod', ns)
        assert canon_method is not None
        canon_algo = canon_method.get('Algorithm')
        assert 'c14n' in canon_algo.lower()  # C14N canonicalization
        
        # Verify SignatureMethod
        sig_method = tree.find('.//ds:SignatureMethod', ns)
        assert sig_method is not None
        sig_algo = sig_method.get('Algorithm')
        assert 'rsa-sha256' in sig_algo.lower()
        
        # Verify DigestMethod
        digest_method = tree.find('.//ds:DigestMethod', ns)
        assert digest_method is not None
        digest_algo = digest_method.get('Algorithm')
        assert 'sha256' in digest_algo.lower()
        
        # Verify SignatureValue
        sig_value = tree.find('.//ds:SignatureValue', ns)
        assert sig_value is not None
        assert sig_value.text is not None
        assert len(sig_value.text) > 0
        
        # Verify KeyInfo with X509Certificate
        key_info = tree.find('.//ds:KeyInfo', ns)
        assert key_info is not None
        
        x509_cert = tree.find('.//ds:X509Certificate', ns)
        assert x509_cert is not None
        assert x509_cert.text is not None
    
    def test_sign_assertion_rsa_sha512(self, cert_bundle, unsigned_assertion):
        """Test signing with RSA-SHA512 algorithm."""
        signer = SAMLSigner(cert_bundle, signature_algorithm="RSA-SHA512")
        signed_assertion = signer.sign_assertion(unsigned_assertion)
        
        assert "<ds:Signature" in signed_assertion.xml_content
        assert signed_assertion.signature != ""
        
        # Verify signature method is RSA-SHA512
        tree = etree.fromstring(signed_assertion.xml_content.encode('utf-8'))
        ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
        sig_method = tree.find('.//ds:SignatureMethod', ns)
        sig_algo = sig_method.get('Algorithm')
        assert 'rsa-sha512' in sig_algo.lower()
    
    def test_sign_assertion_malformed_xml(self, cert_bundle):
        """Test signing with malformed XML raises appropriate error."""
        from dataclasses import replace
        from datetime import datetime, timezone
        
        malformed_assertion = SAMLAssertion(
            assertion_id="_test123",
            issuer="https://test.com",
            subject="test@test.com",
            audience="https://audience.com",
            issue_instant=datetime.now(timezone.utc),
            not_before=datetime.now(timezone.utc),
            not_on_or_after=datetime.now(timezone.utc),
            xml_content="<invalid>unclosed tag",  # Malformed XML
            signature="",
            certificate_subject="",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC
        )
        
        signer = SAMLSigner(cert_bundle)
        
        with pytest.raises(ValueError, match="Invalid XML structure"):
            signer.sign_assertion(malformed_assertion)
    
    def test_sign_assertion_preserves_assertion_id(self, cert_bundle, unsigned_assertion):
        """Test signing preserves original assertion ID."""
        signer = SAMLSigner(cert_bundle)
        original_id = unsigned_assertion.assertion_id
        
        signed_assertion = signer.sign_assertion(unsigned_assertion)
        
        assert signed_assertion.assertion_id == original_id
        assert f'ID="{original_id}"' in signed_assertion.xml_content
    
    def test_sign_assertion_preserves_timestamps(self, cert_bundle, unsigned_assertion):
        """Test signing preserves original timestamps."""
        signer = SAMLSigner(cert_bundle)
        
        original_issue_instant = unsigned_assertion.issue_instant
        original_not_before = unsigned_assertion.not_before
        original_not_on_or_after = unsigned_assertion.not_on_or_after
        
        signed_assertion = signer.sign_assertion(unsigned_assertion)
        
        assert signed_assertion.issue_instant == original_issue_instant
        assert signed_assertion.not_before == original_not_before
        assert signed_assertion.not_on_or_after == original_not_on_or_after


class TestBatchSigning:
    """Test batch assertion signing."""
    
    def test_sign_batch_success(self, cert_bundle):
        """Test batch signing 10 assertions."""
        generator = SAMLProgrammaticGenerator()
        assertions = [
            generator.generate(
                subject=f"user{i}@example.com",
                issuer="https://idp.example.com",
                audience="https://sp.example.com"
            )
            for i in range(10)
        ]
        
        signer = SAMLSigner(cert_bundle)
        signed_assertions = signer.sign_batch(assertions)
        
        assert len(signed_assertions) == 10
        assert all(a.signature != "" for a in signed_assertions)
        assert all("<ds:Signature" in a.xml_content for a in signed_assertions)
    
    def test_sign_batch_performance(self, cert_bundle):
        """Test batch signing 10 assertions completes in < 1 second."""
        import time
        
        generator = SAMLProgrammaticGenerator()
        assertions = [
            generator.generate(
                subject=f"user{i}@example.com",
                issuer="https://idp.example.com",
                audience="https://sp.example.com"
            )
            for i in range(10)
        ]
        
        signer = SAMLSigner(cert_bundle)
        start = time.time()
        signed_assertions = signer.sign_batch(assertions)
        duration = time.time() - start
        
        assert len(signed_assertions) == 10
        assert duration < 1.0  # Should complete in < 1 second
    
    def test_sign_batch_continues_on_error(self, cert_bundle, unsigned_assertion):
        """Test batch signing continues if individual assertion fails."""
        from dataclasses import replace
        from datetime import datetime, timezone
        
        # Create mix of valid and invalid assertions
        malformed_assertion = SAMLAssertion(
            assertion_id="_malformed",
            issuer="https://test.com",
            subject="test@test.com",
            audience="https://audience.com",
            issue_instant=datetime.now(timezone.utc),
            not_before=datetime.now(timezone.utc),
            not_on_or_after=datetime.now(timezone.utc),
            xml_content="<invalid>unclosed",  # Malformed
            signature="",
            certificate_subject="",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC
        )
        
        assertions = [
            unsigned_assertion,
            malformed_assertion,
            unsigned_assertion
        ]
        
        signer = SAMLSigner(cert_bundle)
        signed_assertions = signer.sign_batch(assertions)
        
        # Should have signed 2 out of 3 (skipped malformed)
        assert len(signed_assertions) == 2
        assert all(a.signature != "" for a in signed_assertions)
    
    def test_sign_batch_empty_list(self, cert_bundle):
        """Test batch signing empty list."""
        signer = SAMLSigner(cert_bundle)
        signed_assertions = signer.sign_batch([])
        
        assert len(signed_assertions) == 0


class TestSigningCoverage:
    """Additional tests for code coverage."""
    
    def test_signature_value_extraction(self, cert_bundle, unsigned_assertion):
        """Test that signature value is correctly extracted."""
        signer = SAMLSigner(cert_bundle)
        signed_assertion = signer.sign_assertion(unsigned_assertion)
        
        # Verify signature field populated
        assert signed_assertion.signature != ""
        assert len(signed_assertion.signature) > 100  # Signatures are long base64 strings
        
        # Verify signature value matches what's in XML
        tree = etree.fromstring(signed_assertion.xml_content.encode('utf-8'))
        ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
        sig_value_elem = tree.find('.//ds:SignatureValue', ns)
        
        assert sig_value_elem.text == signed_assertion.signature
    
    def test_certificate_subject_populated(self, cert_bundle, unsigned_assertion):
        """Test that certificate subject is populated in signed assertion."""
        signer = SAMLSigner(cert_bundle)
        signed_assertion = signer.sign_assertion(unsigned_assertion)
        
        assert signed_assertion.certificate_subject != ""
        assert signed_assertion.certificate_subject == cert_bundle.info.subject
