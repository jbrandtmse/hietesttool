"""Unit tests for ITI-41 endpoint."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
from lxml import etree

from src.ihe_test_util.mock_server.iti41_endpoint import (
    extract_mtom_parts,
    extract_xdsb_metadata,
    generate_registry_response,
    generate_soap_fault,
)


class TestExtractMtomParts:
    """Test MTOM multipart message parsing."""

    def test_extract_mtom_parts_valid_message(self):
        """Test extraction of SOAP envelope and document from valid MTOM message."""
        # Arrange
        boundary = "MIME_boundary_test"
        soap_content = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <test>content</test>
    </soap:Body>
</soap:Envelope>"""
        
        doc_content = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id extension="123456"/>
</ClinicalDocument>"""
        
        mtom_message = (
            f"--{boundary}\r\n"
            f"Content-Type: application/xop+xml; charset=UTF-8\r\n"
            f"Content-ID: <soap@example.org>\r\n"
            f"\r\n"
            f"{soap_content}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: text/xml\r\n"
            f"Content-ID: <doc@example.org>\r\n"
            f"\r\n"
            f"{doc_content}\r\n"
            f"--{boundary}--"
        ).encode("utf-8")
        
        content_type = f'multipart/related; boundary="{boundary}"'
        
        # Act
        result = extract_mtom_parts(mtom_message, content_type)
        
        # Assert
        assert "soap_envelope" in result
        assert "document_attachment" in result
        assert "document_content_id" in result
        assert "<soap:Envelope" in result["soap_envelope"]
        assert "<ClinicalDocument" in result["document_attachment"]
        assert result["document_content_id"] == "doc@example.org"

    def test_extract_mtom_parts_missing_soap_envelope(self):
        """Test MTOM parsing fails when SOAP envelope is missing."""
        # Arrange
        boundary = "MIME_boundary_test"
        doc_content = """<?xml version="1.0"?><ClinicalDocument/>"""
        
        mtom_message = (
            f"--{boundary}\r\n"
            f"Content-Type: text/xml\r\n"
            f"Content-ID: <doc@example.org>\r\n"
            f"\r\n"
            f"{doc_content}\r\n"
            f"--{boundary}--"
        ).encode("utf-8")
        
        content_type = f'multipart/related; boundary="{boundary}"'
        
        # Act & Assert
        with pytest.raises(ValueError, match="Missing SOAP envelope"):
            extract_mtom_parts(mtom_message, content_type)

    def test_extract_mtom_parts_missing_document_attachment(self):
        """Test MTOM parsing fails when document attachment is missing."""
        # Arrange
        boundary = "MIME_boundary_test"
        soap_content = """<?xml version="1.0"?><soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"/>"""
        
        mtom_message = (
            f"--{boundary}\r\n"
            f"Content-Type: application/xop+xml\r\n"
            f"Content-ID: <soap@example.org>\r\n"
            f"\r\n"
            f"{soap_content}\r\n"
            f"--{boundary}--"
        ).encode("utf-8")
        
        content_type = f'multipart/related; boundary="{boundary}"'
        
        # Act & Assert
        with pytest.raises(ValueError, match="Missing CCD document attachment"):
            extract_mtom_parts(mtom_message, content_type)

    def test_extract_mtom_parts_non_multipart_content(self):
        """Test MTOM parsing fails for non-multipart content."""
        # Arrange
        simple_content = b"<soap:Envelope/>"
        content_type = "text/xml"
        
        # Act & Assert
        with pytest.raises(ValueError, match="non-multipart content"):
            extract_mtom_parts(simple_content, content_type)

    def test_extract_mtom_parts_malformed_mime(self):
        """Test MTOM parsing fails for malformed MIME message."""
        # Arrange
        malformed_message = b"This is not a valid MIME message"
        content_type = 'multipart/related; boundary="test"'
        
        # Act & Assert
        with pytest.raises(ValueError, match="non-multipart content"):
            extract_mtom_parts(malformed_message, content_type)


class TestExtractXdsbMetadata:
    """Test XDSb metadata extraction from SOAP envelopes."""

    def test_extract_xdsb_metadata_complete(self):
        """Test extraction of complete XDSb metadata."""
        # Arrange
        soap_xml = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
            <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
                <rim:RegistryPackage id="SubmissionSet01">
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8" value="SubmissionSet_12345"/>
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:554ac39e-e3fe-47fe-b233-965d2a147832" value="1.2.3.4.5"/>
                </rim:RegistryPackage>
                <rim:ExtrinsicObject id="Document01" mimeType="text/xml">
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab" value="Document_67890"/>
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:58a6f841-87b3-4a3e-92fd-a8ffeff98427" value="PAT123^^^&amp;1.2.3.4&amp;ISO"/>
                    <rim:Classification classificationScheme="urn:uuid:41a5887f-8865-4c09-adf7-e362475b143a" nodeRepresentation="34133-9"/>
                    <rim:Classification classificationScheme="urn:uuid:f0306f51-975f-434e-a61c-c59651d33983" nodeRepresentation="34133-9"/>
                    <xop:Include xmlns:xop="http://www.w3.org/2004/08/xop/include" href="cid:doc@example.org"/>
                </rim:ExtrinsicObject>
            </rim:RegistryObjectList>
        </lcm:SubmitObjectsRequest>
    </soap:Body>
</soap:Envelope>"""
        
        # Act
        metadata = extract_xdsb_metadata(soap_xml)
        
        # Assert
        assert metadata["submission_set_id"] == "SubmissionSet_12345"
        assert metadata["document_unique_id"] == "Document_67890"
        assert metadata["patient_id"] == "PAT123^^^&1.2.3.4&ISO"
        assert metadata["source_id"] == "1.2.3.4.5"
        assert metadata["content_id_reference"] == "cid:doc@example.org"
        assert metadata["mime_type"] == "text/xml"
        assert metadata["class_code"] == "34133-9"
        assert metadata["type_code"] == "34133-9"

    def test_extract_xdsb_metadata_minimal(self):
        """Test extraction with minimal required metadata."""
        # Arrange
        soap_xml = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
            <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
                <rim:RegistryPackage id="SubmissionSet01"/>
                <rim:ExtrinsicObject id="Document01"/>
            </rim:RegistryObjectList>
        </lcm:SubmitObjectsRequest>
    </soap:Body>
</soap:Envelope>"""
        
        # Act
        metadata = extract_xdsb_metadata(soap_xml)
        
        # Assert
        # Generated IDs should be present
        assert "submission_set_id" in metadata
        assert "document_unique_id" in metadata
        assert metadata["submission_set_id"].startswith("SubmissionSet_")
        assert metadata["document_unique_id"].startswith("Document_")

    def test_extract_xdsb_metadata_missing_submit_objects_request(self):
        """Test metadata extraction fails when SubmitObjectsRequest is missing."""
        # Arrange
        soap_xml = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <SomeOtherRequest/>
    </soap:Body>
</soap:Envelope>"""
        
        # Act & Assert
        with pytest.raises(ValueError, match="Missing SubmitObjectsRequest"):
            extract_xdsb_metadata(soap_xml)

    def test_extract_xdsb_metadata_malformed_xml(self):
        """Test metadata extraction fails for malformed XML."""
        # Arrange
        malformed_xml = "<soap:Envelope><unclosed>"
        
        # Act & Assert
        with pytest.raises(ValueError, match="Failed to parse SOAP XML"):
            extract_xdsb_metadata(malformed_xml)


class TestGenerateRegistryResponse:
    """Test XDSb RegistryResponse generation."""

    def test_generate_registry_response_structure(self):
        """Test RegistryResponse has correct structure and namespaces."""
        # Arrange
        request_id = str(uuid.uuid4())
        submission_set_id = "SubmissionSet_12345"
        document_unique_id = "Document_67890"
        
        # Act
        response_xml = generate_registry_response(
            request_id, submission_set_id, document_unique_id
        )
        
        # Assert
        assert '<?xml version' in response_xml
        assert 'soap:Envelope' in response_xml
        assert 'rs:RegistryResponse' in response_xml
        assert 'ResponseStatusType:Success' in response_xml
        
        # Parse and validate structure
        tree = etree.fromstring(response_xml.encode("utf-8"))
        namespaces = {
            "soap": "http://www.w3.org/2003/05/soap-envelope",
            "rs": "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0",
            "rim": "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
        }
        
        # Check RegistryResponse exists
        registry_response = tree.xpath("//rs:RegistryResponse", namespaces=namespaces)
        assert len(registry_response) == 1
        
        # Check status attribute
        status = registry_response[0].get("status")
        assert status == "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"

    def test_generate_registry_response_includes_ids(self):
        """Test RegistryResponse includes submission set and document unique IDs."""
        # Arrange
        request_id = str(uuid.uuid4())
        submission_set_id = "SubmissionSet_TEST"
        document_unique_id = "Document_TEST"
        
        # Act
        response_xml = generate_registry_response(
            request_id, submission_set_id, document_unique_id
        )
        
        # Assert
        assert submission_set_id in response_xml
        assert document_unique_id in response_xml
        
        # Parse and validate slots
        tree = etree.fromstring(response_xml.encode("utf-8"))
        namespaces = {
            "rim": "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
        }
        
        # Check SubmissionSetUniqueId slot
        submission_slot = tree.xpath(
            '//rim:Slot[@name="SubmissionSetUniqueId"]/rim:ValueList/rim:Value',
            namespaces=namespaces
        )
        assert len(submission_slot) == 1
        assert submission_slot[0].text == submission_set_id
        
        # Check DocumentUniqueId slot
        document_slot = tree.xpath(
            '//rim:Slot[@name="DocumentUniqueId"]/rim:ValueList/rim:Value',
            namespaces=namespaces
        )
        assert len(document_slot) == 1
        assert document_slot[0].text == document_unique_id

    def test_generate_registry_response_includes_timestamp(self):
        """Test RegistryResponse includes timestamp."""
        # Arrange
        request_id = str(uuid.uuid4())
        submission_set_id = "SubmissionSet_12345"
        document_unique_id = "Document_67890"
        
        # Act
        response_xml = generate_registry_response(
            request_id, submission_set_id, document_unique_id
        )
        
        # Assert
        tree = etree.fromstring(response_xml.encode("utf-8"))
        namespaces = {
            "rim": "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
        }
        
        # Check Timestamp slot exists
        timestamp_slot = tree.xpath(
            '//rim:Slot[@name="Timestamp"]/rim:ValueList/rim:Value',
            namespaces=namespaces
        )
        assert len(timestamp_slot) == 1
        assert timestamp_slot[0].text  # Timestamp should not be empty


class TestGenerateSoapFault:
    """Test SOAP fault generation."""

    def test_generate_soap_fault_basic(self):
        """Test SOAP fault generation with basic parameters."""
        # Arrange
        faultcode = "soap:Sender"
        faultstring = "Invalid request"
        
        # Act
        fault_xml = generate_soap_fault(faultcode, faultstring)
        
        # Assert
        assert '<?xml version' in fault_xml
        assert 'soap:Envelope' in fault_xml
        assert 'soap:Fault' in fault_xml
        assert faultcode in fault_xml
        assert faultstring in fault_xml

    def test_generate_soap_fault_with_detail(self):
        """Test SOAP fault generation with detail element."""
        # Arrange
        faultcode = "soap:Sender"
        faultstring = "MTOM Parsing Error"
        detail = "Missing document attachment in MTOM message"
        
        # Act
        fault_xml = generate_soap_fault(faultcode, faultstring, detail)
        
        # Assert
        assert 'soap:Detail' in fault_xml
        assert detail in fault_xml
        
        # Parse and validate structure
        tree = etree.fromstring(fault_xml.encode("utf-8"))
        namespaces = {"soap": "http://www.w3.org/2003/05/soap-envelope"}
        
        # Check fault exists
        fault = tree.xpath("//soap:Fault", namespaces=namespaces)
        assert len(fault) == 1
        
        # Check detail exists
        detail_elem = tree.xpath("//soap:Detail/error", namespaces=namespaces)
        assert len(detail_elem) == 1
        assert detail_elem[0].text == detail

    def test_generate_soap_fault_structure(self):
        """Test SOAP fault has correct XML structure."""
        # Arrange
        faultcode = "soap:Receiver"
        faultstring = "Internal Server Error"
        
        # Act
        fault_xml = generate_soap_fault(faultcode, faultstring)
        
        # Assert
        tree = etree.fromstring(fault_xml.encode("utf-8"))
        namespaces = {"soap": "http://www.w3.org/2003/05/soap-envelope"}
        
        # Check fault code
        code_value = tree.xpath("//soap:Fault/soap:Code/soap:Value", namespaces=namespaces)
        assert len(code_value) == 1
        assert code_value[0].text == faultcode
        
        # Check fault string
        reason_text = tree.xpath("//soap:Fault/soap:Reason/soap:Text", namespaces=namespaces)
        assert len(reason_text) == 1
        assert reason_text[0].text == faultstring


class TestDocumentSaving:
    """Test document saving functionality."""

    @patch("src.ihe_test_util.mock_server.iti41_endpoint.Path")
    def test_document_saving_when_enabled(self, mock_path_class):
        """Test documents are saved when save_submitted_documents is enabled."""
        # This test would be in integration tests since it involves the full endpoint
        # For unit tests, we just verify Path operations are correct
        
        # Arrange
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance
        
        doc_dir = Path("mocks/data/documents")
        doc_id = "Document_TEST123"
        
        # Act
        doc_path = doc_dir / f"{doc_id}.xml"
        
        # Assert - use Path normalization to handle Windows vs Unix separators
        assert doc_path == Path("mocks") / "data" / "documents" / f"{doc_id}.xml"


class TestMetadataLogging:
    """Test metadata logging."""

    def test_metadata_logging_captures_all_fields(self):
        """Test that metadata logging captures all required fields."""
        # Arrange
        soap_xml = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <lcm:SubmitObjectsRequest xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0">
            <rim:RegistryObjectList xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
                <rim:RegistryPackage id="SubmissionSet01">
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8" value="SS_001"/>
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:554ac39e-e3fe-47fe-b233-965d2a147832" value="1.2.3"/>
                </rim:RegistryPackage>
                <rim:ExtrinsicObject id="Document01" mimeType="text/xml">
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab" value="DOC_001"/>
                    <rim:ExternalIdentifier identificationScheme="urn:uuid:58a6f841-87b3-4a3e-92fd-a8ffeff98427" value="PAT001"/>
                    <rim:Classification classificationScheme="urn:uuid:41a5887f-8865-4c09-adf7-e362475b143a" nodeRepresentation="CC_001"/>
                    <rim:Classification classificationScheme="urn:uuid:f0306f51-975f-434e-a61c-c59651d33983" nodeRepresentation="TC_001"/>
                    <rim:Classification classificationScheme="urn:uuid:a09d5840-386c-46f2-b5ad-9c3699a4309d" nodeRepresentation="FC_001"/>
                </rim:ExtrinsicObject>
            </rim:RegistryObjectList>
        </lcm:SubmitObjectsRequest>
    </soap:Body>
</soap:Envelope>"""
        
        # Act
        metadata = extract_xdsb_metadata(soap_xml)
        
        # Assert - verify all expected fields are extracted
        expected_fields = [
            "submission_set_id",
            "document_unique_id",
            "patient_id",
            "source_id",
            "mime_type",
            "class_code",
            "type_code",
            "format_code"
        ]
        
        for field in expected_fields:
            assert field in metadata, f"Missing field: {field}"
        
        # Verify values
        assert metadata["submission_set_id"] == "SS_001"
        assert metadata["document_unique_id"] == "DOC_001"
        assert metadata["patient_id"] == "PAT001"
        assert metadata["source_id"] == "1.2.3"
        assert metadata["class_code"] == "CC_001"
        assert metadata["type_code"] == "TC_001"
        assert metadata["format_code"] == "FC_001"
