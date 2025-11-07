"""Mock PIX Add endpoint for testing."""

import logging
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Blueprint, Response, request
from lxml import etree

from .config import MockServerConfig

# HL7v3 and SOAP namespaces
HL7_NS = "urn:hl7-org:v3"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

NAMESPACES = {
    "hl7": HL7_NS,
    "soap": SOAP_NS,
}

# Create Blueprint
pix_add_bp = Blueprint("pix_add", __name__)

# PIX Add specific logger
pix_logger = logging.getLogger("ihe_test_util.mock_server.pix_add")

# Store config reference
_config: MockServerConfig | None = None


def setup_pix_add_logging(config: MockServerConfig) -> None:
    """Configure PIX Add specific logging with rotation.
    
    Args:
        config: Mock server configuration
    """
    global pix_logger
    
    pix_logger.setLevel(logging.DEBUG)
    pix_logger.handlers.clear()
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    pix_logger.addHandler(console_handler)
    
    # File handler (DEBUG and above) with rotation
    log_path = Path("mocks/logs/pix-add.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    pix_logger.addHandler(file_handler)
    
    pix_logger.info("PIX Add logging initialized")


def extract_patient_from_prpa(soap_xml: str) -> dict:
    """Extract patient data from PRPA_IN201301UV02 message.
    
    Args:
        soap_xml: SOAP envelope containing PRPA_IN201301UV02 message
        
    Returns:
        Dictionary containing patient data:
        - request_message_id: Request message ID
        - request_message_id_oid: Request message ID OID
        - patient_id: Patient identifier
        - patient_id_oid: Patient identifier OID
        - first_name: Patient first name (optional)
        - last_name: Patient last name (optional)
        - birth_date: Patient birth date (optional)
        - gender: Patient gender code (optional)
        - street: Street address (optional)
        - city: City (optional)
        - state: State (optional)
        - postal_code: Postal code (optional)
        
    Raises:
        ValueError: If PRPA_IN201301UV02 element is missing
        ValueError: If patient identifier is missing
    """
    try:
        tree = etree.fromstring(soap_xml.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise ValueError(
            f"Malformed XML: {e}. Ensure the request contains valid XML."
        )
    
    # Find PRPA_IN201301UV02 element
    prpa_elem = tree.find(".//hl7:PRPA_IN201301UV02", namespaces=NAMESPACES)
    if prpa_elem is None:
        raise ValueError(
            "Missing PRPA_IN201301UV02 element in SOAP body. "
            "Ensure the request contains a valid PIX Add message."
        )
    
    # Extract request message ID
    request_id_elem = prpa_elem.find("hl7:id", namespaces=NAMESPACES)
    if request_id_elem is None:
        raise ValueError(
            "Missing message ID <id> element in PRPA_IN201301UV02. "
            "Ensure message includes message ID with root OID and extension."
        )
    
    request_message_id_oid = request_id_elem.get("root", "")
    request_message_id = request_id_elem.get("extension", "")
    
    # Extract patient element
    patient_elem = prpa_elem.find(
        ".//hl7:controlActProcess/hl7:subject/hl7:registrationEvent/"
        "hl7:subject1/hl7:patient",
        namespaces=NAMESPACES
    )
    
    if patient_elem is None:
        raise ValueError(
            "Missing patient element in PRPA_IN201301UV02. "
            "Ensure message includes patient registration data."
        )
    
    # Extract patient identifier
    patient_id_elem = patient_elem.find("hl7:id", namespaces=NAMESPACES)
    if patient_id_elem is None:
        raise ValueError(
            "Missing patient identifier <id> element in PRPA_IN201301UV02. "
            "Ensure message includes patient ID with root OID and extension."
        )
    
    patient_id_oid = patient_id_elem.get("root", "")
    patient_id = patient_id_elem.get("extension", "")
    
    if not patient_id:
        raise ValueError(
            "Missing patient identifier extension attribute. "
            "Ensure patient <id> element includes extension attribute with patient ID."
        )
    
    # Extract patient demographics (optional fields)
    patient_person_elem = patient_elem.find("hl7:patientPerson", namespaces=NAMESPACES)
    
    result = {
        "request_message_id": request_message_id,
        "request_message_id_oid": request_message_id_oid,
        "patient_id": patient_id,
        "patient_id_oid": patient_id_oid,
    }
    
    if patient_person_elem is not None:
        # Extract name
        name_elem = patient_person_elem.find("hl7:name", namespaces=NAMESPACES)
        if name_elem is not None:
            given_elem = name_elem.find("hl7:given", namespaces=NAMESPACES)
            family_elem = name_elem.find("hl7:family", namespaces=NAMESPACES)
            if given_elem is not None and given_elem.text:
                result["first_name"] = given_elem.text
            if family_elem is not None and family_elem.text:
                result["last_name"] = family_elem.text
        
        # Extract birth date
        birth_elem = patient_person_elem.find("hl7:birthTime", namespaces=NAMESPACES)
        if birth_elem is not None:
            birth_date = birth_elem.get("value")
            if birth_date:
                result["birth_date"] = birth_date
        
        # Extract gender
        gender_elem = patient_person_elem.find(
            "hl7:administrativeGenderCode",
            namespaces=NAMESPACES
        )
        if gender_elem is not None:
            gender = gender_elem.get("code")
            if gender:
                result["gender"] = gender
        
        # Extract address
        addr_elem = patient_person_elem.find("hl7:addr", namespaces=NAMESPACES)
        if addr_elem is not None:
            street_elem = addr_elem.find("hl7:streetAddressLine", namespaces=NAMESPACES)
            city_elem = addr_elem.find("hl7:city", namespaces=NAMESPACES)
            state_elem = addr_elem.find("hl7:state", namespaces=NAMESPACES)
            postal_elem = addr_elem.find("hl7:postalCode", namespaces=NAMESPACES)
            
            if street_elem is not None and street_elem.text:
                result["street"] = street_elem.text
            if city_elem is not None and city_elem.text:
                result["city"] = city_elem.text
            if state_elem is not None and state_elem.text:
                result["state"] = state_elem.text
            if postal_elem is not None and postal_elem.text:
                result["postal_code"] = postal_elem.text
    
    pix_logger.debug(f"Extracted patient data: {result}")
    
    return result


def generate_acknowledgment(
    request_message_id: str,
    request_message_id_oid: str,
    patient_id: str,
    patient_id_oid: str,
    status: str = "AA"
) -> str:
    """Generate MCCI_IN000002UV01 acknowledgment.
    
    Args:
        request_message_id: Original request message ID (for correlation)
        request_message_id_oid: Original request message ID OID
        patient_id: Patient identifier to echo back
        patient_id_oid: Patient identifier OID to echo back
        status: Acknowledgment status code (AA=accept, AE=error, AR=reject)
        
    Returns:
        Complete SOAP envelope containing MCCI_IN000002UV01 acknowledgment
    """
    # Generate unique response message ID
    response_message_id = str(uuid.uuid4())
    
    # Create SOAP envelope
    soap_envelope = etree.Element(
        f"{{{SOAP_NS}}}Envelope",
        nsmap={"SOAP-ENV": SOAP_NS}
    )
    
    soap_body = etree.SubElement(soap_envelope, f"{{{SOAP_NS}}}Body")
    
    # Create MCCI_IN000002UV01 acknowledgment
    mcci_elem = etree.SubElement(
        soap_body,
        f"{{{HL7_NS}}}MCCI_IN000002UV01",
        nsmap={None: HL7_NS},
        ITSVersion="XML_1.0"
    )
    
    # Add response message ID
    id_elem = etree.SubElement(mcci_elem, f"{{{HL7_NS}}}id")
    id_elem.set("root", request_message_id_oid)
    id_elem.set("extension", response_message_id)
    
    # Add creation time
    creation_time = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    creation_time_elem = etree.SubElement(mcci_elem, f"{{{HL7_NS}}}creationTime")
    creation_time_elem.set("value", creation_time)
    
    # Add acknowledgment
    ack_elem = etree.SubElement(mcci_elem, f"{{{HL7_NS}}}acknowledgement")
    
    type_code_elem = etree.SubElement(ack_elem, f"{{{HL7_NS}}}typeCode")
    type_code_elem.set("code", status)
    
    # Add target message (correlation ID)
    target_msg_elem = etree.SubElement(ack_elem, f"{{{HL7_NS}}}targetMessage")
    target_id_elem = etree.SubElement(target_msg_elem, f"{{{HL7_NS}}}id")
    target_id_elem.set("root", request_message_id_oid)
    target_id_elem.set("extension", request_message_id)
    
    # Echo back patient identifiers
    control_act_elem = etree.SubElement(mcci_elem, f"{{{HL7_NS}}}controlActProcess")
    subject_elem = etree.SubElement(control_act_elem, f"{{{HL7_NS}}}subject")
    reg_event_elem = etree.SubElement(subject_elem, f"{{{HL7_NS}}}registrationEvent")
    subject1_elem = etree.SubElement(reg_event_elem, f"{{{HL7_NS}}}subject1")
    patient_elem = etree.SubElement(subject1_elem, f"{{{HL7_NS}}}patient")
    
    patient_id_elem = etree.SubElement(patient_elem, f"{{{HL7_NS}}}id")
    patient_id_elem.set("root", patient_id_oid)
    patient_id_elem.set("extension", patient_id)
    
    # Convert to XML string
    xml_string = etree.tostring(
        soap_envelope,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    ).decode("utf-8")
    
    return xml_string


def generate_soap_fault(
    faultcode: str,
    faultstring: str,
    detail: str | None = None
) -> str:
    """Generate SOAP 1.2 fault response.
    
    Args:
        faultcode: SOAP fault code (e.g., 'soap:Sender', 'soap:Receiver')
        faultstring: Human-readable fault description
        detail: Optional detailed error information
        
    Returns:
        SOAP fault XML string
    """
    import html
    
    # Escape XML special characters
    faultstring_escaped = html.escape(faultstring)
    
    detail_xml = ""
    if detail:
        detail_escaped = html.escape(detail)
        detail_xml = f"""
      <soap:Detail>
        <error>{detail_escaped}</error>
      </soap:Detail>"""
    
    fault_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <soap:Fault>
      <soap:Code>
        <soap:Value>{faultcode}</soap:Value>
      </soap:Code>
      <soap:Reason>
        <soap:Text xml:lang="en">{faultstring_escaped}</soap:Text>
      </soap:Reason>{detail_xml}
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""
    
    return fault_xml


@pix_add_bp.route("/pix/add", methods=["POST"])
def handle_pix_add() -> tuple[Response, int]:
    """Handle PIX Add request.
    
    Returns:
        Tuple of (Response object, HTTP status code)
    """
    global _config
    
    start_time = datetime.now(timezone.utc)
    
    pix_logger.info("Received PIX Add request")
    
    try:
        # Get request data
        request_data = request.data.decode("utf-8")
        
        pix_logger.debug(f"Request size: {len(request_data)} bytes")
        pix_logger.debug(f"Full SOAP request:\n{request_data}")
        
        # Extract patient data from PRPA message
        try:
            patient_data = extract_patient_from_prpa(request_data)
        except ValueError as e:
            pix_logger.warning(f"SOAP fault: {e}")
            fault_xml = generate_soap_fault(
                "soap:Sender",
                str(e),
                detail="Invalid PIX Add request structure"
            )
            return Response(fault_xml, mimetype="text/xml; charset=utf-8"), 400
        except etree.XMLSyntaxError as e:
            pix_logger.warning(f"XML parsing error: {e}")
            fault_xml = generate_soap_fault(
                "soap:Sender",
                "Malformed XML",
                detail=f"Failed to parse XML: {e}"
            )
            return Response(fault_xml, mimetype="text/xml; charset=utf-8"), 400
        
        # Log extracted patient data
        pix_logger.info(
            f"PIX Add request - MessageID: {patient_data['request_message_id']}, "
            f"PatientID: {patient_data['patient_id']}"
        )
        
        if "first_name" in patient_data and "last_name" in patient_data:
            pix_logger.info(
                f"Patient demographics - Name: {patient_data['first_name']} "
                f"{patient_data['last_name']}"
            )
        
        # Simulate response delay if configured
        if _config and _config.response_delay_ms > 0:
            pix_logger.debug(f"Simulating network delay: {_config.response_delay_ms}ms")
            time.sleep(_config.response_delay_ms / 1000.0)
        
        # Generate acknowledgment
        ack_xml = generate_acknowledgment(
            patient_data["request_message_id"],
            patient_data["request_message_id_oid"],
            patient_data["patient_id"],
            patient_data["patient_id_oid"],
            status="AA"
        )
        
        # Log response
        processing_time_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )
        
        pix_logger.info(
            f"PIX Add response - Status: AA, "
            f"CorrelationID: {patient_data['request_message_id']}, "
            f"ProcessingTime: {processing_time_ms}ms"
        )
        pix_logger.debug(f"Full SOAP response:\n{ack_xml}")
        
        return Response(ack_xml, mimetype="text/xml; charset=utf-8"), 200
        
    except Exception as e:
        pix_logger.error(f"Unexpected error processing PIX Add request: {e}", exc_info=True)
        fault_xml = generate_soap_fault(
            "soap:Receiver",
            "Internal Server Error",
            detail=str(e)
        )
        return Response(fault_xml, mimetype="text/xml; charset=utf-8"), 500


def register_pix_add_endpoint(app, config: MockServerConfig) -> None:
    """Register PIX Add endpoint with Flask app.
    
    Args:
        app: Flask application instance
        config: Mock server configuration
    """
    global _config
    _config = config
    
    # Setup PIX Add logging
    setup_pix_add_logging(config)
    
    # Register Blueprint (only if not already registered)
    if pix_add_bp.name not in app.blueprints:
        app.register_blueprint(pix_add_bp)
        pix_logger.info(f"Registered PIX Add endpoint: {config.pix_add_endpoint}")
    else:
        pix_logger.debug("PIX Add endpoint already registered")
