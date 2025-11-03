# Coding Standards

**⚠️ These standards are MANDATORY for AI agents and developers.**

### Core Standards

**Languages & Runtimes:**
- Python 3.10+ (minimum version)
- Type hints required for all function signatures
- Docstrings required for all public functions (Google style)

**Style & Linting:**
- **Formatter:** `black` with default settings (88-character line length)
- **Linter:** `ruff` with project-specific rules
- **Type Checker:** `mypy` in strict mode

**Test Organization:**
- Unit tests in `tests/unit/`, mirror `src/` structure
- Integration tests in `tests/integration/`
- E2E tests in `tests/e2e/`
- Test files named `test_*.py`
- Test functions named `test_*`

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| **Modules** | snake_case | `csv_parser.py` |
| **Classes** | PascalCase | `PatientDemographics` |
| **Functions** | snake_case | `parse_csv()` |
| **Variables** | snake_case | `patient_id` |
| **Constants** | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT` |
| **Private** | Leading underscore | `_internal_function()` |

### Critical Rules

**RULE 1: Never use print() statements**
- **Requirement:** Always use the logging module
- **Rationale:** Enables configurable log levels and audit trails
- **Example:** `logger.info("Processing patient")` not `print("Processing patient")`

**RULE 2: All IHE transactions MUST log complete request/response**
- **Requirement:** Log full SOAP envelopes to audit files
- **Rationale:** Critical for debugging IHE transaction failures
- **Example:** `audit_logger.log_transaction(request_xml, response_xml)`

**RULE 3: Configuration values via Config Manager only**
- **Requirement:** Never access environment variables directly with `os.getenv()`
- **Rationale:** Ensures configuration precedence and validation
- **Example:** `config.get_endpoint("pix_add")` not `os.getenv("PIX_ADD_URL")`

**RULE 4: All file I/O MUST use Path objects**
- **Requirement:** Use `pathlib.Path` not string paths
- **Rationale:** Cross-platform compatibility (Windows/Unix)
- **Example:** `Path("data") / "file.csv"` not `"data/file.csv"`

**RULE 5: Exceptions must include actionable context**
- **Requirement:** Error messages must explain what failed and suggest fixes
- **Rationale:** Improves developer experience and reduces support burden
- **Example:** `raise ValidationError("Invalid gender 'X'. Must be M, F, O, or U.")` not `raise ValidationError("Invalid gender")`

**RULE 6: No bare except clauses**
- **Requirement:** Always catch specific exceptions
- **Rationale:** Prevents hiding bugs and makes error handling explicit
- **Example:** `except TransportError` not `except:`

**RULE 7: Type hints are mandatory**
- **Requirement:** All function signatures must have complete type hints
- **Rationale:** Enables static analysis and catches errors early
- **Example:** `def parse_csv(file_path: Path) -> pd.DataFrame:` not `def parse_csv(file_path):`
