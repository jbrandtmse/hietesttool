"""
Unit tests for project structure validation.

Tests verify that all required directories, files, and modules exist
and are properly configured.
"""

import importlib
import sys
from pathlib import Path

import pytest


class TestProjectStructure:
    """Test suite for validating project directory structure."""

    def test_required_directories_exist(self, project_root: Path) -> None:
        """
        Test that all required top-level directories exist.

        Args:
            project_root: Project root directory fixture.
        """
        # Arrange
        required_dirs = [
            "src",
            "tests",
            "mocks",
            "templates",
            "examples",
            "config",
            "docs",
        ]

        # Act
        missing_dirs = [
            d for d in required_dirs if not (project_root / d).exists()
        ]

        # Assert
        assert not missing_dirs, f"Missing required directories: {missing_dirs}"

    def test_src_module_directories_exist(self, src_dir: Path) -> None:
        """
        Test that all required module directories exist in src/ihe_test_util.

        Args:
            src_dir: Source directory fixture.
        """
        # Arrange
        ihe_test_util_dir = src_dir / "ihe_test_util"
        required_modules = [
            "cli",
            "csv_parser",
            "template_engine",
            "ihe_transactions",
            "saml",
            "transport",
            "mock_server",
            "config",
            "logging_audit",
            "models",
            "utils",
        ]

        # Act
        missing_modules = [
            m for m in required_modules if not (ihe_test_util_dir / m).exists()
        ]

        # Assert
        assert (
            not missing_modules
        ), f"Missing required module directories: {missing_modules}"

    def test_module_init_files_exist(self, src_dir: Path) -> None:
        """
        Test that all module directories contain __init__.py files.

        Args:
            src_dir: Source directory fixture.
        """
        # Arrange
        ihe_test_util_dir = src_dir / "ihe_test_util"
        module_dirs = [
            ihe_test_util_dir,
            ihe_test_util_dir / "cli",
            ihe_test_util_dir / "csv_parser",
            ihe_test_util_dir / "template_engine",
            ihe_test_util_dir / "ihe_transactions",
            ihe_test_util_dir / "saml",
            ihe_test_util_dir / "transport",
            ihe_test_util_dir / "mock_server",
            ihe_test_util_dir / "config",
            ihe_test_util_dir / "logging_audit",
            ihe_test_util_dir / "models",
            ihe_test_util_dir / "utils",
        ]

        # Act
        missing_init_files = [
            str(d.relative_to(src_dir))
            for d in module_dirs
            if not (d / "__init__.py").exists()
        ]

        # Assert
        assert (
            not missing_init_files
        ), f"Missing __init__.py files in: {missing_init_files}"

    def test_test_directories_exist(self, tests_dir: Path) -> None:
        """
        Test that all required test subdirectories exist.

        Args:
            tests_dir: Tests directory fixture.
        """
        # Arrange
        required_test_dirs = ["unit", "integration", "e2e", "fixtures"]

        # Act
        missing_test_dirs = [
            d for d in required_test_dirs if not (tests_dir / d).exists()
        ]

        # Assert
        assert (
            not missing_test_dirs
        ), f"Missing required test directories: {missing_test_dirs}"

    def test_configuration_files_exist(self, project_root: Path) -> None:
        """
        Test that all required configuration files exist.

        Args:
            project_root: Project root directory fixture.
        """
        # Arrange
        required_config_files = [
            "pyproject.toml",
            "pytest.ini",
            "mypy.ini",
            "ruff.toml",
            ".gitignore",
            ".env.example",
            "README.md",
            "requirements.txt",
            "requirements-dev.txt",
        ]

        # Act
        missing_files = [
            f for f in required_config_files if not (project_root / f).exists()
        ]

        # Assert
        assert not missing_files, f"Missing required configuration files: {missing_files}"


class TestPackageImports:
    """Test suite for validating package imports."""

    def test_package_version_accessible(self) -> None:
        """Test that package version is accessible from ihe_test_util.__version__."""
        # Arrange / Act
        from ihe_test_util import __version__

        # Assert
        assert __version__ == "0.1.0"
        assert isinstance(__version__, str)

    def test_main_package_import(self) -> None:
        """Test that main package can be imported."""
        # Arrange / Act
        import ihe_test_util

        # Assert
        assert hasattr(ihe_test_util, "__version__")

    def test_utils_exceptions_import(self) -> None:
        """Test that utils.exceptions module can be imported."""
        # Arrange / Act
        from ihe_test_util.utils import exceptions

        # Assert
        assert hasattr(exceptions, "IHETestUtilError")
        assert hasattr(exceptions, "ValidationError")
        assert hasattr(exceptions, "TransportError")
        assert hasattr(exceptions, "ConfigurationError")

    def test_saml_module_import(self) -> None:
        """Test that saml module can be imported."""
        # Arrange / Act
        import ihe_test_util.saml

        # Assert
        assert ihe_test_util.saml is not None

    def test_ihe_transactions_module_import(self) -> None:
        """Test that ihe_transactions module can be imported."""
        # Arrange / Act
        import ihe_test_util.ihe_transactions

        # Assert
        assert ihe_test_util.ihe_transactions is not None

    def test_mock_server_module_import(self) -> None:
        """Test that mock_server module can be imported."""
        # Arrange / Act
        import ihe_test_util.mock_server

        # Assert
        assert ihe_test_util.mock_server is not None

    def test_all_placeholder_modules_importable(self) -> None:
        """Test that all placeholder modules can be imported without errors."""
        # Arrange
        modules = [
            "ihe_test_util.cli",
            "ihe_test_util.csv_parser",
            "ihe_test_util.template_engine",
            "ihe_test_util.transport",
            "ihe_test_util.config",
            "ihe_test_util.logging_audit",
            "ihe_test_util.models",
            "ihe_test_util.utils",
        ]

        # Act & Assert
        for module_name in modules:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")


class TestExceptionHierarchy:
    """Test suite for validating custom exception classes."""

    def test_base_exception_exists(self) -> None:
        """Test that base IHETestUtilError exception exists."""
        # Arrange / Act
        from ihe_test_util.utils.exceptions import IHETestUtilError

        # Assert
        assert issubclass(IHETestUtilError, Exception)

    def test_all_custom_exceptions_inherit_from_base(self) -> None:
        """Test that all custom exceptions inherit from IHETestUtilError."""
        # Arrange
        from ihe_test_util.utils.exceptions import (
            ConfigurationError,
            HL7v3Error,
            IHETestUtilError,
            IHETransactionError,
            SAMLError,
            TemplateError,
            TransportError,
            ValidationError,
        )

        exception_classes = [
            ValidationError,
            TransportError,
            ConfigurationError,
            TemplateError,
            SAMLError,
            HL7v3Error,
            IHETransactionError,
        ]

        # Act & Assert
        for exc_class in exception_classes:
            assert issubclass(
                exc_class, IHETestUtilError
            ), f"{exc_class.__name__} does not inherit from IHETestUtilError"

    def test_exceptions_can_be_instantiated_with_message(self) -> None:
        """Test that exceptions can be instantiated with error messages."""
        # Arrange
        from ihe_test_util.utils.exceptions import ValidationError

        error_message = "Test validation error"

        # Act
        error = ValidationError(error_message)

        # Assert
        assert str(error) == error_message
        assert isinstance(error, Exception)


class TestProjectConfiguration:
    """Test suite for validating project configuration."""

    def test_pyproject_toml_is_valid_toml(self, project_root: Path) -> None:
        """Test that pyproject.toml is valid TOML format."""
        # Arrange
        pyproject_path = project_root / "pyproject.toml"

        # Act & Assert
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        # Assert key sections exist
        assert "project" in config
        assert "build-system" in config
        assert config["project"]["name"] == "ihe-test-util"
        assert config["project"]["version"] == "0.1.0"

    def test_pytest_ini_exists_and_configured(self, project_root: Path) -> None:
        """Test that pytest.ini exists and has required configuration."""
        # Arrange
        pytest_ini_path = project_root / "pytest.ini"

        # Act
        content = pytest_ini_path.read_text()

        # Assert
        assert "[pytest]" in content
        assert "testpaths" in content
        assert "--cov=src/ihe_test_util" in content

    def test_gitignore_excludes_python_artifacts(self, project_root: Path) -> None:
        """Test that .gitignore excludes common Python artifacts."""
        # Arrange
        gitignore_path = project_root / ".gitignore"

        # Act
        content = gitignore_path.read_text()

        # Assert
        assert "__pycache__" in content
        assert ".venv" in content or "venv" in content
        assert "*.pyc" in content or "*.py[cod]" in content  # Accept compact pattern
        assert ".pytest_cache" in content
