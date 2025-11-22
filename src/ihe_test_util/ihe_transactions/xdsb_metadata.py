"""XDSb metadata builder for ITI-41 document submissions.

This module provides XDSb metadata construction per IHE ITI TF-3 Section 4.2.
Builds ProvideAndRegisterDocumentSetRequest with SubmissionSet, DocumentEntry,
and Association elements.
"""

import hashlib
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from lxml import etree

from ihe_test_util.config.xdsb_config import XDSbConfig, get_default_xdsb_config
from ihe_test_util.models.ccd import CCDDocument

logger = logging.getLogger(__name__)

# XDSb namespaces per IHE ITI TF-3
XDS_NS = "urn:ihe:iti:xds-b:2007"
RIM_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
RS_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"
LCM_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0"

NSMAP = {
    "xds": XDS_NS,
    "rim": RIM_NS,
    "rs": RS_NS,
    "lcm": LCM_NS,
}

# Classification Scheme UUIDs per IHE ITI TF-3
CLASS_CODE_SCHEME = "urn:uuid:41a5887f-8865-4c09-adf7-e362475b143a"
TYPE_CODE_SCHEME = "urn:uuid:f0306f51-975f-434e-a61c-c59651d33983"
FORMAT_CODE_SCHEME = "urn:uuid:a09d5840-386c-46f2-b5ad-9c3699a4309d"
CONFIDENTIALITY_CODE_SCHEME = "urn:uuid:f4f85eac-e6cb-4883-b524-f2705394840f"
HEALTHCARE_FACILITY_TYPE_CODE_SCHEME = "urn:uuid:f33fb8ac-18af-42cc-ae0e-ed0b0bdb91e1"
PRACTICE_SETTING_CODE_SCHEME = "urn:uuid:cccf5598-8b07-4b77-a05e-ae952c785ead"
CONTENT_TYPE_CODE_SCHEME = "urn:uuid:aa543740-bdda-424e-8c96-df4873be8500"

# External Identifier UUIDs per IHE ITI TF-3
DOC_ENTRY_UNIQUE_ID_SCHEME = "urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab"
DOC_ENTRY_PATIENT_ID_SCHEME = "urn:uuid:58a6f841-87b3-4a3e-92fd-a8ffeff98427"
SUBMISSION_SET_UNIQUE_ID_SCHEME = "urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8"
SUBMISSION_SET_SOURCE_ID_SCHEME = "urn:uuid:554ac39e-e3fe-47fe-b233-965d2a147832"
SUBMISSION_SET_PATIENT_ID_SCHEME = "urn:uuid:6b5aea1a-874d-4603-a4bc-96a0a7b38446"

# Object Types per IHE ITI TF-3
DOCUMENT_ENTRY_OBJECT_TYPE = "urn:uuid:7edca82f-054d-47f2-a032-9b2a5b5186c1"
SUBMISSION_SET_OBJECT_TYPE = "urn:uuid:a54d6aa5-d40d-43f9-88c5-b4633d873bdd"

# OID validation pattern
OID_PATTERN = re.compile(r"^[0-2](\.[1-9][0-9]*)*$")


class MetadataError(Exception):
    """Error in XDSb metadata construction."""

    pass


class XDSbMetadataBuilder:
    """Builds XDSb metadata for ITI-41 document submissions.
    
    Constructs ProvideAndRegisterDocumentSetRequest with SubmissionSet,
    DocumentEntry, and Association elements per IHE ITI TF-3 Section 4.2.
    
    Example:
        >>> config = get_default_xdsb_config()
        >>> builder = XDSbMetadataBuilder(config)
        >>> builder.set_patient_identifier("PAT123", "2.16.840.1.113883.3.72.5.9.1")
        >>> builder.set_document(ccd_document)
        >>> metadata_xml = builder.build()
    
    Attributes:
        submission_set_id: Generated ID for the submission set
        document_entry_id: Generated ID for the document entry
    """

    def __init__(self, config: Optional[XDSbConfig] = None) -> None:
        """Initialize builder with XDSb configuration.
        
        Args:
            config: XDSb configuration. Uses defaults if None.
        """
        self._config = config or get_default_xdsb_config()
        self._patient_id: Optional[str] = None
        self._patient_id_oid: Optional[str] = None
        self._document: Optional[CCDDocument] = None
        self._custom_slots: list[tuple[str, list[str]]] = []
        self._oid_sequence = 0
        
        # Generated IDs (populated on build)
        self.submission_set_id: str = ""
        self.document_entry_id: str = ""

    def set_patient_identifier(self, patient_id: str, patient_id_oid: str) -> "XDSbMetadataBuilder":
        """Set patient identifier for metadata.
        
        Args:
            patient_id: Patient identifier value
            patient_id_oid: Patient identifier OID domain
            
        Returns:
            Self for method chaining
            
        Raises:
            MetadataError: If OID format is invalid
        """
        if not self._validate_oid(patient_id_oid):
            raise MetadataError(
                f"Invalid OID format: {patient_id_oid}. "
                f"OID must match pattern: 2.16.840... (numeric segments separated by dots)"
            )
        self._patient_id = patient_id
        self._patient_id_oid = patient_id_oid
        return self

    def set_document(self, document: CCDDocument) -> "XDSbMetadataBuilder":
        """Set CCD document for metadata generation.
        
        Args:
            document: CCD document with content, hash, and size
            
        Returns:
            Self for method chaining
        """
        self._document = document
        return self

    def add_slot(self, name: str, values: list[str]) -> "XDSbMetadataBuilder":
        """Add custom slot element.
        
        Args:
            name: Slot name
            values: List of slot values
            
        Returns:
            Self for method chaining
        """
        self._custom_slots.append((name, values))
        return self

    def build(self) -> etree._Element:
        """Build complete ProvideAndRegisterDocumentSetRequest.
        
        Returns:
            lxml Element containing the complete XDSb metadata
            
        Raises:
            MetadataError: If required data (document, patient ID) not set
        """
        if self._document is None:
            raise MetadataError(
                "Document not set. Call set_document() before build(). "
                "Example: builder.set_document(ccd_document)"
            )
        
        if self._patient_id is None or self._patient_id_oid is None:
            raise MetadataError(
                "Patient identifier not set. Call set_patient_identifier() before build(). "
                "Example: builder.set_patient_identifier('PAT123', '2.16.840.1.113883.3.72.5.9.1')"
            )
        
        # Generate unique IDs
        self.submission_set_id = self._generate_id("SubmissionSet")
        self.document_entry_id = self._generate_id("DocumentEntry")
        
        logger.debug(
            f"Building XDSb metadata: submission_set_id={self.submission_set_id}, "
            f"document_entry_id={self.document_entry_id}"
        )
        
        # Build root element
        root = etree.Element(
            f"{{{XDS_NS}}}ProvideAndRegisterDocumentSetRequest",
            nsmap=NSMAP
        )
        
        # Build SubmitObjectsRequest
        submit_request = etree.SubElement(
            root,
            f"{{{LCM_NS}}}SubmitObjectsRequest"
        )
        
        # Build RegistryObjectList
        registry_list = etree.SubElement(
            submit_request,
            f"{{{RIM_NS}}}RegistryObjectList"
        )
        
        # Build components
        self._build_document_entry(registry_list)
        self._build_submission_set(registry_list)
        self._build_association(registry_list)
        
        logger.info(
            f"Built XDSb metadata for patient {self._patient_id} "
            f"with document {self._document.document_id}"
        )
        
        return root

    def build_xml_string(self, pretty_print: bool = True) -> str:
        """Build and return metadata as XML string.
        
        Args:
            pretty_print: Whether to format with indentation
            
        Returns:
            XML string of the metadata
        """
        root = self.build()
        return etree.tostring(
            root,
            pretty_print=pretty_print,
            xml_declaration=False,
            encoding="unicode"
        )

    def _build_document_entry(self, registry_list: etree._Element) -> None:
        """Build ExtrinsicObject (DocumentEntry) element.
        
        Args:
            registry_list: Parent RegistryObjectList element
        """
        doc = self._document
        assert doc is not None
        
        # Create ExtrinsicObject
        extrinsic = etree.SubElement(
            registry_list,
            f"{{{RIM_NS}}}ExtrinsicObject",
            id=self.document_entry_id,
            mimeType=doc.mime_type,
            objectType=DOCUMENT_ENTRY_OBJECT_TYPE
        )
        
        # Add slots
        self._add_slot(extrinsic, "creationTime", [self._format_hl7_timestamp(doc.creation_timestamp)])
        self._add_slot(extrinsic, "hash", [doc.sha256_hash.lower()])
        self._add_slot(extrinsic, "size", [str(doc.size_bytes)])
        self._add_slot(extrinsic, "languageCode", [self._config.language_code])
        self._add_slot(extrinsic, "repositoryUniqueId", [self._config.repository_unique_id])
        
        # Add name
        name_elem = etree.SubElement(extrinsic, f"{{{RIM_NS}}}Name")
        etree.SubElement(
            name_elem,
            f"{{{RIM_NS}}}LocalizedString",
            value="Clinical Document"
        )
        
        # Add classifications
        self._add_classification(
            registry_list,
            self.document_entry_id,
            CLASS_CODE_SCHEME,
            self._config.class_code.code,
            self._config.class_code.display_name,
            self._config.class_code.coding_scheme
        )
        self._add_classification(
            registry_list,
            self.document_entry_id,
            TYPE_CODE_SCHEME,
            self._config.type_code.code,
            self._config.type_code.display_name,
            self._config.type_code.coding_scheme
        )
        self._add_classification(
            registry_list,
            self.document_entry_id,
            FORMAT_CODE_SCHEME,
            self._config.format_code.code,
            self._config.format_code.display_name,
            self._config.format_code.coding_scheme
        )
        self._add_classification(
            registry_list,
            self.document_entry_id,
            CONFIDENTIALITY_CODE_SCHEME,
            self._config.confidentiality_code.code,
            self._config.confidentiality_code.display_name,
            self._config.confidentiality_code.coding_scheme
        )
        self._add_classification(
            registry_list,
            self.document_entry_id,
            HEALTHCARE_FACILITY_TYPE_CODE_SCHEME,
            self._config.healthcare_facility_type_code.code,
            self._config.healthcare_facility_type_code.display_name,
            self._config.healthcare_facility_type_code.coding_scheme
        )
        self._add_classification(
            registry_list,
            self.document_entry_id,
            PRACTICE_SETTING_CODE_SCHEME,
            self._config.practice_setting_code.code,
            self._config.practice_setting_code.display_name,
            self._config.practice_setting_code.coding_scheme
        )
        
        # Add author
        self._add_author_classification(registry_list, self.document_entry_id)
        
        # Add external identifiers
        self._add_external_identifier(
            registry_list,
            self.document_entry_id,
            DOC_ENTRY_UNIQUE_ID_SCHEME,
            self._generate_unique_id(),
            "XDSDocumentEntry.uniqueId"
        )
        self._add_external_identifier(
            registry_list,
            self.document_entry_id,
            DOC_ENTRY_PATIENT_ID_SCHEME,
            self._format_patient_id(),
            "XDSDocumentEntry.patientId"
        )

    def _build_submission_set(self, registry_list: etree._Element) -> None:
        """Build RegistryPackage (SubmissionSet) element.
        
        Args:
            registry_list: Parent RegistryObjectList element
        """
        # Create RegistryPackage
        registry_package = etree.SubElement(
            registry_list,
            f"{{{RIM_NS}}}RegistryPackage",
            id=self.submission_set_id,
            objectType=SUBMISSION_SET_OBJECT_TYPE
        )
        
        # Add slots
        self._add_slot(registry_package, "submissionTime", [self._format_hl7_timestamp(datetime.now(timezone.utc))])
        
        # Add name
        name_elem = etree.SubElement(registry_package, f"{{{RIM_NS}}}Name")
        etree.SubElement(
            name_elem,
            f"{{{RIM_NS}}}LocalizedString",
            value="Submission Set"
        )
        
        # Add content type classification
        self._add_classification(
            registry_list,
            self.submission_set_id,
            CONTENT_TYPE_CODE_SCHEME,
            self._config.content_type_code.code,
            self._config.content_type_code.display_name,
            self._config.content_type_code.coding_scheme
        )
        
        # Add author
        self._add_author_classification(registry_list, self.submission_set_id)
        
        # Add external identifiers
        self._add_external_identifier(
            registry_list,
            self.submission_set_id,
            SUBMISSION_SET_UNIQUE_ID_SCHEME,
            self._generate_unique_id(),
            "XDSSubmissionSet.uniqueId"
        )
        self._add_external_identifier(
            registry_list,
            self.submission_set_id,
            SUBMISSION_SET_SOURCE_ID_SCHEME,
            self._config.source_id,
            "XDSSubmissionSet.sourceId"
        )
        self._add_external_identifier(
            registry_list,
            self.submission_set_id,
            SUBMISSION_SET_PATIENT_ID_SCHEME,
            self._format_patient_id(),
            "XDSSubmissionSet.patientId"
        )

    def _build_association(self, registry_list: etree._Element) -> None:
        """Build Association element linking submission set to document.
        
        Args:
            registry_list: Parent RegistryObjectList element
        """
        association_id = self._generate_id("Association")
        
        association = etree.SubElement(
            registry_list,
            f"{{{RIM_NS}}}Association",
            id=association_id,
            associationType="urn:oasis:names:tc:ebxml-regrep:AssociationType:HasMember",
            sourceObject=self.submission_set_id,
            targetObject=self.document_entry_id
        )
        
        self._add_slot(association, "SubmissionSetStatus", ["Original"])

    def _add_slot(self, parent: etree._Element, name: str, values: list[str]) -> None:
        """Add Slot element to parent.
        
        Args:
            parent: Parent element
            name: Slot name
            values: List of values
        """
        slot = etree.SubElement(parent, f"{{{RIM_NS}}}Slot", name=name)
        value_list = etree.SubElement(slot, f"{{{RIM_NS}}}ValueList")
        for val in values:
            value_elem = etree.SubElement(value_list, f"{{{RIM_NS}}}Value")
            value_elem.text = val

    def _add_classification(
        self,
        registry_list: etree._Element,
        classified_object: str,
        scheme: str,
        code: str,
        display_name: str,
        coding_scheme: str
    ) -> None:
        """Add Classification element.
        
        Args:
            registry_list: Parent RegistryObjectList
            classified_object: ID of object being classified
            scheme: Classification scheme UUID
            code: Code value
            display_name: Human-readable display name
            coding_scheme: OID of the coding scheme
        """
        classification = etree.SubElement(
            registry_list,
            f"{{{RIM_NS}}}Classification",
            id=f"cl-{uuid.uuid4()}",
            classificationScheme=scheme,
            classifiedObject=classified_object,
            nodeRepresentation=code
        )
        
        self._add_slot(classification, "codingScheme", [coding_scheme])
        
        name_elem = etree.SubElement(classification, f"{{{RIM_NS}}}Name")
        etree.SubElement(
            name_elem,
            f"{{{RIM_NS}}}LocalizedString",
            value=display_name
        )

    def _add_author_classification(
        self,
        registry_list: etree._Element,
        classified_object: str
    ) -> None:
        """Add author classification with slots.
        
        Args:
            registry_list: Parent RegistryObjectList
            classified_object: ID of object being classified
        """
        author = self._config.author
        
        classification = etree.SubElement(
            registry_list,
            f"{{{RIM_NS}}}Classification",
            id=f"cl-{uuid.uuid4()}",
            classificationScheme="urn:uuid:93606bcf-9494-43ec-9b4e-a7748d1a838d",
            classifiedObject=classified_object,
            nodeRepresentation=""
        )
        
        # Add authorPerson slot (XCN format)
        author_person = self._format_author_person()
        if author_person:
            self._add_slot(classification, "authorPerson", [author_person])
        
        # Add authorInstitution slot (XON format)
        author_institution = self._format_author_institution()
        if author_institution:
            self._add_slot(classification, "authorInstitution", [author_institution])
        
        # Add authorRole slot
        if author.role:
            self._add_slot(classification, "authorRole", [author.role])

    def _add_external_identifier(
        self,
        registry_list: etree._Element,
        registry_object: str,
        scheme: str,
        value: str,
        name: str
    ) -> None:
        """Add ExternalIdentifier element.
        
        Args:
            registry_list: Parent RegistryObjectList
            registry_object: ID of registry object
            scheme: Identification scheme UUID
            value: Identifier value
            name: Human-readable name
        """
        ext_id = etree.SubElement(
            registry_list,
            f"{{{RIM_NS}}}ExternalIdentifier",
            id=f"ei-{uuid.uuid4()}",
            registryObject=registry_object,
            identificationScheme=scheme,
            value=value
        )
        
        name_elem = etree.SubElement(ext_id, f"{{{RIM_NS}}}Name")
        etree.SubElement(
            name_elem,
            f"{{{RIM_NS}}}LocalizedString",
            value=name
        )

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID for metadata element.
        
        Args:
            prefix: Prefix for the ID (e.g., 'DocumentEntry', 'SubmissionSet')
            
        Returns:
            Unique ID string
        """
        if self._config.id_scheme == "uuid":
            return f"urn:uuid:{uuid.uuid4()}"
        else:
            return self._generate_oid_based_id(prefix)

    def _generate_unique_id(self) -> str:
        """Generate unique ID for external identifiers.
        
        Returns:
            Unique ID in OID format for external identifiers
        """
        if self._config.id_scheme == "uuid":
            return f"urn:uuid:{uuid.uuid4()}"
        else:
            self._oid_sequence += 1
            timestamp = int(time.time() * 1000)
            return f"{self._config.root_oid}.{timestamp}.{self._oid_sequence}"

    def _generate_oid_based_id(self, prefix: str) -> str:
        """Generate OID-based unique ID.
        
        Args:
            prefix: Prefix for logging/debugging
            
        Returns:
            OID-based unique ID
        """
        self._oid_sequence += 1
        timestamp = int(time.time() * 1000)
        return f"{self._config.root_oid}.{timestamp}.{self._oid_sequence}"

    def _format_patient_id(self) -> str:
        """Format patient ID in CX format.
        
        Returns:
            Patient ID in format: {id}^^^&{oid}&ISO
        """
        return f"{self._patient_id}^^^&{self._patient_id_oid}&ISO"

    def _format_author_person(self) -> str:
        """Format author person in XCN format.
        
        Returns:
            Author person in XCN format or empty string if not configured
        """
        author = self._config.author
        if not author.person_id and not author.person_family_name:
            return ""
        
        # XCN format: {id}^{family}^{given}^^^{prefix}^^^&{oid}&ISO
        return (
            f"{author.person_id}^{author.person_family_name}^{author.person_given_name}"
            f"^^^{author.person_prefix}^^^&{author.person_oid}&ISO"
        )

    def _format_author_institution(self) -> str:
        """Format author institution in XON format.
        
        Returns:
            Author institution in XON format or empty string if not configured
        """
        author = self._config.author
        if not author.institution_name:
            return ""
        
        # XON format: {name}^^^&{oid}&ISO
        return f"{author.institution_name}^^^&{author.institution_oid}&ISO"

    @staticmethod
    def _format_hl7_timestamp(dt: datetime) -> str:
        """Format datetime as HL7 DTM timestamp.
        
        Args:
            dt: Datetime to format
            
        Returns:
            Timestamp in YYYYMMDDHHMMSS format
        """
        return dt.strftime("%Y%m%d%H%M%S")

    @staticmethod
    def _validate_oid(oid: str) -> bool:
        """Validate OID format.
        
        Args:
            oid: OID string to validate
            
        Returns:
            True if valid OID format
        """
        return bool(OID_PATTERN.match(oid))


def build_xdsb_metadata(
    document: CCDDocument,
    patient_id: str,
    patient_id_oid: str,
    config: Optional[XDSbConfig] = None
) -> tuple[etree._Element, str, str]:
    """Convenience function to build XDSb metadata.
    
    Args:
        document: CCD document to build metadata for
        patient_id: Patient identifier
        patient_id_oid: Patient identifier OID domain
        config: Optional XDSb configuration
        
    Returns:
        Tuple of (metadata_element, submission_set_id, document_entry_id)
        
    Example:
        >>> metadata, ss_id, doc_id = build_xdsb_metadata(
        ...     document=ccd,
        ...     patient_id="PAT123",
        ...     patient_id_oid="2.16.840.1.113883.3.72.5.9.1"
        ... )
    """
    builder = XDSbMetadataBuilder(config)
    builder.set_patient_identifier(patient_id, patient_id_oid)
    builder.set_document(document)
    metadata = builder.build()
    return metadata, builder.submission_set_id, builder.document_entry_id
