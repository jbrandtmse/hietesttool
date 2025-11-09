"""Configuration management for mock server."""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ValidationMode(str, Enum):
    """Validation mode for mock endpoints."""

    STRICT = "strict"
    LENIENT = "lenient"


class PIXAddBehavior(BaseModel):
    """PIX Add endpoint behavior configuration.
    
    Attributes:
        response_delay_ms: Response delay in milliseconds (0-5000)
        failure_rate: Probability of returning SOAP fault (0.0-1.0)
        custom_patient_id: Custom patient ID for acknowledgment
        custom_fault_message: Custom SOAP fault message on failure
        validation_mode: Validation strictness (strict or lenient)
    """

    response_delay_ms: int = Field(
        default=0,
        ge=0,
        le=5000,
        description="Response delay in milliseconds",
    )
    failure_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Probability of returning SOAP fault (0.0-1.0)",
    )
    custom_patient_id: Optional[str] = Field(
        default=None,
        description="Custom patient ID for acknowledgment",
    )
    custom_fault_message: Optional[str] = Field(
        default=None,
        description="Custom SOAP fault message on failure",
    )
    validation_mode: ValidationMode = Field(
        default=ValidationMode.LENIENT,
        description="Validation strictness",
    )


class ITI41Behavior(BaseModel):
    """ITI-41 endpoint behavior configuration.
    
    Attributes:
        response_delay_ms: Response delay in milliseconds (0-5000)
        failure_rate: Probability of returning SOAP fault (0.0-1.0)
        custom_submission_set_id: Custom submission set unique ID
        custom_document_id: Custom document unique ID
        custom_fault_message: Custom SOAP fault message on failure
        validation_mode: Validation strictness (strict or lenient)
    """

    response_delay_ms: int = Field(
        default=0,
        ge=0,
        le=5000,
        description="Response delay in milliseconds",
    )
    failure_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Probability of returning SOAP fault (0.0-1.0)",
    )
    custom_submission_set_id: Optional[str] = Field(
        default=None,
        description="Custom submission set unique ID",
    )
    custom_document_id: Optional[str] = Field(
        default=None,
        description="Custom document unique ID",
    )
    custom_fault_message: Optional[str] = Field(
        default=None,
        description="Custom SOAP fault message on failure",
    )
    validation_mode: ValidationMode = Field(
        default=ValidationMode.LENIENT,
        description="Validation strictness",
    )


class MockServerConfig(BaseModel):
    """Mock server configuration model.
    
    Configuration precedence:
    1. Environment variables (MOCK_SERVER_* prefix)
    2. JSON config file
    3. Default values
    """

    host: str = Field(default="0.0.0.0", description="Server host address")
    http_port: int = Field(default=8080, description="HTTP server port")
    https_port: int = Field(default=8443, description="HTTPS server port")
    cert_path: str = Field(default="mocks/cert.pem", description="SSL certificate path")
    key_path: str = Field(default="mocks/key.pem", description="SSL key path")
    log_level: str = Field(default="INFO", description="Logging level")
    log_path: str = Field(default="mocks/logs/mock-server.log", description="Log file path")
    pix_add_endpoint: str = Field(default="/pix/add", description="PIX Add endpoint path")
    iti41_endpoint: str = Field(default="/iti41/submit", description="ITI-41 endpoint path")
    response_delay_ms: int = Field(
        default=0,
        ge=0,
        le=5000,
        description="DEPRECATED: Global response delay. Use per-endpoint behavior configuration instead.",
    )
    save_submitted_documents: bool = Field(default=False, description="Save submitted CCD documents to disk")

    # Per-endpoint behavior configuration
    pix_add_behavior: PIXAddBehavior = Field(
        default_factory=PIXAddBehavior,
        description="PIX Add endpoint behavior configuration",
    )
    iti41_behavior: ITI41Behavior = Field(
        default_factory=ITI41Behavior,
        description="ITI-41 endpoint behavior configuration",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(valid_levels)}"
            )
        return v_upper

    @field_validator("http_port", "https_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port number is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Invalid port {v}. Must be between 1 and 65535.")
        return v


def load_config(config_file: Path | None = None) -> MockServerConfig:
    """Load mock server configuration from file and environment variables.
    
    Args:
        config_file: Path to configuration JSON file. Defaults to mocks/config.json
        
    Returns:
        MockServerConfig instance with merged configuration
        
    Raises:
        FileNotFoundError: If config file specified but not found
        ValueError: If configuration is invalid
    """
    # Default config file path
    if config_file is None:
        config_file = Path("mocks/config.json")

    # Load from JSON file if exists
    config_data = {}
    if config_file.exists():
        try:
            with open(config_file) as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse configuration file '{config_file}': {e}. "
                f"Ensure the file contains valid JSON."
            )
    elif config_file != Path("mocks/config.json"):
        # Only raise if non-default config file was explicitly specified
        raise FileNotFoundError(
            f"Configuration file not found: '{config_file}'. "
            f"Ensure the file exists or check the path."
        )

    # Override with environment variables (MOCK_SERVER_ prefix)
    env_prefix = "MOCK_SERVER_"
    for key in MockServerConfig.model_fields.keys():
        env_key = f"{env_prefix}{key.upper()}"
        if env_key in os.environ:
            value = os.environ[env_key]
            # Convert to int for port fields
            if key in ["http_port", "https_port"]:
                try:
                    value = int(value)
                except ValueError:
                    raise ValueError(
                        f"Invalid value for {env_key}: '{value}'. Must be an integer."
                    )
            config_data[key] = value

    # Create and validate configuration
    try:
        config = MockServerConfig(**config_data)
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")

    return config


class ConfigWatcher:
    """Watches configuration file for changes and reloads.
    
    Attributes:
        config_path: Path to configuration file
        config: Current configuration instance
        last_modified: Last modification time of config file
    """

    def __init__(self, config_path: Path, config: MockServerConfig):
        """Initialize ConfigWatcher.
        
        Args:
            config_path: Path to configuration file to watch
            config: Initial configuration instance
        """
        self.config_path = config_path
        self.config = config
        self.last_modified = self._get_mtime()

    def _get_mtime(self) -> float:
        """Get file modification time.
        
        Returns:
            Modification timestamp, or 0.0 if file doesn't exist
        """
        if self.config_path.exists():
            return self.config_path.stat().st_mtime
        return 0.0

    def check_reload(self) -> bool:
        """Check if config file changed and reload if needed.
        
        Returns:
            True if config was reloaded, False otherwise
        """
        import logging

        logger = logging.getLogger(__name__)

        current_mtime = self._get_mtime()
        if current_mtime > self.last_modified:
            try:
                self.config = load_config(self.config_path)
                self.last_modified = current_mtime
                logger.info("Configuration reloaded from %s", self.config_path)
                return True
            except Exception as e:
                logger.warning(
                    "Failed to reload configuration from %s: %s. Keeping existing config.",
                    self.config_path,
                    e,
                )
        return False
