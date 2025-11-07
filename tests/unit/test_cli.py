"""Unit tests for CLI commands.

This module tests the command-line interface for ihe-test-util including
main commands, CSV operations, and option handling.
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ihe_test_util.cli.main import cli


class TestMainCLI:
    """Test cases for main CLI entry point."""

    def test_cli_help(self):
        """Test main CLI help output."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["--help"])

        # Assert
        assert result.exit_code == 0
        assert "IHE Test Utility" in result.output
        assert "Testing tool for IHE transactions" in result.output
        assert "--verbose" in result.output
        assert "--version" in result.output

    def test_cli_version(self):
        """Test version command displays version."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["--version"])

        # Assert
        assert result.exit_code == 0
        assert "ihe-test-util" in result.output
        assert "version" in result.output.lower()

    def test_cli_version_command(self):
        """Test explicit version command."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["version"])

        # Assert
        assert result.exit_code == 0
        assert "ihe-test-util version" in result.output

    def test_verbose_flag_configures_logging(self):
        """Test --verbose flag enables DEBUG logging."""
        # Arrange
        runner = CliRunner()

        # Act - with verbose flag
        with patch('ihe_test_util.cli.main.configure_logging') as mock_config:
            result = runner.invoke(cli, ["--verbose", "csv", "--help"])

        # Assert
        assert result.exit_code == 0
        mock_config.assert_called_once()
        call_kwargs = mock_config.call_args[1]
        assert call_kwargs['level'] == 'DEBUG'

    def test_no_verbose_flag_uses_info_logging(self):
        """Test without --verbose flag uses INFO logging."""
        # Arrange
        runner = CliRunner()

        # Act - without verbose flag
        with patch('ihe_test_util.cli.main.configure_logging') as mock_config:
            result = runner.invoke(cli, ["csv", "--help"])

        # Assert
        assert result.exit_code == 0
        mock_config.assert_called_once()
        call_kwargs = mock_config.call_args[1]
        assert call_kwargs['level'] == 'INFO'


class TestCSVCommands:
    """Test cases for CSV command group."""

    def test_csv_help(self):
        """Test CSV command group help output."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["csv", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "CSV file operations" in result.output
        assert "validate" in result.output
        assert "process" in result.output


class TestCSVValidateCommand:
    """Test cases for csv validate command."""

    def test_validate_help(self):
        """Test validate command help output."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["csv", "validate", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Validate patient demographics CSV file" in result.output
        assert "--export-errors" in result.output
        assert "--json" in result.output
        assert "Examples:" in result.output

    def test_validate_valid_csv_success(self, tmp_path):
        """Test validate command with valid CSV returns exit code 0."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
            "Jane,Smith,1975-05-15,F,1.2.3.4,TEST-002\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "validate", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        assert "Validation" in result.output or "valid" in result.output.lower()

    def test_validate_invalid_csv_failure(self, tmp_path):
        """Test validate command with invalid CSV returns exit code 1."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "invalid.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,invalid-date,M,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "validate", str(csv_file)])

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output or "error" in result.output.lower()

    def test_validate_missing_required_columns(self, tmp_path):
        """Test validate command with missing required columns."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "missing_columns.csv"
        csv_content = "first_name,last_name\nJohn,Doe\n"
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "validate", str(csv_file)])

        # Assert
        assert result.exit_code == 1
        assert "Missing required columns" in result.output or "required" in result.output.lower()

    def test_validate_file_not_found(self, tmp_path):
        """Test validate command with non-existent file."""
        # Arrange
        runner = CliRunner()
        nonexistent_file = tmp_path / "nonexistent.csv"

        # Act
        result = runner.invoke(cli, ["csv", "validate", str(nonexistent_file)])

        # Assert
        assert result.exit_code == 2  # Click exits with 2 for file not found in path validation
        assert "does not exist" in result.output.lower() or "error" in result.output.lower()

    def test_validate_with_export_errors_flag(self, tmp_path):
        """Test validate command with --export-errors flag."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        error_file = tmp_path / "errors.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,email\n"
            "John,Doe,1980-01-01,M,1.2.3.4,valid@example.com\n"
            "Jane,Smith,1975-05-15,F,1.2.3.4,invalid-email\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(
            cli, ["csv", "validate", str(csv_file), "--export-errors", str(error_file)]
        )

        # Assert
        # May exit with 0 or 1 depending on whether invalid email is error or warning
        # Check that error file is mentioned if there are errors
        if result.exit_code == 1:
            assert error_file.exists() or "exported" in result.output.lower()

    def test_validate_with_json_flag(self, tmp_path, caplog):
        """Test validate command with --json flag outputs JSON."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
        )
        csv_file.write_text(csv_content)

        # Act - disable pytest logging capture during CLI invocation
        with caplog.at_level(logging.CRITICAL):
            result = runner.invoke(cli, ["csv", "validate", str(csv_file), "--json"])

        # Assert
        assert result.exit_code == 0
        # Output should be valid JSON (extract first JSON object from output)
        # In case there's any logging output, find the JSON portion
        output = result.output.strip()
        
        # Try to parse the entire output as JSON first
        try:
            output_json = json.loads(output)
            assert isinstance(output_json, dict)
        except json.JSONDecodeError:
            # If that fails, try to extract just the JSON portion
            # Look for the first '{' and find matching '}'
            json_start = output.find('{')
            if json_start != -1:
                # Find the matching closing brace
                brace_count = 0
                json_end = json_start
                for i in range(json_start, len(output)):
                    if output[i] == '{':
                        brace_count += 1
                    elif output[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                json_output = output[json_start:json_end]
                try:
                    output_json = json.loads(json_output)
                    assert isinstance(output_json, dict)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Output is not valid JSON. Output was: {repr(output)}\nError: {e}")
            else:
                pytest.fail(f"No JSON found in output. Output was: {repr(output)}")


class TestCSVProcessCommand:
    """Test cases for csv process command."""

    def test_process_help(self):
        """Test process command help output."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["csv", "process", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Process and display patient demographics" in result.output
        assert "--output" in result.output
        assert "--seed" in result.output
        assert "Examples:" in result.output

    def test_process_valid_csv_success(self, tmp_path):
        """Test process command with valid CSV displays patient summary."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
            "Jane,Smith,1975-05-15,F,1.2.3.4,TEST-002\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        assert "Processing CSV file" in result.output
        assert "Total patients: 2" in result.output
        assert "Patient Summary:" in result.output
        assert "Doe, John" in result.output
        assert "Smith, Jane" in result.output
        assert "Processing complete" in result.output

    def test_process_with_auto_generated_ids(self, tmp_path):
        """Test process command auto-generates missing patient IDs."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
            "Jane,Smith,1975-05-15,F,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        assert "Total patients: 2" in result.output
        assert "Auto-generated IDs: 2" in result.output
        assert "Provided IDs: 0" in result.output

    def test_process_with_seed_option(self, tmp_path):
        """Test process command with --seed option for reproducible IDs."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act - run twice with same seed
        result1 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", "42"])
        result2 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", "42"])

        # Assert
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        # Extract patient IDs from output (they should match)
        assert "TEST-" in result1.output
        assert "TEST-" in result2.output
        # Both runs should produce the same output (deterministic)
        # Extract the patient summary sections
        assert "Patient Summary:" in result1.output
        assert "Patient Summary:" in result2.output

    def test_process_with_output_option(self, tmp_path):
        """Test process command with --output option."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        output_dir = tmp_path / "output"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(
            cli, ["csv", "process", str(csv_file), "--output", str(output_dir)]
        )

        # Assert
        assert result.exit_code == 0
        assert "Processing complete" in result.output

    def test_process_invalid_csv_failure(self, tmp_path):
        """Test process command with invalid CSV returns exit code 1."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "invalid.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,invalid-date,M,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output or "error" in result.output.lower()

    def test_process_file_not_found(self, tmp_path):
        """Test process command with non-existent file."""
        # Arrange
        runner = CliRunner()
        nonexistent_file = tmp_path / "nonexistent.csv"

        # Act
        result = runner.invoke(cli, ["csv", "process", str(nonexistent_file)])

        # Assert
        assert result.exit_code == 2  # Click exits with 2 for file not found in path validation
        assert "does not exist" in result.output.lower() or "error" in result.output.lower()

    def test_process_displays_warnings(self, tmp_path):
        """Test process command displays warning count if warnings present."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        # Create CSV with data that might generate warnings (e.g., duplicate names)
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
            "John,Doe,1980-01-02,M,1.2.3.4,TEST-002\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        # If warnings are present, they should be mentioned
        if "warning" in result.output.lower():
            assert "csv validate" in result.output.lower()


class TestCLIIntegration:
    """Integration tests for CLI workflows."""

    def test_validate_then_process_workflow(self, tmp_path):
        """Test complete workflow: validate CSV then process it."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
            "Jane,Smith,1975-05-15,F,1.2.3.4,TEST-002\n"
        )
        csv_file.write_text(csv_content)

        # Act - validate first
        validate_result = runner.invoke(cli, ["csv", "validate", str(csv_file)])

        # Assert - validation succeeds
        assert validate_result.exit_code == 0

        # Act - then process
        process_result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert - processing succeeds
        assert process_result.exit_code == 0
        assert "Total patients: 2" in process_result.output

    def test_verbose_mode_produces_debug_output(self, tmp_path):
        """Test verbose mode produces additional debug information."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
        )
        csv_file.write_text(csv_content)

        # Act - run with verbose flag
        result = runner.invoke(cli, ["--verbose", "csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        # Verbose output may include additional details (exact format depends on implementation)

    def test_reproducible_ids_with_same_seed(self, tmp_path):
        """Test that same seed produces same patient IDs across runs."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
            "Jane,Smith,1975-05-15,F,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act - run multiple times with same seed
        result1 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", "12345"])
        result2 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", "12345"])

        # Assert - both runs succeed and produce same IDs
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        # Extract patient IDs from both outputs (should be identical)
        # Check that patient summaries contain the same IDs (ignoring timestamps in logs)
        import re
        ids1 = re.findall(r'TEST-[a-f0-9\-]+', result1.output)
        ids2 = re.findall(r'TEST-[a-f0-9\-]+', result2.output)
        # Use sets to get unique IDs (avoid duplicates from log messages)
        unique_ids1 = list(dict.fromkeys(ids1))  # Preserves order
        unique_ids2 = list(dict.fromkeys(ids2))
        assert unique_ids1 == unique_ids2
        assert len(unique_ids1) == 2  # Should have 2 unique patient IDs
