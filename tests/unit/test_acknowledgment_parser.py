"""Unit tests for acknowledgment parser functionality."""

import pytest
from lxml import etree

from src.ihe_test_util.ihe_transactions.parsers import (
    parse_acknowledgment,
    parse_pix_add_acknowledgment,
    AcknowledgmentResponse,
    AcknowledgmentDetail,
    _extract_patient_identifiers,
    _extract_query_continuation,
)


# Test fixtures - sample acknowledgment XMLs
@pytest.fixture
def ack_success_aa():
    """Successful acknowledgment with status AA."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
      <id root="2.16.840.1.113883.3.72.5.9.1" extension="ACK-12345"/>
      <creationTime value="20251116140530"/>
      <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
      <processingCode code="P"/>
      <processingModeCode code="T"/>
      <acceptAckCode code="AL"/>
      <acknowledgement>
        <typeCode code="AA"/>
        <targetMessage>
          <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-456"/>
        </targetMessage>
      </acknowledgement>
    </MCCI_IN000002UV01>"""


@pytest.fixture
def ack_error_ae():
    """Error acknowledgment with status AE and error details."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
      <id root="2.16.840.1.113883.3.72.5.9.1" extension="ACK-67890"/>
      <creationTime value="20251116140530"/>
      <acknowledgement>
        <typeCode code="AE"/>
        <targetMessage>
          <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-789"/>
        </targetMessage>
        <acknowledgementDetail typeCode="E">
          <code code="204" codeSystem="2.16.840.1.113883.12.357"/>
          <text>Unknown patient identifier domain</text>
        </acknowledgementDetail>
      </acknowledgement>
    </MCCI_IN000002UV01>"""


@pytest.fixture
def ack_rejected_ar():
    """Rejected acknowledgment with status AR."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.1" extension="ACK-99999"/>
      <acknowledgement>
        <typeCode code="AR"/>
        <targetMessage>
          <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-111"/>
        </targetMessage>
        <acknowledgementDetail typeCode="E">
          <text>Message rejected due to policy violation</text>
        </acknowledgementDetail>
      </acknowledgement>
    </MCCI_IN000002UV01>"""


@pytest.fixture
def ack_with_patient_ids():
    """Acknowledgment containing patient identifiers."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.1" extension="ACK-11111"/>
      <acknowledgement>
        <typeCode code="AA"/>
      </acknowledgement>
      <controlActProcess>
        <subject typeCode="SUBJ">
          <registrationEvent>
            <subject1 typeCode="SBJ">
              <patient>
                <id root="2.16.840.1.113883.3.72.5.9.1" extension="PAT123456"/>
                <id root="1.2.840.114350.1.13.99998.8734" extension="EID987654"/>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </MCCI_IN000002UV01>"""


@pytest.fixture
def ack_with_query_continuation():
    """Acknowledgment with query continuation information."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.1" extension="ACK-22222"/>
      <acknowledgement>
        <typeCode code="AA"/>
      </acknowledgement>
      <controlActProcess>
        <queryAck>
          <queryResponseCode code="OK"/>
          <resultTotalQuantity value="10"/>
          <resultCurrentQuantity value="5"/>
          <resultRemainingQuantity value="5"/>
        </queryAck>
      </controlActProcess>
    </MCCI_IN000002UV01>"""


@pytest.fixture
def ack_malformed_xml():
    """Malformed XML for error testing."""
    return """<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="broken
      <acknowledgement>
        <typeCode code="AA"/>
    """


@pytest.fixture
def ack_missing_acknowledgement():
    """Valid XML but missing acknowledgement element."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-123"/>
    </MCCI_IN000002UV01>"""


@pytest.fixture
def ack_missing_type_code():
    """Acknowledgement without typeCode."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-123"/>
      <acknowledgement>
        <targetMessage>
          <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-456"/>
        </targetMessage>
      </acknowledgement>
    </MCCI_IN000002UV01>"""


@pytest.fixture
def ack_invalid_namespace():
    """XML with wrong namespace."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="http://wrong-namespace.org">
      <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-123"/>
      <acknowledgement>
        <typeCode code="AA"/>
      </acknowledgement>
    </MCCI_IN000002UV01>"""


# Test successful acknowledgment parsing
def test_parse_acknowledgment_success_aa(ack_success_aa):
    """Test parsing successful AA acknowledgment."""
    result = parse_acknowledgment(ack_success_aa)
    
    assert isinstance(result, AcknowledgmentResponse)
    assert result.status == "AA"
    assert result.is_success is True
    assert result.message_id is not None
    assert "ACK-12345" in result.message_id
    assert result.target_message_id is not None
    assert "MSG-456" in result.target_message_id
    assert len(result.details) == 0


def test_parse_acknowledgment_error_ae(ack_error_ae):
    """Test parsing error AE acknowledgment."""
    result = parse_acknowledgment(ack_error_ae)
    
    assert result.status == "AE"
    assert result.is_success is False
    assert "ACK-67890" in result.message_id
    assert "MSG-789" in result.target_message_id
    assert len(result.details) == 1
    assert result.details[0].type_code == "E"
    assert "Unknown patient identifier domain" in result.details[0].text
    assert result.details[0].code == "204"
    assert result.details[0].code_system == "2.16.840.1.113883.12.357"


def test_parse_acknowledgment_rejected_ar(ack_rejected_ar):
    """Test parsing rejected AR acknowledgment."""
    result = parse_acknowledgment(ack_rejected_ar)
    
    assert result.status == "AR"
    assert result.is_success is False
    assert "ACK-99999" in result.message_id
    assert "MSG-111" in result.target_message_id
    assert len(result.details) == 1
    assert "policy violation" in result.details[0].text


def test_parse_acknowledgment_commit_accept_ca():
    """Test parsing commit accept CA acknowledgment."""
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <acknowledgement>
        <typeCode code="CA"/>
      </acknowledgement>
    </MCCI_IN000002UV01>"""
    
    result = parse_acknowledgment(ack_xml)
    
    assert result.status == "CA"
    assert result.is_success is True


# Test patient identifier extraction
def test_parse_acknowledgment_with_patient_ids(ack_with_patient_ids):
    """Test extracting patient identifiers from acknowledgment."""
    result = parse_acknowledgment(ack_with_patient_ids)
    
    assert result.status == "AA"
    assert result.is_success is True
    assert result.patient_identifiers is not None
    assert result.patient_identifiers["patient_id"] == "PAT123456"
    assert result.patient_identifiers["patient_id_root"] == "2.16.840.1.113883.3.72.5.9.1"
    assert "additional_ids" in result.patient_identifiers
    assert len(result.patient_identifiers["additional_ids"]) == 1
    assert result.patient_identifiers["additional_ids"][0]["extension"] == "EID987654"
    assert result.patient_identifiers["additional_ids"][0]["root"] == "1.2.840.114350.1.13.99998.8734"


def test_extract_patient_identifiers_multiple_ids(ack_with_patient_ids):
    """Test _extract_patient_identifiers with multiple IDs."""
    root = etree.fromstring(ack_with_patient_ids.encode("utf-8"))
    identifiers = _extract_patient_identifiers(root)
    
    assert identifiers["patient_id"] == "PAT123456"
    assert identifiers["patient_id_root"] == "2.16.840.1.113883.3.72.5.9.1"
    assert len(identifiers["additional_ids"]) == 1


def test_extract_patient_identifiers_no_ids(ack_success_aa):
    """Test _extract_patient_identifiers when no patient IDs present."""
    root = etree.fromstring(ack_success_aa.encode("utf-8"))
    identifiers = _extract_patient_identifiers(root)
    
    assert identifiers == {}


# Test query continuation extraction
def test_parse_acknowledgment_with_query_continuation(ack_with_query_continuation):
    """Test extracting query continuation information."""
    result = parse_acknowledgment(ack_with_query_continuation)
    
    assert result.status == "AA"
    assert result.query_continuation is not None
    assert result.query_continuation["query_response_code"] == "OK"
    assert result.query_continuation["result_total_quantity"] == 10
    assert result.query_continuation["result_current_quantity"] == 5
    assert result.query_continuation["result_remaining_quantity"] == 5


def test_extract_query_continuation_present(ack_with_query_continuation):
    """Test _extract_query_continuation when data is present."""
    root = etree.fromstring(ack_with_query_continuation.encode("utf-8"))
    continuation = _extract_query_continuation(root)
    
    assert continuation is not None
    assert continuation["query_response_code"] == "OK"
    assert continuation["result_total_quantity"] == 10


def test_extract_query_continuation_absent(ack_success_aa):
    """Test _extract_query_continuation when no data present."""
    root = etree.fromstring(ack_success_aa.encode("utf-8"))
    continuation = _extract_query_continuation(root)
    
    assert continuation is None


# Test error handling
def test_parse_acknowledgment_malformed_xml(ack_malformed_xml):
    """Test parsing malformed XML raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        parse_acknowledgment(ack_malformed_xml)
    
    assert "Invalid acknowledgment XML" in str(exc_info.value)
    assert "MCCI_IN000002UV01 message" in str(exc_info.value)


def test_parse_acknowledgment_missing_acknowledgement_element(ack_missing_acknowledgement):
    """Test parsing XML without acknowledgement element."""
    with pytest.raises(ValueError) as exc_info:
        parse_acknowledgment(ack_missing_acknowledgement)
    
    assert "No acknowledgement element found" in str(exc_info.value)
    assert "urn:hl7-org:v3" in str(exc_info.value)


def test_parse_acknowledgment_missing_type_code(ack_missing_type_code):
    """Test parsing acknowledgement without typeCode."""
    with pytest.raises(ValueError) as exc_info:
        parse_acknowledgment(ack_missing_type_code)
    
    assert "No typeCode element found" in str(exc_info.value)
    assert "AA|AE|AR|CA|CE|CR" in str(exc_info.value)


def test_parse_acknowledgment_invalid_namespace(ack_invalid_namespace):
    """Test parsing XML with wrong namespace logs warning."""
    # Should still parse but log warning
    result = parse_acknowledgment(ack_invalid_namespace)
    
    assert result.status == "AA"
    assert result.is_success is True


# Test to_dict() method
def test_acknowledgment_response_to_dict(ack_error_ae):
    """Test converting AcknowledgmentResponse to dictionary."""
    response = parse_acknowledgment(ack_error_ae)
    data = response.to_dict()
    
    assert isinstance(data, dict)
    assert data["status"] == "AE"
    assert data["is_success"] is False
    assert "message_id" in data
    assert "target_message_id" in data
    assert isinstance(data["details"], list)
    assert len(data["details"]) == 1
    assert data["details"][0]["type_code"] == "E"
    assert data["details"][0]["text"] == "Unknown patient identifier domain"
    assert data["patient_identifiers"] == {}
    assert data["query_continuation"] is None
    
    # Verify JSON serializable
    import json
    json_str = json.dumps(data)
    assert isinstance(json_str, str)


def test_acknowledgment_response_to_dict_with_patient_ids(ack_with_patient_ids):
    """Test to_dict() with patient identifiers."""
    response = parse_acknowledgment(ack_with_patient_ids)
    data = response.to_dict()
    
    assert data["patient_identifiers"]["patient_id"] == "PAT123456"
    assert "additional_ids" in data["patient_identifiers"]


def test_acknowledgment_response_to_dict_with_query_continuation(ack_with_query_continuation):
    """Test to_dict() with query continuation."""
    response = parse_acknowledgment(ack_with_query_continuation)
    data = response.to_dict()
    
    assert data["query_continuation"] is not None
    assert data["query_continuation"]["query_response_code"] == "OK"


# Test PIX Add acknowledgment wrapper
def test_pix_add_acknowledgment_wrapper(ack_success_aa):
    """Test parse_pix_add_acknowledgment delegates to parse_acknowledgment."""
    result1 = parse_pix_add_acknowledgment(ack_success_aa)
    result2 = parse_acknowledgment(ack_success_aa)
    
    assert result1.status == result2.status
    assert result1.is_success == result2.is_success
    assert result1.message_id == result2.message_id


# Test bytes input handling
def test_parse_acknowledgment_bytes_input(ack_success_aa):
    """Test parsing acknowledgment from bytes input."""
    ack_bytes = ack_success_aa.encode("utf-8")
    result = parse_acknowledgment(ack_bytes)
    
    assert result.status == "AA"
    assert result.is_success is True


# Test all status codes
@pytest.mark.parametrize("status_code,expected_success", [
    ("AA", True),
    ("AE", False),
    ("AR", False),
    ("CA", True),
    ("CE", False),
    ("CR", False),
])
def test_all_status_codes(status_code, expected_success):
    """Test all valid acknowledgment status codes."""
    ack_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <acknowledgement>
        <typeCode code="{status_code}"/>
      </acknowledgement>
    </MCCI_IN000002UV01>"""
    
    result = parse_acknowledgment(ack_xml)
    
    assert result.status == status_code
    assert result.is_success == expected_success


# Test edge cases
def test_acknowledgment_detail_without_code():
    """Test acknowledgement detail without code element."""
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <acknowledgement>
        <typeCode code="AE"/>
        <acknowledgementDetail typeCode="W">
          <text>This is a warning message</text>
        </acknowledgementDetail>
      </acknowledgement>
    </MCCI_IN000002UV01>"""
    
    result = parse_acknowledgment(ack_xml)
    
    assert len(result.details) == 1
    assert result.details[0].type_code == "W"
    assert result.details[0].text == "This is a warning message"
    assert result.details[0].code is None
    assert result.details[0].code_system is None


def test_acknowledgment_detail_without_text():
    """Test acknowledgement detail with missing text element."""
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <acknowledgement>
        <typeCode code="AE"/>
        <acknowledgementDetail typeCode="E">
          <code code="500" codeSystem="2.16.840.1.113883.12.357"/>
        </acknowledgementDetail>
      </acknowledgement>
    </MCCI_IN000002UV01>"""
    
    result = parse_acknowledgment(ack_xml)
    
    assert len(result.details) == 1
    assert result.details[0].text == "No detail message provided"


def test_query_continuation_invalid_quantities():
    """Test query continuation with invalid quantity values."""
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <acknowledgement>
        <typeCode code="AA"/>
      </acknowledgement>
      <controlActProcess>
        <queryAck>
          <queryResponseCode code="OK"/>
          <resultTotalQuantity value="invalid"/>
          <resultCurrentQuantity value="also-invalid"/>
        </queryAck>
      </controlActProcess>
    </MCCI_IN000002UV01>"""
    
    result = parse_acknowledgment(ack_xml)
    
    # Should still parse, but invalid quantities should be skipped
    assert result.query_continuation is not None
    assert result.query_continuation["query_response_code"] == "OK"
    assert "result_total_quantity" not in result.query_continuation
    assert "result_current_quantity" not in result.query_continuation
