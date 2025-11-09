"""Mock ITI-41 endpoint for testing document submission.

This module implements a mock XDSb Provide and Register Document Set-b endpoint
that accepts MTOM-encoded SOAP messages with CCD document attachments.
"""

import logging
import random
import time
import uuid
from datetime import datetime, timezone
from email import message_from_bytes
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, request, g
from lxml import etree

from .config import MockServerConfig, ValidationMode


# Create Blueprint
iti41_bp = Blueprint("iti41", __name__)

# Configure logger for ITI-41 endpoint
logger = logging.getLogger("ihe_test_util.mock_server.iti41")

# XDSb namespaces
SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
LCM_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0"
RIM_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"
RS_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"
XOP_NS = "http://www.w3.org/2004/08/xop/include"

NSMAP = {
    "soap": SOAP_NS,
    "lcm": LCM_NS,
    "rim": RIM_NS,
    "rs": RS_NS,
    "xop": XOP_NS,
}


def extract_mtom_parts(request_data: bytes, content_type: str) -> dict[str, Any]:
    """Extract SOAP envelope and document attachment from MTOM multipart message.
    
    Args:
        request_data: Raw MTOM multipart message bytes
        content_type: Content-Type header value
        
    Returns:
        Dictionary containing:
            - soap_envelope: SOAP envelope XML string
            - document_attachment: CCD document XML string
            - document_content_id: Content-ID of the document attachment
            
    Raises:
        ValueError: If MTOM structure is invalid or parts are missing
    """
    logger.debug("Parsing MTOM multipart message")

    # Parse multipart message using email.mime
    try:
        # Construct full message with headers for email parser
        full_message = f"Content-Type: {content_type}\r\n\r\n".encode() + request_data
        msg = message_from_bytes(full_message)
    except Exception as e:
        raise ValueError(
            f"Failed to parse MTOM multipart message: {e}. "
            f"Ensure the message is properly formatted as multipart/related."
        )

    if not msg.is_multipart():
        raise ValueError(
            "Expected multipart/related MTOM message but received non-multipart content. "
            "Ensure Content-Type is multipart/related with proper boundary."
        )

    soap_envelope = None
    document_attachment = None
    document_content_id = None
    parts_found = []

    # Iterate through MIME parts
    for part in msg.walk():
        if part.is_multipart():
            continue

        part_content_type = part.get_content_type()
        content_id = part.get("Content-ID", "").strip("<>")
        parts_found.append(part_content_type)

        logger.debug(f"Found MIME part: Content-Type={part_content_type}, Content-ID={content_id}")

        # Extract SOAP envelope (application/xop+xml)
        if part_content_type == "application/xop+xml" or "soap" in part_content_type:
            try:
                soap_envelope = part.get_payload(decode=True).decode("utf-8")
                logger.debug(f"Extracted SOAP envelope ({len(soap_envelope)} bytes)")
            except Exception as e:
                raise ValueError(f"Failed to decode SOAP envelope: {e}")

        # Extract document attachment (text/xml or application/xml)
        elif part_content_type in ["text/xml", "application/xml"]:
            try:
                document_attachment = part.get_payload(decode=True).decode("utf-8")
                document_content_id = content_id
                logger.debug(
                    f"Extracted document attachment ({len(document_attachment)} bytes), "
                    f"Content-ID={content_id}"
                )
            except Exception as e:
                raise ValueError(f"Failed to decode document attachment: {e}")

    # Validate required parts were found
    if soap_envelope is None:
        raise ValueError(
            f"Missing SOAP envelope in MTOM message. Found parts: {parts_found}. "
            f"Ensure multipart message includes application/xop+xml part."
        )

    if document_attachment is None:
        raise ValueError(
            f"Missing CCD document attachment in MTOM message. Found parts: {parts_found}. "
            f"Ensure multipart message includes text/xml or application/xml part with document content."
        )

    logger.info("Successfully extracted MTOM parts")

    return {
        "soap_envelope": soap_envelope,
        "document_attachment": document_attachment,
        "document_content_id": document_content_id,
    }


def extract_xdsb_metadata(soap_xml: str) -> dict[str, Any]:
    """Extract XDSb metadata from ProvideAndRegisterDocumentSetRequest.
    
    Args:
        soap_xml: SOAP envelope XML string
        
    Returns:
        Dictionary containing extracted metadata:
            - submission_set_id: Submission set unique ID
            - document_unique_id: Document unique ID
            - patient_id: Patient identifier
            - source_id: Source identifier
            - content_id_reference: xop:Include href reference
            - class_code: Document class code (optional)
            - type_code: Document type code (optional)
            - format_code: Document format code (optional)
            - mime_type: Document MIME type (optional)
            
    Raises:
        ValueError: If required metadata is missing or XML is malformed
    """
    logger.debug("Extracting XDSb metadata from SOAP envelope")

    try:
        tree = etree.fromstring(soap_xml.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise ValueError(
            f"Failed to parse SOAP XML: {e}. Ensure the SOAP envelope is valid XML."
        )

    metadata: dict[str, Any] = {}

    # Extract SubmitObjectsRequest
    submit_objects = tree.xpath(
        "//lcm:SubmitObjectsRequest",
        namespaces=NSMAP
    )
    if not submit_objects:
        raise ValueError(
            "Missing SubmitObjectsRequest element in SOAP body. "
            "Ensure the message is a valid XDSb ProvideAndRegisterDocumentSetRequest."
        )

    # Extract Submission Set Unique ID
    submission_set_id = tree.xpath(
        '//rim:RegistryPackage/rim:ExternalIdentifier'
        '[@identificationScheme="urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8"]/@value',
        namespaces=NSMAP
    )
    if submission_set_id:
        metadata["submission_set_id"] = submission_set_id[0]
        logger.debug(f"Submission Set ID: {submission_set_id[0]}")
    else:
        # Generate a default if not provided
        metadata["submission_set_id"] = f"SubmissionSet_{uuid.uuid4().hex[:12]}"
        logger.warning("Submission Set ID not found, generated default")

    # Extract Source ID
    source_id = tree.xpath(
        '//rim:RegistryPackage/rim:ExternalIdentifier'
        '[@identificationScheme="urn:uuid:554ac39e-e3fe-47fe-b233-965d2a147832"]/@value',
        namespaces=NSMAP
    )
    if source_id:
        metadata["source_id"] = source_id[0]
        logger.debug(f"Source ID: {source_id[0]}")

    # Extract Document Unique ID
    document_unique_id = tree.xpath(
        '//rim:ExtrinsicObject/rim:ExternalIdentifier'
        '[@identificationScheme="urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab"]/@value',
        namespaces=NSMAP
    )
    if document_unique_id:
        metadata["document_unique_id"] = document_unique_id[0]
        logger.debug(f"Document Unique ID: {document_unique_id[0]}")
    else:
        # Generate a default if not provided
        metadata["document_unique_id"] = f"Document_{uuid.uuid4().hex[:12]}"
        logger.warning("Document Unique ID not found, generated default")

    # Extract Patient ID
    patient_id = tree.xpath(
        '//rim:ExtrinsicObject/rim:ExternalIdentifier'
        '[@identificationScheme="urn:uuid:58a6f841-87b3-4a3e-92fd-a8ffeff98427"]/@value',
        namespaces=NSMAP
    )
    if patient_id:
        metadata["patient_id"] = patient_id[0]
        logger.debug(f"Patient ID: {patient_id[0]}")

    # Extract Content-ID reference from xop:Include
    content_id_ref = tree.xpath(
        "//rim:ExtrinsicObject//xop:Include/@href",
        namespaces=NSMAP
    )
    if content_id_ref:
        metadata["content_id_reference"] = content_id_ref[0]
        logger.debug(f"Content-ID reference: {content_id_ref[0]}")

    # Extract optional metadata

    # MIME type
    mime_type = tree.xpath("//rim:ExtrinsicObject/@mimeType", namespaces=NSMAP)
    if mime_type:
        metadata["mime_type"] = mime_type[0]

    # Class Code
    class_code = tree.xpath(
        '//rim:Classification[@classificationScheme="urn:uuid:41a5887f-8865-4c09-adf7-e362475b143a"]'
        '/@nodeRepresentation',
        namespaces=NSMAP
    )
    if class_code:
        metadata["class_code"] = class_code[0]

    # Type Code
    type_code = tree.xpath(
        '//rim:Classification[@classificationScheme="urn:uuid:f0306f51-975f-434e-a61c-c59651d33983"]'
        '/@nodeRepresentation',
        namespaces=NSMAP
    )
    if type_code:
        metadata["type_code"] = type_code[0]

    # Format Code
    format_code = tree.xpath(
        '//rim:Classification[@classificationScheme="urn:uuid:a09d5840-386c-46f2-b5ad-9c3699a4309d"]'
        '/@nodeRepresentation',
        namespaces=NSMAP
    )
    if format_code:
        metadata["format_code"] = format_code[0]

    logger.info(f"Extracted XDSb metadata: {len(metadata)} fields")

    return metadata


def generate_registry_response(
    request_id: str,
    submission_set_id: str,
    document_unique_id: str
) -> str:
    """Generate XDSb RegistryResponse with success status.
    
    Args:
        request_id: Original request correlation ID
        submission_set_id: Submission set unique ID
        document_unique_id: Document unique ID
        
    Returns:
        Complete SOAP envelope with RegistryResponse XML string
    """
    logger.debug(f"Generating RegistryResponse for request {request_id}")

    # Generate unique response ID
    response_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build SOAP envelope
    soap_envelope = etree.Element(
        f"{{{SOAP_NS}}}Envelope",
        nsmap={"soap": SOAP_NS}
    )

    soap_body = etree.SubElement(soap_envelope, f"{{{SOAP_NS}}}Body")

    # Build RegistryResponse
    registry_response = etree.SubElement(
        soap_body,
        f"{{{RS_NS}}}RegistryResponse",
        nsmap={"rs": RS_NS, "rim": RIM_NS},
        status="urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success",
        requestId=request_id
    )

    # Add SubmissionSetUniqueId slot
    submission_slot = etree.SubElement(
        registry_response,
        f"{{{RIM_NS}}}Slot",
        name="SubmissionSetUniqueId"
    )
    submission_value_list = etree.SubElement(submission_slot, f"{{{RIM_NS}}}ValueList")
    submission_value = etree.SubElement(submission_value_list, f"{{{RIM_NS}}}Value")
    submission_value.text = submission_set_id

    # Add DocumentUniqueId slot
    document_slot = etree.SubElement(
        registry_response,
        f"{{{RIM_NS}}}Slot",
        name="DocumentUniqueId"
    )
    document_value_list = etree.SubElement(document_slot, f"{{{RIM_NS}}}ValueList")
    document_value = etree.SubElement(document_value_list, f"{{{RIM_NS}}}Value")
    document_value.text = document_unique_id

    # Add ResponseId and Timestamp slots
    response_id_slot = etree.SubElement(registry_response, f"{{{RIM_NS}}}Slot", name="ResponseId")
    response_id_value_list = etree.SubElement(response_id_slot, f"{{{RIM_NS}}}ValueList")
    response_id_value = etree.SubElement(response_id_value_list, f"{{{RIM_NS}}}Value")
    response_id_value.text = response_id

    timestamp_slot = etree.SubElement(registry_response, f"{{{RIM_NS}}}Slot", name="Timestamp")
    timestamp_value_list = etree.SubElement(timestamp_slot, f"{{{RIM_NS}}}ValueList")
    timestamp_value = etree.SubElement(timestamp_value_list, f"{{{RIM_NS}}}Value")
    timestamp_value.text = timestamp

    # Convert to string
    response_xml = etree.tostring(
        soap_envelope,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    ).decode("utf-8")

    logger.info("Generated RegistryResponse with status Success")

    return response_xml


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
    detail_xml = ""
    if detail:
        detail_xml = f"""
      <soap:Detail>
        <error>{detail}</error>
      </soap:Detail>"""

    fault_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <soap:Fault>
      <soap:Code>
        <soap:Value>{faultcode}</soap:Value>
      </soap:Code>
      <soap:Reason>
        <soap:Text xml:lang="en">{faultstring}</soap:Text>
      </soap:Reason>{detail_xml}
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""

    logger.warning(f"Generated SOAP Fault: {faultcode} - {faultstring}")

    return fault_xml


@iti41_bp.route("/iti41/submit", methods=["POST"])
def handle_iti41_submit() -> tuple[Response, int]:
    """Handle ITI-41 Provide and Register Document Set-b request.
    
    Returns:
        Tuple of (Flask Response with RegistryResponse or SOAP fault, HTTP status code)
    """
    logger.info("Received ITI-41 request")

    # Get configuration from Flask context (supports hot-reload) or app config
    from flask import current_app
    config: MockServerConfig = getattr(g, "config", None) or current_app.config.get("MOCK_SERVER_CONFIG")
    
    behavior = config.iti41_behavior if config else None
    
    if behavior:
        logger.debug(
            f"ITI-41 behavior - delay: {behavior.response_delay_ms}ms, "
            f"failure_rate: {behavior.failure_rate}, "
            f"validation: {behavior.validation_mode.value}"
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    request_id = str(uuid.uuid4())

    try:
        # Apply response delay from behavior config
        if behavior and behavior.response_delay_ms > 0:
            logger.debug(f"Simulating network delay: {behavior.response_delay_ms}ms")
            time.sleep(behavior.response_delay_ms / 1000.0)
        
        # Simulate failure rate
        if behavior and behavior.failure_rate > 0:
            if random.random() < behavior.failure_rate:
                fault_message = (
                    behavior.custom_fault_message
                    or "Simulated ITI-41 submission failure for testing"
                )
                logger.info(f"Simulating failure (rate: {behavior.failure_rate})")
                fault_xml = generate_soap_fault("soap:Receiver", fault_message)
                return Response(fault_xml, mimetype="application/soap+xml; charset=utf-8"), 500
        
        # Get request data
        content_type = request.content_type or ""
        request_data = request.data

        logger.debug(f"Content-Type: {content_type}")
        logger.debug(f"Request size: {len(request_data)} bytes")

        # Validate multipart/related content type
        if "multipart/related" not in content_type.lower():
            error_msg = (
                f"Invalid Content-Type '{content_type}'. "
                f"Expected multipart/related for MTOM attachments."
            )
            logger.warning(error_msg)
            fault_xml = generate_soap_fault(
                "soap:Sender",
                "Invalid Content-Type",
                error_msg
            )
            return Response(fault_xml, mimetype="application/soap+xml; charset=utf-8"), 400

        # Extract MTOM parts
        try:
            mtom_parts = extract_mtom_parts(request_data, content_type)
            soap_envelope = mtom_parts["soap_envelope"]
            document_attachment = mtom_parts["document_attachment"]
            document_content_id = mtom_parts["document_content_id"]
        except ValueError as e:
            logger.warning(f"MTOM parsing error: {e}")
            fault_xml = generate_soap_fault(
                "soap:Sender",
                "MTOM Parsing Error",
                str(e)
            )
            return Response(fault_xml, mimetype="application/soap+xml; charset=utf-8"), 400

        # Extract XDSb metadata
        try:
            metadata = extract_xdsb_metadata(soap_envelope)
        except ValueError as e:
            logger.warning(f"XDSb metadata extraction error: {e}")
            fault_xml = generate_soap_fault(
                "soap:Sender",
                "Invalid XDSb Metadata",
                str(e)
            )
            return Response(fault_xml, mimetype="application/soap+xml; charset=utf-8"), 400
        
        # Validation mode enforcement
        if behavior and behavior.validation_mode == ValidationMode.STRICT:
            # Strict mode: require all XDSb metadata
            required_fields = ["patient_id", "class_code", "type_code"]
            missing_fields = [f for f in required_fields if f not in metadata]
            if missing_fields:
                logger.warning(f"Strict validation failed: missing {missing_fields}")
                fault_xml = generate_soap_fault(
                    "soap:Sender",
                    f"Strict validation failed: Missing required XDSb metadata fields: {', '.join(missing_fields)}. "
                    f"Enable lenient validation mode or provide complete XDSb metadata.",
                )
                return Response(fault_xml, mimetype="application/soap+xml; charset=utf-8"), 400

        # Setup logging directory
        log_dir = Path("mocks/logs/iti41-submissions")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Use custom IDs if provided in behavior config
        doc_id = metadata.get("document_unique_id", "unknown")
        submission_set_id = metadata.get("submission_set_id", "unknown")
        
        if behavior and behavior.custom_document_id:
            doc_id = behavior.custom_document_id
            logger.debug(f"Using custom document ID: {doc_id}")
        
        if behavior and behavior.custom_submission_set_id:
            submission_set_id = behavior.custom_submission_set_id
            logger.debug(f"Using custom submission set ID: {submission_set_id}")
        
        patient_id = metadata.get("patient_id", "unknown")

        logger.info(f"ITI-41 Submission - SubmissionSetID: {submission_set_id}")
        logger.info(f"ITI-41 Submission - DocumentUniqueID: {doc_id}")
        logger.info(f"ITI-41 Submission - PatientID: {patient_id}")

        # Log extracted metadata
        for key, value in metadata.items():
            if key not in ["submission_set_id", "document_unique_id", "patient_id"]:
                logger.info(f"Metadata - {key}: {value}")

        # Log full SOAP envelope at DEBUG level
        logger.debug(f"SOAP Envelope:\n{soap_envelope}")

        # Log full CCD document at DEBUG level
        logger.debug(f"CCD Document ({len(document_attachment)} bytes):\n{document_attachment[:500]}...")

        # Save transaction log
        log_file = log_dir / f"{timestamp}-{doc_id}.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=== ITI-41 Transaction Log ===\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Request ID: {request_id}\n")
            f.write(f"Submission Set ID: {submission_set_id}\n")
            f.write(f"Document Unique ID: {doc_id}\n")
            f.write(f"Patient ID: {patient_id}\n")
            f.write("\n=== Metadata ===\n")
            for key, value in metadata.items():
                f.write(f"{key}: {value}\n")
            f.write("\n=== SOAP Envelope ===\n")
            f.write(soap_envelope)
            f.write("\n\n=== CCD Document ===\n")
            f.write(document_attachment)

        logger.info(f"Saved transaction log to {log_file}")

        # Optionally save CCD document to disk
        if config and config.save_submitted_documents:
            doc_dir = Path("mocks/data/documents")
            doc_dir.mkdir(parents=True, exist_ok=True)
            doc_path = doc_dir / f"{doc_id}.xml"
            doc_path.write_text(document_attachment, encoding="utf-8")
            logger.info(f"Saved document to {doc_path}")

        # Generate RegistryResponse
        response_xml = generate_registry_response(
            request_id=request_id,
            submission_set_id=submission_set_id,
            document_unique_id=doc_id
        )

        # Log response at DEBUG level
        logger.debug(f"RegistryResponse:\n{response_xml}")

        logger.info("ITI-41 request processed successfully - Status: Success")

        return Response(
            response_xml,
            mimetype="application/soap+xml; charset=utf-8"
        ), 200

    except Exception as e:
        logger.error(f"Unexpected error processing ITI-41 request: {e}", exc_info=True)
        fault_xml = generate_soap_fault(
            "soap:Receiver",
            "Internal Server Error",
            f"An unexpected error occurred: {e!s}"
        )
        return Response(fault_xml, mimetype="application/soap+xml; charset=utf-8"), 500


def register_iti41_endpoint(app, config: MockServerConfig) -> None:
    """Register ITI-41 endpoint Blueprint with Flask app.
    
    Args:
        app: Flask application instance
        config: Mock server configuration
    """
    # Store config in app for access in route handlers
    app.config["MOCK_SERVER_CONFIG"] = config

    # Check if blueprint is already registered (for test scenarios)
    if "iti41" in app.blueprints:
        logger.debug("ITI-41 endpoint already registered")
        return

    # Register Blueprint
    app.register_blueprint(iti41_bp)

    logger.info(f"Registered ITI-41 endpoint: {config.iti41_endpoint}")
