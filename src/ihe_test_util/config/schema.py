"""Configuration schema models using pydantic.

This module defines the configuration structure and validation rules using pydantic.
All configuration values are validated according to the schema defined here.

Extended for Story 6.6 with batch processing, template configuration, and
per-operation logging support.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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


class OperationLoggingConfig(BaseModel):
    """Per-operation logging configuration (AC: 6).
    
    Allows different log levels for different operation types to enable
    focused debugging without excessive log noise.
    
    Attributes:
        csv_log_level: Log level for CSV parsing operations
        pix_add_log_level: Log level for PIX Add transactions
        iti41_log_level: Log level for ITI-41 transactions
        saml_log_level: Log level for SAML generation/signing
        
    Example:
        >>> op_logging = OperationLoggingConfig(
        ...     csv_log_level="DEBUG",
        ...     pix_add_log_level="INFO",
        ...     iti41_log_level="WARNING"
        ... )
    """
    
    csv_log_level: str = Field(
        default="INFO",
        description="Log level for CSV parsing operations"
    )
    pix_add_log_level: str = Field(
        default="INFO",
        description="Log level for PIX Add transactions"
    )
    iti41_log_level: str = Field(
        default="INFO",
        description="Log level for ITI-41 transactions"
    )
    saml_log_level: str = Field(
        default="WARNING",
        description="Log level for SAML generation/signing"
    )
    
    @field_validator("csv_log_level", "pix_add_log_level", "iti41_log_level", "saml_log_level")
    @classmethod
    def validate_operation_log_level(cls, v: str) -> str:
        """Validate operation-specific log level.
        
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


class BatchConfig(BaseModel):
    """Batch processing configuration (AC: 1, 4, 5).
    
    Configuration for batch processing workflows including checkpoint/resume,
    connection pooling, and fail-fast behavior.
    
    Attributes:
        batch_size: Maximum patients per batch (for partitioning large CSVs)
        checkpoint_interval: Save checkpoint every N patients
        checkpoint_file: Path to checkpoint file for resume capability
        resume_enabled: Whether to enable resume from checkpoint
        fail_fast: Stop processing on first error
        concurrent_connections: Maximum concurrent HTTP connections
        output_dir: Base output directory for batch results
        
    Example:
        >>> batch_config = BatchConfig(
        ...     batch_size=100,
        ...     checkpoint_interval=50,
        ...     fail_fast=False,
        ...     concurrent_connections=10
        ... )
    """
    
    batch_size: int = Field(
        default=100,
        ge=1,
        description="Maximum patients per batch"
    )
    checkpoint_interval: int = Field(
        default=50,
        ge=1,
        description="Save checkpoint every N patients"
    )
    checkpoint_file: Optional[Path] = Field(
        default=None,
        description="Path to checkpoint file for resume"
    )
    resume_enabled: bool = Field(
        default=True,
        description="Enable resume from checkpoint"
    )
    fail_fast: bool = Field(
        default=False,
        description="Stop processing on first error"
    )
    concurrent_connections: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum concurrent HTTP connections (NFR3: 10+)"
    )
    output_dir: Path = Field(
        default=Path("output"),
        description="Base output directory for batch results"
    )
    
    @model_validator(mode="after")
    def validate_checkpoint_interval(self) -> "BatchConfig":
        """Validate checkpoint interval is not greater than batch size.
        
        Returns:
            Validated BatchConfig instance
            
        Raises:
            ValueError: If checkpoint_interval > batch_size
        """
        if self.checkpoint_interval > self.batch_size:
            raise ValueError(
                f"checkpoint_interval ({self.checkpoint_interval}) cannot be greater "
                f"than batch_size ({self.batch_size}). "
                f"Fix: Set checkpoint_interval <= batch_size."
            )
        return self


class TemplateConfig(BaseModel):
    """Template paths configuration (AC: 2).
    
    Configuration for CCD and SAML template file paths.
    
    Attributes:
        ccd_template_path: Path to CCD template XML file
        saml_template_path: Path to SAML template XML file
        
    Example:
        >>> template_config = TemplateConfig(
        ...     ccd_template_path=Path("templates/ccd-template.xml"),
        ...     saml_template_path=Path("templates/saml-template.xml")
        ... )
    """
    
    ccd_template_path: Optional[Path] = Field(
        default=None,
        description="Path to CCD template XML file"
    )
    saml_template_path: Optional[Path] = Field(
        default=None,
        description="Path to SAML template XML file"
    )


class Config(BaseModel):
    """Root configuration model.
    
    This is the main configuration class that contains all configuration sections.
    Extended in Story 6.6 with batch processing, templates, and operation logging.
    
    Attributes:
        endpoints: IHE endpoint URLs configuration
        certificates: Certificate and key paths configuration
        transport: HTTP/HTTPS transport configuration
        logging: Logging configuration
        batch: Batch processing configuration (Story 6.6)
        templates: Template paths configuration (Story 6.6)
        operation_logging: Per-operation logging configuration (Story 6.6)
        sender_oid: Sender facility OID
        receiver_oid: Receiver facility OID
        sender_application: Sender application identifier
        receiver_application: Receiver application identifier
        
    Example:
        >>> config = Config(
        ...     endpoints=EndpointsConfig(
        ...         pix_add_url="http://localhost:8080/pix/add",
        ...         iti41_url="http://localhost:8080/iti41/submit"
        ...     ),
        ...     batch=BatchConfig(checkpoint_interval=50),
        ...     templates=TemplateConfig(ccd_template_path=Path("templates/ccd.xml"))
        ... )
        >>> config.endpoints.pix_add_url
        'http://localhost:8080/pix/add'
        >>> config.batch.checkpoint_interval
        50
    """
    
    endpoints: EndpointsConfig
    certificates: CertificatesConfig = CertificatesConfig()
    transport: TransportConfig = TransportConfig()
    logging: LoggingConfig = LoggingConfig()
    
    # Story 6.6: Batch processing configuration
    batch: BatchConfig = BatchConfig()
    templates: TemplateConfig = TemplateConfig()
    operation_logging: OperationLoggingConfig = OperationLoggingConfig()
    
    # OID configuration
    sender_oid: str = Field(default="1.2.3.4.5", description="Sender facility OID")
    receiver_oid: str = Field(default="1.2.3.4.6", description="Receiver facility OID")
    sender_application: str = Field(default="TEST_APP", description="Sender application identifier")
    receiver_application: str = Field(default="RECEIVER_APP", description="Receiver application identifier")
