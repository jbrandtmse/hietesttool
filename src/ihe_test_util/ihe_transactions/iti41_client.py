"""ITI-41 SOAP Client for Provide and Register Document Set-b transactions.

This module provides a SOAP client for ITI-41 transactions with MTOM packaging,
WS-Security with SAML assertions, and comprehensive error handling per ADR-001.

Uses manual MTOM construction with requests library (not zeep's experimental MTOM)
as recommended in spike findings.
"""

import logging
import ssl
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import requests
from lxml import etree

from ihe_test_util.ihe_transactions.mtom import MTOMPackage, MTOMAttachment
from ihe_test_util.ihe_transactions.parsers import (
    parse_registry_response,
    RegistryResponse,
)
from ihe_test_util.logging_audit.audit import log_transaction
from ihe_test_util.models.responses import (
    TransactionResponse,
    TransactionStatus,
    TransactionType,
)
from ihe_test_util.models.saml import SAMLAssertion
from ihe_test_util.models.transactions import ITI41Transaction
from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
from ihe_test_util.utils.exceptions import (
    ITI41SOAPError,
    ITI41TimeoutError,
    ITI41TransportError,
)

logger = logging.getLogger(__name__)

# Namespace constants
SOAP12_NS = "http://www.w3.org/2003/05/soap-envelope"
WSA_NS = "http://www.w3.org/2005/08/addressing"
WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
XDS_NS = "urn:ihe:iti:xds-b:2007"
RS_NS = "urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"

# WS-Addressing constants
WSA_ANONYMOUS = "http://www.w3.org/2005/08/addressing/anonymous"
ITI41_ACTION = "urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b"
ITI41_RESPONSE_ACTION = "urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-bResponse"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds
RETRYABLE_STATUS_CODES = {503}  # Service Unavailable
RETRYABLE_EXCEPTIONS = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)

# XDSb Registry Response status codes
REGISTRY_SUCCESS = "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"
REGISTRY_FAILURE = "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Failure"
REGISTRY_PARTIAL_SUCCESS = "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:PartialSuccess"


class ITI41SOAPClient:
    """SOAP client for ITI-41 (Provide and Register Document Set-b) transactions.
    
    Implements MTOM packaging with requests library per ADR-001, WS-Addressing
    headers, WS-Security with SAML assertions, and comprehensive retry logic.
    
    Attributes:
        endpoint_url: The ITI-41 endpoint URL
        timeout: Request timeout in seconds
    
    Example:
        >>> client = ITI41SOAPClient("http://localhost:8080/iti41/submit")
        >>> response = client.submit(transaction, saml_assertion)
        >>> if response.status == TransactionStatus.SUCCESS:
        ...     logger.info(f"Document submitted: {response.extracted_identifiers}")
    """

    def __init__(
        self,
        endpoint_url: str,
        timeout: int = 60,
        verify_tls: bool = True,
        ca_bundle_path: Optional[str] = None,
    ) -> None:
        """Initialize ITI-41 client.
        
        Args:
            endpoint_url: ITI-41 endpoint URL
            timeout: Request timeout in seconds (default 60)
            verify_tls: Whether to verify TLS certificates (default True)
            ca_bundle_path: Optional path to CA certificate bundle
        """
        self._endpoint_url = endpoint_url
        self._timeout = timeout
        self._verify_tls = verify_tls
        self._ca_bundle_path = ca_bundle_path
        self._session = self._create_session()
        self._ws_security_builder = WSSecurityHeaderBuilder()
        
        # Log HTTP warning
        if endpoint_url.startswith("http://"):
            logger.warning(
                "WARNING: Using HTTP transport for ITI-41. "
                "HTTPS recommended for production environments."
            )
        
        logger.debug(
            f"ITI41SOAPClient initialized: endpoint={endpoint_url}, "
            f"timeout={timeout}s, verify_tls={verify_tls}"
        )

    @property
    def endpoint_url(self) -> str:
        """Get the ITI-41 endpoint URL."""
        return self._endpoint_url

    @property
    def timeout(self) -> int:
        """Get the request timeout in seconds."""
        return self._timeout

    def _create_session(self) -> requests.Session:
        """Create HTTP session with TLS 1.2+ configuration.
        
        Returns:
            Configured requests.Session instance
        """
        session = requests.Session()
        
        # Configure TLS 1.2 minimum via SSLContext
        # Note: requests uses urllib3 which respects ssl context settings
        if self._endpoint_url.startswith("https://"):
            # TLS 1.2+ is enforced by default in modern Python/requests
            # Additional configuration can be done via HTTPAdapter if needed
            logger.debug("HTTPS transport configured with TLS 1.2+ enforcement")
        
        return session

    def submit(
        self,
        transaction: ITI41Transaction,
        saml_assertion: SAMLAssertion,
    ) -> TransactionResponse:
        """Submit ITI-41 transaction with MTOM packaging.
        
        Builds SOAP envelope with WS-Security header, packages with MTOM,
        and submits to the configured endpoint with retry logic.
        
        Args:
            transaction: ITI-41 transaction with CCD document
            saml_assertion: Signed SAML assertion for WS-Security
            
        Returns:
            TransactionResponse with status and extracted identifiers
            
        Raises:
            ITI41TransportError: Network/transport errors after all retries
            ITI41SOAPError: SOAP fault response received
            ITI41TimeoutError: Request timeout exceeded
        """
        start_time = time.time()
        message_id = f"urn:uuid:{uuid.uuid4()}"
        
        logger.info(
            f"Submitting ITI-41 transaction: transaction_id={transaction.transaction_id}, "
            f"patient_id={transaction.patient_id}, message_id={message_id}"
        )
        
        try:
            # Build SOAP envelope with WS-Addressing and WS-Security
            soap_envelope = self._build_soap_envelope(
                xdsb_metadata=transaction.metadata_xml,
                message_id=message_id,
                saml_assertion=saml_assertion,
            )
            
            # Create MTOM attachment for CCD document
            content_id = transaction.mtom_content_id or f"{uuid.uuid4()}@ihe-test-util.local"
            # CCDDocument uses xml_content attribute
            ccd_content = transaction.ccd_document.xml_content
            attachment = MTOMAttachment(
                content=ccd_content.encode("utf-8")
                if isinstance(ccd_content, str)
                else ccd_content,
                content_id=content_id,
                content_type="text/xml",
            )
            
            # Package with MTOM
            mtom_package = MTOMPackage(soap_envelope)
            mtom_package.add_attachment(attachment)
            
            # Validate MTOM package
            is_valid, errors = mtom_package.validate()
            if not is_valid:
                raise ITI41SOAPError(
                    f"MTOM package validation failed: {'; '.join(errors)}. "
                    "Verify SOAP envelope structure and attachment references."
                )
            
            # Build MTOM message
            message_bytes, content_type = mtom_package.build()
            
            # Submit with retry logic
            response = self._submit_with_retry(
                url=self._endpoint_url,
                data=message_bytes,
                headers={"Content-Type": content_type},
                max_retries=MAX_RETRIES,
            )
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Log complete transaction
            self._log_transaction(
                request_xml=soap_envelope.decode("utf-8"),
                response_xml=response.text,
                duration_ms=processing_time_ms,
                message_id=message_id,
            )
            
            # Parse response using new parser from parsers module
            try:
                parsed_response = parse_registry_response(response.text)
            except ValueError as e:
                # Fall back to error response if parsing fails
                logger.error(f"Failed to parse registry response: {e}")
                return TransactionResponse(
                    response_id=str(uuid.uuid4()),
                    request_id=message_id,
                    transaction_type=TransactionType.ITI_41,
                    status=TransactionStatus.ERROR,
                    status_code="ParseError",
                    response_timestamp=datetime.now(timezone.utc),
                    response_xml=response.text,
                    extracted_identifiers={},
                    error_messages=[str(e)],
                    processing_time_ms=processing_time_ms,
                )
            
            # Check correlation (using request_id from parsed response)
            if parsed_response.request_id and parsed_response.request_id != message_id:
                logger.warning(
                    f"Response correlation mismatch: expected={message_id}, "
                    f"got={parsed_response.request_id}"
                )
            elif parsed_response.request_id:
                logger.debug(f"Response correlation matched: {message_id}")
            
            # Map RegistryResponse to TransactionResponse
            status = self._map_registry_status_from_parsed(parsed_response)
            
            # Build identifiers dict from parsed response
            identifiers = {}
            if parsed_response.document_ids:
                identifiers["document_ids"] = parsed_response.document_ids
            if parsed_response.submission_set_id:
                identifiers["submission_set_id"] = parsed_response.submission_set_id
            
            # Build error messages from parsed errors
            error_messages = [
                f"[{e.severity}] {e.error_code}: {e.code_context}"
                for e in parsed_response.errors
            ]
            # Add warnings as well for visibility
            for w in parsed_response.warnings:
                error_messages.append(f"[Warning] {w.error_code}: {w.code_context}")
            
            return TransactionResponse(
                response_id=parsed_response.response_id or str(uuid.uuid4()),
                request_id=message_id,
                transaction_type=TransactionType.ITI_41,
                status=status,
                status_code=parsed_response.status,
                response_timestamp=datetime.now(timezone.utc),
                response_xml=response.text,
                extracted_identifiers=identifiers,
                error_messages=error_messages,
                processing_time_ms=processing_time_ms,
            )
            
        except ITI41TimeoutError:
            raise
        except ITI41TransportError:
            raise
        except ITI41SOAPError:
            raise
        except requests.exceptions.Timeout as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            raise ITI41TimeoutError(
                f"ITI-41 request to {self._endpoint_url} timed out after {self._timeout}s. "
                f"Consider increasing timeout or checking endpoint performance. "
                f"Transaction ID: {transaction.transaction_id}"
            ) from e
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"ITI-41 submission failed: {e}",
                exc_info=True,
            )
            raise ITI41TransportError(
                f"ITI-41 submission failed: {e}. "
                f"Transaction ID: {transaction.transaction_id}"
            ) from e

    def _build_soap_envelope(
        self,
        xdsb_metadata: str,
        message_id: str,
        saml_assertion: SAMLAssertion,
    ) -> bytes:
        """Build SOAP 1.2 envelope with WS-Addressing and WS-Security.
        
        Args:
            xdsb_metadata: XDSb ProvideAndRegisterDocumentSetRequest XML
            message_id: WS-Addressing MessageID
            saml_assertion: Signed SAML assertion for WS-Security
            
        Returns:
            SOAP envelope as bytes
        """
        # Parse XDSb metadata
        try:
            xdsb_element = etree.fromstring(xdsb_metadata.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ITI41SOAPError(
                f"Invalid XDSb metadata XML: {e}. "
                "Verify metadata was generated correctly by build_iti41_request()."
            )
        
        # Build WS-Security header
        ws_security = self._ws_security_builder.build_ws_security_header(saml_assertion)
        
        # Create SOAP envelope
        nsmap = {
            "soap12": SOAP12_NS,
            "wsa": WSA_NS,
            "wsse": WSSE_NS,
        }
        
        envelope = etree.Element(f"{{{SOAP12_NS}}}Envelope", nsmap=nsmap)
        
        # SOAP Header
        header = etree.SubElement(envelope, f"{{{SOAP12_NS}}}Header")
        
        # WS-Addressing headers
        self._add_ws_addressing_headers(header, message_id)
        
        # WS-Security header
        header.append(ws_security)
        
        # SOAP Body
        body = etree.SubElement(envelope, f"{{{SOAP12_NS}}}Body")
        body.append(xdsb_element)
        
        logger.debug(f"Built SOAP envelope with message_id={message_id}")
        
        return etree.tostring(
            envelope,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

    def _add_ws_addressing_headers(
        self,
        header: etree._Element,
        message_id: str,
    ) -> None:
        """Add WS-Addressing headers to SOAP header.
        
        Args:
            header: SOAP Header element
            message_id: Unique message identifier
        """
        # wsa:Action
        action = etree.SubElement(header, f"{{{WSA_NS}}}Action")
        action.text = ITI41_ACTION
        
        # wsa:MessageID
        msg_id = etree.SubElement(header, f"{{{WSA_NS}}}MessageID")
        msg_id.text = message_id
        
        # wsa:To
        to = etree.SubElement(header, f"{{{WSA_NS}}}To")
        to.text = self._endpoint_url
        
        # wsa:ReplyTo
        reply_to = etree.SubElement(header, f"{{{WSA_NS}}}ReplyTo")
        address = etree.SubElement(reply_to, f"{{{WSA_NS}}}Address")
        address.text = WSA_ANONYMOUS
        
        logger.debug(
            f"Added WS-Addressing headers: Action={ITI41_ACTION}, "
            f"MessageID={message_id}, To={self._endpoint_url}"
        )

    def _embed_saml_assertion(
        self,
        soap_envelope: bytes,
        saml_xml: str,
    ) -> bytes:
        """Embed SAML assertion in WS-Security header.
        
        Args:
            soap_envelope: SOAP envelope bytes
            saml_xml: SAML assertion XML string
            
        Returns:
            SOAP envelope with embedded SAML assertion
        """
        # This functionality is now handled by WSSecurityHeaderBuilder
        # Kept for interface compatibility
        logger.debug("SAML assertion embedding delegated to WSSecurityHeaderBuilder")
        return soap_envelope

    def _submit_with_retry(
        self,
        url: str,
        data: bytes,
        headers: dict,
        max_retries: int = 3,
    ) -> requests.Response:
        """Submit HTTP request with exponential backoff retry.
        
        Retries on transient errors: ConnectionError, Timeout, 503 Service Unavailable.
        Does NOT retry on: 400 Bad Request, 401 Unauthorized, 500 Internal Server Error.
        
        Args:
            url: Target URL
            data: Request body bytes
            headers: HTTP headers
            max_retries: Maximum retry attempts
            
        Returns:
            requests.Response on success
            
        Raises:
            ITI41TransportError: After max retries exceeded
            ITI41TimeoutError: On timeout
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Configure TLS verification
                verify = self._ca_bundle_path if self._ca_bundle_path else self._verify_tls
                
                response = self._session.post(
                    url,
                    data=data,
                    headers=headers,
                    timeout=self._timeout,
                    verify=verify,
                )
                
                # Check for retryable status codes
                if response.status_code in RETRYABLE_STATUS_CODES:
                    if attempt < max_retries:
                        delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                        logger.warning(
                            f"Received {response.status_code} response, "
                            f"retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                        continue
                
                # Check for non-retryable errors
                if response.status_code >= 400:
                    if response.status_code == 500:
                        raise ITI41SOAPError(
                            f"Server error (500) from {url}. "
                            f"Response: {response.text[:500]}..."
                        )
                    elif response.status_code in (400, 401, 403):
                        raise ITI41SOAPError(
                            f"Client error ({response.status_code}) from {url}. "
                            f"Check SAML assertion and request format. "
                            f"Response: {response.text[:500]}..."
                        )
                
                logger.debug(
                    f"ITI-41 request successful: status={response.status_code}, "
                    f"response_size={len(response.content)} bytes"
                )
                return response
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < max_retries:
                    delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                    logger.warning(
                        f"Request timeout, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(delay)
                else:
                    raise ITI41TimeoutError(
                        f"Request to {url} timed out after {max_retries} retries. "
                        f"Timeout setting: {self._timeout}s. "
                        "Consider increasing timeout or checking endpoint availability."
                    ) from e
                    
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < max_retries:
                    delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                    logger.warning(
                        f"Connection error, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(delay)
                else:
                    raise ITI41TransportError(
                        f"Connection to {url} failed after {max_retries} retries. "
                        "Check network connectivity and endpoint availability."
                    ) from e
        
        # Should not reach here, but safety net
        raise ITI41TransportError(
            f"Request to {url} failed after {max_retries} retries. "
            f"Last error: {last_exception}"
        )

    def _log_transaction(
        self,
        request_xml: str,
        response_xml: str,
        duration_ms: int,
        message_id: str,
    ) -> None:
        """Log complete transaction per RULE 2.
        
        Args:
            request_xml: Complete SOAP request XML
            response_xml: Complete SOAP response XML
            duration_ms: Transaction duration in milliseconds
            message_id: Message ID for correlation
        """
        log_transaction(
            transaction_type="ITI41_SUBMIT",
            request=request_xml,
            response=response_xml,
            status="success" if "Success" in response_xml else "failure",
        )
        
        logger.info(
            f"ITI-41 transaction logged: message_id={message_id}, "
            f"duration={duration_ms}ms"
        )

    def _correlate_response(
        self,
        response_xml: str,
        request_message_id: str,
    ) -> bool:
        """Correlate response with request via MessageID.
        
        Args:
            response_xml: SOAP response XML
            request_message_id: Original request MessageID
            
        Returns:
            True if RelatesTo matches request MessageID
        """
        try:
            root = etree.fromstring(response_xml.encode("utf-8"))
            
            # Look for wsa:RelatesTo
            relates_to = root.find(f".//{{{WSA_NS}}}RelatesTo")
            
            if relates_to is not None and relates_to.text:
                matched = relates_to.text == request_message_id
                if matched:
                    logger.debug(
                        f"Response correlation matched: {request_message_id}"
                    )
                else:
                    logger.warning(
                        f"Response correlation mismatch: expected={request_message_id}, "
                        f"got={relates_to.text}"
                    )
                return matched
            else:
                logger.debug(
                    "No wsa:RelatesTo in response, correlation skipped"
                )
                return False
                
        except etree.XMLSyntaxError as e:
            logger.warning(f"Failed to parse response for correlation: {e}")
            return False

    def _map_registry_status_from_parsed(
        self, parsed_response: RegistryResponse
    ) -> TransactionStatus:
        """Map parsed RegistryResponse status to TransactionStatus.
        
        Args:
            parsed_response: Parsed RegistryResponse from parsers module
            
        Returns:
            Corresponding TransactionStatus enum value
        """
        if parsed_response.is_success:
            return TransactionStatus.SUCCESS
        elif parsed_response.status == "PartialSuccess":
            return TransactionStatus.PARTIAL_SUCCESS
        elif parsed_response.status == "Failure":
            return TransactionStatus.ERROR
        else:
            logger.warning(f"Unknown registry status: {parsed_response.status}")
            return TransactionStatus.ERROR
