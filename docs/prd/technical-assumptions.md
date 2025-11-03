# Technical Assumptions

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
