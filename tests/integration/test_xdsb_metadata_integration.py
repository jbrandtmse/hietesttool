"""Integration tests for XDSb metadata workflow.

Tests verify XDSb metadata construction with real document data.
"""

import hashlib
from datetime import datetime
from pathlib import Path

import pytest
from lxml import etree

from ihe_test_util.config.xdsb_config import XDSbConfig, get_default_xdsb_config
from ihe_test_util.ihe_transactions.xdsb_metadata import (
    XDSbMetadataBuilder,
    build_xdsb_metadata,
    RIM_NS,
    XDS_NS,
)
from ihe_test_util.models.ccd import CCDDocument


# Namespace helper for XPath
NSMAP = {
    "xds": XDS_NS,
    "rim": RIM_NS,
}


@pytest.fixture
def test_ccd_path() -> Path:
    """Path to test CCD template."""
    return Path("tests/fixtures/test_ccd_template.xml")


@pytest.fixture
def real_ccd_document(test_ccd_path: Path) -> CCDDocument:
    """Create CCD document from actual test file."""
    if not test_ccd_path.exists():
        pytest.skip(f"Test fixture not found: {test_ccd_path}")
    
    xml_content = test_ccd_path.read_text(encoding="utf-8")
    return CCDDocument(
        document_id="test-doc-001",
        patient_id="PAT123456",
        template_path=str(test_ccd_path),
        xml_content=xml_content,
        creation_timestamp=datetime(2025, 11, 22, 10, 0, 0),
    )


class TestRealCCDDocument:
    """6.1-INT-001: Build complete request with real CCD document."""

    def test_metadata_with_real_ccd_document(
        self, real_ccd_document: CCDDocument
    ) -> None:
        """Verify metadata generation with real CCD content."""
        # Arrange
        config = get_default_xdsb_config()
        builder = XDSbMetadataBuilder(config)
        builder.set_patient_identifier("PAT123456", "2.16.840.1.113883.3.72.5.9.1")
        builder.set_document(real_ccd_document)
        
        # Act
        result = builder.build()
        
        # Assert - verify complete structure
        assert result.tag == f"{{{XDS_NS}}}ProvideAndRegisterDocumentSetRequest"
        
        # Verify document entry exists
        doc_entries = result.xpath(
            "//rim:ExtrinsicObject",
            namespaces=NSMAP,
        )
        assert len(doc_entries) == 1
        
        # Verify submission set exists
        registry_packages = result.xpath(
            "//rim:RegistryPackage",
            namespaces=NSMAP,
        )
        assert len(registry_packages) == 1
        
        # Verify association exists
        associations = result.xpath(
            "//rim:Association",
            namespaces=NSMAP,
        )
        assert len(associations) == 1


class TestHashVerification:
    """6.1-INT-002: Verify hash calculation against known CCD content."""

    def test_hash_calculation_with_known_content(
        self, real_ccd_document: CCDDocument
    ) -> None:
        """Verify SHA-256 hash is calculated correctly."""
        # Arrange
        expected_hash = hashlib.sha256(
            real_ccd_document.xml_content.encode("utf-8")
        ).hexdigest().lower()
        
        config = get_default_xdsb_config()
        builder = XDSbMetadataBuilder(config)
        builder.set_patient_identifier("PAT123456", "2.16.840.1.113883.3.72.5.9.1")
        builder.set_document(real_ccd_document)
        
        # Act
        result = builder.build()
        
        # Assert
        hash_values = result.xpath(
            "//rim:ExtrinsicObject//rim:Slot[@name='hash']/rim:ValueList/rim:Value",
            namespaces=NSMAP,
        )
        assert len(hash_values) == 1
        assert hash_values[0].text == expected_hash


class TestSizeVerification:
    """6.1-INT-003: Verify size calculation against file system size."""

    def test_size_calculation_matches_file_size(
        self, real_ccd_document: CCDDocument
    ) -> None:
        """Verify size slot matches actual document byte count."""
        # Arrange
        expected_size = len(real_ccd_document.xml_content.encode("utf-8"))
        
        config = get_default_xdsb_config()
        builder = XDSbMetadataBuilder(config)
        builder.set_patient_identifier("PAT123456", "2.16.840.1.113883.3.72.5.9.1")
        builder.set_document(real_ccd_document)
        
        # Act
        result = builder.build()
        
        # Assert
        size_values = result.xpath(
            "//rim:ExtrinsicObject//rim:Slot[@name='size']/rim:ValueList/rim:Value",
            namespaces=NSMAP,
        )
        assert len(size_values) == 1
        assert int(size_values[0].text) == expected_size


class TestConfigurationLoading:
    """6.1-INT-006: Verify configuration loading."""

    def test_metadata_configuration_loading(
        self, real_ccd_document: CCDDocument
    ) -> None:
        """Verify configuration values are properly applied."""
        # Arrange
        config = XDSbConfig(
            source_id="2.16.840.1.113883.3.72.5.9.99",
            language_code="de-DE",
        )
        builder = XDSbMetadataBuilder(config)
        builder.set_patient_identifier("PAT123456", "2.16.840.1.113883.3.72.5.9.1")
        builder.set_document(real_ccd_document)
        
        # Act
        result = builder.build()
        
        # Assert - verify source ID from config
        source_ids = result.xpath(
            "//rim:ExternalIdentifier[contains(@identificationScheme, '554ac39e')]",
            namespaces=NSMAP,
        )
        assert len(source_ids) == 1
        assert source_ids[0].get("value") == "2.16.840.1.113883.3.72.5.9.99"
        
        # Verify language code from config
        language_codes = result.xpath(
            "//rim:Slot[@name='languageCode']/rim:ValueList/rim:Value",
            namespaces=NSMAP,
        )
        assert len(language_codes) == 1
        assert language_codes[0].text == "de-DE"


class TestConvenienceFunction:
    """Test build_xdsb_metadata convenience function integration."""

    def test_convenience_function_with_real_document(
        self, real_ccd_document: CCDDocument
    ) -> None:
        """Verify convenience function works with real document."""
        # Arrange - document already created
        
        # Act
        metadata, ss_id, doc_id = build_xdsb_metadata(
            document=real_ccd_document,
            patient_id="PAT123456",
            patient_id_oid="2.16.840.1.113883.3.72.5.9.1",
        )
        
        # Assert
        assert metadata is not None
        assert ss_id.startswith("urn:uuid:")
        assert doc_id.startswith("urn:uuid:")
        
        # Verify XML is well-formed
        xml_string = etree.tostring(metadata, encoding="unicode")
        assert "ProvideAndRegisterDocumentSetRequest" in xml_string
