"""Integration tests for CSV validation workflow.

Tests end-to-end validation including CLI integration, error export,
and validation report accuracy.
"""

import json
import logging
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from ihe_test_util.cli.main import cli
from ihe_test_util.csv_parser.parser import parse_csv
from ihe_test_util.csv_parser.validator import export_invalid_rows


class TestCSVValidationWorkflow:
    """Integration tests for complete CSV validation workflow."""

    def test_end_to_end_validation_with_export(self, tmp_path: Path) -> None:
        """Test complete workflow: CSV with errors → validate → export errors → verify export.

        Arrange: Create CSV with mixed valid/invalid data
        Act: Parse and validate, then export errors
        Assert: Exported file contains only error rows with descriptions
        """
        # Arrange: Create CSV with errors
        csv_file = tmp_path / "test_patients.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,phone,email
TEST-001,1.2.3.4,John,Doe,1980-01-01,M,555-555-1234,john@example.com
TEST-002,1.2.3.4,Jane,Smith,1990-02-15,F,invalid-phone,jane@example.com
TEST-001,1.2.3.4,Bob,Jones,1975-03-20,M,555-555-5678,bob@example.com"""
        csv_file.write_text(csv_content)

        error_file = tmp_path / "errors.csv"

        # Act: Validate and export errors
        df, result = parse_csv(csv_file, validate=True)

        assert result is not None
        assert result.has_errors  # Duplicate patient_id
        assert result.has_warnings  # Invalid phone

        export_invalid_rows(df, result, error_file)

        # Assert: Verify exported file
        assert error_file.exists()

        error_df = pd.read_csv(error_file)
        assert len(error_df) == 2  # Two rows with duplicate TEST-001
        assert "error_description" in error_df.columns

        # Verify error descriptions are present
        for desc in error_df["error_description"]:
            assert "Duplicate patient_id" in desc
            assert "TEST-001" in desc

    def test_validation_summary_large_csv(self, tmp_path: Path) -> None:
        """Test validation summary accuracy for larger CSV (100+ rows).

        Arrange: Create CSV with 100 rows including various issues
        Act: Validate the CSV
        Assert: Summary statistics are accurate
        """
        # Arrange: Generate 100 rows with mix of valid/invalid data
        csv_file = tmp_path / "large_patients.csv"

        rows = [
            "patient_id,patient_id_oid,first_name,last_name,dob,gender,phone,email"
        ]

        # 90 valid rows
        for i in range(90):
            rows.append(
                f"TEST-{i:03d},1.2.3.4,First{i},Last{i},1980-01-01,M,555-555-{i:04d},user{i}@example.com"
            )

        # 5 rows with duplicate IDs (errors)
        for i in range(5):
            rows.append(
                f"TEST-DUP,1.2.3.4,Dup{i},User{i},1980-01-01,F,555-555-9999,dup{i}@example.com"
            )

        # 5 rows with invalid phone (warnings)
        for i in range(5):
            rows.append(
                f"TEST-W{i:03d},1.2.3.4,Warn{i},User{i},1980-01-01,M,invalid-phone,warn{i}@example.com"
            )

        csv_file.write_text("\n".join(rows))

        # Act: Validate
        df, result = parse_csv(csv_file, validate=True)

        # Assert: Verify summary statistics
        assert result is not None
        assert result.total_rows == 100
        assert result.has_errors  # Duplicate IDs
        assert result.has_warnings  # Invalid phones
        assert len(result.duplicate_patient_ids) == 1  # One unique duplicate ID
        assert result.duplicate_patient_ids[0] == "TEST-DUP"

        # Verify error count (5 duplicate rows)
        assert result.error_rows == 5

        # Verify warning count (5 invalid phone rows)
        assert result.warning_rows == 5

    def test_cli_validate_command_success(self, tmp_path: Path) -> None:
        """Test CLI validate command with valid CSV returns exit code 0.

        Arrange: Create valid CSV file
        Act: Run CLI validate command
        Assert: Exit code 0, success message displayed
        """
        # Arrange
        csv_file = tmp_path / "valid.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,phone,email
TEST-001,1.2.3.4,John,Doe,1980-01-01,M,555-555-1234,john@example.com
TEST-002,1.2.3.4,Jane,Smith,1990-02-15,F,555-555-5678,jane@example.com"""
        csv_file.write_text(csv_content)

        # Act
        runner = CliRunner()
        result = runner.invoke(cli, ["csv", "validate", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        assert "2 rows processed" in result.output or "valid" in result.output.lower()

    def test_cli_validate_command_with_errors(self, tmp_path: Path) -> None:
        """Test CLI validate command with errors returns exit code 1.

        Arrange: Create CSV with duplicate IDs (errors)
        Act: Run CLI validate command
        Assert: Exit code 1, errors displayed
        """
        # Arrange
        csv_file = tmp_path / "invalid.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
TEST-001,1.2.3.4,John,Doe,1980-01-01,M
TEST-001,1.2.3.4,Jane,Smith,1990-02-15,F"""
        csv_file.write_text(csv_content)

        # Act
        runner = CliRunner()
        result = runner.invoke(cli, ["csv", "validate", str(csv_file)])

        # Assert
        assert result.exit_code == 1
        assert "error" in result.output.lower() or "duplicate" in result.output.lower()

    def test_cli_validate_command_with_warnings_only(self, tmp_path: Path) -> None:
        """Test CLI validate command with only warnings returns exit code 0.

        Arrange: Create CSV with warnings (invalid phone) but no errors
        Act: Run CLI validate command
        Assert: Exit code 0 (warnings don't fail), warnings displayed
        """
        # Arrange
        csv_file = tmp_path / "warnings.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,phone
TEST-001,1.2.3.4,John,Doe,1980-01-01,M,invalid-phone
TEST-002,1.2.3.4,Jane,Smith,1990-02-15,F,555-555-5678"""
        csv_file.write_text(csv_content)

        # Act
        runner = CliRunner()
        result = runner.invoke(cli, ["csv", "validate", str(csv_file)])

        # Assert
        assert result.exit_code == 0  # Warnings don't cause failure
        assert "warning" in result.output.lower()

    def test_cli_validate_with_export_errors_flag(self, tmp_path: Path) -> None:
        """Test CLI validate command with --export-errors flag.

        Arrange: Create CSV with errors
        Act: Run CLI with --export-errors flag
        Assert: Error file created and contains invalid rows
        """
        # Arrange
        csv_file = tmp_path / "test.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
TEST-001,1.2.3.4,John,Doe,1980-01-01,M
TEST-001,1.2.3.4,Jane,Smith,1990-02-15,F"""
        csv_file.write_text(csv_content)

        error_file = tmp_path / "errors.csv"

        # Act
        runner = CliRunner()
        result = runner.invoke(
            cli, ["csv", "validate", str(csv_file), "--export-errors", str(error_file)]
        )

        # Assert
        assert result.exit_code == 1  # Validation failed
        assert error_file.exists()

        error_df = pd.read_csv(error_file)
        assert len(error_df) == 2  # Both duplicate rows exported
        assert "error_description" in error_df.columns

    def test_cli_validate_with_json_output(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test CLI validate command with --json flag.

        Arrange: Create CSV with validation issues
        Act: Run CLI with --json flag
        Assert: Valid JSON output with validation results
        """
        # Arrange
        csv_file = tmp_path / "test.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,phone
TEST-001,1.2.3.4,John,Doe,1980-01-01,M,invalid-phone"""
        csv_file.write_text(csv_content)

        # Act - disable pytest logging capture during CLI invocation to prevent
        # log messages from being mixed with JSON output
        runner = CliRunner()
        with caplog.at_level(logging.CRITICAL):
            result = runner.invoke(cli, ["csv", "validate", str(csv_file), "--json"])

        # Assert
        assert result.exit_code == 0  # Only warnings

        # Verify JSON output - extract just the JSON portion in case any log output leaked through
        output = result.output.strip()
        try:
            output_data = json.loads(output)
        except json.JSONDecodeError:
            # If that fails, try to extract just the JSON portion
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
                output_data = json.loads(json_output)
            else:
                pytest.fail(f"No JSON found in output. Output was: {repr(output)}")
        
        assert "total_rows" in output_data
        assert "valid_rows" in output_data
        assert "error_rows" in output_data
        assert "warning_rows" in output_data
        assert output_data["total_rows"] == 1
        assert output_data["warning_rows"] == 1

    def test_validation_with_missing_optional_fields(self, tmp_path: Path) -> None:
        """Test validation handles missing optional fields gracefully.

        Arrange: Create CSV with only required fields
        Act: Validate
        Assert: No errors, no warnings for missing optional fields
        """
        # Arrange
        csv_file = tmp_path / "minimal.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
TEST-001,1.2.3.4,John,Doe,1980-01-01,M
TEST-002,1.2.3.4,Jane,Smith,1990-02-15,F"""
        csv_file.write_text(csv_content)

        # Act
        df, result = parse_csv(csv_file, validate=True)

        # Assert
        assert result is not None
        assert not result.has_errors
        assert not result.has_warnings  # Missing optional fields don't generate warnings
        assert result.total_rows == 2
        assert result.valid_rows == 2

    def test_validation_disabled_with_validate_false(self, tmp_path: Path) -> None:
        """Test validation can be disabled with validate=False parameter.

        Arrange: Create CSV with duplicate IDs
        Act: Parse with validate=False
        Assert: No validation performed, no errors raised
        """
        # Arrange
        csv_file = tmp_path / "duplicates.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender
TEST-001,1.2.3.4,John,Doe,1980-01-01,M
TEST-001,1.2.3.4,Jane,Smith,1990-02-15,F"""
        csv_file.write_text(csv_content)

        # Act
        df, result = parse_csv(csv_file, validate=False)

        # Assert
        assert result is None  # No validation result when disabled
        assert len(df) == 2  # DataFrame still loaded
