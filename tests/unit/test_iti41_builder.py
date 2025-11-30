"""Unit tests for ITI-41 transaction builder module.

Tests the ITI41Request class and build_iti41_request function.
"""

import tempfile
import uuid
from pathlib import Path

import pytest
from lxml import etree

from ihe_test_util.ihe_transactions.iti41 import (
    ITI41Request,
    build_iti41_request,
    _add_slot,
    _add_name,
    XDS_NS,
    RIM_NS,
    LCM_NS,
    NSMAP,
)


class TestITI41Request:
    """Tests for ITI41Request class."""

    def test_init_with_required_params(self) -> None:
        """Test ITI41Request initialization with required parameters only."""
        request = ITI41Request(
            patient_id="PAT001",
            patient_id_root="2.16.840.1.113883.3.72.5.9.1"
        )
        
        assert request.patient_id == "PAT001"
        assert request.patient_id_root == "2.16.840.1.113883.3.72.5.9.1"
        # Auto-generated IDs should be UUIDs
        assert request.document_unique_id is not None
        assert request.submission_set_id is not None
        # Default OIDs
        assert request.document_unique_id_root == "2.16.840.1.113883.3.72.5.9.1"
        assert request.submission_set_id_root == "2.16.840.1.113883.3.72.5.9.2"

    def test_init_with_all_params(self) -> None:
        """Test ITI41Request initialization with all parameters."""
        request = ITI41Request(
            patient_id="PAT002",
            patient_id_root="1.2.3.4.5",
            document_unique_id="doc-123",
            document_unique_id_root="1.2.3.4.6",
            submission_set_id="ss-456",
            submission_set_id_root="1.2.3.4.7"
        )
        
        assert request.patient_id == "PAT002"
        assert request.patient_id_root == "1.2.3.4.5"
        assert request.document_unique_id == "doc-123"
        assert request.document_unique_id_root == "1.2.3.4.6"
        assert request.submission_set_id == "ss-456"
        assert request.submission_set_id_root == "1.2.3.4.7"

    def test_auto_generated_ids_are_unique(self) -> None:
        """Test that auto-generated IDs are unique across instances."""
        request1 = ITI41Request(patient_id="PAT1", patient_id_root="1.2.3")
        request2 = ITI41Request(patient_id="PAT2", patient_id_root="1.2.3")
        
        assert request1.document_unique_id != request2.document_unique_id
        assert request1.submission_set_id != request2.submission_set_id


class TestBuildITI41Request:
    """Tests for build_iti41_request function."""

    @pytest.fixture
    def sample_ccd_document(self, tmp_path: Path) -> Path:
        """Create a sample CCD document for testing."""
        ccd_content = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <realmCode code="US"/>
    <typeId root="2.16.840.1.113883.1.3" extension="POCD_HD000040"/>
    <templateId root="2.16.840.1.113883.10.20.22.1.1"/>
    <id root="2.16.840.1.113883.19.5.99999.1" extension="Test123"/>
    <code code="34133-9" codeSystem="2.16.840.1.113883.6.1"/>
    <title>Test Clinical Document</title>
    <effectiveTime value="20251130120000"/>
    <recordTarget>
        <patientRole>
            <id root="2.16.840.1.113883.3.72.5.9.1" extension="PAT001"/>
            <patient>
                <name><given>John</given><family>Doe</family></name>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
"""
        ccd_path = tmp_path / "test_ccd.xml"
        ccd_path.write_text(ccd_content)
        return ccd_path

    def test_build_request_success(self, sample_ccd_document: Path) -> None:
        """Test successful ITI-41 request build."""
        request = ITI41Request(
            patient_id="PAT001",
            patient_id_root="2.16.840.1.113883.3.72.5.9.1"
        )
        
        xml_string, attachment = build_iti41_request(
            request=request,
            document_path=sample_ccd_document
        )
        
        # Verify XML is valid
        assert xml_string is not None
        root = etree.fromstring(xml_string.encode('utf-8'))
        
        # Verify root element
        assert root.tag == f"{{{XDS_NS}}}ProvideAndRegisterDocumentSetRequest"
        
        # Verify SubmitObjectsRequest
        submit_request = root.find(f".//{{{LCM_NS}}}SubmitObjectsRequest")
        assert submit_request is not None
        
        # Verify RegistryObjectList
        registry_list = root.find(f".//{{{RIM_NS}}}RegistryObjectList")
        assert registry_list is not None
        
        # Verify ExtrinsicObject (Document Entry)
        extrinsic = root.find(f".//{{{RIM_NS}}}ExtrinsicObject")
        assert extrinsic is not None
        assert extrinsic.get("mimeType") == "text/xml"
        
        # Verify attachment
        assert attachment is not None
        assert attachment.content_id is not None

    def test_build_request_with_custom_params(self, sample_ccd_document: Path) -> None:
        """Test ITI-41 request build with custom parameters."""
        request = ITI41Request(
            patient_id="PAT002",
            patient_id_root="1.2.3.4.5"
        )
        
        xml_string, attachment = build_iti41_request(
            request=request,
            document_path=sample_ccd_document,
            content_id="custom@test.com",
            document_title="Custom Title",
            class_code="11488-4",
            type_code="11488-4",
            format_code="urn:custom:format"
        )
        
        root = etree.fromstring(xml_string.encode('utf-8'))
        
        # Verify Document Name
        name_elem = root.find(f".//{{{RIM_NS}}}Name/{{{RIM_NS}}}LocalizedString")
        assert name_elem is not None
        assert name_elem.get("value") == "Custom Title"
        
        # Verify attachment content ID
        assert attachment.content_id == "custom@test.com"

    def test_build_request_file_not_found(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised for non-existent document."""
        request = ITI41Request(
            patient_id="PAT001",
            patient_id_root="1.2.3"
        )
        
        nonexistent_path = tmp_path / "nonexistent.xml"
        
        with pytest.raises(FileNotFoundError) as exc_info:
            build_iti41_request(request=request, document_path=nonexistent_path)
        
        assert "Document not found" in str(exc_info.value)

    def test_build_request_contains_patient_id(self, sample_ccd_document: Path) -> None:
        """Test that request contains correct patient ID."""
        request = ITI41Request(
            patient_id="TEST-PAT-123",
            patient_id_root="2.16.840.1.113883.3.72.5.9.1"
        )
        
        xml_string, _ = build_iti41_request(
            request=request,
            document_path=sample_ccd_document
        )
        
        # Patient ID should appear in the XML
        assert "TEST-PAT-123" in xml_string
        assert "2.16.840.1.113883.3.72.5.9.1" in xml_string

    def test_build_request_contains_document_element(self, sample_ccd_document: Path) -> None:
        """Test that request contains Document element for MTOM."""
        request = ITI41Request(
            patient_id="PAT001",
            patient_id_root="1.2.3"
        )
        
        xml_string, _ = build_iti41_request(
            request=request,
            document_path=sample_ccd_document
        )
        
        root = etree.fromstring(xml_string.encode('utf-8'))
        
        # Verify Document element exists
        doc_elem = root.find(f".//{{{XDS_NS}}}Document")
        assert doc_elem is not None
        assert doc_elem.get("id") == "Document01"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_add_slot(self) -> None:
        """Test _add_slot helper function."""
        parent = etree.Element(f"{{{RIM_NS}}}Classification")
        
        _add_slot(parent, "codingScheme", "2.16.840.1.113883.6.1")
        
        slot = parent.find(f".//{{{RIM_NS}}}Slot")
        assert slot is not None
        assert slot.get("name") == "codingScheme"
        
        value = slot.find(f".//{{{RIM_NS}}}Value")
        assert value is not None
        assert value.text == "2.16.840.1.113883.6.1"

    def test_add_name(self) -> None:
        """Test _add_name helper function."""
        parent = etree.Element(f"{{{RIM_NS}}}Classification")
        
        _add_name(parent, "Test Name Value")
        
        name = parent.find(f".//{{{RIM_NS}}}Name")
        assert name is not None
        
        localized = name.find(f".//{{{RIM_NS}}}LocalizedString")
        assert localized is not None
        assert localized.get("value") == "Test Name Value"


class TestNamespaceConstants:
    """Tests for namespace constants."""

    def test_namespace_constants_defined(self) -> None:
        """Test that all namespace constants are properly defined."""
        assert XDS_NS == "urn:ihe:iti:xds-b:2007"
        assert RIM_NS == "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
        assert LCM_NS == "urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0"

    def test_nsmap_contains_all_namespaces(self) -> None:
        """Test that NSMAP contains all required namespaces."""
        assert "xds" in NSMAP
        assert "rim" in NSMAP
        assert "lcm" in NSMAP
        assert "rs" in NSMAP
        
        assert NSMAP["xds"] == XDS_NS
        assert NSMAP["rim"] == RIM_NS
        assert NSMAP["lcm"] == LCM_NS
