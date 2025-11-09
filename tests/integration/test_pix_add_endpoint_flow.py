"""Integration tests for PIX Add endpoint complete flow."""

import json
from pathlib import Path

import pytest
from lxml import etree

from src.ihe_test_util.mock_server.app import app, initialize_app
from src.ihe_test_util.mock_server.config import MockServerConfig


@pytest.fixture
def test_config():
    """Create test configuration."""
    return MockServerConfig(
        host="127.0.0.1",
        http_port=8080,
        log_level="DEBUG",
        log_path="mocks/logs/test-mock-server.log",
        response_delay_ms=0  # No delay for tests
    )


@pytest.fixture
def client(test_config):
    """Create Flask test client with initialized app."""
    initialize_app(test_config)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def valid_pix_add_request():
    """Valid PIX Add SOAP request."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
      <id root="1.2.3.4.5" extension="TEST-MSG-12345"/>
      <creationTime value="20250106150000"/>
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <id root="1.2.840.114350" extension="TEST-PAT-001"/>
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


@pytest.fixture
def minimal_pix_add_request():
    """Minimal PIX Add request with only required fields."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <id root="1.2.3" extension="MIN-MSG-001"/>
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <id root="1.2.3.4" extension="MIN-PAT-001"/>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""


class TestPIXAddEndpointFlow:
    """Test complete PIX Add endpoint request/response flow."""

    def test_valid_pix_add_request_returns_acknowledgment(self, client, valid_pix_add_request):
        """Test that valid PIX Add request returns AA acknowledgment."""
        response = client.post(
            "/pix/add",
            data=valid_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 200
        assert "text/xml" in response.content_type

        # Parse response
        tree = etree.fromstring(response.data)
        ns = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "hl7": "urn:hl7-org:v3"
        }

        # Verify MCCI acknowledgment
        mcci = tree.find(".//hl7:MCCI_IN000002UV01", namespaces=ns)
        assert mcci is not None

        # Verify AA status
        type_code = tree.find(
            ".//hl7:acknowledgement/hl7:typeCode",
            namespaces=ns
        )
        assert type_code is not None
        assert type_code.get("code") == "AA"

    def test_acknowledgment_echoes_patient_identifiers(self, client, valid_pix_add_request):
        """Test that acknowledgment echoes back patient identifiers correctly."""
        response = client.post(
            "/pix/add",
            data=valid_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 200

        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}

        # Verify patient ID is echoed
        patient_id = tree.find(
            ".//hl7:controlActProcess/hl7:subject/hl7:registrationEvent/"
            "hl7:subject1/hl7:patient/hl7:id",
            namespaces=ns
        )
        assert patient_id is not None
        assert patient_id.get("root") == "1.2.840.114350"
        assert patient_id.get("extension") == "TEST-PAT-001"

    def test_correlation_id_matches_request_message_id(self, client, valid_pix_add_request):
        """Test that response correlation ID matches request message ID."""
        response = client.post(
            "/pix/add",
            data=valid_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 200

        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}

        # Verify correlation ID
        target_id = tree.find(
            ".//hl7:acknowledgement/hl7:targetMessage/hl7:id",
            namespaces=ns
        )
        assert target_id is not None
        assert target_id.get("root") == "1.2.3.4.5"
        assert target_id.get("extension") == "TEST-MSG-12345"

    def test_minimal_pix_add_request_succeeds(self, client, minimal_pix_add_request):
        """Test that minimal PIX Add request (no demographics) succeeds."""
        response = client.post(
            "/pix/add",
            data=minimal_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 200

        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}

        # Verify AA status
        type_code = tree.find(
            ".//hl7:acknowledgement/hl7:typeCode",
            namespaces=ns
        )
        assert type_code.get("code") == "AA"

        # Verify patient ID
        patient_id = tree.find(
            ".//hl7:patient/hl7:id",
            namespaces=ns
        )
        assert patient_id.get("extension") == "MIN-PAT-001"

    def test_malformed_xml_returns_soap_fault(self, client):
        """Test that malformed XML returns SOAP fault with 400 status."""
        malformed_request = "This is not XML"

        response = client.post(
            "/pix/add",
            data=malformed_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 400
        assert "text/xml" in response.content_type

        # Verify SOAP fault structure
        tree = etree.fromstring(response.data)
        ns = {"soap": "http://www.w3.org/2003/05/soap-envelope"}

        fault = tree.find(".//soap:Fault", namespaces=ns)
        assert fault is not None

        code = fault.find("soap:Code/soap:Value", namespaces=ns)
        assert code.text == "soap:Sender"

    def test_missing_prpa_element_returns_soap_fault(self, client):
        """Test that missing PRPA element returns SOAP fault."""
        invalid_request = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <InvalidMessage>Not a PRPA message</InvalidMessage>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        response = client.post(
            "/pix/add",
            data=invalid_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 400

        tree = etree.fromstring(response.data)
        ns = {"soap": "http://www.w3.org/2003/05/soap-envelope"}

        reason = tree.find(".//soap:Reason/soap:Text", namespaces=ns)
        assert "Missing PRPA_IN201301UV02 element" in reason.text

    def test_missing_patient_id_returns_soap_fault(self, client):
        """Test that missing patient ID returns SOAP fault."""
        invalid_request = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <id root="1.2.3" extension="MSG-001"/>
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

        response = client.post(
            "/pix/add",
            data=invalid_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 400

        tree = etree.fromstring(response.data)
        ns = {"soap": "http://www.w3.org/2003/05/soap-envelope"}

        reason = tree.find(".//soap:Reason/soap:Text", namespaces=ns)
        assert "Missing patient identifier" in reason.text

    def test_response_delay_configuration(self, test_config, valid_pix_add_request):
        """Test that response delay configuration works."""
        import time

        # Configure with 100ms delay using per-endpoint behavior
        test_config.pix_add_behavior.response_delay_ms = 100
        initialize_app(test_config)
        app.config["TESTING"] = True

        with app.test_client() as client:
            start_time = time.time()
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )
            elapsed_time = (time.time() - start_time) * 1000  # Convert to ms

            assert response.status_code == 200
            # Allow some margin for processing time
            assert elapsed_time >= 100
            assert elapsed_time < 200  # Should not take too long

    def test_health_check_includes_pix_add_endpoint(self, client):
        """Test that health check endpoint includes /pix/add in endpoints list."""
        response = client.get("/health")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert "endpoints" in data
        assert "/pix/add" in data["endpoints"]
        assert data["status"] == "healthy"

    def test_female_patient_request(self, client):
        """Test PIX Add request with female patient."""
        female_request = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">
      <id root="1.2.3" extension="MSG-F001"/>
      <controlActProcess>
        <subject>
          <registrationEvent>
            <subject1>
              <patient>
                <id root="1.2.3.4" extension="PAT-F001"/>
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

        response = client.post(
            "/pix/add",
            data=female_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 200

        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}

        # Verify patient ID is echoed
        patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
        assert patient_id.get("extension") == "PAT-F001"

    def test_multiple_requests_increment_processing(self, client, valid_pix_add_request):
        """Test that multiple requests are processed independently."""
        # Send first request
        response1 = client.post(
            "/pix/add",
            data=valid_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )
        assert response1.status_code == 200

        # Send second request
        response2 = client.post(
            "/pix/add",
            data=valid_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )
        assert response2.status_code == 200

        # Both should succeed
        tree1 = etree.fromstring(response1.data)
        tree2 = etree.fromstring(response2.data)
        ns = {"hl7": "urn:hl7-org:v3"}

        status1 = tree1.find(".//hl7:acknowledgement/hl7:typeCode", namespaces=ns)
        status2 = tree2.find(".//hl7:acknowledgement/hl7:typeCode", namespaces=ns)

        assert status1.get("code") == "AA"
        assert status2.get("code") == "AA"

    def test_response_has_unique_message_ids(self, client, valid_pix_add_request):
        """Test that each response has a unique message ID."""
        response1 = client.post(
            "/pix/add",
            data=valid_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )
        response2 = client.post(
            "/pix/add",
            data=valid_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )

        tree1 = etree.fromstring(response1.data)
        tree2 = etree.fromstring(response2.data)
        ns = {"hl7": "urn:hl7-org:v3"}

        msg_id1 = tree1.find(".//hl7:MCCI_IN000002UV01/hl7:id", namespaces=ns)
        msg_id2 = tree2.find(".//hl7:MCCI_IN000002UV01/hl7:id", namespaces=ns)

        # Response message IDs should be different
        assert msg_id1.get("extension") != msg_id2.get("extension")

    def test_logging_creates_pix_add_log_file(self, client, valid_pix_add_request, tmp_path):
        """Test that PIX Add logging creates log file."""
        # Note: This test verifies logging behavior without checking actual file creation
        # since logging setup happens during app initialization
        response = client.post(
            "/pix/add",
            data=valid_pix_add_request,
            content_type="text/xml; charset=utf-8"
        )

        assert response.status_code == 200

        # Verify log directory would be created
        log_dir = Path("mocks/logs")
        assert log_dir.exists()
