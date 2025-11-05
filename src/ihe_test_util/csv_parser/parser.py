"""CSV parser for patient demographics.

This module provides functionality to parse and validate patient demographics
from CSV files for use in IHE transaction testing.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from ihe_test_util.csv_parser.id_generator import generate_patient_id, reset_generated_ids
from ihe_test_util.csv_parser.validator import validate_demographics, ValidationResult
from ihe_test_util.utils.exceptions import ValidationError


logger = logging.getLogger(__name__)

# Required CSV columns
REQUIRED_COLUMNS = ["first_name", "last_name", "dob", "gender", "patient_id_oid"]

# Optional CSV columns
OPTIONAL_COLUMNS = [
    "patient_id",
    "mrn",
    "ssn",
    "address",
    "city",
    "state",
    "zip",
    "phone",
    "email",
]

# Valid gender values (case-insensitive)
VALID_GENDERS = ["M", "F", "O", "U"]

# Minimum reasonable birth year for validation
MIN_BIRTH_YEAR = 1900


def parse_csv(
    file_path: Path, seed: Optional[int] = None, validate: bool = True
) -> tuple[pd.DataFrame, Optional[ValidationResult]]:
    """Parse patient demographics from CSV file.

    Validates required columns, data formats, and returns a pandas DataFrame
    with validated patient demographics ready for IHE transaction processing.
    Automatically generates patient IDs for rows where patient_id is missing.

    Args:
        file_path: Path to CSV file containing patient data
        seed: Optional random seed for deterministic patient ID generation.
              When provided, enables reproducible test data generation with
              the same sequence of auto-generated IDs across runs.
        validate: If True, runs comprehensive validation after basic parsing.
                  Warnings are logged but don't fail parsing. Errors raise
                  ValidationError. If False, skips comprehensive validation.

    Returns:
        Tuple of (DataFrame, ValidationResult):
        - DataFrame with validated patient demographics. All validation
          rules have been applied and data is ready for downstream processing.
          Any missing patient_id values will be auto-generated in TEST-{UUID} format.
        - ValidationResult with comprehensive validation details, or None if
          validate=False

    Raises:
        ValidationError: If required columns missing, data invalid, or format errors
        FileNotFoundError: If CSV file does not exist
    """
    logger.info(f"Loading CSV from {file_path}")
    
    # Reset generated IDs tracking for this batch
    reset_generated_ids()
    
    if seed is not None:
        logger.info(f"Using seed {seed} for deterministic ID generation")

    # Check file exists
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    # Load CSV with UTF-8 encoding
    try:
        df = pd.read_csv(file_path, encoding="utf-8")
    except Exception as e:
        raise ValidationError(
            f"Failed to read CSV file {file_path}. Ensure file is valid CSV with UTF-8 encoding. Error: {e}"
        ) from e

    logger.info("Validating CSV structure and data")

    # Collect all validation errors
    errors: list[str] = []

    # Validate required columns are present
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        errors.append(
            f"Missing required columns: {', '.join(missing_columns)}. "
            f"Required columns are: {', '.join(REQUIRED_COLUMNS)}"
        )

    # Check for unknown columns (log warning, don't fail)
    all_valid_columns = set(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    unknown_columns = [col for col in df.columns if col not in all_valid_columns]
    if unknown_columns:
        logger.warning(
            f"CSV contains unknown columns that will be ignored: {', '.join(unknown_columns)}"
        )

    # If required columns are missing, raise error immediately
    # (can't continue validation without required columns)
    if missing_columns:
        raise ValidationError(
            "CSV validation failed:\n  - " + "\n  - ".join(errors)
        )

    # Validate date of birth column
    dob_errors = _validate_dob_column(df)
    errors.extend(dob_errors)

    # Validate gender column
    gender_errors = _validate_gender_column(df)
    errors.extend(gender_errors)

    # If any validation errors found, raise comprehensive error
    if errors:
        error_message = (
            f"Found {len(errors)} validation error(s) in CSV:\n  - "
            + "\n  - ".join(errors)
        )
        raise ValidationError(error_message)

    # Generate patient IDs for rows with missing patient_id values
    _generate_missing_patient_ids(df, seed)

    logger.info(f"Successfully parsed {len(df)} patient record(s)")

    # Run comprehensive validation if requested
    validation_result = None
    if validate:
        logger.info("Running comprehensive validation")
        validation_result = validate_demographics(df)

        # Log all warnings
        for warning in validation_result.all_warnings:
            logger.warning(
                f"Row {warning.row_number} [{warning.column_name}]: {warning.message}"
            )

        # Log validation summary
        logger.info(
            f"Comprehensive validation complete: {len(validation_result.all_errors)} errors, "
            f"{len(validation_result.all_warnings)} warnings"
        )

    return df, validation_result


def _validate_dob_column(df: pd.DataFrame) -> list[str]:
    """Validate date of birth column.

    Args:
        df: DataFrame to validate

    Returns:
        List of error messages (empty if no errors)
    """
    errors: list[str] = []

    # Parse dates with YYYY-MM-DD format
    for idx, row in df.iterrows():
        row_num = idx + 2  # +2 because: +1 for header, +1 for 1-indexed
        dob_value = row["dob"]

        # Check if empty
        if pd.isna(dob_value) or str(dob_value).strip() == "":
            errors.append(
                f"Row {row_num}: Missing required field 'dob'. Expected format: YYYY-MM-DD"
            )
            continue

        # Try to parse date
        try:
            parsed_date = pd.to_datetime(dob_value, format="%Y-%m-%d")

            # Validate date is not in future
            if parsed_date.date() > datetime.now(timezone.utc).date():
                logger.warning(
                    f"Row {row_num}: Date of birth {dob_value} is in the future. "
                    "This may be a data entry error."
                )

            # Validate date is reasonable (not before MIN_BIRTH_YEAR)
            if parsed_date.year < MIN_BIRTH_YEAR:
                errors.append(
                    f"Row {row_num}: Date of birth {dob_value} is before {MIN_BIRTH_YEAR}. "
                    "Please verify the date is correct."
                )

        except (ValueError, TypeError):
            errors.append(
                f"Row {row_num}: Invalid date format '{dob_value}'. "
                "Expected format: YYYY-MM-DD (e.g., 1980-01-15)"
            )

    return errors


def _validate_gender_column(df: pd.DataFrame) -> list[str]:
    """Validate gender column.

    Args:
        df: DataFrame to validate

    Returns:
        List of error messages (empty if no errors)
    """
    errors: list[str] = []

    for idx, row in df.iterrows():
        row_num = idx + 2  # +2 because: +1 for header, +1 for 1-indexed
        gender_value = row["gender"]

        # Check if empty
        if pd.isna(gender_value) or str(gender_value).strip() == "":
            errors.append(
                f"Row {row_num}: Missing required field 'gender'. "
                f"Must be one of: {', '.join(VALID_GENDERS)}"
            )
            continue

        # Convert to uppercase for case-insensitive comparison
        gender_upper = str(gender_value).strip().upper()

        # Validate against valid values
        if gender_upper not in VALID_GENDERS:
            errors.append(
                f"Row {row_num}: Invalid gender '{gender_value}'. "
                f"Must be one of: {', '.join(VALID_GENDERS)} (case-insensitive)"
            )
        else:
            # Normalize to uppercase in the DataFrame
            df.at[idx, "gender"] = gender_upper

    return errors


def _generate_missing_patient_ids(df: pd.DataFrame, seed: Optional[int] = None) -> None:
    """Generate patient IDs for rows with missing patient_id values.

    Modifies the DataFrame in-place by filling in missing patient_id values
    with auto-generated IDs in TEST-{UUID} format.

    Args:
        df: DataFrame to process
        seed: Optional random seed for deterministic ID generation
    """
    # Check if patient_id column exists
    if "patient_id" not in df.columns:
        # Create the column if it doesn't exist with object dtype to hold strings
        df["patient_id"] = pd.Series(dtype='object')
        logger.info("patient_id column not found in CSV, creating with auto-generated IDs")
    
    # Ensure column is object dtype to prevent FutureWarning when assigning strings
    if df["patient_id"].dtype != 'object':
        df["patient_id"] = df["patient_id"].astype('object')

    # Identify rows with missing patient_id values
    missing_id_mask = df["patient_id"].isna() | (df["patient_id"].astype(str).str.strip() == "")
    
    generated_count = 0
    provided_count = 0

    logger.info("Starting patient ID generation for batch")

    for idx in df.index:
        row_num = idx + 2  # +2 because: +1 for header, +1 for 1-indexed
        
        if missing_id_mask.loc[idx]:
            # Generate ID for this row
            generated_id = generate_patient_id(seed=seed)
            df.at[idx, "patient_id"] = generated_id
            logger.info(f"Generated patient ID {generated_id} for row {row_num}")
            generated_count += 1
        else:
            # Log provided ID
            provided_id = df.at[idx, "patient_id"]
            logger.info(f"Using provided patient ID {provided_id} for row {row_num}")
            provided_count += 1

    # Log summary
    logger.info(
        f"ID generation summary: {generated_count} generated, {provided_count} provided"
    )
