# Epic 1: Foundation & CSV Processing

**Epic Goal:** Establish a solid foundation for the IHE test utility by first validating critical technology choices through focused technical spikes (SOAP/MTOM, XML signing, HL7v3), then creating the project structure, implementing CSV demographic data import with validation and ID generation, and providing a basic CLI for CSV processing operations. This epic delivers immediate value by de-risking technical unknowns early and enabling users to import and validate patient demographic data, setting the stage for all subsequent functionality.

### Story 1.1: SOAP/MTOM Integration Spike

**As a** technical lead,
**I want** to validate that zeep library can handle MTOM attachments for ITI-41,
**so that** I can confirm our SOAP library choice before committing to full implementation.

**Acceptance Criteria:**

1. Create minimal PIX Add SOAP message using zeep library
2. Construct basic ITI-41 SOAP envelope with MTOM attachment using zeep
3. Test MTOM attachment with sample CCD document (>10KB)
4. Verify SOAP envelope structure matches IHE ITI-41 specification requirements
5. Confirm Content-ID references work correctly between metadata and attachment
6. Test against mock ITI-41 endpoint and verify successful submission
7. Validate zeep can parse MTOM response from mock endpoint
8. Document any zeep library limitations or configuration requirements discovered
9. Provide code sample demonstrating MTOM attachment handling
10. Make go/no-go recommendation on zeep library with alternatives if needed

**Estimated Duration:** 2-3 days

### Story 1.2: XML Signing Validation Spike

**As a** technical lead,
**I want** to validate python-xmlsec integration for SAML assertion signing,
**so that** I can confirm XML signature implementation before building SAML module.

**Acceptance Criteria:**

1. Generate or obtain test X.509 certificate and private key (PEM format)
2. Create minimal SAML 2.0 assertion XML structure
3. Implement XML canonicalization (C14N) using python-xmlsec
4. Sign SAML assertion with test certificate using RSA-SHA256
5. Verify signed assertion validates correctly with python-xmlsec
6. Test certificate loading from PEM, PKCS12, and DER formats
7. Test with certificate chain (root, intermediate, leaf)
8. Embed signed SAML in WS-Security SOAP header and verify structure
9. Document python-xmlsec installation requirements and dependencies
10. Provide code sample demonstrating complete signing and verification workflow

**Estimated Duration:** 2-3 days

### Story 1.3: HL7v3 Message Construction Spike

**As a** technical lead,
**I want** to validate HL7v3 message construction approach,
**so that** I can confirm we can build spec-compliant PIX Add messages.

**Acceptance Criteria:**

1. Study HL7v3 PRPA_IN201301UV02 message specification structure
2. Build sample PRPA_IN201301UV02 message using lxml
3. Validate message structure against HL7v3 schema (if available)
4. Test patient demographic data insertion (name, DOB, gender, identifiers)
5. Verify correct HL7v3 namespace declarations and prefixes
6. Parse sample MCCI_IN000002UV01 acknowledgment response
7. Extract status code (AA/AE/AR) and patient identifiers from acknowledgment
8. Test against mock PIX Add endpoint and verify acknowledgment parsing
9. Document HL7v3 namespace and structure requirements
10. Provide code sample demonstrating message construction and response parsing

**Estimated Duration:** 2-3 days

### Story 1.4: Project Structure & Dependencies

**As a** developer,
**I want** a well-organized Python project structure with all core dependencies configured,
**so that** I can start building features with a solid foundation and clear module boundaries.

**Acceptance Criteria:**

1. Project follows recommended monorepo structure with `src/`, `tests/`, `mocks/`, `templates/`, `docs/`, and `examples/` directories
2. `pyproject.toml` configured with project metadata, dependencies (pandas, lxml, zeep, click, flask, requests, python-xmlsec), and build system
3. Python 3.10+ specified as minimum version requirement
4. Git repository initialized with `.gitignore` for Python projects (excluding `__pycache__`, `.venv`, `.pytest_cache`, etc.)
5. README.md created with project overview and setup instructions placeholder
6. Virtual environment setup documented in README
7. `src/` directory contains placeholder modules: `cli/`, `csv_parser/`, `template_engine/`, `ihe_transactions/`, `saml/`, `transport/`, `utils/`
8. Each module contains `__init__.py` for Python package structure
9. Project can be installed in development mode via `pip install -e .`
10. All dependencies install successfully on Windows, macOS, and Linux

### Story 1.5: CSV Parser Implementation

**As a** healthcare integration developer,
**I want** to import patient demographics from CSV files with validation,
**so that** I can prepare patient data for IHE transaction testing.

**Acceptance Criteria:**

1. CSV parser accepts file path and reads CSV using pandas
2. Required columns validated: `first_name`, `last_name`, `dob`, `gender`, `patient_id_oid` (OID value required per technical assumptions)
3. Optional columns supported: `patient_id`, `mrn`, `ssn`, `address`, `city`, `state`, `zip`, `phone`, `email`
4. Date of birth (dob) validated and parsed into standard format (YYYY-MM-DD)
5. Gender validated against acceptable values (M, F, O, U)
6. Clear error messages displayed for missing required fields with row numbers
7. Clear error messages displayed for malformed dates or invalid gender values
8. Parser handles UTF-8 encoding and common CSV edge cases (quotes, commas in fields)
9. Parsed data returned as pandas DataFrame for downstream processing
10. Unit tests cover valid CSV, missing required fields, malformed dates, invalid gender, encoding issues

### Story 1.6: Patient ID Auto-Generation

**As a** QA engineer,
**I want** unique patient IDs automatically generated when not provided in CSV,
**so that** I can quickly create test patients without manually assigning IDs.

**Acceptance Criteria:**

1. ID generation triggered when `patient_id` column is empty/missing for a row
2. Generated IDs follow format: `TEST-{UUID}` where UUID is a unique identifier
3. Generated IDs are unique across entire batch within single execution
4. Generated IDs are deterministic when optional seed parameter provided (for reproducible test data)
5. Patient ID OID value from `patient_id_oid` column preserved and associated with generated ID
6. Both provided and generated patient IDs logged in processing output
7. CSV can contain mix of provided and auto-generated IDs
8. Generated ID format documented in user guide
9. Unit tests verify uniqueness, format, and seed-based reproducibility
10. Integration test processes CSV with missing IDs and verifies generation

### Story 1.7: CSV Validation & Error Reporting

**As a** developer,
**I want** comprehensive validation with actionable error messages,
**so that** I can quickly identify and fix data quality issues in my CSV files.

**Acceptance Criteria:**

1. Validation runs before any processing begins
2. All validation errors collected and reported together (not fail-fast on first error)
3. Error messages include: row number, column name, issue description, suggested fix
4. Warning messages displayed for optional fields with questionable values (e.g., future DOB, invalid phone format)
5. Validation summary shows: total rows, valid rows, rows with errors, rows with warnings
6. Invalid rows can be optionally exported to separate error CSV file with error descriptions
7. Validation report includes statistics: duplicate patient IDs, missing OIDs, data type issues
8. Exit code 0 for success, non-zero for validation failures (CI/CD compatible)
9. Detailed troubleshooting guidance in documentation for common validation errors
10. Unit tests cover comprehensive validation scenarios and error message clarity

### Story 1.8: Basic CLI for CSV Operations

**As a** healthcare integration developer,
**I want** a command-line interface for CSV processing,
**so that** I can validate and prepare patient data from the terminal.

**Acceptance Criteria:**

1. CLI framework implemented using `click` library
2. Main command `ihe-test-util` available after installation
3. Subcommand `csv validate <file>` validates CSV and displays report
4. Subcommand `csv process <file>` validates and processes CSV, displaying parsed patient summary
5. Common options: `--output <dir>` for output location, `--verbose` for detailed logging, `--seed <value>` for reproducible ID generation
6. CSV validate command displays color-coded output: green for success, red for errors, yellow for warnings
7. Help text (`--help`) provides clear usage examples for each command
8. Version command `--version` displays utility version from pyproject.toml
9. CSV processing errors display helpful messages and exit with appropriate codes
10. CLI output suitable for both human reading and log file capture

### Story 1.9: Logging & Audit Trail Foundation

**As a** compliance-focused developer,
**I want** comprehensive logging configured from the start,
**so that** all operations are auditable and debugging is straightforward.

**Acceptance Criteria:**

1. Python `logging` module configured with configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
2. Log output to both console (INFO and above) and file (DEBUG and above by default)
3. Log file location configurable via environment variable or CLI flag (default: `./logs/ihe-test-util.log`)
4. Log entries include: timestamp, log level, module name, message
5. Structured logging for key operations: CSV file loaded, validation started/completed, patients processed
6. Log rotation configured to prevent unbounded log file growth (max 10MB per file, keep 5 rotated files)
7. Sensitive data (patient names, SSNs) optionally redacted in logs via `--redact-pii` flag
8. Audit trail captures: operation type, input file, record counts, success/failure status, duration
9. Log format documentation provided for parsing/analysis tools
10. Unit tests verify logging configuration and audit trail entries

### Story 1.10: Configuration File Support

**As a** developer,
**I want** to manage endpoint and certificate configuration via JSON files,
**so that** I don't need to pass numerous CLI flags for every operation.

**Acceptance Criteria:**

1. Configuration file format is JSON (per technical assumptions)
2. Default config file location: `./config/config.json`, overridable via `--config <path>` CLI flag
3. Config supports sections: `endpoints` (PIX Add, ITI-41 URLs), `certificates` (paths to PEM/PKCS12/DER files), `transport` (HTTP/HTTPS settings), `logging` (log level, file path)
4. Environment variables override config file values (precedence: CLI args > env vars > config file > defaults)
5. Sensitive values (certificate passwords, endpoint credentials) loaded from environment variables, not stored in config file
6. Example configuration file provided in `examples/config.example.json` with documentation
7. Configuration validation on load with clear error messages for invalid structure or missing required fields
8. `config validate <file>` CLI command validates configuration without executing operations
9. Configuration schema documented in user guide
10. Unit tests cover config loading, environment variable overrides, validation errors

### Story 1.11: Sample CSV Templates & Examples

**As a** new user,
**I want** sample CSV files and documentation,
**so that** I can quickly understand the expected format and start creating test data.

**Acceptance Criteria:**

1. Sample CSV file created in `examples/patients_sample.csv` with 10 diverse patient records
2. Sample includes all required columns and demonstrates optional columns
3. Sample demonstrates mix of provided patient IDs and empty IDs (for auto-generation testing)
4. Sample includes varied demographics: multiple genders, age ranges, complete and partial addresses
5. CSV column documentation created in `docs/csv-format.md` explaining each field, data types, and validation rules
6. Documentation includes common OID values for testing (e.g., example OIDs for different healthcare organizations)
7. Troubleshooting section in documentation addresses common CSV formatting issues
8. Quick start guide includes step-by-step example using sample CSV file
9. Sample demonstrates UTF-8 encoding and proper handling of special characters in names
10. Additional minimal example CSV (`examples/patients_minimal.csv`) with only required columns for simplest use case
