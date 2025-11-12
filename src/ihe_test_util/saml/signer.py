"""XML signing module using signxml library.

This module provides functionality for signing SAML assertions using XML Signature
(XMLDSig) with RSA-SHA256 and C14N canonicalization. Uses signxml library for
pure Python implementation with zero compilation requirements.
"""

import logging
from typing import List, Optional

from lxml import etree
from signxml import DigestAlgorithm, SignatureMethod, XMLSigner
from signxml.exceptions import InvalidInput

from ..models.saml import CertificateBundle, SAMLAssertion
from ..utils.exceptions import CertificateLoadError

logger = logging.getLogger(__name__)

# XML Signature namespace
DS_NS = "http://www.w3.org/2000/09/xmldsig#"


class SAMLSigner:
    """Sign SAML assertions with XML digital signatures.
    
    This class provides methods to sign SAML 2.0 assertions using W3C XML Signature
    with configurable signature algorithms (default RSA-SHA256) and C14N canonicalization.
    Supports both single assertion signing and optimized batch signing.
    
    Attributes:
        cert_bundle: Certificate bundle containing certificate and private key
        signature_algorithm: Signature algorithm (RSA-SHA256, RSA-SHA512)
        signer: XMLSigner instance configured with signature algorithm
        
    Example:
        >>> from pathlib import Path
        >>> from ihe_test_util.saml.certificate_manager import load_certificate
        >>> from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
        >>> 
        >>> # Load certificate
        >>> cert_bundle = load_certificate(Path("certs/saml.p12"), password=b"secret")
        >>> 
        >>> # Generate SAML assertion
        >>> generator = SAMLProgrammaticGenerator()
        >>> assertion = generator.generate(
        ...     subject="user@example.com",
        ...     issuer="https://idp.example.com",
        ...     audience="https://sp.example.com"
        ... )
        >>> 
        >>> # Sign assertion
        >>> signer = SAMLSigner(cert_bundle)
        >>> signed_assertion = signer.sign_assertion(assertion)
        >>> assert "<ds:Signature" in signed_assertion.xml_content
    """
    
    def __init__(
        self,
        cert_bundle: CertificateBundle,
        signature_algorithm: str = "RSA-SHA256"
    ) -> None:
        """Initialize SAML signer with certificate bundle.
        
        Args:
            cert_bundle: Certificate bundle containing certificate and private key
            signature_algorithm: Signature algorithm (RSA-SHA256, RSA-SHA512)
            
        Raises:
            CertificateLoadError: If certificate bundle is invalid or missing key
            ValueError: If signature algorithm is unsupported
            
        Example:
            >>> cert_bundle = load_certificate(Path("certs/saml.p12"), password=b"secret")
            >>> signer = SAMLSigner(cert_bundle, signature_algorithm="RSA-SHA256")
        """
        # Validate certificate bundle
        if not cert_bundle.certificate:
            raise CertificateLoadError(
                "Certificate bundle must contain a valid certificate. "
                "Ensure certificate was loaded correctly."
            )
        
        if not cert_bundle.private_key:
            raise CertificateLoadError(
                "Certificate bundle must contain a private key for signing. "
                "Ensure private key was loaded with certificate (use PKCS12 or provide key_path)."
            )
        
        self.cert_bundle = cert_bundle
        self.signature_algorithm = signature_algorithm
        
        # Map signature algorithm string to SignatureMethod enum
        algorithm_map = {
            "RSA-SHA256": SignatureMethod.RSA_SHA256,
            "RSA-SHA512": SignatureMethod.RSA_SHA512,
        }
        
        if signature_algorithm not in algorithm_map:
            raise ValueError(
                f"Unsupported signature algorithm: {signature_algorithm}. "
                f"Supported algorithms: {', '.join(algorithm_map.keys())}"
            )
        
        # Create XMLSigner with configured algorithm
        self.signer = XMLSigner(
            signature_algorithm=algorithm_map[signature_algorithm],
            digest_algorithm=DigestAlgorithm.SHA256
        )
        
        logger.info(
            f"SAMLSigner initialized: algorithm={signature_algorithm}, "
            f"certificate={cert_bundle.info.subject}"
        )
    
    def sign_assertion(self, saml_assertion: SAMLAssertion) -> SAMLAssertion:
        """Sign SAML assertion with XML digital signature.
        
        Applies W3C XML Signature with configured signature algorithm to the provided
        SAML assertion. The signature is embedded as a child element of the assertion
        and includes the signing certificate in KeyInfo.
        
        Args:
            saml_assertion: Unsigned SAML assertion to sign
            
        Returns:
            New SAMLAssertion with signature embedded in xml_content and
            signature field populated with base64 signature value
            
        Raises:
            ValueError: If SAML assertion has invalid XML structure
            InvalidInput: If certificate or key is invalid (from signxml)
            
        Example:
            >>> signer = SAMLSigner(cert_bundle)
            >>> unsigned_assertion = generator.generate(...)
            >>> signed_assertion = signer.sign_assertion(unsigned_assertion)
            >>> assert signed_assertion.signature != ""
            >>> assert "<ds:Signature" in signed_assertion.xml_content
        """
        try:
            logger.info(f"Signing SAML assertion: {saml_assertion.assertion_id}")
            
            # Parse XML content
            assertion_element = etree.fromstring(saml_assertion.xml_content.encode('utf-8'))
            
            # Convert certificate and key to PEM format bytes
            from cryptography.hazmat.primitives import serialization
            
            cert_pem = self.cert_bundle.certificate.public_bytes(
                encoding=serialization.Encoding.PEM
            )
            
            key_pem = self.cert_bundle.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Sign assertion
            signed_element = self.signer.sign(
                assertion_element,
                key=key_pem,
                cert=cert_pem
            )
            
            # Extract signature value
            ns = {'ds': DS_NS}
            sig_value_elem = signed_element.find('.//ds:SignatureValue', ns)
            
            if sig_value_elem is None or sig_value_elem.text is None:
                raise ValueError(
                    "Failed to extract SignatureValue from signed assertion. "
                    "This indicates a signing operation error."
                )
            
            sig_value = sig_value_elem.text
            
            # Serialize signed XML
            signed_xml = etree.tostring(signed_element, encoding='unicode')
            
            # Create new SAMLAssertion with signature
            from dataclasses import replace
            signed_assertion = replace(
                saml_assertion,
                xml_content=signed_xml,
                signature=sig_value,
                certificate_subject=self.cert_bundle.info.subject
            )
            
            logger.info(
                f"SAML assertion signed successfully: {saml_assertion.assertion_id}"
            )
            
            return signed_assertion
            
        except etree.XMLSyntaxError as e:
            logger.error(f"Invalid XML structure in SAML assertion: {e}")
            raise ValueError(
                f"Invalid XML structure in SAML assertion: {e}. "
                f"Ensure xml_content is well-formed XML."
            )
        
        except InvalidInput as e:
            logger.error(f"Invalid certificate or private key: {e}")
            raise InvalidInput(
                f"Invalid certificate or private key: {e}. "
                f"Verify certificate bundle is correct."
            )
        
        except Exception as e:
            logger.error(f"Unexpected error during SAML signing: {e}")
            raise ValueError(
                f"Unexpected error during SAML signing: {e}. "
                f"Check certificate, key, and XML content."
            )
    
    def sign_batch(self, assertions: List[SAMLAssertion]) -> List[SAMLAssertion]:
        """Sign multiple SAML assertions with optimized batch processing.
        
        Signs multiple assertions efficiently by reusing the same XMLSigner
        instance and certificate/key configuration. Continues processing even
        if individual assertions fail, returning all successfully signed assertions.
        
        Args:
            assertions: List of SAML assertions to sign
            
        Returns:
            List of signed SAMLAssertion objects (may be partial if some failed)
            
        Example:
            >>> assertions = [generator.generate(...) for _ in range(10)]
            >>> signer = SAMLSigner(cert_bundle)
            >>> signed_assertions = signer.sign_batch(assertions)
            >>> assert len(signed_assertions) == 10
        """
        import time
        
        logger.info(f"Starting batch signing: {len(assertions)} assertions")
        start_time = time.time()
        
        signed_assertions: List[SAMLAssertion] = []
        failed_count = 0
        
        for idx, assertion in enumerate(assertions):
            try:
                signed = self.sign_assertion(assertion)
                signed_assertions.append(signed)
            except Exception as e:
                logger.error(
                    f"Failed to sign assertion {idx + 1}/{len(assertions)} "
                    f"(ID: {assertion.assertion_id}): {e}"
                )
                failed_count += 1
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Batch signing complete: {len(signed_assertions)}/{len(assertions)} successful, "
            f"{failed_count} failed, duration={duration_ms:.1f}ms"
        )
        
        return signed_assertions
