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
    """Raised when template processing errors occur.
    
    Examples:
        - Template file not found
        - Invalid template syntax
        - Missing template variables
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
