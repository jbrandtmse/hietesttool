"""Transaction response data models.

This module defines data models for IHE transaction responses including
PIX Add acknowledgments and ITI-41 registry responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class TransactionType(Enum):
    """IHE transaction types."""
    
    PIX_ADD = "PIX_ADD"
    ITI_41 = "ITI_41"
    PIX_QUERY = "PIX_QUERY"
    XCPD = "XCPD"


class TransactionStatus(Enum):
    """Transaction processing status."""
    
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"


@dataclass
class TransactionResponse:
    """Response from an IHE transaction.
    
    Contains all information about a transaction response including status,
    timing, identifiers, and any error messages.
    
    Attributes:
        response_id: Unique response message ID
        request_id: Original request message ID
        transaction_type: Type of transaction (PIX_ADD, ITI_41, etc.)
        status: Transaction status (SUCCESS, ERROR, etc.)
        status_code: HL7/XDSb status code (AA, AE, AR, Success, Failure)
        response_timestamp: When response was received
        response_xml: Complete SOAP response XML
        extracted_identifiers: Patient IDs or document IDs extracted from response
        error_messages: List of error messages if any
        processing_time_ms: Round-trip latency in milliseconds
        
    Example:
        >>> response = TransactionResponse(
        ...     response_id="ACK-123",
        ...     request_id="MSG-456",
        ...     transaction_type=TransactionType.PIX_ADD,
        ...     status=TransactionStatus.SUCCESS,
        ...     status_code="AA",
        ...     response_timestamp=datetime.now(),
        ...     response_xml="<SOAP>...</SOAP>",
        ...     processing_time_ms=250
        ... )
    """
    
    response_id: str
    request_id: str
    transaction_type: TransactionType
    status: TransactionStatus
    status_code: str
    response_timestamp: datetime
    response_xml: str
    extracted_identifiers: Dict[str, str] = field(default_factory=dict)
    error_messages: List[str] = field(default_factory=list)
    processing_time_ms: int = 0
    
    @property
    def is_success(self) -> bool:
        """Check if transaction was successful.
        
        Returns:
            True if status is SUCCESS or PARTIAL_SUCCESS
        """
        return self.status in (TransactionStatus.SUCCESS, TransactionStatus.PARTIAL_SUCCESS)
    
    @property
    def has_errors(self) -> bool:
        """Check if transaction has errors.
        
        Returns:
            True if error_messages is not empty
        """
        return len(self.error_messages) > 0
