# Python Utility for IHE Test Patient Creation and CCD Submission Product Requirements Document (PRD)

## Goals and Background Context

### Goals

- Automate creation of test patient data and HL7 CCD/CCDA documents from CSV demographics
- Enable rapid, scalable IHE transaction testing (PIX Add, ITI-41) with proper SOAP formatting and security
- Provide template-based flexibility for CCD and SAML assertion personalization
- Support comprehensive query/retrieve workflows (PIX Query, XCPD, ITI-18, ITI-43) in post-MVP phases
- Reduce test data preparation time from hours to minutes (10x improvement)
- Achieve 95%+ transaction success rate against IHE endpoints
- Enable batch processing of 100+ patient records in under 5 minutes
- Support both HTTP and HTTPS transport with appropriate security warnings
- Provide mock IHE endpoints for isolated testing without external dependencies
- Deliver a lightweight, local Python utility requiring no containerization or cloud infrastructure

### Background Context

Healthcare interoperability testing for IHE (Integrating the Healthcare Enterprise) profiles requires extensive test patient data and realistic clinical documents. Current approaches are manual, time-consuming, and don't scale—developers spend hours crafting individual SOAP messages and XML documents instead of focusing on core integration logic. This creates testing bottlenecks, increases costs, and risks inadequate test coverage that can lead to failed certifications and delayed production deployments.

This Python utility solves these challenges by automating the entire IHE test patient lifecycle from data creation through submission, query, and retrieval. It reads CSV demographic data, generates personalized HL7 CCD/CCDA documents from user-provided templates, and executes IHE transactions with proper SOAP formatting, SAML assertion signing, and flexible HTTP/HTTPS transport. Unlike expensive commercial tools or complex containerized solutions, this lightweight CLI application runs locally in a standard Python virtual environment and includes built-in mock endpoints for comprehensive testing without external dependencies.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-11-02 | 0.1 | Initial PRD draft | PM |
| 2025-11-03 | 0.2 | Integrated Epic 0 (Technical Validation Spikes) into Epic 1 as Stories 1.1-1.3; renumbered remaining Epic 1 stories to 1.4-1.11 | PO |

## Requirements

### Functional

**FR1**: System shall parse CSV files containing patient demographics (name, DOB, gender, identifiers) and validate required fields with clear error messages for malformed data

**FR2**: System shall auto-generate unique patient IDs when not provided in CSV input

**FR3**: System shall accept user-provided HL7 CCDA/XDSb XML template documents and perform simple string replacement for patient-specific data (names, IDs, dates, OIDs)

**FR4**: System shall generate personalized CCD documents for multiple patients in batch mode

**FR5**: System shall construct HL7v3 PRPA_IN201301UV02 patient registration messages and submit to IHE PIX Add endpoints via SOAP

**FR6**: System shall parse and log PIX Add acknowledgment and error responses

**FR7**: System shall construct SOAP-based ITI-41 (Provide and Register Document Set-b) transactions encapsulating personalized CCDs with proper XDSb metadata

**FR8**: System shall use MTOM (MIME attachment) for all ITI-41 document submissions

**FR9**: System shall support two SAML approaches: (1) user-provided SAML XML templates with runtime value substitution, or (2) programmatic generation of SAML 2.0 assertions

**FR10**: System shall sign SAML assertions with X.509 certificates using XML Signature standards and embed in WS-Security SOAP headers

**FR11**: System shall support HTTP and HTTPS transport configuration via CLI flag or configuration file

**FR12**: System shall display security warnings when HTTP transport is selected

**FR13**: System shall support TLS verification disable for testing environments

**FR14**: System shall provide CLI interface for batch processing with flags for input files, endpoints, certificates, and transport mode

**FR15**: System shall display real-time processing status during batch operations

**FR16**: System shall log full SOAP request/response payloads to local files with timestamps

**FR17**: System shall track batch processing progress with success/failure counts per patient

**FR18**: System shall provide detailed error messages with troubleshooting guidance for transaction failures

**FR19**: System shall include mock PIX Add endpoint that responds with static acknowledgments containing pre-defined identifiers

**FR20**: System shall include mock ITI-41 endpoint that performs simple validation and returns static acknowledgments

**FR21**: System shall support HTTP and HTTPS for mock endpoints with configurable certificates

**FR22**: System shall process PIX Add transactions sequentially before ITI-41 submissions (PIX Add must complete successfully first)

### Non Functional

**NFR1**: System shall process 100 patient records through PIX Add and ITI-41 in under 5 minutes (assuming adequate network performance)

**NFR2**: Individual transaction latency shall be under 3 seconds excluding network time

**NFR3**: Mock endpoints shall support 10+ simultaneous connections

**NFR4**: System shall use memory-efficient streaming for large document processing

**NFR5**: System shall run on Python 3.10+ across Windows, macOS, and Linux platforms

**NFR6**: System shall operate in standard Python virtual environment without requiring Docker or containerization

**NFR7**: System shall support X.509 certificates in PEM, PKCS12, and DER formats (prioritized in that order)

**NFR8**: System shall enforce TLS 1.2+ when using HTTPS transport

**NFR9**: System shall use XML canonicalization to prevent XML wrapping attacks

**NFR10**: System shall verify SAML signature validity and timestamp freshness

**NFR11**: System shall maintain comprehensive audit logs for compliance purposes

**NFR12**: System shall provide exit codes and structured output suitable for CI/CD integration

**NFR13**: System shall achieve 80%+ unit test coverage

**NFR14**: System shall include integration tests for all IHE transactions

## Technical Assumptions

### Repository Structure: Monorepo

**Decision:** Single repository containing all components (CLI, IHE transactions, mock endpoints, templates, tests)

**Rationale:** 
- Simpler development workflow for single-application project
- Easier version synchronization across components
- Reduced complexity for target users cloning and setting up project
- All dependencies managed in single `pyproject.toml`

### Service Architecture

**Decision:** Modular monolith - single Python package with clear separation of concerns

**Structure:**
```
ihe-test-utility/
├── src/
│   ├── cli/              # Command-line interface (click)
│   ├── csv_parser/       # CSV import and validation (pandas)
│   ├── template_engine/  # CCD and SAML personalization (lxml)
│   ├── ihe_transactions/ # PIX Add, ITI-41 implementations (zeep)
│   ├── saml/            # SAML generation and signing (python-xmlsec)
│   ├── transport/        # HTTP/HTTPS client (requests)
│   └── utils/           # Common utilities, logging
├── mocks/               # Mock IHE endpoints (Flask)
├── templates/           # Example CCD and SAML templates
├── tests/               # Unit and integration tests (pytest)
├── docs/                # Documentation
└── examples/            # Usage examples and sample CSVs
```

**Rationale:**
- Single deployable artifact simplifies distribution
- Clear module boundaries enable isolated testing
- Easier for developers to understand complete codebase
- No network overhead between components
- Straightforward debugging and logging

### Testing Requirements

**Decision:** Full testing pyramid - Unit + Integration + End-to-End testing

**Coverage:**
- **Unit Tests (80%+ coverage):** All modules independently tested
- **Integration Tests:** IHE transaction workflows against mock endpoints
- **End-to-End Tests:** Complete CSV → PIX Add → ITI-41 workflows
- **Mock Endpoint Tests:** Validate mock server responses
- **Manual Testing Guidance:** Documentation for testing against real IHE endpoints (NIST, Gazelle)

**Test Framework:** pytest with pytest-cov for coverage reporting

**CI/CD Integration:** GitHub Actions workflow running full test suite on push/PR

**Rationale:**
- Comprehensive testing critical for healthcare integration reliability
- Mock endpoints enable fast, isolated automated testing
- Manual testing documentation bridges gap to real-world validation
- pytest ecosystem mature and well-documented

### Additional Technical Assumptions and Requests

**Core Dependencies:**
- **Python 3.10+** - Modern language features, type hints, excellent library ecosystem
- **CSV Processing:** `pandas` for robust data manipulation
  - CSV must include OID values for patient identifiers
- **XML Processing:** `lxml` for high-performance XML parsing with simple string replacement
- **SOAP Client:** `zeep` for mature SOAP/WS-Addressing/WS-Security support
- **SAML & Security:** `python-saml` or `pysaml2` for SAML generation, `python-xmlsec` for XML signing
  - SAML tokens assumed to have lifetime sufficient for run duration (no timeout handling in MVP)
- **HTTP Transport:** `requests` library for reliable HTTP/HTTPS with TLS configuration
- **CLI Framework:** `click` for user-friendly command-line interface
- **Logging:** Python `logging` module with detail sufficient for debugging
- **Mock Servers:** `Flask` for lightweight test endpoints

**Certificate Support:**
- Support X.509 certificates and private keys in priority order: PEM, PKCS12, DER
- Certificate/key storage via environment variables or local filesystem (OS keychain integration deferred to Phase 2)

**Configuration:**
- JSON format for endpoint and credential configuration (prioritize simplicity over flexibility)
- Environment variables for sensitive data (endpoints, certificates, keys)

**Transaction Processing:**
- Sequential processing model (no multi-threading in MVP)
- PIX Add must complete successfully before ITI-41 submission
- MTOM mandatory for all ITI-41 document submissions
- Log-based batch output (no progress bar UI for MVP)

**Security Requirements:**
- XML canonicalization to prevent XML wrapping attacks
- TLS 1.2+ enforcement when using HTTPS
- SAML signature and timestamp validation
- Comprehensive audit logging for compliance

**Platform & Deployment:**
- Cross-platform support: Windows, macOS, Linux
- Standard Python virtual environment (no Docker/containerization requirement)
- Distribute via PyPI and/or GitHub releases
- Installation via `pip install ihe-test-utility`
- Optional Dockerfile provided for users who prefer containerization (but not required)

## Epic List

**Epic 1: Foundation & CSV Processing**
Establish project infrastructure through technical validation spikes, then build Python package structure, CSV demographic data import with validation and ID generation, and basic CLI for CSV processing operations. This epic begins with focused technical spikes to validate critical architectural decisions (SOAP/MTOM, XML signing, HL7v3 messaging) before proceeding with foundation implementation.

**Epic 2: Mock IHE Endpoints**
Create Flask-based mock PIX Add and ITI-41 endpoints with HTTP/HTTPS support, including CLI commands to start/stop/configure mock servers for isolated testing.

**Epic 3: Template Engine & CCD Personalization**
Implement XML template processing with string replacement for CCD personalization, batch generation from CSV demographics, and CLI for template processing operations.

**Epic 4: SAML Generation & XML Signing**
Implement dual SAML approach (template-based and programmatic) with X.509 certificate signing, WS-Security header embedding, and CLI for SAML generation and testing.

**Epic 5: PIX Add Transaction Implementation**
Build HL7v3 PRPA_IN201301UV02 message construction, SOAP-based submission to PIX Add endpoints with acknowledgment parsing/logging, and CLI for patient registration workflows.

**Epic 6: ITI-41 Document Submission & Complete Workflow**
Implement ITI-41 Provide and Register Document Set-b transaction with MTOM support, XDSb metadata, integration with PIX Add, and complete CLI for end-to-end patient submission workflows with batch processing and configuration management.

**Epic 7: Integration Testing & Documentation**
Implement comprehensive test suite (unit, integration, end-to-end), CI/CD pipeline with GitHub Actions, and complete user documentation with examples and troubleshooting guides.

## Epic 1: Foundation & CSV Processing

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

## Epic 2: Mock IHE Endpoints

**Epic Goal:** Create Flask-based mock PIX Add and ITI-41 endpoints with HTTP/HTTPS support, enabling isolated testing and development without external dependencies. This epic delivers critical infrastructure that allows developers to test IHE transactions locally, accelerating development velocity and reducing dependency on external test environments.

### Story 2.1: Flask Mock Server Foundation

**As a** developer,
**I want** a Flask-based mock server framework with HTTP/HTTPS support,
**so that** I can simulate IHE endpoints locally for testing.

**Acceptance Criteria:**

1. Flask application created in `mocks/` directory with modular structure
2. Server supports both HTTP and HTTPS with configurable port (defaults: HTTP 8080, HTTPS 8443)
3. Self-signed certificate generation script provided for HTTPS testing
4. Server configuration loaded from JSON file or environment variables
5. Health check endpoint (`/health`) returns server status and configuration summary
6. Request logging captures all incoming SOAP requests with timestamps
7. Response headers include appropriate SOAP/XML content-type
8. Server handles graceful shutdown with cleanup
9. Error handling returns proper SOAP fault messages for malformed requests
10. Unit tests verify HTTP/HTTPS operation, configuration loading, health check

### Story 2.2: Mock PIX Add Endpoint Implementation

**As a** developer,
**I want** a mock PIX Add endpoint that simulates patient registration,
**so that** I can test PIX Add transaction logic without external dependencies.

**Acceptance Criteria:**

1. Endpoint implements `/pix/add` route accepting SOAP requests
2. Validates incoming SOAP envelope structure (basic validation, not deep semantic)
3. Extracts patient identifiers and demographics from HL7v3 PRPA_IN201301UV02 messages
4. Returns static acknowledgment (MCCI_IN000002UV01) with pre-configured patient ID in response
5. Acknowledgment contains success status code and echoes back patient identifiers
6. Invalid SOAP structure returns SOAP fault with error description
7. Request/response pairs logged to `mocks/logs/pix-add.log` with timestamps
8. Configurable response delays simulate network latency (default 0ms, max 5000ms)
9. Response includes correlation IDs for request tracking
10. Unit and integration tests verify SOAP handling, validation, acknowledgments

### Story 2.3: Mock ITI-41 Endpoint Implementation

**As a** developer,
**I want** a mock ITI-41 endpoint that simulates document submission,
**so that** I can test document submission logic without external XDSb repositories.

**Acceptance Criteria:**

1. Endpoint implements `/iti41/submit` route accepting SOAP with MTOM
2. Validates incoming SOAP envelope and MTOM attachment structure
3. Extracts document metadata from XDSb Provide and Register transaction
4. Validates presence of CCD document in MTOM attachment
5. Returns static Registry Response with success status and document unique ID
6. Response includes submission set unique ID and document entry unique IDs
7. Invalid structure or missing attachments return appropriate SOAP faults
8. Documents and metadata logged to `mocks/logs/iti41-submissions/` directory
9. Submitted documents optionally saved to `mocks/data/documents/` for inspection
10. Unit and integration tests verify MTOM handling, metadata extraction, responses

### Story 2.4: Mock Server CLI Commands

**As a** developer,
**I want** CLI commands to manage mock servers,
**so that** I can easily start/stop/configure mock endpoints during testing.

**Acceptance Criteria:**

1. CLI command `mock start` launches mock server (HTTP by default)
2. Option `--https` enables HTTPS mode with certificate configuration
3. Option `--port <port>` specifies custom port (default 8080 for HTTP, 8443 for HTTPS)
4. Option `--config <file>` loads custom mock server configuration
5. Command `mock stop` gracefully shuts down running mock server
6. Command `mock status` displays running status, endpoints, port, protocol
7. Command `mock logs` displays recent mock server logs with filtering options
8. Server runs in background with PID file for management
9. Clear console output shows server URL, available endpoints, and status
10. Help documentation includes usage examples for common scenarios

### Story 2.5: Mock Endpoint Configuration & Customization

**As a** QA engineer,
**I want** to customize mock endpoint responses and behavior,
**so that** I can test various scenarios including failures and edge cases.

**Acceptance Criteria:**

1. Configuration file (`mocks/config.json`) defines response templates and behavior
2. Configurable response delay per endpoint (simulate network latency)
3. Configurable success/failure rates (e.g., 10% failure rate for testing error handling)
4. Custom SOAP fault messages for different error scenarios
5. Pre-defined patient IDs and document IDs used in acknowledgments
6. Toggle for strict vs. lenient validation modes
7. Configuration hot-reload without server restart
8. Example configurations provided for common test scenarios
9. Configuration validation on load with clear error messages
10. Documentation explains all configuration options with examples

### Story 2.6: Mock Server Documentation & Examples

**As a** new user,
**I want** comprehensive mock server documentation,
**so that** I can quickly set up local testing environments.

**Acceptance Criteria:**

1. Mock server documentation created in `docs/mock-servers.md`
2. Quick start guide with step-by-step server setup and basic usage
3. Example SOAP requests for PIX Add and ITI-41 included in `examples/`
4. Troubleshooting guide for common issues (port conflicts, certificate errors)
5. Documentation covers HTTP vs HTTPS setup and when to use each
6. Configuration reference documents all options with defaults
7. Examples show integration with main utility CLI commands
8. Security warnings about using self-signed certificates
9. Guide for running mock servers in CI/CD pipelines
10. Performance considerations and limitations documented

## Epic 3: Template Engine & CCD Personalization

**Epic Goal:** Implement XML template processing with string replacement for CCD personalization, enabling batch generation of personalized clinical documents from CSV demographics. This epic delivers the core document generation capability that transforms patient data into valid HL7 CCDA documents.

### Story 3.1: XML Template Loader & Validator

**As a** developer,
**I want** to load and validate XML template files,
**so that** I can ensure templates are well-formed before personalization.

**Acceptance Criteria:**

1. Template loader accepts file path to XML template
2. XML parsing using `lxml` library validates well-formed XML structure
3. Template validation checks for required placeholder syntax (e.g., `{{field_name}}`)
4. Loader extracts and catalogs all placeholders found in template
5. Validation reports missing required placeholders for CCD documents
6. Support for both file paths and template string input
7. Clear error messages for malformed XML with line numbers
8. Template encoding detection and normalization to UTF-8
9. Loaded templates cached for reuse in batch operations
10. Unit tests cover valid templates, malformed XML, missing placeholders, encoding issues

### Story 3.2: String Replacement Engine

**As a** developer,
**I want** a string replacement engine for personalizing XML templates,
**so that** I can generate patient-specific documents from demographics.

**Acceptance Criteria:**

1. Replacement engine accepts template and dictionary of field values
2. All placeholder instances (`{{field_name}}`) replaced with corresponding values
3. Missing values in dictionary trigger clear error or use configurable default
4. Special character escaping for XML (e.g., &, <, >, quotes)
5. Date formatting applied automatically for date fields (configurable format)
6. OID values properly inserted for patient identifiers
7. Whitespace and indentation preserved from original template
8. Support for nested placeholders and conditional sections
9. Replacement operation efficient for batch processing (100+ patients)
10. Unit tests verify replacement accuracy, escaping, error handling, performance

### Story 3.3: CCD Template Personalization

**As a** healthcare integration developer,
**I want** to personalize CCD templates with patient demographics from CSV,
**so that** I can generate valid clinical documents for testing.

**Acceptance Criteria:**

1. Personalization accepts CCD template and pandas DataFrame row
2. Maps CSV columns to CCD template placeholders automatically
3. Required CCD fields populated: patient name, DOB, gender, identifiers
4. Optional fields populated when available: address, contact info, MRN
5. Generated CCD includes proper HL7 CCDA XML structure and namespaces
6. Document creation timestamp automatically inserted
7. Unique document IDs generated for each personalized CCD
8. Personalized CCDs validated as well-formed XML before output
9. Batch mode personalizes templates for all rows in DataFrame
10. Integration test generates CCDs from sample CSV and validates output

### Story 3.4: Template Library & Examples

**As a** new user,
**I want** example CCD templates and documentation,
**so that** I can understand template structure and create my own.

**Acceptance Criteria:**

1. Sample CCD template provided in `templates/ccd-template.xml`
2. Template includes common clinical sections (demographics, medications, problems, allergies)
3. All required placeholders clearly marked and documented
4. Template follows HL7 CCDA R2.1 structure and namespaces
5. Minimal CCD template provided for simplest use case
6. Template documentation in `docs/ccd-templates.md` explains structure
7. Placeholder reference lists all supported fields and formats
8. Examples show how to add custom sections to templates
9. Template validation checklist helps users verify custom templates
10. Quick start guide walks through creating first personalized CCD

### Story 3.5: Template Processing CLI

**As a** developer,
**I want** CLI commands for template processing,
**so that** I can generate CCDs from the command line.

**Acceptance Criteria:**

1. CLI command `template validate <file>` validates template structure and placeholders
2. Command `template process <template> <csv>` generates personalized CCDs
3. Option `--output <dir>` specifies output directory for generated CCDs
4. Option `--format <format>` controls output naming (e.g., `{patient_id}.xml`)
5. Batch processing displays progress for large CSV files
6. Generated CCDs saved with meaningful names based on patient identifiers
7. Summary report shows: total patients, CCDs generated, errors
8. Option `--validate-output` performs XML validation on generated CCDs
9. Error handling reports which patients failed with specific reasons
10. CLI output suitable for scripting and automation

## Epic 4: SAML Generation & XML Signing

**Epic Goal:** Implement dual SAML approach (template-based and programmatic) with X.509 certificate signing and WS-Security header embedding. This epic delivers the security infrastructure required for authenticated IHE transactions.

### Story 4.1: Certificate Management & Loading

**As a** developer,
**I want** to load and manage X.509 certificates for signing,
**so that** I can create signed SAML assertions for authenticated transactions.

**Acceptance Criteria:**

1. Certificate loader supports PEM, PKCS12, and DER formats (prioritized in that order)
2. Private key loading with optional password protection
3. Certificate and key loaded from file paths or environment variables
4. Certificate validation checks: expiration, key usage, validity period
5. Clear error messages for invalid certificates, mismatched keys, expired certs
6. Certificate information extraction: subject, issuer, expiration date, key size
7. Support for certificate chains (root, intermediate, leaf)
8. Certificate and key cached in memory for reuse (not persisted to disk)
9. Security warning logged when certificate near expiration (< 30 days)
10. Unit tests verify loading all formats, validation, error handling

### Story 4.2: Template-Based SAML Generation

**As a** developer,
**I want** to personalize SAML assertion templates with runtime values,
**so that** I can use organization-provided SAML templates.

**Acceptance Criteria:**

1. SAML template loader accepts XML template file
2. Template placeholders for common SAML fields: subject, issuer, audience, attributes
3. Timestamp fields automatically populated: IssueInstant, NotBefore, NotOnOrAfter
4. Unique assertion ID generated for each SAML assertion
5. User attributes injected from configuration or runtime parameters
6. Template validation ensures required SAML 2.0 structure present
7. Personalized SAML ready for signing (canonicalized XML)
8. Support for multiple assertion templates for different use cases
9. Example SAML template provided in `templates/saml-template.xml`
10. Unit tests verify personalization, timestamp generation, ID uniqueness

### Story 4.3: Programmatic SAML Generation

**As a** developer,
**I want** to generate SAML assertions programmatically,
**so that** I don't need pre-defined templates for standard scenarios.

**Acceptance Criteria:**

1. SAML generator creates SAML 2.0 assertion from parameters
2. Required parameters: subject, issuer, audience
3. Optional parameters: attributes, conditions, validity duration
4. Generated assertion follows SAML 2.0 specification structure
5. Assertion includes AuthnStatement with timestamp
6. Configurable assertion validity period (default 5 minutes)
7. Support for custom attribute statements
8. Generated SAML properly formatted and canonicalized for signing
9. Integration with certificate management for issuer identity
10. Unit tests verify SAML structure, validity periods, attribute handling

### Story 4.4: XML Signature Implementation

**As a** developer,
**I want** to sign SAML assertions using XML signatures,
**so that** I can create authenticated assertions for IHE transactions.

**Acceptance Criteria:**

1. XML signing using `python-xmlsec` library
2. Signature algorithm configurable (default RSA-SHA256)
3. XML canonicalization (C14N) applied before signing to prevent tampering
4. Signature includes KeyInfo with certificate reference
5. Signed SAML assertion validates against XML signature specification
6. Signature verification function validates signed assertions
7. Clear error messages for signing failures, invalid keys, corrupted XML
8. Timestamp freshness validated when verifying signatures
9. Performance optimization for batch signing operations
10. Unit tests verify signing, verification, canonicalization, error cases

### Story 4.5: WS-Security Header Construction

**As a** developer,
**I want** to embed signed SAML in WS-Security SOAP headers,
**so that** I can create authenticated SOAP requests for IHE transactions.

**Acceptance Criteria:**

1. WS-Security header builder accepts signed SAML assertion
2. Proper WS-Security namespace and structure applied
3. SAML embedded in `<wsse:Security>` header element
4. Timestamp element added to WS-Security header
5. Header positioning correct for SOAP envelope (first child of SOAP:Header)
6. Support for additional WS-Security tokens if needed
7. Generated header validates against WS-Security specification
8. Integration with SOAP client (zeep) for header injection
9. Example SOAP envelope with WS-Security header in documentation
10. Unit and integration tests verify header structure, SOAP integration

### Story 4.6: SAML CLI & Testing Tools

**As a** developer,
**I want** CLI commands for SAML generation and testing,
**so that** I can test SAML workflows independently.

**Acceptance Criteria:**

1. CLI command `saml generate` creates SAML assertion from parameters
2. Option `--template <file>` uses template-based generation
3. Option `--programmatic` uses programmatic generation with parameters
4. Option `--sign` signs assertion with specified certificate
5. Option `--output <file>` saves SAML assertion to file
6. Command `saml verify <file>` validates SAML structure and signature
7. Certificate information displayed when verifying signed assertions
8. Command `saml demo` generates sample WS-Security SOAP envelope
9. Clear output shows SAML structure, validity period, signature status
10. Documentation includes examples for common SAML scenarios

## Epic 5: PIX Add Transaction Implementation

**Epic Goal:** Build HL7v3 PRPA_IN201301UV02 message construction and SOAP-based submission to PIX Add endpoints with acknowledgment parsing and logging. This epic delivers the first complete IHE transaction workflow, enabling patient registration.

### Story 5.1: HL7v3 Message Builder Foundation

**As a** developer,
**I want** to build HL7v3 message structures programmatically,
**so that** I can construct valid PIX Add messages.

**Acceptance Criteria:**

1. Message builder creates HL7v3 XML structure with proper namespaces
2. Support for HL7v3 PRPA_IN201301UV02 message type
3. Required elements populated: message ID, creation time, sender, receiver
4. Patient identifier construction with root OID and extension
5. Patient demographics mapped from parsed CSV data
6. Administrative gender coded values (M, F, O, U) mapped to HL7 codes
7. Birth time formatted in HL7 TS format (YYYYMMDDHHmmss)
8. Message control ID generation (unique per message)
9. XML output properly formatted and indented for readability
10. Unit tests verify message structure, required elements, HL7 conformance

### Story 5.2: PIX Add SOAP Client

**As a** developer,
**I want** a SOAP client for PIX Add transactions,
**so that** I can submit patient registration messages to IHE endpoints.

**Acceptance Criteria:**

1. SOAP client implementation using `zeep` library
2. PIX Add endpoint URL configurable via configuration file
3. HTTP and HTTPS transport support with TLS 1.2+ enforcement
4. Security warning displayed when HTTP transport used
5. WS-Addressing headers included in SOAP envelope (Action, MessageID, To)
6. Signed SAML assertion embedded in WS-Security header
7. Complete SOAP request logged to audit file before transmission
8. Request timeout configurable (default 30 seconds)
9. Network error handling with retry logic (configurable retries, default 3)
10. Unit tests with mock SOAP server verify client behavior

### Story 5.3: PIX Add Acknowledgment Parsing

**As a** developer,
**I want** to parse PIX Add acknowledgment responses,
**so that** I can determine transaction success and extract patient identifiers.

**Acceptance Criteria:**

1. Acknowledgment parser handles HL7v3 MCCI_IN000002UV01 response messages
2. Response validation checks for proper HL7v3 structure and namespaces
3. Acknowledgment status extracted: success (AA), error (AE), rejected (AR)
4. Patient identifiers extracted from acknowledgment when present
5. Error messages and details extracted for failed transactions
6. Query continuation information extracted if present
7. Response correlation with request via message ID
8. Parsed response data returned as structured dictionary
9. Full SOAP response logged to audit file after reception
10. Unit tests verify parsing success, error, and malformed responses

### Story 5.4: PIX Add Workflow Integration

**As a** healthcare integration developer,
**I want** end-to-end PIX Add workflow from CSV to acknowledgment,
**so that** I can register patients with a single command.

**Acceptance Criteria:**

1. Workflow orchestrates: CSV parsing → HL7v3 message building → SAML signing → SOAP submission → acknowledgment parsing
2. Sequential processing for multiple patients (per technical requirements)
3. Success/failure status tracked per patient with detailed logging
4. Patient registration summary displayed: total patients, successful, failed
5. Failed registrations include error details and suggested remediation
6. Registered patient identifiers saved to output file for downstream use
7. Workflow halts on critical errors (endpoint unreachable, certificate invalid)
8. Non-critical errors (single patient failure) continue processing remaining patients
9. Comprehensive audit log captures complete workflow execution
10. Integration test verifies complete workflow against mock PIX Add endpoint

### Story 5.5: PIX Add Error Handling & Resilience

**As a** developer,
**I want** robust error handling for PIX Add transactions,
**so that** transient failures don't halt batch processing.

**Acceptance Criteria:**

1. Network errors trigger configurable retry logic with exponential backoff
2. SOAP faults parsed and logged with detailed error information
3. HL7 application-level errors (AE, AR status) handled gracefully
4. Certificate errors (expired, invalid) halt processing with clear guidance
5. Endpoint unreachable errors suggest troubleshooting steps
6. Malformed response errors logged with raw response for debugging
7. Timeout errors include timing information and retry status
8. Error categorization: transient (retry), permanent (skip), critical (halt)
9. Error summary report shows categories and frequencies
10. Unit tests simulate various error scenarios and verify handling

### Story 5.6: PIX Add CLI Commands

**As a** healthcare integration developer,
**I want** CLI commands for PIX Add operations,
**so that** I can register patients from the terminal.

**Acceptance Criteria:**

1. CLI command `pix-add register <csv>` registers patients from CSV file
2. Option `--endpoint <url>` specifies PIX Add endpoint (overrides config)
3. Option `--cert <path>` specifies certificate for SAML signing
4. Option `--http` enables HTTP transport (with security warning)
5. Option `--output <file>` saves registration results to JSON file
6. Real-time status display shows progress through patient list
7. Color-coded output: green (success), red (failed), yellow (warning)
8. Summary report displays success rate and error breakdown
9. Option `--dry-run` validates without actually submitting
10. Detailed help documentation with usage examples

## Epic 6: ITI-41 Document Submission & Complete Workflow

**Epic Goal:** Implement ITI-41 Provide and Register Document Set-b transaction with MTOM support, XDSb metadata, and integration with PIX Add to deliver complete end-to-end patient submission workflow with batch processing capabilities.

### Story 6.1: XDSb Metadata Construction

**As a** developer,
**I want** to construct XDSb metadata for document submissions,
**so that** I can create valid ITI-41 transactions.

**Acceptance Criteria:**

1. Metadata builder creates ProvideAndRegisterDocumentSetRequest structure
2. Submission set metadata with unique ID, timestamp, source ID
3. Document entry metadata with unique ID, MIME type, hash, size
4. Patient identifier mapping from PIX Add registration results
5. Document classification codes (classCode, typeCode, formatCode) configurable
6. Author information populated from configuration or defaults
7. Metadata associations between submission set and document entries
8. XDSb slot elements for custom metadata attributes
9. Unique IDs generated using UUID or OID-based schemes
10. Unit tests verify metadata structure, required elements, XDSb conformance

### Story 6.2: MTOM Attachment Handling

**As a** developer,
**I want** to attach CCD documents using MTOM,
**so that** I can submit large documents efficiently.

**Acceptance Criteria:**

1. MTOM attachment creation for CCD XML documents
2. Content-ID generation and reference in metadata
3. Base64 encoding applied for binary transport
4. Document hash (SHA256) calculation for integrity verification
5. Document size calculation and inclusion in metadata
6. Multiple document support for future extensibility
7. MTOM packaging with proper MIME multipart boundaries
8. Memory-efficient streaming for large documents (per NFR4)
9. MTOM structure validation before transmission
10. Unit tests verify MTOM packaging, hash calculation, size accuracy

### Story 6.3: ITI-41 SOAP Client Implementation

**As a** developer,
**I want** a SOAP client for ITI-41 transactions,
**so that** I can submit documents to XDSb repositories.

**Acceptance Criteria:**

1. SOAP client implementation using `zeep` with MTOM plugin
2. ITI-41 endpoint URL configurable via configuration file
3. HTTP and HTTPS transport support with TLS 1.2+ enforcement
4. WS-Addressing headers included (Action, MessageID, To, ReplyTo)
5. Signed SAML assertion embedded in WS-Security header
6. Complete SOAP request with MTOM attachment logged to audit file
7. Request timeout configurable (default 60 seconds for large documents)
8. Network error handling with retry logic for transient failures
9. Response correlation with request via message ID
10. Integration test submits CCD to mock ITI-41 endpoint

### Story 6.4: Registry Response Parsing

**As a** developer,
**I want** to parse ITI-41 registry responses,
**so that** I can determine submission success and extract document identifiers.

**Acceptance Criteria:**

1. Response parser handles RegistryResponse from XDSb repository
2. Response status extraction: Success, Failure, PartialSuccess
3. Document unique IDs extracted from successful submissions
4. Error list parsed for failed or partial success responses
5. Error codes and context information extracted and logged
6. Submission set unique ID extracted from response
7. Response correlation with request via submission set ID
8. Structured response data returned for downstream processing
9. Full SOAP response logged to audit file
10. Unit tests verify parsing success, failure, and partial success responses

### Story 6.5: PIX Add + ITI-41 Integration Workflow

**As a** healthcare integration developer,
**I want** complete workflow from CSV to document submission,
**so that** I can create and submit test patients with one command.

**Acceptance Criteria:**

1. Workflow orchestrates: CSV → CCD generation → PIX Add → ITI-41 submission
2. PIX Add must complete successfully before ITI-41 (per FR22)
3. Patient identifiers from PIX Add acknowledgment used in ITI-41 metadata
4. Sequential processing maintains patient registration order
5. Per-patient workflow status tracking: CSV parsed, CCD generated, PIX Add success, ITI-41 success
6. Failed PIX Add registration skips ITI-41 for that patient
7. Complete workflow results saved to JSON output file
8. Summary report shows pipeline metrics: patients processed, PIX Add success rate, ITI-41 success rate
9. Workflow audit log captures all operations with timing information
10. End-to-end integration test verifies complete workflow against mock endpoints

### Story 6.6: Batch Processing & Configuration Management

**As a** QA engineer,
**I want** batch processing with comprehensive configuration,
**so that** I can efficiently test large patient datasets.

**Acceptance Criteria:**

1. Batch mode processes entire CSV file without manual intervention
2. Configuration file consolidates all settings: endpoints, certificates, templates, transport
3. Environment variable overrides for sensitive values (per technical requirements)
4. Processing checkpoint/resume capability for very large batches
5. Concurrent connection limit to mock endpoints (respects NFR3: 10+ connections)
6. Configurable logging verbosity per operation type
7. Batch processing statistics: throughput, average latency, error rates
8. Output directory organization: logs/, documents/, results/, audit/
9. Batch configuration templates for common scenarios (development, testing, staging)
10. Documentation covers batch processing best practices and performance tuning

### Story 6.7: Complete Workflow CLI

**As a** healthcare integration developer,
**I want** a single CLI command for complete patient submission,
**so that** I can execute end-to-end workflow easily.

**Acceptance Criteria:**

1. CLI command `submit <csv>` executes complete workflow (PIX Add + ITI-41)
2. Option `--ccd-template <file>` specifies CCD template to use
3. Option `--config <file>` loads complete workflow configuration
4. Option `--pix-only` executes only PIX Add registration
5. Option `--iti41-only` executes only ITI-41 (requires prior PIX Add results)
6. Real-time progress display with patient count and success rates
7. Color-coded status output with detailed error reporting
8. Option `--output <dir>` specifies output directory for all artifacts
9. Final summary report with breakdown by workflow stage
10. Comprehensive help documentation with examples for all scenarios

## Epic 7: Integration Testing & Documentation

**Epic Goal:** Implement comprehensive test suite (unit, integration, end-to-end), CI/CD pipeline with GitHub Actions, and complete user documentation to ensure production readiness and enable user success.

### Story 7.1: Unit Test Suite Completion

**As a** developer,
**I want** comprehensive unit test coverage,
**so that** I can confidently refactor and extend the codebase.

**Acceptance Criteria:**

1. Unit tests for all modules: csv_parser, template_engine, ihe_transactions, saml, transport, utils, cli
2. Test coverage measured using pytest-cov plugin
3. Target 80%+ coverage achieved (per NFR13)
4. Test fixtures for common test data: sample CSVs, templates, certificates, SOAP messages
5. Mocking used for external dependencies (file I/O, network calls)
6. Parametrized tests cover multiple scenarios efficiently
7. Test organization mirrors source code structure
8. Fast execution: complete unit suite runs in < 2 minutes
9. Coverage report generated in HTML and terminal formats
10. CI pipeline fails if coverage drops below 75%

### Story 7.2: Integration Test Suite

**As a** QA engineer,
**I want** integration tests for IHE transaction workflows,
**so that** I can verify component interactions work correctly.

**Acceptance Criteria:**

1. Integration tests use mock IHE endpoints for all transactions
2. Test scenarios: CSV → PIX Add, CSV → CCD generation, PIX Add + ITI-41 workflow
3. Mock endpoints started/stopped automatically by test fixtures
4. Tests verify SOAP message structure, SAML embedding, MTOM attachments
5. Acknowledgment and response parsing tested with realistic mock responses
6. Error scenarios tested: endpoint unavailable, invalid certificates, malformed responses
7. Certificate and key loading tested with real PEM/PKCS12/DER files
8. Configuration loading and precedence tested (CLI > env > config > defaults)
9. Logging and audit trail verified in integration scenarios
10. Integration suite runs in < 5 minutes with clear pass/fail reporting

### Story 7.3: End-to-End Test Suite

**As a** product owner,
**I want** end-to-end tests for complete workflows,
**so that** I can verify the system meets all requirements.

**Acceptance Criteria:**

1. E2E test executes: CSV file → PIX Add → CCD generation → ITI-41 → verify results
2. Test data includes diverse patient demographics (various ages, genders, addresses)
3. Tests verify 100 patient batch completes in < 5 minutes (per NFR1)
4. Success criteria validated: 95%+ transaction success rate (per goals)
5. All generated artifacts verified: CCDs, logs, audit trails, result files
6. Error handling paths tested with intentionally malformed data
7. HTTP and HTTPS transport modes both tested
8. Certificate rotation scenario tested (expired cert handling)
9. Tests runnable against both mock endpoints and external test beds (NIST - manual)
10. E2E suite runs in < 10 minutes with detailed reporting

### Story 7.4: CI/CD Pipeline Implementation

**As a** development team,
**I want** automated CI/CD pipeline,
**so that** code quality is continuously validated.

**Acceptance Criteria:**

1. GitHub Actions workflow configured in `.github/workflows/ci.yml`
2. Pipeline triggers on push to main branch and all pull requests
3. Multi-OS testing: Ubuntu (required), Windows (optional), macOS (optional)
4. Python 3.10, 3.11, 3.12 tested in matrix
5. Pipeline steps: dependencies install, linting (flake8/ruff), unit tests, integration tests
6. Code coverage reported and enforced (minimum 75%)
7. Build artifacts archived: test reports, coverage reports, logs
8. Pipeline status badge added to README
9. Failures send notifications (GitHub checks, optional email/Slack)
10. Pipeline completes in < 15 minutes for fast feedback

### Story 7.5: User Documentation & Guides

**As a** new user,
**I want** comprehensive documentation,
**so that** I can quickly learn and use the utility effectively.

**Acceptance Criteria:**

1. README.md includes: project overview, features, installation, quick start, links to docs
2. Installation guide covers: Python setup, virtual environment, dependency installation, certificate setup
3. Quick start guide: CSV preparation, configuration, first PIX Add, first ITI-41, batch workflow
4. Configuration reference documents all options: endpoints, certificates, transport, logging
5. CSV format specification with field descriptions and validation rules
6. Template guide explains CCD and SAML template creation and customization
7. CLI reference documents all commands with options and examples
8. Troubleshooting guide addresses common issues: network errors, certificate problems, validation failures
9. Architecture documentation explains component interactions and data flow
10. All documentation in Markdown format in `docs/` directory

### Story 7.6: Example Scenarios & Tutorials

**As a** new user,
**I want** practical examples and tutorials,
**so that** I can learn by doing.

**Acceptance Criteria:**

1. Tutorial 1: Simple PIX Add registration with 10 patients
2. Tutorial 2: Generating CCDs from CSV using templates
3. Tutorial 3: Complete workflow (PIX Add + ITI-41) with batch processing
4. Tutorial 4: Setting up and using mock endpoints for development
5. Tutorial 5: Testing against external IHE test bed (NIST)
6. Each tutorial includes: objectives, prerequisites, step-by-step instructions, expected output, troubleshooting tips
7. Sample data files provided for all tutorials in `examples/tutorials/`
8. Video walkthrough or animated GIFs for key workflows (optional but recommended)
9. Advanced scenarios documented: custom templates, error recovery, performance optimization
10. Tutorial completion checklist helps users verify success

## Checklist Results Report

### Executive Summary

**Overall PRD Completeness:** 95% Complete

**MVP Scope Appropriateness:** Just Right - Well-balanced scope focused on core PIX Add and ITI-41 transactions with clear deferral of query/retrieve functionality to Phase 2.

**Readiness for Architecture Phase:** **READY** - The PRD provides comprehensive requirements, clear technical constraints, and well-structured epics ready for architectural design.

**Most Critical Achievement:** Excellent epic and story structure with detailed acceptance criteria (10 per story), clear CLI integration throughout, and comprehensive testing requirements.

### Category Analysis

| Category | Status | Critical Issues |
|----------|--------|-----------------|
| 1. Problem Definition & Context | PASS | None - Clear problem statement, target users, and success metrics |
| 2. MVP Scope Definition | PASS | None - Well-defined MVP boundaries with Phase 2 roadmap |
| 3. User Experience Requirements | PARTIAL | Minor - CLI-focused (appropriate for utility), could expand error message examples |
| 4. Functional Requirements | PASS | None - 22 comprehensive FRs covering all workflows |
| 5. Non-Functional Requirements | PASS | None - 14 NFRs covering performance, security, platform, testing |
| 6. Epic & Story Structure | PASS | None - 7 epics with detailed stories, excellent acceptance criteria |
| 7. Technical Guidance | PASS | None - Comprehensive technical assumptions and technology stack |
| 8. Cross-Functional Requirements | PASS | None - Configuration, integration, operational concerns addressed |
| 9. Clarity & Communication | PASS | None - Well-structured, clear language, ready for handoff |

### Detailed Findings

#### Strengths

1. **Exceptional Story Quality**: Each story includes 10 specific, testable acceptance criteria - exceeds typical PM documentation standards
2. **Technology Stack Clarity**: Specific libraries chosen (pandas, zeep, click, flask) with rationale
3. **Testing Focus**: Comprehensive testing strategy (80%+ unit coverage, integration, E2E, CI/CD)
4. **Scope Discipline**: Clear MVP focus on PIX Add + ITI-41, explicit Phase 2 deferral of query/retrieve
5. **CLI Integration**: Distributed CLI work across epics rather than separate epic (vertical slices)
6. **Mock Endpoints**: Treated as first-class Epic 2 feature, enabling isolated testing
7. **Security**: Comprehensive SAML, XML signing, certificate management requirements
8. **Documentation**: Epic 7 dedicates significant effort to docs, tutorials, examples

#### Minor Improvements (Optional)

1. **User Journey Examples**: Could add 2-3 concrete user journey examples showing complete workflows
2. **Error Message Templates**: Could provide example error messages for common scenarios
3. **Performance Benchmarks**: NFR1 includes network assumption caveat - consider adding baseline metrics
4. **Dockerfile Scope**: Noted as optional but deferred - could clarify in which epic Dockerfile will be added

#### MVP Scope Assessment

**Verdict: Appropriately Scoped**

- **Core Value Delivered**: PIX Add patient registration + ITI-41 document submission
- **Essential Infrastructure**: CSV processing, templates, SAML, mocks all necessary for core workflow
- **Smart Deferrals**: Query/retrieve workflows (PIX Query, XCPD, ITI-18, ITI-43) to Phase 2
- **Testing Investment**: Appropriate for healthcare integration where reliability is critical
- **Timeline Realism**: 7 epics over 3-4 months with part-time allocation is achievable

**Features That Could Be Cut** (if needed):
- Story 1.8 (Sample CSV Templates) - could be simplified
- Story 2.6 (Mock Server Documentation) - could be minimal initially
- Dual SAML approach - could start with template-only, add programmatic later

**No Missing Essential Features Identified**

#### Technical Readiness for Architect

**Assessment: READY**

**Clear Technical Constraints:**
- Python 3.10+, specific libraries identified
- Monorepo structure defined
- Sequential processing (no multi-threading in MVP)
- Certificate format priorities (PEM > PKCS12 > DER)

**Identified Technical Risks:**
- IHE specification complexity (acknowledged in Brief)
- SAML/XML signing complexity (Epic 4 dedicated to this)
- SOAP library maintenance (zeep chosen as most mature)

**Areas for Architect Investigation:**
- HL7v3 message structure details (Epic 5)
- XDSb metadata specifics (Epic 6)
- MTOM implementation with zeep (Epic 6)
- Mock endpoint fidelity requirements (Epic 2)

**Complexity Flags:**
- Epic 4 (SAML & XML Signing) - highest technical complexity
- Epic 5 (PIX Add) - requires deep HL7v3 knowledge
- Epic 6 (ITI-41 with MTOM) - complex SOAP/MTOM handling

### Top Issues by Priority

**BLOCKERS:** None identified

**HIGH:** None identified

**MEDIUM:**
1. Consider adding example error messages for common failure scenarios (helps development)
2. Clarify which epic will include optional Dockerfile (mentioned but not assigned)

**LOW:**
1. Could add 2-3 concrete user journey examples to supplement epic descriptions
2. Could expand accessibility considerations beyond cross-platform (though CLI limits this)

### Recommendations

#### For Product Manager (Before Architect Handoff)

1. **Document Dockerfile Decision**: Add note in Epic 1 or Epic 7 about optional Dockerfile inclusion, or create separate story if desired
2. **Consider Adding**: Brief appendix with 2-3 end-to-end user journey examples showing complete workflows
3. **Review with Stakeholders**: Share Epic structure with development team for sanity check on sizing

#### For Architect (Next Steps)

1. **Research Phase**: 
   - Survey 2-3 IHE test beds (NIST, Gazelle) to validate requirements
   - Prototype zeep library with basic PIX Add transaction
   - Validate MTOM support in zeep

2. **Architecture Document Sections**:
   - Component interaction diagrams (CSV → Template → SAML → SOAP → IHE)
   - HL7v3 message structure details
   - SAML assertion flow
   - Mock endpoint architecture
   - Error handling strategy
   - Logging and audit architecture

3. **Technical Spikes**:
   - XML signing with python-xmlsec (Epic 4 prerequisite)
   - MTOM attachment handling (Epic 6 prerequisite)
   - Template engine performance with 100+ patients (NFR1 validation)

4. **Risk Mitigation**:
   - Early Epic 2 (Mocks) implementation enables testing before external dependencies
   - Incremental epic delivery allows course correction
   - Comprehensive testing catches integration issues early

### Final Decision

✅ **READY FOR ARCHITECT**

The PRD and epic structure are comprehensive, properly scoped, and provide clear guidance for architectural design. The requirements are specific, testable, and well-organized. The MVP scope is appropriate, with smart deferrals to Phase 2. Technical constraints are well-documented, and the epic/story breakdown is detailed enough for AI agent implementation.

**Confidence Level:** High - This PRD meets or exceeds standards for handoff to architecture phase.

**Next Step:** Proceed with architecture document creation using this PRD as the requirements foundation.

## Next Steps

### UX Expert Prompt

*Note: This project is primarily CLI-focused with minimal UI/UX requirements. UX involvement is optional but could provide value for CLI command structure and error message design.*

**Prompt for UX Expert (@ux-expert):**

"Review the Python Utility for IHE Test Patient Creation and CCD Submission PRD (docs/prd.md) and provide recommendations for:

1. CLI command structure and naming conventions for optimal developer experience
2. Error message templates for common failure scenarios (CSV validation errors, network failures, certificate issues)
3. Progress indicators and status reporting for batch operations (text-based, suitable for terminal output)
4. Help text structure and examples for CLI commands

Focus on creating a developer-friendly command-line experience with clear, actionable error messages and intuitive command hierarchies."

### Architect Prompt

**Prompt for Architect (@architect):**

"Create a comprehensive architecture document for the Python Utility for IHE Test Patient Creation and CCD Submission based on the PRD in docs/prd.md and Project Brief in docs/brief.md.

The architecture document should include:

1. **System Architecture Overview** - Component interaction diagrams showing data flow from CSV → Template → SAML → SOAP → IHE endpoints
2. **Module Specifications** - Detailed design for each module (csv_parser, template_engine, saml, ihe_transactions, transport, cli, mocks)
3. **HL7v3 Message Structure** - PIX Add (PRPA_IN201301UV02) and Acknowledgment (MCCI_IN000002UV01) message specifications
4. **XDSb Metadata Structure** - ITI-41 ProvideAndRegisterDocumentSetRequest with MTOM attachment handling
5. **SAML Assertion Architecture** - Dual approach (template-based and programmatic) with XML signing workflow
6. **Mock Endpoint Design** - Flask server architecture for PIX Add and ITI-41 simulation
7. **Error Handling Strategy** - Classification (transient/permanent/critical) and retry logic
8. **Logging & Audit Architecture** - Comprehensive audit trail design with PII redaction
9. **Testing Strategy** - Unit, integration, and E2E testing approach
10. **Deployment Architecture** - PyPI distribution, virtual environment setup, optional Docker support

Key Technical Constraints:
- Python 3.10+, monorepo structure, sequential processing (no multi-threading in MVP)
- Libraries: pandas, lxml, zeep, click, flask, python-xmlsec, requests, pytest
- Certificate priority: PEM > PKCS12 > DER
- Configuration: JSON format with environment variable overrides

Deliverable: Create docs/architecture.md using the architecture template (brownfield-architecture-tmpl.yaml or architecture-tmpl.yaml)."
