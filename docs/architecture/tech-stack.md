# Tech Stack

### Cloud Infrastructure

**Not Applicable** - This is a local CLI utility with no cloud infrastructure requirements. All processing occurs on the user's local machine in a Python virtual environment.

### Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
|----------|-----------|---------|---------|--------------|
| **Language** | Python | 3.10+ | Primary development language | Modern features (type hints, pattern matching), excellent library ecosystem, wide healthcare integration adoption |
| **Runtime** | CPython | 3.10+ | Python interpreter | Standard Python implementation, best compatibility with dependencies |
| **Package Manager** | pip | Latest | Dependency management | Standard Python package manager, widely supported |
| **Build Tool** | setuptools | Latest | Package building | Standard Python build system, supports pyproject.toml |
| **Project Config** | pyproject.toml | PEP 518 | Project metadata and dependencies | Modern Python standard, consolidates configuration |
| **CLI Framework** | click | 8.1+ | Command-line interface | Superior to argparse for complex CLIs, excellent documentation, decorator-based API |
| **CSV Processing** | pandas | 2.1+ | CSV import and data validation | Robust data manipulation, excellent error handling, widely used |
| **XML Processing** | lxml | 5.1+ | XML parsing, template processing, and message construction | High performance, standards-compliant, supports XPath and XSLT. Used for HL7v3 and XDSb metadata construction |
| **SOAP Client** | zeep | 4.2+ | SOAP/WSDL client with WS-Security (limited use) | Used for standard SOAP operations. **Note:** Has experimental MTOM support - not used for ITI-41 |
| **MTOM/MIME** | email.mime | Built-in | Manual MTOM multipart message construction | Standard library for multipart MIME. Used for ITI-41 MTOM packaging due to zeep's experimental MTOM support |
| **XML Signing** | signxml | 3.2+ | XML signature and canonicalization | Pure Python W3C XML Signature implementation, zero compilation, excellent Windows compatibility. Supports RSA-SHA256, SAML 2.0, XAdES, WS-Security |
| **SAML Generation** | lxml + signxml | 5.1+ / 3.2+ | SAML 2.0 assertion generation and signing | Custom lightweight generator using lxml for assertions, signxml for signing. Simpler than pysaml2, meets project needs |
| **HTTP Client** | requests | 2.31+ | HTTP/HTTPS transport | De facto standard, excellent TLS support, simple API |
| **Mock Server** | Flask | 3.0+ | Mock IHE endpoints for testing | Lightweight, well-documented, easy to configure |
| **WSGI Server** | Werkzeug | 3.0+ | Development server for Flask mocks | Built-in with Flask, sufficient for local testing |
| **Testing Framework** | pytest | 7.4+ | Unit, integration, and E2E tests | Superior to unittest, excellent plugin ecosystem |
| **Test Coverage** | pytest-cov | 4.1+ | Code coverage reporting | Integrates with pytest, generates HTML/XML reports |
| **Test Mocking** | pytest-mock | 3.12+ | Simplified mocking in tests | pytest-native wrapper around unittest.mock |
| **Test Fixtures** | pytest-fixtures | Built-in | Reusable test data | Part of pytest core, supports complex fixture chains |
| **Logging** | logging | Built-in | Structured logging and audit trails | Python standard library, no dependencies |
| **Configuration** | python-dotenv | 1.0+ | Environment variable management | Load .env files for configuration |
| **Date/Time** | python-dateutil | 2.8+ | Date parsing and formatting | Robust date handling for HL7 timestamps |
| **Validation** | pydantic | 2.5+ | Data validation and settings | Type-safe configuration and data validation |
| **Cryptography** | cryptography | 41.0+ | Certificate handling and TLS | Dependency of pysaml2, modern crypto primitives |
| **Code Linting** | ruff | 0.1+ | Fast Python linter | Modern replacement for flake8, significantly faster |
| **Type Checking** | mypy | 1.7+ | Static type checking | Catches type errors before runtime |
| **Code Formatting** | black | 23.12+ | Opinionated code formatter | Eliminates style debates, widely adopted |
| **CI/CD Platform** | GitHub Actions | N/A | Continuous integration | Free for open source, excellent Python support |
| **Documentation** | Markdown | N/A | Project documentation | Simple, readable, version-controllable |
| **Version Control** | Git | 2.40+ | Source control | Industry standard |

### Additional Dependencies (Transitive)

These are required by primary dependencies but listed for transparency:

- **certifi** - Certificate bundle for TLS verification
- **charset-normalizer** - Character encoding detection
- **idna** - Internationalized domain name support
- **urllib3** - HTTP connection pooling (used by requests)
- **defusedxml** - XML bomb protection (used by pysaml2)

### Development Tools

| Tool | Purpose |
|------|---------| 
| **VS Code / PyCharm** | Recommended IDE |
| **virtualenv / venv** | Virtual environment isolation |
| **pip-tools** | Dependency version locking (optional) |
| **pre-commit** | Git pre-commit hooks (optional) |
