"""Integration tests for MTOM workflow.

Tests for complete MTOM workflow with real CCD fixtures per Story 6.2.
Follows AAA pattern (Arrange, Act, Assert) per test-strategy-and-standards.md.
"""

import hashlib
import os
from pathlib import Path

import pytest
from lxml import etree

from ihe_test_util.ihe_transactions.mtom import (
    MTOMAttachment,
    MTOMPackage,
    XOP_NS,
    generate_content_id,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_ccd_path() -> Path:
    """Path to test CCD template fixture."""
    return Path("tests/fixtures/test_ccd_template.xml")


@pytest.fixture
def test_ccd_content(test_ccd_path: Path) -> bytes:
    """Content of test CCD template fixture."""
    return test_ccd_path.read_bytes()


@pytest.fixture
def real_soap_envelope_with_xop() -> bytes:
    """Real SOAP envelope with XOP Include for integration testing."""
    content_id = "doc1@ihe-test-util.local"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:xds="urn:ihe:iti:xds-b:2007"
               xmlns:xop="http://www.w3.org/2004/08/xop/include">
    <soap:Header>
        <wsa:Action xmlns:wsa="http://www.w3.org/2005/08/addressing">
            urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b
        </wsa:Action>
    </soap:Header>
    <soap:Body>
        <xds:ProvideAndRegisterDocumentSetRequest>
            <xds:Document id="Document01">
                <xop:Include href="cid:{content_id}"/>
            </xds:Document>
        </xds:ProvideAndRegisterDocumentSetRequest>
    </soap:Body>
</soap:Envelope>""".encode("utf-8")


# =============================================================================
# Integration Tests - Real CCD Fixture (6.2-INT-001 to 005)
# =============================================================================


class TestMTOMWithRealCCD:
    """Integration tests using real CCD fixture (6.2-INT-001 to 005)."""

    def test_attachment_from_real_ccd_fixture(self, test_ccd_path: Path) -> None:
        """Test creating attachment from real CCD fixture (6.2-INT-001)."""
        # Arrange
        content_id = generate_content_id()

        # Act
        attachment = MTOMAttachment.from_file(test_ccd_path, content_id)

        # Assert
        assert attachment.content == test_ccd_path.read_bytes()
        assert attachment.size_bytes > 0
        assert len(attachment.sha256_hash) == 64
        assert "@" in attachment.content_id

    def test_hash_of_ccd_fixture_matches_expected(
        self, test_ccd_path: Path, test_ccd_content: bytes
    ) -> None:
        """Test hash of CCD fixture matches expected value (6.2-INT-002)."""
        # Arrange
        expected_hash = hashlib.sha256(test_ccd_content).hexdigest()
        content_id = generate_content_id()

        # Act
        attachment = MTOMAttachment.from_file(test_ccd_path, content_id)

        # Assert
        assert attachment.sha256_hash == expected_hash
        assert attachment.sha256_hash == attachment.sha256_hash.lower()

    def test_size_matches_file_system_size(self, test_ccd_path: Path) -> None:
        """Test size matches file system size (6.2-INT-003)."""
        # Arrange
        expected_size = test_ccd_path.stat().st_size
        content_id = generate_content_id()

        # Act
        attachment = MTOMAttachment.from_file(test_ccd_path, content_id)

        # Assert
        assert attachment.size_bytes == expected_size

    def test_xop_reference_resolution(self, test_ccd_path: Path) -> None:
        """Test Content-ID lookup via XOP reference (6.2-INT-004)."""
        # Arrange
        content_id = "doc1@ihe-test-util.local"
        attachment = MTOMAttachment.from_file(test_ccd_path, content_id)

        # Act
        xop_include = attachment.get_xop_include()
        href = xop_include.get("href")

        # Assert
        assert href == f"cid:{content_id}"
        # Verify we can resolve back to content_id
        resolved_id = href[4:]  # Remove "cid:" prefix
        assert resolved_id == attachment.content_id

    def test_mtom_package_parseable_by_mime_parser(
        self, test_ccd_path: Path, real_soap_envelope_with_xop: bytes
    ) -> None:
        """Test built MTOM package parseable by MIME parser (6.2-INT-005)."""
        # Arrange
        from email import message_from_bytes
        from email.policy import default

        content_id = "doc1@ihe-test-util.local"
        attachment = MTOMAttachment.from_file(test_ccd_path, content_id)
        package = MTOMPackage(real_soap_envelope_with_xop)
        package.add_attachment(attachment)

        # Act
        message_bytes, content_type = package.build()

        # Parse as MIME message
        # Prepend Content-Type header for parsing
        full_message = f"Content-Type: {content_type}\r\n\r\n".encode() + message_bytes
        parsed = message_from_bytes(full_message, policy=default)

        # Assert
        assert parsed.is_multipart()
        parts = list(parsed.iter_parts())
        assert len(parts) >= 2  # At least SOAP envelope + 1 attachment


class TestMTOMHashIntegrity:
    """Tests for hash integrity across MTOM workflow."""

    def test_hash_consistent_across_methods(self, test_ccd_path: Path) -> None:
        """Test hash is consistent whether calculated directly or via property."""
        # Arrange
        content = test_ccd_path.read_bytes()
        direct_hash = hashlib.sha256(content).hexdigest()
        attachment = MTOMAttachment.from_file(
            test_ccd_path, "doc1@ihe-test-util.local"
        )

        # Act
        property_hash = attachment.sha256_hash
        method_hash = attachment.calculate_hash()

        # Assert
        assert property_hash == direct_hash
        assert method_hash == direct_hash

    def test_hash_immutable_after_creation(self, test_ccd_path: Path) -> None:
        """Test hash doesn't change after creation."""
        # Arrange
        attachment = MTOMAttachment.from_file(
            test_ccd_path, "doc1@ihe-test-util.local"
        )

        # Act
        hash1 = attachment.sha256_hash
        hash2 = attachment.sha256_hash
        hash3 = attachment.calculate_hash()

        # Assert
        assert hash1 == hash2 == hash3


class TestMTOMPackageIntegration:
    """Integration tests for complete MTOM package workflow."""

    def test_complete_mtom_package_workflow(
        self, test_ccd_path: Path, real_soap_envelope_with_xop: bytes
    ) -> None:
        """Test complete MTOM package build and validation workflow."""
        # Arrange
        content_id = "doc1@ihe-test-util.local"
        attachment = MTOMAttachment.from_file(test_ccd_path, content_id)
        package = MTOMPackage(real_soap_envelope_with_xop)
        package.add_attachment(attachment)

        # Act
        is_valid, errors = package.validate()
        message_bytes, content_type = package.build()

        # Assert
        assert is_valid, f"Validation errors: {errors}"
        assert len(message_bytes) > 0
        assert "multipart/related" in content_type
        assert package.boundary in content_type

    def test_mtom_package_contains_document_content(
        self, test_ccd_path: Path, test_ccd_content: bytes, real_soap_envelope_with_xop: bytes
    ) -> None:
        """Test built MTOM package contains original document content."""
        # Arrange
        content_id = "doc1@ihe-test-util.local"
        attachment = MTOMAttachment.from_file(test_ccd_path, content_id)
        package = MTOMPackage(real_soap_envelope_with_xop)
        package.add_attachment(attachment)

        # Act
        message_bytes, _ = package.build()

        # Assert
        # The document content should appear in the message
        # Note: MIME processing may normalize line endings (\r\n -> \n)
        normalized_content = test_ccd_content.replace(b"\r\n", b"\n")
        assert normalized_content in message_bytes or test_ccd_content in message_bytes

    def test_mtom_package_boundary_structure(
        self, test_ccd_path: Path, real_soap_envelope_with_xop: bytes
    ) -> None:
        """Test MTOM package has correct boundary structure."""
        # Arrange
        content_id = "doc1@ihe-test-util.local"
        attachment = MTOMAttachment.from_file(test_ccd_path, content_id)
        package = MTOMPackage(real_soap_envelope_with_xop)
        package.add_attachment(attachment)

        # Act
        message_bytes, _ = package.build()
        message_str = message_bytes.decode("utf-8", errors="replace")

        # Assert
        # Should have opening boundaries
        assert f"--{package.boundary}" in message_str
        # Should have closing boundary
        assert f"--{package.boundary}--" in message_str


class TestMultipleDocumentsIntegration:
    """Integration tests for multiple document handling."""

    def test_multiple_documents_workflow(
        self, test_ccd_path: Path
    ) -> None:
        """Test workflow with multiple document attachments."""
        # Arrange
        soap_envelope = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body><test/></soap:Body>
</soap:Envelope>"""

        attachment1 = MTOMAttachment.from_file(test_ccd_path, "doc1@example.com")
        attachment2 = MTOMAttachment(
            b"<secondary>document</secondary>", "doc2@example.com"
        )

        package = MTOMPackage(soap_envelope)
        package.add_attachment(attachment1)
        package.add_attachment(attachment2)

        # Act
        message_bytes, content_type = package.build()

        # Assert
        assert len(package.attachments) == 2
        assert b"doc1@example.com" in message_bytes
        assert b"doc2@example.com" in message_bytes

    def test_each_attachment_unique_content_id(self, test_ccd_path: Path) -> None:
        """Test each attachment gets unique Content-ID."""
        # Arrange
        attachments = [
            MTOMAttachment.from_file_streaming(test_ccd_path),
            MTOMAttachment.from_file_streaming(test_ccd_path),
            MTOMAttachment.from_file_streaming(test_ccd_path),
        ]

        # Act
        content_ids = [a.content_id for a in attachments]

        # Assert
        assert len(content_ids) == len(set(content_ids))  # All unique


class TestXOPIncludeIntegration:
    """Integration tests for XOP Include element generation."""

    def test_xop_include_valid_xml_structure(self, test_ccd_path: Path) -> None:
        """Test XOP Include produces valid XML structure."""
        # Arrange
        attachment = MTOMAttachment.from_file(
            test_ccd_path, "doc1@ihe-test-util.local"
        )

        # Act
        xop_include = attachment.get_xop_include()

        # Assert
        # Serialize and parse to verify XML validity
        xml_string = etree.tostring(xop_include, encoding="unicode")
        parsed = etree.fromstring(xml_string)
        assert parsed.tag == f"{{{XOP_NS}}}Include"
        assert "href" in parsed.attrib

    def test_xop_include_in_soap_context(self, test_ccd_path: Path) -> None:
        """Test XOP Include can be inserted into SOAP context."""
        # Arrange
        attachment = MTOMAttachment.from_file(
            test_ccd_path, "doc1@ihe-test-util.local"
        )
        soap_body = etree.Element(
            "{http://www.w3.org/2003/05/soap-envelope}Body"
        )
        document_elem = etree.SubElement(
            soap_body, "{urn:ihe:iti:xds-b:2007}Document"
        )

        # Act
        xop_include = attachment.get_xop_include()
        document_elem.append(xop_include)

        # Assert
        serialized = etree.tostring(soap_body, encoding="unicode")
        assert "xop:Include" in serialized
        assert f"cid:{attachment.content_id}" in serialized


class TestStreamingIntegration:
    """Integration tests for streaming large document handling."""

    def test_streaming_produces_same_hash(self, test_ccd_path: Path) -> None:
        """Test streaming produces same hash as direct loading."""
        # Arrange
        direct_attachment = MTOMAttachment.from_file(
            test_ccd_path, "doc1@example.com"
        )

        # Act
        streaming_attachment = MTOMAttachment.from_file_streaming(
            test_ccd_path, "doc2@example.com"
        )

        # Assert
        assert direct_attachment.sha256_hash == streaming_attachment.sha256_hash

    def test_streaming_produces_same_size(self, test_ccd_path: Path) -> None:
        """Test streaming produces same size as direct loading."""
        # Arrange
        direct_attachment = MTOMAttachment.from_file(
            test_ccd_path, "doc1@example.com"
        )

        # Act
        streaming_attachment = MTOMAttachment.from_file_streaming(
            test_ccd_path, "doc2@example.com"
        )

        # Assert
        assert direct_attachment.size_bytes == streaming_attachment.size_bytes
