"""Certificate management module for loading and handling X.509 certificates.

This module provides functionality for loading certificates and private keys
from multiple formats (PEM, PKCS12, DER) and managing certificate chains.
"""

import logging
from pathlib import Path
from typing import Any, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

logger = logging.getLogger(__name__)


class CertificateManager:
    """Manages X.509 certificates and private keys in multiple formats."""

    @staticmethod
    def load_pem_certificate(cert_path: Path) -> x509.Certificate:
        """Load X.509 certificate from PEM file.

        Args:
            cert_path: Path to PEM certificate file

        Returns:
            Loaded X.509 certificate

        Raises:
            FileNotFoundError: If certificate file does not exist
            ValueError: If certificate file is invalid or corrupted
        """
        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")

        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            
            # Log certificate details (never log full certificate)
            logger.info(f"Loaded PEM certificate: {cert.subject.rfc4514_string()}")
            logger.info(f"Certificate expires: {cert.not_valid_after}")
            
            return cert
        except Exception as e:
            raise ValueError(f"Failed to load PEM certificate from {cert_path}: {e}")

    @staticmethod
    def load_pem_private_key(
        key_path: Path, password: Optional[bytes] = None
    ) -> Any:
        """Load private key from PEM file.

        Args:
            key_path: Path to PEM private key file
            password: Optional password for encrypted private key

        Returns:
            Loaded private key

        Raises:
            FileNotFoundError: If private key file does not exist
            ValueError: If private key file is invalid or password incorrect
        """
        if not key_path.exists():
            raise FileNotFoundError(f"Private key file not found: {key_path}")

        try:
            with open(key_path, "rb") as f:
                key_data = f.read()
            private_key = serialization.load_pem_private_key(
                key_data, password=password, backend=default_backend()
            )
            
            logger.info(f"Loaded PEM private key from: {key_path.name}")
            # NEVER log private key contents
            
            return private_key
        except Exception as e:
            raise ValueError(f"Failed to load PEM private key from {key_path}: {e}")

    @staticmethod
    def load_der_certificate(cert_path: Path) -> x509.Certificate:
        """Load X.509 certificate from DER file.

        Args:
            cert_path: Path to DER certificate file

        Returns:
            Loaded X.509 certificate

        Raises:
            FileNotFoundError: If certificate file does not exist
            ValueError: If certificate file is invalid or corrupted
        """
        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")

        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
            
            logger.info(f"Loaded DER certificate: {cert.subject.rfc4514_string()}")
            logger.info(f"Certificate expires: {cert.not_valid_after}")
            
            return cert
        except Exception as e:
            raise ValueError(f"Failed to load DER certificate from {cert_path}: {e}")

    @staticmethod
    def load_pkcs12(
        pkcs12_path: Path, password: Optional[bytes] = None
    ) -> Tuple[Any, x509.Certificate, list]:
        """Load private key and certificate from PKCS12 file.

        Args:
            pkcs12_path: Path to PKCS12 (.p12 or .pfx) file
            password: Password for PKCS12 file (required for most PKCS12 files)

        Returns:
            Tuple of (private_key, certificate, additional_certificates)

        Raises:
            FileNotFoundError: If PKCS12 file does not exist
            ValueError: If PKCS12 file is invalid or password incorrect
        """
        if not pkcs12_path.exists():
            raise FileNotFoundError(f"PKCS12 file not found: {pkcs12_path}")

        try:
            with open(pkcs12_path, "rb") as f:
                pkcs12_data = f.read()
            
            # Load PKCS12
            private_key, certificate, additional_certs = (
                serialization.pkcs12.load_key_and_certificates(
                    pkcs12_data, password=password, backend=default_backend()
                )
            )
            
            if certificate:
                logger.info(
                    f"Loaded PKCS12 certificate: {certificate.subject.rfc4514_string()}"
                )
                logger.info(f"Certificate expires: {certificate.not_valid_after}")
            
            if additional_certs:
                logger.info(f"Loaded {len(additional_certs)} additional certificates from chain")
            
            return private_key, certificate, additional_certs or []
        except Exception as e:
            raise ValueError(f"Failed to load PKCS12 from {pkcs12_path}: {e}")

    @staticmethod
    def convert_to_pem(
        cert: x509.Certificate,
    ) -> bytes:
        """Convert certificate to PEM format bytes.

        Args:
            cert: X.509 certificate to convert

        Returns:
            Certificate in PEM format as bytes
        """
        return cert.public_bytes(Encoding.PEM)

    @staticmethod
    def convert_key_to_pem(
        private_key: Any, password: Optional[bytes] = None
    ) -> bytes:
        """Convert private key to PEM format bytes.

        Args:
            private_key: Private key to convert
            password: Optional password to encrypt the private key

        Returns:
            Private key in PEM format as bytes
        """
        encryption = (
            serialization.BestAvailableEncryption(password)
            if password
            else serialization.NoEncryption()
        )
        
        return private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )
