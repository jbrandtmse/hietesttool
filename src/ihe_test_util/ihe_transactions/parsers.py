"""Response parsers for IHE transactions (acknowledgments and registry responses)."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from lxml import etree

logger = logging.getLogger(__name__)

# HL7v3 namespaces
HL7_NS = "urn:hl7-org:v3"

# SOAP namespaces
SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
SOAP_11_NS = "http://schemas.xmlsoap.org/soap/envelope/"

# XDSb/ebXML namespaces
RS_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"
RIM_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
WSA_NS = "http://www.w3.org/2005/08/addressing"

# XDSb Registry Response status URIs
REGISTRY_SUCCESS = "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"
REGISTRY_FAILURE = "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Failure"
REGISTRY_PARTIAL_SUCCESS = "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:PartialSuccess"

# XDSb Error Severity URIs
ERROR_SEVERITY_ERROR = "urn:oasis:names:tc:ebxml-regrep:ErrorSeverityType:Error"
ERROR_SEVERITY_WARNING = "urn:oasis:names:tc:ebxml-regrep:ErrorSeverityType:Warning"

# XDSb Identification Scheme UUIDs (IHE ITI TF-3)
DOCUMENT_UNIQUE_ID_SCHEME = "urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab"
SUBMISSION_SET_UNIQUE_ID_SCHEME = "urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8"
PATIENT_ID_SCHEME = "urn:uuid:6b5aea1a-874d-4603-a4bc-96a0a7b38446"

# Audit loggers
audit_logger = logging.getLogger('ihe_test_util.audit.acknowledgments')
registry_audit_logger = logging.getLogger('ihe_test_util.audit.registry')


@dataclass
class SOAPFaultInfo:
    """Parsed SOAP fault information.
    
    Attributes:
        fault_code: SOAP fault code (e.g., "SOAP-ENV:Sender", "SOAP-ENV:Receiver")
        fault_string: Human-readable fault message
        fault_detail: Optional detailed fault information
        fault_actor: Optional fault actor/role
        subcodes: Optional list of fault subcodes
        
    Example:
        >>> fault_info = parse_soap_fault(response_xml)
        >>> print(fault_info.fault_code)
        SOAP-ENV:Sender
        >>> print(fault_info.fault_string)
        Invalid SAML assertion
    """
    
    fault_code: str
    fault_string: str
    fault_detail: Optional[str] = None
    fault_actor: Optional[str] = None
    subcodes: List[str] = None
    
    def __post_init__(self):
        """Initialize subcodes list if None."""
        if self.subcodes is None:
            self.subcodes = []


@dataclass
class HL7ErrorInfo:
    """HL7v3 acknowledgment error information.
    
    Attributes:
        code: HL7 error code (e.g., "204", "205")
        text: Human-readable error message
        location: Optional XPath location of error in message
        severity: Error severity (E=Error, W=Warning, I=Info)
        code_system: Optional code system OID
        
    Example:
        >>> error_info = HL7ErrorInfo(
        ...     code="204",
        ...     text="Unknown key identifier",
        ...     severity="E"
        ... )
    """
    
    code: Optional[str]
    text: str
    location: Optional[str] = None
    severity: str = "E"
    code_system: Optional[str] = None


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


def parse_soap_fault(fault_xml: str) -> SOAPFaultInfo:
    """Parse SOAP fault from response XML.
    
    Parses both SOAP 1.1 and SOAP 1.2 fault structures, extracting
    fault code, fault string, details, and actor information.
    
    Args:
        fault_xml: XML string containing SOAP envelope with fault
        
    Returns:
        SOAPFaultInfo with parsed fault details
        
    Raises:
        ValueError: If XML is malformed or not a SOAP fault
        
    Example:
        >>> fault_info = parse_soap_fault(response_xml)
        >>> print(f"Fault: {fault_info.fault_code} - {fault_info.fault_string}")
    """
    logger.info("Parsing SOAP fault")
    
    try:
        # Parse XML
        if isinstance(fault_xml, bytes):
            root = etree.fromstring(fault_xml)
        else:
            root = etree.fromstring(fault_xml.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise ValueError(
            f"Invalid SOAP fault XML: {e}. "
            "Response is not valid XML."
        ) from e
    
    # Try SOAP 1.2 first, then SOAP 1.1
    fault_elem = root.find(f".//{{{SOAP_NS}}}Fault")
    soap_version = "1.2"
    
    if fault_elem is None:
        fault_elem = root.find(f".//{{{SOAP_11_NS}}}Fault")
        soap_version = "1.1"
    
    if fault_elem is None:
        raise ValueError(
            "No SOAP Fault element found in response. "
            "Expected <SOAP-ENV:Fault> element in SOAP envelope."
        )
    
    logger.debug(f"Parsing SOAP {soap_version} fault")
    
    # Parse based on SOAP version
    if soap_version == "1.2":
        fault_info = _parse_soap_12_fault(fault_elem)
    else:
        fault_info = _parse_soap_11_fault(fault_elem)
    
    # Log complete fault for audit trail (RULE 2)
    logger.error(
        f"SOAP Fault received - Code: {fault_info.fault_code}, "
        f"Message: {fault_info.fault_string}"
    )
    
    if fault_info.fault_detail:
        logger.error(f"Fault Detail: {fault_info.fault_detail}")
    
    if fault_info.subcodes:
        logger.error(f"Fault Subcodes: {', '.join(fault_info.subcodes)}")
    
    return fault_info


def _parse_soap_12_fault(fault_elem: etree.Element) -> SOAPFaultInfo:
    """Parse SOAP 1.2 fault structure.
    
    Args:
        fault_elem: SOAP:Fault element
        
    Returns:
        SOAPFaultInfo with parsed fault details
    """
    # Extract fault code
    code_elem = fault_elem.find(f".//{{{SOAP_NS}}}Code/{{{SOAP_NS}}}Value")
    fault_code = code_elem.text if code_elem is not None else "Unknown"
    
    # Extract subcodes
    subcodes = []
    subcode_elems = fault_elem.findall(f".//{{{SOAP_NS}}}Subcode/{{{SOAP_NS}}}Value")
    for subcode_elem in subcode_elems:
        if subcode_elem.text:
            subcodes.append(subcode_elem.text)
    
    # Extract fault string (reason)
    reason_elem = fault_elem.find(f".//{{{SOAP_NS}}}Reason/{{{SOAP_NS}}}Text")
    fault_string = reason_elem.text if reason_elem is not None else "No fault message provided"
    
    # Extract fault detail
    detail_elem = fault_elem.find(f".//{{{SOAP_NS}}}Detail")
    fault_detail = None
    if detail_elem is not None:
        # Get text content or serialize children
        if detail_elem.text and detail_elem.text.strip():
            fault_detail = detail_elem.text.strip()
        else:
            # Serialize child elements
            detail_parts = []
            for child in detail_elem:
                if child.text and child.text.strip():
                    detail_parts.append(child.text.strip())
            if detail_parts:
                fault_detail = "; ".join(detail_parts)
    
    # Extract fault actor (role in SOAP 1.2)
    role_elem = fault_elem.find(f".//{{{SOAP_NS}}}Role")
    fault_actor = role_elem.text if role_elem is not None else None
    
    return SOAPFaultInfo(
        fault_code=fault_code,
        fault_string=fault_string,
        fault_detail=fault_detail,
        fault_actor=fault_actor,
        subcodes=subcodes
    )


def _parse_soap_11_fault(fault_elem: etree.Element) -> SOAPFaultInfo:
    """Parse SOAP 1.1 fault structure.
    
    Args:
        fault_elem: SOAP:Fault element
        
    Returns:
        SOAPFaultInfo with parsed fault details
    """
    # Extract faultcode
    faultcode_elem = fault_elem.find("faultcode")
    fault_code = faultcode_elem.text if faultcode_elem is not None else "Unknown"
    
    # Extract faultstring
    faultstring_elem = fault_elem.find("faultstring")
    fault_string = faultstring_elem.text if faultstring_elem is not None else "No fault message provided"
    
    # Extract detail
    detail_elem = fault_elem.find("detail")
    fault_detail = None
    if detail_elem is not None:
        if detail_elem.text and detail_elem.text.strip():
            fault_detail = detail_elem.text.strip()
        else:
            # Serialize child elements
            detail_parts = []
            for child in detail_elem:
                if child.text and child.text.strip():
                    detail_parts.append(child.text.strip())
            if detail_parts:
                fault_detail = "; ".join(detail_parts)
    
    # Extract faultactor
    faultactor_elem = fault_elem.find("faultactor")
    fault_actor = faultactor_elem.text if faultactor_elem is not None else None
    
    return SOAPFaultInfo(
        fault_code=fault_code,
        fault_string=fault_string,
        fault_detail=fault_detail,
        fault_actor=fault_actor,
        subcodes=[]
    )


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


@dataclass
class RegistryErrorInfo:
    """XDSb registry error information.
    
    Represents an error or warning from an XDSb RegistryResponse.
    
    Attributes:
        error_code: XDSb error code (e.g., "XDSMissingDocument", "XDSPatientIdDoesNotMatch")
        code_context: Human-readable error context message
        severity: Error severity ("Error" or "Warning")
        location: Optional location reference within the request
        
    Example:
        >>> error_info = RegistryErrorInfo(
        ...     error_code="XDSMissingDocument",
        ...     code_context="Document with id 'doc001' not found",
        ...     severity="Error"
        ... )
    """
    
    error_code: str
    code_context: str
    severity: str = "Error"
    location: Optional[str] = None


@dataclass
class RegistryResponse:
    """Parsed XDSb registry response.
    
    Contains the parsed results from an ITI-41 (Provide and Register Document Set-b)
    registry response, including status, document identifiers, and error details.
    
    Attributes:
        status: Registry response status (Success, Failure, PartialSuccess)
        is_success: True if status indicates success
        response_id: Optional response message ID from WS-Addressing
        submission_set_id: Optional submission set unique ID
        document_ids: List of document unique IDs from successful submissions
        errors: List of RegistryErrorInfo for errors
        warnings: List of RegistryErrorInfo for warnings
        request_id: Optional request ID for correlation (from RelatesTo header)
        
    Example:
        >>> response = parse_registry_response(response_xml)
        >>> if response.is_success:
        ...     logger.info(f"Documents submitted: {response.document_ids}")
        >>> else:
        ...     for error in response.errors:
        ...         logger.error(f"{error.error_code}: {error.code_context}")
    """
    
    status: str
    is_success: bool
    response_id: Optional[str] = None
    submission_set_id: Optional[str] = None
    document_ids: List[str] = field(default_factory=list)
    errors: List[RegistryErrorInfo] = field(default_factory=list)
    warnings: List[RegistryErrorInfo] = field(default_factory=list)
    request_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the registry response.
            
        Example:
            >>> response = RegistryResponse(status="Success", is_success=True)
            >>> data = response.to_dict()
            >>> print(data["status"])
            Success
        """
        return {
            "status": self.status,
            "is_success": self.is_success,
            "response_id": self.response_id,
            "submission_set_id": self.submission_set_id,
            "document_ids": self.document_ids,
            "errors": [
                {
                    "error_code": e.error_code,
                    "code_context": e.code_context,
                    "severity": e.severity,
                    "location": e.location,
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "error_code": w.error_code,
                    "code_context": w.code_context,
                    "severity": w.severity,
                    "location": w.location,
                }
                for w in self.warnings
            ],
            "request_id": self.request_id,
        }


def log_registry_response(
    response_xml: str,
    status: str,
    submission_set_id: Optional[str] = None,
) -> None:
    """Log complete registry response to audit trail.
    
    Logs ITI-41 and other XDSb registry responses to dedicated audit file.
    Follows RULE 2: All IHE transactions MUST log complete request/response.
    
    Args:
        response_xml: Complete SOAP/XML response
        status: Registry response status (Success, Failure, PartialSuccess)
        submission_set_id: Optional submission set ID for correlation
        
    Example:
        >>> log_registry_response(response_xml, "Success", "1.2.3.4.5.6")
    """
    # Ensure log directory exists
    log_dir = Path("logs/transactions")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create dated log file
    log_file = log_dir / f"iti41-responses-{datetime.now().strftime('%Y%m%d')}.log"
    
    # Configure audit logger if not already configured
    if not registry_audit_logger.handlers:
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        registry_audit_logger.addHandler(handler)
        registry_audit_logger.setLevel(logging.DEBUG)
    
    # Log summary at INFO level
    submission_info = f", SubmissionSetID: {submission_set_id}" if submission_set_id else ""
    registry_audit_logger.info(
        f"ITI-41 Registry Response - Status: {status}{submission_info}, "
        f"Size: {len(response_xml)} bytes"
    )
    
    # Log complete response XML at DEBUG level (RULE 2)
    registry_audit_logger.debug(
        f"Response XML (SubmissionSetID: {submission_set_id}):\n{response_xml}"
    )


def _map_registry_status_to_string(status_uri: str) -> str:
    """Map XDSb registry status URI to human-readable string.
    
    Args:
        status_uri: XDSb registry status URI
        
    Returns:
        Human-readable status string: Success, Failure, or PartialSuccess
    """
    if status_uri == REGISTRY_SUCCESS:
        return "Success"
    elif status_uri == REGISTRY_FAILURE:
        return "Failure"
    elif status_uri == REGISTRY_PARTIAL_SUCCESS:
        return "PartialSuccess"
    else:
        # Log unknown status but return it as-is
        logger.warning(f"Unknown registry status URI: {status_uri}")
        return status_uri


def _map_error_severity_to_string(severity_uri: str) -> str:
    """Map XDSb error severity URI to human-readable string.
    
    Args:
        severity_uri: XDSb error severity URI
        
    Returns:
        Human-readable severity string: Error or Warning
    """
    if severity_uri == ERROR_SEVERITY_ERROR:
        return "Error"
    elif severity_uri == ERROR_SEVERITY_WARNING:
        return "Warning"
    else:
        # Extract last part of URI or return as-is
        if ":" in severity_uri:
            return severity_uri.split(":")[-1]
        return severity_uri


def _extract_document_ids(root: etree._Element) -> List[str]:
    """Extract document unique IDs from registry response.
    
    Parses ExtrinsicObject elements to find document entries and extracts
    their unique IDs using the XDSDocumentEntry.uniqueId identification scheme.
    
    Args:
        root: Parsed lxml Element of SOAP response
        
    Returns:
        List of document unique IDs
    """
    document_ids = []
    
    # Find all ExternalIdentifier elements with the document uniqueId scheme
    xpath = (
        f".//{{{RIM_NS}}}ExtrinsicObject"
        f"/{{{RIM_NS}}}ExternalIdentifier"
        f"[@identificationScheme='{DOCUMENT_UNIQUE_ID_SCHEME}']"
    )
    
    external_ids = root.findall(xpath)
    
    for ext_id in external_ids:
        value = ext_id.get("value")
        if value:
            document_ids.append(value)
            logger.debug(f"Extracted document unique ID: {value}")
    
    if document_ids:
        logger.info(f"Extracted {len(document_ids)} document unique ID(s)")
    else:
        logger.debug("No document unique IDs found in response")
    
    return document_ids


def _extract_submission_set_id(root: etree._Element) -> Optional[str]:
    """Extract submission set unique ID from registry response.
    
    Parses RegistryPackage elements to find the submission set and extracts
    its unique ID using the XDSSubmissionSet.uniqueId identification scheme.
    
    Args:
        root: Parsed lxml Element of SOAP response
        
    Returns:
        Submission set unique ID or None if not found
    """
    # Find ExternalIdentifier with submission set uniqueId scheme
    xpath = (
        f".//{{{RIM_NS}}}RegistryPackage"
        f"/{{{RIM_NS}}}ExternalIdentifier"
        f"[@identificationScheme='{SUBMISSION_SET_UNIQUE_ID_SCHEME}']"
    )
    
    ext_id = root.find(xpath)
    
    if ext_id is not None:
        value = ext_id.get("value")
        if value:
            logger.info(f"Extracted submission set unique ID: {value}")
            return value
    
    logger.debug("No submission set unique ID found in response")
    return None


def _extract_error_list(
    registry_response: etree._Element,
) -> tuple[List[RegistryErrorInfo], List[RegistryErrorInfo]]:
    """Extract errors and warnings from RegistryErrorList.
    
    Parses the RegistryErrorList element and categorizes items by severity.
    
    Args:
        registry_response: RegistryResponse element
        
    Returns:
        Tuple of (errors, warnings) lists
    """
    errors: List[RegistryErrorInfo] = []
    warnings: List[RegistryErrorInfo] = []
    
    error_list = registry_response.find(f".//{{{RS_NS}}}RegistryErrorList")
    
    if error_list is None:
        logger.debug("No RegistryErrorList found in response")
        return errors, warnings
    
    for error_elem in error_list.findall(f".//{{{RS_NS}}}RegistryError"):
        error_code = error_elem.get("errorCode", "Unknown")
        code_context = error_elem.get("codeContext", "No context provided")
        severity_uri = error_elem.get("severity", ERROR_SEVERITY_ERROR)
        location = error_elem.get("location")
        
        severity = _map_error_severity_to_string(severity_uri)
        
        error_info = RegistryErrorInfo(
            error_code=error_code,
            code_context=code_context,
            severity=severity,
            location=location,
        )
        
        # Categorize by severity
        if severity == "Warning":
            warnings.append(error_info)
            logger.warning(
                f"Registry warning [{error_code}]: {code_context}"
                + (f" (location: {location})" if location else "")
            )
        else:
            errors.append(error_info)
            logger.error(
                f"Registry error [{error_code}]: {code_context}"
                + (f" (location: {location})" if location else "")
            )
    
    logger.info(f"Extracted {len(errors)} error(s) and {len(warnings)} warning(s)")
    return errors, warnings


def _extract_request_correlation(root: etree._Element) -> Optional[str]:
    """Extract request ID from WS-Addressing RelatesTo header.
    
    Args:
        root: Parsed lxml Element of SOAP response
        
    Returns:
        Request ID from RelatesTo header or None if not found
    """
    relates_to = root.find(f".//{{{WSA_NS}}}RelatesTo")
    
    if relates_to is not None and relates_to.text:
        request_id = relates_to.text
        logger.debug(f"Extracted request correlation ID: {request_id}")
        return request_id
    
    logger.debug("No WS-Addressing RelatesTo header found")
    return None


def _extract_response_id(root: etree._Element) -> Optional[str]:
    """Extract response message ID from WS-Addressing MessageID header.
    
    Args:
        root: Parsed lxml Element of SOAP response
        
    Returns:
        Response message ID or None if not found
    """
    message_id = root.find(f".//{{{WSA_NS}}}MessageID")
    
    if message_id is not None and message_id.text:
        response_id = message_id.text
        logger.debug(f"Extracted response message ID: {response_id}")
        return response_id
    
    logger.debug("No WS-Addressing MessageID header found")
    return None


def parse_registry_response(response_xml: str) -> RegistryResponse:
    """Parse XDSb RegistryResponse from ITI-41 SOAP response.
    
    Parses the registry response from an ITI-41 (Provide and Register Document Set-b)
    transaction, extracting status, document identifiers, submission set ID,
    and any errors or warnings.
    
    Args:
        response_xml: Complete SOAP response XML string
        
    Returns:
        RegistryResponse with parsed status, IDs, and errors
        
    Raises:
        ValueError: If XML is malformed or missing required elements
        
    Example:
        >>> response = parse_registry_response(soap_response_xml)
        >>> if response.is_success:
        ...     logger.info(f"Submission successful: {response.submission_set_id}")
        >>> else:
        ...     for error in response.errors:
        ...         logger.error(f"Error: {error.error_code} - {error.code_context}")
    """
    logger.info("Parsing XDSb registry response")
    
    # Parse XML
    try:
        if isinstance(response_xml, bytes):
            root = etree.fromstring(response_xml)
        else:
            root = etree.fromstring(response_xml.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise ValueError(
            f"Invalid registry response XML: {e}. "
            "Check if response is valid SOAP envelope with XDSb RegistryResponse. "
            "Verify the XDSb repository endpoint is responding correctly."
        ) from e
    
    # Check for SOAP Fault first
    soap_fault = root.find(f".//{{{SOAP_NS}}}Fault")
    if soap_fault is not None:
        # Extract fault details
        fault_code_elem = soap_fault.find(f".//{{{SOAP_NS}}}Code/{{{SOAP_NS}}}Value")
        fault_reason_elem = soap_fault.find(f".//{{{SOAP_NS}}}Reason/{{{SOAP_NS}}}Text")
        
        fault_code = fault_code_elem.text if fault_code_elem is not None else "Unknown"
        fault_reason = fault_reason_elem.text if fault_reason_elem is not None else "Unknown error"
        
        logger.error(f"SOAP Fault received: {fault_code} - {fault_reason}")
        
        # Log the response for audit
        log_registry_response(response_xml, "SOAP Fault")
        
        # Create error response
        error_info = RegistryErrorInfo(
            error_code=f"SOAP:{fault_code}",
            code_context=fault_reason,
            severity="Error",
        )
        
        return RegistryResponse(
            status="Failure",
            is_success=False,
            response_id=_extract_response_id(root),
            errors=[error_info],
            request_id=_extract_request_correlation(root),
        )
    
    # Find RegistryResponse element
    registry_response = root.find(f".//{{{RS_NS}}}RegistryResponse")
    
    if registry_response is None:
        raise ValueError(
            "No RegistryResponse element found in SOAP response. "
            "Expected element: <rs:RegistryResponse> with namespace "
            f"'{RS_NS}'. Verify the XDSb repository returned a valid response."
        )
    
    # Extract status
    status_uri = registry_response.get("status", "")
    if not status_uri:
        raise ValueError(
            "RegistryResponse element missing 'status' attribute. "
            "Expected attribute with value like "
            "'urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success'. "
            "Check XDSb repository response format."
        )
    
    status = _map_registry_status_to_string(status_uri)
    is_success = status == "Success"
    
    # Log status at appropriate level
    if is_success:
        logger.info(f"Registry response status: {status}")
    elif status == "PartialSuccess":
        logger.warning(f"Registry response status: {status} (some items may have failed)")
    else:
        logger.error(f"Registry response status: {status}")
    
    # Extract response and request IDs for correlation
    response_id = _extract_response_id(root)
    request_id = _extract_request_correlation(root)
    
    # Extract document IDs and submission set ID
    document_ids = _extract_document_ids(root)
    submission_set_id = _extract_submission_set_id(root)
    
    # Extract errors and warnings
    errors, warnings = _extract_error_list(registry_response)
    
    # Log complete response for audit (RULE 2)
    log_registry_response(response_xml, status, submission_set_id)
    
    # Create response object
    response = RegistryResponse(
        status=status,
        is_success=is_success,
        response_id=response_id,
        submission_set_id=submission_set_id,
        document_ids=document_ids,
        errors=errors,
        warnings=warnings,
        request_id=request_id,
    )
    
    logger.info(
        f"Parsed registry response: status={status}, success={is_success}, "
        f"document_count={len(document_ids)}, submission_set_id={submission_set_id}, "
        f"error_count={len(errors)}, warning_count={len(warnings)}"
    )
    
    return response
