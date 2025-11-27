"""Batch processing data models.

This module defines data models for batch processing workflows including
patient results and batch processing summaries.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ihe_test_util.models.responses import TransactionStatus


@dataclass
class PatientWorkflowResult:
    """Per-patient workflow status tracking for integrated PIX Add + ITI-41 workflow.
    
    Tracks the outcome of processing a single patient through the complete
    workflow: CSV parsing → CCD generation → PIX Add → ITI-41 submission.
    
    Status values use strings: "pending", "success", "failed", "skipped"
    
    Attributes:
        patient_id: Patient identifier from source CSV
        csv_parsed: Whether CSV row was successfully parsed
        ccd_generated: Whether CCD was successfully generated
        pix_add_status: PIX Add transaction status ("pending", "success", "failed")
        pix_add_message: Human-readable PIX Add status or error message
        pix_enterprise_id: Enterprise patient ID from PIX Add response
        pix_enterprise_id_oid: OID for enterprise patient ID domain
        iti41_status: ITI-41 transaction status ("pending", "success", "failed", "skipped")
        iti41_message: Human-readable ITI-41 status or error message
        document_id: Document unique ID from ITI-41 response
        pix_add_time_ms: Time taken for PIX Add transaction (milliseconds)
        iti41_time_ms: Time taken for ITI-41 transaction (milliseconds)
        total_time_ms: Total time for patient processing (milliseconds)
        error_message: Primary error message for troubleshooting
        
    Example:
        >>> result = PatientWorkflowResult(
        ...     patient_id="PAT001",
        ...     csv_parsed=True,
        ...     ccd_generated=True,
        ...     pix_add_status="success",
        ...     pix_add_message="Patient registered successfully",
        ...     pix_enterprise_id="12345",
        ...     iti41_status="success",
        ...     iti41_message="Document submitted successfully",
        ...     pix_add_time_ms=250,
        ...     iti41_time_ms=500,
        ...     total_time_ms=750
        ... )
    """
    
    patient_id: str
    csv_parsed: bool = False
    ccd_generated: bool = False
    pix_add_status: str = "pending"  # "pending", "success", "failed"
    pix_add_message: str = ""
    pix_enterprise_id: Optional[str] = None
    pix_enterprise_id_oid: Optional[str] = None
    iti41_status: str = "pending"  # "pending", "success", "failed", "skipped"
    iti41_message: str = ""
    document_id: Optional[str] = None
    pix_add_time_ms: int = 0
    iti41_time_ms: int = 0
    total_time_ms: int = 0
    error_message: Optional[str] = None
    
    @property
    def is_fully_successful(self) -> bool:
        """Check if both PIX Add and ITI-41 were successful.
        
        Returns:
            True if both transactions succeeded
        """
        return self.pix_add_status == "success" and self.iti41_status == "success"
    
    @property
    def pix_add_success(self) -> bool:
        """Check if PIX Add was successful.
        
        Returns:
            True if PIX Add succeeded
        """
        return self.pix_add_status == "success"
    
    @property
    def iti41_success(self) -> bool:
        """Check if ITI-41 was successful.
        
        Returns:
            True if ITI-41 succeeded
        """
        return self.iti41_status == "success"
    
    @property
    def complete_success(self) -> bool:
        """Alias for is_fully_successful for backwards compatibility.
        
        Returns:
            True if both transactions succeeded
        """
        return self.is_fully_successful
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of patient workflow result
        """
        return {
            "patient_id": self.patient_id,
            "csv_parsed": self.csv_parsed,
            "ccd_generated": self.ccd_generated,
            "pix_add": {
                "status": self.pix_add_status,
                "message": self.pix_add_message,
                "enterprise_id": self.pix_enterprise_id,
                "enterprise_id_oid": self.pix_enterprise_id_oid,
                "time_ms": self.pix_add_time_ms,
            },
            "iti41": {
                "status": self.iti41_status,
                "message": self.iti41_message,
                "document_id": self.document_id,
                "time_ms": self.iti41_time_ms,
            },
            "total_time_ms": self.total_time_ms,
            "error_message": self.error_message,
        }


@dataclass
class BatchWorkflowResult:
    """Result of batch processing multiple patients through integrated workflow.
    
    Aggregates results from processing an entire batch of patients through
    the complete PIX Add + ITI-41 workflow including statistics, timing,
    and per-patient outcomes.
    
    Attributes:
        batch_id: Unique identifier for this batch
        csv_file: Path to source CSV file
        ccd_template: Path to CCD template file
        start_timestamp: When batch processing started (UTC)
        end_timestamp: When batch processing completed (UTC)
        patient_results: List of individual patient workflow results
        
    Example:
        >>> result = BatchWorkflowResult(
        ...     batch_id="550e8400-e29b-41d4-a716-446655440000",
        ...     csv_file="patients.csv",
        ...     ccd_template="template.xml",
        ...     start_timestamp=datetime.now(),
        ...     patient_results=[]
        ... )
    """
    
    batch_id: str
    csv_file: str
    ccd_template: str
    start_timestamp: datetime
    end_timestamp: Optional[datetime] = None
    patient_results: List["PatientWorkflowResult"] = field(default_factory=list)
    
    @property
    def total_patients(self) -> int:
        """Total number of patients processed."""
        return len(self.patient_results)
    
    @property
    def fully_successful_count(self) -> int:
        """Number of patients with both PIX Add and ITI-41 success."""
        return sum(1 for r in self.patient_results if r.is_fully_successful)
    
    @property
    def pix_add_success_count(self) -> int:
        """Number of successful PIX Add registrations."""
        return sum(1 for r in self.patient_results if r.pix_add_status == "success")
    
    @property
    def pix_add_failed_count(self) -> int:
        """Number of failed PIX Add registrations."""
        return sum(1 for r in self.patient_results if r.pix_add_status == "failed")
    
    @property
    def iti41_success_count(self) -> int:
        """Number of successful ITI-41 submissions."""
        return sum(1 for r in self.patient_results if r.iti41_status == "success")
    
    @property
    def iti41_failed_count(self) -> int:
        """Number of failed ITI-41 submissions."""
        return sum(1 for r in self.patient_results if r.iti41_status == "failed")
    
    @property
    def iti41_skipped_count(self) -> int:
        """Number of skipped ITI-41 submissions (due to PIX Add failure)."""
        return sum(1 for r in self.patient_results if r.iti41_status == "skipped")
    
    @property
    def full_success_rate(self) -> float:
        """Calculate full success rate (both PIX Add and ITI-41) as percentage."""
        if self.total_patients == 0:
            return 0.0
        return (self.fully_successful_count / self.total_patients) * 100
    
    @property
    def pix_add_success_rate(self) -> float:
        """Calculate PIX Add success rate as percentage."""
        if self.total_patients == 0:
            return 0.0
        return (self.pix_add_success_count / self.total_patients) * 100
    
    @property
    def iti41_success_rate(self) -> float:
        """Calculate ITI-41 success rate as percentage (of attempted, not total)."""
        attempted = self.pix_add_success_count  # ITI-41 only attempted if PIX Add succeeded
        if attempted == 0:
            return 0.0
        return (self.iti41_success_count / attempted) * 100
    
    @property
    def total_duration_seconds(self) -> Optional[float]:
        """Calculate batch processing duration in seconds."""
        if self.end_timestamp is None:
            return None
        return (self.end_timestamp - self.start_timestamp).total_seconds()
    
    @property
    def average_patient_time_seconds(self) -> Optional[float]:
        """Calculate average processing time per patient in seconds."""
        if not self.patient_results:
            return None
        total_ms = sum(r.total_time_ms for r in self.patient_results)
        return (total_ms / len(self.patient_results)) / 1000
    
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
    def duration_formatted(self) -> str:
        """Get formatted duration string (e.g., '5 minutes 30 seconds').
        
        Returns:
            Formatted duration string
        """
        if self.duration_seconds is None:
            return "In progress"
        total_seconds = int(self.duration_seconds)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        if minutes > 0:
            return f"{minutes} minutes {seconds} seconds"
        return f"{seconds} seconds"
    
    @property
    def average_processing_time_ms(self) -> Optional[float]:
        """Calculate average processing time per patient.
        
        Returns:
            Average time in milliseconds, or None if no results
        """
        if not self.patient_results:
            return None
        total_time = sum(r.total_time_ms for r in self.patient_results)
        return total_time / len(self.patient_results)
    
    @property
    def throughput_per_minute(self) -> Optional[float]:
        """Calculate throughput in patients per minute.
        
        Returns:
            Patients per minute, or None if not enough data
        """
        if self.duration_seconds is None or self.duration_seconds == 0:
            return None
        return (len(self.patient_results) / self.duration_seconds) * 60
    
    def get_pix_add_success_rate(self) -> float:
        """Calculate PIX Add success rate as percentage.
        
        Returns:
            Success rate (0.0 to 100.0)
        """
        if self.total_patients == 0:
            return 0.0
        return (self.pix_add_success_count / self.total_patients) * 100
    
    def get_iti41_success_rate(self) -> float:
        """Calculate ITI-41 success rate as percentage.
        
        Returns:
            Success rate (0.0 to 100.0)
        """
        if self.total_patients == 0:
            return 0.0
        return (self.iti41_success_count / self.total_patients) * 100
    
    def get_overall_success_rate(self) -> float:
        """Calculate overall success rate (both PIX Add and ITI-41).
        
        Returns:
            Success rate (0.0 to 100.0)
        """
        if self.total_patients == 0:
            return 0.0
        return (self.fully_successful_count / self.total_patients) * 100
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of batch workflow result
        """
        return {
            "batch_id": self.batch_id,
            "csv_file": self.csv_file,
            "ccd_template": self.ccd_template,
            "start_timestamp": self.start_timestamp.isoformat(),
            "end_timestamp": self.end_timestamp.isoformat() if self.end_timestamp else None,
            "summary": {
                "total_patients": self.total_patients,
                "fully_successful": self.fully_successful_count,
                "pix_add_success": self.pix_add_success_count,
                "pix_add_failed": self.pix_add_failed_count,
                "iti41_success": self.iti41_success_count,
                "iti41_failed": self.iti41_failed_count,
                "iti41_skipped": self.iti41_skipped_count,
                "full_success_rate": self.full_success_rate,
                "pix_add_success_rate": self.pix_add_success_rate,
            },
            "processing_time_ms": int(self.duration_seconds * 1000) if self.duration_seconds else None,
            "average_processing_time_ms": self.average_processing_time_ms,
            "patients": [r.to_dict() for r in self.patient_results],
        }


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
