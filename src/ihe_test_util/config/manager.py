"""Configuration manager for loading and managing configuration.

This module provides the main configuration loading and management functionality,
including support for JSON configuration files, environment variable overrides,
and configuration validation.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import ValidationError

from ihe_test_util.config.defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_PATH
from ihe_test_util.config.schema import (
    BatchConfig,
    Config,
    LoggingConfig,
    OperationLoggingConfig,
    TemplateConfig,
    TransportConfig,
)
from ihe_test_util.utils.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Environment variable prefix for all configuration overrides
ENV_PREFIX = "IHE_TEST_"


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from file and environment variables.
    
    Configuration is loaded with the following precedence (highest to lowest):
    1. CLI arguments (handled by caller)
    2. Environment variables (IHE_TEST_* prefix)
    3. Configuration file (JSON)
    4. Default values
    
    Args:
        config_path: Path to configuration file. If None, uses ./config/config.json
        
    Returns:
        Validated Config instance
        
    Raises:
        ConfigurationError: If configuration is invalid or malformed
        
    Example:
        >>> config = load_config(Path("custom/config.json"))
        >>> pix_url = config.endpoints.pix_add_url
        >>> 
        >>> # Use with defaults
        >>> config = load_config()
        >>> log_level = config.logging.level
    """
    # Load .env file if present in project root
    load_dotenv()
    
    # Determine config file path
    if config_path is None:
        config_path = Path(DEFAULT_CONFIG_PATH)
    
    # Load config file or use defaults
    config_dict = _load_config_file(config_path)
    
    # Apply environment variable overrides
    config_dict = _apply_env_overrides(config_dict)
    
    # Check for sensitive values in config file
    _check_sensitive_values(config_dict)
    
    # Validate and return
    try:
        return Config(**config_dict)
    except ValidationError as e:
        raise ConfigurationError(
            f"Configuration validation failed:\n{e}\n\n"
            f"Fix: Check your configuration file at {config_path} and ensure all "
            f"values match the expected format. See documentation for details."
        )


def _load_config_file(config_path: Path) -> dict[str, Any]:
    """Load configuration file or return defaults.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        ConfigurationError: If JSON is malformed
    """
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config_dict
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in config file: {config_path}\n"
                f"Error: {e}\n"
                f"Fix: Check JSON syntax at line {e.lineno}, column {e.colno}"
            )
        except (OSError, IOError) as e:
            raise ConfigurationError(
                f"Failed to read config file: {config_path}\n"
                f"Error: {e}\n"
                f"Fix: Check file permissions and path"
            )
    else:
        logger.info(
            f"Config file not found: {config_path}. Using default configuration."
        )
        # Return a deep copy of defaults to avoid mutation
        return json.loads(json.dumps(DEFAULT_CONFIG))


def _apply_env_overrides(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides with IHE_TEST_ prefix.
    
    Environment variables follow the pattern: IHE_TEST_<SECTION>_<FIELD>
    For example: IHE_TEST_PIX_ADD_URL, IHE_TEST_LOG_LEVEL
    
    Extended in Story 6.6 with batch and template overrides:
    - IHE_TEST_BATCH_* for batch processing settings
    - IHE_TEST_TEMPLATE_* for template paths
    - IHE_TEST_OP_LOG_* for per-operation logging
    
    Args:
        config_dict: Configuration dictionary to update
        
    Returns:
        Updated configuration dictionary with environment overrides applied
    """
    # Endpoints section
    if pix_add_url := os.getenv(f"{ENV_PREFIX}PIX_ADD_URL"):
        config_dict.setdefault("endpoints", {})["pix_add_url"] = pix_add_url
        logger.debug("Override: pix_add_url from environment")
    
    if iti41_url := os.getenv(f"{ENV_PREFIX}ITI41_URL"):
        config_dict.setdefault("endpoints", {})["iti41_url"] = iti41_url
        logger.debug("Override: iti41_url from environment")
    
    # Certificates section
    if cert_path := os.getenv(f"{ENV_PREFIX}CERT_PATH"):
        config_dict.setdefault("certificates", {})["cert_path"] = cert_path
        logger.debug("Override: cert_path from environment")
    
    if key_path := os.getenv(f"{ENV_PREFIX}KEY_PATH"):
        config_dict.setdefault("certificates", {})["key_path"] = key_path
        logger.debug("Override: key_path from environment")
    
    if cert_format := os.getenv(f"{ENV_PREFIX}CERT_FORMAT"):
        config_dict.setdefault("certificates", {})["cert_format"] = cert_format
        logger.debug("Override: cert_format from environment")
    
    # Transport section
    if verify_tls := os.getenv(f"{ENV_PREFIX}VERIFY_TLS"):
        config_dict.setdefault("transport", {})["verify_tls"] = _parse_bool(
            verify_tls
        )
        logger.debug("Override: verify_tls from environment")
    
    if timeout_connect := os.getenv(f"{ENV_PREFIX}TIMEOUT_CONNECT"):
        config_dict.setdefault("transport", {})["timeout_connect"] = int(
            timeout_connect
        )
        logger.debug("Override: timeout_connect from environment")
    
    if timeout_read := os.getenv(f"{ENV_PREFIX}TIMEOUT_READ"):
        config_dict.setdefault("transport", {})["timeout_read"] = int(timeout_read)
        logger.debug("Override: timeout_read from environment")
    
    if max_retries := os.getenv(f"{ENV_PREFIX}MAX_RETRIES"):
        config_dict.setdefault("transport", {})["max_retries"] = int(max_retries)
        logger.debug("Override: max_retries from environment")
    
    if backoff_factor := os.getenv(f"{ENV_PREFIX}BACKOFF_FACTOR"):
        config_dict.setdefault("transport", {})["backoff_factor"] = float(
            backoff_factor
        )
        logger.debug("Override: backoff_factor from environment")
    
    # Logging section
    if log_level := os.getenv(f"{ENV_PREFIX}LOG_LEVEL"):
        config_dict.setdefault("logging", {})["level"] = log_level
        logger.debug("Override: log_level from environment")
    
    if log_file := os.getenv(f"{ENV_PREFIX}LOG_FILE"):
        config_dict.setdefault("logging", {})["log_file"] = log_file
        logger.debug("Override: log_file from environment")
    
    if redact_pii := os.getenv(f"{ENV_PREFIX}REDACT_PII"):
        config_dict.setdefault("logging", {})["redact_pii"] = _parse_bool(redact_pii)
        logger.debug("Override: redact_pii from environment")
    
    # Story 6.6: Apply batch and template overrides
    config_dict = _apply_batch_env_overrides(config_dict)
    config_dict = _apply_template_env_overrides(config_dict)
    config_dict = _apply_operation_logging_env_overrides(config_dict)
    
    return config_dict


def _apply_batch_env_overrides(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Apply batch configuration environment variable overrides.
    
    Environment variables follow the pattern: IHE_TEST_BATCH_<FIELD>
    For example: IHE_TEST_BATCH_SIZE, IHE_TEST_BATCH_CHECKPOINT_INTERVAL
    
    Args:
        config_dict: Configuration dictionary to update
        
    Returns:
        Updated configuration dictionary with batch overrides applied
    """
    # Batch section (Story 6.6)
    if batch_size := os.getenv(f"{ENV_PREFIX}BATCH_SIZE"):
        config_dict.setdefault("batch", {})["batch_size"] = int(batch_size)
        logger.debug("Override: batch_size from environment")
    
    if checkpoint_interval := os.getenv(f"{ENV_PREFIX}BATCH_CHECKPOINT_INTERVAL"):
        config_dict.setdefault("batch", {})["checkpoint_interval"] = int(
            checkpoint_interval
        )
        logger.debug("Override: checkpoint_interval from environment")
    
    if checkpoint_file := os.getenv(f"{ENV_PREFIX}BATCH_CHECKPOINT_FILE"):
        config_dict.setdefault("batch", {})["checkpoint_file"] = checkpoint_file
        logger.debug("Override: checkpoint_file from environment")
    
    if resume_enabled := os.getenv(f"{ENV_PREFIX}BATCH_RESUME_ENABLED"):
        config_dict.setdefault("batch", {})["resume_enabled"] = _parse_bool(
            resume_enabled
        )
        logger.debug("Override: resume_enabled from environment")
    
    if fail_fast := os.getenv(f"{ENV_PREFIX}BATCH_FAIL_FAST"):
        config_dict.setdefault("batch", {})["fail_fast"] = _parse_bool(fail_fast)
        logger.debug("Override: fail_fast from environment")
    
    if concurrent_connections := os.getenv(f"{ENV_PREFIX}BATCH_CONCURRENT_CONNECTIONS"):
        config_dict.setdefault("batch", {})["concurrent_connections"] = int(
            concurrent_connections
        )
        logger.debug("Override: concurrent_connections from environment")
    
    if output_dir := os.getenv(f"{ENV_PREFIX}BATCH_OUTPUT_DIR"):
        config_dict.setdefault("batch", {})["output_dir"] = output_dir
        logger.debug("Override: output_dir from environment")
    
    return config_dict


def _apply_template_env_overrides(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Apply template configuration environment variable overrides.
    
    Environment variables follow the pattern: IHE_TEST_TEMPLATE_<FIELD>
    For example: IHE_TEST_TEMPLATE_CCD_PATH, IHE_TEST_TEMPLATE_SAML_PATH
    
    Args:
        config_dict: Configuration dictionary to update
        
    Returns:
        Updated configuration dictionary with template overrides applied
    """
    # Templates section (Story 6.6)
    if ccd_template_path := os.getenv(f"{ENV_PREFIX}TEMPLATE_CCD_PATH"):
        config_dict.setdefault("templates", {})["ccd_template_path"] = ccd_template_path
        logger.debug("Override: ccd_template_path from environment")
    
    if saml_template_path := os.getenv(f"{ENV_PREFIX}TEMPLATE_SAML_PATH"):
        config_dict.setdefault("templates", {})["saml_template_path"] = saml_template_path
        logger.debug("Override: saml_template_path from environment")
    
    return config_dict


def _apply_operation_logging_env_overrides(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Apply per-operation logging configuration environment variable overrides.
    
    Environment variables follow the pattern: IHE_TEST_OP_LOG_<OPERATION>_LEVEL
    For example: IHE_TEST_OP_LOG_CSV_LEVEL, IHE_TEST_OP_LOG_PIX_ADD_LEVEL
    
    Args:
        config_dict: Configuration dictionary to update
        
    Returns:
        Updated configuration dictionary with operation logging overrides applied
    """
    # Operation logging section (Story 6.6)
    if csv_log_level := os.getenv(f"{ENV_PREFIX}OP_LOG_CSV_LEVEL"):
        config_dict.setdefault("operation_logging", {})["csv_log_level"] = csv_log_level
        logger.debug("Override: csv_log_level from environment")
    
    if pix_add_log_level := os.getenv(f"{ENV_PREFIX}OP_LOG_PIX_ADD_LEVEL"):
        config_dict.setdefault("operation_logging", {})["pix_add_log_level"] = pix_add_log_level
        logger.debug("Override: pix_add_log_level from environment")
    
    if iti41_log_level := os.getenv(f"{ENV_PREFIX}OP_LOG_ITI41_LEVEL"):
        config_dict.setdefault("operation_logging", {})["iti41_log_level"] = iti41_log_level
        logger.debug("Override: iti41_log_level from environment")
    
    if saml_log_level := os.getenv(f"{ENV_PREFIX}OP_LOG_SAML_LEVEL"):
        config_dict.setdefault("operation_logging", {})["saml_log_level"] = saml_log_level
        logger.debug("Override: saml_log_level from environment")
    
    return config_dict


def _parse_bool(value: str) -> bool:
    """Parse boolean value from string.
    
    Args:
        value: String value to parse (case-insensitive)
        
    Returns:
        Boolean value
    """
    return value.lower() in ("true", "1", "yes", "on")


def _check_sensitive_values(config_dict: dict[str, Any]) -> None:
    """Check for sensitive values in configuration and warn user.
    
    Sensitive values like passwords should be in environment variables,
    not in configuration files.
    
    Args:
        config_dict: Configuration dictionary to check
    """
    # Check if PKCS12 password is in config (it shouldn't be)
    certs = config_dict.get("certificates", {})
    if "pkcs12_password" in certs:
        logger.warning(
            "WARNING: PKCS12 password found in configuration file! "
            "Passwords should be stored in environment variables, not config files. "
            f"Use {ENV_PREFIX}PKCS12_PASSWORD environment variable instead."
        )


def get_endpoint(config: Config, endpoint_name: str) -> str:
    """Get endpoint URL by name.
    
    Args:
        config: Configuration instance
        endpoint_name: Name of endpoint ('pix_add' or 'iti41')
        
    Returns:
        Endpoint URL string
        
    Raises:
        ValueError: If endpoint_name is invalid
        
    Example:
        >>> config = load_config()
        >>> pix_url = get_endpoint(config, 'pix_add')
    """
    if endpoint_name == "pix_add":
        return config.endpoints.pix_add_url
    elif endpoint_name == "iti41":
        return config.endpoints.iti41_url
    else:
        raise ValueError(
            f"Invalid endpoint name: {endpoint_name}. "
            f"Must be one of: 'pix_add', 'iti41'"
        )


def get_certificate_paths(config: Config) -> tuple[Optional[Path], Optional[Path]]:
    """Get certificate and key paths from configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        Tuple of (cert_path, key_path) as Path objects or None
        
    Example:
        >>> config = load_config()
        >>> cert_path, key_path = get_certificate_paths(config)
        >>> if cert_path:
        ...     with open(cert_path, 'r') as f:
        ...         cert_data = f.read()
    """
    return config.certificates.cert_path, config.certificates.key_path


def get_transport_config(config: Config) -> TransportConfig:
    """Get transport configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        TransportConfig instance
        
    Example:
        >>> config = load_config()
        >>> transport = get_transport_config(config)
        >>> timeout = transport.timeout_connect
    """
    return config.transport


def get_logging_config(config: Config) -> LoggingConfig:
    """Get logging configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        LoggingConfig instance
        
    Example:
        >>> config = load_config()
        >>> logging_cfg = get_logging_config(config)
        >>> log_level = logging_cfg.level
    """
    return config.logging


def get_batch_config(config: Config) -> BatchConfig:
    """Get batch processing configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        BatchConfig instance
        
    Example:
        >>> config = load_config()
        >>> batch_cfg = get_batch_config(config)
        >>> checkpoint_interval = batch_cfg.checkpoint_interval
    """
    return config.batch


def get_template_config(config: Config) -> TemplateConfig:
    """Get template paths configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        TemplateConfig instance
        
    Example:
        >>> config = load_config()
        >>> template_cfg = get_template_config(config)
        >>> ccd_path = template_cfg.ccd_template_path
    """
    return config.templates


def get_operation_logging_config(config: Config) -> OperationLoggingConfig:
    """Get per-operation logging configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        OperationLoggingConfig instance
        
    Example:
        >>> config = load_config()
        >>> op_log_cfg = get_operation_logging_config(config)
        >>> pix_add_level = op_log_cfg.pix_add_log_level
    """
    return config.operation_logging
