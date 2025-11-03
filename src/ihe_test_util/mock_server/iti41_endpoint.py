"""Mock ITI-41 endpoint for testing document submission."""

import logging
from datetime import datetime
from pathlib import Path
from flask import request, Response
from lxml import etree

logger = logging.getLogger(__name__)

# XDS.b response namespaces
RS_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"
RIM_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0"

NSMAP = {
    "rs": RS_NS,
    "rim": RIM_NS,
}


def create_iti41_response(
    status: str = "Success",
    submission_id: str = "SubmissionSet01",
) -> str:
    """Create XDSb RegistryResponse.
    
    Args:
        status: Response status (Success, Failure, PartialSuccess)
        submission_id: ID of the submission set
        
    Returns:
        XML string containing the RegistryResponse
    """
    logger.info(f"Creating ITI-41 response with status: {status}")
    
    # Build response
    root = etree.Element(
        f"{{{RS_NS}}}RegistryResponse",
        nsmap=NSMAP,
        status=f"urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:{status}"
    )
    
    # Add slot with submission set ID
    slot = etree.SubElement(root, f"{{{RIM_NS}}}Slot", name="SubmissionSet")
    value_list = etree.SubElement(slot, f"{{{RIM_NS}}}ValueList")
    value_elem = etree.SubElement(value_list, f"{{{RIM_NS}}}Value")
    value_elem.text = submission_id
    
    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    ).decode("utf-8")
    
    return xml_string


def handle_iti41_request():
    """Handle ITI-41 Provide and Register Document Set-b request.
    
    Returns:
        Flask Response with XDSb RegistryResponse
    """
    logger.info("Received ITI-41 request")
    
    try:
        # Get request data
        content_type = request.content_type
        request_data = request.data
        
        logger.debug(f"Content-Type: {content_type}")
        logger.debug(f"Request size: {len(request_data)} bytes")
        
        # Log the request
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_dir = Path("mocks/logs/iti41-submissions")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        request_log_path = log_dir / f"request_{timestamp}.xml"
        request_log_path.write_bytes(request_data)
        logger.info(f"Saved request to: {request_log_path}")
        
        # Parse multipart MTOM if present
        if "multipart" in content_type:
            logger.info("Detected MTOM multipart request")
            # In a real implementation, we'd parse the multipart boundaries
            # For this spike, we'll just log that we received it
            parts = request_data.split(b"--")
            logger.info(f"Multipart message has {len(parts)} parts")
            
            # Try to extract and save the CCD document
            for i, part in enumerate(parts):
                if b"Content-Type: text/xml" in part or b"Content-Type: application/xml" in part:
                    logger.debug(f"Found XML part {i}")
                    # Extract the XML content after headers
                    if b"\r\n\r\n" in part:
                        xml_content = part.split(b"\r\n\r\n", 1)[1]
                        if xml_content.strip().startswith(b"<?xml") or xml_content.strip().startswith(b"<"):
                            doc_path = log_dir / f"document_{timestamp}.xml"
                            doc_path.write_bytes(xml_content.strip())
                            logger.info(f"Saved document to: {doc_path}")
        
        # Create success response
        response_xml = create_iti41_response(status="Success")
        
        # Log the response
        response_log_path = log_dir / f"response_{timestamp}.xml"
        response_log_path.write_text(response_xml)
        logger.info(f"Saved response to: {response_log_path}")
        
        return Response(
            response_xml,
            mimetype="application/soap+xml; charset=utf-8",
            status=200
        )
        
    except Exception as e:
        logger.error(f"Error processing ITI-41 request: {e}", exc_info=True)
        
        # Return error response
        error_response = create_iti41_response(status="Failure")
        return Response(
            error_response,
            mimetype="application/soap+xml; charset=utf-8",
            status=500
        )


def register_iti41_endpoint(app):
    """Register ITI-41 endpoint with Flask app.
    
    Args:
        app: Flask application instance
    """
    @app.route("/DocumentRepository_Service", methods=["POST"])
    def iti41_endpoint():
        return handle_iti41_request()
    
    @app.route("/iti41/submit", methods=["POST"])
    def iti41_submit():
        return handle_iti41_request()
    
    logger.info("Registered ITI-41 endpoints: /DocumentRepository_Service, /iti41/submit")
