"""Batch processing data models.

This module defines data models for batch processing workflows including
patient results and batch processing summaries.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ihe_test_util.models.responses import TransactionStatus


@dataclass
class PatientResult:
    """Result of processing a single patient through PIX Add workflow.
    
    Tracks the outcome of registering a single patient including status,
    timing, and any error information.
    
    Attributes:
        patient_id: Patient identifier from source CSV
        pix_add_status: Transaction status (SUCCESS, ERROR, etc.)
        pix_add_message: Human-readable status or error message
        processing_time_ms: Time taken to process this patient (milliseconds)
        enterprise_id: Enterprise patient ID assigned by PIX Manager (if successful)
        enterprise_id_oid: OID for enterprise patient ID domain
        registration_timestamp: When patient was registered (UTC)
        error_details: Additional error context for troubleshooting
        
    Example:
        >>> result = PatientResult(
        ...     patient_id="PAT001",
        ...     pix_add_status=TransactionStatus.SUCCESS,
        ...     pix_add_message="Registration successful",
        ...     processing_time_ms=250
        ... )
    """
    
    patient_id: str
    pix_add_status: TransactionStatus
    pix_add_message: str
    processing_time_ms: int
    enterprise_id: Optional[str] = None
    enterprise_id_oid: Optional[str] = None
    registration_timestamp: Optional[datetime] = None
    error_details: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """Check if patient registration was successful.
        
        Returns:
            True if status is SUCCESS
        """
        return self.pix_add_status == TransactionStatus.SUCCESS
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of patient result
        """
        return {
            "patient_id": self.patient_id,
            "pix_add_status": self.pix_add_status.value,
            "pix_add_message": self.pix_add_message,
            "processing_time_ms": self.processing_time_ms,
            "enterprise_id": self.enterprise_id,
            "enterprise_id_oid": self.enterprise_id_oid,
            "registration_timestamp": self.registration_timestamp.isoformat() if self.registration_timestamp else None,
            "error_details": self.error_details
        }


@dataclass
class BatchProcessingResult:
    """Result of batch processing multiple patients through PIX Add workflow.
    
    Aggregates results from processing an entire batch of patients including
    statistics, timing, and per-patient outcomes.
    
    Attributes:
        batch_id: Unique identifier for this batch
        csv_file_path: Path to source CSV file
        start_timestamp: When batch processing started (UTC)
        end_timestamp: When batch processing completed (UTC)
        total_patients: Total number of patients in batch
        successful_patients: Number of successfully registered patients
        failed_patients: Number of failed patient registrations
        pix_add_success_count: Same as successful_patients for PIX Add only workflow
        patient_results: List of individual patient results
        error_summary: Summary of errors grouped by type
        
    Example:
        >>> result = BatchProcessingResult(
        ...     batch_id="550e8400-e29b-41d4-a716-446655440000",
        ...     csv_file_path="patients.csv",
        ...     start_timestamp=datetime.now(),
        ...     total_patients=10
        ... )
    """
    
    batch_id: str
    csv_file_path: str
    start_timestamp: datetime
    total_patients: int
    end_timestamp: Optional[datetime] = None
    successful_patients: int = 0
    failed_patients: int = 0
    pix_add_success_count: int = 0
    patient_results: List[PatientResult] = field(default_factory=list)
    error_summary: Dict[str, int] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate batch processing duration in seconds.
        
        Returns:
            Duration in seconds, or None if not yet completed
        """
        if self.end_timestamp is None:
            return None
        return (self.end_timestamp - self.start_timestamp).total_seconds()
    
    @property
    def average_processing_time_ms(self) -> Optional[float]:
        """Calculate average processing time per patient.
        
        Returns:
            Average time in milliseconds, or None if no results
        """
        if not self.patient_results:
            return None
        total_time = sum(r.processing_time_ms for r in self.patient_results)
        return total_time / len(self.patient_results)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage.
        
        Returns:
            Success rate (0.0 to 100.0)
        """
        if self.total_patients == 0:
            return 0.0
        return (self.successful_patients / self.total_patients) * 100
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of batch result
        """
        return {
            "batch_id": self.batch_id,
            "csv_file_path": self.csv_file_path,
            "start_timestamp": self.start_timestamp.isoformat(),
            "end_timestamp": self.end_timestamp.isoformat() if self.end_timestamp else None,
            "total_patients": self.total_patients,
            "successful_patients": self.successful_patients,
            "failed_patients": self.failed_patients,
            "pix_add_success_count": self.pix_add_success_count,
            "duration_seconds": self.duration_seconds,
            "average_processing_time_ms": self.average_processing_time_ms,
            "success_rate": self.success_rate,
            "patient_results": [r.to_dict() for r in self.patient_results],
            "error_summary": self.error_summary
        }
