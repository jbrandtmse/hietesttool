"""Zeep SOAP client wrapper for IHE transactions."""

import logging
from typing import Optional, Dict, Any
from zeep import Client
from zeep.transports import Transport
from requests import Session

logger = logging.getLogger(__name__)


class SOAPClient:
    """Wrapper for zeep SOAP client with IHE-specific configuration.
    
    Attributes:
        endpoint_url: The SOAP endpoint URL
        timeout: Request timeout in seconds
    """

    def __init__(self, endpoint_url: str, timeout: int = 60):
        """Initialize SOAP client.
        
        Args:
            endpoint_url: The SOAP endpoint URL
            timeout: Request timeout in seconds (default: 60)
        """
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        
        # Create requests session with timeout
        session = Session()
        session.timeout = timeout
        
        # Create zeep transport
        self.transport = Transport(session=session)
        
        logger.info(f"Initialized SOAP client for endpoint: {endpoint_url}")

    def create_client(self, wsdl_url: Optional[str] = None) -> Client:
        """Create zeep client instance.
        
        Args:
            wsdl_url: Optional WSDL URL (if None, uses endpoint_url)
            
        Returns:
            Configured zeep Client instance
        """
        target_wsdl = wsdl_url or self.endpoint_url
        logger.debug(f"Creating zeep client with WSDL: {target_wsdl}")
        
        return Client(target_wsdl, transport=self.transport)
