"""Unit tests for PIX Add endpoint."""

import pytest
from lxml import etree

from src.ihe_test_util.mock_server.pix_add_endpoint import (
    extract_patient_from_prpa,
    generate_acknowledgment,
    generate_soap_fault,
)


class TestExtractPatientFromPRPA:
    """Test patient data extraction from PRPA_IN201301UV02 messages."""

    def test_extract_patient_from_valid_prpa(self):
        """Test extraction from valid PRPA message with all fields."""
        soap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
      <id root="1.2.3.4.5" extension="MSG-12345"/>
      <creationTime value="20250106150000"/>
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <id root="1.2.840.114350" extension="PAT-001"/>
                <patientPerson>
                  <name>
                    <given>John</given>
                    <family>Doe</family>
                  </name>
                  <birthTime value="19800101"/>
                  <administrativeGenderCode code="M"/>
                  <addr>
                    <streetAddressLine>123 Main St</streetAddressLine>
                    <city>Springfield</city>
                    <state>IL</state>
                    <postalCode>62701</postalCode>
                  </addr>
                </patientPerson>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        result = extract_patient_from_prpa(soap_xml)

        assert result["request_message_id"] == "MSG-12345"
        assert result["request_message_id_oid"] == "1.2.3.4.5"
        assert result["patient_id"] == "PAT-001"
        assert result["patient_id_oid"] == "1.2.840.114350"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["birth_date"] == "19800101"
        assert result["gender"] == "M"
        assert result["street"] == "123 Main St"
        assert result["city"] == "Springfield"
        assert result["state"] == "IL"
        assert result["postal_code"] == "62701"

    def test_extract_patient_minimal_demographics(self):
        """Test extraction with minimal demographics (only required fields)."""
        soap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <id root="1.2.3" extension="MSG-123"/>
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <id root="1.2.3.4" extension="PAT-002"/>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        result = extract_patient_from_prpa(soap_xml)

        assert result["patient_id"] == "PAT-002"
        assert result["patient_id_oid"] == "1.2.3.4"
        assert "first_name" not in result
        assert "last_name" not in result
        assert "birth_date" not in result
        assert "gender" not in result

    def test_extract_patient_female_gender(self):
        """Test extraction with female gender code."""
        soap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <id root="1.2.3" extension="MSG-456"/>
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <id root="1.2.3.4" extension="PAT-003"/>
                <patientPerson>
                  <name>
                    <given>Jane</given>
                    <family>Smith</family>
                  </name>
                  <administrativeGenderCode code="F"/>
                </patientPerson>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        result = extract_patient_from_prpa(soap_xml)

        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Smith"
        assert result["gender"] == "F"

    def test_malformed_xml_raises_error(self):
        """Test that malformed XML raises ValueError."""
        malformed_xml = "This is not XML at all"

        with pytest.raises(ValueError) as exc_info:
            extract_patient_from_prpa(malformed_xml)

        assert "Malformed XML" in str(exc_info.value)

    def test_missing_prpa_element_raises_error(self):
        """Test that missing PRPA_IN201301UV02 element raises ValueError."""
        soap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <SomeOtherMessage>Not a PRPA message</SomeOtherMessage>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        with pytest.raises(ValueError) as exc_info:
            extract_patient_from_prpa(soap_xml)

        assert "Missing PRPA_IN201301UV02 element" in str(exc_info.value)

    def test_missing_message_id_raises_error(self):
        """Test that missing message ID raises ValueError."""
        soap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <id root="1.2.3.4" extension="PAT-001"/>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        with pytest.raises(ValueError) as exc_info:
            extract_patient_from_prpa(soap_xml)

        assert "Missing message ID" in str(exc_info.value)

    def test_missing_patient_element_raises_error(self):
        """Test that missing patient element raises ValueError."""
        soap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <id root="1.2.3" extension="MSG-123"/>
      <controlActProcess>
      </controlActProcess>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        with pytest.raises(ValueError) as exc_info:
            extract_patient_from_prpa(soap_xml)

        assert "Missing patient element" in str(exc_info.value)

    def test_missing_patient_id_raises_error(self):
        """Test that missing patient identifier raises ValueError."""
        soap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <id root="1.2.3" extension="MSG-123"/>
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <!-- Missing patient id -->
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        with pytest.raises(ValueError) as exc_info:
            extract_patient_from_prpa(soap_xml)

        assert "Missing patient identifier" in str(exc_info.value)

    def test_empty_patient_id_extension_raises_error(self):
        """Test that empty patient ID extension raises ValueError."""
        soap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <id root="1.2.3" extension="MSG-123"/>
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <id root="1.2.3.4" extension=""/>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        with pytest.raises(ValueError) as exc_info:
            extract_patient_from_prpa(soap_xml)

        assert "Missing patient identifier extension" in str(exc_info.value)


class TestGenerateAcknowledgment:
    """Test MCCI_IN000002UV01 acknowledgment generation."""

    def test_generate_acknowledgment_success(self):
        """Test acknowledgment generation with AA status."""
        ack_xml = generate_acknowledgment(
            request_message_id="MSG-12345",
            request_message_id_oid="1.2.3.4.5",
            patient_id="PAT-001",
            patient_id_oid="1.2.840.114350",
            status="AA"
        )

        # Parse acknowledgment
        tree = etree.fromstring(ack_xml.encode("utf-8"))
        ns = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "hl7": "urn:hl7-org:v3"
        }

        # Verify SOAP envelope structure
        assert tree.tag == "{http://schemas.xmlsoap.org/soap/envelope/}Envelope"
        body = tree.find("soap:Body", namespaces=ns)
        assert body is not None

        # Verify MCCI message
        mcci = body.find("hl7:MCCI_IN000002UV01", namespaces=ns)
        assert mcci is not None
        assert mcci.get("ITSVersion") == "XML_1.0"

        # Verify response message ID exists and uses request OID
        response_id = mcci.find("hl7:id", namespaces=ns)
        assert response_id is not None
        assert response_id.get("root") == "1.2.3.4.5"
        assert response_id.get("extension") is not None

        # Verify creation time exists
        creation_time = mcci.find("hl7:creationTime", namespaces=ns)
        assert creation_time is not None
        assert creation_time.get("value") is not None

        # Verify acknowledgment status
        ack = mcci.find("hl7:acknowledgement", namespaces=ns)
        assert ack is not None
        type_code = ack.find("hl7:typeCode", namespaces=ns)
        assert type_code is not None
        assert type_code.get("code") == "AA"

        # Verify correlation ID (target message)
        target_msg = ack.find("hl7:targetMessage", namespaces=ns)
        assert target_msg is not None
        target_id = target_msg.find("hl7:id", namespaces=ns)
        assert target_id is not None
        assert target_id.get("root") == "1.2.3.4.5"
        assert target_id.get("extension") == "MSG-12345"

        # Verify patient identifiers are echoed back
        patient = mcci.find(
            ".//hl7:controlActProcess/hl7:subject/hl7:registrationEvent/"
            "hl7:subject1/hl7:patient/hl7:id",
            namespaces=ns
        )
        assert patient is not None
        assert patient.get("root") == "1.2.840.114350"
        assert patient.get("extension") == "PAT-001"

    def test_generate_acknowledgment_error_status(self):
        """Test acknowledgment generation with AE (error) status."""
        ack_xml = generate_acknowledgment(
            request_message_id="MSG-ERROR",
            request_message_id_oid="1.2.3",
            patient_id="PAT-999",
            patient_id_oid="1.2.3.4",
            status="AE"
        )

        tree = etree.fromstring(ack_xml.encode("utf-8"))
        ns = {"hl7": "urn:hl7-org:v3"}

        # Verify error status
        type_code = tree.find(
            ".//hl7:acknowledgement/hl7:typeCode",
            namespaces=ns
        )
        assert type_code is not None
        assert type_code.get("code") == "AE"


class TestGenerateSOAPFault:
    """Test SOAP fault generation."""

    def test_generate_soap_fault_basic(self):
        """Test basic SOAP fault generation."""
        fault_xml = generate_soap_fault(
            faultcode="soap:Sender",
            faultstring="Invalid request"
        )

        tree = etree.fromstring(fault_xml.encode("utf-8"))
        ns = {"soap": "http://www.w3.org/2003/05/soap-envelope"}

        # Verify SOAP envelope
        assert tree.tag == "{http://www.w3.org/2003/05/soap-envelope}Envelope"

        # Verify fault structure
        fault = tree.find(".//soap:Fault", namespaces=ns)
        assert fault is not None

        code = fault.find("soap:Code/soap:Value", namespaces=ns)
        assert code is not None
        assert code.text == "soap:Sender"

        reason = fault.find("soap:Reason/soap:Text", namespaces=ns)
        assert reason is not None
        assert reason.text == "Invalid request"

    def test_generate_soap_fault_with_detail(self):
        """Test SOAP fault generation with detail."""
        fault_xml = generate_soap_fault(
            faultcode="soap:Receiver",
            faultstring="Server error",
            detail="Database connection failed"
        )

        tree = etree.fromstring(fault_xml.encode("utf-8"))
        ns = {"soap": "http://www.w3.org/2003/05/soap-envelope"}

        # Verify detail is included
        detail = tree.find(".//soap:Detail/error", namespaces=ns)
        assert detail is not None
        assert detail.text == "Database connection failed"

    def test_generate_soap_fault_sender_code(self):
        """Test SOAP fault with Sender fault code."""
        fault_xml = generate_soap_fault(
            faultcode="soap:Sender",
            faultstring="Client error"
        )

        assert "soap:Sender" in fault_xml
        assert "Client error" in fault_xml

    def test_generate_soap_fault_receiver_code(self):
        """Test SOAP fault with Receiver fault code."""
        fault_xml = generate_soap_fault(
            faultcode="soap:Receiver",
            faultstring="Server error"
        )

        assert "soap:Receiver" in fault_xml
        assert "Server error" in fault_xml
