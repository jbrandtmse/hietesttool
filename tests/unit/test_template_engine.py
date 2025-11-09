"""Unit tests for template engine module.

Tests cover:
- Template loading from files and strings
- XML validation
- Placeholder extraction
- CCD placeholder validation
- Template caching
- Error handling
"""

from pathlib import Path

import pytest

from ihe_test_util.template_engine import (
    REQUIRED_CCD_FIELDS,
    TemplateLoader,
    extract_placeholders,
    validate_ccd_placeholders,
    validate_xml,
)
from ihe_test_util.utils.exceptions import (
    MalformedXMLError,
    TemplateLoadError,
)


class TestTemplateLoader:
    """Test suite for TemplateLoader class."""

    def test_init(self):
        """Test TemplateLoader initialization."""
        # Arrange & Act
        loader = TemplateLoader()

        # Assert
        assert loader is not None
        assert loader.cache_size == 0

    def test_load_from_file_valid_template(self, tmp_path):
        """Test loading a valid XML template from file."""
        # Arrange
        template_file = tmp_path / "template.xml"
        template_content = '<?xml version="1.0"?><root>{{name}}</root>'
        template_file.write_text(template_content, encoding="utf-8")
        loader = TemplateLoader()

        # Act
        result = loader.load_from_file(template_file)

        # Assert
        assert "{{name}}" in result
        assert result.strip().startswith("<?xml")
        assert loader.cache_size == 1

    def test_load_from_file_caches_template(self, tmp_path):
        """Test that templates are cached after first load."""
        # Arrange
        template_file = tmp_path / "template.xml"
        template_content = '<?xml version="1.0"?><root>{{test}}</root>'
        template_file.write_text(template_content, encoding="utf-8")
        loader = TemplateLoader()

        # Act
        result1 = loader.load_from_file(template_file)
        result2 = loader.load_from_file(template_file)

        # Assert
        assert result1 == result2
        assert loader.cache_size == 1

    def test_load_from_file_not_found(self, tmp_path):
        """Test loading from non-existent file raises TemplateLoadError."""
        # Arrange
        loader = TemplateLoader()
        nonexistent_file = tmp_path / "nonexistent.xml"

        # Act & Assert
        with pytest.raises(TemplateLoadError) as exc_info:
            loader.load_from_file(nonexistent_file)
        assert "not found" in str(exc_info.value).lower()
        assert str(nonexistent_file) in str(exc_info.value)

    def test_load_from_file_malformed_xml(self, tmp_path):
        """Test loading malformed XML raises MalformedXMLError."""
        # Arrange
        template_file = tmp_path / "malformed.xml"
        template_file.write_text("<root><unclosed>", encoding="utf-8")
        loader = TemplateLoader()

        # Act & Assert
        with pytest.raises(MalformedXMLError) as exc_info:
            loader.load_from_file(template_file)
        assert "malformed" in str(exc_info.value).lower()

    def test_load_from_file_with_ccd_template_fixture(self):
        """Test loading the actual test CCD template fixture."""
        # Arrange
        template_file = Path("tests/fixtures/test_ccd_template.xml")
        loader = TemplateLoader()

        # Act
        result = loader.load_from_file(template_file)

        # Assert
        assert "{{patient_id}}" in result
        assert "{{first_name}}" in result
        assert "{{last_name}}" in result
        assert "{{dob}}" in result
        assert "{{gender}}" in result
        assert "ClinicalDocument" in result

    def test_load_from_string_valid_xml(self):
        """Test loading valid XML from string."""
        # Arrange
        loader = TemplateLoader()
        template_str = '<?xml version="1.0"?><root>{{field}}</root>'

        # Act
        result = loader.load_from_string(template_str)

        # Assert
        assert result == template_str
        assert "{{field}}" in result

    def test_load_from_string_malformed_xml(self):
        """Test loading malformed XML from string raises MalformedXMLError."""
        # Arrange
        loader = TemplateLoader()
        malformed_str = "<root><unclosed>"

        # Act & Assert
        with pytest.raises(MalformedXMLError) as exc_info:
            loader.load_from_string(malformed_str)
        assert "malformed" in str(exc_info.value).lower()

    def test_get_cached_template_exists(self, tmp_path):
        """Test retrieving cached template."""
        # Arrange
        template_file = tmp_path / "template.xml"
        template_content = '<?xml version="1.0"?><root>{{test}}</root>'
        template_file.write_text(template_content, encoding="utf-8")
        loader = TemplateLoader()
        loader.load_from_file(template_file)

        # Act
        cached = loader.get_cached_template(template_file)

        # Assert
        assert cached is not None
        assert cached == template_content

    def test_get_cached_template_not_exists(self, tmp_path):
        """Test retrieving non-cached template returns None."""
        # Arrange
        loader = TemplateLoader()
        template_file = tmp_path / "notloaded.xml"

        # Act
        cached = loader.get_cached_template(template_file)

        # Assert
        assert cached is None

    def test_clear_cache(self, tmp_path):
        """Test clearing the template cache."""
        # Arrange
        template_file = tmp_path / "template.xml"
        template_content = '<?xml version="1.0"?><root>{{test}}</root>'
        template_file.write_text(template_content, encoding="utf-8")
        loader = TemplateLoader()
        loader.load_from_file(template_file)
        assert loader.cache_size == 1

        # Act
        loader.clear_cache()

        # Assert
        assert loader.cache_size == 0
        assert loader.get_cached_template(template_file) is None

    def test_cache_size_property(self, tmp_path):
        """Test cache_size property tracks cache entries."""
        # Arrange
        loader = TemplateLoader()
        assert loader.cache_size == 0

        # Act - Load multiple templates
        for i in range(3):
            template_file = tmp_path / f"template{i}.xml"
            template_file.write_text(
                f'<?xml version="1.0"?><root>{{test{i}}}</root>', encoding="utf-8"
            )
            loader.load_from_file(template_file)

        # Assert
        assert loader.cache_size == 3

    def test_load_from_file_permission_error(self, tmp_path, mocker):
        """Test loading file with permission error raises TemplateLoadError."""
        # Arrange
        loader = TemplateLoader()
        template_file = tmp_path / "restricted.xml"
        template_file.write_text('<?xml version="1.0"?><root/>', encoding="utf-8")

        # Mock read_text to raise PermissionError
        mocker.patch.object(
            Path, "read_text", side_effect=PermissionError("Access denied")
        )

        # Act & Assert
        with pytest.raises(TemplateLoadError) as exc_info:
            loader.load_from_file(template_file)
        assert "permission" in str(exc_info.value).lower()

    def test_load_from_file_encoding_error(self, tmp_path, mocker):
        """Test loading file with encoding error raises TemplateLoadError."""
        # Arrange
        loader = TemplateLoader()
        template_file = tmp_path / "badencoding.xml"
        template_file.write_text('<?xml version="1.0"?><root/>', encoding="utf-8")

        # Mock read_text to raise UnicodeDecodeError
        mocker.patch.object(
            Path,
            "read_text",
            side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid"),
        )

        # Act & Assert
        with pytest.raises(TemplateLoadError) as exc_info:
            loader.load_from_file(template_file)
        assert "encoding" in str(exc_info.value).lower()


class TestValidateXML:
    """Test suite for validate_xml function."""

    def test_validate_xml_well_formed(self):
        """Test validation of well-formed XML."""
        # Arrange
        xml_content = '<?xml version="1.0"?><root><child>text</child></root>'

        # Act
        result = validate_xml(xml_content)

        # Assert
        assert result is True

    def test_validate_xml_with_namespaces(self):
        """Test validation of XML with namespaces."""
        # Arrange
        xml_content = '<root xmlns="urn:test"><child>text</child></root>'

        # Act
        result = validate_xml(xml_content)

        # Assert
        assert result is True

    def test_validate_xml_malformed_unclosed_tag(self):
        """Test validation of XML with unclosed tag."""
        # Arrange
        xml_content = "<root><child>text</root>"

        # Act & Assert
        with pytest.raises(MalformedXMLError) as exc_info:
            validate_xml(xml_content)
        assert "malformed" in str(exc_info.value).lower()
        assert "line" in str(exc_info.value).lower()

    def test_validate_xml_malformed_includes_line_number(self):
        """Test that malformed XML error includes line number."""
        # Arrange
        xml_content = """<?xml version="1.0"?>
<root>
  <child>
    <unclosed>
</root>"""

        # Act & Assert
        with pytest.raises(MalformedXMLError) as exc_info:
            validate_xml(xml_content)
        error_msg = str(exc_info.value)
        assert "line" in error_msg.lower()
        # Error should mention checking for unclosed tags
        assert "unclosed" in error_msg.lower() or "check" in error_msg.lower()

    def test_validate_xml_empty_string(self):
        """Test validation of empty string."""
        # Arrange
        xml_content = ""

        # Act & Assert
        with pytest.raises(MalformedXMLError):
            validate_xml(xml_content)


class TestExtractPlaceholders:
    """Test suite for extract_placeholders function."""

    def test_extract_placeholders_single(self):
        """Test extracting single placeholder."""
        # Arrange
        xml_content = "<root>{{name}}</root>"

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        assert result == {"name"}

    def test_extract_placeholders_multiple(self):
        """Test extracting multiple placeholders."""
        # Arrange
        xml_content = "<root>{{first_name}} {{last_name}} {{age}}</root>"

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        assert result == {"first_name", "last_name", "age"}

    def test_extract_placeholders_duplicates(self):
        """Test that duplicate placeholders are returned once."""
        # Arrange
        xml_content = "<root>{{name}} and {{name}} again</root>"

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        assert result == {"name"}
        assert len(result) == 1

    def test_extract_placeholders_none(self):
        """Test extracting from XML with no placeholders."""
        # Arrange
        xml_content = "<root>No placeholders here</root>"

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        assert result == set()
        assert len(result) == 0

    def test_extract_placeholders_in_attributes(self):
        """Test extracting placeholders from XML attributes."""
        # Arrange
        xml_content = '<root id="{{element_id}}" class="{{css_class}}">text</root>'

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        assert result == {"element_id", "css_class"}

    def test_extract_placeholders_ccd_template(self):
        """Test extracting placeholders from CCD template fixture."""
        # Arrange
        template_file = Path("tests/fixtures/test_ccd_template.xml")
        xml_content = template_file.read_text()

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        # Should contain all required CCD fields
        assert "patient_id" in result
        assert "patient_id_oid" in result
        assert "first_name" in result
        assert "last_name" in result
        assert "dob" in result
        assert "gender" in result
        # Should also contain optional fields
        assert "document_id" in result
        assert "address" in result

    def test_extract_placeholders_with_whitespace(self):
        """Test that placeholders with internal whitespace are NOT extracted."""
        # Arrange
        xml_content = "<root>{{ first_name }} {{last_name}}</root>"

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        # Only last_name should be extracted (no internal whitespace)
        assert "last_name" in result
        assert "first_name" not in result  # Has internal whitespace
        assert len(result) == 1

    def test_extract_placeholders_malformed_syntax(self):
        """Test that malformed placeholder syntax is gracefully ignored."""
        # Arrange
        xml_content = """<root>
            {{valid_placeholder}}
            {{unclosed
            {single_brace}
            {{}}
            {{ }}
        </root>"""

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        # Only valid_placeholder should be extracted
        assert result == {"valid_placeholder"}
        assert len(result) == 1

    def test_extract_placeholders_in_xml_comments(self):
        """Test that placeholders in XML comments ARE extracted (by design)."""
        # Arrange
        xml_content = """<?xml version="1.0"?>
        <root>
            <!-- Comment with {{comment_placeholder}} -->
            <field>{{normal_placeholder}}</field>
        </root>"""

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        # Both placeholders extracted (comments are part of XML string)
        assert "comment_placeholder" in result
        assert "normal_placeholder" in result
        assert len(result) == 2

    def test_extract_placeholders_in_cdata(self):
        """Test that placeholders in CDATA sections ARE extracted (by design)."""
        # Arrange
        xml_content = """<?xml version="1.0"?>
        <root>
            <![CDATA[Text with {{cdata_placeholder}}]]>
            <field>{{normal_placeholder}}</field>
        </root>"""

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        # Both placeholders extracted (CDATA is part of XML string)
        assert "cdata_placeholder" in result
        assert "normal_placeholder" in result
        assert len(result) == 2

    def test_extract_placeholders_case_sensitive(self):
        """Test that placeholder extraction is case-sensitive."""
        # Arrange
        xml_content = "<root>{{Patient_ID}} {{patient_id}} {{PATIENT_ID}}</root>"

        # Act
        result = extract_placeholders(xml_content)

        # Assert
        # All three should be extracted as different placeholders
        assert "Patient_ID" in result
        assert "patient_id" in result
        assert "PATIENT_ID" in result
        assert len(result) == 3


class TestValidateCCDPlaceholders:
    """Test suite for validate_ccd_placeholders function."""

    def test_validate_ccd_placeholders_all_present(self):
        """Test validation with all required placeholders present."""
        # Arrange
        placeholders = {
            "patient_id",
            "patient_id_oid",
            "first_name",
            "last_name",
            "dob",
            "gender",
            "extra_field",  # Extra fields are OK
        }

        # Act
        is_valid, missing = validate_ccd_placeholders(placeholders)

        # Assert
        assert is_valid is True
        assert missing == []

    def test_validate_ccd_placeholders_exact_match(self):
        """Test validation with exactly required placeholders."""
        # Arrange
        placeholders = REQUIRED_CCD_FIELDS.copy()

        # Act
        is_valid, missing = validate_ccd_placeholders(placeholders)

        # Assert
        assert is_valid is True
        assert missing == []

    def test_validate_ccd_placeholders_missing_one(self):
        """Test validation with one missing required placeholder."""
        # Arrange
        placeholders = {
            "patient_id",
            "patient_id_oid",
            "first_name",
            "last_name",
            "dob",
            # Missing: gender
        }

        # Act
        is_valid, missing = validate_ccd_placeholders(placeholders)

        # Assert
        assert is_valid is False
        assert missing == ["gender"]

    def test_validate_ccd_placeholders_missing_multiple(self):
        """Test validation with multiple missing required placeholders."""
        # Arrange
        placeholders = {
            "first_name",
            # Missing: patient_id, patient_id_oid, last_name, dob, gender
        }

        # Act
        is_valid, missing = validate_ccd_placeholders(placeholders)

        # Assert
        assert is_valid is False
        assert len(missing) == 5
        assert "patient_id" in missing
        assert "patient_id_oid" in missing
        assert "last_name" in missing
        assert "dob" in missing
        assert "gender" in missing

    def test_validate_ccd_placeholders_missing_all(self):
        """Test validation with all required placeholders missing."""
        # Arrange
        placeholders = set()

        # Act
        is_valid, missing = validate_ccd_placeholders(placeholders)

        # Assert
        assert is_valid is False
        assert len(missing) == len(REQUIRED_CCD_FIELDS)

    def test_validate_ccd_placeholders_returns_sorted_list(self):
        """Test that missing fields are returned in sorted order."""
        # Arrange
        placeholders = {"first_name"}  # Missing most fields

        # Act
        _is_valid, missing = validate_ccd_placeholders(placeholders)

        # Assert
        assert missing == sorted(missing)  # Should be alphabetically sorted


class TestRequiredCCDFields:
    """Test suite for REQUIRED_CCD_FIELDS constant."""

    def test_required_ccd_fields_contains_expected(self):
        """Test that REQUIRED_CCD_FIELDS contains all expected fields."""
        # Assert
        assert "patient_id" in REQUIRED_CCD_FIELDS
        assert "patient_id_oid" in REQUIRED_CCD_FIELDS
        assert "first_name" in REQUIRED_CCD_FIELDS
        assert "last_name" in REQUIRED_CCD_FIELDS
        assert "dob" in REQUIRED_CCD_FIELDS
        assert "gender" in REQUIRED_CCD_FIELDS

    def test_required_ccd_fields_count(self):
        """Test that REQUIRED_CCD_FIELDS has correct number of fields."""
        # Assert
        assert len(REQUIRED_CCD_FIELDS) == 6


class TestIntegrationScenarios:
    """Integration tests combining multiple components."""

    def test_full_workflow_valid_template(self, tmp_path):
        """Test complete workflow: load, validate, extract, validate CCD."""
        # Arrange
        template_content = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <id root="{{patient_id_oid}}" extension="{{patient_id}}"/>
  <patient>
    <name>{{first_name}} {{last_name}}</name>
    <birthTime value="{{dob}}"/>
    <gender code="{{gender}}"/>
  </patient>
</ClinicalDocument>"""
        template_file = tmp_path / "test_template.xml"
        template_file.write_text(template_content, encoding="utf-8")
        loader = TemplateLoader()

        # Act - Load
        loaded_content = loader.load_from_file(template_file)

        # Act - Extract placeholders
        placeholders = extract_placeholders(loaded_content)

        # Act - Validate CCD
        is_valid, missing = validate_ccd_placeholders(placeholders)

        # Assert
        assert loaded_content == template_content
        assert is_valid is True
        assert missing == []
        assert loader.cache_size == 1

    def test_full_workflow_invalid_template(self):
        """Test complete workflow with template missing required fields."""
        # Arrange
        template_file = Path("tests/fixtures/test_ccd_missing_fields.xml")
        loader = TemplateLoader()

        # Act - Load
        loaded_content = loader.load_from_file(template_file)

        # Act - Extract placeholders
        placeholders = extract_placeholders(loaded_content)

        # Act - Validate CCD
        is_valid, missing = validate_ccd_placeholders(placeholders)

        # Assert
        assert is_valid is False
        assert len(missing) > 0
        # At minimum, should be missing patient_id, patient_id_oid, last_name, dob, gender
        assert "patient_id" in missing
        assert "patient_id_oid" in missing
