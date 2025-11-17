"""Response parsers for IHE transactions (acknowledgments and registry responses)."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from lxml import etree

logger = logging.getLogger(__name__)

# HL7v3 namespaces
HL7_NS = "urn:hl7-org:v3"

# Audit logger for acknowledgment responses
audit_logger = logging.getLogger('ihe_test_util.audit.acknowledgments')


def log_acknowledgment_response(response_xml: str, status: str, message_id: str) -> None:
    """Log complete acknowledgment response to audit trail.
    
    Logs PIX Add and other IHE acknowledgment responses to dedicated audit file.
    Follows RULE 2: All IHE transactions MUST log complete request/response.
    
    Args:
        response_xml: Complete SOAP/XML response
        status: Acknowledgment status code (AA, AE, AR, etc.)
        message_id: Message ID for correlation
        
    Example:
        >>> log_acknowledgment_response(response_xml, "AA", "MSG-123")
    """
    # Ensure log directory exists
    log_dir = Path("logs/transactions")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create dated log file
    log_file = log_dir / f"pix-add-responses-{datetime.now().strftime('%Y%m%d')}.log"
    
    # Configure audit logger if not already configured
    if not audit_logger.handlers:
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        audit_logger.addHandler(handler)
        audit_logger.setLevel(logging.DEBUG)
    
    # Log summary at INFO level
    audit_logger.info(
        f"PIX Add Acknowledgment - Status: {status}, MessageID: {message_id}, "
        f"Size: {len(response_xml)} bytes"
    )
    
    # Log complete response XML at DEBUG level (RULE 2)
    audit_logger.debug(f"Response XML (MessageID: {message_id}):\n{response_xml}")


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
        patient_identifiers: Dictionary of patient IDs extracted from response
        query_continuation: Optional query continuation information
    """
    status: str
    is_success: bool
    message_id: Optional[str] = None
    target_message_id: Optional[str] = None
    details: List[AcknowledgmentDetail] = None
    patient_identifiers: dict = None
    query_continuation: Optional[dict] = None
    
    def __post_init__(self):
        """Initialize fields if None."""
        if self.details is None:
            self.details = []
        if self.patient_identifiers is None:
            self.patient_identifiers = {}
        if self.query_continuation is None:
            self.query_continuation = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the acknowledgment response.
            
        Example:
            >>> response = AcknowledgmentResponse(status="AA", is_success=True)
            >>> data = response.to_dict()
            >>> print(data["status"])
            AA
        """
        return {
            "status": self.status,
            "is_success": self.is_success,
            "message_id": self.message_id,
            "target_message_id": self.target_message_id,
            "details": [
                {
                    "type_code": d.type_code,
                    "text": d.text,
                    "code": d.code,
                    "code_system": d.code_system
                }
                for d in self.details
            ],
            "patient_identifiers": self.patient_identifiers,
            "query_continuation": self.query_continuation
        }


def _extract_patient_identifiers(root: etree.Element) -> dict:
    """Extract patient identifiers from acknowledgment response.
    
    Parses the controlActProcess/subject section to find patient ID
    elements returned by the PIX Manager. Handles multiple identifiers
    from different assigning authorities.
    
    Args:
        root: Parsed lxml Element of MCCI_IN000002UV01 message
        
    Returns:
        Dictionary with patient identifiers:
        {
            "patient_id": "PAT123456",
            "patient_id_root": "2.16.840.1.113883.3.72.5.9.1",
            "additional_ids": [
                {"root": "1.2.840.114350.1.13.99998.8734", "extension": "EID987654"}
            ]
        }
        Returns empty dict if no identifiers found.
        
    Example:
        >>> root = etree.fromstring(acknowledgment_xml)
        >>> ids = _extract_patient_identifiers(root)
        >>> print(ids["patient_id"])
        PAT123456
    """
    identifiers = {}
    
    # Find patient elements in controlActProcess section
    patient_elems = root.findall(
        f".//{{{HL7_NS}}}controlActProcess"
        f"//{{{HL7_NS}}}subject"
        f"//{{{HL7_NS}}}registrationEvent"
        f"//{{{HL7_NS}}}subject1"
        f"//{{{HL7_NS}}}patient"
        f"//{{{HL7_NS}}}id"
    )
    
    if not patient_elems:
        logger.debug("No patient identifiers found in acknowledgment")
        return identifiers
    
    # Extract first patient ID as primary
    first_id = patient_elems[0]
    patient_id_root = first_id.get("root")
    patient_id_ext = first_id.get("extension")
    
    if patient_id_ext:
        identifiers["patient_id"] = patient_id_ext
        identifiers["patient_id_root"] = patient_id_root
        logger.info(f"Extracted primary patient ID: {patient_id_ext} (root: {patient_id_root})")
    
    # Extract additional IDs if present
    if len(patient_elems) > 1:
        additional_ids = []
        for id_elem in patient_elems[1:]:
            id_root = id_elem.get("root")
            id_ext = id_elem.get("extension")
            if id_root and id_ext:
                additional_ids.append({"root": id_root, "extension": id_ext})
                logger.debug(f"Extracted additional patient ID: {id_ext} (root: {id_root})")
        
        if additional_ids:
            identifiers["additional_ids"] = additional_ids
    
    return identifiers


def _extract_query_continuation(root: etree.Element) -> Optional[dict]:
    """Extract query continuation information from acknowledgment.
    
    Parses the controlActProcess/queryAck section for query continuation
    details. This is used in PIX Query transactions (ITI-45) but may also
    appear in PIX Add acknowledgments.
    
    Args:
        root: Parsed lxml Element of MCCI_IN000002UV01 message
        
    Returns:
        Dictionary with query continuation information:
        {
            "query_response_code": "OK",
            "result_total_quantity": 1,
            "result_current_quantity": 1,
            "result_remaining_quantity": 0
        }
        Returns None if no query continuation data present.
        
    Example:
        >>> root = etree.fromstring(acknowledgment_xml)
        >>> continuation = _extract_query_continuation(root)
        >>> if continuation:
        ...     print(continuation["query_response_code"])
        OK
    """
    query_ack_elem = root.find(
        f".//{{{HL7_NS}}}controlActProcess"
        f"//{{{HL7_NS}}}queryAck"
    )
    
    if query_ack_elem is None:
        logger.debug("No query continuation information found")
        return None
    
    continuation = {}
    
    # Extract query response code (OK, NF, QE, AE)
    response_code_elem = query_ack_elem.find(f".//{{{HL7_NS}}}queryResponseCode")
    if response_code_elem is not None:
        response_code = response_code_elem.get("code")
        if response_code:
            continuation["query_response_code"] = response_code
            logger.debug(f"Query response code: {response_code}")
    
    # Extract result quantities
    total_elem = query_ack_elem.find(f".//{{{HL7_NS}}}resultTotalQuantity")
    if total_elem is not None:
        total_value = total_elem.get("value")
        if total_value:
            try:
                continuation["result_total_quantity"] = int(total_value)
            except ValueError:
                logger.warning(f"Invalid resultTotalQuantity value: {total_value}")
    
    current_elem = query_ack_elem.find(f".//{{{HL7_NS}}}resultCurrentQuantity")
    if current_elem is not None:
        current_value = current_elem.get("value")
        if current_value:
            try:
                continuation["result_current_quantity"] = int(current_value)
            except ValueError:
                logger.warning(f"Invalid resultCurrentQuantity value: {current_value}")
    
    remaining_elem = query_ack_elem.find(f".//{{{HL7_NS}}}resultRemainingQuantity")
    if remaining_elem is not None:
        remaining_value = remaining_elem.get("value")
        if remaining_value:
            try:
                continuation["result_remaining_quantity"] = int(remaining_value)
            except ValueError:
                logger.warning(f"Invalid resultRemainingQuantity value: {remaining_value}")
    
    if continuation:
        logger.info(f"Extracted query continuation: {continuation}")
        return continuation
    
    return None


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
        raise ValueError(
            f"Invalid acknowledgment XML: {e}. "
            "Check if response is valid HL7v3 MCCI_IN000002UV01 message."
        ) from e
    
    # Validate HL7v3 namespace and determine actual namespace to use
    actual_ns = root.nsmap.get(None, HL7_NS)
    if actual_ns != HL7_NS and root.tag != f"{{{HL7_NS}}}MCCI_IN000002UV01":
        logger.warning(
            f"Unexpected namespace or root element. Expected MCCI_IN000002UV01 "
            f"with namespace {HL7_NS}, got: {root.tag}. "
            "Attempting to parse with actual namespace."
        )
    
    # Extract message ID from root (try both HL7 NS and actual NS)
    message_id = None
    id_elem = root.find(f".//{{{HL7_NS}}}id")
    if id_elem is None:
        id_elem = root.find(f".//{{{actual_ns}}}id")
    if id_elem is not None:
        msg_id_root = id_elem.get("root")
        msg_id_ext = id_elem.get("extension")
        if msg_id_root:
            message_id = msg_id_root
            if msg_id_ext:
                message_id = f"{msg_id_root}::{msg_id_ext}"
    
    # Find acknowledgement element (try both HL7 NS and actual NS)
    ack_elem = root.find(f".//{{{HL7_NS}}}acknowledgement")
    if ack_elem is None:
        ack_elem = root.find(f".//{{{actual_ns}}}acknowledgement")
    if ack_elem is None:
        raise ValueError(
            "No acknowledgement element found in response. "
            "Expected element: <acknowledgement> with namespace urn:hl7-org:v3"
        )
    
    # Extract status code (try both HL7 NS and actual NS)
    type_code_elem = ack_elem.find(f".//{{{HL7_NS}}}typeCode")
    if type_code_elem is None:
        type_code_elem = ack_elem.find(f".//{{{actual_ns}}}typeCode")
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
    
    # Extract target message ID (try both HL7 NS and actual NS)
    target_message_id = None
    target_msg_elem = ack_elem.find(f".//{{{HL7_NS}}}targetMessage")
    if target_msg_elem is None:
        target_msg_elem = ack_elem.find(f".//{{{actual_ns}}}targetMessage")
    if target_msg_elem is not None:
        target_id_elem = target_msg_elem.find(f".//{{{HL7_NS}}}id")
        if target_id_elem is None:
            target_id_elem = target_msg_elem.find(f".//{{{actual_ns}}}id")
        if target_id_elem is not None:
            target_id_root = target_id_elem.get("root")
            target_id_ext = target_id_elem.get("extension")
            if target_id_root:
                target_message_id = target_id_root
                if target_id_ext:
                    target_message_id = f"{target_id_root}::{target_id_ext}"
    
    # Extract acknowledgment details (errors, warnings, info) (try both HL7 NS and actual NS)
    details = []
    detail_elems = ack_elem.findall(f".//{{{HL7_NS}}}acknowledgementDetail")
    if not detail_elems:
        detail_elems = ack_elem.findall(f".//{{{actual_ns}}}acknowledgementDetail")
    for detail_elem in detail_elems:
        # Get type code
        detail_type_code = detail_elem.get("typeCode", "E")  # Default to Error
        
        # Get text
        text_elem = detail_elem.find(f".//{{{HL7_NS}}}text")
        if text_elem is None:
            text_elem = detail_elem.find(f".//{{{actual_ns}}}text")
        text = text_elem.text if text_elem is not None and text_elem.text else "No detail message provided"
        
        # Get code (optional)
        code_elem = detail_elem.find(f".//{{{HL7_NS}}}code")
        if code_elem is None:
            code_elem = detail_elem.find(f".//{{{actual_ns}}}code")
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
    
    # Extract patient identifiers
    patient_identifiers = _extract_patient_identifiers(root)
    
    # Extract query continuation information
    query_continuation = _extract_query_continuation(root)
    
    # Create response object
    response = AcknowledgmentResponse(
        status=status,
        is_success=is_success,
        message_id=message_id,
        target_message_id=target_message_id,
        details=details,
        patient_identifiers=patient_identifiers,
        query_continuation=query_continuation
    )
    
    logger.info(
        f"Parsed acknowledgment: status={status}, success={is_success}, "
        f"details_count={len(details)}, patient_ids={len(patient_identifiers)}, "
        f"has_query_continuation={query_continuation is not None}"
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
