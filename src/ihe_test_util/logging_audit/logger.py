"""Logging configuration and logger factory for the IHE Test Utility.

This module provides centralized logging configuration with support for:
- Console and file handlers with different log levels
- Log rotation to prevent unbounded file growth
- PII redaction via custom formatters
- Environment variable configuration
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .formatters import PIIRedactingFormatter

# Type hint for Config import (avoid circular import)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.schema import Config, OperationLoggingConfig

# Constants
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_FILE = Path("logs") / "ihe-test-util.log"
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

# Track if logging has been configured
_logging_configured = False

# Operation-specific logger names
OPERATION_LOGGERS = {
    "csv": "ihe_test_util.csv",
    "pix_add": "ihe_test_util.pix_add",
    "iti41": "ihe_test_util.iti41",
    "saml": "ihe_test_util.saml",
}

# Module-level logger for this module
logger = logging.getLogger(__name__)


def configure_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    redact_pii: bool = False,
) -> None:
    """Configure logging for the IHE Test Utility.
    
    Sets up both console and file handlers with appropriate log levels and formatting.
    This function is idempotent - it can be called multiple times safely.
    
    Args:
        level: Log level for console output (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               File handler always uses DEBUG level.
        log_file: Path to log file. If None, uses DEFAULT_LOG_FILE or
                 IHE_TEST_LOG_FILE environment variable if set.
        redact_pii: Whether to redact PII (patient names, SSNs) from logs
        
    Raises:
        ValueError: If invalid log level is provided
        RuntimeError: If log directory cannot be created
        
    Example:
        >>> from pathlib import Path
        >>> configure_logging(level="DEBUG", redact_pii=True)
        >>> configure_logging(level="INFO", log_file=Path("custom/app.log"))
    """
    global _logging_configured
    
    # Validate log level
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(
            f"Invalid log level: {level}. "
            f"Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
        )
    
    # Determine log file path
    if log_file is None:
        # Check environment variable first
        env_log_file = os.environ.get("IHE_TEST_LOG_FILE")
        if env_log_file:
            log_file = Path(env_log_file)
        else:
            log_file = DEFAULT_LOG_FILE
    
    # Create log directory if it doesn't exist
    log_dir = log_file.parent
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise RuntimeError(
            f"Failed to create log directory: {log_dir}. "
            f"Ensure write permissions are available. Error: {e}"
        ) from e
    
    # Get root logger
    root_logger = logging.getLogger()
    
    # If already configured, remove existing handlers to avoid duplicates
    if _logging_configured:
        root_logger.handlers.clear()
    
    # Set root logger to DEBUG to allow all messages through
    root_logger.setLevel(logging.DEBUG)
    
    # Create formatters
    console_formatter = PIIRedactingFormatter(
        fmt=DEFAULT_LOG_FORMAT,
        redact_pii=redact_pii,
    )
    file_formatter = PIIRedactingFormatter(
        fmt=DEFAULT_LOG_FORMAT,
        redact_pii=redact_pii,
    )
    
    # Console handler - INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler - DEBUG and above with rotation
    try:
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=MAX_LOG_FILE_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # Log to console if file handler fails, but don't fail completely
        root_logger.warning(
            f"Failed to create file handler for {log_file}: {e}. "
            f"Logging to console only."
        )
    
    _logging_configured = True


def get_logger(module_name: str) -> logging.Logger:
    """Get a logger for the specified module.
    
    This is a convenience function that should be called with __name__
    from the calling module to create module-specific loggers.
    
    Args:
        module_name: Name of the module, typically __name__
        
    Returns:
        Configured logger instance for the module
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
        >>> logger.debug("Detailed processing information")
        >>> logger.error("An error occurred")
    """
    return logging.getLogger(module_name)


def get_operation_logger(operation: str) -> logging.Logger:
    """Get a logger for a specific operation type.
    
    Operation loggers enable per-operation log level configuration.
    Supported operations: csv, pix_add, iti41, saml.
    
    Args:
        operation: Operation type (csv, pix_add, iti41, saml)
        
    Returns:
        Logger instance for the operation
        
    Raises:
        ValueError: If operation is not a recognized type
        
    Example:
        >>> logger = get_operation_logger("pix_add")
        >>> logger.info("PIX Add transaction started")
    """
    if operation not in OPERATION_LOGGERS:
        raise ValueError(
            f"Unknown operation: {operation}. "
            f"Must be one of: {', '.join(OPERATION_LOGGERS.keys())}"
        )
    return logging.getLogger(OPERATION_LOGGERS[operation])


def configure_operation_logging(
    csv_log_level: str = "INFO",
    pix_add_log_level: str = "INFO",
    iti41_log_level: str = "INFO",
    saml_log_level: str = "WARNING",
) -> None:
    """Configure logging levels for each operation type.
    
    Allows different verbosity for different operations, useful for
    debugging specific transaction types without excessive logging.
    
    Args:
        csv_log_level: Log level for CSV processing operations
        pix_add_log_level: Log level for PIX Add transactions
        iti41_log_level: Log level for ITI-41 transactions
        saml_log_level: Log level for SAML operations
        
    Raises:
        ValueError: If any log level is invalid
        
    Example:
        >>> configure_operation_logging(
        ...     csv_log_level="DEBUG",
        ...     pix_add_log_level="INFO",
        ...     iti41_log_level="INFO",
        ...     saml_log_level="WARNING"
        ... )
    """
    levels = {
        "csv": csv_log_level,
        "pix_add": pix_add_log_level,
        "iti41": iti41_log_level,
        "saml": saml_log_level,
    }
    
    for operation, level in levels.items():
        numeric_level = getattr(logging, level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(
                f"Invalid log level for {operation}: {level}. "
                f"Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
            )
        
        logger_name = OPERATION_LOGGERS[operation]
        operation_logger = logging.getLogger(logger_name)
        operation_logger.setLevel(numeric_level)
        logger.debug(
            "Set %s logger level to %s", logger_name, level.upper()
        )


def configure_operation_logging_from_config(config: "OperationLoggingConfig") -> None:
    """Configure operation logging from OperationLoggingConfig object.
    
    Convenience function that accepts an OperationLoggingConfig object
    instead of individual parameters.
    
    Args:
        config: OperationLoggingConfig with log levels for each operation
        
    Example:
        >>> from ihe_test_util.config.schema import OperationLoggingConfig
        >>> config = OperationLoggingConfig(csv_log_level="DEBUG")
        >>> configure_operation_logging_from_config(config)
    """
    configure_operation_logging(
        csv_log_level=config.csv_log_level,
        pix_add_log_level=config.pix_add_log_level,
        iti41_log_level=config.iti41_log_level,
        saml_log_level=config.saml_log_level,
    )


def set_operation_log_level(operation: str, level: str) -> None:
    """Set log level for a specific operation at runtime.
    
    Enables dynamic log level changes without reconfiguring all operations.
    
    Args:
        operation: Operation type (csv, pix_add, iti41, saml)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Raises:
        ValueError: If operation or level is invalid
        
    Example:
        >>> set_operation_log_level("pix_add", "DEBUG")
        >>> # Later, reduce verbosity
        >>> set_operation_log_level("pix_add", "WARNING")
    """
    if operation not in OPERATION_LOGGERS:
        raise ValueError(
            f"Unknown operation: {operation}. "
            f"Must be one of: {', '.join(OPERATION_LOGGERS.keys())}"
        )
    
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(
            f"Invalid log level: {level}. "
            f"Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
        )
    
    logger_name = OPERATION_LOGGERS[operation]
    operation_logger = logging.getLogger(logger_name)
    operation_logger.setLevel(numeric_level)
    logger.debug("Set %s logger level to %s", logger_name, level.upper())
