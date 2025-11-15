"""PIX Add (ITI-44) message builder for HL7v3 PRPA_IN201301UV02."""

import logging
import re
import uuid
from datetime import date, datetime, timezone
from lxml import etree

from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.utils.exceptions import ValidationError

logger = logging.getLogger(__name__)

# HL7v3 and SOAP namespaces
HL7_NS = "urn:hl7-org:v3"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

NSMAP = {
    None: HL7_NS,
    "xsi": XSI_NS,
}

SOAP_NSMAP = {
    "SOAP-ENV": SOAP_NS,
}


def format_hl7_timestamp(dt: datetime) -> str:
    """Format datetime as HL7v3 timestamp (TS).
    
    Converts a Python datetime object to HL7v3 timestamp format.
    Format: YYYYMMDDHHmmss (14 digits, no delimiters).
    
    Args:
        dt: Datetime to format (naive or timezone-aware)
        
    Returns:
        HL7 timestamp string in YYYYMMDDHHmmss format
        
    Example:
        >>> dt = datetime(2025, 11, 14, 15, 30, 0)
        >>> format_hl7_timestamp(dt)
        '20251114153000'
    """
    return dt.strftime("%Y%m%d%H%M%S")


def format_hl7_date(d: date) -> str:
    """Format date as HL7v3 date.
    
    Converts a Python date object to HL7v3 date format.
    Format: YYYYMMDD (8 digits, no delimiters).
    
    Args:
        d: Date to format
        
    Returns:
        HL7 date string in YYYYMMDD format
        
    Example:
        >>> d = date(1980, 1, 1)
        >>> format_hl7_date(d)
        '19800101'
    """
    return d.strftime("%Y%m%d")


def validate_gender_code(gender: str) -> None:
    """Validate HL7 administrative gender code.
    
    Ensures the gender code is one of the valid HL7v3 administrative
    gender codes. Raises an actionable error if invalid.
    
    Args:
        gender: Gender code to validate
        
    Raises:
        ValidationError: If gender code is not M, F, O, or U
        
    Example:
        >>> validate_gender_code("M")  # No error
        >>> validate_gender_code("X")  # Raises ValidationError
    """
    valid_codes = ["M", "F", "O", "U"]
    if not gender or gender not in valid_codes:
        raise ValidationError(
            f"Invalid gender '{gender}'. "
            f"Must be M (Male), F (Female), O (Other), or U (Unknown)."
        )


def validate_oid(oid: str, field_name: str) -> None:
    """Validate OID format.
    
    Ensures the OID follows the standard format: starts with a digit
    and contains only digits and dots.
    
    Args:
        oid: OID string to validate
        field_name: Name of the field (for error message)
        
    Raises:
        ValidationError: If OID format is invalid
    """
    if not oid:
        raise ValidationError(
            f"Missing required field: {field_name}. "
            f"OID must be provided."
        )
    
    # OID must start with digit and contain only digits and dots
    if not re.match(r'^\d+(\.\d+)*$', oid):
        raise ValidationError(
            f"Invalid OID format for {field_name}: '{oid}'. "
            f"OID must start with digit and contain only digits and dots."
        )


def format_xml(xml_element: etree._Element) -> str:
    """Format XML element as human-readable string.
    
    Converts an lxml Element to a pretty-printed XML string with
    proper indentation for readability.
    
    Args:
        xml_element: lxml Element to format
        
    Returns:
        Pretty-printed XML string with indentation
        
    Example:
        >>> root = etree.Element("root")
        >>> child = etree.SubElement(root, "child")
        >>> xml_str = format_xml(root)
        >>> print(xml_str)
        <root>
          <child/>
        </root>
    """
    return etree.tostring(
        xml_element,
        pretty_print=True,
        encoding='unicode',
        xml_declaration=False
    )


def build_pix_add_message(
    demographics: PatientDemographics,
    sending_application: str = "IHE_TEST_UTIL",
    sending_facility: str = "2.16.840.1.113883.3.72.5.1",
    receiver_application: str = "PIX_MANAGER",
    receiver_facility: str = "2.16.840.1.113883.3.72.5.2",
) -> str:
    """Build PIX Add HL7v3 PRPA_IN201301UV02 message.
    
    Constructs a complete HL7v3 message for patient registration via
    IHE PIX Add transaction (ITI-44). Message includes all required
    elements per IHE specification and validates patient demographics.
    
    Args:
        demographics: Patient demographic information from PatientDemographics dataclass
        sending_application: Sending application identifier
        sending_facility: Sending facility OID
        receiver_application: Receiving application identifier
        receiver_facility: Receiving facility OID
        
    Returns:
        Complete HL7v3 XML message as formatted string wrapped in SOAP envelope
        
    Raises:
        ValidationError: If patient gender code is invalid (not M, F, O, U)
        ValidationError: If required patient fields are missing
        ValidationError: If OID format is invalid
        
    Example:
        >>> from datetime import date
        >>> from ihe_test_util.models.patient import PatientDemographics
        >>> patient = PatientDemographics(
        ...     patient_id="12345",
        ...     patient_id_oid="1.2.3.4.5",
        ...     first_name="John",
        ...     last_name="Doe",
        ...     dob=date(1980, 1, 1),
        ...     gender="M"
        ... )
        >>> xml = build_pix_add_message(patient, "SENDER", "1.2.3.4", "RECEIVER", "1.2.3.5")
        >>> print(xml[:100])
        <?xml version='1.0' encoding='UTF-8'?>
        <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">...
    """
    logger.info(f"Building PIX Add message for patient: {demographics.patient_id}")
    
    # Validate required fields
    if not demographics.patient_id:
        raise ValidationError(
            "Missing required patient field: patient_id. "
            "Ensure PatientDemographics has all required fields."
        )
    if not demographics.first_name:
        raise ValidationError(
            "Missing required patient field: first_name. "
            "Ensure PatientDemographics has all required fields."
        )
    if not demographics.last_name:
        raise ValidationError(
            "Missing required patient field: last_name. "
            "Ensure PatientDemographics has all required fields."
        )
    if not demographics.dob:
        raise ValidationError(
            "Missing required patient field: dob. "
            "Ensure PatientDemographics has all required fields."
        )
    
    # Validate gender code
    validate_gender_code(demographics.gender)
    
    # Validate OIDs
    validate_oid(demographics.patient_id_oid, "patient_id_oid")
    validate_oid(sending_facility, "sending_facility")
    validate_oid(receiver_facility, "receiver_facility")
    
    logger.debug("Patient demographics validation passed")
    
    # Generate message control ID
    message_id = str(uuid.uuid4())
    creation_time = format_hl7_timestamp(datetime.now(timezone.utc))
    
    # Convert date to HL7 format
    birth_date_hl7 = format_hl7_date(demographics.dob)
    
    # Build root element
    root = etree.Element(
        f"{{{HL7_NS}}}PRPA_IN201301UV02",
        nsmap=NSMAP,
        ITSVersion="XML_1.0"
    )
    
    # Add Message ID
    id_elem = etree.SubElement(root, f"{{{HL7_NS}}}id")
    id_elem.set("root", message_id)
    
    # Add Creation Time
    creation_time_elem = etree.SubElement(root, f"{{{HL7_NS}}}creationTime")
    creation_time_elem.set("value", creation_time)
    
    # Add Interaction ID
    interaction_id_elem = etree.SubElement(root, f"{{{HL7_NS}}}interactionId")
    interaction_id_elem.set("root", "2.16.840.1.113883.1.6")
    interaction_id_elem.set("extension", "PRPA_IN201301UV02")
    
    # Add Processing Code (P = Production)
    processing_code_elem = etree.SubElement(root, f"{{{HL7_NS}}}processingCode")
    processing_code_elem.set("code", "P")
    
    # Add Processing Mode Code (T = Current processing)
    processing_mode_elem = etree.SubElement(root, f"{{{HL7_NS}}}processingModeCode")
    processing_mode_elem.set("code", "T")
    
    # Add Accept Acknowledgement Code (AL = Always)
    accept_ack_elem = etree.SubElement(root, f"{{{HL7_NS}}}acceptAckCode")
    accept_ack_elem.set("code", "AL")
    
    # Add Receiver
    receiver_elem = etree.SubElement(root, f"{{{HL7_NS}}}receiver")
    receiver_elem.set("typeCode", "RCV")
    device_elem = etree.SubElement(receiver_elem, f"{{{HL7_NS}}}device")
    device_elem.set("classCode", "DEV")
    device_elem.set("determinerCode", "INSTANCE")
    device_id_elem = etree.SubElement(device_elem, f"{{{HL7_NS}}}id")
    device_id_elem.set("root", receiver_facility)
    device_name_elem = etree.SubElement(device_elem, f"{{{HL7_NS}}}name")
    device_name_elem.text = receiver_application
    
    # Add Sender
    sender_elem = etree.SubElement(root, f"{{{HL7_NS}}}sender")
    sender_elem.set("typeCode", "SND")
    sender_device_elem = etree.SubElement(sender_elem, f"{{{HL7_NS}}}device")
    sender_device_elem.set("classCode", "DEV")
    sender_device_elem.set("determinerCode", "INSTANCE")
    sender_id_elem = etree.SubElement(sender_device_elem, f"{{{HL7_NS}}}id")
    sender_id_elem.set("root", sending_facility)
    sender_name_elem = etree.SubElement(sender_device_elem, f"{{{HL7_NS}}}name")
    sender_name_elem.text = sending_application
    
    # Add Control Act Process
    control_act_elem = etree.SubElement(root, f"{{{HL7_NS}}}controlActProcess")
    control_act_elem.set("classCode", "CACT")
    control_act_elem.set("moodCode", "EVN")
    
    # Add Control Act Process Code
    code_elem = etree.SubElement(control_act_elem, f"{{{HL7_NS}}}code")
    code_elem.set("code", "PRPA_TE201301UV02")
    code_elem.set("codeSystem", "2.16.840.1.113883.1.6")
    
    # Add Subject
    subject_elem = etree.SubElement(control_act_elem, f"{{{HL7_NS}}}subject")
    subject_elem.set("typeCode", "SUBJ")
    
    # Add Registration Event
    registration_elem = etree.SubElement(subject_elem, f"{{{HL7_NS}}}registrationEvent")
    registration_elem.set("classCode", "REG")
    registration_elem.set("moodCode", "EVN")
    
    reg_id_elem = etree.SubElement(registration_elem, f"{{{HL7_NS}}}id")
    reg_id_elem.set("nullFlavor", "NA")
    
    status_code_elem = etree.SubElement(registration_elem, f"{{{HL7_NS}}}statusCode")
    status_code_elem.set("code", "active")
    
    # Add Subject1 (Patient)
    subject1_elem = etree.SubElement(registration_elem, f"{{{HL7_NS}}}subject1")
    subject1_elem.set("typeCode", "SBJ")
    
    patient_elem = etree.SubElement(subject1_elem, f"{{{HL7_NS}}}patient")
    patient_elem.set("classCode", "PAT")
    
    # Add Patient ID
    patient_id_elem = etree.SubElement(patient_elem, f"{{{HL7_NS}}}id")
    patient_id_elem.set("extension", demographics.patient_id)
    patient_id_elem.set("root", demographics.patient_id_oid)
    
    # Add Patient Person
    patient_person_elem = etree.SubElement(patient_elem, f"{{{HL7_NS}}}patientPerson")
    patient_person_elem.set("classCode", "PSN")
    patient_person_elem.set("determinerCode", "INSTANCE")
    
    # Add Name
    name_elem = etree.SubElement(patient_person_elem, f"{{{HL7_NS}}}name")
    given_elem = etree.SubElement(name_elem, f"{{{HL7_NS}}}given")
    given_elem.text = demographics.first_name
    family_elem = etree.SubElement(name_elem, f"{{{HL7_NS}}}family")
    family_elem.text = demographics.last_name
    
    # Add Gender
    gender_elem = etree.SubElement(patient_person_elem, f"{{{HL7_NS}}}administrativeGenderCode")
    gender_elem.set("code", demographics.gender)
    
    # Add Birth Date
    birth_elem = etree.SubElement(patient_person_elem, f"{{{HL7_NS}}}birthTime")
    birth_elem.set("value", birth_date_hl7)
    
    # Add Address (if provided)
    if demographics.address or demographics.city:
        addr_elem = etree.SubElement(patient_person_elem, f"{{{HL7_NS}}}addr")
        if demographics.address:
            street_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}streetAddressLine")
            street_elem.text = demographics.address
        if demographics.city:
            city_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}city")
            city_elem.text = demographics.city
        if demographics.state:
            state_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}state")
            state_elem.text = demographics.state
        if demographics.zip:
            postal_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}postalCode")
            postal_elem.text = demographics.zip
    
    # Add Provider Organization
    custodian_elem = etree.SubElement(registration_elem, f"{{{HL7_NS}}}custodian")
    custodian_elem.set("typeCode", "CST")
    
    assigned_entity_elem = etree.SubElement(custodian_elem, f"{{{HL7_NS}}}assignedEntity")
    assigned_entity_elem.set("classCode", "ASSIGNED")
    
    entity_id_elem = etree.SubElement(assigned_entity_elem, f"{{{HL7_NS}}}id")
    entity_id_elem.set("root", sending_facility)
    
    # Wrap PRPA message in SOAP envelope
    soap_envelope = etree.Element(
        f"{{{SOAP_NS}}}Envelope",
        nsmap=SOAP_NSMAP
    )
    soap_body = etree.SubElement(soap_envelope, f"{{{SOAP_NS}}}Body")
    soap_body.append(root)
    
    # Convert to string
    xml_string = etree.tostring(
        soap_envelope,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    ).decode("utf-8")
    
    logger.debug(f"Generated PIX Add message with ID: {message_id}")
    return xml_string
