"""Unit tests for CSV validator module.

Tests comprehensive validation logic including field-level validation,
batch-level validation, error collection, and export functionality.
"""

import pandas as pd
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from ihe_test_util.csv_parser.validator import (
    validate_demographics,
    export_invalid_rows,
    ValidationResult,
    ValidationIssue,
    IssueSeverity,
)


class TestValidateDemographics:
    """Test suite for validate_demographics function."""

    def test_validate_demographics_all_valid(self):
        """Test validation with completely valid data (no errors, no warnings)."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "phone": "555-555-1234",
                    "email": "john@example.com",
                    "ssn": "123-45-6789",
                    "zip": "12345",
                    "address": "123 Main St",
                    "city": "Boston",
                    "state": "MA",
                }
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.total_rows == 1
        assert result.valid_rows == 1
        assert result.error_rows == 0
        assert result.warning_rows == 0
        assert not result.has_errors
        assert not result.has_warnings
        assert len(result.all_errors) == 0
        assert len(result.all_warnings) == 0

    def test_validate_demographics_multiple_valid_rows(self):
        """Test validation with multiple valid rows."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                },
                {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "dob": "1990-05-15",
                    "gender": "F",
                    "patient_id": "TEST-002",
                    "patient_id_oid": "1.2.3.4",
                },
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.total_rows == 2
        assert result.valid_rows == 2
        assert result.error_rows == 0
        assert result.warning_rows == 0
        assert not result.has_errors
        assert not result.has_warnings

    def test_validate_demographics_future_dob_warning(self):
        """Test that future date of birth generates warning."""
        # Arrange
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        df = pd.DataFrame(
            [
                {
                    "first_name": "Future",
                    "last_name": "Baby",
                    "dob": future_date,
                    "gender": "U",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                }
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.warning_rows == 1
        assert len(result.all_warnings) == 1
        assert result.all_warnings[0].row_number == 2  # Row 2 (1-indexed + header)
        assert result.all_warnings[0].column_name == "dob"
        assert result.all_warnings[0].severity == IssueSeverity.WARNING
        assert "Future date of birth" in result.all_warnings[0].message
        assert future_date in result.all_warnings[0].message
        assert not result.has_errors  # Future DOB is warning, not error
        assert result.has_warnings

    def test_validate_demographics_unreasonable_age_warning(self):
        """Test that unreasonable age (>120 years) generates warning."""
        # Arrange
        old_date = (datetime.now() - timedelta(days=125 * 365)).strftime("%Y-%m-%d")
        df = pd.DataFrame(
            [
                {
                    "first_name": "Very",
                    "last_name": "Old",
                    "dob": old_date,
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                }
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.warning_rows == 1
        assert len(result.all_warnings) == 1
        assert "unreasonable" in result.all_warnings[0].message.lower()
        assert result.all_warnings[0].column_name == "dob"

    def test_validate_demographics_invalid_phone_warning(self):
        """Test that invalid phone format generates warning."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "phone": "555-1234",  # Invalid format
                }
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.warning_rows == 1
        assert len(result.all_warnings) == 1
        assert result.all_warnings[0].column_name == "phone"
        assert result.all_warnings[0].severity == IssueSeverity.WARNING
        assert "Phone format may be invalid" in result.all_warnings[0].message
        assert "555-1234" in result.all_warnings[0].message
        assert "555-555-1234" in result.all_warnings[0].suggestion

    def test_validate_demographics_valid_phone_formats(self):
        """Test that both valid phone formats are accepted."""
        # Arrange - Test both formats: 555-555-1234 and (555) 555-1234
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "phone": "555-555-1234",
                },
                {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "dob": "1990-01-01",
                    "gender": "F",
                    "patient_id": "TEST-002",
                    "patient_id_oid": "1.2.3.4",
                    "phone": "(555) 555-1234",
                },
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert not result.has_warnings
        assert not result.has_errors

    def test_validate_demographics_invalid_email_warning(self):
        """Test that invalid email format generates warning."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "email": "notanemail",  # Invalid format
                }
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.warning_rows == 1
        assert len(result.all_warnings) == 1
        assert result.all_warnings[0].column_name == "email"
        assert "Email format appears invalid" in result.all_warnings[0].message
        assert "notanemail" in result.all_warnings[0].message

    def test_validate_demographics_invalid_ssn_warning(self):
        """Test that invalid SSN format generates warning."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "ssn": "123456789",  # Invalid format (missing dashes)
                }
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.warning_rows == 1
        assert len(result.all_warnings) == 1
        assert result.all_warnings[0].column_name == "ssn"
        assert "SSN format invalid" in result.all_warnings[0].message
        assert "123-45-6789" in result.all_warnings[0].suggestion

    def test_validate_demographics_invalid_zip_warning(self):
        """Test that invalid ZIP code format generates warning."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "zip": "1234",  # Invalid format (too short)
                }
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.warning_rows == 1
        assert len(result.all_warnings) == 1
        assert result.all_warnings[0].column_name == "zip"
        assert "ZIP code format invalid" in result.all_warnings[0].message

    def test_validate_demographics_valid_zip_formats(self):
        """Test that both valid ZIP formats are accepted."""
        # Arrange - Test both formats: 12345 and 12345-6789
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "zip": "12345",
                },
                {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "dob": "1990-01-01",
                    "gender": "F",
                    "patient_id": "TEST-002",
                    "patient_id_oid": "1.2.3.4",
                    "zip": "12345-6789",
                },
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert not result.has_warnings
        assert not result.has_errors

    def test_validate_demographics_address_without_city_state_warning(self):
        """Test that address without city/state generates warning."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "address": "123 Main St",
                    # No city or state
                }
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.warning_rows == 1
        assert len(result.all_warnings) == 1
        assert result.all_warnings[0].column_name == "address"
        assert "without city or state" in result.all_warnings[0].message

    def test_validate_demographics_duplicate_patient_ids_error(self):
        """Test that duplicate patient IDs generate errors."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                },
                {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "dob": "1990-01-01",
                    "gender": "F",
                    "patient_id": "TEST-001",  # Duplicate!
                    "patient_id_oid": "1.2.3.4",
                },
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.has_errors
        assert result.error_rows == 2  # Both rows have the duplicate ID
        assert len(result.all_errors) == 2
        assert all(e.column_name == "patient_id" for e in result.all_errors)
        assert all(e.severity == IssueSeverity.ERROR for e in result.all_errors)
        assert all("Duplicate patient_id found: TEST-001" in e.message for e in result.all_errors)
        assert "TEST-001" in result.duplicate_patient_ids

    def test_validate_demographics_duplicate_names_warning(self):
        """Test that duplicate names generate warnings (may be legitimate)."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Smith",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                },
                {
                    "first_name": "John",
                    "last_name": "Smith",
                    "dob": "1990-01-01",
                    "gender": "M",
                    "patient_id": "TEST-002",
                    "patient_id_oid": "1.2.3.4",
                },
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.has_warnings
        assert not result.has_errors  # Names are warnings, not errors
        assert result.warning_rows == 2  # Both rows flagged
        assert len(result.all_warnings) == 2
        assert all("Duplicate name found" in w.message for w in result.all_warnings)
        assert all("John Smith" in w.message for w in result.all_warnings)

    def test_validate_demographics_collects_all_errors(self):
        """Test that all errors are collected before returning (not fail-fast)."""
        # Arrange - Create multiple rows with different issues
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "DUP-001",
                    "patient_id_oid": "1.2.3.4",
                    "phone": "invalid-phone",
                    "email": "invalid-email",
                },
                {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "dob": "1990-01-01",
                    "gender": "F",
                    "patient_id": "DUP-001",  # Duplicate
                    "patient_id_oid": "1.2.3.4",
                    "ssn": "bad-ssn",
                },
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert - Should have collected multiple errors and warnings
        assert result.has_errors  # Duplicate IDs are errors
        assert result.has_warnings  # Invalid formats are warnings
        assert len(result.all_errors) == 2  # Both duplicate ID rows
        assert len(result.all_warnings) >= 3  # phone, email, ssn issues

    def test_validate_demographics_empty_dataframe_raises_error(self):
        """Test that empty DataFrame raises ValueError."""
        # Arrange
        df = pd.DataFrame()

        # Act & Assert
        with pytest.raises(ValueError, match="DataFrame is empty"):
            validate_demographics(df)

    def test_validate_demographics_missing_required_columns_raises_error(self):
        """Test that missing required columns raises ValueError."""
        # Arrange
        df = pd.DataFrame([{"first_name": "John", "last_name": "Doe"}])

        # Act & Assert
        with pytest.raises(ValueError, match="missing required columns"):
            validate_demographics(df)

    def test_validate_demographics_summary_statistics(self):
        """Test that validation summary statistics are accurate."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "Valid",
                    "last_name": "Patient",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                },
                {
                    "first_name": "Warning",
                    "last_name": "Patient",
                    "dob": "1990-01-01",
                    "gender": "F",
                    "patient_id": "TEST-002",
                    "patient_id_oid": "1.2.3.4",
                    "phone": "bad-phone",
                },
                {
                    "first_name": "Error",
                    "last_name": "Patient",
                    "dob": "2000-01-01",
                    "gender": "M",
                    "patient_id": "TEST-002",  # Duplicate!
                    "patient_id_oid": "1.2.3.4",
                },
            ]
        )

        # Act
        result = validate_demographics(df)

        # Assert
        assert result.total_rows == 3
        assert result.error_rows == 2  # Rows 2 and 3 (duplicate ID)
        assert result.warning_rows == 1  # Row 2 (bad phone)
        assert result.valid_rows == 1  # Row 1


class TestValidationResult:
    """Test suite for ValidationResult dataclass methods."""

    def test_format_report_all_valid(self):
        """Test format_report with all valid data."""
        # Arrange
        result = ValidationResult(
            total_rows=5,
            valid_rows=5,
            error_rows=0,
            warning_rows=0,
        )

        # Act
        report = result.format_report()

        # Assert
        assert "Total rows: 5" in report
        assert "Valid rows: 5" in report
        assert "✓ All validations passed" in report
        assert "ERRORS" not in report
        assert "WARNINGS" not in report

    def test_format_report_with_warnings(self):
        """Test format_report with warnings."""
        # Arrange
        result = ValidationResult(
            total_rows=2,
            valid_rows=2,
            error_rows=0,
            warning_rows=1,
            all_warnings=[
                ValidationIssue(
                    row_number=2,
                    column_name="phone",
                    severity=IssueSeverity.WARNING,
                    message="Phone format may be invalid",
                    suggestion="Use format: 555-555-1234",
                )
            ],
        )

        # Act
        report = result.format_report()

        # Assert
        assert "WARNINGS (1)" in report
        assert "Row 2 [phone]" in report
        assert "Phone format may be invalid" in report
        assert "Use format: 555-555-1234" in report
        assert "✓ Validation passed with warnings" in report

    def test_format_report_with_errors(self):
        """Test format_report with errors."""
        # Arrange
        result = ValidationResult(
            total_rows=2,
            valid_rows=1,
            error_rows=1,
            warning_rows=0,
            duplicate_patient_ids=["TEST-001"],
            all_errors=[
                ValidationIssue(
                    row_number=2,
                    column_name="patient_id",
                    severity=IssueSeverity.ERROR,
                    message="Duplicate patient_id found: TEST-001",
                    suggestion="Ensure all patient IDs are unique",
                )
            ],
        )

        # Act
        report = result.format_report()

        # Assert
        assert "ERRORS (1)" in report
        assert "Row 2 [patient_id]" in report
        assert "Duplicate patient_id found: TEST-001" in report
        assert "✗ Validation failed" in report

    def test_to_dict_structure(self):
        """Test to_dict exports proper JSON structure."""
        # Arrange
        result = ValidationResult(
            total_rows=3,
            valid_rows=2,
            error_rows=1,
            warning_rows=1,
            duplicate_patient_ids=["TEST-001"],
            missing_oids_count=0,
            all_errors=[
                ValidationIssue(
                    row_number=2,
                    column_name="patient_id",
                    severity=IssueSeverity.ERROR,
                    message="Duplicate ID",
                    suggestion="Fix it",
                )
            ],
            all_warnings=[
                ValidationIssue(
                    row_number=3,
                    column_name="phone",
                    severity=IssueSeverity.WARNING,
                    message="Bad phone",
                    suggestion="Fix phone",
                )
            ],
        )

        # Act
        result_dict = result.to_dict()

        # Assert: Verify flat structure
        assert result_dict["total_rows"] == 3
        assert result_dict["valid_rows"] == 2
        assert result_dict["error_rows"] == 1
        assert result_dict["warning_rows"] == 1
        assert result_dict["duplicate_patient_ids"] == ["TEST-001"]
        assert result_dict["missing_oids_count"] == 0
        assert "errors" in result_dict
        assert len(result_dict["errors"]) == 1
        assert result_dict["errors"][0]["row_number"] == 2
        assert result_dict["errors"][0]["column_name"] == "patient_id"
        assert result_dict["errors"][0]["severity"] == "error"
        assert "warnings" in result_dict
        assert len(result_dict["warnings"]) == 1
        assert result_dict["warnings"][0]["row_number"] == 3
        assert result_dict["warnings"][0]["severity"] == "warning"


class TestExportInvalidRows:
    """Test suite for export_invalid_rows function."""

    def test_export_invalid_rows_success(self, tmp_path):
        """Test successful export of invalid rows to CSV."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "Valid",
                    "last_name": "Patient",
                    "dob": "1980-01-01",
                    "patient_id": "TEST-001",
                },
                {
                    "first_name": "Invalid",
                    "last_name": "Patient",
                    "dob": "1990-01-01",
                    "patient_id": "TEST-001",  # Duplicate
                },
            ]
        )
        result = ValidationResult(
            total_rows=2,
            valid_rows=1,
            error_rows=1,
            warning_rows=0,
            duplicate_patient_ids=["TEST-001"],
            all_errors=[
                ValidationIssue(
                    row_number=2,
                    column_name="patient_id",
                    severity=IssueSeverity.ERROR,
                    message="Duplicate patient_id found: TEST-001",
                    suggestion="Ensure all patient IDs are unique",
                ),
                ValidationIssue(
                    row_number=3,
                    column_name="patient_id",
                    severity=IssueSeverity.ERROR,
                    message="Duplicate patient_id found: TEST-001",
                    suggestion="Ensure all patient IDs are unique",
                ),
            ],
        )
        output_path = tmp_path / "errors.csv"

        # Act
        export_invalid_rows(df, result, output_path)

        # Assert
        assert output_path.exists()
        exported_df = pd.read_csv(output_path)
        assert len(exported_df) == 2  # Both rows with duplicate ID
        assert "error_description" in exported_df.columns
        assert all("Duplicate patient_id found" in desc for desc in exported_df["error_description"])

    def test_export_invalid_rows_no_errors_raises_error(self, tmp_path):
        """Test that exporting with no errors raises ValueError."""
        # Arrange
        df = pd.DataFrame([{"first_name": "John", "last_name": "Doe"}])
        result = ValidationResult(
            total_rows=1,
            valid_rows=1,
            error_rows=0,
            warning_rows=0,
        )
        output_path = tmp_path / "errors.csv"

        # Act & Assert
        with pytest.raises(ValueError, match="No validation errors to export"):
            export_invalid_rows(df, result, output_path)

    def test_export_invalid_rows_nonexistent_directory_raises_error(self):
        """Test that exporting to nonexistent directory raises error."""
        # Arrange
        df = pd.DataFrame([{"first_name": "John"}])
        result = ValidationResult(
            total_rows=1,
            valid_rows=0,
            error_rows=1,
            warning_rows=0,
            all_errors=[
                ValidationIssue(
                    row_number=2,
                    column_name="test",
                    severity=IssueSeverity.ERROR,
                    message="Error",
                    suggestion="Fix",
                )
            ],
        )
        output_path = Path("/nonexistent/directory/errors.csv")

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Output directory does not exist"):
            export_invalid_rows(df, result, output_path)

    def test_export_invalid_rows_preserves_original_columns(self, tmp_path):
        """Test that exported CSV preserves all original columns."""
        # Arrange
        df = pd.DataFrame(
            [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "dob": "1980-01-01",
                    "gender": "M",
                    "patient_id": "TEST-001",
                    "patient_id_oid": "1.2.3.4",
                    "phone": "555-555-1234",
                }
            ]
        )
        result = ValidationResult(
            total_rows=1,
            valid_rows=0,
            error_rows=1,
            warning_rows=0,
            all_errors=[
                ValidationIssue(
                    row_number=2,
                    column_name="patient_id",
                    severity=IssueSeverity.ERROR,
                    message="Some error",
                    suggestion="Fix it",
                )
            ],
        )
        output_path = tmp_path / "errors.csv"

        # Act
        export_invalid_rows(df, result, output_path)

        # Assert
        exported_df = pd.read_csv(output_path)
        original_columns = set(df.columns)
        exported_columns = set(exported_df.columns) - {"error_description"}
        assert original_columns == exported_columns
