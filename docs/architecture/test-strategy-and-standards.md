# Test Strategy and Standards

### Testing Philosophy

**Approach:** Test-driven development encouraged, test-after acceptable
**Coverage Goals:** 
- Minimum: 75% (CI fails below)
- Target: 80%+
- Critical modules (IHE Transactions, SAML): 90%+

**Test Pyramid:**
- Unit tests: 70% of total tests
- Integration tests: 25% of total tests
- E2E tests: 5% of total tests

### Test Types and Organization

#### Unit Tests

**Framework:** pytest 7.4+
**File Convention:** `tests/unit/test_{module_name}.py`
**Location:** `tests/unit/`
**Mocking Library:** pytest-mock
**Coverage Requirement:** 80%+

**AI Agent Requirements:**
- Generate tests for all public methods
- Cover edge cases and error conditions
- Follow AAA pattern (Arrange, Act, Assert)
- Mock all external dependencies (file I/O, network, etc.)

**Example:**
```python
def test_parse_csv_valid_data(tmp_path):
    # Arrange
    csv_file = tmp_path / "patients.csv"
    csv_file.write_text("first_name,last_name,dob,gender,patient_id_oid\nJohn,Doe,1980-01-01,M,1.2.3.4")
    
    # Act
    result = parse_csv(csv_file)
    
    # Assert
    assert len(result) == 1
    assert result.iloc[0]["first_name"] == "John"
```

#### Integration Tests

**Scope:** Component interactions (e.g., CSV → Template → CCD generation)
**Location:** `tests/integration/`
**Test Infrastructure:**
- **Mock Endpoints:** Flask test client for mock PIX Add and ITI-41
- **File System:** pytest tmp_path fixtures
- **Certificates:** Test certificates in `tests/fixtures/`

**Example:**
```python
def test_pix_add_workflow_against_mock(mock_server, test_patient):
    # Mock server running on localhost:8080
    response = submit_pix_add(test_patient, "http://localhost:8080/pix/add")
    assert response.status == TransactionStatus.SUCCESS
```

#### End-to-End Tests

**Framework:** pytest
**Scope:** Complete CSV → PIX Add → ITI-41 workflows
**Environment:** Mock endpoints (not external test beds in CI)
**Test Data:** `tests/fixtures/sample_patients.csv` (10 diverse patients)

**Example:**
```python
def test_complete_workflow_100_patients(tmp_path, mock_server):
    # Generate 100-patient CSV
    csv_file = generate_test_csv(tmp_path, num_patients=100)
    
    # Execute complete workflow
    start = time.time()
    result = execute_submit_workflow(csv_file)
    duration = time.time() - start
    
    # Assert performance requirements
    assert duration < 300  # Under 5 minutes (NFR1)
    assert result.success_rate >= 0.95  # 95%+ success (PRD goal)
```

### Test Data Management

**Strategy:** Fixtures and factories
**Fixtures:** `tests/conftest.py` for shared fixtures
**Factories:** pytest-factoryboy for model generation (optional)
**Cleanup:** pytest automatically cleans tmp_path fixtures

### Continuous Testing

**CI Integration:** GitHub Actions runs full test suite on push/PR
**Performance Tests:** E2E tests validate 5-minute batch processing requirement
**Security Tests:** Certificate validation, SAML signature verification in integration tests
