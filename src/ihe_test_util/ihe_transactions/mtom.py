"""MTOM (MIME-based SOAP attachment) handling for ITI-41 transactions."""

import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MTOMAttachment:
    """Represents an MTOM attachment for SOAP messages.
    
    Attributes:
        content: The attachment content as bytes
        content_id: The Content-ID reference for the attachment
        content_type: The MIME type of the attachment
    """

    def __init__(
        self,
        content: bytes,
        content_id: str,
        content_type: str = "application/xml"
    ):
        """Initialize MTOM attachment.
        
        Args:
            content: The attachment content as bytes
            content_id: The Content-ID reference (without angle brackets)
            content_type: The MIME type (default: application/xml)
        """
        self.content = content
        self.content_id = content_id
        self.content_type = content_type
        logger.debug(f"Created MTOM attachment with Content-ID: {content_id}")

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
            raise FileNotFoundError(f"Attachment file not found: {file_path}")
        
        content = file_path.read_bytes()
        logger.info(f"Loaded attachment from {file_path} ({len(content)} bytes)")
        return cls(content, content_id, content_type)

    def get_cid_reference(self) -> str:
        """Get the cid: URI reference for use in SOAP metadata.
        
        Returns:
            Content-ID reference in cid: format (e.g., cid:document1@example.com)
        """
        return f"cid:{self.content_id}"
