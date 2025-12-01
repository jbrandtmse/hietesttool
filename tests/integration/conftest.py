"""Integration test fixtures and configuration.

This module provides fixtures for integration tests, including:
- Mock server fixtures for IHE endpoints
- Test data fixtures
- Certificate fixtures
- Configuration fixtures

The mock server fixtures automatically start and stop the Flask mock server
for tests that require actual HTTP endpoint testing.
"""

import logging
import multiprocessing
import socket
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Generator, Iterator

import pytest
import requests
from flask.testing import FlaskClient

from ihe_test_util.mock_server.app import app, initialize_app
from ihe_test_util.mock_server.config import MockServerConfig, load_config
from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.models.saml import SAMLAssertion, SAMLGenerationMethod
from ihe_test_util.models.transactions import ITI41Transaction


# Configure logging for integration tests
logger = logging.getLogger(__name__)


# =============================================================================
# Utility Functions
# =============================================================================


def find_free_port() -> int:
    """Find an available port on localhost.
    
    Returns:
        int: An available port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_server(url: str, timeout: float = 10.0, interval: float = 0.1) -> bool:
    """Wait for server to become available.
    
    Args:
        url: URL to check (e.g., health endpoint).
        timeout: Maximum time to wait in seconds.
        interval: Time between checks in seconds.
        
    Returns:
        bool: True if server became available, False if timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval)
    return False


def _run_mock_server(host: str, port: int, config: MockServerConfig) -> None:
    """Run the mock server in a subprocess.
    
    Args:
        host: Host to bind to.
        port: Port to listen on.
        config: Mock server configuration.
    """
    from ihe_test_util.mock_server.app import app, initialize_app
    
    initialize_app(config)
    app.run(host=host, port=port, debug=False, use_reloader=False)


# =============================================================================
# Mock Server Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def mock_server_config() -> MockServerConfig:
    """Session-scoped mock server configuration.
    
    Returns:
        MockServerConfig: Configuration for mock server.
    """
    return MockServerConfig(
        http_port=find_free_port(),
        pix_add_endpoint="/pix/add",
        iti41_endpoint="/iti41/submit",
        log_level="WARNING",  # Reduce log noise during tests
        log_path="mocks/logs/test_server.log",
        pix_add_response_delay_ms=0,  # No delay for fast tests
        iti41_response_delay_ms=0,
        pix_add_failure_rate=0.0,  # No random failures
        iti41_failure_rate=0.0,
    )


@pytest.fixture(scope="session")
def mock_server_process(
    mock_server_config: MockServerConfig,
) -> Generator[tuple[str, int], None, None]:
    """Session-scoped fixture that starts a mock server in a subprocess.
    
    This fixture starts the Flask mock server once per test session and
    keeps it running for all tests. The server is automatically stopped
    when the test session ends.
    
    Yields:
        tuple[str, int]: Tuple of (host, port) for the running server.
        
    Usage:
        def test_against_mock_server(mock_server_process):
            host, port = mock_server_process
            response = requests.post(f"http://{host}:{port}/pix/add", ...)
    """
    host = "127.0.0.1"
    port = mock_server_config.http_port
    
    # Start server in subprocess
    process = multiprocessing.Process(
        target=_run_mock_server,
        args=(host, port, mock_server_config),
        daemon=True,
    )
    process.start()
    
    # Wait for server to be ready
    health_url = f"http://{host}:{port}/health"
    if not wait_for_server(health_url, timeout=10.0):
        process.terminate()
        process.join(timeout=5)
        pytest.fail(f"Mock server failed to start at {health_url}")
    
    logger.info(f"Mock server started at http://{host}:{port}")
    
    yield host, port
    
    # Cleanup
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
    logger.info("Mock server stopped")


@pytest.fixture
def mock_server_url(mock_server_process: tuple[str, int]) -> str:
    """Get the base URL for the mock server.
    
    Args:
        mock_server_process: The running mock server fixture.
        
    Returns:
        str: Base URL (e.g., "http://127.0.0.1:8080").
    """
    host, port = mock_server_process
    return f"http://{host}:{port}"


@pytest.fixture
def mock_pix_add_url(mock_server_url: str) -> str:
    """Get the PIX Add endpoint URL.
    
    Args:
        mock_server_url: Base URL of mock server.
        
    Returns:
        str: Full PIX Add endpoint URL.
    """
    return f"{mock_server_url}/pix/add"


@pytest.fixture
def mock_iti41_url(mock_server_url: str) -> str:
    """Get the ITI-41 endpoint URL.
    
    Args:
        mock_server_url: Base URL of mock server.
        
    Returns:
        str: Full ITI-41 endpoint URL.
    """
    return f"{mock_server_url}/iti41/submit"


@pytest.fixture
def flask_test_client(mock_server_config: MockServerConfig) -> FlaskClient:
    """Provide Flask test client for in-process testing.
    
    This fixture is faster than the mock_server_process fixture as it
    doesn't require starting a separate process. Use for tests that
    don't need to test actual HTTP transport.
    
    Args:
        mock_server_config: Mock server configuration.
        
    Returns:
        FlaskClient: Flask test client.
    """
    initialize_app(mock_server_config)
    app.config["TESTING"] = True
    return app.test_client()


# =============================================================================
# Patient Data Fixtures
# =============================================================================


@pytest.fixture
def sample_patient() -> PatientDemographics:
    """Sample patient demographics for testing.
    
    Returns:
        PatientDemographics: Sample patient data.
    """
    return PatientDemographics(
        patient_id="TEST-12345",
        patient_id_oid="2.16.840.1.113883.3.72.5.9.1",
        first_name="John",
        last_name="Doe",
        gender="M",
        dob=date(1980, 1, 15),
        address="123 Main Street",
        city="Portland",
        state="OR",
        zip="97201",
    )


@pytest.fixture
def sample_patients() -> list[PatientDemographics]:
    """Multiple sample patients for batch testing.
    
    Returns:
        list[PatientDemographics]: List of sample patients.
    """
    return [
        PatientDemographics(
            patient_id=f"TEST-{1000 + i}",
            patient_id_oid="2.16.840.1.113883.3.72.5.9.1",
            first_name=f"Patient{i}",
            last_name=f"Test{i}",
            gender="M" if i % 2 == 0 else "F",
            dob=date(1970 + i, (i % 12) + 1, (i % 28) + 1),
        )
        for i in range(5)
    ]


# =============================================================================
# Certificate Fixtures
# =============================================================================


@pytest.fixture
def test_cert_path() -> Path:
    """Path to test certificate (PEM format).
    
    Returns:
        Path: Path to test_cert.pem.
    """
    return Path("tests/fixtures/test_cert.pem")


@pytest.fixture
def test_key_path() -> Path:
    """Path to test private key (PEM format).
    
    Returns:
        Path: Path to test_key.pem.
    """
    return Path("tests/fixtures/test_key.pem")


@pytest.fixture
def test_pkcs12_path() -> Path:
    """Path to test certificate (PKCS12 format).
    
    Returns:
        Path: Path to test_cert.p12.
    """
    return Path("tests/fixtures/test_cert.p12")


@pytest.fixture
def test_der_cert_path() -> Path:
    """Path to test certificate (DER format).
    
    Returns:
        Path: Path to test_cert.der.
    """
    return Path("tests/fixtures/test_cert.der")


# =============================================================================
# SAML Fixtures
# =============================================================================


@pytest.fixture
def mock_saml_assertion() -> SAMLAssertion:
    """Mock SAML assertion for testing.
    
    Returns:
        SAMLAssertion: Pre-configured SAML assertion.
    """
    import uuid
    
    return SAMLAssertion(
        assertion_id=f"_integration_test_{uuid.uuid4()}",
        issuer="https://integration-test.example.com/idp",
        subject="test-user@example.com",
        audience="https://integration-test.example.com/sp",
        not_before="2025-01-01T00:00:00Z",
        not_on_or_after="2025-12-31T23:59:59Z",
        authn_instant="2025-01-01T00:00:00Z",
        attributes={
            "urn:oasis:names:tc:xspa:1.0:subject:subject-id": "test-user",
            "urn:oasis:names:tc:xspa:1.0:subject:organization": "Test Hospital",
            "urn:oasis:names:tc:xspa:1.0:subject:role": "physician",
            "urn:oasis:names:tc:xspa:1.0:subject:purposeofuse": "TREATMENT",
        },
        is_signed=False,
        certificate_subject="CN=Integration Test Certificate",
        generation_method=SAMLGenerationMethod.PROGRAMMATIC,
    )


# =============================================================================
# Transaction Fixtures
# =============================================================================


@pytest.fixture
def mock_iti41_transaction(sample_patient: PatientDemographics) -> ITI41Transaction:
    """Mock ITI-41 transaction for testing.
    
    Args:
        sample_patient: Sample patient fixture.
        
    Returns:
        ITI41Transaction: Pre-configured ITI-41 transaction.
    """
    import uuid
    
    # Minimal XDSb metadata for testing
    xdsb_request = """<?xml version="1.0" encoding="UTF-8"?>
<xds:ProvideAndRegisterDocumentSetRequest xmlns:xds="urn:ihe:iti:xds-b:2007">
    <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
        <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
        </rim:RegistryObjectList>
    </lcm:SubmitObjectsRequest>
</xds:ProvideAndRegisterDocumentSetRequest>"""
    
    return ITI41Transaction(
        transaction_id=str(uuid.uuid4()),
        submission_set_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        patient_id=sample_patient.patient_id,
        patient_id_oid=sample_patient.patient_id_oid,
        xdsb_request=xdsb_request,
        soap_xml="",  # Will be generated during submission
    )


# =============================================================================
# Template Fixtures
# =============================================================================


@pytest.fixture
def ccd_template_path() -> Path:
    """Path to CCD template file.
    
    Returns:
        Path: Path to templates/ccd-template.xml.
    """
    return Path("templates/ccd-template.xml")


@pytest.fixture
def ccd_minimal_template_path() -> Path:
    """Path to minimal CCD template file.
    
    Returns:
        Path: Path to templates/ccd-minimal.xml.
    """
    return Path("templates/ccd-minimal.xml")


@pytest.fixture
def test_ccd_template_path() -> Path:
    """Path to test CCD template fixture.
    
    Returns:
        Path: Path to tests/fixtures/test_ccd_template.xml.
    """
    return Path("tests/fixtures/test_ccd_template.xml")


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def sample_config_dict() -> dict:
    """Sample configuration dictionary for testing.
    
    Returns:
        dict: Configuration dictionary.
    """
    return {
        "pix_add_endpoint": "http://localhost:8080/pix/add",
        "iti41_endpoint": "http://localhost:8080/iti41/submit",
        "timeout": 30,
        "retry_count": 3,
        "patient_id_oid": "2.16.840.1.113883.3.72.5.9.1",
        "submission_set_source_id": "1.2.3.4.5",
    }


@pytest.fixture
def temp_config_file(tmp_path: Path, sample_config_dict: dict) -> Path:
    """Create a temporary configuration file.
    
    Args:
        tmp_path: Pytest temporary path fixture.
        sample_config_dict: Configuration dictionary.
        
    Returns:
        Path: Path to temporary config file.
    """
    import json
    
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(sample_config_dict, indent=2))
    return config_file


# =============================================================================
# CSV Fixtures
# =============================================================================


@pytest.fixture
def sample_csv_content() -> str:
    """Sample CSV content for testing.
    
    Returns:
        str: CSV content string.
    """
    return """patient_id,patient_id_oid,first_name,last_name,dob,gender,address,city,state,zip
TEST-001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-15,M,123 Main St,Portland,OR,97201
TEST-002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1975-06-20,F,456 Oak Ave,Seattle,WA,98101
TEST-003,2.16.840.1.113883.3.72.5.9.1,Robert,Johnson,1990-03-10,M,789 Pine Rd,San Francisco,CA,94102
"""


@pytest.fixture
def sample_csv_file(tmp_path: Path, sample_csv_content: str) -> Path:
    """Create a temporary CSV file with sample data.
    
    Args:
        tmp_path: Pytest temporary path fixture.
        sample_csv_content: CSV content.
        
    Returns:
        Path: Path to temporary CSV file.
    """
    csv_file = tmp_path / "patients.csv"
    csv_file.write_text(sample_csv_content)
    return csv_file


# =============================================================================
# Response Fixtures
# =============================================================================


@pytest.fixture
def registry_response_success_path() -> Path:
    """Path to successful registry response fixture.
    
    Returns:
        Path: Path to registry_response_success.xml.
    """
    return Path("tests/fixtures/registry_response_success.xml")


@pytest.fixture
def registry_response_failure_path() -> Path:
    """Path to failed registry response fixture.
    
    Returns:
        Path: Path to registry_response_failure.xml.
    """
    return Path("tests/fixtures/registry_response_failure.xml")


@pytest.fixture
def registry_response_partial_path() -> Path:
    """Path to partial success registry response fixture.
    
    Returns:
        Path: Path to registry_response_partial.xml.
    """
    return Path("tests/fixtures/registry_response_partial.xml")


# =============================================================================
# Pytest Markers Configuration
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure custom pytest markers.
    
    Args:
        config: Pytest configuration object.
    """
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires mock server or external resources)",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow (may take longer than 5 seconds)",
    )
    config.addinivalue_line(
        "markers",
        "requires_mock_server: mark test as requiring the mock server to be running",
    )
