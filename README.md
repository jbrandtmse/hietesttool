# IHE Test Utility

A Python-based test utility for IHE (Integrating the Healthcare Enterprise) integration testing, supporting PIX Add (ITI-44) and ITI-41 (Provide and Register Document Set-b) transactions.

## Overview

This utility enables healthcare system integrators to:
- Parse patient demographics from CSV files
- Generate HL7v3 PIX Add messages
- Create personalized CCD (Continuity of Care Document) documents
- Generate and sign SAML 2.0 assertions for secure document submission
- Submit documents via ITI-41 transactions with MTOM attachments
- Test against mock IHE endpoints

## Key Features

- **CSV-driven patient data** - Bulk patient demographics processing
- **PIX Add transaction support** - Patient Identity Source actor implementation
- **ITI-41 document submission** - XDS Document Source actor with MTOM
- **SAML 2.0 assertion signing** - XML digital signatures with X.509 certificates
- **Mock IHE endpoints** - Built-in Flask server for local testing
- **HL7v3 message construction** - Compliant PRPA_IN201301UV02 messages
- **Template-based CCD generation** - Personalized clinical documents
- **Cross-platform compatibility** - Windows, macOS, and Linux support

## Prerequisites

- **Python 3.10 or higher**
- **Git** (for cloning the repository)
- **Virtual environment** (recommended)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ihe-test-utility
```

### 2. Create Virtual Environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the Package

#### Development Mode (Recommended)

```bash
pip install -e .
```

#### Development Mode with Dev Dependencies

```bash
pip install -e .[dev]
```

#### Production Mode

```bash
pip install .
```

### 4. Verify Installation

```bash
ihe-test-util --version
python -c "from ihe_test_util import __version__; print(__version__)"
```

## Quick Start

### Getting Started with the CLI

After installation, the `ihe-test-util` command is available system-wide:

```bash
# Display help and available commands
ihe-test-util --help

# Display version information
ihe-test-util --version
```

### CSV Operations

#### Validating Patient Data

Validate a CSV file containing patient demographics:

```bash
# Basic validation with color-coded output
ihe-test-util csv validate patients.csv

# Export invalid rows to a separate file
ihe-test-util csv validate patients.csv --export-errors invalid_rows.csv

# Output validation results in JSON format for automation
ihe-test-util csv validate patients.csv --json

# Validate with verbose logging for debugging
ihe-test-util --verbose csv validate patients.csv
```

#### Processing Patient Data

Process and display patient demographics from CSV:

```bash
# Process CSV and display patient summary
ihe-test-util csv process patients.csv

# Process with reproducible ID generation (deterministic)
ihe-test-util csv process patients.csv --seed 42

# Process and specify output directory
ihe-test-util csv process patients.csv --output ./output

# Process with verbose logging
ihe-test-util --verbose csv process patients.csv
```

#### CSV File Format

Your CSV file should include these required columns:
- `first_name` - Patient's first name
- `last_name` - Patient's last name
- `dob` - Date of birth (YYYY-MM-DD format)
- `gender` - Gender (M, F, O, U)
- `patient_id_oid` - OID for patient identifier domain

Optional columns:
- `patient_id` - Patient identifier (auto-generated if not provided)
- `mrn` - Medical record number
- `ssn` - Social security number
- `address`, `city`, `state`, `zip` - Address information
- `phone`, `email` - Contact information

Example CSV:
```csv
first_name,last_name,dob,gender,patient_id_oid,patient_id
John,Doe,1980-01-01,M,1.2.3.4,TEST-001
Jane,Smith,1975-05-15,F,1.2.3.4,TEST-002
```

### Running Mock IHE Endpoints

```bash
# Start mock server on default port 5000
python -m ihe_test_util.mock_server.app

# Or use custom port
python -m ihe_test_util.mock_server.app --port 8080
```

### Common CLI Options

- `--verbose` - Enable verbose logging (DEBUG level) for troubleshooting
- `--log-file <path>` - Specify custom log file location (default: ./logs/ihe-test-util.log)
- `--redact-pii` - Redact PII (patient names, SSNs) from logs for compliance
- `--version` - Display version information
- `--help` - Display help for any command

### Logging Configuration

The utility includes comprehensive logging for audit trails and troubleshooting:

```bash
# Use default logging (INFO level, logs to ./logs/ihe-test-util.log)
ihe-test-util csv validate patients.csv

# Enable verbose/debug logging for troubleshooting
ihe-test-util --verbose csv validate patients.csv

# Specify custom log file location
ihe-test-util --log-file /var/log/ihe-test-util.log csv validate patients.csv

# Enable PII redaction for compliance/sharing logs
ihe-test-util --redact-pii csv validate patients.csv

# Combine options for compliance with debug logging
ihe-test-util --verbose --redact-pii --log-file audit.log csv validate patients.csv
```

**Log Features:**
- **Dual output:** Console (INFO+) and file (DEBUG+)
- **Log rotation:** Automatic rotation at 10MB, keeps 5 backup files
- **PII redaction:** Optional redaction of patient names and SSNs
- **Audit trail:** Structured logging for all operations with correlation IDs
- **Environment variable:** Override default log file with `IHE_TEST_LOG_FILE`

For detailed logging documentation, see [docs/logging-guide.md](docs/logging-guide.md).

### Exit Codes

The CLI uses standard exit codes:
- `0` - Success (including validation warnings)
- `1` - Validation errors or processing failures
- `2` - Invalid command-line arguments or file not found

### Troubleshooting

#### File Not Found Errors

If you see "File not found" errors:
1. Verify the file path is correct (use absolute paths if needed)
2. Ensure the file exists in the specified location
3. Check file permissions

#### Validation Errors

If validation fails:
1. Review the error messages for specific issues
2. Use `--export-errors` to identify invalid rows
3. Check the CSV format matches the expected structure
4. Ensure dates are in YYYY-MM-DD format
5. Verify gender values are M, F, O, or U

#### Need More Details?

Use the `--verbose` flag to see detailed logging:
```bash
ihe-test-util --verbose csv validate patients.csv
```

### Python API Examples

For programmatic usage, see the Python API examples:

```bash
# PIX Add transaction example
python examples/hl7v3_message_example.py

# SAML signing example
python examples/signxml_saml_example.py
```

## Project Structure

```
ihe-test-utility/
├── src/ihe_test_util/          # Main package
│   ├── cli/                    # CLI commands
│   ├── csv_parser/             # CSV parsing and validation
│   ├── template_engine/        # CCD template processing
│   ├── ihe_transactions/       # IHE transaction implementations
│   ├── saml/                   # SAML generation and signing
│   ├── transport/              # HTTP/HTTPS client
│   ├── mock_server/            # Flask mock endpoints
│   ├── config/                 # Configuration management
│   ├── logging_audit/          # Logging and audit trail
│   ├── models/                 # Data models
│   └── utils/                  # Utility functions
├── tests/                      # Test suites
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
├── mocks/                      # Mock data and responses
├── templates/                  # CCD and SAML templates
├── examples/                   # Sample scripts
├── config/                     # Configuration files
├── docs/                       # Documentation
└── pyproject.toml             # Project metadata
```

## Configuration

The IHE Test Utility supports flexible configuration through JSON files, environment variables, and command-line flags.

### Configuration Precedence

Configuration values are loaded with the following precedence (highest to lowest):

1. **CLI Arguments** - Flags passed directly to commands (e.g., `--verbose`, `--log-file`)
2. **Environment Variables** - `IHE_TEST_*` prefixed variables
3. **Configuration File** - JSON file (default: `./config/config.json`)
4. **Defaults** - Built-in default values

### Quick Start

1. **Copy the example configuration:**
   ```bash
   cp examples/config.example.json config/config.json
   ```

2. **Edit the configuration file** to match your environment:
   ```json
   {
     "endpoints": {
       "pix_add_url": "http://localhost:8080/pix/add",
       "iti41_url": "http://localhost:8080/iti41/submit"
     },
     "logging": {
       "level": "INFO",
       "log_file": "logs/ihe-test-util.log"
     }
   }
   ```

3. **Use with custom configuration:**
   ```bash
   ihe-test-util --config config/config.json csv validate patients.csv
   ```

### Configuration Sections

**Endpoints** - IHE endpoint URLs:
- `pix_add_url` - PIX Add endpoint (ITI-8)
- `iti41_url` - ITI-41 document submission endpoint

**Certificates** - Certificate and key paths for SAML signing:
- `cert_path` - Path to certificate file (PEM, PKCS12, or DER)
- `key_path` - Path to private key file
- `cert_format` - Certificate format (`pem`, `pkcs12`, or `der`)

**Transport** - HTTP/HTTPS settings:
- `verify_tls` - Whether to verify TLS certificates
- `timeout_connect` - Connection timeout in seconds
- `timeout_read` - Read timeout in seconds
- `max_retries` - Maximum retry attempts
- `backoff_factor` - Exponential backoff factor

**Logging** - Logging configuration:
- `level` - Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `log_file` - Path to log file
- `redact_pii` - Whether to redact PII from logs

### Environment Variables

Override configuration values using environment variables with the `IHE_TEST_` prefix:

```bash
# Create .env file from example
cp .env.example .env

# Set environment variables
export IHE_TEST_PIX_ADD_URL=http://custom-server:8080/pix/add
export IHE_TEST_LOG_LEVEL=DEBUG
export IHE_TEST_REDACT_PII=true
```

**Supported environment variables:**
- `IHE_TEST_PIX_ADD_URL` - Override PIX Add endpoint
- `IHE_TEST_ITI41_URL` - Override ITI-41 endpoint
- `IHE_TEST_CERT_PATH` - Override certificate path
- `IHE_TEST_KEY_PATH` - Override key path
- `IHE_TEST_LOG_LEVEL` - Override log level
- `IHE_TEST_LOG_FILE` - Override log file path
- `IHE_TEST_VERIFY_TLS` - Override TLS verification
- `IHE_TEST_REDACT_PII` - Override PII redaction

### Configuration Validation

Validate your configuration file before using it:

```bash
# Validate configuration file
ihe-test-util config validate config/config.json

# Output:
# ✓ Configuration is valid
#
# Configuration file: config/config.json
# 
# Endpoints:
#   PIX Add URL: http://localhost:8080/pix/add
#   ITI-41 URL:  http://localhost:8080/iti41/submit
# ...
```

### Security Best Practices

⚠️ **NEVER store passwords or sensitive values in configuration files!**

- Use environment variables for sensitive values (e.g., `IHE_TEST_PKCS12_PASSWORD`)
- Never commit configuration files with credentials to Git
- Use `.env` files for local development (add to `.gitignore`)

### Detailed Documentation

For comprehensive configuration documentation, see:
- [Configuration Guide](docs/configuration-guide.md) - Complete configuration reference
- [Configuration Examples](examples/config.example.json) - Commented example file
- [Environment Variables](.env.example) - Environment variable reference
- [Config Directory](config/README.md) - Configuration directory documentation

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src/ihe_test_util --cov-report=html

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
```

### Code Quality

```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type checking with mypy
mypy src/
```

### Development Dependencies

Install development dependencies for testing, linting, and formatting:

```bash
pip install -e .[dev]
```

This includes:
- pytest (testing framework)
- pytest-cov (coverage reporting)
- pytest-mock (mocking utilities)
- black (code formatter)
- ruff (linter)
- mypy (type checker)

## Documentation

- **Architecture** - See [docs/architecture/](docs/architecture/)
- **PRD (Product Requirements)** - See [docs/prd/](docs/prd/)
- **User Stories** - See [docs/stories/](docs/stories/)
- **Spike Findings** - See [docs/spike-findings-*.md](docs/)
- **ADRs (Architecture Decision Records)** - See [docs/architecture/adr-*.md](docs/architecture/)

## Dependencies

### Core Dependencies

- **pandas** - CSV processing and data validation
- **lxml** - XML processing for HL7v3 and templates
- **zeep** - SOAP client with WS-Security
- **click** - CLI framework
- **flask** - Mock IHE endpoints
- **requests** - HTTP/HTTPS transport
- **signxml** - XML signing and canonicalization
- **cryptography** - Certificate handling
- **pydantic** - Data validation and settings
- **python-dotenv** - Environment variable management

See [pyproject.toml](pyproject.toml) for complete dependency list.

## License

[Specify license here]

## Contributing

[Contribution guidelines to be added]

## Support

For issues, questions, or contributions, please [contact information or issue tracker link].

## Acknowledgments

This project implements IHE integration profiles:

**Phase 1 (MVP):**
- **ITI-44** - Patient Identity Feed HL7v3 (PIX Add v3)
- **ITI-41** - Provide and Register Document Set-b

**Phase 2 (Post-MVP):**
- **ITI-45** - PIX Query v3
- **ITI-18** - Registry Stored Query
- **ITI-43** - Retrieve Document Set

For IHE specifications, see: https://profiles.ihe.net/
