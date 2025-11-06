"""Custom log formatters for the IHE Test Utility.

This module provides specialized formatters for logging, including PII redaction.
"""

import logging
import re
from typing import List, Tuple


class PIIRedactingFormatter(logging.Formatter):
    """Custom formatter that redacts Personally Identifiable Information (PII) from log messages.
    
    This formatter applies regex-based pattern matching to identify and redact
    sensitive information such as patient names and Social Security Numbers (SSNs).
    
    Attributes:
        redact_pii: Whether to enable PII redaction
        patterns: List of (regex_pattern, replacement_text) tuples for redaction
        
    Example:
        >>> formatter = PIIRedactingFormatter(
        ...     fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        ...     redact_pii=True
        ... )
        >>> handler = logging.StreamHandler()
        >>> handler.setFormatter(formatter)
    """
    
    def __init__(
        self,
        fmt: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt: str | None = None,
        redact_pii: bool = False,
    ) -> None:
        """Initialize the PIIRedactingFormatter.
        
        Args:
            fmt: Log message format string
            datefmt: Date format string (optional)
            redact_pii: Whether to enable PII redaction
        """
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.redact_pii = redact_pii
        
        # Define redaction patterns: (regex, replacement_text)
        self.patterns: List[Tuple[re.Pattern[str], str]] = [
            # SSN pattern: 123-45-6789
            (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN-REDACTED]'),
            
            # Patient name patterns in common formats
            # Matches: name="John Doe", name='Jane Smith', name=Bob Jones
            (re.compile(r'name=["\']?([^"\']+)["\']?'), 'name=[NAME-REDACTED]'),
            
            # Additional name patterns in log messages
            # Matches: "Patient: John Doe", "Name: Jane Smith"
            (re.compile(r'(?:Patient|Name):\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'), 
             r'\1: [NAME-REDACTED]'),
        ]
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with optional PII redaction.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log message with PII redacted if enabled
        """
        # Get the original formatted message
        original = super().format(record)
        
        # Apply redaction if enabled
        if self.redact_pii:
            for pattern, replacement in self.patterns:
                original = pattern.sub(replacement, original)
        
        return original
