"""Integration tests for HL7v3 message construction and acknowledgment parsing."""

import pytest
from lxml import etree
from src.ihe_test_util.ihe_transactions.pix_add import (
    PatientDemographics,
    build_pix_add_message,
)
from src.ihe_test_util.ihe_transactions.parsers import (
    parse_acknowledgment,
    parse_pix_add_acknowledgment,
    AcknowledgmentResponse,
    AcknowledgmentDetail,
)


# HL7v3 and SOAP namespaces
HL7_NS = "urn:hl7-org:v3"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"


def extract_hl7v3_from_soap(message_xml: str) -> etree._Element:
    """Extract HL7v3 message from SOAP envelope.
    
    Args:
        message_xml: SOAP-wrapped message
        
    Returns:
        The HL7v3 message element from SOAP Body
    """
    root = etree.fromstring(message_xml.encode("utf-8"))
    
    # Check if this is a SOAP envelope
    if root.tag == f"{{{SOAP_NS}}}Envelope":
        # Extract from SOAP Body
        body = root.find(f"{{{SOAP_NS}}}Body")
        if body is not None and len(body) > 0:
            return body[0]  # Return first child (the HL7v3 message)
    
    # If not SOAP-wrapped, return as-is
    return root


@pytest.fixture
def sample_patient():
    """Sample patient demographics for testing."""
    return PatientDemographics(
        patient_id="PAT987654",
        patient_id_root="2.16.840.1.113883.3.72.5.9.1",
        given_name="Jane",
        family_name="Smith",
        gender="F",
        birth_date="19900515",
        street_address="456 Oak Avenue",
        city="Seattle",
        state="WA",
        postal_code="98101",
        country="US",
    )


@pytest.fixture
def sample_ack_aa():
    """Sample AA (Application Accept) acknowledgment."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
  <id root="2.16.840.1.113883.3.72.5.2" extension="ACK-123456"/>
  <creationTime value="20251103194500"/>
  <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
  <processingCode code="P"/>
  <processingModeCode code="T"/>
  <acceptAckCode code="NE"/>
  <acknowledgement>
    <typeCode code="AA"/>
    <targetMessage>
      <id root="original-message-id"/>
    </targetMessage>
  </acknowledgement>
</MCCI_IN000002UV01>"""


@pytest.fixture
def sample_ack_ae_with_details():
    """Sample AE (Application Error) acknowledgment with error details."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
  <id root="2.16.840.1.113883.3.72.5.2" extension="ACK-ERR-789"/>
  <creationTime value="20251103194530"/>
  <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
  <processingCode code="P"/>
  <processingModeCode code="T"/>
  <acceptAckCode code="NE"/>
  <acknowledgement>
    <typeCode code="AE"/>
    <targetMessage>
      <id root="failed-message-id" extension="MSG-001"/>
    </targetMessage>
    <acknowledgementDetail typeCode="E">
      <text>Patient identifier already exists in registry</text>
      <code code="DUPLICATE_ID" codeSystem="2.16.840.1.113883.3.72.5.99"/>
    </acknowledgementDetail>
  </acknowledgement>
</MCCI_IN000002UV01>"""


@pytest.fixture
def sample_ack_ar():
    """Sample AR (Application Reject) acknowledgment."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
  <id root="2.16.840.1.113883.3.72.5.2" extension="ACK-REJ-999"/>
  <creationTime value="20251103194600"/>
  <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
  <processingCode code="P"/>
  <processingModeCode code="T"/>
  <acceptAckCode code="NE"/>
  <acknowledgement>
    <typeCode code="AR"/>
    <targetMessage>
      <id root="rejected-message-id"/>
    </targetMessage>
    <acknowledgementDetail typeCode="E">
      <text>System temporarily unavailable - retry later</text>
    </acknowledgementDetail>
  </acknowledgement>
</MCCI_IN000002UV01>"""


class TestPRPAIN201301UV02MessageConstruction:
    """Test PRPA_IN201301UV02 (PIX Add) message construction."""
    
    def test_message_has_correct_root_element(self, sample_patient):
        """Test that message has correct root element with namespace.
        
        Acceptance Criteria: AC 2 - Build sample PRPA_IN201301UV02 message using lxml
        """
        # Act
        message_xml = build_pix_add_message(sample_patient)
        root = extract_hl7v3_from_soap(message_xml)
        
        # Assert
        assert root.tag == f"{{{HL7_NS}}}PRPA_IN201301UV02"
        assert root.get("ITSVersion") == "XML_1.0"
    
    def test_message_has_required_hl7v3_namespaces(self, sample_patient):
        """Test that message declares required HL7v3 namespaces.
        
        Acceptance Criteria: AC 5 - Verify correct HL7v3 namespace declarations and prefixes
        """
        # Act
        message_xml = build_pix_add_message(sample_patient)
        root = extract_hl7v3_from_soap(message_xml)
        
        # Assert
        assert root.nsmap[None] == HL7_NS
        assert "xsi" in root.nsmap
        assert root.nsmap["xsi"] == "http://www.w3.org/2001/XMLSchema-instance"
    
    def test_message_has_required_header_elements(self, sample_patient):
        """Test that message includes all required header elements.
        
        Acceptance Criteria: AC 2 - Build sample PRPA_IN201301UV02 message using lxml
        """
        # Act
        message_xml = build_pix_add_message(sample_patient)
        root = extract_hl7v3_from_soap(message_xml)
        
        # Assert - Required header elements
        id_elem = root.find(f"{{{HL7_NS}}}id")
        assert id_elem is not None
        assert id_elem.get("root") is not None
        
        creation_time = root.find(f"{{{HL7_NS}}}creationTime")
        assert creation_time is not None
        assert creation_time.get("value") is not None
        
        interaction_id = root.find(f"{{{HL7_NS}}}interactionId")
        assert interaction_id is not None
        assert interaction_id.get("root") == "2.16.840.1.113883.1.6"
        assert interaction_id.get("extension") == "PRPA_IN201301UV02"
        
        processing_code = root.find(f"{{{HL7_NS}}}processingCode")
        assert processing_code is not None
        assert processing_code.get("code") == "P"
        
        processing_mode = root.find(f"{{{HL7_NS}}}processingModeCode")
        assert processing_mode is not None
        assert processing_mode.get("code") == "T"
        
        accept_ack = root.find(f"{{{HL7_NS}}}acceptAckCode")
        assert accept_ack is not None
        assert accept_ack.get("code") == "AL"
    
    def test_message_has_receiver_and_sender(self, sample_patient):
        """Test that message includes receiver and sender elements.
        
        Acceptance Criteria: AC 2 - Build sample PRPA_IN201301UV02 message using lxml
        """
        # Act
        message_xml = build_pix_add_message(sample_patient)
        root = extract_hl7v3_from_soap(message_xml)
        
        # Assert - Receiver
        receiver = root.find(f"{{{HL7_NS}}}receiver")
        assert receiver is not None
        assert receiver.get("typeCode") == "RCV"
        
        # Assert - Sender
        sender = root.find(f"{{{HL7_NS}}}sender")
        assert sender is not None
        assert sender.get("typeCode") == "SND"
    
    def test_message_has_control_act_process_structure(self, sample_patient):
        """Test that message has correct controlActProcess structure.
        
        Acceptance Criteria: AC 2 - Build sample PRPA_IN201301UV02 message using lxml
        """
        # Act
        message_xml = build_pix_add_message(sample_patient)
        root = extract_hl7v3_from_soap(message_xml)
        
        # Assert
        control_act = root.find(f"{{{HL7_NS}}}controlActProcess")
        assert control_act is not None
        assert control_act.get("classCode") == "CACT"
        assert control_act.get("moodCode") == "EVN"
        
        code_elem = control_act.find(f"{{{HL7_NS}}}code")
        assert code_elem is not None
        assert code_elem.get("code") == "PRPA_TE201301UV02"
    
    def test_message_inserts_patient_demographics_correctly(self, sample_patient):
        """Test that patient demographics are correctly inserted.
        
        Acceptance Criteria: AC 4 - Test patient demographic data insertion
        """
        # Act
        message_xml = build_pix_add_message(sample_patient)
        root = extract_hl7v3_from_soap(message_xml)
        
        # Assert - Patient ID
        patient_id_elem = root.find(f".//{{{HL7_NS}}}patient/{{{HL7_NS}}}id")
        assert patient_id_elem is not None
        assert patient_id_elem.get("extension") == "PAT987654"
        assert patient_id_elem.get("root") == "2.16.840.1.113883.3.72.5.9.1"
        
        # Assert - Patient name
        given_name = root.find(f".//{{{HL7_NS}}}given")
        assert given_name is not None
        assert given_name.text == "Jane"
        
        family_name = root.find(f".//{{{HL7_NS}}}family")
        assert family_name is not None
        assert family_name.text == "Smith"
        
        # Assert - Gender
        gender = root.find(f".//{{{HL7_NS}}}administrativeGenderCode")
        assert gender is not None
        assert gender.get("code") == "F"
        
        # Assert - Birth date
        birth_time = root.find(f".//{{{HL7_NS}}}birthTime")
        assert birth_time is not None
        assert birth_time.get("value") == "19900515"
        
        # Assert - Address
        street = root.find(f".//{{{HL7_NS}}}streetAddressLine")
        assert street is not None
        assert street.text == "456 Oak Avenue"
        
        city = root.find(f".//{{{HL7_NS}}}city")
        assert city is not None
        assert city.text == "Seattle"
    
    def test_message_with_minimal_demographics(self):
        """Test message construction with minimal required demographics."""
        # Arrange
        minimal_patient = PatientDemographics(
            patient_id="MIN001",
            patient_id_root="2.16.840.1.113883.3.72.5.9.1",
            given_name="Test",
            family_name="Minimal",
            gender="U",
            birth_date="20000101",
        )
        
        # Act
        message_xml = build_pix_add_message(minimal_patient)
        root = extract_hl7v3_from_soap(message_xml)
        
        # Assert - Basic structure still correct
        assert root.tag == f"{{{HL7_NS}}}PRPA_IN201301UV02"
        patient_id_elem = root.find(f".//{{{HL7_NS}}}patient/{{{HL7_NS}}}id")
        assert patient_id_elem.get("extension") == "MIN001"


class TestMCCIIN000002UV01AcknowledgmentParsing:
    """Test MCCI_IN000002UV01 acknowledgment parsing."""
    
    def test_parse_aa_acknowledgment_success(self, sample_ack_aa):
        """Test parsing AA (Application Accept) acknowledgment.
        
        Acceptance Criteria: AC 6 - Parse sample MCCI_IN000002UV01 acknowledgment response
        Acceptance Criteria: AC 7 - Extract status code (AA/AE/AR)
        """
        # Act
        result = parse_acknowledgment(sample_ack_aa)
        
        # Assert
        assert isinstance(result, AcknowledgmentResponse)
        assert result.status == "AA"
        assert result.is_success is True
        assert result.target_message_id == "original-message-id"
        assert len(result.details) == 0
    
    def test_parse_ae_acknowledgment_with_error_details(self, sample_ack_ae_with_details):
        """Test parsing AE (Application Error) acknowledgment with error details.
        
        Acceptance Criteria: AC 7 - Extract status code (AA/AE/AR) and patient identifiers
        """
        # Act
        result = parse_acknowledgment(sample_ack_ae_with_details)
        
        # Assert
        assert result.status == "AE"
        assert result.is_success is False
        assert result.target_message_id == "failed-message-id::MSG-001"
        assert len(result.details) == 1
        
        detail = result.details[0]
        assert isinstance(detail, AcknowledgmentDetail)
        assert detail.type_code == "E"
        assert "already exists" in detail.text
        assert detail.code == "DUPLICATE_ID"
        assert detail.code_system == "2.16.840.1.113883.3.72.5.99"
    
    def test_parse_ar_acknowledgment_reject(self, sample_ack_ar):
        """Test parsing AR (Application Reject) acknowledgment.
        
        Acceptance Criteria: AC 7 - Extract status code (AA/AE/AR)
        """
        # Act
        result = parse_acknowledgment(sample_ack_ar)
        
        # Assert
        assert result.status == "AR"
        assert result.is_success is False
        assert len(result.details) == 1
        assert "temporarily unavailable" in result.details[0].text
    
    def test_parse_acknowledgment_missing_element_raises_error(self):
        """Test that parser raises error when acknowledgement element missing."""
        # Arrange
        invalid_ack = """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
  <id root="test"/>
</MCCI_IN000002UV01>"""
        
        # Act & Assert
        with pytest.raises(ValueError, match="No acknowledgement element found"):
            parse_acknowledgment(invalid_ack)
    
    def test_parse_acknowledgment_missing_typecode_raises_error(self):
        """Test that parser raises error when typeCode missing."""
        # Arrange
        invalid_ack = """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
  <acknowledgement>
  </acknowledgement>
</MCCI_IN000002UV01>"""
        
        # Act & Assert
        with pytest.raises(ValueError, match="No typeCode element found"):
            parse_acknowledgment(invalid_ack)
    
    def test_parse_acknowledgment_handles_bytes_input(self, sample_ack_aa):
        """Test that parser handles bytes input correctly."""
        # Act
        result = parse_acknowledgment(sample_ack_aa.encode("utf-8"))
        
        # Assert
        assert result.status == "AA"
        assert result.is_success is True
    
    def test_parse_pix_add_acknowledgment_wrapper(self, sample_ack_aa):
        """Test PIX Add acknowledgment parsing wrapper function."""
        # Act
        result = parse_pix_add_acknowledgment(sample_ack_aa)
        
        # Assert
        assert result.status == "AA"
        assert result.is_success is True


class TestHL7v3MessageValidation:
    """Test HL7v3 message validation and edge cases."""
    
    def test_invalid_gender_raises_validation_error(self):
        """Test that invalid gender code raises validation error."""
        # Arrange
        patient = PatientDemographics(
            patient_id="TEST001",
            patient_id_root="2.16.840.1.113883.3.72.5.9.1",
            given_name="Invalid",
            family_name="Gender",
            gender="Z",  # Invalid
            birth_date="20000101",
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid gender 'Z'. Must be M, F, O, or U."):
            build_pix_add_message(patient)
    
    def test_message_with_all_valid_gender_codes(self):
        """Test message construction with all valid gender codes."""
        # Arrange
        valid_genders = ["M", "F", "O", "U"]
        
        for gender in valid_genders:
            patient = PatientDemographics(
                patient_id=f"TEST-{gender}",
                patient_id_root="2.16.840.1.113883.3.72.5.9.1",
                given_name="Test",
                family_name="Patient",
                gender=gender,
                birth_date="20000101",
            )
            
            # Act
            message_xml = build_pix_add_message(patient)
            root = extract_hl7v3_from_soap(message_xml)
            
            # Assert
            gender_elem = root.find(f".//{{{HL7_NS}}}administrativeGenderCode")
            assert gender_elem.get("code") == gender


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
