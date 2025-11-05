"""Unit tests for CSV parser module."""

import logging

import pandas as pd
import pytest

from ihe_test_util.csv_parser.parser import parse_csv
from ihe_test_util.utils.exceptions import ValidationError


class TestParseCSVValidData:
    """Test parsing valid CSV data."""

    def test_parse_csv_with_required_columns_only(self, tmp_path):
        """Test parsing CSV with only required columns."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-15,M,1.2.3.4.5\n"
            "Jane,Smith,1975-06-20,F,1.2.3.4.6\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        result = parse_csv(csv_file)

        # Assert
        assert len(result) == 2
        assert result.iloc[0]["first_name"] == "John"
        assert result.iloc[0]["last_name"] == "Doe"
        assert result.iloc[0]["dob"] == "1980-01-15"
        assert result.iloc[0]["gender"] == "M"
        assert result.iloc[0]["patient_id_oid"] == "1.2.3.4.5"
        assert result.iloc[1]["first_name"] == "Jane"

    def test_parse_csv_with_required_and_optional_columns(self, tmp_path):
        """Test parsing CSV with required and optional columns."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id,mrn,email,phone\n"
            "John,Doe,1980-01-15,M,1.2.3.4.5,PAT001,MRN001,john@example.com,555-1234\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        result = parse_csv(csv_file)

        # Assert
        assert len(result) == 1
        assert result.iloc[0]["patient_id"] == "PAT001"
        assert result.iloc[0]["mrn"] == "MRN001"
        assert result.iloc[0]["email"] == "john@example.com"
        assert result.iloc[0]["phone"] == "555-1234"

    def test_parse_csv_with_empty_optional_columns(self, tmp_path):
        """Test parsing CSV with empty optional columns."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,email,phone\n"
            "John,Doe,1980-01-15,M,1.2.3.4.5,,\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        result = parse_csv(csv_file)

        # Assert
        assert len(result) == 1
        assert pd.isna(result.iloc[0]["email"]) or result.iloc[0]["email"] == ""
        assert pd.isna(result.iloc[0]["phone"]) or result.iloc[0]["phone"] == ""

    def test_parse_csv_with_utf8_special_characters(self, tmp_path):
        """Test parsing CSV with UTF-8 special characters in names."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "José,García,1980-01-15,M,1.2.3.4.5\n"
            "François,O'Neill,1975-06-20,F,1.2.3.4.6\n"
            "Müller,Schmidt-Weber,1990-03-10,O,1.2.3.4.7\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        result = parse_csv(csv_file)

        # Assert
        assert len(result) == 3
        assert result.iloc[0]["first_name"] == "José"
        assert result.iloc[0]["last_name"] == "García"
        assert result.iloc[1]["first_name"] == "François"
        assert result.iloc[1]["last_name"] == "O'Neill"
        assert result.iloc[2]["first_name"] == "Müller"
        assert result.iloc[2]["last_name"] == "Schmidt-Weber"

    def test_parse_csv_with_quotes_and_commas_in_fields(self, tmp_path):
        """Test parsing CSV with commas and quotes in address fields."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            'first_name,last_name,dob,gender,patient_id_oid,address\n'
            'John,Doe,1980-01-15,M,1.2.3.4.5,"123 Main St, Apt 4"\n'
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        result = parse_csv(csv_file)

        # Assert
        assert len(result) == 1
        assert result.iloc[0]["address"] == "123 Main St, Apt 4"

    def test_parse_csv_normalizes_gender_to_uppercase(self, tmp_path):
        """Test that gender values are normalized to uppercase."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-15,m,1.2.3.4.5\n"
            "Jane,Smith,1975-06-20,f,1.2.3.4.6\n"
            "Alex,Brown,1990-03-10,o,1.2.3.4.7\n"
            "Sam,Wilson,1985-12-05,u,1.2.3.4.8\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        result = parse_csv(csv_file)

        # Assert
        assert result.iloc[0]["gender"] == "M"
        assert result.iloc[1]["gender"] == "F"
        assert result.iloc[2]["gender"] == "O"
        assert result.iloc[3]["gender"] == "U"


class TestParseCSVValidationErrors:
    """Test CSV validation error handling."""

    def test_parse_csv_missing_required_column(self, tmp_path):
        """Test error when required column is missing."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,gender,patient_id_oid\n"  # Missing 'dob'
            "John,Doe,M,1.2.3.4.5\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(csv_file)

        assert "Missing required columns: dob" in str(exc_info.value)
        assert "Required columns are:" in str(exc_info.value)

    def test_parse_csv_multiple_missing_required_columns(self, tmp_path):
        """Test error when multiple required columns are missing."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name\n"  # Missing dob, gender, patient_id_oid
            "John,Doe\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(csv_file)

        assert "Missing required columns:" in str(exc_info.value)
        assert "dob" in str(exc_info.value)
        assert "gender" in str(exc_info.value)
        assert "patient_id_oid" in str(exc_info.value)

    def test_parse_csv_invalid_date_format(self, tmp_path):
        """Test error when date format is invalid."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,01/15/1980,M,1.2.3.4.5\n"  # Invalid format
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(csv_file)

        assert "Row 2" in str(exc_info.value)
        assert "Invalid date format" in str(exc_info.value)
        assert "01/15/1980" in str(exc_info.value)
        assert "YYYY-MM-DD" in str(exc_info.value)

    def test_parse_csv_missing_dob_value(self, tmp_path):
        """Test error when dob value is empty."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,,M,1.2.3.4.5\n"  # Empty dob
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(csv_file)

        assert "Row 2" in str(exc_info.value)
        assert "Missing required field 'dob'" in str(exc_info.value)

    def test_parse_csv_invalid_gender_value(self, tmp_path):
        """Test error when gender value is invalid."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-15,X,1.2.3.4.5\n"  # Invalid gender
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(csv_file)

        assert "Row 2" in str(exc_info.value)
        assert "Invalid gender 'X'" in str(exc_info.value)
        assert "M, F, O, U" in str(exc_info.value)

    def test_parse_csv_missing_gender_value(self, tmp_path):
        """Test error when gender value is empty."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-15,,1.2.3.4.5\n"  # Empty gender
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(csv_file)

        assert "Row 2" in str(exc_info.value)
        assert "Missing required field 'gender'" in str(exc_info.value)

    def test_parse_csv_multiple_validation_errors(self, tmp_path):
        """Test that all validation errors are collected and reported."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,01/15/1980,X,1.2.3.4.5\n"  # Invalid date and gender
            "Jane,Smith,1975-06-20,Y,1.2.3.4.6\n"  # Invalid gender
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(csv_file)

        error_message = str(exc_info.value)
        assert "Row 2" in error_message
        assert "Row 3" in error_message
        assert "Invalid date format" in error_message
        assert "Invalid gender" in error_message

    def test_parse_csv_date_before_1900(self, tmp_path):
        """Test error when date is before 1900."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1850-01-15,M,1.2.3.4.5\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(csv_file)

        assert "Row 2" in str(exc_info.value)
        assert "before 1900" in str(exc_info.value)


class TestParseCSVFileErrors:
    """Test file-related error handling."""

    def test_parse_csv_file_not_found(self, tmp_path):
        """Test error when CSV file does not exist."""
        # Arrange
        csv_file = tmp_path / "nonexistent.csv"

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            parse_csv(csv_file)

        assert "CSV file not found" in str(exc_info.value)


class TestParseCSVLogging:
    """Test logging behavior."""

    def test_parse_csv_logs_loading_message(self, tmp_path, caplog):
        """Test that CSV loading is logged."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-15,M,1.2.3.4.5\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        with caplog.at_level(logging.INFO):
            parse_csv(csv_file)

        # Assert
        assert "Loading CSV from" in caplog.text

    def test_parse_csv_logs_validation_start(self, tmp_path, caplog):
        """Test that validation start is logged."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-15,M,1.2.3.4.5\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        with caplog.at_level(logging.INFO):
            parse_csv(csv_file)

        # Assert
        assert "Validating CSV structure and data" in caplog.text

    def test_parse_csv_logs_success_message(self, tmp_path, caplog):
        """Test that successful parsing is logged with record count."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-15,M,1.2.3.4.5\n"
            "Jane,Smith,1975-06-20,F,1.2.3.4.6\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        with caplog.at_level(logging.INFO):
            parse_csv(csv_file)

        # Assert
        assert "Successfully parsed 2 patient record(s)" in caplog.text

    def test_parse_csv_logs_warning_for_unknown_columns(self, tmp_path, caplog):
        """Test that unknown columns generate warning log."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,unknown_col\n"
            "John,Doe,1980-01-15,M,1.2.3.4.5,extra\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        with caplog.at_level(logging.WARNING):
            parse_csv(csv_file)

        # Assert
        assert "unknown columns" in caplog.text.lower()
        assert "unknown_col" in caplog.text

    def test_parse_csv_logs_warning_for_future_dob(self, tmp_path, caplog):
        """Test that future date of birth generates warning."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        future_date = "2099-01-15"
        csv_content = (
            f"first_name,last_name,dob,gender,patient_id_oid\n"
            f"John,Doe,{future_date},M,1.2.3.4.5\n"
        )
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        with caplog.at_level(logging.WARNING):
            parse_csv(csv_file)

        # Assert
        assert "in the future" in caplog.text
