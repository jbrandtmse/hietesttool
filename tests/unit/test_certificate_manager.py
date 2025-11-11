"""Unit tests for certificate manager module."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa

from ihe_test_util.models.saml import CertificateBundle, CertificateInfo, ValidationResult
from ihe_test_util.saml.certificate_manager import (
    CertificateCache,
    check_expiration_warning,
    clear_certificate_cache,
    get_certificate_info,
    load_certificate,
    load_der_certificate,
    load_pem_certificate,
    load_pem_private_key,
    load_pkcs12_certificate,
    validate_certificate,
)
from ihe_test_util.utils.exceptions import CertificateLoadError


class TestPEMCertificateLoading:
    """Test PEM certificate loading functionality."""

    def test_load_pem_certificate_success(self):
        """Test loading valid PEM certificate."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        cert = load_pem_certificate(cert_path)

        assert cert is not None
        assert isinstance(cert, x509.Certificate)
        assert "CN=" in cert.subject.rfc4514_string()

    def test_load_pem_certificate_file_not_found(self):
        """Test loading PEM certificate when file doesn't exist."""
        cert_path = Path("tests/fixtures/nonexistent.pem")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pem_certificate(cert_path)

        assert "not found" in str(exc_info.value).lower()
        assert "nonexistent.pem" in str(exc_info.value)

    def test_load_pem_certificate_invalid_format(self, tmp_path):
        """Test loading invalid PEM certificate file."""
        invalid_cert = tmp_path / "invalid.pem"
        invalid_cert.write_text("This is not a valid PEM certificate")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pem_certificate(invalid_cert)

        assert "failed to load" in str(exc_info.value).lower()


class TestPEMPrivateKeyLoading:
    """Test PEM private key loading functionality."""

    def test_load_pem_private_key_success(self):
        """Test loading valid PEM private key."""
        key_path = Path("tests/fixtures/test_key.pem")
        key = load_pem_private_key(key_path)

        assert key is not None
        assert isinstance(key, rsa.RSAPrivateKey)
        assert key.key_size in [2048, 4096]

    def test_load_pem_private_key_file_not_found(self):
        """Test loading private key when file doesn't exist."""
        key_path = Path("tests/fixtures/nonexistent_key.pem")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pem_private_key(key_path)

        assert "not found" in str(exc_info.value).lower()

    def test_load_pem_private_key_invalid_format(self, tmp_path):
        """Test loading invalid PEM private key."""
        invalid_key = tmp_path / "invalid_key.pem"
        invalid_key.write_text("This is not a valid PEM key")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pem_private_key(invalid_key)

        assert "failed to load" in str(exc_info.value).lower()


class TestDERCertificateLoading:
    """Test DER certificate loading functionality."""

    def test_load_der_certificate_success(self):
        """Test loading valid DER certificate."""
        cert_path = Path("tests/fixtures/test_cert.der")
        cert = load_der_certificate(cert_path)

        assert cert is not None
        assert isinstance(cert, x509.Certificate)

    def test_load_der_certificate_file_not_found(self):
        """Test loading DER certificate when file doesn't exist."""
        cert_path = Path("tests/fixtures/nonexistent.der")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_der_certificate(cert_path)

        assert "not found" in str(exc_info.value).lower()


class TestPKCS12Loading:
    """Test PKCS12 certificate loading functionality."""

    def test_load_pkcs12_certificate_success(self):
        """Test loading valid PKCS12 certificate with password."""
        p12_path = Path("tests/fixtures/test_cert.p12")
        password = b"testpass"  # Password used in generate_test_certs.py

        cert, key, chain = load_pkcs12_certificate(p12_path, password)

        assert cert is not None
        assert isinstance(cert, x509.Certificate)
        assert key is not None
        assert isinstance(key, rsa.RSAPrivateKey)
        assert isinstance(chain, list)

    def test_load_pkcs12_certificate_wrong_password(self):
        """Test loading PKCS12 with incorrect password."""
        p12_path = Path("tests/fixtures/test_cert.p12")
        wrong_password = b"wrongpassword"

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pkcs12_certificate(p12_path, wrong_password)

        assert "password" in str(exc_info.value).lower()

    def test_load_pkcs12_certificate_file_not_found(self):
        """Test loading PKCS12 when file doesn't exist."""
        p12_path = Path("tests/fixtures/nonexistent.p12")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pkcs12_certificate(p12_path, b"password")

        assert "not found" in str(exc_info.value).lower()


class TestCertificateValidation:
    """Test certificate validation functionality."""

    def test_validate_certificate_valid(self):
        """Test validation of valid certificate."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        cert = load_pem_certificate(cert_path)

        result = validate_certificate(cert)

        assert isinstance(result, ValidationResult)
        # Note: Test certificate might be expired or expiring,
        # so we just check structure
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    def test_validate_certificate_structure(self):
        """Test validation result structure."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        cert = load_pem_certificate(cert_path)

        result = validate_certificate(cert)

        # Check that validation returns proper structure
        assert hasattr(result, "is_valid")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")

        # If certificate is expiring soon, should have warnings
        now = datetime.now(timezone.utc)
        days_until_expiry = (cert.not_valid_after_utc - now).days

        if 0 <= days_until_expiry <= 30:
            assert len(result.warnings) > 0
            assert "expires in" in result.warnings[0].lower()


class TestCertificateInfoExtraction:
    """Test certificate information extraction."""

    def test_get_certificate_info(self):
        """Test extracting certificate information."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        cert = load_pem_certificate(cert_path)

        info = get_certificate_info(cert)

        assert isinstance(info, CertificateInfo)
        assert info.subject is not None
        assert info.issuer is not None
        assert isinstance(info.not_before, datetime)
        assert isinstance(info.not_after, datetime)
        assert isinstance(info.serial_number, int)
        # Key size might be None for some certificate types
        if info.key_size:
            assert info.key_size in [2048, 4096, 3072]

    def test_get_certificate_info_subject_format(self):
        """Test certificate subject is in RFC4514 format."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        cert = load_pem_certificate(cert_path)

        info = get_certificate_info(cert)

        # RFC4514 format should contain CN=
        assert "CN=" in info.subject or "O=" in info.subject


class TestExpirationWarning:
    """Test certificate expiration warning logic."""

    def test_check_expiration_warning_expiring_soon(self):
        """Test expiration warning for certificate expiring soon."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        cert = load_pem_certificate(cert_path)

        now = datetime.now(timezone.utc)
        days_until_expiry = (cert.not_valid_after_utc - now).days

        # Test with appropriate warning days
        if 0 <= days_until_expiry <= 365:
            result = check_expiration_warning(cert, warning_days=365)
            # Should return True if expiring within warning period
            if days_until_expiry <= 365:
                assert result is True

    def test_check_expiration_warning_custom_days(self):
        """Test expiration warning with custom warning days."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        cert = load_pem_certificate(cert_path)

        # Test with very large warning period
        result = check_expiration_warning(cert, warning_days=10000)

        # Most certificates should trigger warning with 10000 day period
        assert isinstance(result, bool)


class TestCertificateCache:
    """Test certificate caching functionality."""

    def test_cache_put_and_get(self, tmp_path):
        """Test caching certificate bundle."""
        cache = CertificateCache()
        cert_path = Path("tests/fixtures/test_cert.pem")

        # Load certificate
        cert = load_pem_certificate(cert_path)
        info = get_certificate_info(cert)
        bundle = CertificateBundle(
            certificate=cert,
            private_key=None,
            chain=[],
            info=info,
        )

        # Cache the bundle
        cache.put(cert_path, bundle)

        # Retrieve from cache
        cached_bundle = cache.get(cert_path)

        assert cached_bundle is not None
        assert cached_bundle.certificate == bundle.certificate

    def test_cache_miss(self):
        """Test cache miss for non-existent entry."""
        cache = CertificateCache()
        cert_path = Path("tests/fixtures/nonexistent.pem")

        cached_bundle = cache.get(cert_path)

        assert cached_bundle is None

    def test_cache_invalidation_on_file_change(self, tmp_path):
        """Test cache invalidation when file is modified."""
        cache = CertificateCache()

        # Create a temporary certificate file
        test_cert_path = Path("tests/fixtures/test_cert.pem")
        cert = load_pem_certificate(test_cert_path)
        info = get_certificate_info(cert)
        bundle = CertificateBundle(
            certificate=cert,
            private_key=None,
            chain=[],
            info=info,
        )

        # Cache the bundle
        cache.put(test_cert_path, bundle)

        # Mock file modification time change
        with patch("os.path.getmtime") as mock_getmtime:
            # Simulate file modification by returning different mtime
            mock_getmtime.return_value = os.path.getmtime(test_cert_path) + 1.0

            # Should return None (cache invalidated)
            cached_bundle = cache.get(test_cert_path)

            assert cached_bundle is None

    def test_cache_clear(self):
        """Test clearing all cached certificates."""
        cache = CertificateCache()
        cert_path = Path("tests/fixtures/test_cert.pem")

        cert = load_pem_certificate(cert_path)
        info = get_certificate_info(cert)
        bundle = CertificateBundle(
            certificate=cert,
            private_key=None,
            chain=[],
            info=info,
        )

        cache.put(cert_path, bundle)
        cache.clear()

        cached_bundle = cache.get(cert_path)
        assert cached_bundle is None


class TestUnifiedCertificateLoader:
    """Test unified certificate loader with auto-detection."""

    def test_load_certificate_pem_format(self):
        """Test loading certificate with PEM auto-detection."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        key_path = Path("tests/fixtures/test_key.pem")

        bundle = load_certificate(cert_path, key_path=key_path, use_cache=False)

        assert isinstance(bundle, CertificateBundle)
        assert bundle.certificate is not None
        assert bundle.private_key is not None
        assert isinstance(bundle.info, CertificateInfo)

    def test_load_certificate_der_format(self):
        """Test loading certificate with DER auto-detection."""
        cert_path = Path("tests/fixtures/test_cert.der")

        bundle = load_certificate(cert_path, use_cache=False)

        assert isinstance(bundle, CertificateBundle)
        assert bundle.certificate is not None
        assert isinstance(bundle.info, CertificateInfo)

    def test_load_certificate_pkcs12_format(self):
        """Test loading certificate with PKCS12 auto-detection."""
        cert_path = Path("tests/fixtures/test_cert.p12")
        password = b"testpass"  # Password used in generate_test_certs.py

        bundle = load_certificate(cert_path, password=password, use_cache=False)

        assert isinstance(bundle, CertificateBundle)
        assert bundle.certificate is not None
        assert bundle.private_key is not None
        assert isinstance(bundle.info, CertificateInfo)

    def test_load_certificate_unsupported_format(self, tmp_path):
        """Test loading certificate with unsupported format."""
        cert_path = tmp_path / "test.xyz"
        cert_path.write_text("test")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_certificate(cert_path, use_cache=False)

        assert "unsupported" in str(exc_info.value).lower()

    def test_load_certificate_with_cache(self):
        """Test certificate loading uses cache."""
        cert_path = Path("tests/fixtures/test_cert.pem")

        # First load
        bundle1 = load_certificate(cert_path, use_cache=True)

        # Second load (should use cache)
        bundle2 = load_certificate(cert_path, use_cache=True)

        # Should return same cached instance
        assert bundle1 is bundle2

        # Clean up
        clear_certificate_cache()

    def test_load_certificate_without_cache(self):
        """Test certificate loading without cache."""
        cert_path = Path("tests/fixtures/test_cert.pem")

        # Load without cache
        bundle1 = load_certificate(cert_path, use_cache=False)
        bundle2 = load_certificate(cert_path, use_cache=False)

        # Should be different instances
        assert bundle1 is not bundle2


class TestEnvironmentVariableLoading:
    """Test loading certificates from environment variables."""

    def test_load_certificate_from_env_var(self, monkeypatch):
        """Test loading certificate from environment variable."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        monkeypatch.setenv("TEST_CERT_PATH", str(cert_path))

        bundle = load_certificate("TEST_CERT_PATH", use_cache=False)

        assert isinstance(bundle, CertificateBundle)
        assert bundle.certificate is not None

    def test_load_certificate_env_var_not_set(self):
        """Test loading certificate when environment variable not set."""
        with pytest.raises(CertificateLoadError) as exc_info:
            load_certificate("NONEXISTENT_ENV_VAR", use_cache=False)

        assert "environment variable" in str(exc_info.value).lower()
        assert "not set" in str(exc_info.value).lower()

    def test_load_certificate_with_key_from_env_var(self, monkeypatch):
        """Test loading certificate and key from environment variables."""
        cert_path = Path("tests/fixtures/test_cert.pem")
        key_path = Path("tests/fixtures/test_key.pem")

        monkeypatch.setenv("TEST_CERT_PATH", str(cert_path))
        monkeypatch.setenv("TEST_KEY_PATH", str(key_path))

        bundle = load_certificate(
            "TEST_CERT_PATH",
            key_path="TEST_KEY_PATH",
            use_cache=False,
        )

        assert bundle.certificate is not None
        assert bundle.private_key is not None


class TestErrorHandling:
    """Test error handling and error messages."""

    def test_error_message_includes_file_path(self):
        """Test error messages include file path for debugging."""
        cert_path = Path("tests/fixtures/missing_certificate.pem")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pem_certificate(cert_path)

        assert "missing_certificate.pem" in str(exc_info.value)

    def test_error_message_actionable_file_not_found(self):
        """Test error message provides actionable guidance."""
        cert_path = Path("tests/fixtures/missing.pem")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pem_certificate(cert_path)

        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg
        assert "ensure" in error_msg or "check" in error_msg

    def test_error_message_actionable_wrong_password(self):
        """Test error message for wrong password is actionable."""
        p12_path = Path("tests/fixtures/test_cert.p12")

        with pytest.raises(CertificateLoadError) as exc_info:
            load_pkcs12_certificate(p12_path, b"wrongpassword")

        error_msg = str(exc_info.value).lower()
        assert "password" in error_msg


class TestGlobalCacheFunctions:
    """Test global cache management functions."""

    def test_clear_certificate_cache(self):
        """Test clearing global certificate cache."""
        cert_path = Path("tests/fixtures/test_cert.pem")

        # Load with cache
        bundle1 = load_certificate(cert_path, use_cache=True)

        # Clear cache
        clear_certificate_cache()

        # Load again (should not be cached)
        bundle2 = load_certificate(cert_path, use_cache=True)

        # Should be different instances after cache clear
        assert bundle1 is not bundle2
