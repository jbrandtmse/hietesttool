# Infrastructure and Deployment

**Note:** This is a local CLI utility with no cloud infrastructure. Deployment focuses on Python package distribution.

### Infrastructure as Code

**Not Applicable** - No cloud infrastructure to manage. Local execution only.

### Deployment Strategy

**Distribution Method:** Python Package (PyPI)
- **Primary Distribution:** PyPI (Python Package Index) via `pip install ihe-test-utility`
- **Alternative:** GitHub Releases with wheel (.whl) and source distribution (.tar.gz)
- **Optional:** Docker image for users preferring containerization (not required)

**Build Process:**
```bash
# Build distributions
python -m build

# Outputs:
# dist/ihe_test_utility-0.1.0-py3-none-any.whl
# dist/ihe_test_utility-0.1.0.tar.gz
```

**Installation:**
```bash
# From PyPI
pip install ihe-test-utility

# From GitHub release
pip install https://github.com/org/ihe-test-utility/releases/download/v0.1.0/ihe_test_utility-0.1.0-py3-none-any.whl

# Development mode
git clone https://github.com/org/ihe-test-utility.git
cd ihe-test-utility
pip install -e ".[dev]"
```

### Environments

| Environment | Purpose | Installation Method |
|-------------|---------|---------------------|
| **Development** | Local development and testing | `pip install -e ".[dev]"` from source |
| **CI/CD** | Automated testing in GitHub Actions | `pip install -e ".[dev]"` from checkout |
| **User Installation** | End-user deployment | `pip install ihe-test-utility` from PyPI |
| **Docker (Optional)** | Containerized execution | `docker build -t ihe-test-utility .` |

### CI/CD Pipeline

**Platform:** GitHub Actions

**Pipeline Stages:**

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install ruff mypy
      - run: ruff check src/ tests/
      - run: mypy src/
  
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.10', '3.11', '3.12']
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov=ihe_test_util --cov-report=xml
      - uses: codecov/codecov-action@v3
        if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.10'
  
  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install build
      - run: python -m build
      - uses: actions/upload-artifact@v3
        with:
          name: distributions
          path: dist/
```

### Rollback Strategy

**Rollback Method:** Version pinning
- Users pin to previous working version: `pip install ihe-test-utility==0.0.9`
- PyPI retains all previous versions indefinitely

**Trigger Conditions:**
- Critical bugs discovered in production use
- Breaking changes to IHE transaction handling
- Security vulnerabilities

**Recovery Time Objective:** Immediate (users can downgrade anytime)
