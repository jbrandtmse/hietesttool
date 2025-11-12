"""WS-Security header construction for IHE transactions.

This module provides functionality to build WS-Security SOAP headers with
embedded signed SAML assertions for authenticating IHE transactions.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from lxml import etree

from ihe_test_util.models.saml import SAMLAssertion

logger = logging.getLogger(__name__)


class WSSecurityHeaderBuilder:
    """Build WS-Security headers with SAML assertions for IHE transactions.
    
    This class constructs WS-Security 1.1 compliant SOAP headers containing
    signed SAML assertions and timestamps for authenticating IHE transactions
    like PIX Add (ITI-44) and ITI-41.
    
    Attributes:
        WSSE_NS: WS-Security extension namespace
        WSU_NS: WS-Security utility namespace
        WSA_NS: WS-Addressing namespace
        SOAP_NS: SOAP 1.2 envelope namespace
        SAML_NS: SAML 2.0 assertion namespace
        DS_NS: XML Digital Signature namespace
    
    Example:
        >>> from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
        >>> from ihe_test_util.saml.signer import SAMLSigner
        >>> 
        >>> # Sign SAML assertion
        >>> signer = SAMLSigner(cert_bundle)
        >>> signed_saml = signer.sign_assertion(assertion)
        >>> 
        >>> # Build WS-Security header
        >>> builder = WSSecurityHeaderBuilder()
        >>> ws_security = builder.build_ws_security_header(signed_saml)
    """
    
    # Namespace constants
    WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
    WSU_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
    WSA_NS = "http://www.w3.org/2005/08/addressing"
    SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
    SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
    DS_NS = "http://www.w3.org/2000/09/xmldsig#"
    
    def __init__(self) -> None:
        """Initialize WS-Security header builder.
        
        Registers XML namespaces for clean serialization.
        """
        # Register namespaces for clean serialization
        etree.register_namespace('wsse', self.WSSE_NS)
        etree.register_namespace('wsu', self.WSU_NS)
        etree.register_namespace('wsa', self.WSA_NS)
        etree.register_namespace('SOAP-ENV', self.SOAP_NS)
        etree.register_namespace('saml', self.SAML_NS)
        etree.register_namespace('ds', self.DS_NS)
        
        logger.debug("WSSecurityHeaderBuilder initialized with namespace registrations")
    
    def build_ws_security_header(
        self,
        signed_saml: SAMLAssertion,
        timestamp_validity_minutes: int = 5
    ) -> etree.Element:
        """Build WS-Security header with signed SAML assertion.
        
        Creates a WS-Security 1.1 compliant security header containing a
        timestamp and the complete signed SAML assertion with signature.
        
        Args:
            signed_saml: Signed SAML assertion from SAMLSigner
            timestamp_validity_minutes: Timestamp validity period (default 5 min)
            
        Returns:
            lxml.etree.Element for wsse:Security header
            
        Raises:
            ValueError: If signed_saml is invalid or missing required fields
            etree.XMLSyntaxError: If SAML XML content is malformed
            
        Example:
            >>> builder = WSSecurityHeaderBuilder()
            >>> ws_security = builder.build_ws_security_header(
            ...     signed_saml,
            ...     timestamp_validity_minutes=10
            ... )
        """
        if not signed_saml:
            raise ValueError("signed_saml parameter is required. Provide a SAMLAssertion instance.")
        
        if not signed_saml.xml_content:
            raise ValueError(
                "SAML assertion xml_content is empty. "
                "Ensure the assertion was generated with SAMLProgrammaticGenerator or SAMLTemplateLoader."
            )
        
        logger.info(
            f"Building WS-Security header for SAML assertion: {signed_saml.assertion_id}"
        )
        
        # Create wsse:Security element
        security = etree.Element(
            f"{{{self.WSSE_NS}}}Security",
            attrib={f"{{{self.SOAP_NS}}}mustUnderstand": "1"}
        )
        
        # Add timestamp
        timestamp = self._create_timestamp(timestamp_validity_minutes)
        security.append(timestamp)
        
        # Parse and embed signed SAML assertion
        try:
            saml_assertion = etree.fromstring(signed_saml.xml_content.encode('utf-8'))
            security.append(saml_assertion)
            logger.debug(
                f"Embedded SAML assertion {signed_saml.assertion_id} in WS-Security header"
            )
        except etree.XMLSyntaxError as e:
            raise ValueError(
                f"Invalid SAML XML structure: {e}. "
                "Ensure signed SAML assertion is valid XML."
            )
        except AttributeError as e:
            raise ValueError(
                f"Missing required SAML field: {e}. "
                "Ensure SAMLAssertion is complete with xml_content."
            )
        
        logger.info("WS-Security header built successfully")
        return security
    
    def _create_timestamp(self, validity_minutes: int) -> etree.Element:
        """Create WS-Security timestamp element.
        
        Generates a wsu:Timestamp element with Created and Expires times
        in ISO 8601 format with UTC timezone.
        
        Args:
            validity_minutes: How long the timestamp is valid (in minutes)
            
        Returns:
            lxml.etree.Element for wsu:Timestamp
            
        Raises:
            ValueError: If validity_minutes is invalid
            
        Example:
            >>> builder = WSSecurityHeaderBuilder()
            >>> timestamp = builder._create_timestamp(10)
        """
        if validity_minutes <= 0:
            raise ValueError(
                f"Invalid validity_minutes: {validity_minutes}. "
                "Must be a positive integer."
            )
        
        from datetime import timezone
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=validity_minutes)
        
        timestamp_id = f"TS-{uuid.uuid4()}"
        
        timestamp = etree.Element(
            f"{{{self.WSU_NS}}}Timestamp",
            attrib={f"{{{self.WSU_NS}}}Id": timestamp_id}
        )
        
        created = etree.SubElement(timestamp, f"{{{self.WSU_NS}}}Created")
        created.text = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        expires_elem = etree.SubElement(timestamp, f"{{{self.WSU_NS}}}Expires")
        expires_elem.text = expires.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        logger.debug(
            f"Created timestamp {timestamp_id} valid until {expires_elem.text}"
        )
        
        return timestamp
    
    def embed_in_soap_envelope(
        self,
        body: etree.Element,
        ws_security_header: etree.Element
    ) -> etree.Element:
        """Embed WS-Security header and body in SOAP 1.2 envelope.
        
        Creates a complete SOAP 1.2 envelope with WS-Security header as the
        first child of SOAP:Header and the provided body content in SOAP:Body.
        
        Args:
            body: SOAP body content (e.g., PIX Add message, ITI-41 request)
            ws_security_header: WS-Security header from build_ws_security_header()
            
        Returns:
            Complete SOAP envelope as lxml.etree.Element
            
        Raises:
            ValueError: If body or header are invalid
            
        Example:
            >>> builder = WSSecurityHeaderBuilder()
            >>> ws_security = builder.build_ws_security_header(signed_saml)
            >>> pix_message = build_pix_add_message(patient)
            >>> envelope = builder.embed_in_soap_envelope(pix_message, ws_security)
        """
        if body is None:
            raise ValueError("body parameter is required. Provide an lxml.etree.Element for SOAP body.")
        
        if ws_security_header is None:
            raise ValueError(
                "ws_security_header parameter is required. "
                "Provide a WS-Security header from build_ws_security_header()."
            )
        
        logger.debug("Embedding WS-Security header and body in SOAP 1.2 envelope")
        
        # Create SOAP-ENV:Envelope
        envelope = etree.Element(
            f"{{{self.SOAP_NS}}}Envelope",
            nsmap={'SOAP-ENV': self.SOAP_NS}
        )
        
        # Create SOAP-ENV:Header as first child
        header = etree.SubElement(envelope, f"{{{self.SOAP_NS}}}Header")
        
        # Insert ws_security_header as first child of Header
        header.append(ws_security_header)
        
        # Create SOAP-ENV:Body as second child of envelope
        soap_body = etree.SubElement(envelope, f"{{{self.SOAP_NS}}}Body")
        
        # Insert body element into SOAP-ENV:Body
        soap_body.append(body)
        
        logger.info("SOAP envelope created successfully with WS-Security header")
        return envelope
    
    def add_ws_addressing_headers(
        self,
        header: etree.Element,
        action: str,
        to: str,
        message_id: Optional[str] = None
    ) -> None:
        """Add WS-Addressing headers to SOAP header.
        
        Adds WS-Addressing headers (Action, To, MessageID, ReplyTo) to the
        SOAP header for IHE transaction routing.
        
        Args:
            header: SOAP header element
            action: IHE transaction action URI
            to: Endpoint URL
            message_id: Optional message ID (generates UUID if not provided)
            
        Raises:
            ValueError: If required parameters are missing
            
        Example:
            >>> builder = WSSecurityHeaderBuilder()
            >>> builder.add_ws_addressing_headers(
            ...     header,
            ...     action="urn:hl7-org:v3:PRPA_IN201301UV02",
            ...     to="http://pix.example.com/pix/add"
            ... )
        """
        if not action:
            raise ValueError("action parameter is required. Provide an IHE transaction action URI.")
        
        if not to:
            raise ValueError("to parameter is required. Provide an endpoint URL.")
        
        logger.debug(f"Adding WS-Addressing headers: action={action}, to={to}")
        
        # Add wsa:Action
        action_elem = etree.SubElement(header, f"{{{self.WSA_NS}}}Action")
        action_elem.text = action
        
        # Add wsa:To
        to_elem = etree.SubElement(header, f"{{{self.WSA_NS}}}To")
        to_elem.text = to
        
        # Add wsa:MessageID
        if message_id is None:
            message_id = f"urn:uuid:{uuid.uuid4()}"
        
        message_id_elem = etree.SubElement(header, f"{{{self.WSA_NS}}}MessageID")
        message_id_elem.text = message_id
        
        # Add wsa:ReplyTo
        reply_to = etree.SubElement(header, f"{{{self.WSA_NS}}}ReplyTo")
        address = etree.SubElement(reply_to, f"{{{self.WSA_NS}}}Address")
        address.text = "http://www.w3.org/2005/08/addressing/anonymous"
        
        logger.debug(f"Added WS-Addressing headers with MessageID: {message_id}")
    
    def create_pix_add_soap_envelope(
        self,
        signed_saml: SAMLAssertion,
        pix_message: etree.Element,
        endpoint_url: str = "http://localhost:5000/pix/add"
    ) -> str:
        """Create complete PIX Add SOAP envelope with WS-Security.
        
        Convenience method to create a complete SOAP envelope for PIX Add
        (ITI-44) transactions with WS-Security header and WS-Addressing.
        
        Args:
            signed_saml: Signed SAML assertion
            pix_message: PIX Add message element
            endpoint_url: PIX Add endpoint URL
            
        Returns:
            Serialized SOAP envelope as string
            
        Raises:
            ValueError: If parameters are invalid
            
        Example:
            >>> builder = WSSecurityHeaderBuilder()
            >>> envelope = builder.create_pix_add_soap_envelope(
            ...     signed_saml,
            ...     pix_message,
            ...     "http://pix.example.com/pix/add"
            ... )
        """
        logger.info(f"Creating PIX Add SOAP envelope for endpoint: {endpoint_url}")
        
        # Build WS-Security header
        ws_security = self.build_ws_security_header(signed_saml)
        
        # Create SOAP envelope
        envelope = self.embed_in_soap_envelope(pix_message, ws_security)
        
        # Get SOAP:Header and add WS-Addressing headers
        header = envelope.find(f".//{{{self.SOAP_NS}}}Header")
        if header is None:
            raise ValueError("SOAP:Header not found in envelope. Internal error.")
        
        self.add_ws_addressing_headers(
            header,
            action="urn:hl7-org:v3:PRPA_IN201301UV02",
            to=endpoint_url
        )
        
        # Serialize to string
        envelope_str = etree.tostring(
            envelope,
            encoding='unicode',
            pretty_print=True
        )
        
        logger.info("PIX Add SOAP envelope created successfully")
        return envelope_str
    
    def create_iti41_soap_envelope(
        self,
        signed_saml: SAMLAssertion,
        iti41_request: etree.Element,
        endpoint_url: str = "http://localhost:5000/iti41/submit"
    ) -> str:
        """Create complete ITI-41 SOAP envelope with WS-Security.
        
        Convenience method to create a complete SOAP envelope for ITI-41
        (Provide and Register Document Set) transactions with WS-Security
        header and WS-Addressing.
        
        Args:
            signed_saml: Signed SAML assertion
            iti41_request: ITI-41 request element
            endpoint_url: ITI-41 endpoint URL
            
        Returns:
            Serialized SOAP envelope as string
            
        Raises:
            ValueError: If parameters are invalid
            
        Example:
            >>> builder = WSSecurityHeaderBuilder()
            >>> envelope = builder.create_iti41_soap_envelope(
            ...     signed_saml,
            ...     iti41_request,
            ...     "http://xds.example.com/iti41/submit"
            ... )
        """
        logger.info(f"Creating ITI-41 SOAP envelope for endpoint: {endpoint_url}")
        
        # Build WS-Security header
        ws_security = self.build_ws_security_header(signed_saml)
        
        # Create SOAP envelope
        envelope = self.embed_in_soap_envelope(iti41_request, ws_security)
        
        # Get SOAP:Header and add WS-Addressing headers
        header = envelope.find(f".//{{{self.SOAP_NS}}}Header")
        if header is None:
            raise ValueError("SOAP:Header not found in envelope. Internal error.")
        
        self.add_ws_addressing_headers(
            header,
            action="urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b",
            to=endpoint_url
        )
        
        # Serialize to string
        envelope_str = etree.tostring(
            envelope,
            encoding='unicode',
            pretty_print=True
        )
        
        logger.info("ITI-41 SOAP envelope created successfully")
        return envelope_str
    
    def validate_ws_security_header(self, header: etree.Element) -> bool:
        """Validate WS-Security header against specification.
        
        Checks that the WS-Security header contains all required elements
        and attributes according to WS-Security 1.1 specification.
        
        Args:
            header: WS-Security header element to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If header is invalid with detailed error message
            
        Example:
            >>> builder = WSSecurityHeaderBuilder()
            >>> is_valid = builder.validate_ws_security_header(ws_security)
        """
        if header is None:
            raise ValueError("Header is None. Provide a valid wsse:Security element.")
        
        logger.debug("Validating WS-Security header structure")
        
        # Check wsse:Security element first
        if not header.tag.endswith('Security'):
            raise ValueError(
                f"Invalid root element: {header.tag}. "
                "Expected wsse:Security element."
            )
        
        # Check mustUnderstand attribute
        must_understand = header.get(f"{{{self.SOAP_NS}}}mustUnderstand")
        if must_understand != "1":
            raise ValueError(
                "Missing or invalid mustUnderstand attribute. "
                "WS-Security header must have SOAP-ENV:mustUnderstand='1'."
            )
        
        # Check wsu:Timestamp present
        timestamp = header.find(f".//{{{self.WSU_NS}}}Timestamp")
        if timestamp is None:
            raise ValueError(
                "Missing wsu:Timestamp element. "
                "WS-Security header must contain a timestamp."
            )
        
        # Check timestamp has Created and Expires
        created = timestamp.find(f".//{{{self.WSU_NS}}}Created")
        expires = timestamp.find(f".//{{{self.WSU_NS}}}Expires")
        if created is None or expires is None:
            raise ValueError(
                "Timestamp missing Created or Expires elements. "
                "Both wsu:Created and wsu:Expires are required."
            )
        
        # Check SAML assertion present
        saml_assertion = header.find(f".//{{{self.SAML_NS}}}Assertion")
        if saml_assertion is None:
            raise ValueError(
                "Missing saml:Assertion element. "
                "WS-Security header must contain a SAML assertion."
            )
        
        # Check signature present in SAML
        signature = saml_assertion.find(f".//{{{self.DS_NS}}}Signature")
        if signature is None:
            logger.warning(
                "SAML assertion does not contain ds:Signature. "
                "Unsigned assertions may be rejected by IHE endpoints."
            )
        
        logger.info("WS-Security header validation passed")
        return True
