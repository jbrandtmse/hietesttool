"""Comprehensive validation for patient demographics CSV data.

This module provides detailed validation with actionable error messages,
collecting all issues before reporting to help users fix multiple problems at once.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import pandas as pd

from ihe_test_util.logging_audit import get_logger


logger = get_logger(__name__)


class IssueSeverity(Enum):
    """Severity level for validation issues."""

    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationIssue:
    """Individual validation issue with context and suggested fix.

    Attributes:
        row_number: 1-indexed row number (including header) for user readability
        column_name: Name of the column with the issue
        severity: ERROR or WARNING level
        message: Description of what's wrong
        suggestion: Actionable guidance on how to fix the issue
    """

    row_number: int
    column_name: str
    severity: IssueSeverity
    message: str
    suggestion: str


@dataclass
class ValidationResult:
    """Comprehensive validation results with statistics and issues.

    Attributes:
        total_rows: Total number of data rows processed
        valid_rows: Number of rows with no errors (warnings OK)
        error_rows: Number of rows with at least one error
        warning_rows: Number of rows with at least one warning
        duplicate_patient_ids: List of patient IDs that appear multiple times
        missing_oids_count: Count of rows missing patient_id_oid
        all_errors: List of all error-level issues
        all_warnings: List of all warning-level issues
    """

    total_rows: int
    valid_rows: int
    error_rows: int
    warning_rows: int
    duplicate_patient_ids: list[str] = field(default_factory=list)
    missing_oids_count: int = 0
    all_errors: list[ValidationIssue] = field(default_factory=list)
    all_warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any error-level issues exist."""
        return len(self.all_errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if any warning-level issues exist."""
        return len(self.all_warnings) > 0

    def format_report(self) -> str:
        """Format validation results as human-readable report.

        Returns:
            Multi-line string with validation summary and detailed issues
        """
        lines = []
        lines.append("=" * 60)
        lines.append("CSV VALIDATION REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Summary statistics
        lines.append("SUMMARY:")
        lines.append(f"  Total rows: {self.total_rows}")
        lines.append(f"  Valid rows: {self.valid_rows}")
        lines.append(f"  Rows with errors: {self.error_rows}")
        lines.append(f"  Rows with warnings: {self.warning_rows}")
        lines.append("")

        # Batch-level statistics
        if self.duplicate_patient_ids or self.missing_oids_count > 0:
            lines.append("BATCH STATISTICS:")
            if self.duplicate_patient_ids:
                lines.append(
                    f"  Duplicate patient IDs: {len(self.duplicate_patient_ids)} "
                    f"({', '.join(self.duplicate_patient_ids[:5])}"
                    f"{'...' if len(self.duplicate_patient_ids) > 5 else ''})"
                )
            if self.missing_oids_count > 0:
                lines.append(f"  Missing OIDs: {self.missing_oids_count}")
            lines.append("")

        # Errors section
        if self.all_errors:
            lines.append(f"ERRORS ({len(self.all_errors)}):")
            for error in self.all_errors[:20]:  # Limit display to first 20
                lines.append(
                    f"  Row {error.row_number} [{error.column_name}]: {error.message}"
                )
                lines.append(f"    → {error.suggestion}")
            if len(self.all_errors) > 20:
                lines.append(f"  ... and {len(self.all_errors) - 20} more errors")
            lines.append("")

        # Warnings section
        if self.all_warnings:
            lines.append(f"WARNINGS ({len(self.all_warnings)}):")
            for warning in self.all_warnings[:20]:  # Limit display to first 20
                lines.append(
                    f"  Row {warning.row_number} [{warning.column_name}]: {warning.message}"
                )
                lines.append(f"    → {warning.suggestion}")
            if len(self.all_warnings) > 20:
                lines.append(f"  ... and {len(self.all_warnings) - 20} more warnings")
            lines.append("")

        # Final result
        lines.append("=" * 60)
        if not self.has_errors and not self.has_warnings:
            lines.append("RESULT: ✓ All validations passed")
        elif not self.has_errors:
            lines.append("RESULT: ✓ Validation passed with warnings")
        else:
            lines.append("RESULT: ✗ Validation failed - please fix errors above")
        lines.append("=" * 60)

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Export validation results as structured dictionary for JSON serialization.

        Returns:
            Dictionary with all validation results
        """
        return {
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "error_rows": self.error_rows,
            "warning_rows": self.warning_rows,
            "duplicate_patient_ids": self.duplicate_patient_ids,
            "missing_oids_count": self.missing_oids_count,
            "errors": [
                {
                    "row_number": e.row_number,
                    "column_name": e.column_name,
                    "severity": e.severity.value,
                    "message": e.message,
                    "suggestion": e.suggestion,
                }
                for e in self.all_errors
            ],
            "warnings": [
                {
                    "row_number": w.row_number,
                    "column_name": w.column_name,
                    "severity": w.severity.value,
                    "message": w.message,
                    "suggestion": w.suggestion,
                }
                for w in self.all_warnings
            ],
        }


# Validation regex patterns
PHONE_PATTERN = re.compile(r"^(\d{3}-\d{3}-\d{4}|\(\d{3}\) \d{3}-\d{4})$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
SSN_PATTERN = re.compile(r"^\d{3}-\d{2}-\d{4}$")
ZIP_PATTERN = re.compile(r"^\d{5}(-\d{4})?$")

# Age validation thresholds
MIN_REASONABLE_AGE = 0
MAX_REASONABLE_AGE = 120


def validate_demographics(df: pd.DataFrame) -> ValidationResult:
    """Perform comprehensive validation on patient demographics DataFrame.

    Validates phone formats, email formats, duplicate patient IDs, date issues,
    and other data quality problems. Collects all errors and warnings before
    returning results (not fail-fast).

    Args:
        df: pandas DataFrame with patient demographics from CSV parser.
            Must include required columns: first_name, last_name, dob, gender,
            patient_id_oid. Optional columns: phone, email, ssn, zip, patient_id, etc.

    Returns:
        ValidationResult containing all errors, warnings, and statistics

    Raises:
        ValueError: If DataFrame is empty or missing required columns
    """
    logger.info("Validation started")

    # Validate DataFrame structure
    if df.empty:
        raise ValueError("DataFrame is empty - no data to validate")

    required_columns = ["first_name", "last_name", "dob", "gender", "patient_id_oid"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"DataFrame missing required columns: {', '.join(missing_columns)}"
        )

    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # Field-level validation (row by row)
    logger.debug("Validating field-level data quality")
    for idx, row in df.iterrows():
        row_num = idx + 2  # +2 for 1-indexed + header row

        # Validate phone number format
        if pd.notna(row.get("phone")) and str(row["phone"]).strip() != "":
            phone_value = str(row["phone"]).strip()
            if not PHONE_PATTERN.match(phone_value):
                warnings.append(
                    ValidationIssue(
                        row_number=row_num,
                        column_name="phone",
                        severity=IssueSeverity.WARNING,
                        message=f"Phone format may be invalid: {phone_value}",
                        suggestion="Recommended formats: 555-555-1234 or (555) 555-1234",
                    )
                )

        # Validate email format
        if pd.notna(row.get("email")) and str(row["email"]).strip() != "":
            email_value = str(row["email"]).strip()
            if not EMAIL_PATTERN.match(email_value):
                warnings.append(
                    ValidationIssue(
                        row_number=row_num,
                        column_name="email",
                        severity=IssueSeverity.WARNING,
                        message=f"Email format appears invalid: {email_value}",
                        suggestion="Ensure email has format: user@domain.com",
                    )
                )

        # Validate SSN format
        if pd.notna(row.get("ssn")) and str(row["ssn"]).strip() != "":
            ssn_value = str(row["ssn"]).strip()
            if not SSN_PATTERN.match(ssn_value):
                warnings.append(
                    ValidationIssue(
                        row_number=row_num,
                        column_name="ssn",
                        severity=IssueSeverity.WARNING,
                        message=f"SSN format invalid: {ssn_value}",
                        suggestion="Use format: 123-45-6789",
                    )
                )

        # Validate ZIP code format
        if pd.notna(row.get("zip")) and str(row["zip"]).strip() != "":
            zip_value = str(row["zip"]).strip()
            if not ZIP_PATTERN.match(zip_value):
                warnings.append(
                    ValidationIssue(
                        row_number=row_num,
                        column_name="zip",
                        severity=IssueSeverity.WARNING,
                        message=f"ZIP code format invalid: {zip_value}",
                        suggestion="Use format: 12345 or 12345-6789",
                    )
                )

        # Validate date of birth (future dates, unreasonable ages)
        dob_value = row.get("dob")
        if pd.notna(dob_value) and str(dob_value).strip() != "":
            try:
                # Parse date (assume YYYY-MM-DD format)
                parsed_dob = pd.to_datetime(dob_value, format="%Y-%m-%d")
                today = datetime.now(timezone.utc).date()

                # Check for future date
                if parsed_dob.date() > today:
                    warnings.append(
                        ValidationIssue(
                            row_number=row_num,
                            column_name="dob",
                            severity=IssueSeverity.WARNING,
                            message=f"Future date of birth: {dob_value}",
                            suggestion="Verify date is correct (YYYY-MM-DD format)",
                        )
                    )
                else:
                    # Only check age reasonableness if date is not in future
                    # Calculate age and check reasonableness
                    age = (today - parsed_dob.date()).days // 365
                    if age < MIN_REASONABLE_AGE:
                        warnings.append(
                            ValidationIssue(
                                row_number=row_num,
                                column_name="dob",
                                severity=IssueSeverity.WARNING,
                                message=f"Age appears negative ({age} years)",
                                suggestion="Verify date is in YYYY-MM-DD format",
                            )
                        )
                    elif age > MAX_REASONABLE_AGE:
                        warnings.append(
                            ValidationIssue(
                                row_number=row_num,
                                column_name="dob",
                                severity=IssueSeverity.WARNING,
                                message=f"Age appears unreasonable ({age} years old)",
                                suggestion="Verify date is correct",
                            )
                        )

            except (ValueError, TypeError):
                # Date parsing errors are already caught by parser.py
                # No need to duplicate here
                pass

        # Check for address without city/state
        has_address = pd.notna(row.get("address")) and str(row["address"]).strip() != ""
        has_city = pd.notna(row.get("city")) and str(row["city"]).strip() != ""
        has_state = pd.notna(row.get("state")) and str(row["state"]).strip() != ""

        if has_address and not (has_city or has_state):
            warnings.append(
                ValidationIssue(
                    row_number=row_num,
                    column_name="address",
                    severity=IssueSeverity.WARNING,
                    message="Address provided without city or state",
                    suggestion="Consider adding city and state for complete address",
                )
            )

    # Batch-level validation
    logger.debug("Validating batch-level data quality")

    # Check for duplicate patient IDs
    if "patient_id" in df.columns:
        # Filter out NaN values before checking duplicates
        non_null_ids = df["patient_id"].dropna()
        if len(non_null_ids) > 0:
            duplicate_mask = non_null_ids.duplicated(keep=False)
            duplicate_ids = non_null_ids[duplicate_mask].unique().tolist()

            if duplicate_ids:
                logger.debug(f"Found {len(duplicate_ids)} duplicate patient IDs")
                # Record error for each row with duplicate ID
                for dup_id in duplicate_ids:
                    rows_with_dup = df[df["patient_id"] == dup_id].index.tolist()
                    for row_idx in rows_with_dup:
                        row_num = row_idx + 2
                        errors.append(
                            ValidationIssue(
                                row_number=row_num,
                                column_name="patient_id",
                                severity=IssueSeverity.ERROR,
                                message=f"Duplicate patient_id found: {dup_id}",
                                suggestion="Ensure all patient IDs are unique or leave empty for auto-generation",
                            )
                        )
        else:
            duplicate_ids = []
    else:
        duplicate_ids = []

    # Check for duplicate names (warning only)
    duplicate_names_mask = df[["first_name", "last_name"]].duplicated(keep=False)
    if duplicate_names_mask.any():
        logger.debug("Found duplicate names (may be legitimate)")
        duplicate_name_rows = df[duplicate_names_mask].index.tolist()
        for row_idx in duplicate_name_rows:
            row_num = row_idx + 2
            first_name = df.at[row_idx, "first_name"]
            last_name = df.at[row_idx, "last_name"]
            warnings.append(
                ValidationIssue(
                    row_number=row_num,
                    column_name="first_name,last_name",
                    severity=IssueSeverity.WARNING,
                    message=f"Duplicate name found: {first_name} {last_name}",
                    suggestion="Verify this is intentional (legitimate duplicates are OK)",
                )
            )

    # Count missing OIDs
    missing_oids_count = df["patient_id_oid"].isna().sum()
    if missing_oids_count > 0:
        logger.debug(f"Found {missing_oids_count} rows with missing patient_id_oid")

    # Calculate statistics
    error_row_numbers = set(e.row_number for e in errors)
    warning_row_numbers = set(w.row_number for w in warnings)
    error_rows = len(error_row_numbers)
    warning_rows = len(warning_row_numbers)
    valid_rows = len(df) - error_rows

    result = ValidationResult(
        total_rows=len(df),
        valid_rows=valid_rows,
        error_rows=error_rows,
        warning_rows=warning_rows,
        duplicate_patient_ids=duplicate_ids,
        missing_oids_count=int(missing_oids_count),
        all_errors=errors,
        all_warnings=warnings,
    )

    logger.info(f"Validation errors found: {len(errors)}")
    if warnings:
        logger.info(f"Validation warnings: {len(warnings)}")

    return result


def export_invalid_rows(
    df: pd.DataFrame, result: ValidationResult, output_path: Path
) -> None:
    """Export rows with validation errors to separate CSV file.

    Args:
        df: Original DataFrame with all patient data
        result: ValidationResult containing error information
        output_path: Path where error CSV should be written

    Raises:
        ValueError: If no errors exist in ValidationResult
        FileNotFoundError: If output_path parent directory doesn't exist
    """
    logger.info(f"Exporting invalid rows to {output_path}")

    if not result.has_errors:
        raise ValueError("No validation errors to export")

    if not output_path.parent.exists():
        raise FileNotFoundError(
            f"Output directory does not exist: {output_path.parent}"
        )

    # Get unique row numbers with errors
    error_row_numbers = set(e.row_number for e in result.all_errors)

    # Convert to 0-indexed for DataFrame (row_num is 1-indexed + header)
    error_indices = [r - 2 for r in error_row_numbers]

    # Filter DataFrame to error rows
    error_df = df.iloc[error_indices].copy()

    # Add error_description column
    error_descriptions = []
    for idx in error_indices:
        row_num = idx + 2
        row_errors = [e for e in result.all_errors if e.row_number == row_num]
        desc = "; ".join([f"{e.column_name}: {e.message}" for e in row_errors])
        error_descriptions.append(desc)

    error_df["error_description"] = error_descriptions

    # Export to CSV
    error_df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info(f"Exported {len(error_df)} invalid rows to {output_path}")
