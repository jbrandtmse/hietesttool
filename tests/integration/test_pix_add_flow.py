"""Integration tests for PIX Add (ITI-44) workflow."""

import pytest
import requests
from pathlib import Path
from lxml import etree
from src.ihe_test_util.ihe_transactions.pix_add import (
    PatientDemographics,
    build_pix_add_message,
)


@pytest.fixture
def mock_endpoint_url():
    """Mock PIX Add endpoint URL."""
    return "http://localhost:8080/pix/add"


@pytest.fixture
def sample_patient():
    """Sample patient demographics."""
    return PatientDemographics(
        patient_id="PAT123456",
        patient_id_root="2.16.840.1.113883.3.72.5.9.1",
        given_name="John",
        family_name="Doe",
        gender="M",
        birth_date="19800101",
        street_address="123 Main Street",
        city="Portland",
        state="OR",
        postal_code="97201",
        country="US",
    )


def test_build_pix_add_message(sample_patient):
    """Test PIX Add message construction.
    
    Acceptance Criteria: AC 1 - Create minimal PIX Add SOAP message using zeep library
    """
    # Arrange - patient demographics provided by fixture
    
    # Act
    message_xml = build_pix_add_message(sample_patient)
    
    # Assert
    assert message_xml is not None
    assert isinstance(message_xml, str)
    assert "PRPA_IN201301UV02" in message_xml
    assert "John" in message_xml
    assert "Doe" in message_xml
    assert "PAT123456" in message_xml
    
    # Verify XML is well-formed
    root = etree.fromstring(message_xml.encode("utf-8"))
    assert root is not None


def test_pix_add_message_structure(sample_patient):
    """Test PIX Add message has correct HL7v3 structure.
    
    Acceptance Criteria: AC 1 - Verify correct HL7v3 namespaces and structure
    """
    # Arrange & Act
    message_xml = build_pix_add_message(sample_patient)
    root = etree.fromstring(message_xml.encode("utf-8"))
    
    # Assert - Check namespaces
    hl7_ns = "urn:hl7-org:v3"
    assert root.nsmap[None] == hl7_ns
    
    # Assert - Check required elements
    id_elem = root.find(f".//{{{hl7_ns}}}id")
    assert id_elem is not None
    
    creation_time = root.find(f".//{{{hl7_ns}}}creationTime")
    assert creation_time is not None
    
    patient_elem = root.find(f".//{{{hl7_ns}}}patient")
    assert patient_elem is not None
    
    # Check patient demographics
    given_name = root.find(f".//{{{hl7_ns}}}given")
    assert given_name is not None
    assert given_name.text == "John"
    
    family_name = root.find(f".//{{{hl7_ns}}}family")
    assert family_name is not None
    assert family_name.text == "Doe"
    
    gender = root.find(f".//{{{hl7_ns}}}administrativeGenderCode")
    assert gender is not None
    assert gender.get("code") == "M"


def test_pix_add_invalid_gender():
    """Test PIX Add message validation rejects invalid gender."""
    # Arrange
    invalid_patient = PatientDemographics(
        patient_id="PAT123",
        patient_id_root="2.16.840.1.113883.3.72.5.9.1",
        given_name="Test",
        family_name="Patient",
        gender="X",  # Invalid gender
        birth_date="19800101",
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="Invalid gender"):
        build_pix_add_message(invalid_patient)


@pytest.mark.integration
def test_pix_add_against_mock_endpoint(sample_patient, mock_endpoint_url):
    """Test PIX Add submission against mock endpoint.
    
    Acceptance Criteria: AC 6 - Test against mock ITI-41 endpoint and verify successful submission
    
    Note: This test requires the mock server to be running on localhost:8080
    Run: python -m src.ihe_test_util.mock_server.app
    """
    # Arrange
    message_xml = build_pix_add_message(sample_patient)
    
    # Act
    try:
        response = requests.post(
            mock_endpoint_url,
            data=message_xml.encode("utf-8"),
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            timeout=10,
        )
        
        # Assert
        assert response.status_code == 200
        
        # Parse response
        response_root = etree.fromstring(response.content)
        assert response_root is not None
        
        # Check for acknowledgement
        hl7_ns = "urn:hl7-org:v3"
        ack_elem = response_root.find(f".//{{{hl7_ns}}}acknowledgement")
        assert ack_elem is not None
        
        type_code = ack_elem.find(f".//{{{hl7_ns}}}typeCode")
        assert type_code is not None
        assert type_code.get("code") == "AA"  # Application Accept
        
    except requests.exceptions.ConnectionError:
        pytest.skip("Mock server not running on localhost:8080")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
