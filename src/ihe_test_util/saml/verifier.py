"""XML signature verification module using signxml library.

This module provides functionality for verifying XML signatures on SAML assertions
and validating assertion timestamp freshness. Uses signxml library for pure Python
implementation with zero compilation requirements.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from lxml import etree
from signxml import XMLVerifier
from signxml.exceptions import InvalidDigest, InvalidSignature

from ..models.saml import CertificateBundle, SAMLAssertion
from ..utils.exceptions import CertificateLoadError

logger = logging.getLogger(__name__)

# XML Signature namespace
DS_NS = "http://www.w3.org/2000/09/xmldsig#"


class SAMLVerifier:
    """Verify XML signatures on SAML assertions.
    
    This class provides methods to verify XML Signature on SAML 2.0 assertions
    and validate assertion timestamp freshness. Uses signxml library for
    standards-compliant signature verification.
    
    Attributes:
        cert_bundle: Optional certificate bundle for verification
        
    Example:
        >>> from pathlib import Path
        >>> from ihe_test_util.saml.certificate_manager import load_certificate
        >>> 
        >>> # Load certificate
        >>> cert_bundle = load_certificate(Path("certs/saml.p12"), password=b"secret")
        >>> 
        >>> # Verify signed assertion
        >>> verifier = SAMLVerifier(cert_bundle)
        >>> is_valid = verifier.verify_assertion(signed_assertion)
        >>> assert is_valid is True
    """
    
    def __init__(self, cert_bundle: Optional[CertificateBundle] = None) -> None:
        """Initialize SAML verifier.
        
        Args:
            cert_bundle: Optional certificate bundle for verification
                        (certificate extracted from signature if not provided)
        
        Example:
            >>> verifier = SAMLVerifier()  # Use certificate from signature
            >>> # or
            >>> verifier = SAMLVerifier(cert_bundle)  # Use specific certificate
        """
        self.cert_bundle = cert_bundle
        
        logger.debug(
            f"SAMLVerifier initialized "
            f"(cert_bundle={'provided' if cert_bundle else 'will extract from signature'})"
        )
    
    def verify_assertion(
        self,
        saml_assertion: SAMLAssertion,
        cert: Optional[str] = None
    ) -> bool:
        """Verify XML signature on SAML assertion.
        
        Verifies the XML Signature embedded in the SAML assertion using either
        the provided certificate, the instance certificate bundle, or the
        certificate extracted from the signature's KeyInfo element.
        
        Args:
            saml_assertion: Signed SAML assertion to verify
            cert: Optional PEM-encoded certificate string for verification
            
        Returns:
            True if signature is valid, False otherwise
            
        Raises:
            InvalidSignature: Signature verification failed (tampered or wrong cert)
            InvalidDigest: Content was modified after signing (tampering detected)
            ValueError: If XML structure is invalid
            
        Example:
            >>> verifier = SAMLVerifier(cert_bundle)
            >>> is_valid = verifier.verify_assertion(signed_assertion)
            >>> if is_valid:
            ...     print("✅ Signature verified")
        """
        try:
            logger.info(f"Verifying SAML assertion: {saml_assertion.assertion_id}")
            
            # Parse signed XML
            signed_element = etree.fromstring(saml_assertion.xml_content.encode('utf-8'))
            
            # Check that signature element exists
            ns = {'ds': DS_NS}
            sig_element = signed_element.find('.//ds:Signature', ns)
            
            if sig_element is None:
                logger.warning(
                    f"No Signature element found in assertion {saml_assertion.assertion_id}"
                )
                return False
            
            # Create verifier
            verifier = XMLVerifier()
            
            # Prepare certificate for verification
            cert_pem: Optional[bytes] = None
            
            if cert:
                # Use provided certificate string
                cert_pem = cert.encode('utf-8')
                logger.debug("Using provided certificate for verification")
            elif self.cert_bundle:
                # Use certificate from bundle
                from cryptography.hazmat.primitives import serialization
                
                cert_pem = self.cert_bundle.certificate.public_bytes(
                    encoding=serialization.Encoding.PEM
                )
                logger.debug("Using certificate from bundle for verification")
            else:
                # Certificate will be extracted from KeyInfo
                logger.debug("Will extract certificate from signature KeyInfo")
            
            # Verify signature
            if cert_pem:
                verified_data = verifier.verify(signed_element, x509_cert=cert_pem)
            else:
                verified_data = verifier.verify(signed_element)
            
            logger.info(
                f"Signature verification successful: {saml_assertion.assertion_id}"
            )
            return True
            
        except InvalidSignature as e:
            logger.warning(
                f"SAML signature verification failed for {saml_assertion.assertion_id}: {e}. "
                f"Assertion may be tampered or signed with different certificate."
            )
            raise InvalidSignature(
                f"SAML signature verification failed: {e}. "
                f"Assertion may be tampered or signed with different certificate."
            )
        
        except InvalidDigest as e:
            logger.warning(
                f"SAML digest verification failed for {saml_assertion.assertion_id}: {e}. "
                f"Assertion content has been modified after signing."
            )
            raise InvalidDigest(
                f"SAML digest verification failed: {e}. "
                f"Assertion content has been modified after signing."
            )
        
        except etree.XMLSyntaxError as e:
            logger.error(
                f"Invalid XML in signed SAML assertion {saml_assertion.assertion_id}: {e}"
            )
            raise ValueError(
                f"Invalid XML in signed SAML assertion: {e}. "
                f"XML may be corrupted."
            )
        
        except Exception as e:
            logger.error(
                f"Unexpected error during signature verification for "
                f"{saml_assertion.assertion_id}: {e}"
            )
            raise ValueError(
                f"Unexpected error during signature verification: {e}. "
                f"Check certificate and XML structure."
            )
    
    def validate_timestamp_freshness(
        self,
        saml_assertion: SAMLAssertion,
        max_age_minutes: int = 5
    ) -> bool:
        """Validate SAML assertion timestamp freshness.
        
        Checks that the assertion is not expired, not yet valid, and not older
        than the specified maximum age. This prevents replay attacks and ensures
        assertions are used within their intended validity period.
        
        Args:
            saml_assertion: SAML assertion to validate
            max_age_minutes: Maximum assertion age in minutes (default: 5)
            
        Returns:
            True if assertion is fresh and within validity period, False otherwise
            
        Example:
            >>> verifier = SAMLVerifier()
            >>> is_fresh = verifier.validate_timestamp_freshness(assertion, max_age_minutes=5)
            >>> if is_fresh:
            ...     print("✅ Assertion is fresh")
        """
        now = datetime.now(timezone.utc)
        
        logger.debug(
            f"Validating timestamp freshness for {saml_assertion.assertion_id}: "
            f"now={now.isoformat()}, "
            f"issue_instant={saml_assertion.issue_instant.isoformat()}, "
            f"not_before={saml_assertion.not_before.isoformat()}, "
            f"not_on_or_after={saml_assertion.not_on_or_after.isoformat()}"
        )
        
        # Check if assertion is not yet valid
        if saml_assertion.not_before > now:
            logger.warning(
                f"SAML assertion {saml_assertion.assertion_id} not yet valid. "
                f"NotBefore: {saml_assertion.not_before.isoformat()}, "
                f"Current: {now.isoformat()}"
            )
            return False
        
        # Check if assertion is expired
        if saml_assertion.not_on_or_after < now:
            logger.warning(
                f"SAML assertion {saml_assertion.assertion_id} expired. "
                f"NotOnOrAfter: {saml_assertion.not_on_or_after.isoformat()}, "
                f"Current: {now.isoformat()}"
            )
            return False
        
        # Check assertion age (from issue_instant)
        age = now - saml_assertion.issue_instant
        max_age = timedelta(minutes=max_age_minutes)
        
        if age > max_age:
            logger.warning(
                f"SAML assertion {saml_assertion.assertion_id} too old. "
                f"Age: {age.total_seconds():.1f}s, "
                f"Max age: {max_age.total_seconds():.1f}s"
            )
            return False
        
        logger.info(
            f"Timestamp validation successful for {saml_assertion.assertion_id}: "
            f"age={age.total_seconds():.1f}s"
        )
        return True
    
    def verify_and_validate(
        self,
        saml_assertion: SAMLAssertion,
        max_age_minutes: int = 5,
        cert: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Verify signature and validate timestamp freshness in one call.
        
        Convenience method that performs both signature verification and
        timestamp freshness validation, returning a combined result.
        
        Args:
            saml_assertion: Signed SAML assertion to verify
            max_age_minutes: Maximum assertion age in minutes (default: 5)
            cert: Optional PEM-encoded certificate string for verification
            
        Returns:
            Tuple of (is_valid: bool, message: str) with validation result
            
        Example:
            >>> verifier = SAMLVerifier(cert_bundle)
            >>> is_valid, message = verifier.verify_and_validate(signed_assertion)
            >>> if is_valid:
            ...     print(f"✅ {message}")
            ... else:
            ...     print(f"❌ {message}")
        """
        try:
            # Verify signature
            is_signature_valid = self.verify_assertion(saml_assertion, cert)
            
            if not is_signature_valid:
                return False, "Signature verification failed"
            
            # Validate timestamp freshness
            is_fresh = self.validate_timestamp_freshness(saml_assertion, max_age_minutes)
            
            if not is_fresh:
                return False, "Assertion expired or not yet valid"
            
            return True, "Signature and timestamp validation successful"
            
        except InvalidSignature as e:
            return False, f"Signature verification failed: {e}"
        
        except InvalidDigest as e:
            return False, f"Digest verification failed (tampering detected): {e}"
        
        except Exception as e:
            return False, f"Validation error: {e}"
