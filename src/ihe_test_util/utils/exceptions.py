"""Custom exception classes for IHE Test Utility.

All exceptions inherit from IHETestUtilError to allow catching all custom exceptions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests


class IHETestUtilError(Exception):
    """Base exception for all IHE Test Utility custom exceptions."""

    pass


class ValidationError(IHETestUtilError):
    """Raised when data validation fails.
    
    Examples:
        - Invalid patient demographics
        - Malformed XML
        - Invalid configuration values
    """

    pass


class TransportError(IHETestUtilError):
    """Raised when network/transport issues occur.
    
    Examples:
        - Connection timeout
        - HTTP error responses
        - Network unreachable
    """

    pass


class ConfigurationError(IHETestUtilError):
    """Raised when configuration loading or validation fails.
    
    Examples:
        - Missing required configuration
        - Invalid configuration file format
        - Configuration value out of range
    """

    pass


class TemplateError(IHETestUtilError):
    """Base exception for template processing errors.
    
    Examples:
        - Template file not found
        - Invalid template syntax
        - Missing template variables
    """

    pass


class TemplateLoadError(TemplateError):
    """Raised when template file cannot be loaded.
    
    Examples:
        - File not found
        - Permission denied
        - Encoding errors
    """

    pass


class MalformedXMLError(TemplateError):
    """Raised when XML is not well-formed.
    
    Examples:
        - Unclosed tags
        - Invalid characters
        - Syntax errors
    """

    pass


class MissingPlaceholderError(TemplateError):
    """Raised when required placeholders are missing from template.
    
    Examples:
        - Missing patient_id placeholder
        - Missing required CCD fields
    """

    pass


class TemplateValidationError(TemplateError):
    """General template validation error.
    
    Examples:
        - Invalid placeholder syntax
        - Template structure validation failure
    """

    pass


class MissingPlaceholderValueError(TemplateError):
    """Raised when required placeholder value is missing during personalization.
    
    Examples:
        - Required patient_id value not provided
        - Missing required CCD field values
    """

    pass


class MaxNestingDepthError(TemplateError):
    """Raised when nested placeholders exceed maximum depth.
    
    Examples:
        - Recursive placeholder nesting too deep
        - Circular placeholder references
    """

    pass


class InvalidOIDFormatError(TemplateError):
    """Raised when OID format is invalid (strict mode only).
    
    Examples:
        - OID with invalid characters
        - OID with incorrect format
    """

    pass


class CCDPersonalizationError(TemplateError):
    """Raised when CCD personalization fails.
    
    Examples:
        - Failed to personalize template with patient data
        - Post-personalization validation failure
        - Missing required patient fields
    """

    pass


class SAMLError(IHETestUtilError):
    """Raised when SAML generation or signing errors occur.
    
    Examples:
        - Certificate loading failure
        - Signing failure
        - Invalid SAML assertion structure
    """

    pass


class CertificateLoadError(SAMLError):
    """Raised when certificate loading fails.
    
    Examples:
        - Certificate file not found
        - Invalid certificate format
        - Incorrect password for encrypted key
        - Corrupted certificate file
    """

    pass


class CertificateValidationError(SAMLError):
    """Raised when certificate validation fails.
    
    Examples:
        - Certificate expired
        - Certificate not yet valid
        - Invalid key usage
        - Certificate chain validation failure
    """

    pass


class CertificateExpiredError(CertificateValidationError):
    """Raised when certificate has expired.
    
    This is a specific case of validation failure for expired certificates.
    """

    pass


class HL7v3Error(IHETestUtilError):
    """Raised when HL7v3 message construction or parsing fails.
    
    Examples:
        - Invalid message structure
        - Missing required elements
        - Parsing failure
    """

    pass


class IHETransactionError(IHETestUtilError):
    """Raised when IHE transaction processing fails.
    
    Examples:
        - PIX Add transaction failure
        - ITI-41 submission failure
        - Invalid transaction response
    """

    pass


class ErrorCategory(Enum):
    """Error categorization for handling strategy.
    
    Determines how errors should be handled in batch processing workflows.
    
    Attributes:
        TRANSIENT: Retry with exponential backoff (network issues, timeouts, 5xx)
        PERMANENT: Skip patient, continue batch (validation errors, 4xx, HL7 AE/AR)
        CRITICAL: Halt processing immediately (cert errors, endpoint unreachable)
        
    Example:
        >>> category = categorize_error(ConnectionError("Network unreachable"))
        >>> if category == ErrorCategory.CRITICAL:
        ...     raise  # halt workflow
    """
    
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    CRITICAL = "CRITICAL"


@dataclass
class ErrorInfo:
    """Structured error information for actionable error handling.
    
    Attributes:
        category: Error category (TRANSIENT, PERMANENT, CRITICAL)
        error_type: Exception class name (e.g., "ConnectionError")
        message: User-friendly error message
        remediation: Actionable guidance for resolving the error
        is_retryable: Whether the error should trigger retry logic
        technical_details: Optional technical details for debugging
        patient_id: Optional patient ID if error occurred during patient processing
        raw_response: Optional raw response content for malformed responses
        
    Example:
        >>> error_info = ErrorInfo(
        ...     category=ErrorCategory.TRANSIENT,
        ...     error_type="ConnectionError",
        ...     message="Cannot reach PIX Add endpoint",
        ...     remediation="Check network connectivity and endpoint URL",
        ...     is_retryable=True
        ... )
    """
    
    category: ErrorCategory
    error_type: str
    message: str
    remediation: str
    is_retryable: bool
    technical_details: Optional[str] = None
    patient_id: Optional[str] = None
    raw_response: Optional[str] = None


def categorize_error(exception: Exception) -> ErrorCategory:
    """Categorize exception for error handling strategy.
    
    Determines whether an error should trigger retry (TRANSIENT),
    be skipped (PERMANENT), or halt processing (CRITICAL).
    
    Args:
        exception: The exception to categorize
        
    Returns:
        ErrorCategory indicating handling strategy
        
    Example:
        >>> categorize_error(ConnectionError("Network unreachable"))
        ErrorCategory.TRANSIENT
        >>> categorize_error(ValidationError("Invalid data"))
        ErrorCategory.PERMANENT
        >>> categorize_error(CertificateExpiredError("Cert expired"))
        ErrorCategory.CRITICAL
    """
    # CRITICAL errors - halt workflow immediately
    if isinstance(exception, (CertificateExpiredError, CertificateValidationError, CertificateLoadError)):
        return ErrorCategory.CRITICAL
    
    if isinstance(exception, ConfigurationError):
        return ErrorCategory.CRITICAL
    
    if isinstance(exception, requests.exceptions.SSLError):
        return ErrorCategory.CRITICAL
    
    # Check for connection errors - these are CRITICAL (endpoint unreachable)
    if isinstance(exception, requests.ConnectionError):
        return ErrorCategory.CRITICAL
    
    # TRANSIENT errors - retry with backoff
    if isinstance(exception, (requests.Timeout, TransportError)):
        return ErrorCategory.TRANSIENT
    
    # HTTP 5xx errors are transient (server errors)
    if isinstance(exception, requests.HTTPError):
        if hasattr(exception, 'response') and exception.response is not None:
            if 500 <= exception.response.status_code < 600:
                return ErrorCategory.TRANSIENT
            # 4xx errors are permanent (client errors)
            if 400 <= exception.response.status_code < 500:
                return ErrorCategory.PERMANENT
    
    # PERMANENT errors - skip, do not retry
    if isinstance(exception, (ValidationError, HL7v3Error)):
        return ErrorCategory.PERMANENT
    
    # Default to PERMANENT for unknown errors
    return ErrorCategory.PERMANENT


def create_error_info(
    exception: Exception,
    patient_id: Optional[str] = None,
    raw_response: Optional[str] = None
) -> ErrorInfo:
    """Create structured error information from exception.
    
    Args:
        exception: Exception that occurred
        patient_id: Optional patient ID if error during patient processing
        raw_response: Optional raw response if error parsing response
        
    Returns:
        ErrorInfo with categorization and remediation guidance
        
    Example:
        >>> error_info = create_error_info(
        ...     ConnectionError("Network unreachable"),
        ...     patient_id="PAT123"
        ... )
        >>> print(error_info.remediation)
    """
    category = categorize_error(exception)
    error_type = type(exception).__name__
    message = str(exception)
    is_retryable = category == ErrorCategory.TRANSIENT
    
    # Generate remediation message
    remediation = _generate_remediation(exception, category)
    
    # Extract technical details
    technical_details = None
    if hasattr(exception, '__cause__') and exception.__cause__:
        technical_details = f"Caused by: {type(exception.__cause__).__name__}: {exception.__cause__}"
    
    return ErrorInfo(
        category=category,
        error_type=error_type,
        message=message,
        remediation=remediation,
        is_retryable=is_retryable,
        technical_details=technical_details,
        patient_id=patient_id,
        raw_response=raw_response
    )


def _generate_remediation(exception: Exception, category: ErrorCategory) -> str:
    """Generate actionable remediation message for an error.
    
    Args:
        exception: Exception that occurred
        category: Error category
        
    Returns:
        Actionable remediation message
    """
    error_str = str(exception).lower()
    
    # Certificate errors
    if isinstance(exception, CertificateExpiredError):
        return (
            "Certificate has expired. Generate new certificate with: scripts/generate_cert.sh. "
            "Update config.json with new certificate path."
        )
    
    if isinstance(exception, (CertificateValidationError, CertificateLoadError)):
        return (
            "Certificate validation or loading failed. Check certificate file format and path. "
            "For development with self-signed certs, set verify_tls=false in config.json. "
            "For production, use valid certificate: scripts/generate_cert.sh"
        )
    
    # SSL/TLS errors
    if isinstance(exception, requests.exceptions.SSLError):
        return (
            "TLS/SSL validation failed. If using self-signed certificates, "
            "set verify_tls=false in config.json (development only). "
            "For production, ensure valid certificate chain."
        )
    
    # Connection errors
    if isinstance(exception, requests.ConnectionError):
        return (
            "Cannot reach endpoint. Check: 1) Network connectivity (ping/curl), "
            "2) Endpoint URL in config.json, 3) Firewall rules, 4) Endpoint is running."
        )
    
    # Timeout errors
    if isinstance(exception, requests.Timeout):
        return (
            "Request timed out. Consider: 1) Increasing timeout in config.json, "
            "2) Checking endpoint performance, 3) Verifying network latency."
        )
    
    # Validation errors
    if isinstance(exception, ValidationError):
        return (
            "Data validation failed. Review patient data in CSV file. "
            "Check examples/patients_sample.csv for correct format."
        )
    
    # Configuration errors
    if isinstance(exception, ConfigurationError):
        return (
            "Configuration error. Check config.json for missing or invalid values. "
            "Use examples/config.example.json as template."
        )
    
    # HL7v3 errors
    if isinstance(exception, HL7v3Error):
        return (
            "HL7v3 message error. Check message structure and required elements. "
            "Review IHE specifications for PIX Add (ITI-44) requirements."
        )
    
    # Generic remediation
    return (
        "Review error message and check logs/transactions/ for complete details. "
        "Consult documentation in docs/ for troubleshooting guidance."
    )
