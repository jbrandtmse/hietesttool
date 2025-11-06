# Configuration Guide

Complete reference for configuring the IHE Test Utility.

## Table of Contents

1. [Overview](#overview)
2. [Configuration File Format](#configuration-file-format)
3. [Configuration Sections](#configuration-sections)
4. [Environment Variables](#environment-variables)
5. [Configuration Precedence](#configuration-precedence)
6. [CLI Integration](#cli-integration)
7. [Security Best Practices](#security-best-practices)
8. [Common Configuration Scenarios](#common-configuration-scenarios)
9. [Troubleshooting](#troubleshooting)

## Overview

The IHE Test Utility uses a flexible configuration system that supports:

- **JSON configuration files** for persistent settings
- **Environment variables** for deployment-specific overrides
- **CLI flags** for per-command customization
- **Validation** to catch configuration errors early

### Quick Start

1. Copy the example configuration:
   ```bash
   cp examples/config.example.json config/config.json
   ```

2. Edit `config/config.json` to match your environment

3. Run with configuration:
   ```bash
   ihe-test-util --config config/config.json <command>
   ```

## Configuration File Format

Configuration files must be valid JSON with the following structure:

```json
{
  "endpoints": {
    "pix_add_url": "http://localhost:8080/pix/add",
    "iti41_url": "http://localhost:8080/iti41/submit"
  },
  "certificates": {
    "cert_path": "path/to/cert.pem",
    "key_path": "path/to/key.pem",
    "cert_format": "pem",
    "pkcs12_password_env_var": "IHE_TEST_PKCS12_PASSWORD"
  },
  "transport": {
    "verify_tls": true,
    "timeout_connect": 10,
    "timeout_read": 30,
    "max_retries": 3,
    "backoff_factor": 1.0
  },
  "logging": {
    "level": "INFO",
    "log_file": "logs/ihe-test-util.log",
    "redact_pii": false
  }
}
```

### Default Location

The default configuration file location is:
```
./config/config.json
```

This path is relative to the directory where you run the `ihe-test-util` command.

## Configuration Sections

### Endpoints

IHE endpoint URLs for PIX Add and ITI-41 transactions.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `pix_add_url` | string | Yes | `http://localhost:8080/pix/add` | PIX Add endpoint URL (ITI-8 transaction) |
| `iti41_url` | string | Yes | `http://localhost:8080/iti41/submit` | ITI-41 endpoint URL (Provide and Register Document Set-b) |

**Validation:**
- URLs must start with `http://` or `https://`

**Example:**
```json
{
  "endpoints": {
    "pix_add_url": "https://pix.hospital.org/pix/add",
    "iti41_url": "https://xds.hospital.org/iti41/submit"
  }
}
```

### Certificates

Certificate and private key configuration for SAML signing and TLS client authentication.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `cert_path` | string | No | `null` | Path to certificate file (PEM, PKCS12, or DER) |
| `key_path` | string | No | `null` | Path to private key file |
| `cert_format` | string | No | `"pem"` | Certificate format: `pem`, `pkcs12`, or `der` |
| `pkcs12_password_env_var` | string | No | `"IHE_TEST_PKCS12_PASSWORD"` | Environment variable for PKCS12 password |

**Validation:**
- `cert_format` must be one of: `pem`, `pkcs12`, `der`
- Paths can be relative or absolute

**Example:**
```json
{
  "certificates": {
    "cert_path": "/etc/ihe-test-util/certs/client.pem",
    "key_path": "/etc/ihe-test-util/certs/client-key.pem",
    "cert_format": "pem"
  }
}
```

**Security Note:** Never store certificate passwords in configuration files. Use environment variables instead.

### Transport

HTTP/HTTPS transport configuration for IHE transactions.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `verify_tls` | boolean | No | `true` | Whether to verify TLS certificates |
| `timeout_connect` | integer | No | `10` | Connection timeout in seconds (≥1) |
| `timeout_read` | integer | No | `30` | Read timeout in seconds (≥1) |
| `max_retries` | integer | No | `3` | Maximum retry attempts (≥0) |
| `backoff_factor` | float | No | `1.0` | Exponential backoff factor (≥0.0) |

**Validation:**
- `timeout_connect` must be ≥ 1
- `timeout_read` must be ≥ 1
- `max_retries` must be ≥ 0
- `backoff_factor` must be ≥ 0.0

**Example:**
```json
{
  "transport": {
    "verify_tls": true,
    "timeout_connect": 15,
    "timeout_read": 60,
    "max_retries": 5,
    "backoff_factor": 2.0
  }
}
```

### Logging

Logging and audit trail configuration.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `level` | string | No | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `log_file` | string | No | `"logs/ihe-test-util.log"` | Path to log file |
| `redact_pii` | boolean | No | `false` | Whether to redact PII from logs |

**Validation:**
- `level` must be one of: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (case-insensitive)

**Example:**
```json
{
  "logging": {
    "level": "DEBUG",
    "log_file": "/var/log/ihe-test-util/app.log",
    "redact_pii": true
  }
}
```

## Environment Variables

All configuration values can be overridden using environment variables with the `IHE_TEST_` prefix.

### Supported Environment Variables

| Variable | Type | Overrides | Example |
|----------|------|-----------|---------|
| `IHE_TEST_PIX_ADD_URL` | string | `endpoints.pix_add_url` | `https://pix.example.com/add` |
| `IHE_TEST_ITI41_URL` | string | `endpoints.iti41_url` | `https://xds.example.com/submit` |
| `IHE_TEST_CERT_PATH` | string | `certificates.cert_path` | `/path/to/cert.pem` |
| `IHE_TEST_KEY_PATH` | string | `certificates.key_path` | `/path/to/key.pem` |
| `IHE_TEST_CERT_FORMAT` | string | `certificates.cert_format` | `pem` |
| `IHE_TEST_PKCS12_PASSWORD` | string | (password) | `my-secret-password` |
| `IHE_TEST_VERIFY_TLS` | boolean | `transport.verify_tls` | `true` or `false` |
| `IHE_TEST_TIMEOUT_CONNECT` | integer | `transport.timeout_connect` | `15` |
| `IHE_TEST_TIMEOUT_READ` | integer | `transport.timeout_read` | `60` |
| `IHE_TEST_MAX_RETRIES` | integer | `transport.max_retries` | `5` |
| `IHE_TEST_BACKOFF_FACTOR` | float | `transport.backoff_factor` | `2.0` |
| `IHE_TEST_LOG_LEVEL` | string | `logging.level` | `DEBUG` |
| `IHE_TEST_LOG_FILE` | string | `logging.log_file` | `/var/log/app.log` |
| `IHE_TEST_REDACT_PII` | boolean | `logging.redact_pii` | `true` or `false` |

### Boolean Values

Boolean environment variables accept (case-insensitive):
- **True:** `true`, `1`, `yes`, `on`
- **False:** `false`, `0`, `no`, `off` (or any other value)

### Using .env Files

Create a `.env` file in your project root for local development:

```bash
# .env
IHE_TEST_PIX_ADD_URL=http://localhost:8080/pix/add
IHE_TEST_ITI41_URL=http://localhost:8080/iti41/submit
IHE_TEST_LOG_LEVEL=DEBUG
IHE_TEST_PKCS12_PASSWORD=my-dev-password
```

The utility automatically loads `.env` files using `python-dotenv`.

**Security Note:** Never commit `.env` files with secrets to Git. Use `.env.example` as a template.

## Configuration Precedence

Configuration values are loaded with the following precedence (highest to lowest):

1. **CLI Arguments** - Flags passed directly to commands
2. **Environment Variables** - `IHE_TEST_*` variables
3. **Configuration File** - Values in `config.json`
4. **Defaults** - Built-in default values

### Example

Given:
- `config.json` has `"level": "INFO"`
- Environment variable `IHE_TEST_LOG_LEVEL=WARNING`
- CLI flag `--verbose` (sets DEBUG)

The effective log level will be `DEBUG` (CLI flag wins).

## CLI Integration

### Global --config Flag

Override the default configuration file location:

```bash
ihe-test-util --config /path/to/custom/config.json <command>
```

### Configuration Validation

Validate a configuration file without running any operations:

```bash
ihe-test-util config validate config/config.json
```

**Success output:**
```
✓ Configuration is valid

Configuration file: config/config.json

Endpoints:
  PIX Add URL: http://localhost:8080/pix/add
  ITI-41 URL:  http://localhost:8080/iti41/submit

Certificates:
  Cert path:   tests/fixtures/test_cert.pem
  Key path:    tests/fixtures/test_key.pem
  Format:      pem

Transport:
  Verify TLS:  True
  Timeouts:    10s connect, 30s read
  Retries:     3

Logging:
  Level:       INFO
  Log file:    logs/ihe-test-util.log
  Redact PII:  False
```

**Failure output:**
```
✗ Configuration validation failed

Configuration validation failed:
1 validation error for Config
endpoints -> pix_add_url
  Invalid URL: ftp://invalid. Must start with http:// or https://
```

### Combining with Other Flags

Configuration can be combined with other CLI flags:

```bash
# Use custom config with verbose logging
ihe-test-util --config prod.json --verbose csv validate patients.csv

# Override log file from config
ihe-test-util --log-file /tmp/debug.log csv process patients.csv
```

## Security Best Practices

### Never Store Secrets in Configuration Files

❌ **DON'T:**
```json
{
  "certificates": {
    "pkcs12_password": "my-secret-password"
  }
}
```

✅ **DO:**
```bash
export IHE_TEST_PKCS12_PASSWORD="my-secret-password"
```

### Use Environment Variables for Sensitive Data

Sensitive values that should NEVER be in configuration files:
- Certificate passwords
- API keys
- Authentication tokens
- Database passwords

### Protect Configuration Files

```bash
# Set restrictive permissions
chmod 600 config/config.json

# Never commit with secrets
echo "config/config.json" >> .gitignore
```

### Use Different Configs for Different Environments

```
config/
├── dev.json
├── test.json
├── staging.json
└── prod.json
```

```bash
# Development
ihe-test-util --config config/dev.json <command>

# Production
ihe-test-util --config config/prod.json <command>
```

## Common Configuration Scenarios

### Local Development with Mock Endpoints

```json
{
  "endpoints": {
    "pix_add_url": "http://localhost:8080/pix/add",
    "iti41_url": "http://localhost:8080/iti41/submit"
  },
  "certificates": {
    "cert_path": null,
    "key_path": null
  },
  "transport": {
    "verify_tls": false
  },
  "logging": {
    "level": "DEBUG",
    "redact_pii": false
  }
}
```

### Production with Real Endpoints

```json
{
  "endpoints": {
    "pix_add_url": "https://pix.hospital.org/pix/add",
    "iti41_url": "https://xds.hospital.org/iti41/submit"
  },
  "certificates": {
    "cert_path": "/etc/ihe-test-util/certs/prod-client.pem",
    "key_path": "/etc/ihe-test-util/certs/prod-client-key.pem",
    "cert_format": "pem"
  },
  "transport": {
    "verify_tls": true,
    "timeout_connect": 15,
    "timeout_read": 60,
    "max_retries": 5
  },
  "logging": {
    "level": "INFO",
    "log_file": "/var/log/ihe-test-util/prod.log",
    "redact_pii": true
  }
}
```

### Testing with Environment Overrides

**config/test.json:**
```json
{
  "endpoints": {
    "pix_add_url": "http://test-default:8080/pix/add",
    "iti41_url": "http://test-default:8080/iti41/submit"
  },
  "logging": {
    "level": "DEBUG"
  }
}
```

**Environment variables override for specific test:**
```bash
export IHE_TEST_PIX_ADD_URL=http://test-server-2:8080/pix/add
ihe-test-util --config config/test.json csv validate patients.csv
```

## Troubleshooting

### Configuration File Not Found

**Symptom:**
```
Config file not found: ./config/config.json. Using default configuration.
```

**Solution:**
This is informational. The utility will use built-in defaults. To create a configuration file:
```bash
cp examples/config.example.json config/config.json
```

### Malformed JSON

**Symptom:**
```
Error loading configuration: Invalid JSON in config file: ./config/config.json
Error: Expecting ',' delimiter: line 10 column 5 (char 234)
Fix: Check JSON syntax at line 10, column 5
```

**Solution:**
- Check for missing or extra commas
- Ensure all quotes are properly closed
- Ensure all brackets `[]` and braces `{}` are balanced
- Use a JSON validator: https://jsonlint.com/

### Invalid URL

**Symptom:**
```
Configuration validation failed:
1 validation error for Config
endpoints -> pix_add_url
  Invalid URL: ftp://invalid. Must start with http:// or https://
```

**Solution:**
Ensure all endpoint URLs start with `http://` or `https://`.

### Invalid Log Level

**Symptom:**
```
Configuration validation failed:
1 validation error for Config
logging -> level
  Invalid log level: TRACE. Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Solution:**
Use one of the valid log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### Environment Variable Not Taking Effect

**Symptom:**
Configuration file value is used instead of environment variable.

**Solution:**
1. Ensure environment variable has `IHE_TEST_` prefix
2. Check variable name matches exactly (case-sensitive)
3. Verify variable is exported: `echo $IHE_TEST_PIX_ADD_URL`
4. Remember CLI flags override environment variables

### Permission Denied

**Symptom:**
```
Error loading configuration: Failed to read config file: ./config/config.json
Error: [Errno 13] Permission denied: './config/config.json'
```

**Solution:**
```bash
chmod 644 config/config.json
```

## Further Reading

- [Configuration Examples](../examples/config.example.json) - Commented example configurations
- [Environment Variables](../.env.example) - Environment variable reference
- [Architecture Documentation](architecture.md) - Technical architecture details
- [PRD](prd.md) - Product requirements and design decisions
