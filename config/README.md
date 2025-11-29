# Configuration Directory

This directory contains the application configuration file for the IHE Test Utility.

## Quick Start

1. Copy the example configuration file:
   ```bash
   cp ../examples/config.example.json config.json
   ```

2. Edit `config.json` to customize endpoint URLs, certificate paths, and other settings.

3. Run the utility with your configuration:
   ```bash
   ihe-test-util --config config/config.json csv validate patients.csv
   ```

## Configuration File Location

The default configuration file location is `./config/config.json` (relative to the project root).

You can override this location using the `--config` CLI flag:
```bash
ihe-test-util --config /path/to/custom/config.json <command>
```

## Configuration Structure

The configuration file is a JSON file with the following sections:

### Endpoints
- `pix_add_url`: PIX Add endpoint URL (ITI-8 transaction)
- `iti41_url`: ITI-41 endpoint URL (Provide and Register Document Set-b)

### Certificates
- `cert_path`: Path to certificate file (PEM, PKCS12, or DER format)
- `key_path`: Path to private key file
- `cert_format`: Certificate format (`pem`, `pkcs12`, or `der`)
- `pkcs12_password_env_var`: Environment variable containing PKCS12 password

### Transport
- `verify_tls`: Whether to verify TLS certificates (boolean)
- `timeout_connect`: Connection timeout in seconds (integer)
- `timeout_read`: Read timeout in seconds (integer)
- `max_retries`: Maximum retry attempts (integer)
- `backoff_factor`: Exponential backoff factor for retries (float)

### Logging
- `level`: Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `log_file`: Path to log file
- `redact_pii`: Whether to redact PII from logs (boolean)

## Environment Variable Overrides

Configuration values can be overridden using environment variables with the `IHE_TEST_` prefix:

- `IHE_TEST_PIX_ADD_URL`
- `IHE_TEST_ITI41_URL`
- `IHE_TEST_CERT_PATH`
- `IHE_TEST_KEY_PATH`
- `IHE_TEST_CERT_FORMAT`
- `IHE_TEST_PKCS12_PASSWORD`
- `IHE_TEST_VERIFY_TLS`
- `IHE_TEST_TIMEOUT_CONNECT`
- `IHE_TEST_TIMEOUT_READ`
- `IHE_TEST_MAX_RETRIES`
- `IHE_TEST_BACKOFF_FACTOR`
- `IHE_TEST_LOG_LEVEL`
- `IHE_TEST_LOG_FILE`
- `IHE_TEST_REDACT_PII`

## Configuration Precedence

Configuration values are loaded with the following precedence (highest to lowest):

1. **CLI Arguments** - Flags passed directly to commands
2. **Environment Variables** - `IHE_TEST_*` variables
3. **Configuration File** - Values in `config.json`
4. **Defaults** - Built-in default values

## Security Best Practices

⚠️ **NEVER store sensitive values in configuration files!**

- **DO NOT** put passwords in `config.json`
- **DO NOT** put API keys in `config.json`
- **DO NOT** commit `config.json` with credentials to Git

**Instead:**
- Use environment variables for sensitive values (e.g., `IHE_TEST_PKCS12_PASSWORD`)
- Use `.env` files for local development (not committed to Git)
- Use secrets management systems for production

## Validating Configuration

Use the `config validate` command to check your configuration file:

```bash
ihe-test-util config validate config/config.json
```

This will validate the configuration structure and report any errors.

## Example Configurations

See `../examples/config.example.json` for complete configuration examples including:

- Local development with mock endpoints
- Production environment with real endpoints and certificates
- Testing environment with environment variable overrides

## Troubleshooting

### Configuration file not found

If you see "Config file not found", the utility will use default values. This is normal if you haven't created `config/config.json` yet.

### Malformed JSON

If you see a JSON parse error, check your configuration file syntax:
- Ensure all quotes are properly closed
- Ensure all brackets and braces are balanced
- Remove trailing commas (JSON doesn't allow them)
- Use a JSON validator tool

### Invalid configuration values

If you see validation errors:
- Check that URLs start with `http://` or `https://`
- Check that log levels are one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Check that certificate format is one of: pem, pkcs12, der
- Check that numeric values are valid integers or floats

## Batch Configuration Templates

Pre-configured templates are available for different environments. These templates include batch processing settings, logging levels, and connection configurations optimized for each use case.

### Available Templates

| Template | File | Use Case |
|----------|------|----------|
| Development | `batch-development.json` | Local development with verbose logging |
| Testing | `batch-testing.json` | CI/CD testing with moderate logging |
| Staging | `batch-staging.json` | Pre-production with minimal logging |

### Template Settings Summary

| Setting | Development | Testing | Staging |
|---------|-------------|---------|---------|
| `batch_size` | 10 | 100 | 500 |
| `checkpoint_interval` | 5 | 50 | 100 |
| `fail_fast` | true | false | false |
| `concurrent_connections` | 5 | 10 | 20 |
| `log_level` | DEBUG | INFO | WARNING |

### Using Batch Templates

1. **Copy the appropriate template:**
   ```bash
   cp config/batch-development.json config/config.json
   ```

2. **Customize endpoint URLs** to point to your target environment:
   ```json
   {
     "endpoints": {
       "pix_add_url": "http://your-server/PIXManager",
       "iti41_url": "http://your-server/XDSRepository"
     }
   }
   ```

3. **Run batch processing:**
   ```bash
   ihe-test-util --config config/config.json submit batch patients.csv
   ```

### Batch Configuration Options

#### Batch Section

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `batch_size` | int | 100 | Maximum patients per batch |
| `checkpoint_interval` | int | 50 | Save checkpoint every N patients |
| `fail_fast` | bool | false | Stop on first error |
| `concurrent_connections` | int | 10 | Max concurrent HTTP connections |
| `output_dir` | string | "output" | Base output directory |
| `resume_enabled` | bool | true | Enable checkpoint/resume capability |

#### Operation Logging Section

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `csv_log_level` | string | "INFO" | Log level for CSV operations |
| `pix_add_log_level` | string | "INFO" | Log level for PIX Add transactions |
| `iti41_log_level` | string | "INFO" | Log level for ITI-41 transactions |
| `saml_log_level` | string | "WARNING" | Log level for SAML operations |

#### Templates Section

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ccd_template_path` | string | null | Path to CCD template file |
| `saml_template_path` | string | null | Path to SAML template file |

### Environment Variable Overrides for Batch Settings

Batch configuration values can be overridden using environment variables:

- `IHE_TEST_BATCH_SIZE` - Override batch size
- `IHE_TEST_BATCH_CHECKPOINT_INTERVAL` - Override checkpoint interval
- `IHE_TEST_BATCH_FAIL_FAST` - Override fail-fast setting (true/false)
- `IHE_TEST_BATCH_CONCURRENT_CONNECTIONS` - Override connection limit
- `IHE_TEST_BATCH_OUTPUT_DIR` - Override output directory
- `IHE_TEST_BATCH_RESUME_ENABLED` - Override resume capability (true/false)

### Checkpoint and Resume

The batch processing system supports checkpoint/resume for large batches:

1. **Checkpoints are saved automatically** at the configured interval
2. **To resume a failed batch:**
   ```bash
   ihe-test-util submit batch --resume output/results/checkpoint-{batch_id}.json patients.csv
   ```
3. **Checkpoint files contain:**
   - Last processed patient index
   - Completed patient IDs
   - Failed patient IDs
   - Timestamp

### Output Directory Structure

When batch processing runs, it creates an organized directory structure:

```
output/
├── logs/
│   └── batch-{batch_id}.log      # Main batch processing log
├── documents/
│   └── ccds/
│       └── patient-{id}-ccd.xml  # Generated CCD documents
├── results/
│   ├── batch-{batch_id}-results.json  # Complete results
│   ├── batch-{batch_id}-summary.txt   # Human-readable summary
│   └── checkpoint-{batch_id}.json     # Checkpoint file
└── audit/
    └── audit-{batch_id}.log      # Audit trail
```

## Further Documentation

For detailed configuration documentation, see:
- [Configuration Guide](../docs/configuration-guide.md) - Complete configuration reference
- [Batch Processing Tutorial](../examples/tutorials/06-batch-processing.md) - Step-by-step batch processing guide
- [Example Configuration](../examples/config.example.json) - Commented example file
- [Environment Variables](../.env.example) - Environment variable reference
