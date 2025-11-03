"""PIX Add (ITI-44) message builder for HL7v3 PRPA_IN201301UV02."""

import logging
import uuid
from datetime import datetime
from typing import Optional
from lxml import etree

logger = logging.getLogger(__name__)

# HL7v3 namespaces
HL7_NS = "urn:hl7-org:v3"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

NSMAP = {
    None: HL7_NS,
    "xsi": XSI_NS,
}


class PatientDemographics:
    """Patient demographic data for PIX Add message.
    
    Attributes:
        patient_id: Patient identifier (extension)
        patient_id_root: Patient identifier OID (root)
        given_name: Patient's first/given name
        family_name: Patient's last/family name
        gender: Administrative gender code (M, F, O, U)
        birth_date: Birth date in YYYYMMDD format
        street_address: Street address
        city: City
        state: State/province
        postal_code: Postal/ZIP code
        country: Country code (default: US)
    """

    def __init__(
        self,
        patient_id: str,
        patient_id_root: str,
        given_name: str,
        family_name: str,
        gender: str,
        birth_date: str,
        street_address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: str = "US",
    ):
        """Initialize patient demographics."""
        self.patient_id = patient_id
        self.patient_id_root = patient_id_root
        self.given_name = given_name
        self.family_name = family_name
        self.gender = gender
        self.birth_date = birth_date
        self.street_address = street_address
        self.city = city
        self.state = state
        self.postal_code = postal_code
        self.country = country


def build_pix_add_message(
    demographics: PatientDemographics,
    sending_application: str = "IHE_TEST_UTIL",
    sending_facility: str = "2.16.840.1.113883.3.72.5.1",
    receiver_application: str = "PIX_MANAGER",
    receiver_facility: str = "2.16.840.1.113883.3.72.5.2",
) -> str:
    """Build PIX Add HL7v3 PRPA_IN201301UV02 message.
    
    Args:
        demographics: Patient demographic data
        sending_application: Sending application identifier
        sending_facility: Sending facility OID
        receiver_application: Receiving application identifier
        receiver_facility: Receiving facility OID
        
    Returns:
        XML string containing the complete PRPA_IN201301UV02 message
        
    Raises:
        ValueError: If required demographic fields are missing or invalid
    """
    logger.info(f"Building PIX Add message for patient: {demographics.patient_id}")
    
    # Validate required fields
    if not demographics.gender or demographics.gender not in ["M", "F", "O", "U"]:
        raise ValueError(f"Invalid gender '{demographics.gender}'. Must be M, F, O, or U.")
    
    # Generate message control ID
    message_id = str(uuid.uuid4())
    creation_time = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    
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
    patient_id_elem.set("root", demographics.patient_id_root)
    
    # Add Patient Person
    patient_person_elem = etree.SubElement(patient_elem, f"{{{HL7_NS}}}patientPerson")
    patient_person_elem.set("classCode", "PSN")
    patient_person_elem.set("determinerCode", "INSTANCE")
    
    # Add Name
    name_elem = etree.SubElement(patient_person_elem, f"{{{HL7_NS}}}name")
    given_elem = etree.SubElement(name_elem, f"{{{HL7_NS}}}given")
    given_elem.text = demographics.given_name
    family_elem = etree.SubElement(name_elem, f"{{{HL7_NS}}}family")
    family_elem.text = demographics.family_name
    
    # Add Gender
    gender_elem = etree.SubElement(patient_person_elem, f"{{{HL7_NS}}}administrativeGenderCode")
    gender_elem.set("code", demographics.gender)
    
    # Add Birth Date
    birth_elem = etree.SubElement(patient_person_elem, f"{{{HL7_NS}}}birthTime")
    birth_elem.set("value", demographics.birth_date)
    
    # Add Address (if provided)
    if demographics.street_address or demographics.city:
        addr_elem = etree.SubElement(patient_person_elem, f"{{{HL7_NS}}}addr")
        if demographics.street_address:
            street_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}streetAddressLine")
            street_elem.text = demographics.street_address
        if demographics.city:
            city_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}city")
            city_elem.text = demographics.city
        if demographics.state:
            state_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}state")
            state_elem.text = demographics.state
        if demographics.postal_code:
            postal_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}postalCode")
            postal_elem.text = demographics.postal_code
        if demographics.country:
            country_elem = etree.SubElement(addr_elem, f"{{{HL7_NS}}}country")
            country_elem.text = demographics.country
    
    # Add Provider Organization
    custodian_elem = etree.SubElement(registration_elem, f"{{{HL7_NS}}}custodian")
    custodian_elem.set("typeCode", "CST")
    
    assigned_entity_elem = etree.SubElement(custodian_elem, f"{{{HL7_NS}}}assignedEntity")
    assigned_entity_elem.set("classCode", "ASSIGNED")
    
    entity_id_elem = etree.SubElement(assigned_entity_elem, f"{{{HL7_NS}}}id")
    entity_id_elem.set("root", sending_facility)
    
    # Convert to string
    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    ).decode("utf-8")
    
    logger.debug(f"Generated PIX Add message with ID: {message_id}")
    return xml_string
