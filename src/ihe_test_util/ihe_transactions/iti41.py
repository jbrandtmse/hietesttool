"""ITI-41 (Provide and Register Document Set-b) transaction builder."""

import logging
import uuid
from typing import Optional
from pathlib import Path
from lxml import etree
from .mtom import MTOMAttachment

logger = logging.getLogger(__name__)

# XDS.b namespaces
XDS_NS = "urn:ihe:iti:xds-b:2007"
RIM_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
LCM_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0"
RS_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"

NSMAP = {
    "xds": XDS_NS,
    "rim": RIM_NS,
    "lcm": LCM_NS,
    "rs": RS_NS,
}


class ITI41Request:
    """ITI-41 Provide and Register Document Set-b request builder.
    
    Attributes:
        patient_id: Patient identifier
        patient_id_root: Patient identifier OID domain
        document_unique_id: Unique identifier for the document
        document_unique_id_root: OID for document unique ID
        submission_set_id: Unique identifier for the submission set
        submission_set_id_root: OID for submission set ID
    """

    def __init__(
        self,
        patient_id: str,
        patient_id_root: str,
        document_unique_id: Optional[str] = None,
        document_unique_id_root: str = "2.16.840.1.113883.3.72.5.9.1",
        submission_set_id: Optional[str] = None,
        submission_set_id_root: str = "2.16.840.1.113883.3.72.5.9.2",
    ):
        """Initialize ITI-41 request.
        
        Args:
            patient_id: Patient identifier
            patient_id_root: Patient identifier OID domain
            document_unique_id: Document unique ID (auto-generated if None)
            document_unique_id_root: OID for document unique ID
            submission_set_id: Submission set ID (auto-generated if None)
            submission_set_id_root: OID for submission set ID
        """
        self.patient_id = patient_id
        self.patient_id_root = patient_id_root
        self.document_unique_id = document_unique_id or str(uuid.uuid4())
        self.document_unique_id_root = document_unique_id_root
        self.submission_set_id = submission_set_id or str(uuid.uuid4())
        self.submission_set_id_root = submission_set_id_root


def build_iti41_request(
    request: ITI41Request,
    document_path: Path,
    content_id: str = "document1@ihe-test-util.example.com",
    document_title: str = "Clinical Document",
    class_code: str = "34133-9",
    type_code: str = "34133-9",
    format_code: str = "urn:ihl7-org:sdwg:ccda-structuredBody:2.1",
) -> tuple[str, MTOMAttachment]:
    """Build ITI-41 ProvideAndRegisterDocumentSetRequest.
    
    Args:
        request: ITI-41 request configuration
        document_path: Path to the CCD document to submit
        content_id: Content-ID for MTOM attachment
        document_title: Human-readable document title
        class_code: XDS classCode (LOINC code)
        type_code: XDS typeCode (LOINC code)
        format_code: XDS formatCode (document format)
        
    Returns:
        Tuple of (XML request string, MTOMAttachment)
        
    Raises:
        FileNotFoundError: If document_path doesn't exist
    """
    logger.info(f"Building ITI-41 request for document: {document_path}")
    
    if not document_path.exists():
        raise FileNotFoundError(f"Document not found: {document_path}")
    
    # Create MTOM attachment
    attachment = MTOMAttachment.from_file(
        document_path,
        content_id,
        content_type="text/xml"
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
    
    # Build ExtrinsicObject (Document Entry)
    doc_entry_id = f"Document01"
    extrinsic = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}ExtrinsicObject",
        id=doc_entry_id,
        mimeType="text/xml",
        objectType="urn:uuid:7edca82f-054d-47f2-a032-9b2a5b5186c1"
    )
    
    # Add Document Entry Name
    name_elem = etree.SubElement(extrinsic, f"{{{RIM_NS}}}Name")
    localized_string = etree.SubElement(
        name_elem,
        f"{{{RIM_NS}}}LocalizedString",
        value=document_title
    )
    
    # Add Document Entry Description
    desc_elem = etree.SubElement(extrinsic, f"{{{RIM_NS}}}Description")
    etree.SubElement(
        desc_elem,
        f"{{{RIM_NS}}}LocalizedString",
        value="Clinical document for patient"
    )
    
    # Add Document Entry Classifications
    
    # classCode
    class_classification = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}Classification",
        id=f"cl-{uuid.uuid4()}",
        classificationScheme="urn:uuid:41a5887f-8865-4c09-adf7-e362475b143a",
        classifiedObject=doc_entry_id,
        nodeRepresentation=class_code
    )
    _add_slot(class_classification, "codingScheme", "2.16.840.1.113883.6.1")
    _add_name(class_classification, "Summarization of Episode Note")
    
    # typeCode
    type_classification = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}Classification",
        id=f"cl-{uuid.uuid4()}",
        classificationScheme="urn:uuid:f0306f51-975f-434e-a61c-c59651d33983",
        classifiedObject=doc_entry_id,
        nodeRepresentation=type_code
    )
    _add_slot(type_classification, "codingScheme", "2.16.840.1.113883.6.1")
    _add_name(type_classification, "Summarization of Episode Note")
    
    # formatCode
    format_classification = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}Classification",
        id=f"cl-{uuid.uuid4()}",
        classificationScheme="urn:uuid:a09d5840-386c-46f2-b5ad-9c3699a4309d",
        classifiedObject=doc_entry_id,
        nodeRepresentation=format_code
    )
    _add_slot(format_classification, "codingScheme", "1.3.6.1.4.1.19376.1.2.3")
    _add_name(format_classification, "CCDA R2.1")
    
    # Add External Identifiers
    
    # patientId
    patient_id_ext = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}ExternalIdentifier",
        id=f"ei-{uuid.uuid4()}",
        registryObject=doc_entry_id,
        identificationScheme="urn:uuid:58a6f841-87b3-4a3e-92fd-a8ffeff98427",
        value=f"{request.patient_id}^^^&{request.patient_id_root}&ISO"
    )
    _add_name(patient_id_ext, "XDSDocumentEntry.patientId")
    
    # uniqueId
    unique_id_ext = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}ExternalIdentifier",
        id=f"ei-{uuid.uuid4()}",
        registryObject=doc_entry_id,
        identificationScheme="urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab",
        value=f"{request.document_unique_id_root}.{request.document_unique_id}"
    )
    _add_name(unique_id_ext, "XDSDocumentEntry.uniqueId")
    
    # Add RegistryPackage (Submission Set)
    submission_set_id_val = f"SubmissionSet01"
    registry_package = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}RegistryPackage",
        id=submission_set_id_val
    )
    
    # Submission Set Name
    ss_name = etree.SubElement(registry_package, f"{{{RIM_NS}}}Name")
    etree.SubElement(
        ss_name,
        f"{{{RIM_NS}}}LocalizedString",
        value="Submission Set"
    )
    
    # Submission Set Description
    ss_desc = etree.SubElement(registry_package, f"{{{RIM_NS}}}Description")
    etree.SubElement(
        ss_desc,
        f"{{{RIM_NS}}}LocalizedString",
        value="Document submission set"
    )
    
    # Submission Set contentTypeCode
    ss_content_type = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}Classification",
        id=f"cl-{uuid.uuid4()}",
        classificationScheme="urn:uuid:aa543740-bdda-424e-8c96-df4873be8500",
        classifiedObject=submission_set_id_val,
        nodeRepresentation=class_code
    )
    _add_slot(ss_content_type, "codingScheme", "2.16.840.1.113883.6.1")
    _add_name(ss_content_type, "Clinical Document")
    
    # Submission Set patientId
    ss_patient_id = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}ExternalIdentifier",
        id=f"ei-{uuid.uuid4()}",
        registryObject=submission_set_id_val,
        identificationScheme="urn:uuid:6b5aea1a-874d-4603-a4bc-96a0a7b38446",
        value=f"{request.patient_id}^^^&{request.patient_id_root}&ISO"
    )
    _add_name(ss_patient_id, "XDSSubmissionSet.patientId")
    
    # Submission Set uniqueId
    ss_unique_id = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}ExternalIdentifier",
        id=f"ei-{uuid.uuid4()}",
        registryObject=submission_set_id_val,
        identificationScheme="urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8",
        value=f"{request.submission_set_id_root}.{request.submission_set_id}"
    )
    _add_name(ss_unique_id, "XDSSubmissionSet.uniqueId")
    
    # Submission Set sourceId
    ss_source_id = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}ExternalIdentifier",
        id=f"ei-{uuid.uuid4()}",
        registryObject=submission_set_id_val,
        identificationScheme="urn:uuid:554ac39e-e3fe-47fe-b233-965d2a147832",
        value="2.16.840.1.113883.3.72.5.1"
    )
    _add_name(ss_source_id, "XDSSubmissionSet.sourceId")
    
    # Add Association (links document to submission set)
    association = etree.SubElement(
        registry_list,
        f"{{{RIM_NS}}}Association",
        id=f"as-{uuid.uuid4()}",
        associationType="urn:oasis:names:tc:ebxml-regrep:AssociationType:HasMember",
        sourceObject=submission_set_id_val,
        targetObject=doc_entry_id
    )
    _add_slot(association, "SubmissionSetStatus", "Original")
    
    # Add Document element with Content-ID reference
    document_elem = etree.SubElement(
        root,
        f"{{{XDS_NS}}}Document",
        id=doc_entry_id
    )
    
    # Add XOP Include reference (this is where MTOM magic happens)
    # Note: In actual MTOM transmission, this gets replaced with xop:Include
    # For now, we'll add a placeholder that zeep should handle
    document_elem.text = "PLACEHOLDER_FOR_MTOM_ATTACHMENT"
    
    # Convert to string
    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=False,
        encoding="UTF-8"
    ).decode("utf-8")
    
    logger.info(f"Generated ITI-41 request with document ID: {request.document_unique_id}")
    return xml_string, attachment


def _add_slot(parent: etree.Element, name: str, value: str) -> None:
    """Add a Slot element to a parent element."""
    slot = etree.SubElement(parent, f"{{{RIM_NS}}}Slot", name=name)
    value_list = etree.SubElement(slot, f"{{{RIM_NS}}}ValueList")
    value_elem = etree.SubElement(value_list, f"{{{RIM_NS}}}Value")
    value_elem.text = value


def _add_name(parent: etree.Element, value: str) -> None:
    """Add a Name element to a parent element."""
    name = etree.SubElement(parent, f"{{{RIM_NS}}}Name")
    localized = etree.SubElement(
        name,
        f"{{{RIM_NS}}}LocalizedString",
        value=value
    )
