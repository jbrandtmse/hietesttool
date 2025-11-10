"""CCD Document model for personalized clinical documents."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CCDDocument:
    """Represents a personalized HL7 CCD document.
    
    Attributes:
        document_id: Unique identifier (UUID4)
        patient_id: Reference to PatientDemographics
        template_path: Path to template file used for personalization
        xml_content: Personalized XML document content
        creation_timestamp: UTC timestamp when document was created
        mime_type: MIME type of document (default: text/xml)
        size_bytes: Size of XML content in bytes
        sha256_hash: SHA256 hash of XML content for integrity verification
    """
    
    document_id: str
    patient_id: str
    template_path: str
    xml_content: str
    creation_timestamp: datetime
    mime_type: str = "text/xml"
    size_bytes: int = 0
    sha256_hash: str = ""
    
    def __post_init__(self) -> None:
        """Calculate size and hash if not provided."""
        if self.size_bytes == 0:
            self.size_bytes = len(self.xml_content.encode('utf-8'))
        if self.sha256_hash == "":
            self.sha256_hash = hashlib.sha256(
                self.xml_content.encode('utf-8')
            ).hexdigest()
    
    def to_file(self, output_path: Path) -> None:
        """Save CCD document to file.
        
        Args:
            output_path: Path where XML should be saved
            
        Raises:
            IOError: If file cannot be written
        """
        output_path.write_text(self.xml_content, encoding='utf-8')
