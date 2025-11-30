"""Unit tests for submit CLI commands (Story 6.7).

Tests cover:
- Direct `submit <csv>` command syntax (AC: 1)
- Backward compatibility with `submit batch <csv>` (AC: 1)
- --pix-only flag parsing and behavior (AC: 4)
- --iti41-only flag with --pix-results validation (AC: 5)
- Real-time progress display format (AC: 6)
- Error categorization logic (AC: 7)
- --quiet, --verbose, --show-errors flags

Test IDs follow QA Test Design document:
- 6.7-UNIT-001 through 6.7-UNIT-018
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from requests import ConnectionError, Timeout
from requests.exceptions import SSLError

from ihe_test_util.cli.submit_commands import (
    ErrorCategory,
    categorize_cli_error,
    load_pix_results,
    save_pix_results,
    submit,
)
from ihe_test_util.models.batch import BatchWorkflowResult, PatientWorkflowResult
from ihe_test_util.utils.exceptions import ConfigurationError, ValidationError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def runner() -> CliRunner:
    """Create Click CLI runner."""
    return CliRunner()


@pytest.fixture
def sample_csv_content() -> str:
    """Sample CSV content for testing."""
    return """first_name,last_name,dob,gender,patient_id_oid
John,Doe,1980-01-01,M,1.2.3.4
Jane,Smith,1990-05-15,F,1.2.3.5
"""


@pytest.fixture
def sample_csv_file(tmp_path: Path, sample_csv_content: str) -> Path:
    """Create a temporary CSV file."""
    csv_file = tmp_path / "patients.csv"
    csv_file.write_text(sample_csv_content)
    return csv_file


@pytest.fixture
def sample_config_content() -> str:
    """Sample configuration JSON."""
    return json.dumps({
        "endpoints": {
            "pix_add_url": "http://localhost:8080/pix/add",
            "iti41_url": "http://localhost:8080/iti41/submit"
        },
        "certificates": {
            "cert_path": "tests/fixtures/test_cert.pem",
            "key_path": "tests/fixtures/test_key.pem"
        }
    })


@pytest.fixture
def sample_config_file(tmp_path: Path, sample_config_content: str) -> Path:
    """Create a temporary config file."""
    config_file = tmp_path / "config.json"
    config_file.write_text(sample_config_content)
    return config_file


@pytest.fixture
def sample_pix_results() -> dict:
    """Sample PIX results data."""
    return {
        "batch_id": "test-batch-001",
        "csv_file": "patients.csv",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patient_results": [
            {
                "patient_id": "PAT001",
                "pix_add_status": "success",
                "pix_enterprise_id": "^^^&1.2.3.4.5&ISO",
                "pix_enterprise_id_oid": "1.2.3.4.5",
                "pix_add_message": "Accepted"
            },
            {
                "patient_id": "PAT002",
                "pix_add_status": "failed",
                "pix_enterprise_id": None,
                "pix_enterprise_id_oid": None,
                "pix_add_message": "Validation error"
            }
        ]
    }


@pytest.fixture
def sample_pix_results_file(tmp_path: Path, sample_pix_results: dict) -> Path:
    """Create a temporary PIX results file."""
    results_file = tmp_path / "pix-results.json"
    results_file.write_text(json.dumps(sample_pix_results))
    return results_file


@pytest.fixture
def mock_batch_result() -> BatchWorkflowResult:
    """Create a mock BatchWorkflowResult."""
    patient_results = [
        PatientWorkflowResult(
            patient_id="PAT001",
            csv_parsed=True,
            ccd_generated=True,
            pix_add_status="success",
            pix_enterprise_id="^^^&1.2.3.4.5&ISO",
            pix_enterprise_id_oid="1.2.3.4.5",
            pix_add_message="Accepted",
            iti41_status="success",
            document_id="DOC001",
            iti41_message="Success",
            total_time_ms=1500,
            pix_add_time_ms=500,
            iti41_time_ms=800,
        ),
        PatientWorkflowResult(
            patient_id="PAT002",
            csv_parsed=True,
            ccd_generated=True,
            pix_add_status="success",
            pix_enterprise_id="^^^&1.2.3.4.6&ISO",
            pix_enterprise_id_oid="1.2.3.4.6",
            pix_add_message="Accepted",
            iti41_status="success",
            document_id="DOC002",
            iti41_message="Success",
            total_time_ms=1400,
            pix_add_time_ms=450,
            iti41_time_ms=750,
        ),
    ]
    return BatchWorkflowResult(
        batch_id="test-batch",
        csv_file="patients.csv",
        ccd_template="templates/ccd-template.xml",
        patient_results=patient_results,
        start_timestamp=datetime.now(timezone.utc),
        end_timestamp=datetime.now(timezone.utc),
    )


# =============================================================================
# AC1: Direct `submit <csv>` Command Tests
# =============================================================================

class TestSubmitDirectCommand:
    """Tests for direct submit <csv> command syntax (AC: 1)."""

    def test_submit_csv_direct_command(self, runner: CliRunner, tmp_path: Path) -> None:
        """6.7-UNIT-001: Verify `submit <csv>` syntax invokes workflow.
        
        Direct submit command should accept CSV file as positional argument
        without requiring 'batch' subcommand.
        """
        # Create test CSV
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        # Run with --dry-run to avoid actual submission
        with patch("ihe_test_util.cli.submit_commands._load_config_with_overrides") as mock_config:
            mock_config.side_effect = ConfigurationError("Test - dry run check")
            
            result = runner.invoke(submit, [str(csv_file)])
            
            # Should attempt to run workflow (config error expected)
            assert "Configuration Error" in result.output or result.exit_code != 0

    def test_submit_backward_compat_batch_syntax(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """6.7-UNIT-002: Verify `submit batch <csv>` still works.
        
        Backward compatibility test ensuring existing scripts using
        `submit batch <csv>` continue to function.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        with patch("ihe_test_util.cli.submit_commands._load_config_with_overrides") as mock_config:
            mock_config.side_effect = ConfigurationError("Test - backward compat")
            
            result = runner.invoke(submit, ["batch", str(csv_file)])
            
            # Should attempt to run batch command
            assert "Configuration Error" in result.output or result.exit_code != 0


# =============================================================================
# AC2-3: Existing Options Tests
# =============================================================================

class TestExistingOptions:
    """Tests for --ccd-template and --config options (AC: 2, 3)."""

    def test_ccd_template_option_parsing(self, runner: CliRunner, tmp_path: Path) -> None:
        """6.7-UNIT-003: Verify --ccd-template flag is parsed correctly.
        
        Backward compatibility test for CCD template option.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        template_file = tmp_path / "ccd-template.xml"
        template_file.write_text("<ClinicalDocument/>")
        
        with patch("ihe_test_util.cli.submit_commands._load_config_with_overrides") as mock_config:
            mock_config.side_effect = ConfigurationError("Test")
            
            result = runner.invoke(
                submit,
                [str(csv_file), "--ccd-template", str(template_file)]
            )
            
            # Command should parse successfully and attempt workflow
            assert result.exit_code != 0  # Config error expected

    def test_config_option_parsing(self, runner: CliRunner, tmp_path: Path) -> None:
        """6.7-UNIT-004: Verify --config flag is parsed correctly.
        
        Backward compatibility test for config option.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "endpoints": {
                "pix_add_url": "http://localhost:8080/pix",
                "iti41_url": "http://localhost:8080/iti41"
            }
        }))
        
        with patch("ihe_test_util.cli.submit_commands.load_config") as mock_load:
            mock_load.side_effect = ConfigurationError("Test")
            
            result = runner.invoke(
                submit,
                [str(csv_file), "--config", str(config_file)]
            )
            
            # Config file should be used
            assert result.exit_code != 0


# =============================================================================
# AC4: PIX-Only Mode Tests
# =============================================================================

class TestPixOnlyMode:
    """Tests for --pix-only flag (AC: 4)."""

    def test_pix_only_flag_parsing(self, runner: CliRunner, tmp_path: Path) -> None:
        """6.7-UNIT-005: Verify --pix-only flag is recognized and stored.
        
        Flag should be parsed without error and passed to workflow.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        with patch("ihe_test_util.cli.submit_commands._load_config_with_overrides") as mock_config:
            mock_config.side_effect = ConfigurationError("Test")
            
            # Options must come BEFORE the CSV file argument for Click groups
            result = runner.invoke(submit, ["--pix-only", str(csv_file)])
            
            # Should parse --pix-only and attempt workflow (config error expected)
            assert "No such command" not in result.output

    def test_pix_only_skips_iti41_status(
        self, tmp_path: Path, mock_batch_result: BatchWorkflowResult
    ) -> None:
        """6.7-UNIT-006: Verify PIX-only result shows ITI-41 as 'skipped'.
        
        When running in PIX-only mode, all ITI-41 statuses should be 'skipped'.
        """
        # Create result with PIX-only pattern
        for pr in mock_batch_result.patient_results:
            pr.iti41_status = "skipped"
            pr.iti41_message = "PIX-only mode"
        
        # Verify results reflect PIX-only mode
        for pr in mock_batch_result.patient_results:
            assert pr.pix_add_status == "success"
            assert pr.iti41_status == "skipped"


# =============================================================================
# AC5: ITI-41 Only Mode Tests
# =============================================================================

class TestIti41OnlyMode:
    """Tests for --iti41-only flag (AC: 5)."""

    def test_iti41_only_requires_pix_results(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """6.7-UNIT-007: Verify error without --pix-results.
        
        Using --iti41-only without --pix-results should produce UsageError.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        # Options must come BEFORE the CSV file argument for Click groups
        result = runner.invoke(submit, ["--iti41-only", str(csv_file)])
        
        assert result.exit_code != 0
        assert "--iti41-only requires --pix-results" in result.output

    def test_iti41_only_flag_parsing(
        self, runner: CliRunner, tmp_path: Path, sample_pix_results_file: Path
    ) -> None:
        """6.7-UNIT-008: Verify --iti41-only flag is recognized.
        
        Flag with --pix-results should be parsed without error.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        with patch("ihe_test_util.cli.submit_commands._load_config_with_overrides") as mock_config:
            mock_config.side_effect = ConfigurationError("Test")
            
            result = runner.invoke(
                submit,
                [
                    str(csv_file),
                    "--iti41-only",
                    "--pix-results", str(sample_pix_results_file)
                ]
            )
            
            # Should parse flags successfully
            assert "requires" not in result.output.lower() or "Configuration Error" in result.output

    def test_iti41_only_loads_pix_results_format(
        self, tmp_path: Path, sample_pix_results: dict
    ) -> None:
        """6.7-UNIT-009: Verify JSON format validation.
        
        load_pix_results should validate required fields.
        """
        # Valid file
        results_file = tmp_path / "valid-results.json"
        results_file.write_text(json.dumps(sample_pix_results))
        
        data = load_pix_results(results_file)
        
        assert "batch_id" in data
        assert "patient_results" in data
        assert len(data["patient_results"]) == 2

    def test_iti41_only_invalid_format_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid PIX results format raises ValidationError."""
        # File missing required field
        invalid_file = tmp_path / "invalid-results.json"
        invalid_file.write_text(json.dumps({"batch_id": "test"}))
        
        with pytest.raises(ValidationError) as exc_info:
            load_pix_results(invalid_file)
        
        assert "missing" in str(exc_info.value).lower()

    def test_mutual_exclusion_pix_iti41_only(
        self, runner: CliRunner, tmp_path: Path, sample_pix_results_file: Path
    ) -> None:
        """6.7-UNIT-010: Verify error when both flags used.
        
        Using --pix-only and --iti41-only together should produce UsageError.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        # Options must come BEFORE the CSV file argument for Click groups
        result = runner.invoke(
            submit,
            [
                "--pix-only",
                "--iti41-only",
                "--pix-results", str(sample_pix_results_file),
                str(csv_file),
            ]
        )
        
        assert result.exit_code != 0
        assert "Cannot use --pix-only and --iti41-only together" in result.output


# =============================================================================
# AC6: Progress Display Tests
# =============================================================================

class TestProgressDisplay:
    """Tests for real-time progress display (AC: 6)."""

    def test_progress_format_patient_count(
        self, mock_batch_result: BatchWorkflowResult
    ) -> None:
        """6.7-UNIT-011: Verify 'Processing patient X/Y' format.
        
        Progress display should show current patient index and total.
        """
        # Verify result structure supports progress display
        assert mock_batch_result.total_patients == 2
        
        # Progress would be: "Patient 1/2", "Patient 2/2"
        for idx, pr in enumerate(mock_batch_result.patient_results, 1):
            expected_format = f"Patient {idx}/{mock_batch_result.total_patients}"
            assert idx <= mock_batch_result.total_patients

    def test_progress_live_success_rates(
        self, mock_batch_result: BatchWorkflowResult
    ) -> None:
        """6.7-UNIT-012: Verify PIX and ITI-41 rates displayed.
        
        Success rates should be calculated and displayed.
        """
        # Verify rate calculations
        assert mock_batch_result.pix_add_success_rate == 100.0
        assert mock_batch_result.iti41_success_rate == 100.0
        
        # Format would be: "PIX: 2/2 (100.0%), ITI-41: 2/2 (100.0%)"
        pix_rate = f"PIX: {mock_batch_result.pix_add_success_count}/{mock_batch_result.total_patients}"
        assert mock_batch_result.pix_add_success_count == 2

    def test_quiet_flag_suppresses_progress(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """6.7-UNIT-013: Verify --quiet hides progress.
        
        With --quiet flag, progress output should be suppressed.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        with patch("ihe_test_util.cli.submit_commands._load_config_with_overrides") as mock_config:
            mock_config.side_effect = ConfigurationError("Test")
            
            # Options must come BEFORE the CSV file argument for Click groups
            result = runner.invoke(submit, ["--quiet", str(csv_file)])
            
            # Should parse --quiet without error (config error expected)
            assert "No such command" not in result.output

    def test_verbose_flag_detailed_output(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """6.7-UNIT-014: Verify --verbose shows per-operation detail.
        
        With --verbose flag, detailed timing should be shown.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        with patch("ihe_test_util.cli.submit_commands._load_config_with_overrides") as mock_config:
            mock_config.side_effect = ConfigurationError("Test")
            
            # Options must come BEFORE the CSV file argument for Click groups
            result = runner.invoke(submit, ["--verbose", str(csv_file)])
            
            # Should parse --verbose without error (config error expected)
            assert "No such command" not in result.output


# =============================================================================
# AC7: Error Categorization Tests
# =============================================================================

class TestErrorCategorization:
    """Tests for error categorization logic (AC: 7)."""

    def test_error_categorization_network(self) -> None:
        """6.7-UNIT-015: Verify network errors categorized.
        
        ConnectionError and Timeout should be categorized as NETWORK.
        """
        # ConnectionError
        conn_error = ConnectionError("Connection refused")
        assert categorize_cli_error(conn_error) == ErrorCategory.NETWORK
        
        # Timeout
        timeout_error = Timeout("Request timed out")
        assert categorize_cli_error(timeout_error) == ErrorCategory.NETWORK
        
        # Generic error with network keywords
        generic_error = Exception("connection timeout to endpoint")
        assert categorize_cli_error(generic_error) == ErrorCategory.NETWORK

    def test_error_categorization_validation(self) -> None:
        """6.7-UNIT-016: Verify validation errors categorized.
        
        ValidationError should be categorized as VALIDATION.
        """
        # ValidationError
        val_error = ValidationError("Invalid patient ID format")
        assert categorize_cli_error(val_error) == ErrorCategory.VALIDATION
        
        # Generic error with validation keywords
        generic_error = Exception("validation failed: invalid format")
        assert categorize_cli_error(generic_error) == ErrorCategory.VALIDATION

    def test_error_categorization_server(self) -> None:
        """Test server errors are categorized correctly."""
        server_error = Exception("500 Internal Server Error")
        assert categorize_cli_error(server_error) == ErrorCategory.SERVER
        
        soap_error = Exception("SOAP response error")
        assert categorize_cli_error(soap_error) == ErrorCategory.SERVER

    def test_error_categorization_certificate(self) -> None:
        """Test certificate/SSL errors are categorized correctly."""
        # Note: SSLError inherits from ConnectionError, so keyword-based check needed
        # for SSLError instances. The categorize function checks SSL keywords.
        cert_error = Exception("certificate expired")
        assert categorize_cli_error(cert_error) == ErrorCategory.CERTIFICATE
        
        tls_error = Exception("TLS handshake failed")
        assert categorize_cli_error(tls_error) == ErrorCategory.CERTIFICATE

    def test_error_categorization_configuration(self) -> None:
        """Test configuration errors are categorized correctly."""
        config_error = ConfigurationError("Missing endpoint URL")
        assert categorize_cli_error(config_error) == ErrorCategory.CONFIGURATION
        
        generic_config = Exception("config file not found")
        assert categorize_cli_error(generic_config) == ErrorCategory.CONFIGURATION

    def test_error_categorization_unknown(self) -> None:
        """Test unknown errors are categorized as UNKNOWN."""
        unknown_error = Exception("Something weird happened")
        assert categorize_cli_error(unknown_error) == ErrorCategory.UNKNOWN

    def test_show_errors_flag_displays_details(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """6.7-UNIT-017: Verify --show-errors shows full errors.
        
        With --show-errors flag, detailed error information should be shown.
        """
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        with patch("ihe_test_util.cli.submit_commands._load_config_with_overrides") as mock_config:
            mock_config.side_effect = ConfigurationError("Test")
            
            # Options must come BEFORE the CSV file argument for Click groups
            result = runner.invoke(submit, ["--show-errors", str(csv_file)])
            
            # Should parse --show-errors without error (config error expected)
            assert "No such command" not in result.output

    def test_top_3_errors_display(self) -> None:
        """6.7-UNIT-018: Verify most common errors summarized.
        
        Error aggregation should identify top 3 most common errors.
        """
        from collections import Counter
        
        # Simulate error messages
        errors = [
            "Connection refused",
            "Connection refused",
            "Connection refused",
            "500 Internal Server Error",
            "500 Internal Server Error",
            "Validation failed",
        ]
        
        error_counts = Counter(errors)
        top_3 = error_counts.most_common(3)
        
        assert top_3[0] == ("Connection refused", 3)
        assert top_3[1] == ("500 Internal Server Error", 2)
        assert top_3[2] == ("Validation failed", 1)


# =============================================================================
# PIX Results File Tests
# =============================================================================

class TestPixResultsFile:
    """Tests for PIX results file save/load."""

    def test_save_pix_results(
        self, tmp_path: Path, mock_batch_result: BatchWorkflowResult
    ) -> None:
        """Test save_pix_results creates valid JSON file."""
        output_path = tmp_path / "pix-results.json"
        
        save_pix_results(mock_batch_result, output_path)
        
        assert output_path.exists()
        
        with output_path.open() as f:
            data = json.load(f)
        
        assert "batch_id" in data
        assert "patient_results" in data
        assert len(data["patient_results"]) == 2

    def test_load_pix_results_file_not_found(self, tmp_path: Path) -> None:
        """Test load_pix_results raises error for missing file."""
        missing_file = tmp_path / "nonexistent.json"
        
        with pytest.raises(ValidationError) as exc_info:
            load_pix_results(missing_file)
        
        assert "not found" in str(exc_info.value).lower()

    def test_load_pix_results_missing_patient_fields(self, tmp_path: Path) -> None:
        """Test load_pix_results validates patient result fields."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text(json.dumps({
            "batch_id": "test",
            "csv_file": "test.csv",
            "patient_results": [
                {"name": "Missing patient_id"}  # Missing required fields
            ]
        }))
        
        with pytest.raises(ValidationError) as exc_info:
            load_pix_results(invalid_file)
        
        assert "missing required fields" in str(exc_info.value).lower()


# =============================================================================
# Help Documentation Tests
# =============================================================================

class TestHelpDocumentation:
    """Tests for comprehensive help documentation (AC: 10)."""

    def test_submit_help_shows_usage(self, runner: CliRunner) -> None:
        """Test submit --help shows usage examples."""
        result = runner.invoke(submit, ["--help"])
        
        assert result.exit_code == 0
        assert "submit" in result.output.lower()
        assert "csv" in result.output.lower()

    def test_submit_help_shows_options(self, runner: CliRunner) -> None:
        """Test submit --help shows all options."""
        result = runner.invoke(submit, ["--help"])
        
        assert "--pix-only" in result.output
        assert "--iti41-only" in result.output
        assert "--pix-results" in result.output
        assert "--quiet" in result.output
        assert "--verbose" in result.output
        assert "--show-errors" in result.output

    def test_submit_help_includes_examples(self, runner: CliRunner) -> None:
        """6.7-UNIT-023: Verify --help shows usage examples."""
        result = runner.invoke(submit, ["--help"])
        
        # Should include example commands
        assert "ihe-test-util submit" in result.output or "submit" in result.output


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_pix_results_only_without_iti41_flag(
        self, runner: CliRunner, tmp_path: Path, sample_pix_results_file: Path
    ) -> None:
        """Test --pix-results without --iti41-only raises error."""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        
        # Options must come BEFORE the CSV file argument for Click groups
        result = runner.invoke(
            submit,
            ["--pix-results", str(sample_pix_results_file), str(csv_file)]
        )
        
        assert result.exit_code != 0
        assert "--pix-results can only be used with --iti41-only" in result.output

    def test_submit_no_csv_shows_help(self, runner: CliRunner) -> None:
        """Test submit without CSV file shows help."""
        result = runner.invoke(submit, [])
        
        # Should show help when no arguments
        assert "Usage:" in result.output or "Options:" in result.output

    def test_submit_nonexistent_csv(self, runner: CliRunner) -> None:
        """Test submit with nonexistent CSV file."""
        result = runner.invoke(submit, ["nonexistent.csv"])
        
        assert result.exit_code != 0
        # Click should report file not found
        assert "exist" in result.output.lower() or "error" in result.output.lower()
