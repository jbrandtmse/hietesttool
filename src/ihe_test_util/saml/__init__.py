"""SAML 2.0 assertion generation, signing, and verification module.

This module provides functionality for:
- Generating SAML 2.0 assertions
- Signing SAML assertions with X.509 certificates (using SignXML)
- Verifying XML signatures
- Managing certificates in multiple formats (PEM, PKCS12, DER)

Note: This spike initially explored python-xmlsec but found Windows installation
issues. SignXML (pure Python with lxml/cryptography) is the recommended alternative.
"""

from ihe_test_util.saml.generator import generate_saml_assertion
from ihe_test_util.saml.certificate_manager import CertificateManager

# Note: signer.py and verifier.py contain python-xmlsec implementations
# For production use, recommend SignXML library instead (see examples/signxml_saml_example.py)

__all__ = [
    "generate_saml_assertion",
    "CertificateManager",
]
