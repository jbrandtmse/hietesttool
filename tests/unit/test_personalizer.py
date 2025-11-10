"""Unit tests for template personalizer module."""

import pytest
from datetime import date, datetime

from ihe_test_util.template_engine.personalizer import (
    MissingValueStrategy,
    TemplatePersonalizer,
    escape_xml_value,
    format_date_value,
    validate_oid,
)
from ihe_test_util.utils.exceptions import (
    MissingPlaceholderValueError,
    MaxNestingDepthError,
)


class TestTemplatePersonalizer:
    """Test suite for TemplatePersonalizer class."""

    def test_personalize_simple_placeholders(self):
        """Test basic placeholder replacement with simple string values."""
        # Arrange
        template = "<patient><name>{{first_name}} {{last_name}}</name></patient>"
        values = {"first_name": "John", "last_name": "Doe"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<name>John Doe</name>" in result
        assert "{{" not in result  # No placeholders remaining

    def test_personalize_all_placeholders_replaced(self):
        """Test that all placeholder instances are replaced."""
        # Arrange
        template = (
            "<patient>"
            "<id>{{patient_id}}</id>"
            "<name>{{first_name}} {{last_name}}</name>"
            "<dob>{{dob}}</dob>"
            "<duplicate_id>{{patient_id}}</duplicate_id>"
            "</patient>"
        )
        values = {
            "patient_id": "PAT-12345",
            "first_name": "Jane",
            "last_name": "Smith",
            "dob": date(1990, 5, 15),
        }
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert result.count("PAT-12345") == 2  # Both instances replaced
        assert "Jane Smith" in result
        assert "19900515" in result  # HL7 formatted date
        assert "{{" not in result

    def test_personalize_preserves_whitespace(self):
        """Test that whitespace and indentation are preserved."""
        # Arrange
        template = """<patient>
    <name>{{first_name}} {{last_name}}</name>
    <id>{{patient_id}}</id>
</patient>"""
        values = {
            "first_name": "Bob",
            "last_name": "Jones",
            "patient_id": "PAT-999",
        }
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "    <name>Bob Jones</name>" in result  # Indentation preserved
        assert "\n" in result  # Newlines preserved

    def test_personalize_with_date_values(self):
        """Test date formatting with HL7 format (default)."""
        # Arrange
        template = "<dob>{{dob}}</dob><timestamp>{{timestamp}}</timestamp>"
        values = {
            "dob": date(1980, 1, 15),
            "timestamp": datetime(2023, 11, 9, 14, 30, 45),
        }
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<dob>19800115</dob>" in result
        assert "<timestamp>20231109143045</timestamp>" in result

    def test_personalize_with_iso_date_format(self):
        """Test date formatting with ISO format."""
        # Arrange
        template = "<dob>{{dob}}</dob>"
        values = {"dob": date(1980, 1, 15)}
        personalizer = TemplatePersonalizer(date_format="ISO")

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<dob>1980-01-15</dob>" in result

    def test_personalize_with_custom_date_format(self):
        """Test date formatting with custom strftime format."""
        # Arrange
        template = "<dob>{{dob}}</dob>"
        values = {"dob": date(1980, 1, 15)}
        personalizer = TemplatePersonalizer(date_format="%m/%d/%Y")

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<dob>01/15/1980</dob>" in result

    def test_personalize_with_oid_values(self):
        """Test OID values are inserted without modification."""
        # Arrange
        template = "<id root='{{patient_id_oid}}' extension='{{patient_id}}'/>"
        values = {"patient_id_oid": "1.2.3.4.5", "patient_id": "PAT-123"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "root='1.2.3.4.5'" in result
        assert "extension='PAT-123'" in result

    def test_personalize_missing_value_error_strategy(self):
        """Test ERROR strategy raises exception for missing values."""
        # Arrange
        template = "<name>{{first_name}} {{last_name}}</name>"
        values = {"first_name": "John"}  # last_name missing
        personalizer = TemplatePersonalizer(
            missing_value_strategy=MissingValueStrategy.ERROR
        )

        # Act & Assert
        with pytest.raises(MissingPlaceholderValueError) as exc_info:
            personalizer.personalize(template, values)

        assert "last_name" in str(exc_info.value)
        assert "Missing required placeholder values" in str(exc_info.value)

    def test_personalize_missing_value_use_empty_strategy(self):
        """Test USE_EMPTY strategy uses empty string for missing values."""
        # Arrange
        template = "<name>{{first_name}} {{last_name}}</name>"
        values = {"first_name": "John"}  # last_name missing
        personalizer = TemplatePersonalizer(
            missing_value_strategy=MissingValueStrategy.USE_EMPTY
        )

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<name>John </name>" in result  # Space but no last name

    def test_personalize_missing_value_use_default_strategy(self):
        """Test USE_DEFAULT strategy uses default values for missing fields."""
        # Arrange
        template = "<name>{{first_name}} {{last_name}}</name>"
        values = {"first_name": "John"}  # last_name missing
        default_values = {"last_name": "Unknown"}
        personalizer = TemplatePersonalizer(
            missing_value_strategy=MissingValueStrategy.USE_DEFAULT,
            default_value_map=default_values,
        )

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<name>John Unknown</name>" in result

    def test_personalize_nested_placeholders(self):
        """Test nested placeholder replacement."""
        # Arrange
        template = "<value>{{outer}}</value>"
        values = {"outer": "prefix_{{inner}}_suffix", "inner": "MIDDLE"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<value>prefix_MIDDLE_suffix</value>" in result

    def test_personalize_max_nesting_depth_exceeded(self):
        """Test that exceeding max nesting depth raises error."""
        # Arrange
        template = "<value>{{level1}}</value>"
        values = {
            "level1": "{{level2}}",
            "level2": "{{level3}}",
            "level3": "{{level4}}",
            "level4": "{{level5}}",
            "level5": "final",
        }
        personalizer = TemplatePersonalizer(max_nesting_depth=2)

        # Act & Assert
        with pytest.raises(MaxNestingDepthError) as exc_info:
            personalizer.personalize(template, values)

        assert "Maximum nesting depth (2) exceeded" in str(exc_info.value)

    def test_personalize_none_value_becomes_empty_string(self):
        """Test that None values are converted to empty strings."""
        # Arrange
        template = "<optional>{{optional_field}}</optional>"
        values = {"optional_field": None}
        personalizer = TemplatePersonalizer(
            missing_value_strategy=MissingValueStrategy.USE_EMPTY
        )

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<optional></optional>" in result

    def test_personalize_empty_template(self):
        """Test personalizing empty template."""
        # Arrange
        template = ""
        values = {"field": "value"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert result == ""

    def test_personalize_empty_values(self):
        """Test personalizing with empty values dict."""
        # Arrange
        template = "<static>No placeholders here</static>"
        values = {}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert result == template  # Unchanged

    def test_personalize_numeric_values(self):
        """Test that numeric values are converted to strings."""
        # Arrange
        template = "<age>{{age}}</age><count>{{count}}</count>"
        values = {"age": 42, "count": 100}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "<age>42</age>" in result
        assert "<count>100</count>" in result


class TestXMLEscaping:
    """Test suite for XML special character escaping."""

    def test_escape_xml_value_ampersand(self):
        """Test escaping ampersand character."""
        assert escape_xml_value("Fish & Chips") == "Fish &amp; Chips"

    def test_escape_xml_value_less_than(self):
        """Test escaping less-than character."""
        assert escape_xml_value("a < b") == "a &lt; b"

    def test_escape_xml_value_greater_than(self):
        """Test escaping greater-than character."""
        assert escape_xml_value("a > b") == "a &gt; b"

    def test_escape_xml_value_double_quote(self):
        """Test escaping double quote character."""
        assert escape_xml_value('He said "Hello"') == "He said &quot;Hello&quot;"

    def test_escape_xml_value_single_quote(self):
        """Test escaping single quote character."""
        assert escape_xml_value("It's working") == "It&apos;s working"

    def test_escape_xml_value_all_special_chars(self):
        """Test escaping all special characters at once."""
        value = """<tag attr="value" other='test'>Fish & Chips</tag>"""
        result = escape_xml_value(value)

        assert "&lt;tag" in result
        assert "&quot;value&quot;" in result
        assert "&apos;test&apos;" in result
        assert "Fish &amp; Chips" in result
        assert "&lt;/tag&gt;" in result

    def test_escape_xml_value_no_special_chars(self):
        """Test that strings without special chars are unchanged."""
        value = "Hello World 123"
        assert escape_xml_value(value) == value

    def test_personalize_applies_xml_escaping(self):
        """Test that personalization applies XML escaping to string values."""
        # Arrange
        template = "<name>{{name}}</name>"
        values = {"name": "Fish & Chips <Company>"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "Fish &amp; Chips &lt;Company&gt;" in result
        assert "<" not in result.split("<name>")[1].split("</name>")[0]  # No raw <


class TestDateFormatting:
    """Test suite for date formatting functionality."""

    def test_format_date_value_hl7_date(self):
        """Test HL7 format for date objects."""
        d = date(1980, 1, 15)
        assert format_date_value(d, "HL7") == "19800115"

    def test_format_date_value_hl7_datetime(self):
        """Test HL7 format for datetime objects."""
        dt = datetime(2023, 11, 9, 14, 30, 45)
        assert format_date_value(dt, "HL7") == "20231109143045"

    def test_format_date_value_iso_date(self):
        """Test ISO format for date objects."""
        d = date(1980, 1, 15)
        assert format_date_value(d, "ISO") == "1980-01-15"

    def test_format_date_value_iso_datetime(self):
        """Test ISO format for datetime objects."""
        dt = datetime(2023, 11, 9, 14, 30, 45)
        result = format_date_value(dt, "ISO")
        assert result.startswith("2023-11-09T14:30:45")

    def test_format_date_value_custom_format(self):
        """Test custom strftime format."""
        d = date(1980, 1, 15)
        assert format_date_value(d, "%m/%d/%Y") == "01/15/1980"

    def test_format_date_value_default_is_hl7(self):
        """Test that default format is HL7."""
        d = date(1980, 1, 15)
        assert format_date_value(d) == "19800115"


class TestOIDValidation:
    """Test suite for OID validation functionality."""

    def test_validate_oid_valid_simple(self):
        """Test validation of simple valid OID."""
        assert validate_oid("1.2.3.4.5") is True

    def test_validate_oid_valid_long(self):
        """Test validation of long valid OID."""
        assert validate_oid("1.2.840.113619.6.197") is True

    def test_validate_oid_valid_single_digit(self):
        """Test validation of single digit OID."""
        assert validate_oid("1") is True

    def test_validate_oid_invalid_letters(self):
        """Test that OID with letters is invalid."""
        assert validate_oid("1.2.abc.4") is False

    def test_validate_oid_invalid_trailing_dot(self):
        """Test that OID ending with dot is invalid."""
        assert validate_oid("1.2.3.") is False

    def test_validate_oid_invalid_leading_dot(self):
        """Test that OID starting with dot is invalid."""
        assert validate_oid(".1.2.3") is False

    def test_validate_oid_invalid_double_dot(self):
        """Test that OID with double dots is invalid."""
        assert validate_oid("1.2..3") is False

    def test_validate_oid_invalid_empty(self):
        """Test that empty string is invalid OID."""
        assert validate_oid("") is False

    def test_validate_oid_invalid_special_chars(self):
        """Test that OID with special chars is invalid."""
        assert validate_oid("1.2-3.4") is False
        assert validate_oid("1.2_3.4") is False

    def test_personalize_warns_on_invalid_oid(self, caplog):
        """Test that personalizer logs warning for invalid OID."""
        # Arrange
        template = "<id root='{{patient_id_oid}}'/>"
        values = {"patient_id_oid": "invalid.oid."}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "invalid.oid." in result  # Still inserted (permissive)
        assert any(
            "invalid OID format" in record.message for record in caplog.records
        )


class TestPerformance:
    """Test suite for performance characteristics."""

    def test_batch_personalization_performance(self):
        """Test that batch personalization is efficient."""
        # Arrange
        template = """<patient>
    <id>{{patient_id}}</id>
    <name>{{first_name}} {{last_name}}</name>
    <dob>{{dob}}</dob>
    <gender>{{gender}}</gender>
</patient>"""
        personalizer = TemplatePersonalizer()

        # Prepare 100 patients
        patients = [
            {
                "patient_id": f"PAT-{i:05d}",
                "first_name": f"Patient{i}",
                "last_name": f"Test{i}",
                "dob": date(1980, 1, 1),
                "gender": "M",
            }
            for i in range(100)
        ]

        # Act - personalize 100 templates
        import time

        start = time.time()
        results = [personalizer.personalize(template, patient) for patient in patients]
        elapsed = time.time() - start

        # Assert
        assert len(results) == 100
        assert all("{{" not in result for result in results)  # All placeholders replaced
        # Target: <10 seconds for 100 patients (100ms each)
        assert elapsed < 10.0, f"Batch processing took {elapsed:.2f}s (target: <10s)"

    def test_regex_pattern_compiled_once(self):
        """Test that regex pattern is class-level (compiled once)."""
        # Arrange
        p1 = TemplatePersonalizer()
        p2 = TemplatePersonalizer()

        # Act & Assert
        assert p1.PLACEHOLDER_PATTERN is p2.PLACEHOLDER_PATTERN  # Same object


class TestEdgeCases:
    """Test suite for edge cases and error conditions."""

    def test_personalize_no_placeholders(self):
        """Test template with no placeholders."""
        # Arrange
        template = "<patient><name>John Doe</name></patient>"
        values = {"first_name": "Jane"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert result == template  # Unchanged

    def test_personalize_placeholder_in_attribute(self):
        """Test placeholder replacement in XML attributes."""
        # Arrange
        template = "<patient id='{{patient_id}}' oid='{{patient_id_oid}}'/>"
        values = {"patient_id": "PAT-123", "patient_id_oid": "1.2.3.4.5"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "id='PAT-123'" in result
        assert "oid='1.2.3.4.5'" in result

    def test_personalize_multiple_occurrences_same_placeholder(self):
        """Test that same placeholder can appear multiple times."""
        # Arrange
        template = "<data>{{value}} and {{value}} and {{value}}</data>"
        values = {"value": "TEST"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert result.count("TEST") == 3

    def test_personalize_placeholder_at_boundaries(self):
        """Test placeholders at start and end of template."""
        # Arrange
        template = "{{start}}<middle>content</middle>{{end}}"
        values = {"start": "BEGIN", "end": "END"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert result == "BEGIN<middle>content</middle>END"

    def test_personalize_malformed_placeholder_not_replaced(self):
        """Test that malformed placeholders are not replaced."""
        # Arrange
        template = "<data>{single} {{valid}} {{{triple}}}</data>"
        values = {"single": "A", "valid": "B", "triple": "C"}
        personalizer = TemplatePersonalizer()

        # Act
        result = personalizer.personalize(template, values)

        # Assert
        assert "{single}" in result  # Not replaced (single braces)
        assert "B" in result  # valid placeholder replaced
        assert "{C}" in result  # Triple braces: {{triple}} -> {C}
