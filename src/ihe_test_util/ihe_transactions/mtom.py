"""MTOM (MIME-based SOAP attachment) handling for ITI-41 transactions.

This module provides MTOM multipart message construction for XDS.b document
submissions per IHE ITI TF-2b Section 3.41.

Uses manual MTOM construction with email.mime per ADR-001, as zeep's MTOM
support is experimental and not recommended for ITI-41.
"""

import base64
import hashlib
import logging
import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional

from lxml import etree

logger = logging.getLogger(__name__)

# XOP namespace for Include elements
XOP_NS = "http://www.w3.org/2004/08/xop/include"

# Threshold for large document handling (1 MB)
LARGE_DOCUMENT_THRESHOLD = 1024 * 1024  # 1 MB

# Default chunk size for streaming reads
DEFAULT_CHUNK_SIZE = 65536  # 64 KB


class MTOMError(Exception):
    """Error in MTOM packaging or validation."""

    pass


class MTOMAttachment:
    """MTOM attachment with hash and size calculation for SOAP messages.
    
    Represents a document attachment for MTOM transmission with support for
    SHA-256 hash calculation, size tracking, and XOP Include generation.
    
    Attributes:
        content: The attachment content as bytes
        content_id: The Content-ID reference for the attachment
        content_type: The MIME type of the attachment
    
    Example:
        >>> attachment = MTOMAttachment.from_file(Path("ccd.xml"), "doc1@local")
        >>> print(attachment.sha256_hash)  # lowercase hex
        >>> print(attachment.size_bytes)
        >>> print(attachment.base64_content)
    """

    def __init__(
        self,
        content: bytes,
        content_id: str,
        content_type: str = "application/xml"
    ) -> None:
        """Initialize MTOM attachment.
        
        Args:
            content: The attachment content as bytes
            content_id: The Content-ID reference (without angle brackets)
            content_type: The MIME type (default: application/xml)
        """
        self._content = content
        self._content_id = content_id
        self._content_type = content_type
        self._hash: Optional[str] = None
        self._file_path: Optional[Path] = None
        self._is_streaming = False
        logger.debug(f"Created MTOM attachment with Content-ID: {content_id}")

    @property
    def content(self) -> bytes:
        """Get attachment content bytes."""
        return self._content

    @property
    def content_id(self) -> str:
        """Get Content-ID reference."""
        return self._content_id

    @property
    def content_type(self) -> str:
        """Get MIME content type."""
        return self._content_type

    @property
    def sha256_hash(self) -> str:
        """Calculate SHA-256 hash of content (lowercase hex).
        
        Returns:
            64-character lowercase hexadecimal hash string
        
        Example:
            >>> attachment.sha256_hash
            'a948904f2f0f479b8f8564cbf12dac6b9c80fdd0bbeeb...'
        """
        if self._hash is None:
            self._hash = self.calculate_hash()
        return self._hash

    @property
    def size_bytes(self) -> int:
        """Return content size in bytes.
        
        Returns:
            Number of bytes in the content
        """
        return self.calculate_size()

    @property
    def base64_content(self) -> str:
        """Return base64 encoded content.
        
        Returns:
            Base64 encoded string of the content
        """
        return base64.b64encode(self._content).decode("ascii")

    @property
    def is_large_document(self) -> bool:
        """Check if document exceeds large document threshold (1MB).
        
        Returns:
            True if document size exceeds 1MB
        """
        return self.size_bytes > LARGE_DOCUMENT_THRESHOLD

    def calculate_hash(self) -> str:
        """Compute SHA-256 hash of content.
        
        Returns:
            64-character lowercase hexadecimal hash string
        """
        return hashlib.sha256(self._content).hexdigest()

    def calculate_size(self) -> int:
        """Return content byte count.
        
        Returns:
            Number of bytes in the content
        """
        return len(self._content)

    def get_cid_reference(self) -> str:
        """Get the cid: URI reference for use in SOAP metadata.
        
        Returns:
            Content-ID reference in cid: format (e.g., cid:document1@example.com)
        """
        return f"cid:{self._content_id}"

    def get_xop_include(self) -> etree._Element:
        """Create XOP Include element for SOAP metadata.
        
        Creates an xop:Include element with href pointing to this attachment's
        Content-ID, per W3C XOP specification.
        
        Returns:
            lxml Element representing the XOP Include reference
        
        Example:
            >>> xop_elem = attachment.get_xop_include()
            >>> # <xop:Include href="cid:doc1@local" xmlns:xop="..."/>
        """
        xop_include = etree.Element(
            f"{{{XOP_NS}}}Include",
            nsmap={"xop": XOP_NS}
        )
        xop_include.set("href", self.get_cid_reference())
        return xop_include

    @classmethod
    def from_file(
        cls,
        file_path: Path,
        content_id: str,
        content_type: str = "application/xml"
    ) -> "MTOMAttachment":
        """Create MTOM attachment from file.
        
        Args:
            file_path: Path to the file to attach
            content_id: The Content-ID reference
            content_type: The MIME type
            
        Returns:
            MTOMAttachment instance
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(
                f"Attachment file not found: {file_path}. "
                f"Verify the file path exists and is accessible."
            )
        
        content = file_path.read_bytes()
        logger.info(f"Loaded attachment from {file_path} ({len(content)} bytes)")
        
        attachment = cls(content, content_id, content_type)
        attachment._file_path = file_path
        return attachment

    @classmethod
    def from_file_streaming(
        cls,
        file_path: Path,
        content_id: Optional[str] = None,
        content_type: str = "application/xml",
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        domain: str = "ihe-test-util.local"
    ) -> "MTOMAttachment":
        """Create MTOM attachment from file with streaming hash/size calculation.
        
        Calculates hash and size without loading entire file into memory for
        files larger than 1MB. Uses chunked reading for memory efficiency.
        
        Args:
            file_path: Path to the file to attach
            content_id: The Content-ID reference (auto-generated if None)
            content_type: The MIME type
            chunk_size: Size of chunks to read (default: 64KB)
            domain: Domain for auto-generated Content-ID
            
        Returns:
            MTOMAttachment instance with pre-calculated hash and size
            
        Raises:
            FileNotFoundError: If file doesn't exist
        
        Example:
            >>> attachment = MTOMAttachment.from_file_streaming(
            ...     Path("large-document.xml"),
            ...     chunk_size=65536
            ... )
        """
        if not file_path.exists():
            raise FileNotFoundError(
                f"Attachment file not found: {file_path}. "
                f"Verify the file path exists and is accessible."
            )
        
        # Generate Content-ID if not provided
        if content_id is None:
            content_id = generate_content_id(domain)
        
        # Calculate hash and size using streaming for large files
        file_size = file_path.stat().st_size
        
        if file_size > LARGE_DOCUMENT_THRESHOLD:
            # Stream the file for hash calculation
            hash_obj = hashlib.sha256()
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hash_obj.update(chunk)
            pre_calculated_hash = hash_obj.hexdigest()
            
            logger.info(
                f"Streaming large file ({file_size} bytes): {file_path}. "
                f"Hash calculated without full memory load."
            )
            
            # For large files, still need to load content for transmission
            # but we've pre-calculated the hash efficiently
            content = file_path.read_bytes()
        else:
            # For smaller files, load directly
            content = file_path.read_bytes()
            pre_calculated_hash = hashlib.sha256(content).hexdigest()
        
        logger.info(f"Loaded attachment from {file_path} ({len(content)} bytes)")
        
        attachment = cls(content, content_id, content_type)
        attachment._hash = pre_calculated_hash
        attachment._file_path = file_path
        attachment._is_streaming = file_size > LARGE_DOCUMENT_THRESHOLD
        return attachment


def generate_content_id(domain: str = "ihe-test-util.local") -> str:
    """Generate unique Content-ID for MTOM attachment.
    
    Generates a Content-ID in the format {uuid}@{domain} to ensure
    uniqueness across all attachments.
    
    Args:
        domain: Domain suffix for the Content-ID (default: ihe-test-util.local)
        
    Returns:
        Content-ID string in format {uuid}@{domain}
    
    Example:
        >>> content_id = generate_content_id()
        >>> # 'a1b2c3d4-e5f6-7890-abcd-ef1234567890@ihe-test-util.local'
    """
    unique_id = str(uuid.uuid4())
    return f"{unique_id}@{domain}"


class MTOMPackage:
    """Builds MTOM multipart/related message for ITI-41 submissions.
    
    Constructs a MIME multipart message with SOAP envelope as the root part
    and document attachments as additional parts, per W3C XOP specification.
    
    Example:
        >>> package = MTOMPackage(soap_envelope_bytes)
        >>> package.add_attachment(attachment)
        >>> message_bytes, content_type = package.build()
        >>> response = requests.post(url, data=message_bytes, headers={'Content-Type': content_type})
    
    Attributes:
        root_content_id: Content-ID of the SOAP envelope root part
    """

    def __init__(
        self,
        soap_envelope: bytes,
        content_type: str = "application/xop+xml",
        root_content_id: str = "root@ihe-test-util.local"
    ) -> None:
        """Initialize MTOM package with SOAP envelope.
        
        Args:
            soap_envelope: SOAP envelope XML as bytes
            content_type: Content type of root part (default: application/xop+xml)
            root_content_id: Content-ID for the root SOAP part
        """
        self._soap_envelope = soap_envelope
        self._content_type = content_type
        self._root_content_id = root_content_id
        self._attachments: list[MTOMAttachment] = []
        self._boundary = f"MIMEBoundary_{uuid.uuid4().hex}"
        
        logger.debug(f"Created MTOM package with boundary: {self._boundary}")

    @property
    def root_content_id(self) -> str:
        """Get the Content-ID of the SOAP envelope root part."""
        return self._root_content_id

    @property
    def boundary(self) -> str:
        """Get the MIME boundary string."""
        return self._boundary

    @property
    def attachments(self) -> list[MTOMAttachment]:
        """Get list of attachments."""
        return list(self._attachments)

    def add_attachment(self, attachment: MTOMAttachment) -> None:
        """Add document attachment to package.
        
        Args:
            attachment: MTOM attachment to add
            
        Raises:
            MTOMError: If Content-ID already exists in package
        """
        # Check for duplicate Content-IDs
        existing_ids = {a.content_id for a in self._attachments}
        if attachment.content_id in existing_ids:
            raise MTOMError(
                f"Content-ID collision: '{attachment.content_id}' already exists. "
                f"Use unique Content-IDs for each attachment. "
                f"Existing IDs: {existing_ids}"
            )
        
        self._attachments.append(attachment)
        logger.debug(
            f"Added attachment: {attachment.content_id} "
            f"({attachment.size_bytes} bytes)"
        )

    def add_attachments(self, attachments: list[MTOMAttachment]) -> None:
        """Add multiple document attachments to package.
        
        Args:
            attachments: List of MTOM attachments to add
            
        Raises:
            MTOMError: If any Content-ID already exists or duplicates in list
        """
        # Check for duplicates within the list being added
        new_ids = [a.content_id for a in attachments]
        if len(new_ids) != len(set(new_ids)):
            duplicates = [cid for cid in new_ids if new_ids.count(cid) > 1]
            raise MTOMError(
                f"Duplicate Content-IDs in attachments list: {set(duplicates)}. "
                f"Each attachment must have a unique Content-ID."
            )
        
        for attachment in attachments:
            self.add_attachment(attachment)

    def build(self) -> tuple[bytes, str]:
        """Build complete MTOM multipart message.
        
        Constructs the MIME multipart/related message with:
        - Root part: SOAP envelope with XOP Include references
        - Additional parts: Document attachments
        
        Returns:
            Tuple of (message_bytes, content_type_header)
            - message_bytes: Complete MTOM message as bytes
            - content_type_header: Content-Type header value with boundary
        
        Example:
            >>> message_bytes, content_type = package.build()
            >>> headers = {'Content-Type': content_type}
        """
        # Create multipart message
        multipart = MIMEMultipart(
            "related",
            boundary=self._boundary,
            type="application/xop+xml",
            start=f"<{self._root_content_id}>",
            start_info="application/soap+xml"
        )
        
        # Add SOAP envelope as root part
        soap_part = MIMEApplication(
            self._soap_envelope,
            "xop+xml",
            _encoder=lambda x: x  # No encoding, use raw bytes
        )
        soap_part.set_param("charset", "utf-8")
        soap_part.set_param("type", "application/soap+xml")
        soap_part.add_header("Content-ID", f"<{self._root_content_id}>")
        # Remove default Content-Transfer-Encoding
        del soap_part["Content-Transfer-Encoding"]
        multipart.attach(soap_part)
        
        # Add document attachments
        for attachment in self._attachments:
            doc_part = MIMEApplication(
                attachment.content,
                attachment.content_type.split("/")[-1] if "/" in attachment.content_type else "xml",
                _encoder=lambda x: x  # No encoding, use raw bytes
            )
            doc_part.add_header("Content-ID", f"<{attachment.content_id}>")
            doc_part.add_header("Content-Transfer-Encoding", "binary")
            multipart.attach(doc_part)
        
        # Build message
        message_str = multipart.as_string()
        message_bytes = message_str.encode("utf-8", errors="surrogateescape")
        
        # Build Content-Type header
        content_type_header = (
            f"multipart/related; "
            f'boundary="{self._boundary}"; '
            f'type="application/xop+xml"; '
            f'start="<{self._root_content_id}>"; '
            f'start-info="application/soap+xml"'
        )
        
        logger.info(
            f"Built MTOM package: {len(self._attachments)} attachment(s), "
            f"{len(message_bytes)} total bytes"
        )
        
        return message_bytes, content_type_header

    def validate(self) -> tuple[bool, list[str]]:
        """Validate MTOM package structure before transmission.
        
        Performs validation checks including:
        - SOAP envelope is well-formed XML
        - All attachments have content
        - Content-ID format is valid (contains @)
        - No duplicate Content-IDs
        - XOP Include references match attachment Content-IDs
        
        Returns:
            Tuple of (is_valid, error_list)
            - is_valid: True if validation passes
            - error_list: List of validation error messages
        
        Example:
            >>> is_valid, errors = package.validate()
            >>> if not is_valid:
            ...     for error in errors:
            ...         logger.error(error)
        """
        errors: list[str] = []
        
        # Validate SOAP envelope is well-formed XML
        try:
            etree.fromstring(self._soap_envelope)
        except etree.XMLSyntaxError as e:
            errors.append(
                f"SOAP envelope is not well-formed XML: {e}. "
                f"Verify the envelope is valid XML before packaging."
            )
        
        # Validate all attachments have content
        for attachment in self._attachments:
            if not attachment.content:
                errors.append(
                    f"Attachment '{attachment.content_id}' has no content. "
                    f"Each attachment must have non-empty content."
                )
        
        # Validate Content-ID format (must contain @)
        all_content_ids = [self._root_content_id] + [a.content_id for a in self._attachments]
        for content_id in all_content_ids:
            if "@" not in content_id:
                errors.append(
                    f"Invalid Content-ID format: '{content_id}'. "
                    f"Content-ID must contain '@' symbol (e.g., 'doc1@example.com')."
                )
        
        # Validate no duplicate Content-IDs (including root)
        if len(all_content_ids) != len(set(all_content_ids)):
            duplicates = [cid for cid in all_content_ids if all_content_ids.count(cid) > 1]
            errors.append(
                f"Duplicate Content-IDs detected: {set(duplicates)}. "
                f"Each part must have a unique Content-ID."
            )
        
        # Validate XOP Include references match attachment Content-IDs
        try:
            soap_tree = etree.fromstring(self._soap_envelope)
            xop_includes = soap_tree.findall(f".//{{{XOP_NS}}}Include")
            attachment_cids = {a.content_id for a in self._attachments}
            
            for xop_include in xop_includes:
                href = xop_include.get("href", "")
                if href.startswith("cid:"):
                    ref_content_id = href[4:]  # Remove "cid:" prefix
                    if ref_content_id not in attachment_cids:
                        errors.append(
                            f"XOP Include reference '{href}' does not match any attachment. "
                            f"Available Content-IDs: {attachment_cids}"
                        )
        except etree.XMLSyntaxError:
            # Already reported above
            pass
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.debug("MTOM package validation passed")
        else:
            logger.warning(f"MTOM package validation failed with {len(errors)} error(s)")
        
        return is_valid, errors
