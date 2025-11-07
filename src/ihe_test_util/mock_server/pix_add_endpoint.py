"""Mock PIX Add (ITI-44) endpoint for testing."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from flask import Response, request
from lxml import etree


logger = logging.getLogger(__name__)

# HL7v3 namespaces
HL7_NS = "urn:hl7-org:v3"

NSMAP = {
    None: HL7_NS,
}


def create_pix_add_acknowledgement(
    message_id: str,
    status: str = "AA"
) -> str:
    """Create HL7v3 MCCI_IN000002UV01 acknowledgement.
    
    Args:
        message_id: Original message ID to acknowledge
        status: Acknowledgement status (AA=Application Accept, AE=Application Error)
        
    Returns:
        XML string containing the acknowledgement
    """
    logger.info(f"Creating PIX Add acknowledgement with status: {status}")

    # Build acknowledgement
    root = etree.Element(
        f"{{{HL7_NS}}}MCCI_IN000002UV01",
        nsmap=NSMAP,
        ITSVersion="XML_1.0"
    )

    # Add ID
    id_elem = etree.SubElement(root, f"{{{HL7_NS}}}id")
    id_elem.set("root", "2.16.840.1.113883.3.72.5.2")
    id_elem.set("extension", f"ACK-{message_id}")

    # Add Creation Time
    creation_time = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    creation_time_elem = etree.SubElement(root, f"{{{HL7_NS}}}creationTime")
    creation_time_elem.set("value", creation_time)

    # Add Interaction ID
    interaction_id_elem = etree.SubElement(root, f"{{{HL7_NS}}}interactionId")
    interaction_id_elem.set("root", "2.16.840.1.113883.1.6")
    interaction_id_elem.set("extension", "MCCI_IN000002UV01")

    # Add Processing Code
    processing_code_elem = etree.SubElement(root, f"{{{HL7_NS}}}processingCode")
    processing_code_elem.set("code", "P")

    # Add Processing Mode Code
    processing_mode_elem = etree.SubElement(root, f"{{{HL7_NS}}}processingModeCode")
    processing_mode_elem.set("code", "T")

    # Add Accept Acknowledgement Code
    accept_ack_elem = etree.SubElement(root, f"{{{HL7_NS}}}acceptAckCode")
    accept_ack_elem.set("code", "NE")

    # Add Acknowledgement
    ack_elem = etree.SubElement(root, f"{{{HL7_NS}}}acknowledgement")
    type_code_elem = etree.SubElement(ack_elem, f"{{{HL7_NS}}}typeCode")
    type_code_elem.set("code", status)

    # Add target message
    target_msg_elem = etree.SubElement(ack_elem, f"{{{HL7_NS}}}targetMessage")
    target_id_elem = etree.SubElement(target_msg_elem, f"{{{HL7_NS}}}id")
    target_id_elem.set("root", message_id)

    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    ).decode("utf-8")

    return xml_string


def handle_pix_add_request():
    """Handle PIX Add (ITI-44) request.
    
    Returns:
        Flask Response with HL7v3 acknowledgement
    """
    logger.info("Received PIX Add request")

    try:
        # Get request data
        content_type = request.content_type
        request_data = request.data

        logger.debug(f"Content-Type: {content_type}")
        logger.debug(f"Request size: {len(request_data)} bytes")

        # Parse the request to extract message ID
        try:
            root = etree.fromstring(request_data)
            # Extract message ID from the request
            id_elem = root.find(f".//{{{HL7_NS}}}id")
            message_id = id_elem.get("root") if id_elem is not None else "unknown"

            # Extract patient demographics for logging
            patient_elem = root.find(f".//{{{HL7_NS}}}patient")
            if patient_elem is not None:
                patient_id_elem = patient_elem.find(f".//{{{HL7_NS}}}id")
                if patient_id_elem is not None:
                    patient_id = patient_id_elem.get("extension", "unknown")
                    logger.info(f"Patient ID: {patient_id}")
        except Exception as e:
            logger.warning(f"Could not parse request XML: {e}")
            message_id = "unknown"

        # Log the request
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_dir = Path("mocks/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        request_log_path = log_dir / f"pix_add_request_{timestamp}.xml"
        request_log_path.write_bytes(request_data)
        logger.info(f"Saved request to: {request_log_path}")

        # Create acknowledgement
        ack_xml = create_pix_add_acknowledgement(message_id, status="AA")

        # Log the response
        response_log_path = log_dir / f"pix_add_response_{timestamp}.xml"
        response_log_path.write_text(ack_xml)
        logger.info(f"Saved response to: {response_log_path}")

        return Response(
            ack_xml,
            mimetype="application/soap+xml; charset=utf-8",
            status=200
        )

    except Exception as e:
        logger.error(f"Error processing PIX Add request: {e}", exc_info=True)

        # Return error acknowledgement
        error_ack = create_pix_add_acknowledgement("unknown", status="AE")
        return Response(
            error_ack,
            mimetype="application/soap+xml; charset=utf-8",
            status=500
        )


def register_pix_add_endpoint(app):
    """Register PIX Add endpoint with Flask app.
    
    Args:
        app: Flask application instance
    """
    @app.route("/pix/add", methods=["POST"])
    def pix_add_endpoint():
        return handle_pix_add_request()

    logger.info("Registered PIX Add endpoint: /pix/add")
