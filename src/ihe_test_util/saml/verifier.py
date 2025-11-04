"""XML signature verification module using python-xmlsec.

This module provides functionality for verifying XML signatures on SAML
assertions and other signed XML documents.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

import xmlsec
from cryptography import x509
from lxml import etree

logger = logging.getLogger(__name__)

# XML Signature namespace
DS_NS = "http://www.w3.org/2000/09/xmldsig#"


def verify_xml_signature(
    signed_xml: etree._Element,
    certificate_path: Optional[Path] = None,
    certificate: Optional[x509.Certificate] = None,
) -> Tuple[bool, str]:
    """Verify XML signature using certificate.

    This function verifies an XML Signature embedded in an XML element.
    The certificate can be provided either as a file path or as a
    cryptography Certificate object. If neither is provided, the function
    will attempt to extract the certificate from the KeyInfo element.

    Args:
        signed_xml: Signed XML element containing Signature
        certificate_path: Optional path to certificate file for verification
        certificate: Optional X.509 certificate object for verification

    Returns:
        Tuple of (success: bool, message: str) indicating verification result

    Raises:
        ValueError: If signature element not found or invalid
        xmlsec.Error: If verification process fails
    """
    try:
        # Find signature node
        signature_node = signed_xml.find(f".//{{{DS_NS}}}Signature")
        
        if signature_node is None:
            return False, "No Signature element found in XML"
        
        logger.info("Found Signature element, proceeding with verification")
        
        # Create signature context
        ctx = xmlsec.SignatureContext()
        
        # Load certificate if provided
        if certificate_path:
            if not certificate_path.exists():
                return False, f"Certificate file not found: {certificate_path}"
            
            logger.info(f"Loading certificate from: {certificate_path.name}")
            key = xmlsec.Key.from_file(
                str(certificate_path),
                xmlsec.constants.KeyDataFormatPem,
            )
            ctx.key = key
            
        elif certificate:
            # Convert certificate to PEM and load
            from cryptography.hazmat.primitives import serialization
            
            cert_pem = certificate.public_bytes(encoding=serialization.Encoding.PEM)
            
            logger.info(f"Loading certificate: {certificate.subject.rfc4514_string()}")
            key = xmlsec.Key.from_memory(
                cert_pem,
                xmlsec.constants.KeyDataFormatPem,
            )
            ctx.key = key
        
        # If no certificate provided, try to extract from KeyInfo
        else:
            logger.info("No certificate provided, will use KeyInfo from signature")
            # xmlsec will automatically use certificate from KeyInfo if present
        
        # Verify signature
        logger.info("Verifying XML signature")
        ctx.verify(signature_node)
        
        logger.info("Signature verification successful")
        return True, "Signature is valid"
        
    except xmlsec.VerificationError as e:
        logger.warning(f"Signature verification failed: {e}")
        return False, f"Signature verification failed: {e}"
        
    except xmlsec.Error as e:
        logger.error(f"xmlsec error during verification: {e}")
        return False, f"Verification error: {e}"
        
    except Exception as e:
        logger.error(f"Unexpected error during verification: {e}")
        return False, f"Unexpected verification error: {e}"


def extract_certificate_from_signature(
    signed_xml: etree._Element,
) -> Optional[x509.Certificate]:
    """Extract X.509 certificate from signature KeyInfo element.

    Args:
        signed_xml: Signed XML element containing Signature

    Returns:
        X.509 Certificate if found, None otherwise

    Raises:
        ValueError: If signature structure is invalid
    """
    try:
        # Find X509Certificate element within KeyInfo
        cert_elem = signed_xml.find(
            f".//{{{DS_NS}}}Signature/{{{DS_NS}}}KeyInfo"
            f"/{{{DS_NS}}}X509Data/{{{DS_NS}}}X509Certificate"
        )
        
        if cert_elem is None or not cert_elem.text:
            logger.warning("No X509Certificate found in KeyInfo")
            return None
        
        # Certificate text is base64 encoded DER
        import base64
        cert_der = base64.b64decode(cert_elem.text)
        
        # Load certificate
        from cryptography.hazmat.backends import default_backend
        cert = x509.load_der_x509_certificate(cert_der, default_backend())
        
        logger.info(f"Extracted certificate: {cert.subject.rfc4514_string()}")
        logger.info(f"Certificate expires: {cert.not_valid_after}")
        
        return cert
        
    except Exception as e:
        logger.error(f"Failed to extract certificate from signature: {e}")
        return None


def verify_with_tamper_detection(
    signed_xml: etree._Element,
    certificate_path: Optional[Path] = None,
) -> Tuple[bool, str, dict]:
    """Verify signature and provide detailed tamper detection information.

    Args:
        signed_xml: Signed XML element
        certificate_path: Optional certificate path for verification

    Returns:
        Tuple of (success: bool, message: str, details: dict)
        Details dict contains signature information and validation results
    """
    details = {
        "signature_found": False,
        "certificate_embedded": False,
        "signature_valid": False,
        "signature_method": None,
        "canonicalization_method": None,
    }
    
    try:
        # Find signature node
        signature_node = signed_xml.find(f".//{{{DS_NS}}}Signature")
        
        if signature_node is None:
            return False, "No signature found", details
        
        details["signature_found"] = True
        
        # Extract signature method
        sig_method = signature_node.find(
            f".//{{{DS_NS}}}SignedInfo/{{{DS_NS}}}SignatureMethod"
        )
        if sig_method is not None:
            details["signature_method"] = sig_method.get("Algorithm")
        
        # Extract canonicalization method
        canon_method = signature_node.find(
            f".//{{{DS_NS}}}SignedInfo/{{{DS_NS}}}CanonicalizationMethod"
        )
        if canon_method is not None:
            details["canonicalization_method"] = canon_method.get("Algorithm")
        
        # Check for embedded certificate
        cert = extract_certificate_from_signature(signed_xml)
        if cert:
            details["certificate_embedded"] = True
            details["certificate_subject"] = cert.subject.rfc4514_string()
            details["certificate_expiry"] = str(cert.not_valid_after)
        
        # Verify signature
        success, message = verify_xml_signature(signed_xml, certificate_path)
        details["signature_valid"] = success
        
        return success, message, details
        
    except Exception as e:
        return False, f"Verification error: {e}", details
