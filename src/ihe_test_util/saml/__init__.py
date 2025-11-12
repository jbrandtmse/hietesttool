"""SAML 2.0 assertion generation, signing, and verification module.

This module provides functionality for:
- Generating SAML 2.0 assertions (template-based and programmatic)
- Signing SAML assertions with X.509 certificates (using SignXML)
- Verifying XML signatures
- Managing certificates in multiple formats (PEM, PKCS12, DER)

Note: This spike initially explored python-xmlsec but found Windows installation
issues. SignXML (pure Python with lxml/cryptography) is the recommended alternative.
"""

from ihe_test_util.saml.generator import generate_saml_assertion
from ihe_test_util.saml.certificate_manager import (
    load_certificate,
    load_pem_certificate,
    load_pem_private_key,
    load_pkcs12_certificate,
    load_der_certificate,
    validate_certificate,
    get_certificate_info,
    check_expiration_warning,
    clear_certificate_cache,
)
from ihe_test_util.saml.template_loader import (
    SAMLTemplatePersonalizer,
    load_saml_template,
    validate_saml_template,
    personalize_saml_template,
    canonicalize_saml,
    extract_saml_placeholders,
    generate_saml_timestamps as template_generate_saml_timestamps,
    generate_assertion_id as template_generate_assertion_id,
)
from ihe_test_util.saml.programmatic_generator import (
    SAMLProgrammaticGenerator,
    generate_assertion_id,
    generate_saml_timestamps,
)

# Note: signer.py and verifier.py contain python-xmlsec implementations
# For production use, recommend SignXML library instead (see examples/signxml_saml_example.py)

__all__ = [
    # Spike generator (legacy)
    "generate_saml_assertion",
    # Certificate management
    "load_certificate",
    "load_pem_certificate",
    "load_pem_private_key",
    "load_pkcs12_certificate",
    "load_der_certificate",
    "validate_certificate",
    "get_certificate_info",
    "check_expiration_warning",
    "clear_certificate_cache",
    # Template-based generation (Story 4.2)
    "SAMLTemplatePersonalizer",
    "load_saml_template",
    "validate_saml_template",
    "personalize_saml_template",
    "canonicalize_saml",
    "extract_saml_placeholders",
    # Programmatic generation (Story 4.3)
    "SAMLProgrammaticGenerator",
    "generate_assertion_id",
    "generate_saml_timestamps",
]
