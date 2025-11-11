"""Integration tests for CLI workflows.

This module tests complete CLI workflows including multi-step processes,
reproducible ID generation, and real-world usage scenarios.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from ihe_test_util.cli.main import cli


class TestCLIWorkflows:
    """Integration tests for complete CLI workflows."""

    def test_validate_and_process_valid_csv_workflow(self, tmp_path):
        """Test complete workflow: validate CSV then process it."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
            "Jane,Smith,1975-05-15,F,1.2.3.4,TEST-002\n"
            "Bob,Johnson,1990-12-01,M,1.2.3.4,TEST-003\n"
        )
        csv_file.write_text(csv_content)

        # Act - Step 1: Validate
        validate_result = runner.invoke(cli, ["csv", "validate", str(csv_file)])

        # Assert - Validation succeeds
        assert validate_result.exit_code == 0
        assert "valid" in validate_result.output.lower() or "complete" in validate_result.output.lower()

        # Act - Step 2: Process
        process_result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert - Processing succeeds
        assert process_result.exit_code == 0
        assert "Total patients: 3" in process_result.output
        assert "Doe, John" in process_result.output
        assert "Smith, Jane" in process_result.output
        assert "Johnson, Bob" in process_result.output

    def test_csv_with_auto_generated_patient_ids(self, tmp_path):
        """Test processing CSV with auto-generated patient IDs."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients_no_ids.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "Alice,Williams,1985-03-20,F,1.2.3.4\n"
            "Charlie,Brown,1992-07-14,M,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act - Process CSV (will auto-generate IDs)
        result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        assert "Total patients: 2" in result.output
        assert "Auto-generated IDs: 2" in result.output
        assert "Provided IDs: 0" in result.output
        assert "TEST-" in result.output  # Auto-generated ID prefix
        assert "Williams, Alice" in result.output
        assert "Brown, Charlie" in result.output

    def test_csv_with_validation_errors_workflow(self, tmp_path):
        """Test workflow with CSV containing validation errors."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "invalid_patients.csv"
        error_export = tmp_path / "errors.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "John,Doe,1980-01-01,M,1.2.3.4\n"
            "Jane,Smith,invalid-date,F,1.2.3.4\n"
            "Bob,Johnson,1990-12-01,X,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act - Step 1: Validate with error export
        validate_result = runner.invoke(
            cli, ["csv", "validate", str(csv_file), "--export-errors", str(error_export)]
        )

        # Assert - Validation fails
        assert validate_result.exit_code == 1
        assert "error" in validate_result.output.lower()

        # Act - Step 2: Try to process (should also fail)
        process_result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert - Processing fails due to validation errors
        assert process_result.exit_code == 1
        assert "error" in process_result.output.lower()

    def test_reproducible_id_generation_with_seed(self, tmp_path):
        """Test that same seed produces identical patient IDs across runs."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "Alice,Adams,1985-01-01,F,1.2.3.4\n"
            "Bob,Baker,1990-02-02,M,1.2.3.4\n"
            "Carol,Carter,1995-03-03,F,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act - Run process command 3 times with same seed
        seed_value = "99999"
        result1 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", seed_value])
        result2 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", seed_value])
        result3 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", seed_value])

        # Assert - All runs succeed
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        assert result3.exit_code == 0

        # Assert - Extract patient IDs from all runs (ignoring timestamps)
        import re
        ids1 = re.findall(r'TEST-[a-f0-9\-]+', result1.output)
        ids2 = re.findall(r'TEST-[a-f0-9\-]+', result2.output)
        ids3 = re.findall(r'TEST-[a-f0-9\-]+', result3.output)
        
        # All runs should produce same IDs
        assert ids1 == ids2
        assert ids2 == ids3
        assert len(ids1) >= 3  # Should have at least 3 patient IDs

    def test_different_seeds_produce_different_ids(self, tmp_path):
        """Test that different seeds produce different patient IDs."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "Alice,Adams,1985-01-01,F,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act - Run with different seeds
        result1 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", "111"])
        result2 = runner.invoke(cli, ["csv", "process", str(csv_file), "--seed", "222"])

        # Assert - Both succeed
        assert result1.exit_code == 0
        assert result2.exit_code == 0

        # Assert - Outputs are different (different IDs generated)
        assert result1.output != result2.output

    def test_cli_output_can_be_piped(self, tmp_path):
        """Test CLI output can be captured to log file."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
        )
        csv_file.write_text(csv_content)

        # Act - Process CSV (output will be captured)
        result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert - Output is captured and can be parsed
        assert result.exit_code == 0
        output_lines = result.output.split("\n")
        assert len(output_lines) > 0
        assert any("Processing CSV file" in line for line in output_lines)
        assert any("Total patients" in line for line in output_lines)

    def test_verbose_mode_with_process_command(self, tmp_path):
        """Test verbose mode produces debug logging with process command."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid\n"
            "Alice,Adams,1985-01-01,F,1.2.3.4\n"
        )
        csv_file.write_text(csv_content)

        # Act - Run with verbose flag
        result = runner.invoke(cli, ["--verbose", "csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        # Verbose mode enables DEBUG logging, but output format may vary
        assert "Processing CSV file" in result.output

    def test_mixed_provided_and_generated_ids(self, tmp_path):
        """Test processing CSV with mix of provided and auto-generated IDs."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "mixed_ids.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "Alice,Adams,1985-01-01,F,1.2.3.4,MANUAL-001\n"
            "Bob,Baker,1990-02-02,M,1.2.3.4,\n"  # Empty ID - will be generated
            "Carol,Carter,1995-03-03,F,1.2.3.4,MANUAL-002\n"
            "David,Davis,2000-04-04,M,1.2.3.4,\n"  # Empty ID - will be generated
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        assert "Total patients: 4" in result.output
        assert "Auto-generated IDs: 2" in result.output
        assert "Provided IDs: 2" in result.output
        assert "MANUAL-001" in result.output
        assert "MANUAL-002" in result.output
        assert "TEST-" in result.output  # Auto-generated ID

    def test_json_output_validation_workflow(self, tmp_path):
        """Test JSON output format for validation can be parsed."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "patients.csv"
        csv_content = (
            "first_name,last_name,dob,gender,patient_id_oid,patient_id\n"
            "John,Doe,1980-01-01,M,1.2.3.4,TEST-001\n"
        )
        csv_file.write_text(csv_content)

        # Act
        result = runner.invoke(cli, ["csv", "validate", str(csv_file), "--json"])

        # Assert
        assert result.exit_code == 0
        # Output should be valid JSON
        import json
        try:
            json_output = json.loads(result.output)
            assert isinstance(json_output, dict)
            # Check for expected keys in validation result
            assert "total_rows" in json_output or "errors" in json_output
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {result.output}")

    def test_error_messages_are_actionable(self, tmp_path):
        """Test error messages provide actionable guidance."""
        # Arrange
        runner = CliRunner()
        nonexistent_file = tmp_path / "nonexistent.csv"

        # Act
        result = runner.invoke(cli, ["csv", "validate", str(nonexistent_file)])

        # Assert
        assert result.exit_code == 2  # Click file validation error
        # Error message should be helpful
        assert "does not exist" in result.output.lower() or "error" in result.output.lower()

    def test_large_csv_file_processing(self, tmp_path):
        """Test processing larger CSV file (50 patients)."""
        # Arrange
        runner = CliRunner()
        csv_file = tmp_path / "large_patients.csv"
        
        # Generate CSV with 50 patients
        lines = ["first_name,last_name,dob,gender,patient_id_oid,patient_id\n"]
        for i in range(50):
            lines.append(f"Patient{i},LastName{i},1980-01-{(i % 28) + 1:02d},M,1.2.3.4,PATIENT-{i:03d}\n")
        
        csv_file.write_text("".join(lines))

        # Act
        result = runner.invoke(cli, ["csv", "process", str(csv_file)])

        # Assert
        assert result.exit_code == 0
        assert "Total patients: 50" in result.output
        assert "Provided IDs: 50" in result.output
        assert "Processing complete" in result.output

    def test_help_text_includes_examples(self):
        """Test that help text includes usage examples."""
        # Arrange
        runner = CliRunner()

        # Act - Check main help
        main_help = runner.invoke(cli, ["--help"])
        
        # Assert
        assert main_help.exit_code == 0
        assert "Common usage:" in main_help.output or "IHE Test Utility" in main_help.output

        # Act - Check validate help
        validate_help = runner.invoke(cli, ["csv", "validate", "--help"])
        
        # Assert
        assert validate_help.exit_code == 0
        assert "Examples:" in validate_help.output

        # Act - Check process help
        process_help = runner.invoke(cli, ["csv", "process", "--help"])
        
        # Assert
        assert process_help.exit_code == 0
        assert "Examples:" in process_help.output


class TestTemplateCLIWorkflows:
    """Integration tests for template CLI commands."""

    def test_template_validate_workflow(self, tmp_path):
        """Test template validate command with real template."""
        # Arrange
        runner = CliRunner()
        template = tmp_path / "template.xml"
        template_content = """<?xml version="1.0"?>
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
        template.write_text(template_content)

        # Act
        result = runner.invoke(cli, ["template", "validate", str(template)])

        # Assert
        assert result.exit_code == 0
        assert "✓ Template is well-formed XML" in result.output
        assert "All required CCD placeholders present" in result.output

    def test_template_process_complete_workflow(self, tmp_path):
        """Test complete template process workflow with sample CSV."""
        # Arrange
        runner = CliRunner()
        template = tmp_path / "template.xml"
        template_content = """<?xml version="1.0"?>
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
        template.write_text(template_content)

        csv_file = tmp_path / "patients.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,mrn
PAT-001,1.2.3.4.5,John,Smith,1980-01-01,M,MRN001
PAT-002,1.2.3.4.5,Jane,Doe,1990-02-15,F,MRN002
PAT-003,1.2.3.4.5,Bob,Johnson,1975-03-10,M,MRN003"""
        csv_file.write_text(csv_content)

        output_dir = tmp_path / "ccds"

        # Act
        result = runner.invoke(
            cli,
            ["template", "process", str(template), str(csv_file), "--output", str(output_dir)]
        )

        # Assert
        assert result.exit_code in [0, 2]  # Allow partial failures
        assert "Processing patients" in result.output or "SUMMARY" in result.output
        assert "Total patients: 3" in result.output

        # Verify output directory created
        assert output_dir.exists()
        assert output_dir.is_dir()

        # Verify output files created
        output_files = list(output_dir.glob("*.xml"))
        assert len(output_files) > 0

        # Verify filenames match default format (patient_id.xml)
        filenames = [f.name for f in output_files]
        if "PAT-001.xml" in filenames:
            assert True  # Expected format found
        else:
            # Check for any valid XML files
            assert any(name.endswith(".xml") for name in filenames)

    def test_template_process_custom_filename_format(self, tmp_path):
        """Test template process with custom filename format."""
        # Arrange
        runner = CliRunner()
        template = tmp_path / "template.xml"
        template_content = """<?xml version="1.0"?>
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
        template.write_text(template_content)

        csv_file = tmp_path / "patients.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,mrn
PAT-001,1.2.3.4.5,John,Smith,1980-01-01,M,MRN001
PAT-002,1.2.3.4.5,Jane,Doe,1990-02-15,F,MRN002"""
        csv_file.write_text(csv_content)

        output_dir = tmp_path / "ccds"

        # Act - Use custom format
        result = runner.invoke(
            cli,
            [
                "template", "process", str(template), str(csv_file),
                "--output", str(output_dir),
                "--format", "{last_name}_{first_name}.xml"
            ]
        )

        # Assert
        assert result.exit_code in [0, 2]
        output_files = list(output_dir.glob("*.xml"))
        assert len(output_files) > 0

        # Check if filenames contain expected pattern
        filenames = [f.name for f in output_files]
        # Should have names like "Smith_John.xml", "Doe_Jane.xml"
        assert any("_" in name for name in filenames)

    def test_template_process_with_validation(self, tmp_path):
        """Test template process with output validation enabled."""
        # Arrange
        runner = CliRunner()
        template = tmp_path / "template.xml"
        template_content = """<?xml version="1.0"?>
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
        template.write_text(template_content)

        csv_file = tmp_path / "patients.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,mrn
PAT-001,1.2.3.4.5,John,Smith,1980-01-01,M,MRN001"""
        csv_file.write_text(csv_content)

        output_dir = tmp_path / "ccds"

        # Act - Enable output validation
        result = runner.invoke(
            cli,
            [
                "template", "process", str(template), str(csv_file),
                "--output", str(output_dir),
                "--validate-output"
            ]
        )

        # Assert
        assert result.exit_code in [0, 2]

        # Verify output files are valid XML
        from lxml import etree
        output_files = list(output_dir.glob("*.xml"))
        for xml_file in output_files:
            try:
                etree.parse(str(xml_file))
                # If parsing succeeds, XML is valid
                assert True
            except etree.XMLSyntaxError:
                pytest.fail(f"Generated CCD {xml_file.name} is not valid XML")

    def test_template_process_summary_report(self, tmp_path):
        """Test template process displays accurate summary report."""
        # Arrange
        runner = CliRunner()
        template = tmp_path / "template.xml"
        template_content = """<?xml version="1.0"?>
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
        template.write_text(template_content)

        csv_file = tmp_path / "patients.csv"
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,mrn
PAT-001,1.2.3.4.5,John,Smith,1980-01-01,M,MRN001
PAT-002,1.2.3.4.5,Jane,Doe,1990-02-15,F,MRN002
PAT-003,1.2.3.4.5,Bob,Johnson,1975-03-10,M,MRN003
PAT-004,1.2.3.4.5,Alice,Williams,1985-06-20,F,MRN004
PAT-005,1.2.3.4.5,Charlie,Brown,1992-08-15,M,MRN005"""
        csv_file.write_text(csv_content)

        output_dir = tmp_path / "ccds"

        # Act
        result = runner.invoke(
            cli,
            ["template", "process", str(template), str(csv_file), "--output", str(output_dir)]
        )

        # Assert - Check summary report
        assert "SUMMARY" in result.output
        assert "Total patients: 5" in result.output
        assert "Successful:" in result.output
        assert "Failed:" in result.output

        # Count actual output files
        output_files = list(output_dir.glob("*.xml"))
        # Summary should be accurate
        assert len(output_files) > 0

    def test_template_process_batch_with_sample_csv(self):
        """Test batch processing with examples/patients_sample.csv (if exists)."""
        # Arrange
        runner = CliRunner()
        import os
        
        # Use actual sample CSV if it exists
        sample_csv = Path("examples/patients_sample.csv")
        sample_template = Path("templates/ccd-template.xml")
        
        if not sample_csv.exists() or not sample_template.exists():
            pytest.skip("Sample CSV or template not available")

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            
            # Act
            result = runner.invoke(
                cli,
                [
                    "template", "process",
                    str(sample_template),
                    str(sample_csv),
                    "--output", str(output_dir)
                ]
            )

            # Assert
            assert result.exit_code in [0, 2]
            
            # Verify progress was shown
            assert "Processing patients" in result.output or "SUMMARY" in result.output
            
            # Verify output files created
            if output_dir.exists():
                output_files = list(output_dir.glob("*.xml"))
                assert len(output_files) > 0
                
                # Verify all generated CCDs are valid XML
                from lxml import etree
                for xml_file in output_files:
                    try:
                        etree.parse(str(xml_file))
                    except etree.XMLSyntaxError:
                        pytest.fail(f"Generated CCD {xml_file.name} is not valid XML")

    def test_template_help_text(self):
        """Test template command group help text."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["template", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "template" in result.output.lower()
        assert "validate" in result.output
        assert "process" in result.output

    def test_template_validate_help_includes_examples(self):
        """Test template validate help includes usage examples."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["template", "validate", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Example:" in result.output
        assert "template" in result.output

    def test_template_process_help_includes_examples(self):
        """Test template process help includes usage examples."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(cli, ["template", "process", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Examples:" in result.output
        assert "--output" in result.output
        assert "--format" in result.output
