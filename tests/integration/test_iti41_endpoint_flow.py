"""Integration tests for ITI-41 endpoint flow.

Tests complete request/response flow with Flask test client.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from lxml import etree

from src.ihe_test_util.mock_server.app import app, initialize_app
from src.ihe_test_util.mock_server.config import MockServerConfig


@pytest.fixture
def client():
    """Create Flask test client with initialized app."""
    config = MockServerConfig(
        log_level="DEBUG",
        log_path="mocks/logs/test-mock-server.log",
        save_submitted_documents=False
    )
    
    with app.test_client() as client:
        with app.app_context():
            initialize_app(config)
            yield client


@pytest.fixture
def client_with_document_saving():
    """Create Flask test client with document saving enabled."""
    config = MockServerConfig(
        log_level="DEBUG",
        log_path="mocks/logs/test-mock-server.log",
        save_submitted_documents=True
    )
    
    with app.test_client() as client:
        with app.app_context():
            initialize_app(config)
            yield client


@pytest.fixture
def valid_mtom_request():
    """Generate valid MTOM ITI-41 request."""
    boundary = "MIME_boundary_test_123"
    
    soap_envelope = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
            <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
                <rim:RegistryPackage id="SubmissionSet01">
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8" 
                                             value="SubmissionSet_TEST_001"/>
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:554ac39e-e3fe-47fe-b233-965d2a147832" 
                                             value="1.2.3.4.5"/>
                </rim:RegistryPackage>
                <rim:ExtrinsicObject id="Document01" mimeType="text/xml">
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab" 
                                             value="Document_TEST_001"/>
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:58a6f841-87b3-4a3e-92fd-a8ffeff98427" 
                                             value="PAT123^^^&amp;1.2.3.4&amp;ISO"/>
                    <rim:Classification classificationScheme="urn:uuid:41a5887f-8865-4c09-adf7-e362475b143a" 
                                         nodeRepresentation="34133-9"/>
                    <rim:Classification classificationScheme="urn:uuid:f0306f51-975f-434e-a61c-c59651d33983" 
                                         nodeRepresentation="34133-9"/>
                    <xop:Include xmlns:xop="http://www.w3.org/2004/08/xop/include" 
                                 href="cid:document@example.org"/>
                </rim:ExtrinsicObject>
            </rim:RegistryObjectList>
        </lcm:SubmitObjectsRequest>
    </soap:Body>
</soap:Envelope>"""
    
    ccd_document = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id extension="TEST_CCD_001" root="1.2.3.4.5"/>
    <code code="34133-9" codeSystem="2.16.840.1.113883.6.1" displayName="Summary of Episode Note"/>
    <title>Continuity of Care Document</title>
    <recordTarget>
        <patientRole>
            <id extension="PAT123" root="1.2.3.4"/>
            <patient>
                <name>
                    <given>John</given>
                    <family>Doe</family>
                </name>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>"""
    
    mtom_request = (
        f"--{boundary}\r\n"
        f"Content-Type: application/xop+xml; charset=UTF-8\r\n"
        f"Content-Transfer-Encoding: 8bit\r\n"
        f"Content-ID: <soap-envelope@example.org>\r\n"
        f"\r\n"
        f"{soap_envelope}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: text/xml\r\n"
        f"Content-Transfer-Encoding: binary\r\n"
        f"Content-ID: <document@example.org>\r\n"
        f"\r\n"
        f"{ccd_document}\r\n"
        f"--{boundary}--"
    ).encode("utf-8")
    
    content_type = (
        f'multipart/related; boundary="{boundary}"; '
        f'type="application/xop+xml"; '
        f'start="<soap-envelope@example.org>"'
    )
    
    return mtom_request, content_type


class TestITI41EndpointFlow:
    """Test complete ITI-41 request/response flow."""

    def test_valid_iti41_submission_returns_success(self, client, valid_mtom_request, tmp_path):
        """Test valid ITI-41 submission returns RegistryResponse with Success status."""
        # Arrange
        mtom_request, content_type = valid_mtom_request
        
        # Mock the log directory to use tmp_path
        with patch("src.ihe_test_util.mock_server.iti41_endpoint.Path") as mock_path:
            mock_log_dir = tmp_path / "logs" / "iti41-submissions"
            mock_log_dir.mkdir(parents=True, exist_ok=True)
            mock_path.return_value = mock_log_dir
            
            # Act
            response = client.post(
                "/iti41/submit",
                data=mtom_request,
                content_type=content_type
            )
        
        # Assert
        assert response.status_code == 200
        assert "application/soap+xml" in response.content_type
        
        # Parse response
        response_xml = response.data.decode("utf-8")
        assert "RegistryResponse" in response_xml
        assert "ResponseStatusType:Success" in response_xml
        
        # Validate response structure
        tree = etree.fromstring(response.data)
        namespaces = {
            "soap": "http://www.w3.org/2003/05/soap-envelope",
            "rs": "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0",
            "rim": "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
        }
        
        registry_response = tree.xpath("//rs:RegistryResponse", namespaces=namespaces)
        assert len(registry_response) == 1
        
        status = registry_response[0].get("status")
        assert status == "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"

    def test_iti41_response_includes_submission_set_and_document_ids(self, client, valid_mtom_request, tmp_path):
        """Test RegistryResponse includes correct submission set and document unique IDs."""
        # Arrange
        mtom_request, content_type = valid_mtom_request
        
        with patch("src.ihe_test_util.mock_server.iti41_endpoint.Path") as mock_path:
            mock_log_dir = tmp_path / "logs" / "iti41-submissions"
            mock_log_dir.mkdir(parents=True, exist_ok=True)
            mock_path.return_value = mock_log_dir
            
            # Act
            response = client.post(
                "/iti41/submit",
                data=mtom_request,
                content_type=content_type
            )
        
        # Assert
        assert response.status_code == 200
        
        response_xml = response.data.decode("utf-8")
        assert "SubmissionSet_TEST_001" in response_xml
        assert "Document_TEST_001" in response_xml
        
        # Validate slots
        tree = etree.fromstring(response.data)
        namespaces = {"rim": "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"}
        
        submission_slot = tree.xpath(
            '//rim:Slot[@name="SubmissionSetUniqueId"]/rim:ValueList/rim:Value',
            namespaces=namespaces
        )
        assert len(submission_slot) == 1
        assert submission_slot[0].text == "SubmissionSet_TEST_001"
        
        document_slot = tree.xpath(
            '//rim:Slot[@name="DocumentUniqueId"]/rim:ValueList/rim:Value',
            namespaces=namespaces
        )
        assert len(document_slot) == 1
        assert document_slot[0].text == "Document_TEST_001"

    def test_invalid_content_type_returns_soap_fault(self, client):
        """Test request with invalid Content-Type returns SOAP fault."""
        # Arrange
        request_data = b"<soap:Envelope/>"
        content_type = "text/xml"  # Should be multipart/related
        
        # Act
        response = client.post(
            "/iti41/submit",
            data=request_data,
            content_type=content_type
        )
        
        # Assert
        assert response.status_code == 400
        
        response_xml = response.data.decode("utf-8")
        assert "soap:Fault" in response_xml
        assert "Invalid Content-Type" in response_xml
        assert "soap:Sender" in response_xml

    def test_malformed_mtom_returns_soap_fault(self, client):
        """Test malformed MTOM message returns SOAP fault."""
        # Arrange
        malformed_request = b"This is not a valid MTOM message"
        content_type = 'multipart/related; boundary="test"'
        
        # Act
        response = client.post(
            "/iti41/submit",
            data=malformed_request,
            content_type=content_type
        )
        
        # Assert
        assert response.status_code == 400
        
        response_xml = response.data.decode("utf-8")
        assert "soap:Fault" in response_xml
        assert "MTOM Parsing Error" in response_xml

    def test_missing_document_attachment_returns_soap_fault(self, client):
        """Test MTOM message missing document attachment returns SOAP fault."""
        # Arrange
        boundary = "MIME_boundary_test"
        soap_only = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
            <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
                <rim:RegistryPackage id="SubmissionSet01"/>
            </rim:RegistryObjectList>
        </lcm:SubmitObjectsRequest>
    </soap:Body>
</soap:Envelope>"""
        
        mtom_request = (
            f"--{boundary}\r\n"
            f"Content-Type: application/xop+xml\r\n"
            f"Content-ID: <soap@example.org>\r\n"
            f"\r\n"
            f"{soap_only}\r\n"
            f"--{boundary}--"
        ).encode("utf-8")
        
        content_type = f'multipart/related; boundary="{boundary}"'
        
        # Act
        response = client.post(
            "/iti41/submit",
            data=mtom_request,
            content_type=content_type
        )
        
        # Assert
        assert response.status_code == 400
        
        response_xml = response.data.decode("utf-8")
        assert "soap:Fault" in response_xml
        assert "Missing CCD document attachment" in response_xml

    def test_invalid_xdsb_metadata_returns_soap_fault(self, client):
        """Test SOAP message with invalid XDSb metadata returns SOAP fault."""
        # Arrange
        boundary = "MIME_boundary_test"
        
        invalid_soap = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <InvalidRequest>Not a valid XDSb request</InvalidRequest>
    </soap:Body>
</soap:Envelope>"""
        
        doc_content = """<?xml version="1.0"?><ClinicalDocument/>"""
        
        mtom_request = (
            f"--{boundary}\r\n"
            f"Content-Type: application/xop+xml\r\n"
            f"Content-ID: <soap@example.org>\r\n"
            f"\r\n"
            f"{invalid_soap}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: text/xml\r\n"
            f"Content-ID: <doc@example.org>\r\n"
            f"\r\n"
            f"{doc_content}\r\n"
            f"--{boundary}--"
        ).encode("utf-8")
        
        content_type = f'multipart/related; boundary="{boundary}"'
        
        # Act
        response = client.post(
            "/iti41/submit",
            data=mtom_request,
            content_type=content_type
        )
        
        # Assert
        assert response.status_code == 400
        
        response_xml = response.data.decode("utf-8")
        assert "soap:Fault" in response_xml
        assert "Invalid XDSb Metadata" in response_xml

    def test_iti41_submission_creates_log_file(self, client, valid_mtom_request, tmp_path):
        """Test ITI-41 submission creates transaction log file."""
        # Arrange
        mtom_request, content_type = valid_mtom_request
        mock_log_dir = tmp_path / "logs" / "iti41-submissions"
        mock_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Act
        with patch("src.ihe_test_util.mock_server.iti41_endpoint.Path") as mock_path:
            def path_side_effect(path_str):
                if "iti41-submissions" in str(path_str):
                    return mock_log_dir
                return Path(path_str)
            
            mock_path.side_effect = path_side_effect
            
            response = client.post(
                "/iti41/submit",
                data=mtom_request,
                content_type=content_type
            )
        
        # Assert
        assert response.status_code == 200
        
        # Check log files were created
        log_files = list(mock_log_dir.glob("*.log"))
        assert len(log_files) > 0
        
        # Verify log file content
        log_content = log_files[0].read_text()
        assert "ITI-41 Transaction Log" in log_content
        assert "SubmissionSet_TEST_001" in log_content
        assert "Document_TEST_001" in log_content
        assert "PAT123" in log_content

    def test_document_saving_when_enabled(self, client_with_document_saving, valid_mtom_request, tmp_path):
        """Test documents are saved to disk when save_submitted_documents is enabled."""
        # Arrange
        mtom_request, content_type = valid_mtom_request
        mock_log_dir = tmp_path / "logs" / "iti41-submissions"
        mock_doc_dir = tmp_path / "data" / "documents"
        mock_log_dir.mkdir(parents=True, exist_ok=True)
        mock_doc_dir.mkdir(parents=True, exist_ok=True)
        
        # Act
        with patch("src.ihe_test_util.mock_server.iti41_endpoint.Path") as mock_path:
            def path_side_effect(path_str):
                if "iti41-submissions" in str(path_str):
                    return mock_log_dir
                elif "documents" in str(path_str):
                    return mock_doc_dir
                return Path(path_str)
            
            mock_path.side_effect = path_side_effect
            
            response = client_with_document_saving.post(
                "/iti41/submit",
                data=mtom_request,
                content_type=content_type
            )
        
        # Assert
        assert response.status_code == 200
        
        # Check document was saved
        doc_files = list(mock_doc_dir.glob("*.xml"))
        assert len(doc_files) > 0
        
        # Verify document content
        doc_content = doc_files[0].read_text()
        assert "ClinicalDocument" in doc_content
        assert "TEST_CCD_001" in doc_content

    def test_content_id_matching(self, client, tmp_path):
        """Test Content-ID matching between metadata and attachment."""
        # Arrange
        boundary = "MIME_boundary_test"
        content_id = "special-document@example.org"
        
        soap_envelope = f"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
            <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
                <rim:RegistryPackage id="SubmissionSet01">
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8" value="SS_001"/>
                </rim:RegistryPackage>
                <rim:ExtrinsicObject id="Document01">
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab" value="DOC_001"/>
                    <xop:Include xmlns:xop="http://www.w3.org/2004/08/xop/include" href="cid:{content_id}"/>
                </rim:ExtrinsicObject>
            </rim:RegistryObjectList>
        </lcm:SubmitObjectsRequest>
    </soap:Body>
</soap:Envelope>"""
        
        ccd_document = """<?xml version="1.0"?><ClinicalDocument xmlns="urn:hl7-org:v3"/>"""
        
        mtom_request = (
            f"--{boundary}\r\n"
            f"Content-Type: application/xop+xml\r\n"
            f"Content-ID: <soap@example.org>\r\n"
            f"\r\n"
            f"{soap_envelope}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: text/xml\r\n"
            f"Content-ID: <{content_id}>\r\n"
            f"\r\n"
            f"{ccd_document}\r\n"
            f"--{boundary}--"
        ).encode("utf-8")
        
        content_type = f'multipart/related; boundary="{boundary}"'
        
        mock_log_dir = tmp_path / "logs" / "iti41-submissions"
        mock_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Act
        with patch("src.ihe_test_util.mock_server.iti41_endpoint.Path") as mock_path:
            mock_path.return_value = mock_log_dir
            
            response = client.post(
                "/iti41/submit",
                data=mtom_request,
                content_type=content_type
            )
        
        # Assert
        assert response.status_code == 200
        
        # Verify Content-ID was extracted and logged
        log_files = list(mock_log_dir.glob("*.log"))
        assert len(log_files) > 0
        log_content = log_files[0].read_text()
        assert f"cid:{content_id}" in log_content

    def test_health_check_includes_iti41_endpoint(self, client):
        """Test health check endpoint includes /iti41/submit in endpoints list."""
        # Act
        response = client.get("/health")
        
        # Assert
        assert response.status_code == 200
        
        health_data = json.loads(response.data)
        assert "endpoints" in health_data
        assert "/iti41/submit" in health_data["endpoints"]
        assert health_data["status"] == "healthy"
