"""Error summary collection and reporting for batch processing.

This module provides tools for aggregating errors across batch processing
and generating human-readable summary reports with remediation guidance.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ihe_test_util.utils.exceptions import ErrorCategory, ErrorInfo

logger = logging.getLogger(__name__)


@dataclass
class ErrorSummary:
    """Aggregated error statistics for batch processing.
    
    Attributes:
        total_errors: Total number of errors encountered
        errors_by_category: Count of errors by category (TRANSIENT, PERMANENT, CRITICAL)
        errors_by_type: Count of errors by exception type
        affected_patients: List of patient IDs affected by each error type
        most_common_errors: List of (error_type, count) tuples sorted by frequency
        error_rate: Percentage of operations that failed
        
    Example:
        >>> summary = collector.get_summary()
        >>> print(f"Total errors: {summary.total_errors}")
        >>> print(f"Critical: {summary.errors_by_category[ErrorCategory.CRITICAL]}")
    """
    
    total_errors: int = 0
    errors_by_category: Dict[ErrorCategory, int] = field(default_factory=dict)
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    affected_patients: Dict[str, List[str]] = field(default_factory=dict)
    most_common_errors: List[tuple] = field(default_factory=list)
    error_rate: float = 0.0


class ErrorSummaryCollector:
    """Collects and aggregates errors during batch processing.
    
    Tracks errors by category, type, and affected patients to generate
    comprehensive error summaries with remediation guidance.
    
    Attributes:
        errors: List of all ErrorInfo objects collected
        patient_count: Total number of patients processed
        
    Example:
        >>> collector = ErrorSummaryCollector()
        >>> collector.add_error(error_info, patient_id="PAT123")
        >>> summary = collector.get_summary()
        >>> report = generate_error_report(summary)
        >>> print(report)
    """
    
    def __init__(self) -> None:
        """Initialize error summary collector."""
        self.errors: List[ErrorInfo] = []
        self.patient_count: int = 0
        logger.debug("Error summary collector initialized")
    
    def add_error(
        self,
        error_info: ErrorInfo,
        patient_id: Optional[str] = None
    ) -> None:
        """Add error to collection.
        
        Args:
            error_info: Structured error information
            patient_id: Optional patient ID if error during patient processing
            
        Example:
            >>> error_info = create_error_info(exception, patient_id="PAT123")
            >>> collector.add_error(error_info, patient_id="PAT123")
        """
        # Set patient_id if not already in error_info
        if patient_id and not error_info.patient_id:
            error_info.patient_id = patient_id
        
        self.errors.append(error_info)
        
        logger.debug(
            f"Error added to collection: {error_info.error_type} "
            f"(category: {error_info.category.value}, patient: {patient_id})"
        )
    
    def set_patient_count(self, count: int) -> None:
        """Set total patient count for error rate calculation.
        
        Args:
            count: Total number of patients in batch
        """
        self.patient_count = count
        logger.debug(f"Patient count set to {count}")
    
    def get_summary(self) -> ErrorSummary:
        """Generate error summary with aggregated statistics.
        
        Returns:
            ErrorSummary with counts, percentages, and affected patients
            
        Example:
            >>> summary = collector.get_summary()
            >>> print(f"Total: {summary.total_errors}")
        """
        logger.info(f"Generating error summary for {len(self.errors)} errors")
        
        # Initialize counters
        errors_by_category: Dict[ErrorCategory, int] = defaultdict(int)
        errors_by_type: Dict[str, int] = defaultdict(int)
        affected_patients: Dict[str, List[str]] = defaultdict(list)
        
        # Aggregate errors
        for error in self.errors:
            # Count by category
            errors_by_category[error.category] += 1
            
            # Count by type
            errors_by_type[error.error_type] += 1
            
            # Track affected patients
            if error.patient_id:
                affected_patients[error.error_type].append(error.patient_id)
        
        # Sort errors by frequency
        most_common_errors = sorted(
            errors_by_type.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Calculate error rate
        error_rate = 0.0
        if self.patient_count > 0:
            error_rate = (len(self.errors) / self.patient_count) * 100
        
        summary = ErrorSummary(
            total_errors=len(self.errors),
            errors_by_category=dict(errors_by_category),
            errors_by_type=dict(errors_by_type),
            affected_patients=dict(affected_patients),
            most_common_errors=most_common_errors,
            error_rate=error_rate
        )
        
        logger.info(
            f"Error summary generated: {summary.total_errors} total errors, "
            f"{len(errors_by_category)} categories, {len(errors_by_type)} types"
        )
        
        return summary


def generate_error_report(
    summary: ErrorSummary,
    max_patients_per_error: int = 5
) -> str:
    """Generate human-readable error summary report.
    
    Creates formatted terminal output with error statistics, breakdown by
    category and type, remediation suggestions, and affected patient lists.
    
    Args:
        summary: Error summary with aggregated statistics
        max_patients_per_error: Maximum patient IDs to show per error type
        
    Returns:
        Formatted error report string
        
    Example:
        >>> report = generate_error_report(summary)
        >>> print(report)
    """
    logger.info("Generating error report")
    
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("ERROR SUMMARY REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    # Overall statistics
    lines.append(f"Total Errors: {summary.total_errors}")
    if summary.error_rate > 0:
        lines.append(f"Error Rate:   {summary.error_rate:.1f}%")
    lines.append("")
    
    # Category breakdown
    if summary.errors_by_category:
        lines.append("-" * 80)
        lines.append("CATEGORY BREAKDOWN")
        lines.append("-" * 80)
        
        total = summary.total_errors
        
        transient_count = summary.errors_by_category.get(ErrorCategory.TRANSIENT, 0)
        if transient_count > 0:
            pct = (transient_count / total) * 100 if total > 0 else 0
            lines.append(f"Transient Errors (Retry):     {transient_count:3d} ({pct:5.1f}%)")
        
        permanent_count = summary.errors_by_category.get(ErrorCategory.PERMANENT, 0)
        if permanent_count > 0:
            pct = (permanent_count / total) * 100 if total > 0 else 0
            lines.append(f"Permanent Errors (Skip):      {permanent_count:3d} ({pct:5.1f}%)")
        
        critical_count = summary.errors_by_category.get(ErrorCategory.CRITICAL, 0)
        if critical_count > 0:
            pct = (critical_count / total) * 100 if total > 0 else 0
            lines.append(f"Critical Errors (Halt):       {critical_count:3d} ({pct:5.1f}%)")
        
        lines.append("")
    
    # Error type frequencies
    if summary.most_common_errors:
        lines.append("-" * 80)
        lines.append("ERROR TYPE FREQUENCIES")
        lines.append("-" * 80)
        
        for idx, (error_type, count) in enumerate(summary.most_common_errors[:10], 1):
            pct = (count / summary.total_errors) * 100 if summary.total_errors > 0 else 0
            lines.append(f"{idx}. {error_type:30s} {count:3d} ({pct:5.1f}%)")
        
        lines.append("")
    
    # Top remediations
    if summary.most_common_errors:
        lines.append("-" * 80)
        lines.append("TOP REMEDIATIONS")
        lines.append("-" * 80)
        
        # Get remediation for top 3 errors
        for idx, (error_type, count) in enumerate(summary.most_common_errors[:3], 1):
            lines.append(f"{idx}. {error_type} ({count} occurrences):")
            
            # Get remediation from first error of this type
            remediation = _get_remediation_for_type(error_type)
            if remediation:
                # Indent remediation message
                for line in remediation.split(". "):
                    if line.strip():
                        lines.append(f"   → {line.strip()}")
            
            lines.append("")
        
        lines.append("")
    
    # Affected patients
    if summary.affected_patients:
        lines.append("-" * 80)
        lines.append("AFFECTED PATIENTS")
        lines.append("-" * 80)
        
        for error_type, patient_ids in list(summary.affected_patients.items())[:5]:
            # Show first N patient IDs
            shown_ids = patient_ids[:max_patients_per_error]
            remaining = len(patient_ids) - len(shown_ids)
            
            patient_list = ", ".join(shown_ids)
            if remaining > 0:
                patient_list += f" (+{remaining} more)"
            
            lines.append(f"{error_type}: {patient_list}")
        
        lines.append("")
    
    # Recommendations
    if summary.most_common_errors:
        lines.append("-" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 80)
        
        # Generate recommendations based on most common errors
        top_error_type = summary.most_common_errors[0][0]
        top_error_count = summary.most_common_errors[0][1]
        top_error_pct = (top_error_count / summary.total_errors) * 100 if summary.total_errors > 0 else 0
        
        lines.append(
            f"• Address {top_error_type} first ({top_error_pct:.0f}% of errors)"
        )
        
        # Category-specific recommendations
        if summary.errors_by_category.get(ErrorCategory.CRITICAL, 0) > 0:
            lines.append("• Critical errors require immediate attention before continuing")
        
        if summary.errors_by_category.get(ErrorCategory.TRANSIENT, 0) > 0:
            lines.append("• Transient errors may resolve with retry or timeout adjustments")
        
        if summary.errors_by_category.get(ErrorCategory.PERMANENT, 0) > 0:
            lines.append("• Permanent errors require data correction or configuration changes")
        
        lines.append("")
    
    lines.append("=" * 80)
    
    report = "\n".join(lines)
    
    logger.info("Error report generated")
    
    return report


def _get_remediation_for_type(error_type: str) -> str:
    """Get remediation message for an error type.
    
    Args:
        error_type: Exception class name
        
    Returns:
        Remediation message
    """
    # Map error types to remediation messages
    remediation_map = {
        "ConnectionError": (
            "Check endpoint URL in config.json. "
            "Verify network connectivity: ping/curl. "
            "Check firewall rules. "
            "Verify endpoint is running and accessible."
        ),
        "Timeout": (
            "Consider increasing timeout in config.json. "
            "Check endpoint performance/load. "
            "Verify network latency."
        ),
        "ValidationError": (
            "Review CSV data for validation errors. "
            "Check required fields are present. "
            "Verify data formats match specifications."
        ),
        "SSLError": (
            "For development with self-signed certs, set verify_tls=false in config.json. "
            "For production, ensure valid certificate chain. "
            "Check certificate expiration date."
        ),
        "CertificateExpiredError": (
            "Generate new certificate: scripts/generate_cert.sh. "
            "Update config.json with new certificate path."
        ),
        "ConfigurationError": (
            "Check config.json for missing or invalid values. "
            "Use examples/config.example.json as template. "
            "Ensure all required fields are present."
        ),
        "HL7v3Error": (
            "Review HL7v3 message structure. "
            "Check IHE PIX Add (ITI-44) specification compliance. "
            "Verify required elements are present."
        ),
    }
    
    return remediation_map.get(error_type, "Review error message and consult documentation.")
