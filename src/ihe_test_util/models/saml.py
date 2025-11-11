"""Data models for SAML and certificate handling.

This module defines dataclasses for SAML-related operations, including
certificate information, validation results, and certificate bundles.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

from cryptography import x509


@dataclass
class CertificateInfo:
    """Certificate information for display and logging.
    
    Contains extracted metadata from X.509 certificates without
    exposing sensitive key material.
    
    Attributes:
        subject: Certificate subject Distinguished Name (DN)
        issuer: Certificate issuer Distinguished Name (DN)
        not_before: Certificate validity start date
        not_after: Certificate expiration date
        serial_number: Certificate serial number
        key_size: Public key size in bits (e.g., 2048, 4096)
    """
    
    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime
    serial_number: int
    key_size: Optional[int]


@dataclass
class ValidationResult:
    """Result of certificate validation.
    
    Attributes:
        is_valid: True if certificate passes all validation checks
        errors: List of validation errors (blocking issues)
        warnings: List of validation warnings (non-blocking concerns)
    """
    
    is_valid: bool
    errors: List[str]
    warnings: List[str]


@dataclass
class CertificateBundle:
    """Complete certificate bundle with key and chain.
    
    Represents a loaded certificate with its associated private key,
    certificate chain, and metadata information.
    
    Attributes:
        certificate: X.509 certificate
        private_key: Private key (if available)
        chain: Certificate chain (root, intermediate, leaf)
        info: Extracted certificate information
    """
    
    certificate: x509.Certificate
    private_key: Optional[Any]
    chain: List[x509.Certificate]
    info: CertificateInfo
