# Source Tree

Based on the PRD's monorepo structure and modular Python package architecture, here's the project folder structure:

```
ihe-test-utility/
├── .github/
│   └── workflows/
│       ├── ci.yml                      # CI pipeline: linting, testing, coverage
│       └── publish.yml                 # PyPI publication workflow
├── src/
│   └── ihe_test_util/
│       ├── __init__.py                 # Package initialization, version
│       ├── __main__.py                 # Entry point for `python -m ihe_test_util`
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py                 # Main CLI entry point (click)
│       │   ├── csv_commands.py         # csv validate, csv process commands
│       │   ├── template_commands.py    # template validate, template process
│       │   ├── saml_commands.py        # saml generate, saml verify
│       │   ├── pix_commands.py         # pix-add register command
│       │   ├── submit_commands.py      # submit command (main workflow)
│       │   └── mock_commands.py        # mock start, mock stop, mock status
│       ├── csv_parser/
│       │   ├── __init__.py
│       │   ├── parser.py               # CSV parsing logic (pandas)
│       │   ├── validator.py            # Demographics validation (pydantic)
│       │   └── id_generator.py         # Patient ID generation
│       ├── template_engine/
│       │   ├── __init__.py
│       │   ├── loader.py               # Template loading and caching
│       │   ├── personalizer.py         # String replacement engine
│       │   └── validators.py           # XML validation
│       ├── ihe_transactions/
│       │   ├── __init__.py
│       │   ├── pix_add.py              # PIX Add message builder and submitter
│       │   ├── iti41.py                # ITI-41 transaction builder and submitter
│       │   ├── soap_client.py          # Zeep SOAP client wrapper
│       │   ├── parsers.py              # Response parsers (acknowledgment, registry)
│       │   └── mtom.py                 # MTOM attachment handling
│       ├── saml/
│       │   ├── __init__.py
│       │   ├── generator.py            # SAML generation (template & programmatic)
│       │   ├── signer.py               # XML signing with python-xmlsec
│       │   ├── verifier.py             # Signature verification
│       │   └── certificate_manager.py  # Certificate loading (PEM/PKCS12/DER)
│       ├── transport/
│       │   ├── __init__.py
│       │   ├── http_client.py          # Requests-based HTTP/HTTPS client
│       │   ├── retry_logic.py          # Exponential backoff retry handler
│       │   └── tls_config.py           # TLS configuration
│       ├── mock_server/
│       │   ├── __init__.py
│       │   ├── app.py                  # Flask application
│       │   ├── pix_add_endpoint.py     # /pix/add mock endpoint
│       │   ├── iti41_endpoint.py       # /iti41/submit mock endpoint
│       │   └── config.py               # Mock server configuration
│       ├── config/
│       │   ├── __init__.py
│       │   ├── manager.py              # Configuration loading and validation
│       │   ├── schema.py               # Pydantic configuration models
│       │   └── defaults.py             # Default configuration values
│       ├── logging_audit/
│       │   ├── __init__.py
│       │   ├── logger.py               # Logging configuration
│       │   ├── audit.py                # Audit trail functions
│       │   └── formatters.py           # Custom log formatters
│       ├── models/
│       │   ├── __init__.py
│       │   ├── patient.py              # PatientDemographics dataclass
│       │   ├── ccd.py                  # CCDDocument dataclass
│       │   ├── saml.py                 # SAMLAssertion dataclass
│       │   ├── transactions.py         # PIXAddMessage, ITI41Transaction
│       │   ├── responses.py            # TransactionResponse dataclass
│       │   └── batch.py                # BatchProcessingResult dataclass
│       └── utils/
│           ├── __init__.py
│           ├── xml_utils.py            # XML helper functions
│           ├── oid_utils.py            # OID validation and formatting
│           ├── date_utils.py           # HL7 date formatting
│           └── exceptions.py           # Custom exception classes
├── mocks/
│   ├── __init__.py
│   ├── data/
│   │   ├── documents/                  # Saved submitted CCDs (optional)
│   │   └── responses/                  # Response templates
│   ├── logs/
│   │   ├── pix-add.log                 # PIX Add mock request logs
│   │   └── iti41-submissions/          # ITI-41 submission logs
│   └── config.json                     # Mock server configuration
├── templates/
│   ├── ccd-template.xml                # Example CCD template
│   ├── ccd-minimal.xml                 # Minimal CCD example
│   ├── saml-template.xml               # Example SAML template
│   └── README.md                       # Template documentation
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Pytest fixtures and configuration
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_csv_parser.py
│   │   ├── test_template_engine.py
│   │   ├── test_saml.py
│   │   ├── test_ihe_transactions.py
│   │   ├── test_transport.py
│   │   ├── test_config.py
│   │   └── test_models.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_pix_add_flow.py        # PIX Add against mock endpoint
│   │   ├── test_iti41_flow.py          # ITI-41 against mock endpoint
│   │   ├── test_mock_server.py         # Mock server behavior
│   │   └── test_certificate_loading.py # Certificate handling
│   ├── e2e/
│   │   ├── __init__.py
│   │   ├── test_complete_workflow.py   # CSV → PIX Add → ITI-41
│   │   └── test_batch_processing.py    # 100 patient batch test
│   └── fixtures/
│       ├── sample_patients.csv         # Test CSV data
│       ├── test_ccd_template.xml       # Test CCD template
│       ├── test_cert.pem               # Test certificate
│       └── test_key.pem                # Test private key
├── examples/
│   ├── config.example.json             # Example configuration file
│   ├── patients_sample.csv             # Sample patient data (10 patients)
│   ├── patients_minimal.csv            # Minimal CSV example
│   └── tutorials/
│       ├── 01-csv-validation.md        # Tutorial: CSV validation
│       ├── 02-ccd-generation.md        # Tutorial: CCD generation
│       ├── 03-pix-add.md               # Tutorial: PIX Add registration
│       ├── 04-complete-workflow.md     # Tutorial: Complete workflow
│       └── 05-mock-endpoints.md        # Tutorial: Using mock endpoints
├── docs/
│   ├── prd.md                          # Product Requirements Document
│   ├── brief.md                        # Project Brief
│   ├── architecture.md                 # This architecture document
│   ├── csv-format.md                   # CSV format specification
│   ├── ccd-templates.md                # CCD template guide
│   ├── saml-guide.md                   # SAML configuration guide
│   ├── mock-servers.md                 # Mock server documentation
│   ├── troubleshooting.md              # Common issues and solutions
│   └── api-reference.md                # API/CLI reference
├── scripts/
│   ├── generate_test_data.py           # Generate test CSV files
│   ├── generate_cert.sh                # Self-signed certificate generation
│   └── setup_dev.sh                    # Development environment setup
├── config/
│   ├── config.json                     # Default configuration
│   └── logging.conf                    # Logging configuration
├── logs/                                # Created at runtime
│   ├── audit/                          # Audit trail logs
│   ├── transactions/                   # Transaction request/response logs
│   └── ihe-test-util.log               # Main application log
├── .env.example                        # Environment variables template
├── .gitignore                          # Git ignore rules
├── .pre-commit-config.yaml             # Pre-commit hooks configuration
├── pyproject.toml                      # Project metadata and dependencies
├── setup.py                            # Setuptools configuration (if needed)
├── requirements.txt                    # Pinned dependencies for deployment
├── requirements-dev.txt                # Development dependencies
├── pytest.ini                          # Pytest configuration
├── mypy.ini                            # Type checking configuration
├── ruff.toml                           # Linting configuration
├── README.md                           # Project overview and quick start
├── LICENSE                             # License file (MIT/Apache 2.0)
└── CHANGELOG.md                        # Version history
```

**Key Structure Decisions:**

1. **src/ Layout:** Modern Python packaging with `src/ihe_test_util/` prevents import confusion
2. **Module Organization:** Each component gets its own directory with clear responsibility
3. **Separation of Tests:** `tests/` at root level, mirroring `src/` structure
4. **Mock Server Isolation:** `mocks/` separate from main application code
5. **Template & Example Separation:** `templates/` for runtime use, `examples/` for documentation
6. **Configuration Files:** Separate `config/` directory for all configuration
7. **Logs Generated at Runtime:** `logs/` created when needed, not committed to Git

**Installation & Entry Points:**

```toml
# pyproject.toml excerpt
[project.scripts]
ihe-test-util = "ihe_test_util.cli.main:cli"

[tool.setuptools.packages.find]
where = ["src"]
```

**Import Conventions:**

```python
# Within the package
from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.csv_parser.parser import parse_csv
from ihe_test_util.ihe_transactions.pix_add import submit_pix_add

# External usage after installation
from ihe_test_util import __version__
```
