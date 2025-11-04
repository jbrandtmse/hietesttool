"""XML signing module using python-xmlsec.

This module provides functionality for signing SAML assertions and other XML
documents using XML Signature (XMLDSig) with RSA-SHA256 and C14N canonicalization.
"""

import logging
from pathlib import Path
from typing import Optional

import xmlsec
from cryptography import x509
from lxml import etree

logger = logging.getLogger(__name__)

# XML Signature namespace
DS_NS = "http://www.w3.org/2000/09/xmldsig#"


def sign_xml(
    xml_element: etree._Element,
    private_key_path: Path,
    certificate: Optional[x509.Certificate] = None,
    key_password: Optional[bytes] = None,
) -> etree._Element:
    """Sign XML element with RSA-SHA256 and embed signature.

    This function signs an XML element (typically a SAML assertion) using
    XML Signature (XMLDSig) with RSA-SHA256 algorithm and Exclusive C14N
    canonicalization. The signature is embedded as a child element.

    Args:
        xml_element: XML element to sign (e.g., SAML Assertion)
        private_key_path: Path to private key file (PEM format)
        certificate: Optional X.509 certificate to embed in KeyInfo
        key_password: Optional password for encrypted private key

    Returns:
        Signed XML element with embedded Signature element

    Raises:
        FileNotFoundError: If private key file does not exist
        xmlsec.Error: If signing operation fails
        ValueError: If XML element is invalid
    """
    if not private_key_path.exists():
        raise FileNotFoundError(f"Private key not found: {private_key_path}")

    try:
        # Initialize xmlsec library
        xmlsec.enable_debug_trace(False)
        
        logger.info("Creating signature template for XML element")
        
        # Create signature template using Exclusive C14N and RSA-SHA256
        signature_node = xmlsec.template.create(
            xml_element,
            xmlsec.constants.TransformExclC14N,
            xmlsec.constants.TransformRsaSha256,
        )
        
        # Add signature node as second child (after Issuer in SAML)
        # For SAML, signature should be after Issuer but before Subject
        if len(xml_element) > 0:
            xml_element.insert(1, signature_node)
        else:
            xml_element.append(signature_node)
        
        # Add Reference node with SHA-256 digest
        ref = xmlsec.template.add_reference(
            signature_node,
            xmlsec.constants.TransformSha256,
            uri="",  # Empty URI means sign the parent element
        )
        
        # Add Enveloped signature transform (signature is within signed element)
        xmlsec.template.add_transform(ref, xmlsec.constants.TransformEnveloped)
        
        # Add Exclusive C14N transform to Reference
        xmlsec.template.add_transform(ref, xmlsec.constants.TransformExclC14N)
        
        # Add KeyInfo node
        key_info = xmlsec.template.ensure_key_info(signature_node)
        
        # Add X509Data to KeyInfo if certificate provided
        if certificate:
            logger.debug("Adding X509 certificate to KeyInfo")
            x509_data = xmlsec.template.add_x509_data(key_info)
            xmlsec.template.x509_data_add_certificate(x509_data)
        
        # Load private key
        logger.info(f"Loading private key from: {private_key_path.name}")
        key = xmlsec.Key.from_file(
            str(private_key_path),
            xmlsec.constants.KeyDataFormatPem,
            password=key_password.decode() if key_password else None,
        )
        
        # Load certificate if provided
        if certificate:
            # Convert certificate to PEM bytes and load into key
            cert_pem = certificate.public_bytes(encoding=serialization.Encoding.PEM)
            key.load_cert_from_memory(cert_pem, xmlsec.constants.KeyDataFormatPem)
        
        # Create signature context and sign
        ctx = xmlsec.SignatureContext()
        ctx.key = key
        
        logger.info("Signing XML element with RSA-SHA256")
        ctx.sign(signature_node)
        
        logger.debug("XML element signed successfully")
        return xml_element
        
    except xmlsec.Error as e:
        logger.error(f"Failed to sign XML: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during XML signing: {e}")
        raise ValueError(f"Failed to sign XML element: {e}")


def sign_xml_with_cert_path(
    xml_element: etree._Element,
    private_key_path: Path,
    certificate_path: Path,
    key_password: Optional[bytes] = None,
) -> etree._Element:
    """Sign XML element using certificate from file path.

    Convenience wrapper around sign_xml that loads certificate from file.

    Args:
        xml_element: XML element to sign
        private_key_path: Path to private key file (PEM format)
        certificate_path: Path to certificate file (PEM format)
        key_password: Optional password for encrypted private key

    Returns:
        Signed XML element

    Raises:
        FileNotFoundError: If certificate or key file not found
        xmlsec.Error: If signing operation fails
    """
    if not certificate_path.exists():
        raise FileNotFoundError(f"Certificate not found: {certificate_path}")
    
    # Load certificate using cryptography
    from ihe_test_util.saml.certificate_manager import CertificateManager
    
    cert = CertificateManager.load_pem_certificate(certificate_path)
    
    return sign_xml(xml_element, private_key_path, cert, key_password)


# Import for certificate conversion
from cryptography.hazmat.primitives import serialization
