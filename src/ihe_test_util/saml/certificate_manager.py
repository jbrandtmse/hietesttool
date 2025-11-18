"""Certificate management module for loading and handling X.509 certificates.

This module provides functionality for loading certificates and private keys
from multiple formats (PEM, PKCS12, DER), validating certificates, caching,
and managing certificate chains.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.hazmat.primitives.serialization import pkcs12

from ..models.saml import CertificateBundle, CertificateInfo, ValidationResult
from ..utils.exceptions import (
    CertificateExpiredError,
    CertificateLoadError,
    CertificateValidationError,
)

logger = logging.getLogger(__name__)


class CertificateCache:
    """In-memory certificate cache to avoid repeated file I/O.
    
    Caches certificate bundles keyed by file path and modification time.
    Automatically invalidates cache entries when files are modified.
    """

    def __init__(self) -> None:
        """Initialize empty certificate cache."""
        self._cache: Dict[str, Tuple[float, CertificateBundle]] = {}

    def get(self, cert_path: Path) -> Optional[CertificateBundle]:
        """Get cached certificate if file hasn't changed.

        Args:
            cert_path: Path to certificate file

        Returns:
            Cached CertificateBundle or None if not cached or stale
        """
        cache_key = str(cert_path.absolute())
        if cache_key not in self._cache:
            return None

        cached_mtime, bundle = self._cache[cache_key]
        
        try:
            current_mtime = os.path.getmtime(cert_path)
        except OSError:
            # File no longer exists or accessible, invalidate cache
            del self._cache[cache_key]
            return None

        if current_mtime != cached_mtime:
            # File changed, invalidate cache
            del self._cache[cache_key]
            return None

        logger.debug(f"Cache hit for {cert_path.name}")
        return bundle

    def put(self, cert_path: Path, bundle: CertificateBundle) -> None:
        """Cache certificate bundle.

        Args:
            cert_path: Path to certificate file
            bundle: CertificateBundle to cache
        """
        cache_key = str(cert_path.absolute())
        try:
            mtime = os.path.getmtime(cert_path)
            self._cache[cache_key] = (mtime, bundle)
            logger.debug(f"Cached certificate: {cert_path.name}")
        except OSError as e:
            logger.warning(f"Failed to cache certificate {cert_path.name}: {e}")

    def clear(self) -> None:
        """Clear all cached certificates."""
        self._cache.clear()
        logger.debug("Certificate cache cleared")


# Global certificate cache instance
_certificate_cache = CertificateCache()


def get_certificate_info(cert: x509.Certificate) -> CertificateInfo:
    """Extract certificate information for display and logging.

    Args:
        cert: X.509 certificate

    Returns:
        CertificateInfo dataclass with certificate details

    Example:
        >>> cert = load_pem_certificate(Path("test_cert.pem"))
        >>> info = get_certificate_info(cert)
        >>> print(info.subject)
        CN=Test Certificate
    """
    # Get public key size
    public_key = cert.public_key()
    key_size = public_key.key_size if hasattr(public_key, "key_size") else None

    return CertificateInfo(
        subject=cert.subject.rfc4514_string(),
        issuer=cert.issuer.rfc4514_string(),
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        serial_number=cert.serial_number,
        key_size=key_size,
    )


def check_expiration_warning(
    cert: x509.Certificate, warning_days: int = 30
) -> bool:
    """Check if certificate is expiring soon and log warning.

    Args:
        cert: X.509 certificate to check
        warning_days: Number of days before expiration to warn (default: 30)

    Returns:
        True if certificate expires within warning_days, False otherwise

    Example:
        >>> cert = load_pem_certificate(Path("test_cert.pem"))
        >>> if check_expiration_warning(cert):
        ...     print("Certificate expiring soon!")
    """
    now = datetime.now(timezone.utc)
    warning_date = now + timedelta(days=warning_days)

    if cert.not_valid_after_utc < warning_date:
        days_remaining = (cert.not_valid_after_utc - now).days
        logger.warning(
            f"⚠️  Certificate expiring soon: {days_remaining} days remaining "
            f"(expires: {cert.not_valid_after_utc.strftime('%Y-%m-%d')})"
        )
        return True

    return False


def validate_certificate_not_expired(cert_path: Path) -> ValidationResult:
    """Validate that certificate has not expired.
    
    Checks certificate validity dates and calculates days until expiration.
    Provides actionable error messages with remediation guidance.
    
    Args:
        cert_path: Path to certificate file
        
    Returns:
        ValidationResult with validation status and remediation guidance
        
    Raises:
        CertificateLoadError: If certificate cannot be loaded
        
    Example:
        >>> result = validate_certificate_not_expired(Path("cert.pem"))
        >>> if not result.is_valid:
        ...     print(result.errors[0])
        Certificate expired on 2024-01-15. Generate new: scripts/generate_cert.sh
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    # Load certificate
    try:
        cert = load_pem_certificate(cert_path)
    except CertificateLoadError:
        # Try other formats
        if cert_path.suffix.lower() in ['.p12', '.pfx']:
            cert, _, _ = load_pkcs12_certificate(cert_path)
        elif cert_path.suffix.lower() == '.der':
            cert = load_der_certificate(cert_path)
        else:
            raise
    
    now = datetime.now(timezone.utc)
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    
    # Check not yet valid
    if now < not_before:
        errors.append(
            f"Certificate not yet valid. Valid from: {not_before.strftime('%Y-%m-%d')}. "
            f"Check system time or use a different certificate."
        )
    
    # Check expired (CRITICAL)
    if now > not_after:
        days_expired = (now - not_after).days
        errors.append(
            f"Certificate expired {days_expired} days ago on {not_after.strftime('%Y-%m-%d')}. "
            f"Generate new certificate: scripts/generate_cert.sh. "
            f"Update config.json with new certificate path."
        )
    
    # Check expiring soon (WARNING - within 30 days)
    days_until_expiry = (not_after - now).days
    if 0 < days_until_expiry < 30:
        warnings.append(
            f"Certificate expires in {days_until_expiry} days on {not_after.strftime('%Y-%m-%d')}. "
            f"Generate new certificate soon: scripts/generate_cert.sh"
        )
    
    is_valid = len(errors) == 0
    
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def validate_certificate_chain(cert_path: Path) -> ValidationResult:
    """Validate certificate chain of trust.
    
    Verifies that certificate has a valid chain and checks for basic
    certificate chain issues.
    
    Args:
        cert_path: Path to certificate file
        
    Returns:
        ValidationResult with validation status
        
    Note:
        Full chain validation requires CA certificates. This function
        performs basic validation only.
        
    Example:
        >>> result = validate_certificate_chain(Path("cert.pem"))
        >>> if result.warnings:
        ...     for warning in result.warnings:
        ...         print(warning)
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    # Load certificate
    try:
        cert = load_pem_certificate(cert_path)
    except CertificateLoadError:
        if cert_path.suffix.lower() in ['.p12', '.pfx']:
            cert, _, chain = load_pkcs12_certificate(cert_path)
            if not chain:
                warnings.append(
                    "No certificate chain found in PKCS12 file. "
                    "For production use, include full certificate chain."
                )
        elif cert_path.suffix.lower() == '.der':
            cert = load_der_certificate(cert_path)
            warnings.append(
                "DER format does not include certificate chain. "
                "For production, use PKCS12 with full chain or provide separate chain file."
            )
        else:
            raise
    
    # Check if self-signed
    if cert.issuer == cert.subject:
        warnings.append(
            "Certificate is self-signed. This is acceptable for development/testing only. "
            "For production, use certificate from trusted CA."
        )
    
    is_valid = len(errors) == 0
    
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def validate_certificate(cert: x509.Certificate) -> ValidationResult:
    """Validate certificate for use in signing operations.

    Checks certificate validity period and generates warnings for
    certificates expiring soon.

    Args:
        cert: X.509 certificate to validate

    Returns:
        ValidationResult with is_valid flag and any errors/warnings

    Example:
        >>> cert = load_pem_certificate(Path("test_cert.pem"))
        >>> result = validate_certificate(cert)
        >>> if not result.is_valid:
        ...     print(f"Validation failed: {result.errors}")
    """
    errors: List[str] = []
    warnings: List[str] = []
    now = datetime.now(timezone.utc)

    # Check not yet valid
    if cert.not_valid_before_utc > now:
        errors.append(
            f"Certificate not yet valid until "
            f"{cert.not_valid_before_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

    # Check expired
    if cert.not_valid_after_utc < now:
        days_expired = (now - cert.not_valid_after_utc).days
        errors.append(
            f"Certificate expired {days_expired} days ago on "
            f"{cert.not_valid_after_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
            f"Generate new certificate: scripts/generate_cert.sh"
        )

    # Check expiration warning (< 30 days)
    warning_date = now + timedelta(days=30)
    if cert.not_valid_after_utc < warning_date and cert.not_valid_after_utc >= now:
        days_remaining = (cert.not_valid_after_utc - now).days
        warnings.append(
            f"Certificate expires in {days_remaining} days "
            f"({cert.not_valid_after_utc.strftime('%Y-%m-%d')}). "
            f"Generate new certificate soon: scripts/generate_cert.sh"
        )

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def load_pem_certificate(cert_path: Path) -> x509.Certificate:
    """Load X.509 certificate from PEM file.

    Args:
        cert_path: Path to PEM certificate file

    Returns:
        Loaded X.509 certificate

    Raises:
        CertificateLoadError: If certificate cannot be loaded

    Example:
        >>> cert = load_pem_certificate(Path("certs/test.pem"))
        >>> print(cert.subject.rfc4514_string())
    """
    if not cert_path.exists():
        raise CertificateLoadError(
            f"Certificate file not found: {cert_path}. "
            f"Ensure the file exists and path is correct."
        )

    try:
        with open(cert_path, "rb") as f:
            cert_data = f.read()
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())

        # Log certificate details (never log full certificate)
        logger.info(f"Loaded PEM certificate: {cert.subject.rfc4514_string()}")
        logger.info(
            f"Certificate expires: {cert.not_valid_after_utc.strftime('%Y-%m-%d')}"
        )

        # Check expiration warning
        check_expiration_warning(cert)

        return cert
    except Exception as e:
        raise CertificateLoadError(
            f"Failed to load PEM certificate from {cert_path}: {e}. "
            f"Ensure file is valid PEM format."
        )


def load_pem_private_key(
    key_path: Path, password: Optional[bytes] = None
) -> rsa.RSAPrivateKey:
    """Load private key from PEM file.

    Args:
        key_path: Path to PEM private key file
        password: Optional password for encrypted private key

    Returns:
        Loaded RSA private key

    Raises:
        CertificateLoadError: If private key cannot be loaded

    Example:
        >>> key = load_pem_private_key(Path("certs/test_key.pem"))
        >>> print(f"Key size: {key.key_size}")
    """
    if not key_path.exists():
        raise CertificateLoadError(
            f"Private key file not found: {key_path}. "
            f"Ensure the file exists and path is correct."
        )

    try:
        with open(key_path, "rb") as f:
            key_data = f.read()
        private_key = serialization.load_pem_private_key(
            key_data, password=password, backend=default_backend()
        )

        logger.info(f"Loaded PEM private key from: {key_path.name}")
        # CRITICAL: Never log private key contents

        return private_key  # type: ignore
    except TypeError as e:
        raise CertificateLoadError(
            f"Failed to load private key from {key_path}: Incorrect password. "
            f"If key is encrypted, provide correct password."
        )
    except Exception as e:
        raise CertificateLoadError(
            f"Failed to load PEM private key from {key_path}: {e}. "
            f"Ensure file is valid PEM format and password is correct if encrypted."
        )


def load_der_certificate(cert_path: Path) -> x509.Certificate:
    """Load X.509 certificate from DER file.

    Args:
        cert_path: Path to DER certificate file

    Returns:
        Loaded X.509 certificate

    Raises:
        CertificateLoadError: If certificate cannot be loaded

    Example:
        >>> cert = load_der_certificate(Path("certs/test.der"))
        >>> print(cert.subject.rfc4514_string())
    """
    if not cert_path.exists():
        raise CertificateLoadError(
            f"Certificate file not found: {cert_path}. "
            f"Ensure the file exists and path is correct."
        )

    try:
        with open(cert_path, "rb") as f:
            cert_data = f.read()
        cert = x509.load_der_x509_certificate(cert_data, default_backend())

        logger.info(f"Loaded DER certificate: {cert.subject.rfc4514_string()}")
        logger.info(
            f"Certificate expires: {cert.not_valid_after_utc.strftime('%Y-%m-%d')}"
        )

        # Check expiration warning
        check_expiration_warning(cert)

        return cert
    except Exception as e:
        raise CertificateLoadError(
            f"Failed to load DER certificate from {cert_path}: {e}. "
            f"Ensure file is valid DER format."
        )


def load_pkcs12_certificate(
    p12_path: Path, password: Optional[bytes] = None
) -> Tuple[x509.Certificate, rsa.RSAPrivateKey, List[x509.Certificate]]:
    """Load certificate, private key, and chain from PKCS12 file.

    Args:
        p12_path: Path to PKCS12 (.p12 or .pfx) file
        password: Password for PKCS12 file (usually required)

    Returns:
        Tuple of (certificate, private_key, certificate_chain)

    Raises:
        CertificateLoadError: If PKCS12 cannot be loaded

    Example:
        >>> cert, key, chain = load_pkcs12_certificate(
        ...     Path("certs/test.p12"),
        ...     password=b"secret"
        ... )
        >>> print(f"Chain length: {len(chain)}")
    """
    if not p12_path.exists():
        raise CertificateLoadError(
            f"PKCS12 file not found: {p12_path}. "
            f"Ensure the file exists and path is correct."
        )

    try:
        with open(p12_path, "rb") as f:
            pkcs12_data = f.read()

        # Load PKCS12
        private_key, certificate, additional_certs = (
            pkcs12.load_key_and_certificates(
                pkcs12_data, password=password, backend=default_backend()
            )
        )

        if not certificate:
            raise CertificateLoadError(
                f"No certificate found in PKCS12 file: {p12_path}"
            )

        if not private_key:
            raise CertificateLoadError(
                f"No private key found in PKCS12 file: {p12_path}"
            )

        logger.info(f"Loaded PKCS12 certificate: {certificate.subject.rfc4514_string()}")
        logger.info(
            f"Certificate expires: {certificate.not_valid_after_utc.strftime('%Y-%m-%d')}"
        )

        if additional_certs:
            logger.info(
                f"Loaded {len(additional_certs)} additional certificates from chain"
            )

        # Check expiration warning
        check_expiration_warning(certificate)

        return certificate, private_key, additional_certs or []  # type: ignore
    except TypeError as e:
        raise CertificateLoadError(
            f"Failed to load PKCS12 from {p12_path}: Incorrect password. "
            f"PKCS12 files typically require a password."
        )
    except Exception as e:
        raise CertificateLoadError(
            f"Failed to load PKCS12 from {p12_path}: {e}. "
            f"Ensure file is valid PKCS12 format and password is correct."
        )


def load_certificate(
    cert_source: Union[Path, str],
    key_path: Optional[Union[Path, str]] = None,
    password: Optional[bytes] = None,
    use_cache: bool = True,
) -> CertificateBundle:
    """Load certificate with auto-format detection and caching.

    Supports PEM (.pem), PKCS12 (.p12, .pfx), and DER (.der) formats.
    Format is detected by file extension. Also supports loading from
    environment variables.

    Args:
        cert_source: Path to certificate file or environment variable name
        key_path: Optional path to separate private key file (for PEM/DER)
        password: Optional password for PKCS12 or encrypted PEM keys
        use_cache: Whether to use certificate cache (default: True)

    Returns:
        CertificateBundle containing certificate, key, chain, and info

    Raises:
        CertificateLoadError: If certificate cannot be loaded or format unsupported

    Example:
        >>> # Load from file path
        >>> bundle = load_certificate(Path("certs/test.p12"), password=b"secret")
        >>> print(bundle.info.subject)
        
        >>> # Load from environment variable
        >>> bundle = load_certificate("IHE_TEST_CERT_PATH")
        >>> print(bundle.info.key_size)
    """
    # Resolve environment variable if string
    if isinstance(cert_source, str) and not Path(cert_source).exists():
        env_path = os.getenv(cert_source)
        if not env_path:
            raise CertificateLoadError(
                f"Environment variable {cert_source} not set. "
                f"Set the variable or provide a direct file path."
            )
        cert_path = Path(env_path)
        logger.info(f"Resolved {cert_source} to {cert_path}")
    else:
        cert_path = Path(cert_source) if isinstance(cert_source, str) else cert_source

    # Resolve key path if provided
    resolved_key_path: Optional[Path] = None
    if key_path:
        if isinstance(key_path, str) and not Path(key_path).exists():
            env_key_path = os.getenv(key_path)
            if not env_key_path:
                raise CertificateLoadError(
                    f"Environment variable {key_path} not set for private key"
                )
            resolved_key_path = Path(env_key_path)
        else:
            resolved_key_path = Path(key_path) if isinstance(key_path, str) else key_path

    # Check cache
    if use_cache:
        cached = _certificate_cache.get(cert_path)
        if cached:
            return cached

    # Auto-detect format by extension
    suffix = cert_path.suffix.lower()

    certificate: x509.Certificate
    private_key: Optional[rsa.RSAPrivateKey] = None
    chain: List[x509.Certificate] = []

    if suffix == ".pem":
        # PEM format
        certificate = load_pem_certificate(cert_path)
        if resolved_key_path:
            private_key = load_pem_private_key(resolved_key_path, password)
    elif suffix in [".p12", ".pfx"]:
        # PKCS12 format
        certificate, private_key, chain = load_pkcs12_certificate(cert_path, password)
    elif suffix == ".der":
        # DER format (certificate only)
        certificate = load_der_certificate(cert_path)
        if resolved_key_path:
            # Try loading key as PEM
            private_key = load_pem_private_key(resolved_key_path, password)
    else:
        raise CertificateLoadError(
            f"Unsupported certificate format: {suffix}. "
            f"Supported formats: .pem, .p12, .pfx, .der"
        )

    # Extract certificate info
    info = get_certificate_info(certificate)

    # Create bundle
    bundle = CertificateBundle(
        certificate=certificate,
        private_key=private_key,
        chain=chain,
        info=info,
    )

    # Cache the bundle
    if use_cache:
        _certificate_cache.put(cert_path, bundle)

    return bundle


def convert_to_pem(cert: x509.Certificate) -> bytes:
    """Convert certificate to PEM format bytes.

    Args:
        cert: X.509 certificate to convert

    Returns:
        Certificate in PEM format as bytes
    """
    return cert.public_bytes(Encoding.PEM)


def convert_key_to_pem(
    private_key: rsa.RSAPrivateKey, password: Optional[bytes] = None
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


def clear_certificate_cache() -> None:
    """Clear all cached certificates.
    
    Useful for testing or when certificates are updated on disk.
    """
    _certificate_cache.clear()
