"""End-to-end test fixtures and configuration.

This module provides fixtures for E2E tests that validate complete workflows
from CSV parsing through PIX Add and ITI-41 submission. Fixtures include:

- Session-scoped mock server fixtures (minimizes server restarts)
- Test data generation fixtures (CSV files, certificates)
- Temporary output directory fixtures (CCDs, logs, results)
- Configuration fixtures for workflow testing

Usage Examples:
    # Use mock server for complete workflow test
    def test_complete_workflow(e2e_mock_server, e2e_test_csv, e2e_output_dir):
        workflow = IntegratedWorkflow(config, template_path)
        results = workflow.process_batch(e2e_test_csv)
        assert results.fully_successful_count > 0

    # Use diverse patient data for batch testing
    def test_batch_processing(e2e_diverse_patients_csv, e2e_mock_server):
        # Test with 100 diverse patients
        results = workflow.process_batch(e2e_diverse_patients_csv)
        assert results.total_patients == 100
"""

import json
import logging
import multiprocessing
import os
import shutil
import socket
import ssl
import tempfile
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional

import pytest
import requests

from ihe_test_util.config.schema import (
    BatchConfig,
    CertificatesConfig,
    Config,
    EndpointsConfig,
)
from ihe_test_util.mock_server.app import app, initialize_app
from ihe_test_util.mock_server.config import MockServerConfig
from ihe_test_util.models.patient import PatientDemographics


# Configure logging for E2E tests
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


def wait_for_server(url: str, timeout: float = 30.0, interval: float = 0.2) -> bool:
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
            response = requests.get(url, timeout=2)
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
    # Import inside function to avoid multiprocessing issues
    from ihe_test_util.mock_server.app import app, initialize_app
    
    initialize_app(config)
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


# =============================================================================
# Mock Server Fixtures (Session-Scoped for Performance)
# =============================================================================


@pytest.fixture(scope="session")
def e2e_mock_server_config() -> MockServerConfig:
    """Session-scoped mock server configuration for E2E tests.
    
    Creates a mock server configuration optimized for E2E testing with:
    - Dynamic port assignment to avoid conflicts
    - Reduced log noise during tests
    - No artificial delays for performance
    - No random failures for predictable results
    
    Returns:
        MockServerConfig: Configuration for mock server.
    """
    return MockServerConfig(
        http_port=find_free_port(),
        pix_add_endpoint="/pix/add",
        iti41_endpoint="/iti41/submit",
        log_level="WARNING",
        log_path="mocks/logs/e2e_test_server.log",
        pix_add_response_delay_ms=0,
        iti41_response_delay_ms=0,
        pix_add_failure_rate=0.0,
        iti41_failure_rate=0.0,
    )


@pytest.fixture(scope="session")
def e2e_mock_server(
    e2e_mock_server_config: MockServerConfig,
) -> Generator[tuple[str, int], None, None]:
    """Session-scoped fixture that starts a mock server for E2E tests.
    
    This fixture starts the Flask mock server once per test session and
    keeps it running for all E2E tests. The server is automatically stopped
    when the test session ends.
    
    Session scope minimizes server restarts for better performance.
    
    Yields:
        tuple[str, int]: Tuple of (host, port) for the running server.
        
    Usage:
        def test_complete_workflow(e2e_mock_server):
            host, port = e2e_mock_server
            # Server is running at http://{host}:{port}
    """
    host = "127.0.0.1"
    port = e2e_mock_server_config.http_port
    
    # Start server in subprocess
    process = multiprocessing.Process(
        target=_run_mock_server,
        args=(host, port, e2e_mock_server_config),
        daemon=True,
    )
    process.start()
    
    # Wait for server to be ready
    health_url = f"http://{host}:{port}/health"
    if not wait_for_server(health_url, timeout=30.0):
        process.terminate()
        process.join(timeout=5)
        pytest.fail(f"E2E mock server failed to start at {health_url}")
    
    logger.info(f"E2E mock server started at http://{host}:{port}")
    
    yield host, port
    
    # Cleanup
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
    logger.info("E2E mock server stopped")


@pytest.fixture(scope="session")
def e2e_mock_server_url(e2e_mock_server: tuple[str, int]) -> str:
    """Get the base URL for the E2E mock server.
    
    Args:
        e2e_mock_server: The running mock server fixture.
        
    Returns:
        str: Base URL (e.g., "http://127.0.0.1:8080").
    """
    host, port = e2e_mock_server
    return f"http://{host}:{port}"


@pytest.fixture(scope="session")
def e2e_pix_add_url(e2e_mock_server_url: str) -> str:
    """Get the PIX Add endpoint URL for E2E tests.
    
    Args:
        e2e_mock_server_url: Base URL of mock server.
        
    Returns:
        str: Full PIX Add endpoint URL.
    """
    return f"{e2e_mock_server_url}/pix/add"


@pytest.fixture(scope="session")
def e2e_iti41_url(e2e_mock_server_url: str) -> str:
    """Get the ITI-41 endpoint URL for E2E tests.
    
    Args:
        e2e_mock_server_url: Base URL of mock server.
        
    Returns:
        str: Full ITI-41 endpoint URL.
    """
    return f"{e2e_mock_server_url}/iti41/submit"


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def e2e_test_config(
    e2e_pix_add_url: str,
    e2e_iti41_url: str,
    e2e_test_certificate: tuple[Path, Path],
) -> Config:
    """Session-scoped configuration for E2E workflow tests.
    
    Creates a complete configuration with:
    - Mock server endpoints
    - Test certificates
    - Standard OIDs for testing
    
    Args:
        e2e_pix_add_url: PIX Add endpoint URL
        e2e_iti41_url: ITI-41 endpoint URL
        e2e_test_certificate: Test certificate paths
        
    Returns:
        Config: Complete configuration for E2E tests.
    """
    cert_path, key_path = e2e_test_certificate
    
    return Config(
        endpoints=EndpointsConfig(
            pix_add_url=e2e_pix_add_url,
            iti41_url=e2e_iti41_url,
        ),
        certificates=CertificatesConfig(
            cert_path=cert_path,
            key_path=key_path,
        ),
        sender_oid="2.16.840.1.113883.3.72.5.9.1",
        receiver_oid="2.16.840.1.113883.3.72.5.9.2",
        sender_application="E2E_TEST_APP",
        receiver_application="MOCK_PIX_MGR",
    )


@pytest.fixture
def e2e_batch_config() -> BatchConfig:
    """Batch configuration for E2E tests.
    
    Returns:
        BatchConfig: Batch processing configuration.
    """
    return BatchConfig(
        checkpoint_interval=25,
        fail_fast=False,
        concurrent_connections=1,
    )


# =============================================================================
# Certificate Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def e2e_test_certificate() -> tuple[Path, Path]:
    """Session-scoped test certificate fixture.
    
    Returns paths to test certificate and private key.
    Uses existing test certificates from fixtures directory.
    
    Returns:
        tuple[Path, Path]: Paths to (cert.pem, key.pem)
    """
    cert_path = Path("tests/fixtures/test_cert.pem")
    key_path = Path("tests/fixtures/test_key.pem")
    
    if not cert_path.exists() or not key_path.exists():
        pytest.skip("Test certificates not found. Run tests/fixtures/generate_test_certs.py first.")
    
    return cert_path, key_path


@pytest.fixture(scope="session")
def e2e_expired_certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Generate an expired certificate for testing certificate handling.
    
    Creates a self-signed certificate that has already expired.
    
    Args:
        tmp_path_factory: Session-scoped temp path factory
        
    Returns:
        tuple[Path, Path]: Paths to (expired_cert.pem, expired_key.pem)
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        pytest.skip("cryptography library required for certificate generation")
    
    tmp_dir = tmp_path_factory.mktemp("expired_certs")
    
    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Generate expired certificate (expired 30 days ago)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Oregon"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Portland"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "E2E Test Expired"),
        x509.NameAttribute(NameOID.COMMON_NAME, "e2e-test-expired.local"),
    ])
    
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=60))  # Valid from 60 days ago
        .not_valid_after(now - timedelta(days=30))   # Expired 30 days ago
        .sign(key, hashes.SHA256())
    )
    
    # Save certificate and key
    cert_path = tmp_dir / "expired_cert.pem"
    key_path = tmp_dir / "expired_key.pem"
    
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    
    return cert_path, key_path


@pytest.fixture(scope="session")
def e2e_not_yet_valid_certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Generate a not-yet-valid certificate for testing certificate handling.
    
    Creates a self-signed certificate that is not valid until a future date.
    
    Args:
        tmp_path_factory: Session-scoped temp path factory
        
    Returns:
        tuple[Path, Path]: Paths to (future_cert.pem, future_key.pem)
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        pytest.skip("cryptography library required for certificate generation")
    
    tmp_dir = tmp_path_factory.mktemp("future_certs")
    
    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Generate not-yet-valid certificate (valid starting 30 days from now)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Oregon"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Portland"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "E2E Test Future"),
        x509.NameAttribute(NameOID.COMMON_NAME, "e2e-test-future.local"),
    ])
    
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now + timedelta(days=30))  # Valid starting 30 days from now
        .not_valid_after(now + timedelta(days=365))  # Valid for 1 year
        .sign(key, hashes.SHA256())
    )
    
    # Save certificate and key
    cert_path = tmp_dir / "future_cert.pem"
    key_path = tmp_dir / "future_key.pem"
    
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    
    return cert_path, key_path


# =============================================================================
# Test Data Generation Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def e2e_ccd_template_path() -> Path:
    """Path to CCD template for E2E tests.
    
    Returns:
        Path: Path to CCD template file.
    """
    template_path = Path("templates/ccd-template.xml")
    if not template_path.exists():
        # Fall back to minimal template
        template_path = Path("templates/ccd-minimal.xml")
    
    if not template_path.exists():
        pytest.skip("CCD template not found")
    
    return template_path


@pytest.fixture
def e2e_sample_patient() -> PatientDemographics:
    """Single sample patient for E2E workflow testing.
    
    Returns:
        PatientDemographics: Sample patient data.
    """
    return PatientDemographics(
        patient_id=f"E2E-{uuid.uuid4().hex[:8].upper()}",
        patient_id_oid="2.16.840.1.113883.3.72.5.9.1",
        first_name="John",
        last_name="TestPatient",
        gender="M",
        dob=date(1980, 5, 15),
        address="123 E2E Test Street",
        city="Portland",
        state="OR",
        zip="97201",
    )


@pytest.fixture
def e2e_test_csv(tmp_path: Path) -> Path:
    """Create a small test CSV file for basic workflow testing.
    
    Creates a CSV with 3 patients for quick workflow validation.
    
    Args:
        tmp_path: Pytest temporary path fixture.
        
    Returns:
        Path: Path to temporary CSV file.
    """
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,address,city,state,zip
E2E-001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-15,M,123 Main St,Portland,OR,97201
E2E-002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1975-06-20,F,456 Oak Ave,Seattle,WA,98101
E2E-003,2.16.840.1.113883.3.72.5.9.1,Robert,Johnson,1990-03-10,M,789 Pine Rd,San Francisco,CA,94102
"""
    csv_file = tmp_path / "e2e_test_patients.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def e2e_ten_patient_csv(tmp_path: Path) -> Path:
    """Create a 10-patient CSV file for multi-patient testing.
    
    Args:
        tmp_path: Pytest temporary path fixture.
        
    Returns:
        Path: Path to temporary CSV file with 10 patients.
    """
    header = "patient_id,patient_id_oid,first_name,last_name,dob,gender,address,city,state,zip\n"
    
    first_names = ["John", "Jane", "Robert", "Maria", "Michael", "Sarah", "David", "Emily", "James", "Lisa"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Martinez", "Wilson"]
    genders = ["M", "F", "M", "F", "M", "F", "M", "F", "M", "F"]
    states = ["OR", "WA", "CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA"]
    
    rows = []
    for i in range(10):
        year = 1950 + (i * 5)
        month = (i % 12) + 1
        day = (i % 28) + 1
        zip_code = f"{97000 + (i * 100):05d}"
        
        row = f"E2E-{i+1:03d},2.16.840.1.113883.3.72.5.9.1,{first_names[i]},{last_names[i]},{year}-{month:02d}-{day:02d},{genders[i]},{100 + i} Test St,TestCity,{states[i]},{zip_code}"
        rows.append(row)
    
    csv_content = header + "\n".join(rows) + "\n"
    csv_file = tmp_path / "e2e_ten_patients.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture(scope="session")
def e2e_diverse_patients_csv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a diverse 100-patient CSV file for batch testing.
    
    Creates CSV with patients having various:
    - Ages (infant, child, adult, elderly)
    - Genders (M, F, O, U)
    - Address formats (US states, various formats)
    - Name variations (special characters, hyphens, apostrophes)
    
    Session-scoped to avoid regeneration.
    
    Args:
        tmp_path_factory: Session-scoped temp path factory.
        
    Returns:
        Path: Path to CSV file with 100 diverse patients.
    """
    tmp_dir = tmp_path_factory.mktemp("e2e_data")
    
    header = "patient_id,patient_id_oid,first_name,last_name,dob,gender,address,city,state,zip\n"
    
    # Diverse first names including special characters
    first_names = [
        "John", "María", "Wei", "Björk", "O'Brien", "Jean-Pierre", 
        "Nguyễn", "Müller", "Søren", "François", "Ana", "José",
        "Yuki", "Ahmed", "Olga", "Raj", "Fatima", "Chen", "Kim", "Lars"
    ]
    
    # Diverse last names
    last_names = [
        "Smith", "García", "Wang", "O'Connor", "McDonald", "St. Clair",
        "van der Berg", "de la Cruz", "Al-Hassan", "Nakamura", "Johansson",
        "Patel", "Nguyen", "Kim", "Singh", "Cohen", "Müller", "Dubois", "Rossi", "Santos"
    ]
    
    # Genders including O (Other) and U (Unknown)
    genders = ["M", "F", "M", "F", "O", "U", "M", "F", "M", "F"]
    
    # US States
    states = ["OR", "WA", "CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA",
              "NC", "MI", "NJ", "VA", "AZ", "MA", "TN", "IN", "MO", "MD"]
    
    rows = []
    for i in range(100):
        # Generate diverse ages (0-99 years old)
        if i < 5:
            # Infants (0-2 years)
            year = 2023
            month = (i % 12) + 1
        elif i < 15:
            # Children (3-17 years)
            year = 2010 - (i % 10)
            month = (i % 12) + 1
        elif i < 70:
            # Adults (18-65 years)
            year = 1960 + (i % 40)
            month = (i % 12) + 1
        else:
            # Elderly (65+ years)
            year = 1935 + (i % 25)
            month = (i % 12) + 1
        
        day = (i % 28) + 1
        first_name = first_names[i % len(first_names)]
        last_name = last_names[i % len(last_names)]
        gender = genders[i % len(genders)]
        state = states[i % len(states)]
        zip_code = f"{10000 + (i * 500):05d}"
        
        row = f"E2E-DIVERSE-{i+1:03d},2.16.840.1.113883.3.72.5.9.1,{first_name},{last_name},{year}-{month:02d}-{day:02d},{gender},{100 + i} Test Ave,City{i},{state},{zip_code}"
        rows.append(row)
    
    csv_content = header + "\n".join(rows) + "\n"
    csv_file = tmp_dir / "e2e_diverse_100_patients.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    
    return csv_file


@pytest.fixture
def e2e_malformed_csv(tmp_path: Path) -> Path:
    """Create a CSV with malformed/invalid data for error handling tests.
    
    Includes:
    - Missing required fields
    - Invalid date formats
    - Invalid gender codes
    
    Args:
        tmp_path: Pytest temporary path fixture.
        
    Returns:
        Path: Path to malformed CSV file.
    """
    csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,address,city,state,zip
E2E-BAD-001,2.16.840.1.113883.3.72.5.9.1,John,Doe,invalid-date,M,123 Main St,Portland,OR,97201
E2E-BAD-002,2.16.840.1.113883.3.72.5.9.1,,Smith,1980-01-15,F,456 Oak Ave,Seattle,WA,98101
E2E-BAD-003,2.16.840.1.113883.3.72.5.9.1,Robert,,1990-03-10,M,789 Pine Rd,San Francisco,CA,94102
E2E-BAD-004,2.16.840.1.113883.3.72.5.9.1,Valid,Patient,1985-07-20,X,Invalid Gender,City,ST,12345
,2.16.840.1.113883.3.72.5.9.1,Missing,ID,1975-11-05,F,No Patient ID,Town,AA,00000
"""
    csv_file = tmp_path / "e2e_malformed_patients.csv"
    csv_file.write_text(csv_content)
    return csv_file


# =============================================================================
# Output Directory Fixtures
# =============================================================================


@pytest.fixture
def e2e_output_dir(tmp_path: Path) -> Path:
    """Create temporary output directory for E2E test artifacts.
    
    Creates structured output directory with subdirectories for:
    - logs/: Transaction and audit logs
    - results/: JSON result files
    - documents/: Generated CCD documents
    - audit/: Audit trail files
    
    Args:
        tmp_path: Pytest temporary path fixture.
        
    Returns:
        Path: Path to output directory.
    """
    output_dir = tmp_path / "e2e_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (output_dir / "logs").mkdir()
    (output_dir / "results").mkdir()
    (output_dir / "documents").mkdir()
    (output_dir / "audit").mkdir()
    
    return output_dir


@pytest.fixture
def e2e_checkpoint_file(tmp_path: Path) -> Path:
    """Path for checkpoint file in E2E tests.
    
    Args:
        tmp_path: Pytest temporary path fixture.
        
    Returns:
        Path: Path where checkpoint file should be saved.
    """
    return tmp_path / "e2e_checkpoint.json"


# =============================================================================
# External Test Bed Configuration (for NIST testing)
# =============================================================================


@pytest.fixture
def e2e_external_config_path() -> Optional[Path]:
    """Path to external test bed configuration file.
    
    Checks for external configuration in environment variable or default path.
    Returns None if no external configuration is available.
    
    Returns:
        Optional[Path]: Path to external config, or None.
    """
    # Check environment variable first
    env_config = os.environ.get("E2E_EXTERNAL_CONFIG")
    if env_config:
        config_path = Path(env_config)
        if config_path.exists():
            return config_path
    
    # Check default location
    default_path = Path("tests/e2e/external_config.json")
    if default_path.exists():
        return default_path
    
    return None


@pytest.fixture
def e2e_external_config(e2e_external_config_path: Optional[Path]) -> Optional[dict]:
    """Load external test bed configuration if available.
    
    Args:
        e2e_external_config_path: Path to external config file.
        
    Returns:
        Optional[dict]: External configuration, or None if not available.
    """
    if e2e_external_config_path is None:
        return None
    
    with e2e_external_config_path.open("r") as f:
        return json.load(f)


# =============================================================================
# Pytest Markers Configuration
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure custom pytest markers for E2E tests.
    
    Args:
        config: Pytest configuration object.
    """
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end test (requires mock server)",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow (may take longer than 30 seconds)",
    )
    config.addinivalue_line(
        "markers",
        "external: mark test as requiring external test bed (NIST)",
    )
    config.addinivalue_line(
        "markers",
        "performance: mark test as performance/benchmark test",
    )
    config.addinivalue_line(
        "markers",
        "certificate: mark test as certificate-related",
    )
    config.addinivalue_line(
        "markers",
        "https: mark test as requiring HTTPS transport",
    )


# =============================================================================
# Test Timeout Configuration
# =============================================================================


@pytest.fixture(autouse=True)
def e2e_test_timeout(request: pytest.FixtureRequest) -> None:
    """Apply default timeout to E2E tests to prevent hanging.
    
    This fixture is auto-applied to all E2E tests.
    Tests marked with 'slow' get extended timeout.
    
    Args:
        request: Pytest fixture request.
    """
    # Default timeout for E2E tests: 60 seconds
    # Slow tests get 600 seconds (10 minutes)
    markers = [marker.name for marker in request.node.iter_markers()]
    
    if "slow" in markers or "performance" in markers:
        # Extended timeout for slow/performance tests
        timeout = 600
    else:
        # Default timeout for regular E2E tests
        timeout = 60
    
    # Note: Actual timeout enforcement requires pytest-timeout plugin
    # This fixture just documents the expected timeouts


# =============================================================================
# Cleanup Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def e2e_cleanup_logs() -> Generator[None, None, None]:
    """Clean up any E2E test logs after test completion.
    
    Yields control to the test, then cleans up log files.
    """
    yield
    
    # Clean up E2E-specific logs if they exist
    log_patterns = [
        Path("mocks/logs/e2e_test_server.log"),
        Path("logs/e2e_test.log"),
    ]
    
    for log_path in log_patterns:
        if log_path.exists():
            try:
                log_path.unlink()
            except OSError:
                pass  # Ignore cleanup errors
