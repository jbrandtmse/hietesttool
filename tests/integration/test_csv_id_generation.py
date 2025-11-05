"""Integration tests for CSV patient ID auto-generation."""

import re
from pathlib import Path

import pandas as pd
import pytest

from ihe_test_util.csv_parser.parser import parse_csv


class TestCSVIdGenerationIntegration:
    """Integration tests for end-to-end patient ID generation workflow."""

    def test_end_to_end_csv_with_missing_ids(self, tmp_path):
        """Test end-to-end: CSV with missing IDs → parse → verify all IDs present."""
        # Arrange: Create CSV with missing patient_id values
        csv_content = """first_name,last_name,dob,gender,patient_id_oid,patient_id
John,Doe,1980-01-01,M,1.2.3.4,
Jane,Smith,1975-05-15,F,1.2.3.4,PROVIDED-123
Bob,Jones,1990-10-20,M,1.2.3.4,"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act: Parse CSV with seed for reproducibility
        df = parse_csv(csv_file, seed=42)

        # Assert: Verify all patients have IDs
        assert len(df) == 3
        assert "patient_id" in df.columns
        assert not df["patient_id"].isna().any(), "All patients should have patient_id"
        assert all(df["patient_id"] != ""), "No empty patient_id values"

        # Verify generated IDs have correct format
        assert df.iloc[0]["patient_id"].startswith("TEST-")
        assert df.iloc[2]["patient_id"].startswith("TEST-")
        
        # Verify provided ID is preserved
        assert df.iloc[1]["patient_id"] == "PROVIDED-123"

        # Verify all patient_id_oid values preserved
        assert all(df["patient_id_oid"] == "1.2.3.4")

    def test_end_to_end_dataframe_structure_after_id_generation(self, tmp_path):
        """Test DataFrame contains all expected columns and data after ID generation."""
        # Arrange
        csv_content = """first_name,last_name,dob,gender,patient_id_oid,mrn,email
John,Doe,1980-01-01,M,1.2.3.4.5,MRN001,john@example.com
Jane,Smith,1975-05-15,F,2.3.4.5.6,MRN002,jane@example.com"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        df = parse_csv(csv_file, seed=100)

        # Assert: Verify DataFrame structure
        expected_columns = ["first_name", "last_name", "dob", "gender", "patient_id_oid", "mrn", "email", "patient_id"]
        assert all(col in df.columns for col in expected_columns)

        # Verify patient_id column was created
        assert "patient_id" in df.columns
        assert len(df) == 2

        # Verify all IDs generated correctly
        assert df.iloc[0]["patient_id"].startswith("TEST-")
        assert df.iloc[1]["patient_id"].startswith("TEST-")

        # Verify other data preserved
        assert df.iloc[0]["first_name"] == "John"
        assert df.iloc[0]["mrn"] == "MRN001"
        assert df.iloc[0]["email"] == "john@example.com"
        assert df.iloc[1]["first_name"] == "Jane"

    def test_end_to_end_generated_ids_format_validation(self, tmp_path):
        """Test that all generated IDs match TEST-{UUID} format specification."""
        # Arrange: Create CSV with only empty patient_id values
        csv_content = """first_name,last_name,dob,gender,patient_id_oid,patient_id
Patient1,Test,1980-01-01,M,1.2.3.4,
Patient2,Test,1981-02-02,F,1.2.3.4,
Patient3,Test,1982-03-03,O,1.2.3.4,
Patient4,Test,1983-04-04,U,1.2.3.4,
Patient5,Test,1984-05-05,M,1.2.3.4,"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        df = parse_csv(csv_file, seed=777)

        # Assert: Verify all IDs match format
        uuid_pattern = r"TEST-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        
        for idx in range(len(df)):
            patient_id = df.iloc[idx]["patient_id"]
            assert re.match(uuid_pattern, patient_id), f"Patient ID {patient_id} does not match TEST-{{UUID}} format"
            assert len(patient_id) == 41, f"Patient ID {patient_id} has incorrect length"
            assert patient_id.startswith("TEST-"), f"Patient ID {patient_id} does not start with TEST-"

    def test_end_to_end_uniqueness_across_batch(self, tmp_path):
        """Test that all generated IDs in a batch are unique."""
        # Arrange: Create CSV with 50 patients, all missing IDs
        rows = []
        rows.append("first_name,last_name,dob,gender,patient_id_oid,patient_id")
        for i in range(50):
            rows.append(f"Patient{i},Test{i},1980-01-{(i % 28) + 1:02d},M,1.2.3.4,")
        
        csv_content = "\n".join(rows)
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        df = parse_csv(csv_file)

        # Assert: Verify all IDs are unique
        patient_ids = df["patient_id"].tolist()
        assert len(patient_ids) == 50
        assert len(set(patient_ids)) == 50, "All generated patient IDs should be unique"

        # Verify all are generated (not provided)
        assert all(pid.startswith("TEST-") for pid in patient_ids)

    def test_end_to_end_deterministic_generation_with_seed(self, tmp_path):
        """Test that using same seed produces identical results across runs."""
        # Arrange
        csv_content = """first_name,last_name,dob,gender,patient_id_oid,patient_id
John,Doe,1980-01-01,M,1.2.3.4,
Jane,Smith,1975-05-15,F,1.2.3.4,
Bob,Jones,1990-10-20,M,1.2.3.4,"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content, encoding="utf-8")
        
        seed = 12345

        # Act: Parse same file multiple times with same seed
        df1 = parse_csv(csv_file, seed=seed)
        df2 = parse_csv(csv_file, seed=seed)
        df3 = parse_csv(csv_file, seed=seed)

        # Assert: All runs should produce identical IDs
        for i in range(len(df1)):
            assert df1.iloc[i]["patient_id"] == df2.iloc[i]["patient_id"]
            assert df2.iloc[i]["patient_id"] == df3.iloc[i]["patient_id"]

    def test_end_to_end_mixed_provided_and_generated_ids(self, tmp_path):
        """Test complex scenario with mix of provided, missing, and empty IDs."""
        # Arrange: Various ID states
        csv_content = """first_name,last_name,dob,gender,patient_id_oid,patient_id
Patient1,Test,1980-01-01,M,1.2.3.4.5,PROVIDED-001
Patient2,Test,1981-02-02,F,2.3.4.5.6,
Patient3,Test,1982-03-03,O,3.4.5.6.7,PROVIDED-003
Patient4,Test,1983-04-04,U,4.5.6.7.8,
Patient5,Test,1984-05-05,M,5.6.7.8.9,PROVIDED-005
Patient6,Test,1985-06-06,F,6.7.8.9.0,"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        df = parse_csv(csv_file, seed=555)

        # Assert: Verify mix of provided and generated
        assert df.iloc[0]["patient_id"] == "PROVIDED-001"  # Provided
        assert df.iloc[1]["patient_id"].startswith("TEST-")  # Generated
        assert df.iloc[2]["patient_id"] == "PROVIDED-003"  # Provided
        assert df.iloc[3]["patient_id"].startswith("TEST-")  # Generated
        assert df.iloc[4]["patient_id"] == "PROVIDED-005"  # Provided
        assert df.iloc[5]["patient_id"].startswith("TEST-")  # Generated

        # Verify patient_id_oid preserved for all
        assert df.iloc[0]["patient_id_oid"] == "1.2.3.4.5"
        assert df.iloc[1]["patient_id_oid"] == "2.3.4.5.6"
        assert df.iloc[2]["patient_id_oid"] == "3.4.5.6.7"
        assert df.iloc[3]["patient_id_oid"] == "4.5.6.7.8"
        assert df.iloc[4]["patient_id_oid"] == "5.6.7.8.9"
        assert df.iloc[5]["patient_id_oid"] == "6.7.8.9.0"

        # Verify all generated IDs are unique
        generated_ids = [df.iloc[i]["patient_id"] for i in [1, 3, 5]]
        assert len(set(generated_ids)) == 3, "All generated IDs should be unique"

    def test_end_to_end_csv_without_patient_id_column_at_all(self, tmp_path):
        """Test CSV that doesn't have patient_id column creates it automatically."""
        # Arrange: CSV without patient_id column
        csv_content = """first_name,last_name,dob,gender,patient_id_oid,mrn
John,Doe,1980-01-01,M,1.2.3.4.5,MRN001
Jane,Smith,1975-05-15,F,2.3.4.5.6,MRN002
Bob,Jones,1990-10-20,M,3.4.5.6.7,MRN003"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        df = parse_csv(csv_file, seed=999)

        # Assert: patient_id column created with generated IDs
        assert "patient_id" in df.columns
        assert len(df) == 3
        
        for i in range(len(df)):
            assert df.iloc[i]["patient_id"].startswith("TEST-")
            assert len(df.iloc[i]["patient_id"]) == 41

        # Verify other columns preserved
        assert df.iloc[0]["first_name"] == "John"
        assert df.iloc[0]["mrn"] == "MRN001"
        assert df.iloc[1]["first_name"] == "Jane"
        assert df.iloc[2]["first_name"] == "Bob"

    def test_end_to_end_reproducible_test_data_generation(self, tmp_path):
        """Test that seed parameter enables reproducible test data across sessions."""
        # Arrange: Create two identical CSV files in different locations
        csv_content = """first_name,last_name,dob,gender,patient_id_oid
TestPatient1,Test,1980-01-01,M,1.2.3.4
TestPatient2,Test,1981-02-02,F,1.2.3.4
TestPatient3,Test,1982-03-03,O,1.2.3.4"""
        
        csv_file1 = tmp_path / "test1" / "patients.csv"
        csv_file1.parent.mkdir(parents=True, exist_ok=True)
        csv_file1.write_text(csv_content, encoding="utf-8")
        
        csv_file2 = tmp_path / "test2" / "patients.csv"
        csv_file2.parent.mkdir(parents=True, exist_ok=True)
        csv_file2.write_text(csv_content, encoding="utf-8")
        
        seed = 2024

        # Act: Parse both files with same seed
        df1 = parse_csv(csv_file1, seed=seed)
        df2 = parse_csv(csv_file2, seed=seed)

        # Assert: Generated IDs should be identical
        assert df1.iloc[0]["patient_id"] == df2.iloc[0]["patient_id"]
        assert df1.iloc[1]["patient_id"] == df2.iloc[1]["patient_id"]
        assert df1.iloc[2]["patient_id"] == df2.iloc[2]["patient_id"]

        # All should be generated
        for i in range(3):
            assert df1.iloc[i]["patient_id"].startswith("TEST-")
            assert df2.iloc[i]["patient_id"].startswith("TEST-")

    def test_end_to_end_large_batch_performance(self, tmp_path):
        """Test ID generation with larger batch to verify performance and correctness."""
        # Arrange: Create CSV with 100 patients
        rows = ["first_name,last_name,dob,gender,patient_id_oid,patient_id"]
        for i in range(100):
            dob_day = (i % 28) + 1
            gender = ["M", "F", "O", "U"][i % 4]
            # Mix of provided and missing IDs
            patient_id = f"PROVIDED-{i:03d}" if i % 5 == 0 else ""
            rows.append(f"Patient{i},Test{i},1980-01-{dob_day:02d},{gender},1.2.3.4,{patient_id}")
        
        csv_content = "\n".join(rows)
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        # Act
        df = parse_csv(csv_file, seed=12345)

        # Assert
        assert len(df) == 100
        assert "patient_id" in df.columns
        
        # Verify all patients have IDs
        assert not df["patient_id"].isna().any()
        assert all(df["patient_id"] != "")
        
        # Count provided vs generated
        provided_count = sum(1 for pid in df["patient_id"] if pid.startswith("PROVIDED-"))
        generated_count = sum(1 for pid in df["patient_id"] if pid.startswith("TEST-"))
        
        assert provided_count == 20  # Every 5th patient (0, 5, 10, ..., 95)
        assert generated_count == 80  # Remaining patients
        assert provided_count + generated_count == 100
        
        # Verify all IDs are unique
        assert len(set(df["patient_id"])) == 100
