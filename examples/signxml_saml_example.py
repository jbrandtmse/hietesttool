"""SignXML SAML Signing and Verification Example.

This example demonstrates using SignXML library (instead of python-xmlsec)
for signing and verifying SAML 2.0 assertions. SignXML has better Windows
compatibility as it only requires lxml and cryptography (both have pre-built wheels).
"""

from pathlib import Path
from lxml import etree
from signxml import XMLSigner, XMLVerifier, SignatureMethod, DigestAlgorithm

# Import our SAML generator
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ihe_test_util.saml.generator import generate_saml_assertion
from ihe_test_util.saml.certificate_manager import CertificateManager


def main():
    """Demonstrate SAML signing and verification with SignXML."""
    
    # Setup paths
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    cert_path = fixtures_dir / "test_cert.pem"
    key_path = fixtures_dir / "test_key.pem"
    
    print("=" * 70)
    print("SignXML SAML Signing and Verification Example")
    print("=" * 70)
    
    # Step 1: Generate SAML assertion
    print("\n1. Generating SAML 2.0 assertion...")
    assertion = generate_saml_assertion(
        issuer="https://test-issuer.example.com",
        subject="patient-12345"
    )
    
    print(f"   Generated assertion with ID: {assertion.get('ID')}")
    print(f"   Issuer: {assertion.find('.//{*}Issuer').text}")
    print(f"   Subject: {assertion.find('.//{*}Subject/{*}NameID').text}")
    
    # Step 2: Load certificate and key
    print("\n2. Loading certificate and private key...")
    cert = CertificateManager.load_pem_certificate(cert_path)
    key = CertificateManager.load_pem_private_key(key_path)
    
    print(f"   Certificate Subject: {cert.subject.rfc4514_string()}")
    print(f"   Certificate Expires: {cert.not_valid_after}")
    
    # Step 3: Sign SAML assertion using SignXML
    print("\n3. Signing SAML assertion with SignXML...")
    
    # Convert private key to PEM bytes
    from cryptography.hazmat.primitives import serialization
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Convert certificate to PEM bytes
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    
    # Create signer with explicit RSA-SHA256 configuration
    signer = XMLSigner(
        signature_algorithm=SignatureMethod.RSA_SHA256,
        digest_algorithm=DigestAlgorithm.SHA256
    )
    
    # Sign the assertion
    signed_assertion = signer.sign(
        assertion,
        key=key_pem,
        cert=cert_pem
    )
    
    print("   ✓ Assertion signed successfully with RSA-SHA256")
    print(f"   Signature element added: {signed_assertion.find('.//{http://www.w3.org/2000/09/xmldsig#}Signature') is not None}")
    
    # Step 4: Verify the signature
    print("\n4. Verifying signature...")
    
    verifier = XMLVerifier()
    
    try:
        verified_data = verifier.verify(
            signed_assertion,
            x509_cert=cert_pem
        )
        print("   ✓ Signature verification SUCCESSFUL")
        print(f"   Verified data type: {type(verified_data.signed_xml)}")
    except Exception as e:
        print(f"   ✗ Signature verification FAILED: {e}")
        return
    
    # Step 5: Test tampering detection
    print("\n5. Testing tampering detection...")
    
    # Tamper with the signed assertion
    tampered = etree.fromstring(etree.tostring(signed_assertion))
    subject_elem = tampered.find('.//{*}Subject/{*}NameID')
    original_subject = subject_elem.text
    subject_elem.text = "TAMPERED-DATA"
    
    print(f"   Original subject: {original_subject}")
    print(f"   Tampered subject: {subject_elem.text}")
    
    try:
        verifier.verify(tampered, x509_cert=cert_pem)
        print("   ✗ ERROR: Tampered signature verified (should have failed!)")
    except Exception as e:
        print(f"   ✓ Tampering detected correctly: {type(e).__name__}")
    
    # Step 6: Display signed XML
    print("\n6. Signed SAML Assertion (excerpt):")
    print("-" * 70)
    signed_xml_str = etree.tostring(signed_assertion, pretty_print=True, encoding='unicode')
    # Show first 1000 characters
    print(signed_xml_str[:1000])
    if len(signed_xml_str) > 1000:
        print(f"... (truncated, {len(signed_xml_str) - 1000} more characters)")
    print("-" * 70)
    
    print("\n" + "=" * 70)
    print("✅ SignXML Example Complete!")
    print("=" * 70)
    print("\nKey Findings:")
    print("  • SignXML successfully signs SAML assertions")
    print("  • RSA-SHA256 signature algorithm supported")
    print("  • Signature verification works correctly")
    print("  • Tampering detection functions properly")
    print("  • No compilation required on Windows")
    print("  • Only dependencies: lxml + cryptography (both have wheels)")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
