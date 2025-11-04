"""
Shared pytest configuration and fixtures.

This module provides fixtures and configuration used across all test suites
(unit, integration, and e2e tests).
"""

import pytest
from pathlib import Path
from typing import Generator


@pytest.fixture
def project_root() -> Path:
    """
    Return the project root directory.
    
    Returns:
        Path: Absolute path to the project root directory.
    """
    return Path(__file__).parent.parent


@pytest.fixture
def src_dir(project_root: Path) -> Path:
    """
    Return the src directory path.
    
    Args:
        project_root: Project root directory fixture.
    
    Returns:
        Path: Absolute path to the src directory.
    """
    return project_root / "src"


@pytest.fixture
def tests_dir(project_root: Path) -> Path:
    """
    Return the tests directory path.
    
    Args:
        project_root: Project root directory fixture.
    
    Returns:
        Path: Absolute path to the tests directory.
    """
    return project_root / "tests"


@pytest.fixture
def fixtures_dir(tests_dir: Path) -> Path:
    """
    Return the test fixtures directory path.
    
    Args:
        tests_dir: Tests directory fixture.
    
    Returns:
        Path: Absolute path to the test fixtures directory.
    """
    return tests_dir / "fixtures"


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Create a temporary configuration file for testing.
    
    Args:
        tmp_path: Pytest's temporary directory fixture.
    
    Yields:
        Path: Path to the temporary configuration file.
    """
    config_file = tmp_path / "test_config.json"
    config_file.write_text('{"test": "value"}')
    yield config_file
    # Cleanup handled by tmp_path


@pytest.fixture
def sample_csv_data() -> str:
    """
    Return sample CSV data for testing CSV parser.
    
    Returns:
        str: Sample CSV content with patient data.
    """
    return """PatientID,FirstName,LastName,DateOfBirth,Gender
12345,John,Doe,1980-01-01,M
67890,Jane,Smith,1975-05-15,F"""


@pytest.fixture
def sample_patient_dict() -> dict:
    """
    Return sample patient data as a dictionary.
    
    Returns:
        dict: Sample patient demographics dictionary.
    """
    return {
        "patient_id": "12345",
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1980-01-01",
        "gender": "M"
    }
