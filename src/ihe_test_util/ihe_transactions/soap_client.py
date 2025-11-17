"""PIX Add SOAP client for IHE ITI-44 transactions.

This module provides a SOAP client for submitting PIX Add messages to
IHE endpoints with WS-Security authentication, retry logic, and audit logging.
"""

import logging
import ssl
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from lxml import etree
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from ihe_test_util.config.schema import Config
from ihe_test_util.models.responses import (
    TransactionResponse,
    TransactionStatus,
    TransactionType,
)
from ihe_test_util.models.saml import SAMLAssertion
from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder
from ihe_test_util.ihe_transactions.parsers import parse_acknowledgment
from ihe_test_util.utils.exceptions import ValidationError

logger = logging.getLogger(__name__)


class TLS12Adapter(HTTPAdapter):
    """Force TLS 1.2+ for HTTPS connections.
    
    Custom requests adapter that enforces minimum TLS 1.2 for all
    HTTPS connections to IHE endpoints.
    
    Example:
        >>> session = requests.Session()
        >>> session.mount('https://', TLS12Adapter())
    """
    
    def init_poolmanager(self, *args, **kwargs):
        """Initialize connection pool with TLS 1.2+ enforcement.
        
        Args:
            *args: Positional arguments for pool manager
            **kwargs: Keyword arguments for pool manager
            
        Returns:
            Initialized pool manager with TLS 1.2+ context
        """
        context = create_urllib3_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


class PIXAddSOAPClient:
    """SOAP client for PIX Add (ITI-44) transactions.
    
    Handles complete PIX Add workflow including SOAP envelope construction,
    WS-Security headers, WS-Addressing, retry logic, and response parsing.
    
    Attributes:
        config: Application configuration
        endpoint_url: PIX Add endpoint URL
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts for failed requests
        session: Configured requests session with TLS enforcement
        
    Example:
        >>> from ihe_test_util.config.manager import ConfigManager
        >>> config = ConfigManager().load_config()
        >>> client = PIXAddSOAPClient(config)
        >>> response = client.submit_pix_add(pix_message, saml_assertion)
        >>> print(response.status)
        TransactionStatus.SUCCESS
    """
    
    def __init__(
        self,
        config: Config,
        endpoint_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ) -> None:
        """Initialize PIX Add SOAP client.
        
        Args:
            config: Application configuration with endpoint URLs
            endpoint_url: Override endpoint URL (uses config if not provided)
            timeout: Request timeout in seconds (default 30)
            max_retries: Maximum retry attempts (default 3)
            
        Raises:
            ValidationError: If timeout <= 0 or max_retries < 0
            ValidationError: If endpoint URL is invalid
        """
        logger.info("Initializing PIX Add SOAP client")
        
        # Validate timeout and retries
        if timeout <= 0:
            raise ValidationError(
                f"Invalid timeout: {timeout}. Must be greater than 0 seconds."
            )
        
        if max_retries < 0:
            raise ValidationError(
                f"Invalid max_retries: {max_retries}. Must be >= 0."
            )
        
        self.config = config
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Load endpoint URL from config or use provided
        if endpoint_url:
            self.endpoint_url = endpoint_url
        else:
            self.endpoint_url = config.endpoints.pix_add_url
        
        # Validate endpoint URL format
        if not self.endpoint_url.startswith(('http://', 'https://')):
            raise ValidationError(
                f"Invalid endpoint URL: {self.endpoint_url}. "
                "Must start with http:// or https://"
            )
        
        # Log security warning for HTTP endpoints
        if self.endpoint_url.startswith('http://'):
            logger.warning(
                "SECURITY WARNING: Using HTTP transport (not HTTPS) for PIX Add endpoint. "
                "This is only acceptable for local development. "
                "Production endpoints MUST use HTTPS with valid certificates."
            )
        
        # Create session with TLS 1.2+ enforcement
        self.session = requests.Session()
        self.session.mount('https://', TLS12Adapter())
        
        # Configure certificate verification
        self.session.verify = config.transport.verify_tls
        
        if not config.transport.verify_tls:
            logger.warning(
                "TLS certificate verification is DISABLED. "
                "This should only be used for development with self-signed certificates."
            )
        
        logger.info(
            f"PIX Add SOAP client initialized: endpoint={self.endpoint_url}, "
            f"timeout={timeout}s, max_retries={max_retries}"
        )
    
    def submit_pix_add(
        self,
        hl7v3_message: str,
        saml_assertion: SAMLAssertion
    ) -> TransactionResponse:
        """Submit PIX Add transaction to IHE endpoint.
        
        Constructs complete SOAP envelope with WS-Security and WS-Addressing
        headers, submits to configured PIX Add endpoint, and parses the
        HL7v3 acknowledgment response.
        
        Args:
            hl7v3_message: Complete HL7v3 PRPA_IN201301UV02 message XML
            saml_assertion: Signed SAML assertion for authentication
            
        Returns:
            TransactionResponse with acknowledgment status and details
            
        Raises:
            ValidationError: If SAML assertion is unsigned or invalid
            requests.ConnectionError: If endpoint unreachable after retries
            requests.Timeout: If request exceeds configured timeout
            requests.exceptions.SSLError: If TLS/certificate validation fails
            
        Example:
            >>> response = client.submit_pix_add(pix_message, saml)
            >>> if response.is_success:
            ...     print(f"Patient registered: {response.status_code}")
            ... else:
            ...     print(f"Error: {response.error_messages}")
        """
        start_time = time.time()
        
        # Validate SAML assertion has signature
        if not saml_assertion.signature:
            raise ValidationError(
                "SAML assertion is not signed. "
                "Call SAMLSigner.sign_assertion() before submitting PIX Add transaction."
            )
        
        logger.info(f"Submitting PIX Add transaction to {self.endpoint_url}")
        
        # Build SOAP envelope with WS-Security and WS-Addressing headers
        soap_envelope = self._build_soap_envelope(hl7v3_message, saml_assertion)
        
        # Extract request ID for correlation
        request_id = self._extract_message_id(hl7v3_message)
        
        # Log complete request to audit trail before transmission
        self._log_transaction(
            request_xml=soap_envelope,
            response_xml=None,
            status="SENDING",
            request_id=request_id
        )
        
        # Submit with retry logic
        try:
            response_xml, status_code = self._submit_with_retry(soap_envelope)
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Log complete response to audit trail
            self._log_transaction(
                request_xml=soap_envelope,
                response_xml=response_xml,
                status="SUCCESS",
                request_id=request_id
            )
            
            # Parse acknowledgment response
            transaction_response = self._parse_acknowledgment(
                response_xml=response_xml,
                request_id=request_id,
                processing_time_ms=processing_time_ms
            )
            
            logger.info(
                f"PIX Add transaction completed: status={transaction_response.status}, "
                f"code={transaction_response.status_code}, time={processing_time_ms}ms"
            )
            
            return transaction_response
            
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.SSLError) as e:
            # Log error to audit trail
            processing_time_ms = int((time.time() - start_time) * 1000)
            self._log_transaction(
                request_xml=soap_envelope,
                response_xml=None,
                status="ERROR",
                request_id=request_id,
                error_message=str(e)
            )
            
            # Re-raise with original exception
            raise
    
    def _build_soap_envelope(
        self,
        hl7v3_message: str,
        saml_assertion: SAMLAssertion
    ) -> str:
        """Build complete SOAP envelope with WS-Security and WS-Addressing.
        
        Args:
            hl7v3_message: HL7v3 message XML string
            saml_assertion: Signed SAML assertion
            
        Returns:
            Complete SOAP envelope as XML string
            
        Raises:
            etree.XMLSyntaxError: If HL7v3 message XML is malformed
        """
        logger.debug("Building SOAP envelope with WS-Security headers")
        
        # Parse HL7v3 message to extract PRPA_IN201301UV02 element from SOAP:Body
        hl7v3_root = etree.fromstring(hl7v3_message.encode('utf-8'))
        
        # Check if already wrapped in SOAP envelope (from build_pix_add_message)
        soap_ns = "http://schemas.xmlsoap.org/soap/envelope/"
        if hl7v3_root.tag == f"{{{soap_ns}}}Envelope":
            # Extract PRPA_IN201301UV02 from SOAP:Body
            body = hl7v3_root.find(f".//{{{soap_ns}}}Body")
            if body is not None and len(body) > 0:
                pix_message_element = body[0]
            else:
                raise ValidationError("SOAP envelope does not contain body element")
        else:
            # Use as-is if not wrapped
            pix_message_element = hl7v3_root
        
        # Use WSSecurityHeaderBuilder convenience method for PIX Add
        builder = WSSecurityHeaderBuilder()
        soap_envelope_str = builder.create_pix_add_soap_envelope(
            signed_saml=saml_assertion,
            pix_message=pix_message_element,
            endpoint_url=self.endpoint_url
        )
        
        logger.debug("SOAP envelope built successfully with WS-Security and WS-Addressing headers")
        return soap_envelope_str
    
    def _submit_with_retry(self, soap_envelope: str) -> tuple[str, int]:
        """Submit SOAP request with retry logic.
        
        Implements exponential backoff retry logic for transient errors
        (connection errors, timeouts, 5xx server errors).
        
        Args:
            soap_envelope: Complete SOAP envelope XML string
            
        Returns:
            Tuple of (response_xml, status_code)
            
        Raises:
            requests.ConnectionError: After max retries exceeded
            requests.Timeout: After max retries exceeded
            requests.exceptions.SSLError: On TLS/certificate errors (no retry)
            requests.HTTPError: On 4xx client errors (no retry)
        """
        backoff_delays = [1, 2, 4, 8, 16]  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"PIX Add submission attempt {attempt}/{self.max_retries}")
                
                response = self.session.post(
                    self.endpoint_url,
                    data=soap_envelope.encode('utf-8'),
                    headers={
                        'Content-Type': 'application/soap+xml; charset=utf-8',
                        'SOAPAction': 'urn:hl7-org:v3:PRPA_IN201301UV02'
                    },
                    timeout=self.timeout
                )
                
                # Handle HTTP error responses
                if response.status_code >= 400:
                    logger.warning(
                        f"HTTP error {response.status_code} from PIX Add endpoint"
                    )
                    
                    # 4xx errors are client errors - do not retry
                    if 400 <= response.status_code < 500:
                        response.raise_for_status()
                    
                    # 5xx errors are server errors - retry if attempts remain
                    if attempt == self.max_retries:
                        response.raise_for_status()
                    else:
                        delay = backoff_delays[min(attempt - 1, len(backoff_delays) - 1)]
                        logger.warning(
                            f"Retry {attempt}/{self.max_retries} after {delay}s delay "
                            f"(HTTP {response.status_code})"
                        )
                        time.sleep(delay)
                        continue
                
                # Success - return response
                logger.debug(f"PIX Add request successful (HTTP {response.status_code})")
                return response.text, response.status_code
                
            except requests.exceptions.SSLError as e:
                # SSL errors are permanent - do not retry
                logger.error(
                    f"SSL certificate validation failed for {self.endpoint_url}. "
                    f"Check server certificate or TLS configuration. Error: {e}"
                )
                raise
                
            except requests.ConnectionError as e:
                if attempt == self.max_retries:
                    logger.error(
                        f"Could not connect to PIX Add endpoint at {self.endpoint_url} "
                        f"after {self.max_retries} attempts. "
                        f"Check network connectivity and endpoint URL. Error: {e}"
                    )
                    raise
                else:
                    delay = backoff_delays[min(attempt - 1, len(backoff_delays) - 1)]
                    logger.warning(
                        f"Connection error on attempt {attempt}/{self.max_retries}. "
                        f"Retrying after {delay}s delay. Error: {e}"
                    )
                    time.sleep(delay)
                    
            except requests.Timeout as e:
                if attempt == self.max_retries:
                    logger.error(
                        f"Request timeout after {self.timeout}s on attempt {attempt}/{self.max_retries}. "
                        f"Consider increasing timeout configuration (current: {self.timeout}s). "
                        f"Error: {e}"
                    )
                    raise
                else:
                    delay = backoff_delays[min(attempt - 1, len(backoff_delays) - 1)]
                    logger.warning(
                        f"Timeout on attempt {attempt}/{self.max_retries}. "
                        f"Retrying after {delay}s delay."
                    )
                    time.sleep(delay)
        
        # Should not reach here, but raise error if we do
        raise RuntimeError("Retry logic error - should not reach this point")
    
    def _parse_acknowledgment(
        self,
        response_xml: str,
        request_id: str,
        processing_time_ms: int
    ) -> TransactionResponse:
        """Parse HL7v3 MCCI_IN000002UV01 acknowledgment response.
        
        Args:
            response_xml: Complete SOAP response XML
            request_id: Original request message ID
            processing_time_ms: Round-trip latency in milliseconds
            
        Returns:
            TransactionResponse with parsed acknowledgment details
            
        Raises:
            ValueError: If response XML is malformed or missing required elements
        """
        logger.debug("Parsing PIX Add acknowledgment response")
        
        try:
            # Parse acknowledgment using parsers module
            ack = parse_acknowledgment(response_xml)
            
            # Map HL7 status codes to TransactionStatus
            if ack.status == "AA":
                status = TransactionStatus.SUCCESS
            else:
                status = TransactionStatus.ERROR
            
            # Extract error messages from acknowledgment details
            error_messages = [detail.text for detail in ack.details if detail.text]
            
            # Create transaction response
            transaction_response = TransactionResponse(
                response_id=ack.message_id or str(uuid.uuid4()),
                request_id=request_id,
                transaction_type=TransactionType.PIX_ADD,
                status=status,
                status_code=ack.status,
                response_timestamp=datetime.now(timezone.utc),
                response_xml=response_xml,
                extracted_identifiers=ack.patient_identifiers,
                error_messages=error_messages,
                processing_time_ms=processing_time_ms
            )
            
            logger.debug(
                f"Parsed acknowledgment: status={ack.status}, "
                f"success={ack.is_success}, errors={len(error_messages)}"
            )
            
            return transaction_response
            
        except Exception as e:
            logger.error(f"Failed to parse acknowledgment response: {e}")
            
            # Return error response
            return TransactionResponse(
                response_id=str(uuid.uuid4()),
                request_id=request_id,
                transaction_type=TransactionType.PIX_ADD,
                status=TransactionStatus.ERROR,
                status_code="PARSE_ERROR",
                response_timestamp=datetime.now(timezone.utc),
                response_xml=response_xml,
                error_messages=[f"Failed to parse acknowledgment: {e}"],
                processing_time_ms=processing_time_ms
            )
    
    def _extract_message_id(self, hl7v3_message: str) -> str:
        """Extract message ID from HL7v3 message.
        
        Args:
            hl7v3_message: HL7v3 message XML string
            
        Returns:
            Message ID or generated UUID if not found
        """
        try:
            root = etree.fromstring(hl7v3_message.encode('utf-8'))
            hl7_ns = "urn:hl7-org:v3"
            
            # Try to find id element in PRPA_IN201301UV02
            id_elem = root.find(f".//{{{hl7_ns}}}PRPA_IN201301UV02/{{{hl7_ns}}}id")
            if id_elem is not None:
                msg_id = id_elem.get('root', '')
                if msg_id:
                    return msg_id
            
            # Fallback to generating UUID
            return str(uuid.uuid4())
            
        except Exception as e:
            logger.warning(f"Could not extract message ID: {e}")
            return str(uuid.uuid4())
    
    def _log_transaction(
        self,
        request_xml: str,
        response_xml: Optional[str],
        status: str,
        request_id: str,
        error_message: Optional[str] = None
    ) -> None:
        """Log complete transaction to audit trail.
        
        Logs complete SOAP request and response to audit file for debugging
        and compliance. CRITICAL: All IHE transactions MUST log complete
        request/response (RULE 2).
        
        Args:
            request_xml: Complete SOAP request envelope
            response_xml: Complete SOAP response envelope (None if error)
            status: Transaction status (SENDING, SUCCESS, ERROR, RETRY)
            request_id: Request message ID for correlation
            error_message: Error message if status is ERROR
        """
        # Create audit log directory if it doesn't exist
        log_dir = Path("logs/transactions")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create audit logger for transactions
        audit_logger = logging.getLogger('ihe_test_util.audit.pix_add')
        audit_logger.setLevel(logging.DEBUG)
        
        # Add file handler if not already present
        if not audit_logger.handlers:
            timestamp = datetime.now().strftime('%Y%m%d')
            log_file = log_dir / f"pix-add-{timestamp}.log"
            
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            audit_logger.addHandler(handler)
        
        # Log transaction details
        audit_logger.info(
            f"PIX Add Transaction - Status: {status}, "
            f"RequestID: {request_id}, "
            f"Endpoint: {self.endpoint_url}"
        )
        
        # Log complete request XML (RULE 2 - MANDATORY)
        audit_logger.debug(f"Request XML:\n{request_xml}")
        
        # Log complete response XML (RULE 2 - MANDATORY)
        if response_xml:
            audit_logger.debug(f"Response XML:\n{response_xml}")
        
        # Log error message if present
        if error_message:
            audit_logger.error(f"Error: {error_message}")
        
        logger.debug(f"Transaction logged to audit trail: {status}")
