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
- `--version` - Display version information
- `--help` - Display help for any command

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

Configuration is managed through:

1. **Environment variables** - `.env` file (create from `.env.example`)
2. **Configuration files** - JSON files in `config/` directory
3. **Command-line arguments** - Override via CLI flags

### Environment Variables

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
# - IHE_PIX_ENDPOINT: PIX Manager endpoint URL
# - IHE_XDS_ENDPOINT: XDS Repository endpoint URL
# - SAML_ISSUER: SAML assertion issuer URI
# - CERTIFICATE_PATH: Path to signing certificate
# - PRIVATE_KEY_PATH: Path to private key
```

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
