"""Custom exception classes for IHE Test Utility.

All exceptions inherit from IHETestUtilError to allow catching all custom exceptions.
"""


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
