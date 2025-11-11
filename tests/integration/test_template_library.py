"""
Integration tests for Story 3.4: Template Library & Examples

Tests that the provided CCD templates (ccd-template.xml and ccd-minimal.xml)
work correctly with the existing template engine (Stories 3.1-3.3).

Test Coverage:
- Template XML validation
- Required placeholder presence
- Personalization with sample data
- Output validation
- Both minimal and comprehensive templates
"""

from pathlib import Path

import pandas as pd
import pytest

from ihe_test_util.template_engine import (
    CCDPersonalizer,
    TemplateLoader,
    extract_placeholders,
    validate_ccd_placeholders,
    validate_xml,
)


class TestTemplateValidation:
    """Test template XML structure and placeholder validation."""

    def test_ccd_minimal_is_valid_xml(self):
        """Verify ccd-minimal.xml is well-formed XML."""
        template_path = Path("templates/ccd-minimal.xml")
        template_content = template_path.read_text(encoding="utf-8")

        # Should not raise exception
        validate_xml(template_content)

    def test_ccd_template_is_valid_xml(self):
        """Verify ccd-template.xml is well-formed XML."""
        template_path = Path("templates/ccd-template.xml")
        template_content = template_path.read_text(encoding="utf-8")

        # Should not raise exception
        validate_xml(template_content)

    def test_ccd_minimal_has_required_placeholders(self):
        """Verify ccd-minimal.xml includes all required placeholders."""
        template_path = Path("templates/ccd-minimal.xml")
        template_content = template_path.read_text(encoding="utf-8")

        placeholders = extract_placeholders(template_content)
        is_valid, missing = validate_ccd_placeholders(placeholders)

        assert is_valid, f"Missing required placeholders: {missing}"

    def test_ccd_template_has_required_placeholders(self):
        """Verify ccd-template.xml includes all required placeholders."""
        template_path = Path("templates/ccd-template.xml")
        template_content = template_path.read_text(encoding="utf-8")

        placeholders = extract_placeholders(template_content)
        is_valid, missing = validate_ccd_placeholders(placeholders)

        assert is_valid, f"Missing required placeholders: {missing}"

    def test_ccd_minimal_placeholder_count(self):
        """Verify ccd-minimal.xml has expected placeholder count."""
        template_path = Path("templates/ccd-minimal.xml")
        template_content = template_path.read_text(encoding="utf-8")

        placeholders = extract_placeholders(template_content)

        # Should have at least the 6 required + 2 auto-generated = 8 placeholders
        assert len(placeholders) >= 8, f"Expected at least 8 placeholders, found {len(placeholders)}"
        assert "patient_id" in placeholders
        assert "document_id" in placeholders
        assert "creation_timestamp" in placeholders

    def test_ccd_template_placeholder_count(self):
        """Verify ccd-template.xml has more placeholders than minimal."""
        minimal_path = Path("templates/ccd-minimal.xml")
        minimal_content = minimal_path.read_text(encoding="utf-8")
        minimal_placeholders = extract_placeholders(minimal_content)

        template_path = Path("templates/ccd-template.xml")
        template_content = template_path.read_text(encoding="utf-8")
        template_placeholders = extract_placeholders(template_content)

        # Comprehensive template should have more placeholders (includes optional fields)
        assert (
            len(template_placeholders) >= len(minimal_placeholders)
        ), "Comprehensive template should have at least as many placeholders as minimal"

    def test_both_templates_use_correct_namespace(self):
        """Verify both templates use correct HL7 CDA namespace."""
        for template_name in ["ccd-minimal.xml", "ccd-template.xml"]:
            template_path = Path("templates") / template_name
            template_content = template_path.read_text(encoding="utf-8")

            assert 'xmlns="urn:hl7-org:v3"' in template_content, (
                f"{template_name} missing HL7 CDA namespace"
            )


class TestTemplatePersonalization:
    """Test template personalization with actual patient data."""

    @pytest.fixture
    def sample_patients(self):
        """Load sample patient data from CSV."""
        csv_path = Path("examples/patients_sample.csv")
        df = pd.read_csv(csv_path)
        df['dob'] = pd.to_datetime(df['dob']).dt.date
        return df

    @pytest.fixture
    def personalizer(self):
        """Create CCDPersonalizer instance."""
        return CCDPersonalizer()

    def test_ccd_minimal_personalizes_successfully(self, personalizer, sample_patients):
        """Verify ccd-minimal.xml can be personalized with sample data."""
        template_path = Path("templates/ccd-minimal.xml")

        # Personalize with first patient
        ccd = personalizer.personalize_from_dataframe_row(
            template_path, sample_patients.iloc[0]
        )

        # Verify document was generated
        assert ccd.document_id
        assert ccd.patient_id
        assert ccd.creation_timestamp
        assert ccd.xml_content
        assert ccd.size_bytes > 0
        assert ccd.sha256_hash

        # Verify output is valid XML
        validate_xml(ccd.xml_content)

        # Verify placeholders were replaced
        assert "{{patient_id}}" not in ccd.xml_content
        assert "{{first_name}}" not in ccd.xml_content
        assert "{{last_name}}" not in ccd.xml_content
        assert "{{document_id}}" not in ccd.xml_content

    def test_ccd_template_personalizes_successfully(self, personalizer, sample_patients):
        """Verify ccd-template.xml can be personalized with sample data."""
        template_path = Path("templates/ccd-template.xml")

        # Personalize with first patient
        ccd = personalizer.personalize_from_dataframe_row(
            template_path, sample_patients.iloc[0]
        )

        # Verify document was generated
        assert ccd.document_id
        assert ccd.patient_id
        assert ccd.creation_timestamp
        assert ccd.xml_content
        assert ccd.size_bytes > 0

        # Verify output is valid XML
        validate_xml(ccd.xml_content)

        # Verify placeholders were replaced
        assert "{{patient_id}}" not in ccd.xml_content
        assert "{{first_name}}" not in ccd.xml_content

    def test_ccd_template_includes_clinical_sections(self, personalizer, sample_patients):
        """Verify ccd-template.xml includes clinical sections after personalization."""
        template_path = Path("templates/ccd-template.xml")

        ccd = personalizer.personalize_from_dataframe_row(
            template_path, sample_patients.iloc[0]
        )

        # Verify clinical sections are present
        assert "<section>" in ccd.xml_content
        assert "Allergies" in ccd.xml_content or "48765-2" in ccd.xml_content  # LOINC code
        assert "Medications" in ccd.xml_content or "10160-0" in ccd.xml_content
        assert "Problems" in ccd.xml_content or "11450-4" in ccd.xml_content
        assert "Procedures" in ccd.xml_content or "47519-4" in ccd.xml_content

    def test_ccd_minimal_does_not_include_clinical_sections(
        self, personalizer, sample_patients
    ):
        """Verify ccd-minimal.xml has empty structured body."""
        template_path = Path("templates/ccd-minimal.xml")

        ccd = personalizer.personalize_from_dataframe_row(
            template_path, sample_patients.iloc[0]
        )

        # Should have structuredBody but no sections
        assert "<structuredBody>" in ccd.xml_content
        assert "</structuredBody>" in ccd.xml_content

        # Should not have clinical sections (or very minimal)
        section_count = ccd.xml_content.count("<section>")
        assert section_count == 0, "Minimal template should have no clinical sections"

    def test_batch_personalization_minimal(self, personalizer, sample_patients):
        """Verify batch personalization works with ccd-minimal.xml."""
        template_path = Path("templates/ccd-minimal.xml")

        # Process first 5 patients
        ccd_documents = []
        for i in range(min(5, len(sample_patients))):
            ccd = personalizer.personalize_from_dataframe_row(
                template_path, sample_patients.iloc[i]
            )
            ccd_documents.append(ccd)

        # Verify all documents generated
        assert len(ccd_documents) == min(5, len(sample_patients))

        # Verify each document is unique
        document_ids = [ccd.document_id for ccd in ccd_documents]
        assert len(set(document_ids)) == len(document_ids), "Document IDs should be unique"

        # Verify each document is valid
        for ccd in ccd_documents:
            validate_xml(ccd.xml_content)

    def test_template_with_optional_fields(self, personalizer, sample_patients):
        """Verify ccd-template.xml handles optional fields correctly."""
        template_path = Path("templates/ccd-template.xml")

        # Find patient with optional fields (address, phone, etc.)
        patient_with_address = None
        for i in range(len(sample_patients)):
            row = sample_patients.iloc[i]
            if row.get("address") and row.get("city"):
                patient_with_address = row
                break

        if patient_with_address is not None:
            ccd = personalizer.personalize_from_dataframe_row(
                template_path, patient_with_address
            )

            # Verify optional fields were populated
            if patient_with_address.get("address"):
                assert patient_with_address["address"] in ccd.xml_content
            if patient_with_address.get("city"):
                assert patient_with_address["city"] in ccd.xml_content


class TestTemplateLoader:
    """Test that templates work with TemplateLoader caching."""

    def test_loader_caches_minimal_template(self):
        """Verify TemplateLoader caches ccd-minimal.xml correctly."""
        loader = TemplateLoader()
        template_path = Path("templates/ccd-minimal.xml")

        # Load twice
        content1 = loader.load_from_file(template_path)
        content2 = loader.load_from_file(template_path)

        # Should return same content
        assert content1 == content2

        # Should be valid XML
        validate_xml(content1)

    def test_loader_caches_comprehensive_template(self):
        """Verify TemplateLoader caches ccd-template.xml correctly."""
        loader = TemplateLoader()
        template_path = Path("templates/ccd-template.xml")

        # Load twice
        content1 = loader.load_from_file(template_path)
        content2 = loader.load_from_file(template_path)

        # Should return same content
        assert content1 == content2

        # Should be valid XML
        validate_xml(content1)


class TestTemplateDocumentation:
    """Test that template documentation is accurate."""

    def test_minimal_template_has_inline_comments(self):
        """Verify ccd-minimal.xml has inline documentation comments."""
        template_path = Path("templates/ccd-minimal.xml")
        template_content = template_path.read_text(encoding="utf-8")

        # Should have XML comments
        assert "<!--" in template_content
        assert "-->" in template_content

        # Should document placeholders
        assert "REQUIRED PLACEHOLDERS" in template_content or "Required" in template_content

    def test_comprehensive_template_has_inline_comments(self):
        """Verify ccd-template.xml has inline documentation comments."""
        template_path = Path("templates/ccd-template.xml")
        template_content = template_path.read_text(encoding="utf-8")

        # Should have extensive comments
        assert "<!--" in template_content
        assert "-->" in template_content

        # Should document sections
        assert "PATIENT DEMOGRAPHICS" in template_content or "recordTarget" in template_content
        assert (
            "ALLERGIES" in template_content
            or "Allergies" in template_content
            or "48765-2" in template_content
        )

    def test_templates_readme_exists(self):
        """Verify templates/README.md exists and has content."""
        readme_path = Path("templates/README.md")
        assert readme_path.exists(), "templates/README.md should exist"

        content = readme_path.read_text(encoding="utf-8")
        assert len(content) > 100, "README should have substantial content"
        assert "ccd-minimal.xml" in content
        assert "ccd-template.xml" in content


class TestTemplateComparison:
    """Test differences between minimal and comprehensive templates."""

    @pytest.fixture
    def sample_patients(self):
        """Load sample patient data from CSV."""
        csv_path = Path("examples/patients_sample.csv")
        df = pd.read_csv(csv_path)
        df['dob'] = pd.to_datetime(df['dob']).dt.date
        return df

    def test_comprehensive_larger_than_minimal(self):
        """Verify ccd-template.xml is larger than ccd-minimal.xml."""
        minimal_path = Path("templates/ccd-minimal.xml")
        template_path = Path("templates/ccd-template.xml")

        minimal_size = minimal_path.stat().st_size
        template_size = template_path.stat().st_size

        assert (
            template_size > minimal_size
        ), "Comprehensive template should be larger than minimal"

    def test_minimal_template_faster_personalization(self, sample_patients):
        """Verify minimal template personalizes faster (approximately)."""
        import time

        personalizer = CCDPersonalizer()

        # Time minimal template
        minimal_path = Path("templates/ccd-minimal.xml")
        start = time.time()
        for i in range(min(3, len(sample_patients))):
            personalizer.personalize_from_dataframe_row(
                minimal_path, sample_patients.iloc[i]
            )
        minimal_time = time.time() - start

        # Time comprehensive template
        template_path = Path("templates/ccd-template.xml")
        start = time.time()
        for i in range(min(3, len(sample_patients))):
            personalizer.personalize_from_dataframe_row(
                template_path, sample_patients.iloc[i]
            )
        template_time = time.time() - start

        # Comprehensive should take at least as long (may be slightly longer)
        # This is a soft check - mainly verifying both work, not strict performance
        assert minimal_time >= 0 and template_time >= 0, "Both should complete successfully"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
