"""Audit trail functionality for the IHE Test Utility.

This module provides structured audit logging for tracking operations,
transactions, and compliance requirements.
"""

import logging
import time
import uuid
from typing import Any, Dict

from .logger import get_logger

logger = get_logger(__name__)


def log_audit_event(event_type: str, details: Dict[str, Any]) -> None:
    """Log an audit trail event.
    
    Creates a structured audit log entry with standard fields for tracking
    operations and compliance. Audit events are logged at INFO level for
    successful operations and ERROR level for failures.
    
    Args:
        event_type: Type of operation (e.g., "CSV_PROCESSED", "VALIDATION_FAILED",
                   "PIX_ADD_SUBMITTED", "ITI41_SUBMITTED")
        details: Dictionary with event details. Common fields include:
                - input_file: Path to input file (if applicable)
                - record_count: Number of records processed
                - status: "success" or "failure"
                - duration: Operation duration in seconds
                - error_message: Error details (if status is failure)
                - correlation_id: Optional correlation ID for tracking related events
                
    Example:
        >>> log_audit_event("CSV_PROCESSED", {
        ...     "input_file": "patients.csv",
        ...     "record_count": 100,
        ...     "status": "success",
        ...     "duration": 2.5
        ... })
        >>> log_audit_event("VALIDATION_FAILED", {
        ...     "input_file": "patients.csv",
        ...     "record_count": 100,
        ...     "error_count": 5,
        ...     "status": "failure",
        ...     "error_message": "5 validation errors found"
        ... })
    """
    # Add timestamp and correlation ID if not present
    if "timestamp" not in details:
        details["timestamp"] = time.time()
    
    if "correlation_id" not in details:
        details["correlation_id"] = str(uuid.uuid4())
    
    # Build structured log message
    message_parts = [f"AUDIT [{event_type}]"]
    
    # Add key fields in consistent order
    field_order = [
        "status",
        "input_file",
        "record_count",
        "duration",
        "error_count",
        "error_message",
        "correlation_id",
    ]
    
    for field in field_order:
        if field in details:
            value = details[field]
            # Format duration with 2 decimal places
            if field == "duration" and isinstance(value, (int, float)):
                message_parts.append(f"{field}={value:.2f}s")
            else:
                message_parts.append(f"{field}={value}")
    
    # Add any remaining fields not in the standard order
    for key, value in details.items():
        if key not in field_order and key != "timestamp":
            message_parts.append(f"{key}={value}")
    
    audit_message = " | ".join(message_parts)
    
    # Log at appropriate level based on status
    status = details.get("status", "unknown")
    if status == "failure":
        logger.error(audit_message)
    else:
        logger.info(audit_message)


def log_transaction(
    transaction_type: str,
    request: str,
    response: str,
    status: str = "success",
) -> None:
    """Log a complete IHE transaction with request and response.
    
    This function is designed for logging complete SOAP transactions to meet
    compliance and debugging requirements. The transaction details are logged
    at DEBUG level to avoid cluttering INFO logs.
    
    Args:
        transaction_type: Type of transaction (e.g., "PIX_ADD", "ITI41_SUBMIT")
        request: Full request XML/SOAP envelope
        response: Full response XML/SOAP envelope
        status: Transaction status ("success" or "failure")
        
    Example:
        >>> request_xml = '<soap:Envelope>...</soap:Envelope>'
        >>> response_xml = '<soap:Envelope>...</soap:Envelope>'
        >>> log_transaction("PIX_ADD", request_xml, response_xml, "success")
    """
    correlation_id = str(uuid.uuid4())
    
    # Log transaction header at INFO level
    logger.info(
        f"TRANSACTION [{transaction_type}] | "
        f"status={status} | "
        f"correlation_id={correlation_id} | "
        f"request_size={len(request)} bytes | "
        f"response_size={len(response)} bytes"
    )
    
    # Log full request and response at DEBUG level
    logger.debug(
        f"TRANSACTION REQUEST [{transaction_type}] | "
        f"correlation_id={correlation_id}\n"
        f"{request}"
    )
    
    logger.debug(
        f"TRANSACTION RESPONSE [{transaction_type}] | "
        f"correlation_id={correlation_id}\n"
        f"{response}"
    )
