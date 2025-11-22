"""XDSb metadata configuration model using pydantic.

This module defines configuration for XDSb metadata construction including
classification codes, author information, and OID settings.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ClassificationCode(BaseModel):
    """A single classification code with its coding scheme.
    
    Attributes:
        code: The code value (e.g., "34133-9")
        display_name: Human-readable display name
        coding_scheme: OID of the coding scheme (e.g., "2.16.840.1.113883.6.1" for LOINC)
    """
    
    code: str
    display_name: str
    coding_scheme: str


class AuthorConfig(BaseModel):
    """Author information for XDSb metadata.
    
    Attributes:
        person_id: Author person identifier
        person_family_name: Author family name
        person_given_name: Author given name
        person_prefix: Author name prefix (e.g., "Dr.")
        person_oid: OID for author person identifier domain
        institution_name: Organization name
        institution_oid: OID for organization
        role: Author role (e.g., "Author", "Provider")
    """
    
    person_id: str = Field(default="", description="Author person identifier")
    person_family_name: str = Field(default="", description="Author family name")
    person_given_name: str = Field(default="", description="Author given name")
    person_prefix: str = Field(default="", description="Author name prefix")
    person_oid: str = Field(
        default="2.16.840.1.113883.4.6",
        description="OID for author person identifier domain"
    )
    institution_name: str = Field(
        default="Healthcare Organization",
        description="Organization name"
    )
    institution_oid: str = Field(
        default="2.16.840.1.113883.3.72.5.1",
        description="OID for organization"
    )
    role: str = Field(default="Author", description="Author role")


class XDSbConfig(BaseModel):
    """Configuration for XDSb metadata construction.
    
    Attributes:
        source_id: Source facility OID
        repository_unique_id: Repository unique identifier OID
        id_scheme: ID generation scheme ('uuid' or 'oid')
        root_oid: Root OID for OID-based ID generation
        language_code: Document language code (default: en-US)
        author: Author configuration
        class_code: Document class classification code
        type_code: Document type classification code
        format_code: Document format classification code
        confidentiality_code: Document confidentiality classification code
        healthcare_facility_type_code: Healthcare facility type classification code
        practice_setting_code: Practice setting classification code
        content_type_code: Submission set content type classification code
        
    Example:
        >>> config = XDSbConfig()
        >>> config.class_code.code
        '34133-9'
    """
    
    # Source and repository identifiers
    source_id: str = Field(
        default="2.16.840.1.113883.3.72.5.1",
        description="Source facility OID"
    )
    repository_unique_id: str = Field(
        default="2.16.840.1.113883.3.72.5.9.3",
        description="Repository unique identifier OID"
    )
    
    # ID generation settings
    id_scheme: str = Field(
        default="uuid",
        description="ID generation scheme: 'uuid' or 'oid'"
    )
    root_oid: str = Field(
        default="2.16.840.1.113883.3.72.5.9.1",
        description="Root OID for OID-based ID generation"
    )
    
    # Document settings
    language_code: str = Field(
        default="en-US",
        description="Document language code"
    )
    
    # Author configuration
    author: AuthorConfig = Field(default_factory=AuthorConfig)
    
    # Classification codes with defaults for CCD documents
    class_code: ClassificationCode = Field(
        default_factory=lambda: ClassificationCode(
            code="34133-9",
            display_name="Summarization of Episode Note",
            coding_scheme="2.16.840.1.113883.6.1"
        ),
        description="Document class code (LOINC)"
    )
    
    type_code: ClassificationCode = Field(
        default_factory=lambda: ClassificationCode(
            code="34133-9",
            display_name="Summarization of Episode Note",
            coding_scheme="2.16.840.1.113883.6.1"
        ),
        description="Document type code (LOINC)"
    )
    
    format_code: ClassificationCode = Field(
        default_factory=lambda: ClassificationCode(
            code="urn:ihe:pcc:xds-ms:2007",
            display_name="Medical Summary",
            coding_scheme="1.3.6.1.4.1.19376.1.2.3"
        ),
        description="Document format code"
    )
    
    confidentiality_code: ClassificationCode = Field(
        default_factory=lambda: ClassificationCode(
            code="N",
            display_name="Normal",
            coding_scheme="2.16.840.1.113883.5.25"
        ),
        description="Document confidentiality code"
    )
    
    healthcare_facility_type_code: ClassificationCode = Field(
        default_factory=lambda: ClassificationCode(
            code="OF",
            display_name="Outpatient Facility",
            coding_scheme="2.16.840.1.113883.5.11"
        ),
        description="Healthcare facility type code"
    )
    
    practice_setting_code: ClassificationCode = Field(
        default_factory=lambda: ClassificationCode(
            code="394802001",
            display_name="General Medicine",
            coding_scheme="2.16.840.1.113883.6.96"
        ),
        description="Practice setting code (SNOMED CT)"
    )
    
    content_type_code: ClassificationCode = Field(
        default_factory=lambda: ClassificationCode(
            code="34133-9",
            display_name="Clinical Document",
            coding_scheme="2.16.840.1.113883.6.1"
        ),
        description="Submission set content type code"
    )


def get_default_xdsb_config() -> XDSbConfig:
    """Get default XDSb configuration.
    
    Returns:
        XDSbConfig instance with default values for CCD documents.
    """
    return XDSbConfig()
