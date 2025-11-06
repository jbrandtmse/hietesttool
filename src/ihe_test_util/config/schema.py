"""Configuration schema models using pydantic.

This module defines the configuration structure and validation rules using pydantic.
All configuration values are validated according to the schema defined here.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EndpointsConfig(BaseModel):
    """Configuration for IHE endpoint URLs.
    
    Attributes:
        pix_add_url: PIX Add endpoint URL (ITI-8 transaction)
        iti41_url: ITI-41 Provide and Register Document Set-b endpoint URL
    """
    
    pix_add_url: str = Field(..., description="PIX Add endpoint URL")
    iti41_url: str = Field(..., description="ITI-41 endpoint URL")
    
    @field_validator("pix_add_url", "iti41_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL is valid HTTP/HTTPS.
        
        Args:
            v: URL string to validate
            
        Returns:
            Validated URL string
            
        Raises:
            ValueError: If URL does not start with http:// or https://
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                f"Invalid URL: {v}. Must start with http:// or https://"
            )
        return v


class CertificatesConfig(BaseModel):
    """Configuration for certificate and key paths.
    
    Attributes:
        cert_path: Path to certificate file
        key_path: Path to private key file
        cert_format: Certificate format (pem, pkcs12, or der)
        pkcs12_password_env_var: Environment variable name for PKCS12 password
    """
    
    cert_path: Optional[Path] = None
    key_path: Optional[Path] = None
    cert_format: str = Field(
        default="pem",
        description="Certificate format: pem, pkcs12, or der"
    )
    pkcs12_password_env_var: Optional[str] = Field(
        default="IHE_TEST_PKCS12_PASSWORD",
        description="Environment variable for PKCS12 password"
    )
    
    @field_validator("cert_format")
    @classmethod
    def validate_cert_format(cls, v: str) -> str:
        """Validate certificate format.
        
        Args:
            v: Certificate format string
            
        Returns:
            Validated format string
            
        Raises:
            ValueError: If format is not one of: pem, pkcs12, der
        """
        valid_formats = ["pem", "pkcs12", "der"]
        if v not in valid_formats:
            raise ValueError(
                f"Invalid cert_format: {v}. Must be one of: {', '.join(valid_formats)}"
            )
        return v


class TransportConfig(BaseModel):
    """Configuration for HTTP/HTTPS transport.
    
    Attributes:
        verify_tls: Whether to verify TLS certificates
        timeout_connect: Connection timeout in seconds
        timeout_read: Read timeout in seconds
        max_retries: Maximum retry attempts for failed requests
        backoff_factor: Exponential backoff factor for retries
    """
    
    verify_tls: bool = True
    timeout_connect: int = Field(
        default=10,
        ge=1,
        description="Connection timeout in seconds"
    )
    timeout_read: int = Field(
        default=30,
        ge=1,
        description="Read timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts"
    )
    backoff_factor: float = Field(
        default=1.0,
        ge=0.0,
        description="Exponential backoff factor"
    )


class LoggingConfig(BaseModel):
    """Configuration for logging.
    
    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        redact_pii: Whether to redact PII from logs
    """
    
    level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    log_file: Path = Field(
        default=Path("logs/ihe-test-util.log"),
        description="Log file path"
    )
    redact_pii: bool = Field(
        default=False,
        description="Redact PII from logs"
    )
    
    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level.
        
        Args:
            v: Log level string
            
        Returns:
            Validated log level (uppercase)
            
        Raises:
            ValueError: If log level is not valid
        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level: {v}. Must be one of: {', '.join(valid_levels)}"
            )
        return v_upper


class Config(BaseModel):
    """Root configuration model.
    
    This is the main configuration class that contains all configuration sections.
    
    Attributes:
        endpoints: IHE endpoint URLs configuration
        certificates: Certificate and key paths configuration
        transport: HTTP/HTTPS transport configuration
        logging: Logging configuration
        
    Example:
        >>> config = Config(
        ...     endpoints=EndpointsConfig(
        ...         pix_add_url="http://localhost:8080/pix/add",
        ...         iti41_url="http://localhost:8080/iti41/submit"
        ...     )
        ... )
        >>> config.endpoints.pix_add_url
        'http://localhost:8080/pix/add'
    """
    
    endpoints: EndpointsConfig
    certificates: CertificatesConfig = CertificatesConfig()
    transport: TransportConfig = TransportConfig()
    logging: LoggingConfig = LoggingConfig()
