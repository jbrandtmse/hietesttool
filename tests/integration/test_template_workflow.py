"""Integration tests for template loader and personalizer workflow."""

import pytest
from datetime import date
from pathlib import Path

from ihe_test_util.template_engine import (
    TemplateLoader,
    TemplatePersonalizer,
    MissingValueStrategy,
    validate_xml,
)


class TestTemplateWorkflow:
    """Integration tests for complete template processing workflow."""

    def test_load_and_personalize_template(self):
        """Test loading template and personalizing it with patient data."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer()
        
        # Load template from file
        template_path = Path("tests/fixtures/test_ccd_template.xml")
        template = loader.load_from_file(template_path)
        
        # Patient data
        values = {
            "patient_id": "PAT-12345",
            "patient_id_oid": "1.2.3.4.5",
            "document_id": "2.16.840.1.113883.19.5.99999.1",
            "first_name": "John",
            "last_name": "Doe",
            "dob": date(1980, 1, 15),
            "gender": "M",
            "address": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701",
            "phone": "555-1234",
        }
        
        # Act
        result = personalizer.personalize(template, values)
        
        # Assert
        assert "PAT-12345" in result
        assert "John" in result
        assert "Doe" in result
        assert "19800115" in result  # HL7 formatted date
        assert "{{" not in result  # No placeholders remaining
        
        # Verify result is valid XML
        validate_xml(result)

    def test_load_personalize_and_validate_xml(self):
        """Test complete workflow: load → personalize → validate."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer()
        
        template_path = Path("tests/fixtures/test_ccd_template.xml")
        template = loader.load_from_file(template_path)
        
        values = {
            "patient_id": "PAT-99999",
            "patient_id_oid": "1.2.840.113619.6.197",
            "document_id": "2.16.840.1.113883.19.5.99999.2",
            "first_name": "Jane",
            "last_name": "Smith",
            "dob": date(1990, 5, 20),
            "gender": "F",
            "address": "456 Oak Ave",
            "city": "Boston",
            "state": "MA",
            "zip": "02101",
            "phone": "555-5678",
        }
        
        # Act
        result = personalizer.personalize(template, values)
        
        # Assert - should not raise any validation errors
        validate_xml(result)
        assert "Jane" in result
        assert "Smith" in result
        assert "{{" not in result  # No placeholders remaining

    def test_cached_template_personalization(self):
        """Test that cached templates work correctly with personalizer."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer()
        
        template_path = Path("tests/fixtures/test_ccd_template.xml")
        
        # Load template twice (second load should use cache)
        template1 = loader.load_from_file(template_path)
        template2 = loader.load_from_file(template_path)
        
        # Verify caching worked
        assert template1 == template2
        
        # Personalize with different patients
        patient1 = {
            "patient_id": "PAT-001",
            "patient_id_oid": "1.2.3.4.5",
            "document_id": "2.16.840.1.113883.19.5.99999.3",
            "first_name": "Alice",
            "last_name": "Anderson",
            "dob": date(1985, 3, 10),
            "gender": "F",
            "address": "100 First St",
            "city": "Chicago",
            "state": "IL",
            "zip": "60601",
            "phone": "555-0001",
        }
        
        patient2 = {
            "patient_id": "PAT-002",
            "patient_id_oid": "1.2.3.4.5",
            "document_id": "2.16.840.1.113883.19.5.99999.4",
            "first_name": "Bob",
            "last_name": "Brown",
            "dob": date(1975, 7, 25),
            "gender": "M",
            "address": "200 Second Ave",
            "city": "Seattle",
            "state": "WA",
            "zip": "98101",
            "phone": "555-0002",
        }
        
        # Act
        result1 = personalizer.personalize(template1, patient1)
        result2 = personalizer.personalize(template2, patient2)
        
        # Assert
        assert "Alice" in result1
        assert "Anderson" in result1
        assert "Bob" in result2
        assert "Brown" in result2
        assert result1 != result2  # Different patients

    def test_batch_processing_with_loader_and_personalizer(self):
        """Test batch processing multiple patients through complete workflow."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer()
        
        template_path = Path("tests/fixtures/test_ccd_template.xml")
        template = loader.load_from_file(template_path)
        
        # Create 10 test patients
        patients = [
            {
                "patient_id": f"PAT-{i:03d}",
                "patient_id_oid": "1.2.3.4.5",
                "document_id": f"2.16.840.1.113883.19.5.99999.{i+10}",
                "first_name": f"Patient{i}",
                "last_name": f"Test{i}",
                "dob": date(1980 + i, 1, 1),
                "gender": "M" if i % 2 == 0 else "F",
                "address": f"{i} Test St",
                "city": "TestCity",
                "state": "TS",
                "zip": "12345",
                "phone": f"555-{i:04d}",
            }
            for i in range(10)
        ]
        
        # Act
        results = [personalizer.personalize(template, patient) for patient in patients]
        
        # Assert
        assert len(results) == 10
        for i, result in enumerate(results):
            assert f"PAT-{i:03d}" in result
            assert f"Patient{i}" in result
            assert "{{" not in result
            validate_xml(result)  # All results should be valid XML

    def test_personalize_with_missing_values_lenient(self):
        """Test personalization with missing optional values using lenient strategy."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer(
            missing_value_strategy=MissingValueStrategy.USE_EMPTY
        )
        
        template_path = Path("tests/fixtures/test_ccd_template.xml")
        template = loader.load_from_file(template_path)
        
        # Minimal patient data (some fields missing)
        values = {
            "patient_id": "PAT-MIN",
            "patient_id_oid": "1.2.3.4.5",
            "first_name": "Minimal",
            "last_name": "Patient",
            "dob": date(1990, 1, 1),
            "gender": "U",
            # Missing: address, city, state, zip
        }
        
        # Act
        result = personalizer.personalize(template, values)
        
        # Assert
        assert "Minimal" in result
        assert "Patient" in result
        assert "{{" not in result  # All placeholders replaced (with empty strings if needed)
        validate_xml(result)

    def test_personalize_with_xml_special_characters(self):
        """Test that XML special characters in values are properly escaped."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer()
        
        template_path = Path("tests/fixtures/test_ccd_template.xml")
        template = loader.load_from_file(template_path)
        
        # Patient data with XML special characters
        values = {
            "patient_id": "PAT-123",
            "patient_id_oid": "1.2.3.4.5",
            "document_id": "2.16.840.1.113883.19.5.99999.123",
            "first_name": "John<script>",
            "last_name": "Doe & Associates",
            "dob": date(1980, 1, 15),
            "gender": "M",
            "address": "123 Main St, Apt #5",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701",
            "phone": "555-9999",
        }
        
        # Act
        result = personalizer.personalize(template, values)
        
        # Assert
        assert "John&lt;script&gt;" in result  # < and > escaped
        assert "Doe &amp; Associates" in result  # & escaped
        validate_xml(result)  # Must still be valid XML

    def test_personalize_with_iso_date_format(self):
        """Test personalization with ISO date format instead of HL7."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer(date_format="ISO")
        
        template_path = Path("tests/fixtures/test_ccd_template.xml")
        template = loader.load_from_file(template_path)
        
        values = {
            "patient_id": "PAT-ISO",
            "patient_id_oid": "1.2.3.4.5",
            "document_id": "2.16.840.1.113883.19.5.99999.999",
            "first_name": "ISO",
            "last_name": "Format",
            "dob": date(1980, 1, 15),
            "gender": "M",
            "address": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701",
            "phone": "555-ISO1",
        }
        
        # Act
        result = personalizer.personalize(template, values)
        
        # Assert
        assert "1980-01-15" in result  # ISO format date
        assert "19800115" not in result  # Not HL7 format
        validate_xml(result)

    def test_load_from_string_and_personalize(self):
        """Test loading template from string and personalizing."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer()
        
        template_string = """<?xml version="1.0" encoding="UTF-8"?>
<patient>
    <id root="{{patient_id_oid}}" extension="{{patient_id}}"/>
    <name>
        <given>{{first_name}}</given>
        <family>{{last_name}}</family>
    </name>
    <birthTime value="{{dob}}"/>
    <administrativeGenderCode code="{{gender}}"/>
</patient>"""
        
        template = loader.load_from_string(template_string)
        
        values = {
            "patient_id": "PAT-STRING",
            "patient_id_oid": "1.2.3.4.5",
            "first_name": "String",
            "last_name": "Test",
            "dob": date(1985, 6, 15),
            "gender": "F",
        }
        
        # Act
        result = personalizer.personalize(template, values)
        
        # Assert
        assert "PAT-STRING" in result
        assert "String" in result
        assert "Test" in result
        assert "19850615" in result
        assert "F" in result
        validate_xml(result)

    def test_reusable_personalizer_instance(self):
        """Test that single personalizer instance can be reused for multiple patients."""
        # Arrange
        loader = TemplateLoader()
        personalizer = TemplatePersonalizer()  # Single instance
        
        template_path = Path("tests/fixtures/test_ccd_template.xml")
        template = loader.load_from_file(template_path)
        
        patients = [
            {
                "patient_id": f"PAT-{i}",
                "patient_id_oid": "1.2.3.4.5",
                "document_id": f"2.16.840.1.113883.19.5.99999.{i+100}",
                "first_name": f"First{i}",
                "last_name": f"Last{i}",
                "dob": date(1980, 1, 1),
                "gender": "M",
                "address": f"{i} St",
                "city": "City",
                "state": "ST",
                "zip": "12345",
                "phone": f"555-{i:04d}",
            }
            for i in range(5)
        ]
        
        # Act - reuse same personalizer instance
        results = []
        for patient in patients:
            result = personalizer.personalize(template, patient)
            results.append(result)
        
        # Assert
        assert len(results) == 5
        for i, result in enumerate(results):
            assert f"PAT-{i}" in result
            assert f"First{i}" in result
            assert f"Last{i}" in result
            validate_xml(result)
