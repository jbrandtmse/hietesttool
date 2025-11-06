"""Default configuration values.

This module defines the default configuration values used when no configuration
file is provided or when configuration values are not specified.
"""

from typing import Any

# Default configuration dictionary
# This is used as a fallback when no configuration file is present
DEFAULT_CONFIG: dict[str, Any] = {
    "endpoints": {
        # Default to localhost mock endpoints
        "pix_add_url": "http://localhost:8080/pix/add",
        "iti41_url": "http://localhost:8080/iti41/submit",
    },
    "certificates": {
        # No default certificate paths - must be provided by user
        "cert_path": None,
        "key_path": None,
        # Default certificate format is PEM
        "cert_format": "pem",
        # Default environment variable for PKCS12 password
        "pkcs12_password_env_var": "IHE_TEST_PKCS12_PASSWORD",
    },
    "transport": {
        # Verify TLS certificates by default for security
        "verify_tls": True,
        # Connection timeout: 10 seconds
        "timeout_connect": 10,
        # Read timeout: 30 seconds
        "timeout_read": 30,
        # Retry up to 3 times on failure
        "max_retries": 3,
        # Exponential backoff factor: 1.0 second
        "backoff_factor": 1.0,
    },
    "logging": {
        # Default log level: INFO (moderate verbosity)
        "level": "INFO",
        # Default log file path
        "log_file": "logs/ihe-test-util.log",
        # Do not redact PII by default (user must opt-in for privacy)
        "redact_pii": False,
    },
}

# Default configuration file path
DEFAULT_CONFIG_PATH = "config/config.json"
