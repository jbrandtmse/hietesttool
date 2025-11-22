"""Unit tests for MTOM attachment handling.

Tests for MTOMAttachment, MTOMPackage, and generate_content_id per Story 6.2.
Follows AAA pattern (Arrange, Act, Assert) per test-strategy-and-standards.md.
"""

import base64
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from lxml import etree

from ihe_test_util.ihe_transactions.mtom import (
    DEFAULT_CHUNK_SIZE,
    LARGE_DOCUMENT_THRESHOLD,
    XOP_NS,
    MTOMAttachment,
    MTOMError,
    MTOMPackage,
    generate_content_id,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_content() -> bytes:
    """Sample XML content for testing."""
    return b'<?xml version="1.0" encoding="UTF-8"?><root><data>test</data></root>'


@pytest.fixture
def known_hash_content() -> bytes:
    """Content with known SHA-256 hash for verification."""
    return b"test content for hashing"


@pytest.fixture
def known_hash() -> str:
    """Pre-calculated SHA-256 hash for known_hash_content."""
    return hashlib.sha256(b"test content for hashing").hexdigest()


@pytest.fixture
def sample_attachment(sample_content: bytes) -> MTOMAttachment:
    """Sample MTOM attachment for testing."""
    return MTOMAttachment(
        content=sample_content,
        content_id="doc1@ihe-test-util.local",
        content_type="application/xml"
    )


@pytest.fixture
def sample_soap_envelope() -> bytes:
    """Sample SOAP envelope for MTOM package testing."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <test>Sample SOAP body</test>
    </soap:Body>
</soap:Envelope>"""


@pytest.fixture
def soap_with_xop_include() -> bytes:
    """SOAP envelope with XOP Include reference."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:xop="http://www.w3.org/2004/08/xop/include">
    <soap:Body>
        <Document>
            <xop:Include href="cid:doc1@ihe-test-util.local"/>
        </Document>
    </soap:Body>
</soap:Envelope>"""


@pytest.fixture
def temp_xml_file(sample_content: bytes) -> Path:
    """Create temporary XML file for testing."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".xml", delete=False) as f:
        f.write(sample_content)
        return Path(f.name)


@pytest.fixture
def large_temp_file() -> Path:
    """Create large temporary file (> 1MB) for streaming tests."""
    # Create content > 1MB
    content = b"x" * (LARGE_DOCUMENT_THRESHOLD + 1024)
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".xml", delete=False) as f:
        f.write(content)
        return Path(f.name)


# =============================================================================
# MTOMAttachment Tests - Creation (AC1)
# =============================================================================


class TestMTOMAttachmentCreation:
    """Tests for MTOMAttachment creation (6.2-UNIT-001, 6.2-UNIT-002)."""

    def test_attachment_from_bytes(self, sample_content: bytes) -> None:
        """Test creating MTOMAttachment from bytes (6.2-UNIT-001)."""
        # Arrange
        content_id = "doc1@example.com"
        content_type = "application/xml"

        # Act
        attachment = MTOMAttachment(
            content=sample_content,
            content_id=content_id,
            content_type=content_type
        )

        # Assert
        assert attachment.content == sample_content
        assert attachment.content_id == content_id
        assert attachment.content_type == content_type

    def test_attachment_from_file(self, temp_xml_file: Path) -> None:
        """Test creating MTOMAttachment from file path (6.2-UNIT-002)."""
        # Arrange
        content_id = "doc1@example.com"

        # Act
        attachment = MTOMAttachment.from_file(
            file_path=temp_xml_file,
            content_id=content_id
        )

        # Assert
        assert attachment.content == temp_xml_file.read_bytes()
        assert attachment.content_id == content_id
        assert attachment.content_type == "application/xml"

        # Cleanup
        temp_xml_file.unlink()

    def test_attachment_from_file_not_found(self) -> None:
        """Test FileNotFoundError for missing file."""
        # Arrange
        non_existent_path = Path("/nonexistent/file.xml")

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            MTOMAttachment.from_file(non_existent_path, "doc1@example.com")
        
        assert "Attachment file not found" in str(exc_info.value)

    def test_attachment_default_content_type(self, sample_content: bytes) -> None:
        """Test default content type is application/xml."""
        # Arrange & Act
        attachment = MTOMAttachment(
            content=sample_content,
            content_id="doc1@example.com"
        )

        # Assert
        assert attachment.content_type == "application/xml"


# =============================================================================
# Content-ID Tests (AC2)
# =============================================================================


class TestContentID:
    """Tests for Content-ID generation and references (6.2-UNIT-005 to 009)."""

    def test_content_id_format_contains_at_symbol(self) -> None:
        """Test Content-ID format contains @ symbol (6.2-UNIT-005)."""
        # Arrange & Act
        content_id = generate_content_id()

        # Assert
        assert "@" in content_id

    def test_content_id_contains_uuid(self) -> None:
        """Test Content-ID contains UUID component (6.2-UNIT-006)."""
        # Arrange & Act
        content_id = generate_content_id("example.com")

        # Assert
        uuid_part = content_id.split("@")[0]
        # UUID format: 8-4-4-4-12 (36 characters with hyphens)
        assert len(uuid_part) == 36
        assert uuid_part.count("-") == 4

    def test_content_id_custom_domain(self) -> None:
        """Test Content-ID with custom domain."""
        # Arrange
        domain = "custom.domain.org"

        # Act
        content_id = generate_content_id(domain)

        # Assert
        assert content_id.endswith(f"@{domain}")

    def test_content_id_uniqueness(self) -> None:
        """Test Content-ID generates unique values."""
        # Arrange & Act
        ids = [generate_content_id() for _ in range(100)]

        # Assert
        assert len(ids) == len(set(ids))

    def test_cid_reference_format(self, sample_attachment: MTOMAttachment) -> None:
        """Test get_cid_reference() returns cid: URI (6.2-UNIT-007)."""
        # Arrange & Act
        cid_ref = sample_attachment.get_cid_reference()

        # Assert
        assert cid_ref.startswith("cid:")
        assert cid_ref == f"cid:{sample_attachment.content_id}"

    def test_xop_include_element(self, sample_attachment: MTOMAttachment) -> None:
        """Test get_xop_include() returns valid XOP element (6.2-UNIT-009)."""
        # Arrange & Act
        xop_elem = sample_attachment.get_xop_include()

        # Assert
        assert xop_elem.tag == f"{{{XOP_NS}}}Include"
        assert xop_elem.get("href") == sample_attachment.get_cid_reference()

    def test_xop_include_namespace(self, sample_attachment: MTOMAttachment) -> None:
        """Test XOP Include element has correct namespace."""
        # Arrange & Act
        xop_elem = sample_attachment.get_xop_include()

        # Assert
        assert xop_elem.nsmap.get("xop") == XOP_NS


# =============================================================================
# Base64 Encoding Tests (AC3)
# =============================================================================


class TestBase64Encoding:
    """Tests for base64 encoding (6.2-UNIT-012)."""

    def test_base64_content_property(self, sample_content: bytes) -> None:
        """Test base64_content property returns valid base64 (6.2-UNIT-012)."""
        # Arrange
        attachment = MTOMAttachment(sample_content, "doc1@example.com")

        # Act
        b64_content = attachment.base64_content

        # Assert
        decoded = base64.b64decode(b64_content)
        assert decoded == sample_content

    def test_base64_encoding_roundtrip(self) -> None:
        """Test base64 encoding can be decoded back to original."""
        # Arrange
        original = b"Hello, World! \x00\x01\x02 Binary data"
        attachment = MTOMAttachment(original, "doc1@example.com")

        # Act
        encoded = attachment.base64_content
        decoded = base64.b64decode(encoded)

        # Assert
        assert decoded == original


# =============================================================================
# SHA-256 Hash Tests (AC4)
# =============================================================================


class TestSHA256Hash:
    """Tests for SHA-256 hash calculation (6.2-UNIT-015 to 017)."""

    def test_sha256_hash_lowercase_hex(self, sample_attachment: MTOMAttachment) -> None:
        """Test sha256_hash returns lowercase hex (6.2-UNIT-015)."""
        # Arrange & Act
        hash_value = sample_attachment.sha256_hash

        # Assert
        assert hash_value == hash_value.lower()
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_sha256_hash_length(self, sample_attachment: MTOMAttachment) -> None:
        """Test sha256_hash is 64 characters (6.2-UNIT-016)."""
        # Arrange & Act
        hash_value = sample_attachment.sha256_hash

        # Assert
        assert len(hash_value) == 64

    def test_sha256_hash_matches_precalculated(
        self, known_hash_content: bytes, known_hash: str
    ) -> None:
        """Test sha256_hash matches pre-calculated value (6.2-UNIT-017)."""
        # Arrange
        attachment = MTOMAttachment(known_hash_content, "doc1@example.com")

        # Act
        hash_value = attachment.sha256_hash

        # Assert
        assert hash_value == known_hash

    def test_sha256_hash_cached(self, sample_attachment: MTOMAttachment) -> None:
        """Test hash is cached after first calculation."""
        # Arrange & Act
        hash1 = sample_attachment.sha256_hash
        hash2 = sample_attachment.sha256_hash

        # Assert
        assert hash1 is hash2  # Same object (cached)

    def test_calculate_hash_method(self, sample_content: bytes) -> None:
        """Test calculate_hash() method."""
        # Arrange
        attachment = MTOMAttachment(sample_content, "doc1@example.com")
        expected = hashlib.sha256(sample_content).hexdigest()

        # Act
        result = attachment.calculate_hash()

        # Assert
        assert result == expected


# =============================================================================
# Size Calculation Tests (AC5)
# =============================================================================


class TestSizeCalculation:
    """Tests for size calculation (6.2-UNIT-019, 6.2-UNIT-020)."""

    def test_size_bytes_exact_count(self, sample_content: bytes) -> None:
        """Test size_bytes returns exact byte count (6.2-UNIT-019)."""
        # Arrange
        attachment = MTOMAttachment(sample_content, "doc1@example.com")

        # Act
        size = attachment.size_bytes

        # Assert
        assert size == len(sample_content)

    def test_size_matches_len_content(self, sample_attachment: MTOMAttachment) -> None:
        """Test size_bytes matches len(content) (6.2-UNIT-020)."""
        # Arrange & Act
        size = sample_attachment.size_bytes

        # Assert
        assert size == len(sample_attachment.content)

    def test_calculate_size_method(self, sample_content: bytes) -> None:
        """Test calculate_size() method."""
        # Arrange
        attachment = MTOMAttachment(sample_content, "doc1@example.com")

        # Act
        result = attachment.calculate_size()

        # Assert
        assert result == len(sample_content)

    def test_is_large_document_false(self, sample_content: bytes) -> None:
        """Test is_large_document returns False for small documents."""
        # Arrange
        attachment = MTOMAttachment(sample_content, "doc1@example.com")

        # Act & Assert
        assert not attachment.is_large_document

    def test_is_large_document_true(self) -> None:
        """Test is_large_document returns True for large documents."""
        # Arrange
        large_content = b"x" * (LARGE_DOCUMENT_THRESHOLD + 1)
        attachment = MTOMAttachment(large_content, "doc1@example.com")

        # Act & Assert
        assert attachment.is_large_document


# =============================================================================
# MTOMPackage Tests (AC7)
# =============================================================================


class TestMTOMPackage:
    """Tests for MTOMPackage class (6.2-UNIT-024 to 026)."""

    def test_package_generates_unique_boundary(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test MTOMPackage generates unique boundary (6.2-UNIT-024)."""
        # Arrange & Act
        package1 = MTOMPackage(sample_soap_envelope)
        package2 = MTOMPackage(sample_soap_envelope)

        # Assert
        assert package1.boundary != package2.boundary
        assert package1.boundary.startswith("MIMEBoundary_")

    def test_build_returns_bytes_and_content_type(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test build() returns bytes and content-type (6.2-UNIT-025)."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)

        # Act
        message_bytes, content_type = package.build()

        # Assert
        assert isinstance(message_bytes, bytes)
        assert isinstance(content_type, str)

    def test_content_type_is_multipart_related(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test Content-Type is multipart/related (6.2-UNIT-026)."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)

        # Act
        _, content_type = package.build()

        # Assert
        assert content_type.startswith("multipart/related")

    def test_content_type_has_required_params(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test Content-Type has all required parameters."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)

        # Act
        _, content_type = package.build()

        # Assert
        assert "boundary=" in content_type
        assert "type=" in content_type
        assert "start=" in content_type
        assert "start-info=" in content_type

    def test_package_with_attachment(
        self, sample_soap_envelope: bytes, sample_attachment: MTOMAttachment
    ) -> None:
        """Test package with document attachment."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)
        package.add_attachment(sample_attachment)

        # Act
        message_bytes, _ = package.build()

        # Assert
        assert sample_attachment.content_id.encode() in message_bytes
        assert sample_attachment.content in message_bytes

    def test_package_root_content_id(self, sample_soap_envelope: bytes) -> None:
        """Test package has correct root Content-ID."""
        # Arrange
        root_id = "custom-root@example.com"
        package = MTOMPackage(sample_soap_envelope, root_content_id=root_id)

        # Act & Assert
        assert package.root_content_id == root_id


# =============================================================================
# Multiple Documents Tests (AC6)
# =============================================================================


class TestMultipleDocuments:
    """Tests for multiple document support (6.2-UNIT-023)."""

    def test_add_attachments_method(self, sample_soap_envelope: bytes) -> None:
        """Test add_attachments() method adds multiple documents."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)
        attachments = [
            MTOMAttachment(b"doc1", "doc1@example.com"),
            MTOMAttachment(b"doc2", "doc2@example.com"),
            MTOMAttachment(b"doc3", "doc3@example.com"),
        ]

        # Act
        package.add_attachments(attachments)

        # Assert
        assert len(package.attachments) == 3

    def test_multiple_attachments_in_message(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test multiple attachments appear in built message."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)
        package.add_attachment(MTOMAttachment(b"doc1", "doc1@example.com"))
        package.add_attachment(MTOMAttachment(b"doc2", "doc2@example.com"))

        # Act
        message_bytes, _ = package.build()

        # Assert
        assert b"doc1@example.com" in message_bytes
        assert b"doc2@example.com" in message_bytes

    def test_duplicate_content_id_raises_error(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test duplicate Content-ID raises MTOMError."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)
        package.add_attachment(MTOMAttachment(b"doc1", "doc1@example.com"))

        # Act & Assert
        with pytest.raises(MTOMError) as exc_info:
            package.add_attachment(MTOMAttachment(b"doc2", "doc1@example.com"))
        
        assert "Content-ID collision" in str(exc_info.value)

    def test_duplicate_in_batch_raises_error(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test duplicate Content-ID in batch raises MTOMError."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)
        attachments = [
            MTOMAttachment(b"doc1", "doc1@example.com"),
            MTOMAttachment(b"doc2", "doc1@example.com"),  # Duplicate
        ]

        # Act & Assert
        with pytest.raises(MTOMError) as exc_info:
            package.add_attachments(attachments)
        
        assert "Duplicate Content-IDs" in str(exc_info.value)


# =============================================================================
# Validation Tests (AC9)
# =============================================================================


class TestMTOMValidation:
    """Tests for MTOM validation (6.2-UNIT-030 to 032)."""

    def test_validation_success(
        self, soap_with_xop_include: bytes, sample_attachment: MTOMAttachment
    ) -> None:
        """Test validation passes for valid package (6.2-UNIT-030)."""
        # Arrange
        package = MTOMPackage(soap_with_xop_include)
        package.add_attachment(sample_attachment)

        # Act
        is_valid, errors = package.validate()

        # Assert
        assert is_valid
        assert len(errors) == 0

    def test_validation_failure_malformed_xml(
        self, sample_attachment: MTOMAttachment
    ) -> None:
        """Test validation fails for malformed XML (6.2-UNIT-031)."""
        # Arrange
        bad_soap = b"<invalid><xml>"
        package = MTOMPackage(bad_soap)
        package.add_attachment(sample_attachment)

        # Act
        is_valid, errors = package.validate()

        # Assert
        assert not is_valid
        assert any("not well-formed XML" in e for e in errors)

    def test_validation_failure_missing_content_id_at(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test validation fails for Content-ID without @."""
        # Arrange
        bad_attachment = MTOMAttachment(b"test", "invalid-content-id")
        package = MTOMPackage(sample_soap_envelope)
        package._attachments.append(bad_attachment)  # Bypass check

        # Act
        is_valid, errors = package.validate()

        # Assert
        assert not is_valid
        assert any("must contain '@'" in e for e in errors)

    def test_validation_failure_empty_content(
        self, sample_soap_envelope: bytes
    ) -> None:
        """Test validation fails for empty attachment content."""
        # Arrange
        empty_attachment = MTOMAttachment(b"", "doc1@example.com")
        package = MTOMPackage(sample_soap_envelope)
        package._attachments.append(empty_attachment)  # Bypass check

        # Act
        is_valid, errors = package.validate()

        # Assert
        assert not is_valid
        assert any("has no content" in e for e in errors)

    def test_validation_xop_reference_mismatch(
        self, soap_with_xop_include: bytes
    ) -> None:
        """Test validation detects XOP reference mismatch."""
        # Arrange - SOAP references doc1@... but we add different attachment
        different_attachment = MTOMAttachment(b"test", "doc2@example.com")
        package = MTOMPackage(soap_with_xop_include)
        package.add_attachment(different_attachment)

        # Act
        is_valid, errors = package.validate()

        # Assert
        assert not is_valid
        assert any("does not match any attachment" in e for e in errors)


# =============================================================================
# Streaming Tests (AC8)
# =============================================================================


class TestStreamingAttachment:
    """Tests for memory-efficient streaming (6.2-UNIT-033)."""

    def test_from_file_streaming_small_file(self, temp_xml_file: Path) -> None:
        """Test streaming with small file loads directly."""
        # Arrange & Act
        attachment = MTOMAttachment.from_file_streaming(temp_xml_file)

        # Assert
        assert attachment.content == temp_xml_file.read_bytes()
        assert not attachment._is_streaming

        # Cleanup
        temp_xml_file.unlink()

    def test_from_file_streaming_large_file(self, large_temp_file: Path) -> None:
        """Test streaming with large file uses chunked reading (6.2-UNIT-033)."""
        # Arrange & Act
        attachment = MTOMAttachment.from_file_streaming(large_temp_file)

        # Assert
        assert attachment.size_bytes > LARGE_DOCUMENT_THRESHOLD
        assert attachment._is_streaming
        assert attachment.sha256_hash == hashlib.sha256(large_temp_file.read_bytes()).hexdigest()

        # Cleanup
        large_temp_file.unlink()

    def test_from_file_streaming_auto_content_id(self, temp_xml_file: Path) -> None:
        """Test streaming auto-generates Content-ID."""
        # Arrange & Act
        attachment = MTOMAttachment.from_file_streaming(temp_xml_file)

        # Assert
        assert "@ihe-test-util.local" in attachment.content_id

        # Cleanup
        temp_xml_file.unlink()

    def test_from_file_streaming_custom_domain(self, temp_xml_file: Path) -> None:
        """Test streaming with custom domain for Content-ID."""
        # Arrange
        domain = "custom.domain"

        # Act
        attachment = MTOMAttachment.from_file_streaming(
            temp_xml_file, domain=domain
        )

        # Assert
        assert attachment.content_id.endswith(f"@{domain}")

        # Cleanup
        temp_xml_file.unlink()

    def test_from_file_streaming_not_found(self) -> None:
        """Test streaming raises error for missing file."""
        # Arrange
        non_existent_path = Path("/nonexistent/file.xml")

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            MTOMAttachment.from_file_streaming(non_existent_path)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_binary_content_handling(self) -> None:
        """Test handling of binary content."""
        # Arrange
        binary_content = bytes(range(256))  # All byte values

        # Act
        attachment = MTOMAttachment(binary_content, "doc1@example.com")

        # Assert
        assert attachment.content == binary_content
        assert len(attachment.sha256_hash) == 64
        assert attachment.size_bytes == 256

    def test_empty_soap_envelope_validation(self) -> None:
        """Test validation with empty SOAP envelope."""
        # Arrange
        package = MTOMPackage(b"")

        # Act
        is_valid, errors = package.validate()

        # Assert
        assert not is_valid

    def test_unicode_content_handling(self) -> None:
        """Test handling of Unicode content."""
        # Arrange
        unicode_content = "Hello, 世界! 🌍".encode("utf-8")
        attachment = MTOMAttachment(unicode_content, "doc1@example.com")

        # Act
        b64 = attachment.base64_content

        # Assert
        assert base64.b64decode(b64) == unicode_content

    def test_attachments_property_returns_copy(
        self, sample_soap_envelope: bytes, sample_attachment: MTOMAttachment
    ) -> None:
        """Test attachments property returns a copy, not original list."""
        # Arrange
        package = MTOMPackage(sample_soap_envelope)
        package.add_attachment(sample_attachment)

        # Act
        attachments1 = package.attachments
        attachments2 = package.attachments

        # Assert
        assert attachments1 is not attachments2
        assert attachments1 == attachments2
