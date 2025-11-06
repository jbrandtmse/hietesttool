"""Integration tests for ITI-41 (Provide and Register Document Set-b) workflow."""

import pytest
import requests
from pathlib import Path
from lxml import etree
from src.ihe_test_util.ihe_transactions.iti41 import (
    ITI41Request,
    build_iti41_request,
)
from src.ihe_test_util.ihe_transactions.mtom import MTOMAttachment


@pytest.fixture
def mock_endpoint_url():
    """Mock ITI-41 endpoint URL."""
    return "http://localhost:8080/DocumentRepository_Service"


@pytest.fixture
def sample_ccd_path():
    """Path to sample CCD document."""
    return Path("mocks/data/documents/sample-ccd.xml")


@pytest.fixture
def iti41_request():
    """Sample ITI-41 request configuration."""
    return ITI41Request(
        patient_id="PAT123456",
        patient_id_root="2.16.840.1.113883.3.72.5.9.1",
    )


def test_build_iti41_request(iti41_request, sample_ccd_path):
    """Test ITI-41 request construction.
    
    Acceptance Criteria: AC 2 - Construct basic ITI-41 SOAP envelope with MTOM attachment
    """
    # Arrange - fixtures provide configuration
    
    # Act
    request_xml, attachment = build_iti41_request(iti41_request, sample_ccd_path)
    
    # Assert
    assert request_xml is not None
    assert isinstance(request_xml, str)
    assert "ProvideAndRegisterDocumentSetRequest" in request_xml
    assert "SubmitObjectsRequest" in request_xml
    assert "ExtrinsicObject" in request_xml
    
    # Verify attachment
    assert attachment is not None
    assert isinstance(attachment, MTOMAttachment)
    assert len(attachment.content) > 10000  # AC 3: >10KB


def test_iti41_request_structure(iti41_request, sample_ccd_path):
    """Test ITI-41 request has correct XDSb structure.
    
    Acceptance Criteria: AC 4 - Verify SOAP envelope structure matches IHE ITI-41 specification
    """
    # Arrange & Act
    request_xml, attachment = build_iti41_request(iti41_request, sample_ccd_path)
    root = etree.fromstring(request_xml.encode("utf-8"))
    
    # Assert - Check namespaces
    xds_ns = "urn:ihe:iti:xds-b:2007"
    rim_ns = "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
    lcm_ns = "urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0"
    
    assert root.nsmap["xds"] == xds_ns
    assert root.nsmap["rim"] == rim_ns
    assert root.nsmap["lcm"] == lcm_ns
    
    # Assert - Check required elements
    submit_request = root.find(f".//{{{lcm_ns}}}SubmitObjectsRequest")
    assert submit_request is not None
    
    registry_list = root.find(f".//{{{rim_ns}}}RegistryObjectList")
    assert registry_list is not None
    
    # Check ExtrinsicObject (Document Entry)
    extrinsic = root.find(f".//{{{rim_ns}}}ExtrinsicObject")
    assert extrinsic is not None
    assert extrinsic.get("id") == "Document01"
    assert extrinsic.get("mimeType") == "text/xml"
    
    # Check RegistryPackage (Submission Set)
    registry_package = root.find(f".//{{{rim_ns}}}RegistryPackage")
    assert registry_package is not None
    
    # Check Association
    association = root.find(f".//{{{rim_ns}}}Association")
    assert association is not None


def test_iti41_content_id_reference(iti41_request, sample_ccd_path):
    """Test Content-ID reference in ITI-41 request.
    
    Acceptance Criteria: AC 5 - Confirm Content-ID references work correctly between metadata and attachment
    """
    # Arrange
    content_id = "test-document@example.com"
    
    # Act
    request_xml, attachment = build_iti41_request(
        iti41_request,
        sample_ccd_path,
        content_id=content_id
    )
    
    # Assert
    assert attachment.content_id == content_id
    assert attachment.get_cid_reference() == f"cid:{content_id}"
    
    # Verify document element exists in request
    root = etree.fromstring(request_xml.encode("utf-8"))
    xds_ns = "urn:ihe:iti:xds-b:2007"
    document_elem = root.find(f".//{{{xds_ns}}}Document")
    assert document_elem is not None
    assert document_elem.get("id") == "Document01"


def test_iti41_document_size(iti41_request, sample_ccd_path):
    """Test MTOM attachment with CCD document >10KB.
    
    Acceptance Criteria: AC 3 - Test MTOM attachment with sample CCD document (>10KB)
    """
    # Arrange & Act
    request_xml, attachment = build_iti41_request(iti41_request, sample_ccd_path)
    
    # Assert
    document_size = len(attachment.content)
    assert document_size > 10240, f"Document size {document_size} bytes is not >10KB"
    
    # Verify document is valid XML
    doc_root = etree.fromstring(attachment.content)
    assert doc_root is not None


def test_iti41_metadata_requirements(iti41_request, sample_ccd_path):
    """Test ITI-41 includes required metadata.
    
    Acceptance Criteria: AC 4, 5 - Include required metadata (patient ID, document unique ID, 
    submission set ID, classCode, typeCode, formatCode)
    """
    # Arrange & Act
    request_xml, attachment = build_iti41_request(iti41_request, sample_ccd_path)
    root = etree.fromstring(request_xml.encode("utf-8"))
    
    rim_ns = "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
    
    # Assert - Check External Identifiers
    external_ids = root.findall(f".//{{{rim_ns}}}ExternalIdentifier")
    assert len(external_ids) >= 4  # patientId, uniqueId for both doc and submission set
    
    # Check patientId external identifier
    patient_id_found = False
    for ext_id in external_ids:
        # Check the Name element which contains "XDSDocumentEntry.patientId" or "XDSSubmissionSet.patientId"
        name_elem = ext_id.find(f".//{{{rim_ns}}}Name/{{{rim_ns}}}LocalizedString")
        if name_elem is not None:
            name_value = name_elem.get("value", "")
            if "patientId" in name_value:
                patient_id_found = True
                value = ext_id.get("value")
                assert "PAT123456" in value
                break
    assert patient_id_found, "No patientId external identifier found in metadata"
    
    # Assert - Check Classifications (classCode, typeCode, formatCode)
    classifications = root.findall(f".//{{{rim_ns}}}Classification")
    assert len(classifications) >= 3
    
    # Verify specific classification schemes
    schemes = [c.get("classificationScheme") for c in classifications]
    assert "urn:uuid:41a5887f-8865-4c09-adf7-e362475b143a" in schemes  # classCode
    assert "urn:uuid:f0306f51-975f-434e-a61c-c59651d33983" in schemes  # typeCode
    assert "urn:uuid:a09d5840-386c-46f2-b5ad-9c3699a4309d" in schemes  # formatCode


@pytest.mark.integration
def test_iti41_against_mock_endpoint(iti41_request, sample_ccd_path, mock_endpoint_url):
    """Test ITI-41 submission against mock endpoint.
    
    Acceptance Criteria: AC 6, 7 - Test against mock ITI-41 endpoint and verify successful 
    submission, validate zeep can parse MTOM response from mock endpoint
    
    Note: This test requires the mock server to be running on localhost:8080
    Run: python -m src.ihe_test_util.mock_server.app
    """
    # Arrange
    request_xml, attachment = build_iti41_request(iti41_request, sample_ccd_path)
    
    # Act
    try:
        # For this spike, we're testing with raw requests instead of zeep
        # to validate the mock endpoint independently
        response = requests.post(
            mock_endpoint_url,
            data=request_xml.encode("utf-8"),
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            timeout=60,  # ITI-41 timeout
        )
        
        # Assert
        assert response.status_code == 200
        
        # Parse response
        response_root = etree.fromstring(response.content)
        assert response_root is not None
        
        # Check for RegistryResponse
        rs_ns = "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"
        assert response_root.tag == f"{{{rs_ns}}}RegistryResponse"
        
        # Verify success status
        status = response_root.get("status")
        assert "Success" in status
        
    except requests.exceptions.ConnectionError:
        pytest.skip("Mock server not running on localhost:8080")


def test_iti41_missing_document():
    """Test ITI-41 request fails gracefully with missing document."""
    # Arrange
    request = ITI41Request(
        patient_id="PAT123",
        patient_id_root="2.16.840.1.113883.3.72.5.9.1"
    )
    missing_path = Path("nonexistent/document.xml")
    
    # Act & Assert
    with pytest.raises(FileNotFoundError):
        build_iti41_request(request, missing_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
