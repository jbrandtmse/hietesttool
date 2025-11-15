"""Unit tests for PIX Add message builder."""

import pytest
from datetime import date, datetime, timezone
from lxml import etree

from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.ihe_transactions.pix_add import (
    build_pix_add_message,
    format_hl7_timestamp,
    format_hl7_date,
    validate_gender_code,
    validate_oid,
    format_xml,
)
from ihe_test_util.utils.exceptions import ValidationError


# HL7v3 and SOAP namespaces for testing
HL7_NS = "urn:hl7-org:v3"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"


@pytest.fixture
def minimal_patient():
    """Minimal patient demographics with only required fields."""
    return PatientDemographics(
        patient_id="TEST001",
        patient_id_oid="1.2.3.4.5",
        first_name="Test",
        last_name="Patient",
        dob=date(2000, 1, 1),
        gender="M"
    )


@pytest.fixture
def complete_patient():
    """Complete patient demographics with all optional fields."""
    return PatientDemographics(
        patient_id="TEST002",
        patient_id_oid="1.2.3.4.5",
        first_name="John",
        last_name="Doe",
        dob=date(1980, 5, 15),
        gender="F",
        mrn="MRN12345",
        ssn="123-45-6789",
        address="123 Main St",
        city="Portland",
        state="OR",
        zip="97201",
        phone="555-1234",
        email="john.doe@example.com"
    )


class TestFormatHL7Timestamp:
    """Test HL7 timestamp formatting function."""
    
    def test_format_timestamp_standard(self):
        """Test formatting a standard datetime."""
        dt = datetime(2025, 11, 14, 15, 30, 45)
        result = format_hl7_timestamp(dt)
        assert result == "20251114153045"
        assert len(result) == 14
        assert result.isdigit()
    
    def test_format_timestamp_timezone_aware(self):
        """Test formatting timezone-aware datetime."""
        dt = datetime(2025, 11, 14, 15, 30, 45, tzinfo=timezone.utc)
        result = format_hl7_timestamp(dt)
        assert result == "20251114153045"
    
    def test_format_timestamp_midnight(self):
        """Test formatting datetime at midnight."""
        dt = datetime(2025, 1, 1, 0, 0, 0)
        result = format_hl7_timestamp(dt)
        assert result == "20250101000000"
    
    def test_format_timestamp_end_of_day(self):
        """Test formatting datetime at end of day."""
        dt = datetime(2025, 12, 31, 23, 59, 59)
        result = format_hl7_timestamp(dt)
        assert result == "20251231235959"


class TestFormatHL7Date:
    """Test HL7 date formatting function."""
    
    def test_format_date_standard(self):
        """Test formatting a standard date."""
        d = date(1980, 1, 1)
        result = format_hl7_date(d)
        assert result == "19800101"
        assert len(result) == 8
        assert result.isdigit()
    
    def test_format_date_leap_year(self):
        """Test formatting date in leap year."""
        d = date(2024, 2, 29)
        result = format_hl7_date(d)
        assert result == "20240229"
    
    def test_format_date_current_century(self):
        """Test formatting date in current century."""
        d = date(2025, 11, 14)
        result = format_hl7_date(d)
        assert result == "20251114"


class TestValidateGenderCode:
    """Test gender code validation function."""
    
    def test_validate_male_gender(self):
        """Test validation of male gender code."""
        validate_gender_code("M")  # Should not raise
    
    def test_validate_female_gender(self):
        """Test validation of female gender code."""
        validate_gender_code("F")  # Should not raise
    
    def test_validate_other_gender(self):
        """Test validation of other gender code."""
        validate_gender_code("O")  # Should not raise
    
    def test_validate_unknown_gender(self):
        """Test validation of unknown gender code."""
        validate_gender_code("U")  # Should not raise
    
    def test_validate_invalid_gender_raises_error(self):
        """Test that invalid gender code raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_gender_code("X")
        assert "Invalid gender 'X'" in str(exc_info.value)
        assert "Must be M (Male), F (Female), O (Other), or U (Unknown)" in str(exc_info.value)
    
    def test_validate_empty_gender_raises_error(self):
        """Test that empty gender code raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_gender_code("")
    
    def test_validate_none_gender_raises_error(self):
        """Test that None gender code raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_gender_code(None)
    
    def test_validate_lowercase_gender_raises_error(self):
        """Test that lowercase gender code raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_gender_code("m")


class TestValidateOID:
    """Test OID validation function."""
    
    def test_validate_simple_oid(self):
        """Test validation of simple OID."""
        validate_oid("1.2.3.4.5", "test_oid")  # Should not raise
    
    def test_validate_complex_oid(self):
        """Test validation of complex OID."""
        validate_oid("2.16.840.1.113883.3.72.5.9.1", "test_oid")  # Should not raise
    
    def test_validate_single_arc_oid(self):
        """Test validation of single arc OID."""
        validate_oid("1", "test_oid")  # Should not raise
    
    def test_validate_empty_oid_raises_error(self):
        """Test that empty OID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_oid("", "test_field")
        assert "Missing required field: test_field" in str(exc_info.value)
    
    def test_validate_oid_starting_with_dot_raises_error(self):
        """Test that OID starting with dot raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_oid(".1.2.3", "test_field")
        assert "Invalid OID format" in str(exc_info.value)
        assert "must start with digit" in str(exc_info.value)
    
    def test_validate_oid_with_letters_raises_error(self):
        """Test that OID with letters raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_oid("1.2.ABC.4", "test_field")
        assert "Invalid OID format" in str(exc_info.value)
    
    def test_validate_oid_with_double_dots_raises_error(self):
        """Test that OID with double dots raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_oid("1.2..3.4", "test_field")


class TestFormatXML:
    """Test XML formatting function."""
    
    def test_format_simple_element(self):
        """Test formatting simple XML element."""
        root = etree.Element("root")
        result = format_xml(root)
        assert "<root/>" in result or "<root>" in result
    
    def test_format_element_with_children(self):
        """Test formatting XML element with children."""
        root = etree.Element("root")
        etree.SubElement(root, "child1")
        etree.SubElement(root, "child2")
        result = format_xml(root)
        assert "<root>" in result
        assert "<child1/>" in result or "<child1>" in result
        assert "<child2/>" in result or "<child2>" in result
    
    def test_format_preserves_text_content(self):
        """Test that formatting preserves text content."""
        root = etree.Element("root")
        root.text = "Hello World"
        result = format_xml(root)
        assert "Hello World" in result
    
    def test_format_includes_newlines(self):
        """Test that formatted output includes newlines."""
        root = etree.Element("root")
        etree.SubElement(root, "child")
        result = format_xml(root)
        assert "\n" in result  # Pretty-printed output has newlines


class TestBuildPIXAddMessage:
    """Test PIX Add message building function."""
    
    def test_build_message_with_minimal_demographics(self, minimal_patient):
        """Test building message with minimal patient demographics."""
        xml = build_pix_add_message(minimal_patient)
        
        # Parse the SOAP envelope
        root = etree.fromstring(xml.encode("utf-8"))
        
        # Extract HL7v3 message from SOAP Body
        assert root.tag == f"{{{SOAP_NS}}}Envelope"
        body = root.find(f"{{{SOAP_NS}}}Body")
        assert body is not None
        
        hl7_msg = body[0]
        assert hl7_msg.tag == f"{{{HL7_NS}}}PRPA_IN201301UV02"
    
    def test_build_message_with_complete_demographics(self, complete_patient):
        """Test building message with complete patient demographics."""
        xml = build_pix_add_message(complete_patient)
        
        root = etree.fromstring(xml.encode("utf-8"))
        body = root.find(f"{{{SOAP_NS}}}Body")
        hl7_msg = body[0]
        
        # Verify patient demographics are present
        given_name = hl7_msg.find(f".//{{{HL7_NS}}}given")
        assert given_name is not None
        assert given_name.text == "John"
        
        family_name = hl7_msg.find(f".//{{{HL7_NS}}}family")
        assert family_name is not None
        assert family_name.text == "Doe"
        
        # Verify address fields
        city = hl7_msg.find(f".//{{{HL7_NS}}}city")
        assert city is not None
        assert city.text == "Portland"
    
    def test_build_message_generates_unique_message_id(self, minimal_patient):
        """Test that each message gets unique message ID."""
        xml1 = build_pix_add_message(minimal_patient)
        xml2 = build_pix_add_message(minimal_patient)
        
        root1 = etree.fromstring(xml1.encode("utf-8"))
        root2 = etree.fromstring(xml2.encode("utf-8"))
        
        id1 = root1.find(f".//{{{HL7_NS}}}id[@root]").get("root")
        id2 = root2.find(f".//{{{HL7_NS}}}id[@root]").get("root")
        
        assert id1 != id2
    
    def test_build_message_formats_birth_date_correctly(self, minimal_patient):
        """Test that birth date is formatted in HL7 format."""
        xml = build_pix_add_message(minimal_patient)
        root = etree.fromstring(xml.encode("utf-8"))
        
        birth_time = root.find(f".//{{{HL7_NS}}}birthTime")
        assert birth_time is not None
        assert birth_time.get("value") == "20000101"
    
    def test_build_message_uses_correct_patient_id_oid(self, minimal_patient):
        """Test that patient ID OID is correctly set."""
        xml = build_pix_add_message(minimal_patient)
        root = etree.fromstring(xml.encode("utf-8"))
        
        patient_id = root.find(f".//{{{HL7_NS}}}patient/{{{HL7_NS}}}id")
        assert patient_id is not None
        assert patient_id.get("root") == "1.2.3.4.5"
        assert patient_id.get("extension") == "TEST001"
    
    def test_build_message_missing_patient_id_raises_error(self):
        """Test that missing patient ID raises ValidationError."""
        patient = PatientDemographics(
            patient_id="",  # Empty
            patient_id_oid="1.2.3.4.5",
            first_name="Test",
            last_name="Patient",
            dob=date(2000, 1, 1),
            gender="M"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_pix_add_message(patient)
        assert "Missing required patient field: patient_id" in str(exc_info.value)
    
    def test_build_message_missing_first_name_raises_error(self):
        """Test that missing first name raises ValidationError."""
        patient = PatientDemographics(
            patient_id="TEST001",
            patient_id_oid="1.2.3.4.5",
            first_name="",  # Empty
            last_name="Patient",
            dob=date(2000, 1, 1),
            gender="M"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_pix_add_message(patient)
        assert "Missing required patient field: first_name" in str(exc_info.value)
    
    def test_build_message_missing_last_name_raises_error(self):
        """Test that missing last name raises ValidationError."""
        patient = PatientDemographics(
            patient_id="TEST001",
            patient_id_oid="1.2.3.4.5",
            first_name="Test",
            last_name="",  # Empty
            dob=date(2000, 1, 1),
            gender="M"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_pix_add_message(patient)
        assert "Missing required patient field: last_name" in str(exc_info.value)
    
    def test_build_message_invalid_gender_raises_error(self):
        """Test that invalid gender code raises ValidationError."""
        patient = PatientDemographics(
            patient_id="TEST001",
            patient_id_oid="1.2.3.4.5",
            first_name="Test",
            last_name="Patient",
            dob=date(2000, 1, 1),
            gender="X"  # Invalid
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_pix_add_message(patient)
        assert "Invalid gender 'X'" in str(exc_info.value)
    
    def test_build_message_invalid_patient_id_oid_raises_error(self):
        """Test that invalid patient ID OID raises ValidationError."""
        patient = PatientDemographics(
            patient_id="TEST001",
            patient_id_oid="INVALID-OID",  # Invalid format
            first_name="Test",
            last_name="Patient",
            dob=date(2000, 1, 1),
            gender="M"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_pix_add_message(patient)
        assert "Invalid OID format" in str(exc_info.value)
        assert "patient_id_oid" in str(exc_info.value)
    
    def test_build_message_invalid_sending_facility_oid_raises_error(self, minimal_patient):
        """Test that invalid sending facility OID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            build_pix_add_message(minimal_patient, sending_facility="INVALID")
        assert "Invalid OID format" in str(exc_info.value)
        assert "sending_facility" in str(exc_info.value)
    
    def test_build_message_has_required_namespace_declarations(self, minimal_patient):
        """Test that message has required namespace declarations."""
        xml = build_pix_add_message(minimal_patient)
        root = etree.fromstring(xml.encode("utf-8"))
        
        body = root.find(f"{{{SOAP_NS}}}Body")
        hl7_msg = body[0]
        
        # Check HL7v3 namespace
        assert hl7_msg.nsmap[None] == HL7_NS
        # Check XSI namespace
        assert "xsi" in hl7_msg.nsmap
    
    def test_build_message_has_correct_interaction_id(self, minimal_patient):
        """Test that message has correct interaction ID."""
        xml = build_pix_add_message(minimal_patient)
        root = etree.fromstring(xml.encode("utf-8"))
        
        interaction_id = root.find(f".//{{{HL7_NS}}}interactionId")
        assert interaction_id is not None
        assert interaction_id.get("extension") == "PRPA_IN201301UV02"
    
    def test_build_message_all_valid_gender_codes(self):
        """Test message building with all valid gender codes."""
        valid_genders = ["M", "F", "O", "U"]
        
        for gender in valid_genders:
            patient = PatientDemographics(
                patient_id=f"TEST-{gender}",
                patient_id_oid="1.2.3.4.5",
                first_name="Test",
                last_name="Patient",
                dob=date(2000, 1, 1),
                gender=gender
            )
            
            xml = build_pix_add_message(patient)
            root = etree.fromstring(xml.encode("utf-8"))
            
            gender_elem = root.find(f".//{{{HL7_NS}}}administrativeGenderCode")
            assert gender_elem is not None
            assert gender_elem.get("code") == gender
    
    def test_build_message_returns_xml_string(self, minimal_patient):
        """Test that function returns XML string."""
        result = build_pix_add_message(minimal_patient)
        assert isinstance(result, str)
        assert result.startswith("<?xml")
    
    def test_build_message_xml_is_well_formed(self, minimal_patient):
        """Test that generated XML is well-formed."""
        xml = build_pix_add_message(minimal_patient)
        # Should not raise exception
        etree.fromstring(xml.encode("utf-8"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
