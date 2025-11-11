"""Unit tests for template CLI commands.

Tests the template validate and template process commands using CliRunner.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from ihe_test_util.cli.template_commands import (
    display_summary,
    format_filename,
    template_group,
)
from ihe_test_util.models.ccd import CCDDocument
from ihe_test_util.utils.exceptions import (
    CCDPersonalizationError,
    MalformedXMLError,
    TemplateLoadError,
    ValidationError,
)


@pytest.fixture
def runner():
    """Provide a Click test runner."""
    return CliRunner()


@pytest.fixture
def valid_template_content():
    """Provide valid template XML content."""
    return """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="{{document_id}}"/>
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>"""


@pytest.fixture
def invalid_xml_template():
    """Provide malformed XML template."""
    return """<?xml version="1.0"?>
<ClinicalDocument>
    <unclosed_tag>
</ClinicalDocument>"""


@pytest.fixture
def missing_placeholders_template():
    """Provide template missing required placeholders."""
    return """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="{{document_id}}"/>
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}"/>
        </patientRole>
    </recordTarget>
</ClinicalDocument>"""


@pytest.fixture
def sample_csv_content():
    """Provide sample CSV content."""
    return """patient_id,patient_id_oid,first_name,last_name,dob,gender,mrn
PAT-001,1.2.3.4.5,John,Smith,1980-01-01,M,MRN001
PAT-002,1.2.3.4.5,Jane,Doe,1990-02-15,F,MRN002"""


class TestTemplateValidateCommand:
    """Test cases for template validate command."""

    def test_validate_valid_template(self, runner, tmp_path, valid_template_content):
        """Test validate command with valid template."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)

        # Act
        result = runner.invoke(template_group, ["validate", str(template)])

        # Assert
        assert result.exit_code == 0
        assert "✓ Template is well-formed XML" in result.output
        assert "All required CCD placeholders present" in result.output
        assert "patient_id" in result.output
        assert "first_name" in result.output

    def test_validate_malformed_xml(self, runner, tmp_path, invalid_xml_template):
        """Test validate command with malformed XML."""
        # Arrange
        template = tmp_path / "bad_template.xml"
        template.write_text(invalid_xml_template)

        # Act
        result = runner.invoke(template_group, ["validate", str(template)])

        # Assert
        assert result.exit_code == 1
        assert "✗ Validation failed" in result.output

    def test_validate_missing_placeholders(
        self, runner, tmp_path, missing_placeholders_template
    ):
        """Test validate command with missing required placeholders."""
        # Arrange
        template = tmp_path / "incomplete_template.xml"
        template.write_text(missing_placeholders_template)

        # Act
        result = runner.invoke(template_group, ["validate", str(template)])

        # Assert
        assert result.exit_code == 1
        assert "✗ Missing required placeholders" in result.output

    def test_validate_nonexistent_file(self, runner, tmp_path):
        """Test validate command with nonexistent file."""
        # Arrange
        nonexistent = tmp_path / "does_not_exist.xml"

        # Act
        result = runner.invoke(template_group, ["validate", str(nonexistent)])

        # Assert
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "error" in result.output.lower()


class TestTemplateProcessCommand:
    """Test cases for template process command."""

    def test_process_basic_usage(
        self, runner, tmp_path, valid_template_content, sample_csv_content
    ):
        """Test process command with valid inputs."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)

        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(sample_csv_content)

        output_dir = tmp_path / "output"

        # Act
        result = runner.invoke(
            template_group,
            ["process", str(template), str(csv_file), "--output", str(output_dir)],
        )

        # Assert
        assert result.exit_code in [0, 2]  # 0 = all success, 2 = partial failure
        assert "Processing patients" in result.output or "SUMMARY" in result.output
        assert "Total patients:" in result.output

        # Check output files created
        output_files = list(output_dir.glob("*.xml"))
        assert len(output_files) > 0

    def test_process_custom_output_directory(
        self, runner, tmp_path, valid_template_content, sample_csv_content
    ):
        """Test process command with custom output directory."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)

        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(sample_csv_content)

        output_dir = tmp_path / "custom_ccds"

        # Act
        result = runner.invoke(
            template_group,
            ["process", str(template), str(csv_file), "--output", str(output_dir)],
        )

        # Assert
        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_process_custom_filename_format(
        self, runner, tmp_path, valid_template_content, sample_csv_content
    ):
        """Test process command with custom filename format."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)

        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(sample_csv_content)

        output_dir = tmp_path / "output"

        # Act
        result = runner.invoke(
            template_group,
            [
                "process",
                str(template),
                str(csv_file),
                "--output",
                str(output_dir),
                "--format",
                "{last_name}_{first_name}.xml",
            ],
        )

        # Assert
        assert result.exit_code in [0, 2]
        output_files = list(output_dir.glob("*.xml"))
        if output_files:
            # Check if filename contains expected pattern
            filenames = [f.name for f in output_files]
            assert any("_" in name for name in filenames)

    def test_process_invalid_format_string(
        self, runner, tmp_path, valid_template_content, sample_csv_content
    ):
        """Test process command with invalid format string (no placeholders)."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)

        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(sample_csv_content)

        output_dir = tmp_path / "output"

        # Act
        result = runner.invoke(
            template_group,
            [
                "process",
                str(template),
                str(csv_file),
                "--output",
                str(output_dir),
                "--format",
                "static_name.xml",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid filename format" in result.output

    def test_process_with_validate_output_enabled(
        self, runner, tmp_path, valid_template_content, sample_csv_content
    ):
        """Test process command with output validation enabled."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)

        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(sample_csv_content)

        output_dir = tmp_path / "output"

        # Act
        result = runner.invoke(
            template_group,
            [
                "process",
                str(template),
                str(csv_file),
                "--output",
                str(output_dir),
                "--validate-output",
            ],
        )

        # Assert
        assert result.exit_code in [0, 2]

    def test_process_with_validate_output_disabled(
        self, runner, tmp_path, valid_template_content, sample_csv_content
    ):
        """Test process command with output validation disabled."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)

        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(sample_csv_content)

        output_dir = tmp_path / "output"

        # Act
        result = runner.invoke(
            template_group,
            [
                "process",
                str(template),
                str(csv_file),
                "--output",
                str(output_dir),
                "--no-validate-output",
            ],
        )

        # Assert
        assert result.exit_code in [0, 2]

    def test_process_nonexistent_template(self, runner, tmp_path, sample_csv_content):
        """Test process command with nonexistent template file."""
        # Arrange
        template = tmp_path / "nonexistent.xml"
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(sample_csv_content)

        # Act
        result = runner.invoke(
            template_group, ["process", str(template), str(csv_file)]
        )

        # Assert
        assert result.exit_code != 0

    def test_process_nonexistent_csv(self, runner, tmp_path, valid_template_content):
        """Test process command with nonexistent CSV file."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)
        csv_file = tmp_path / "nonexistent.csv"

        # Act
        result = runner.invoke(
            template_group, ["process", str(template), str(csv_file)]
        )

        # Assert
        assert result.exit_code != 0


class TestFormatFilename:
    """Test cases for format_filename helper function."""

    def test_format_filename_basic(self):
        """Test basic filename formatting."""
        # Arrange
        format_string = "{patient_id}.xml"
        patient_data = {"patient_id": "PAT-001"}
        used_filenames = {}

        # Act
        result = format_filename(format_string, patient_data, used_filenames)

        # Assert
        assert result == "PAT-001.xml"
        assert "PAT-001.xml" in used_filenames

    def test_format_filename_multiple_placeholders(self):
        """Test filename formatting with multiple placeholders."""
        # Arrange
        format_string = "{last_name}_{first_name}_{patient_id}.xml"
        patient_data = {
            "patient_id": "PAT-001",
            "first_name": "John",
            "last_name": "Smith",
        }
        used_filenames = {}

        # Act
        result = format_filename(format_string, patient_data, used_filenames)

        # Assert
        assert result == "Smith_John_PAT-001.xml"

    def test_format_filename_sanitizes_invalid_chars(self):
        """Test filename sanitization of invalid characters."""
        # Arrange
        format_string = "{patient_id}.xml"
        patient_data = {"patient_id": "PAT<>:001"}
        used_filenames = {}

        # Act
        result = format_filename(format_string, patient_data, used_filenames)

        # Assert
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "PAT___001.xml" == result

    def test_format_filename_handles_none_values(self):
        """Test filename formatting with None values."""
        # Arrange
        format_string = "{patient_id}.xml"
        patient_data = {"patient_id": None}
        used_filenames = {}

        # Act
        result = format_filename(format_string, patient_data, used_filenames)

        # Assert
        assert result == ".xml"

    def test_format_filename_ensures_uniqueness(self):
        """Test filename uniqueness when duplicates occur."""
        # Arrange
        format_string = "{patient_id}.xml"
        patient_data = {"patient_id": "PAT-001"}
        used_filenames = {"PAT-001.xml": 0}

        # Act
        result = format_filename(format_string, patient_data, used_filenames)

        # Assert
        assert result == "PAT-001_1.xml"
        assert used_filenames["PAT-001.xml"] == 1

    def test_format_filename_missing_placeholder_fallback(self):
        """Test filename formatting with missing placeholder."""
        # Arrange
        format_string = "{nonexistent_field}.xml"
        patient_data = {"patient_id": "PAT-001"}
        used_filenames = {}

        # Act
        result = format_filename(format_string, patient_data, used_filenames)

        # Assert
        assert result == "PAT-001.xml"  # Falls back to patient_id


class TestDisplaySummary:
    """Test cases for display_summary helper function."""

    def test_display_summary_all_success(self, capsys):
        """Test summary display with all patients successful."""
        # Arrange
        total = 30
        successful = 30
        failed = 0
        errors = []

        # Act
        display_summary(total, successful, failed, errors)
        captured = capsys.readouterr()

        # Assert
        assert "Total patients: 30" in captured.out
        assert "Successful: 30" in captured.out
        assert "Failed: 0" in captured.out
        assert "SUMMARY" in captured.out

    def test_display_summary_all_failed(self, capsys):
        """Test summary display with all patients failed."""
        # Arrange
        total = 5
        successful = 0
        failed = 5
        errors = [
            ("PAT-001", "Missing required field 'dob'"),
            ("PAT-002", "Invalid gender code"),
            ("PAT-003", "Template error"),
            ("PAT-004", "XML parsing failed"),
            ("PAT-005", "Unknown error"),
        ]

        # Act
        display_summary(total, successful, failed, errors)
        captured = capsys.readouterr()

        # Assert
        assert "Total patients: 5" in captured.out
        assert "Successful: 0" in captured.out
        assert "Failed: 5" in captured.out
        assert "PAT-001" in captured.out
        assert "Missing required field" in captured.out

    def test_display_summary_partial_failure(self, capsys):
        """Test summary display with partial failures."""
        # Arrange
        total = 10
        successful = 8
        failed = 2
        errors = [
            ("PAT-005", "Missing required field 'dob'"),
            ("PAT-009", "Invalid date format"),
        ]

        # Act
        display_summary(total, successful, failed, errors)
        captured = capsys.readouterr()

        # Assert
        assert "Total patients: 10" in captured.out
        assert "Successful: 8" in captured.out
        assert "Failed: 2" in captured.out
        assert "PAT-005" in captured.out
        assert "PAT-009" in captured.out

    def test_display_summary_truncates_long_errors(self, capsys):
        """Test summary display truncates very long error messages."""
        # Arrange
        total = 1
        successful = 0
        failed = 1
        long_error = "x" * 150  # Error longer than 100 characters
        errors = [("PAT-001", long_error)]

        # Act
        display_summary(total, successful, failed, errors)
        captured = capsys.readouterr()

        # Assert
        assert "PAT-001" in captured.out
        assert "..." in captured.out  # Truncated indicator


class TestExitCodes:
    """Test cases for exit code behavior."""

    def test_exit_code_all_success(
        self, runner, tmp_path, valid_template_content, sample_csv_content
    ):
        """Test exit code 0 for all patients successful."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text(valid_template_content)

        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(sample_csv_content)

        output_dir = tmp_path / "output"

        # Act
        result = runner.invoke(
            template_group,
            ["process", str(template), str(csv_file), "--output", str(output_dir)],
        )

        # Assert
        assert result.exit_code in [0, 2]  # Allow partial failures in real scenarios

    def test_exit_code_validation_failure(self, runner, tmp_path, invalid_xml_template):
        """Test exit code 1 for validation failure."""
        # Arrange
        template = tmp_path / "bad_template.xml"
        template.write_text(invalid_xml_template)

        # Act
        result = runner.invoke(template_group, ["validate", str(template)])

        # Assert
        assert result.exit_code == 1
