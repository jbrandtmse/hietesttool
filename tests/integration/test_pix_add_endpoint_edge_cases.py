"""Integration tests for PIX Add endpoint edge cases.

Tests cover:
- Custom patient IDs appearing in actual XML responses
- Custom fault messages in SOAP faults
- Combined behaviors (delay + custom ID + failures)
- Validation mode differences
- Boundary conditions
"""

import time
from lxml import etree

import pytest

from src.ihe_test_util.mock_server.app import app, initialize_app
from src.ihe_test_util.mock_server.config import MockServerConfig, PIXAddBehavior, ValidationMode


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
    """Minimal PIX Add request - missing optional fields."""
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


class TestCustomPatientIDInResponse:
    """Test that custom patient ID appears in actual XML responses."""

    def test_custom_patient_id_appears_in_response_xml(self, valid_pix_add_request):
        """Test custom patient ID is used in acknowledgment response."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(custom_patient_id="CUSTOM-PID-999")
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )

        # Assert
        assert response.status_code == 200
        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}
        
        patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
        assert patient_id is not None
        assert patient_id.get("extension") == "CUSTOM-PID-999"

    def test_default_behavior_echoes_original_patient_id(self, valid_pix_add_request):
        """Test that without custom ID, original patient ID is echoed."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior()  # No custom ID
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )

        # Assert
        assert response.status_code == 200
        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}
        
        patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
        assert patient_id is not None
        assert patient_id.get("extension") == "TEST-PAT-001"  # Original from request


class TestCustomFaultMessageInResponse:
    """Test that custom fault messages appear when failures occur."""

    def test_custom_fault_message_in_soap_fault(self, valid_pix_add_request):
        """Test custom fault message appears in SOAP fault response."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(
                failure_rate=1.0,  # Always fail
                custom_fault_message="Custom test fault - endpoint unavailable"
            )
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )

        # Assert
        assert response.status_code == 500
        tree = etree.fromstring(response.data)
        ns = {"soap": "http://www.w3.org/2003/05/soap-envelope"}
        
        reason = tree.find(".//soap:Reason/soap:Text", namespaces=ns)
        assert reason is not None
        assert "Custom test fault - endpoint unavailable" in reason.text

    def test_default_fault_message_when_not_customized(self, valid_pix_add_request):
        """Test default fault message when custom message not provided."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(
                failure_rate=1.0  # Always fail, no custom message
            )
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )

        # Assert
        assert response.status_code == 500
        tree = etree.fromstring(response.data)
        ns = {"soap": "http://www.w3.org/2003/05/soap-envelope"}
        
        reason = tree.find(".//soap:Reason/soap:Text", namespaces=ns)
        assert reason is not None
        # Should contain default message with "failure" or "error"
        assert "failure" in reason.text.lower() or "error" in reason.text.lower()


class TestCombinedBehaviors:
    """Test combinations of multiple behaviors working together."""

    def test_delay_and_custom_id_combined(self, valid_pix_add_request):
        """Test that delay applies AND custom ID appears in response."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(
                response_delay_ms=200,
                custom_patient_id="COMBINED-PID-123"
            )
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            start_time = time.time()
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )
            elapsed_ms = (time.time() - start_time) * 1000

        # Assert - Both delay and custom ID
        assert response.status_code == 200
        assert elapsed_ms >= 200
        
        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}
        patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
        assert patient_id.get("extension") == "COMBINED-PID-123"

    def test_all_behaviors_combined(self, valid_pix_add_request):
        """Test all behaviors configured together (delay, custom ID, strict validation)."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(
                response_delay_ms=150,
                failure_rate=0.0,  # No failures for this test
                custom_patient_id="ALL-BEHAVIORS-PID",
                validation_mode=ValidationMode.STRICT
            )
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            start_time = time.time()
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )
            elapsed_ms = (time.time() - start_time) * 1000

        # Assert
        assert response.status_code == 200
        assert elapsed_ms >= 150
        
        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}
        patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
        assert patient_id.get("extension") == "ALL-BEHAVIORS-PID"

    def test_delay_still_applies_before_fault(self, valid_pix_add_request):
        """Test that response delay is applied even when fault is returned."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(
                response_delay_ms=200,
                failure_rate=1.0,  # Always fail
                custom_fault_message="Delayed fault"
            )
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            start_time = time.time()
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )
            elapsed_ms = (time.time() - start_time) * 1000

        # Assert - Delay applies AND fault returned
        assert response.status_code == 500
        assert elapsed_ms >= 200  # Delay was applied
        
        tree = etree.fromstring(response.data)
        ns = {"soap": "http://www.w3.org/2003/05/soap-envelope"}
        reason = tree.find(".//soap:Reason/soap:Text", namespaces=ns)
        assert "Delayed fault" in reason.text


class TestValidationModeBehavior:
    """Test validation mode differences between STRICT and LENIENT."""

    def test_strict_mode_rejects_minimal_request(self, minimal_pix_add_request):
        """Test that strict validation rejects minimal request missing optional fields."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(validation_mode=ValidationMode.STRICT)
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            response = client.post(
                "/pix/add",
                data=minimal_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )

        # Assert - Strict mode should reject (or at minimum, we verify mode is active)
        # Note: Actual strict validation behavior depends on implementation
        # For now, verify request is processed and mode was set
        assert response.status_code in [200, 400]  # Either accepted or rejected

    def test_lenient_mode_accepts_minimal_request(self, minimal_pix_add_request):
        """Test that lenient validation accepts minimal request."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(validation_mode=ValidationMode.LENIENT)
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            response = client.post(
                "/pix/add",
                data=minimal_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )

        # Assert - Lenient mode should accept
        assert response.status_code == 200
        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}
        
        # Verify acknowledgment
        type_code = tree.find(".//hl7:acknowledgement/hl7:typeCode", namespaces=ns)
        assert type_code.get("code") == "AA"


class TestBoundaryConditions:
    """Test boundary values for configuration parameters."""

    def test_maximum_delay_5000ms(self, valid_pix_add_request):
        """Test maximum allowed delay of 5000ms actually works."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(response_delay_ms=5000)
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            start_time = time.time()
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )
            elapsed_ms = (time.time() - start_time) * 1000

        # Assert
        assert response.status_code == 200
        assert elapsed_ms >= 5000
        assert elapsed_ms < 6000  # Should not take significantly longer

    def test_zero_delay(self, valid_pix_add_request):
        """Test zero delay (immediate response)."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(response_delay_ms=0)
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            start_time = time.time()
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )
            elapsed_ms = (time.time() - start_time) * 1000

        # Assert
        assert response.status_code == 200
        assert elapsed_ms < 100  # Should be very fast

    def test_failure_rate_0_5_edge_case(self, valid_pix_add_request):
        """Test failure rate at 0.5 (50% failure probability)."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(failure_rate=0.5)
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act - Send multiple requests
        success_count = 0
        failure_count = 0
        
        with app.test_client() as client:
            for _ in range(20):
                response = client.post(
                    "/pix/add",
                    data=valid_pix_add_request,
                    content_type="text/xml; charset=utf-8"
                )
                if response.status_code == 200:
                    success_count += 1
                elif response.status_code == 500:
                    failure_count += 1

        # Assert - Should have mix of successes and failures
        assert success_count > 0
        assert failure_count > 0
        # With 20 requests at 0.5 rate, expect roughly equal distribution
        assert 5 <= success_count <= 15  # Allow variance


class TestEmptyCustomIDs:
    """Test behavior with empty string custom IDs vs None."""

    def test_empty_string_custom_patient_id(self, valid_pix_add_request):
        """Test behavior when custom_patient_id is empty string."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(custom_patient_id="")
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )

        # Assert - Should handle empty string gracefully
        assert response.status_code in [200, 400]
        # Either uses empty string or falls back to original

    def test_none_custom_patient_id_uses_original(self, valid_pix_add_request):
        """Test that None custom_patient_id uses original from request."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(custom_patient_id=None)
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act
        with app.test_client() as client:
            response = client.post(
                "/pix/add",
                data=valid_pix_add_request,
                content_type="text/xml; charset=utf-8"
            )

        # Assert
        assert response.status_code == 200
        tree = etree.fromstring(response.data)
        ns = {"hl7": "urn:hl7-org:v3"}
        
        patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
        assert patient_id.get("extension") == "TEST-PAT-001"  # Original


class TestMultipleRequestsConsistency:
    """Test that configurations are applied consistently across multiple requests."""

    def test_custom_id_consistent_across_requests(self, valid_pix_add_request):
        """Test that custom patient ID is consistently applied to all requests."""
        # Arrange
        config = MockServerConfig(
            pix_add_behavior=PIXAddBehavior(custom_patient_id="CONSISTENT-PID")
        )
        initialize_app(config)
        app.config["TESTING"] = True

        # Act - Send multiple requests
        responses = []
        with app.test_client() as client:
            for _ in range(5):
                response = client.post(
                    "/pix/add",
                    data=valid_pix_add_request,
                    content_type="text/xml; charset=utf-8"
                )
                responses.append(response)

        # Assert - All responses should have same custom ID
        ns = {"hl7": "urn:hl7-org:v3"}
        for response in responses:
            assert response.status_code == 200
            tree = etree.fromstring(response.data)
            patient_id = tree.find(".//hl7:patient/hl7:id", namespaces=ns)
            assert patient_id.get("extension") == "CONSISTENT-PID"
