"""Response parsers for IHE transactions (acknowledgments and registry responses)."""

import logging
from dataclasses import dataclass
from typing import Optional, List
from lxml import etree

logger = logging.getLogger(__name__)

# HL7v3 namespaces
HL7_NS = "urn:hl7-org:v3"


@dataclass
class AcknowledgmentDetail:
    """Details about acknowledgment errors or warnings.
    
    Attributes:
        type_code: Type of detail (E=Error, W=Warning, I=Information)
        text: Human-readable detail message
        code: Optional error code
        code_system: Optional code system OID
    """
    type_code: str
    text: str
    code: Optional[str] = None
    code_system: Optional[str] = None


@dataclass
class AcknowledgmentResponse:
    """Parsed HL7v3 acknowledgment response.
    
    Attributes:
        status: Acknowledgment status code (AA, AE, AR, CA, CE, CR)
        is_success: True if status indicates success (AA or CA)
        message_id: Acknowledgment message ID
        target_message_id: Original message ID being acknowledged
        details: List of acknowledgment details (errors, warnings, info)
    """
    status: str
    is_success: bool
    message_id: Optional[str] = None
    target_message_id: Optional[str] = None
    details: List[AcknowledgmentDetail] = None
    
    def __post_init__(self):
        """Initialize details list if None."""
        if self.details is None:
            self.details = []


def parse_acknowledgment(ack_xml: str) -> AcknowledgmentResponse:
    """Parse HL7v3 MCCI_IN000002UV01 acknowledgment message.
    
    Args:
        ack_xml: XML string containing the acknowledgment message
        
    Returns:
        AcknowledgmentResponse with parsed acknowledgment data
        
    Raises:
        ValueError: If XML is malformed or missing required elements
    """
    logger.info("Parsing HL7v3 acknowledgment message")
    
    try:
        # Parse XML
        if isinstance(ack_xml, bytes):
            root = etree.fromstring(ack_xml)
        else:
            root = etree.fromstring(ack_xml.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid XML in acknowledgment: {e}") from e
    
    # Extract message ID from root
    message_id = None
    id_elem = root.find(f".//{{{HL7_NS}}}id")
    if id_elem is not None:
        msg_id_root = id_elem.get("root")
        msg_id_ext = id_elem.get("extension")
        if msg_id_root:
            message_id = msg_id_root
            if msg_id_ext:
                message_id = f"{msg_id_root}::{msg_id_ext}"
    
    # Find acknowledgement element
    ack_elem = root.find(f".//{{{HL7_NS}}}acknowledgement")
    if ack_elem is None:
        raise ValueError(
            "No acknowledgement element found in response. "
            "Expected element: <acknowledgement> with namespace urn:hl7-org:v3"
        )
    
    # Extract status code
    type_code_elem = ack_elem.find(f".//{{{HL7_NS}}}typeCode")
    if type_code_elem is None:
        raise ValueError(
            "No typeCode element found in acknowledgement. "
            "Expected element: <typeCode code='AA|AE|AR|CA|CE|CR'/>"
        )
    
    status = type_code_elem.get("code")
    if not status:
        raise ValueError(
            "typeCode element missing 'code' attribute. "
            "Expected attribute with value: AA, AE, AR, CA, CE, or CR"
        )
    
    # Validate status code
    valid_statuses = ["AA", "AE", "AR", "CA", "CE", "CR"]
    if status not in valid_statuses:
        logger.warning(
            f"Unknown acknowledgment status code '{status}'. "
            f"Expected one of: {', '.join(valid_statuses)}"
        )
    
    # Determine success
    is_success = status in ["AA", "CA"]
    
    # Extract target message ID
    target_message_id = None
    target_msg_elem = ack_elem.find(f".//{{{HL7_NS}}}targetMessage")
    if target_msg_elem is not None:
        target_id_elem = target_msg_elem.find(f".//{{{HL7_NS}}}id")
        if target_id_elem is not None:
            target_id_root = target_id_elem.get("root")
            target_id_ext = target_id_elem.get("extension")
            if target_id_root:
                target_message_id = target_id_root
                if target_id_ext:
                    target_message_id = f"{target_id_root}::{target_id_ext}"
    
    # Extract acknowledgment details (errors, warnings, info)
    details = []
    detail_elems = ack_elem.findall(f".//{{{HL7_NS}}}acknowledgementDetail")
    for detail_elem in detail_elems:
        # Get type code
        detail_type_code = detail_elem.get("typeCode", "E")  # Default to Error
        
        # Get text
        text_elem = detail_elem.find(f".//{{{HL7_NS}}}text")
        text = text_elem.text if text_elem is not None and text_elem.text else "No detail message provided"
        
        # Get code (optional)
        code_elem = detail_elem.find(f".//{{{HL7_NS}}}code")
        code = code_elem.get("code") if code_elem is not None else None
        code_system = code_elem.get("codeSystem") if code_elem is not None else None
        
        detail = AcknowledgmentDetail(
            type_code=detail_type_code,
            text=text,
            code=code,
            code_system=code_system
        )
        details.append(detail)
        
        logger.debug(f"Found acknowledgment detail [{detail_type_code}]: {text}")
    
    # Create response object
    response = AcknowledgmentResponse(
        status=status,
        is_success=is_success,
        message_id=message_id,
        target_message_id=target_message_id,
        details=details
    )
    
    logger.info(
        f"Parsed acknowledgment: status={status}, success={is_success}, "
        f"details_count={len(details)}"
    )
    
    return response


def parse_pix_add_acknowledgment(ack_xml: str) -> AcknowledgmentResponse:
    """Parse PIX Add (ITI-44) acknowledgment response.
    
    This is a convenience wrapper around parse_acknowledgment() specifically
    for PIX Add transactions. The underlying structure is the same.
    
    Args:
        ack_xml: XML string containing the acknowledgment message
        
    Returns:
        AcknowledgmentResponse with parsed acknowledgment data
        
    Raises:
        ValueError: If XML is malformed or missing required elements
    """
    logger.info("Parsing PIX Add acknowledgment")
    return parse_acknowledgment(ack_xml)


def parse_registry_response(response_xml: str) -> dict:
    """Parse XDS registry response (for ITI-41, ITI-43).
    
    This is a placeholder for future implementation when ITI-41 is developed.
    
    Args:
        response_xml: XML string containing the registry response
        
    Returns:
        Dictionary with parsed response data
        
    Raises:
        NotImplementedError: Not yet implemented
    """
    raise NotImplementedError(
        "Registry response parsing not yet implemented. "
        "This will be added in Story 1.4 (ITI-41 implementation)."
    )
