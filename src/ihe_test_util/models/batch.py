"""Batch processing data models.

This module defines data models for batch processing workflows including
patient results, batch processing summaries, checkpoints, and statistics.

Extended in Story 6.6 with:
- BatchCheckpoint for resumable batch processing
- BatchStatistics for throughput and latency metrics
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

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
class BatchCheckpoint:
    """Checkpoint for resumable batch processing (AC: 4).
    
    Enables saving and resuming batch processing state for large batches.
    Checkpoints are saved at configurable intervals and can be used to
    resume processing after interruption.
    
    Attributes:
        batch_id: Unique identifier for this batch
        csv_file_path: Path to source CSV file
        last_processed_index: Index of last successfully processed patient
        timestamp: When checkpoint was saved (UTC)
        completed_patient_ids: List of successfully processed patient IDs
        failed_patient_ids: List of failed patient IDs
        total_patients: Total number of patients in the batch
        
    Example:
        >>> checkpoint = BatchCheckpoint(
        ...     batch_id="550e8400-e29b-41d4-a716-446655440000",
        ...     csv_file_path="patients.csv",
        ...     last_processed_index=50,
        ...     timestamp=datetime.now(),
        ...     completed_patient_ids=["PAT001", "PAT002"],
        ...     failed_patient_ids=["PAT003"]
        ... )
        >>> json_str = checkpoint.to_json()
        >>> restored = BatchCheckpoint.from_json(json_str)
    """
    
    batch_id: str
    csv_file_path: str
    last_processed_index: int
    timestamp: datetime
    completed_patient_ids: List[str] = field(default_factory=list)
    failed_patient_ids: List[str] = field(default_factory=list)
    total_patients: int = 0
    
    def to_json(self) -> str:
        """Serialize checkpoint to JSON string.
        
        Returns:
            JSON string representation of checkpoint
        """
        data = {
            "batch_id": self.batch_id,
            "csv_file_path": self.csv_file_path,
            "last_processed_index": self.last_processed_index,
            "timestamp": self.timestamp.isoformat(),
            "completed_patient_ids": self.completed_patient_ids,
            "failed_patient_ids": self.failed_patient_ids,
            "total_patients": self.total_patients,
        }
        return json.dumps(data, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "BatchCheckpoint":
        """Deserialize checkpoint from JSON string.
        
        Args:
            json_str: JSON string representation of checkpoint
            
        Returns:
            BatchCheckpoint instance
            
        Raises:
            json.JSONDecodeError: If JSON is invalid
            KeyError: If required fields are missing
        """
        data = json.loads(json_str)
        return cls(
            batch_id=data["batch_id"],
            csv_file_path=data["csv_file_path"],
            last_processed_index=data["last_processed_index"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            completed_patient_ids=data.get("completed_patient_ids", []),
            failed_patient_ids=data.get("failed_patient_ids", []),
            total_patients=data.get("total_patients", 0),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of checkpoint
        """
        return {
            "batch_id": self.batch_id,
            "csv_file_path": self.csv_file_path,
            "last_processed_index": self.last_processed_index,
            "timestamp": self.timestamp.isoformat(),
            "completed_patient_ids": self.completed_patient_ids,
            "failed_patient_ids": self.failed_patient_ids,
            "total_patients": self.total_patients,
        }
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress as percentage.
        
        Returns:
            Progress percentage (0.0 to 100.0)
        """
        if self.total_patients == 0:
            return 0.0
        return (self.last_processed_index / self.total_patients) * 100


@dataclass
class BatchStatistics:
    """Statistics for batch processing (AC: 7).
    
    Provides performance metrics for batch processing including throughput,
    latency, and error rates.
    
    Attributes:
        throughput_patients_per_minute: Processing rate in patients per minute
        avg_latency_ms: Average processing time per patient (milliseconds)
        error_rate: Error rate as decimal (0.0 to 1.0)
        pix_add_avg_latency_ms: Average PIX Add transaction time (milliseconds)
        iti41_avg_latency_ms: Average ITI-41 transaction time (milliseconds)
        slowest_patient_id: Patient ID with longest processing time
        fastest_patient_id: Patient ID with shortest processing time
        total_processing_time_ms: Total batch processing time (milliseconds)
        min_latency_ms: Minimum patient processing time (milliseconds)
        max_latency_ms: Maximum patient processing time (milliseconds)
        
    Example:
        >>> stats = BatchStatistics(
        ...     throughput_patients_per_minute=25.5,
        ...     avg_latency_ms=2350,
        ...     error_rate=0.02,
        ...     pix_add_avg_latency_ms=800,
        ...     iti41_avg_latency_ms=1500,
        ...     total_processing_time_ms=235000
        ... )
    """
    
    throughput_patients_per_minute: float
    avg_latency_ms: float
    error_rate: float
    pix_add_avg_latency_ms: float
    iti41_avg_latency_ms: float
    slowest_patient_id: Optional[str] = None
    fastest_patient_id: Optional[str] = None
    total_processing_time_ms: int = 0
    min_latency_ms: Optional[float] = None
    max_latency_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of statistics
        """
        return {
            "throughput_patients_per_minute": round(self.throughput_patients_per_minute, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "error_rate": round(self.error_rate, 4),
            "error_rate_percentage": round(self.error_rate * 100, 2),
            "pix_add_avg_latency_ms": round(self.pix_add_avg_latency_ms, 2),
            "iti41_avg_latency_ms": round(self.iti41_avg_latency_ms, 2),
            "slowest_patient_id": self.slowest_patient_id,
            "fastest_patient_id": self.fastest_patient_id,
            "total_processing_time_ms": self.total_processing_time_ms,
            "min_latency_ms": round(self.min_latency_ms, 2) if self.min_latency_ms else None,
            "max_latency_ms": round(self.max_latency_ms, 2) if self.max_latency_ms else None,
        }
    
    @classmethod
    def calculate_from_results(
        cls, 
        patient_results: List["PatientWorkflowResult"],
        total_time_ms: int
    ) -> "BatchStatistics":
        """Calculate statistics from patient workflow results.
        
        Args:
            patient_results: List of patient workflow results
            total_time_ms: Total batch processing time in milliseconds
            
        Returns:
            BatchStatistics instance with calculated metrics
        """
        if not patient_results:
            return cls(
                throughput_patients_per_minute=0.0,
                avg_latency_ms=0.0,
                error_rate=0.0,
                pix_add_avg_latency_ms=0.0,
                iti41_avg_latency_ms=0.0,
                total_processing_time_ms=total_time_ms,
            )
        
        total_patients = len(patient_results)
        total_time_seconds = total_time_ms / 1000
        
        # Throughput calculation
        if total_time_seconds > 0:
            throughput = (total_patients / total_time_seconds) * 60
        else:
            throughput = 0.0
        
        # Latency calculations
        total_latency = sum(r.total_time_ms for r in patient_results)
        avg_latency = total_latency / total_patients if total_patients > 0 else 0
        
        # PIX Add latency
        pix_add_times = [r.pix_add_time_ms for r in patient_results if r.pix_add_time_ms > 0]
        pix_add_avg = sum(pix_add_times) / len(pix_add_times) if pix_add_times else 0
        
        # ITI-41 latency
        iti41_times = [r.iti41_time_ms for r in patient_results if r.iti41_time_ms > 0]
        iti41_avg = sum(iti41_times) / len(iti41_times) if iti41_times else 0
        
        # Error rate
        failed_count = sum(1 for r in patient_results if not r.is_fully_successful)
        error_rate = failed_count / total_patients if total_patients > 0 else 0
        
        # Find slowest and fastest
        patient_times = [(r.patient_id, r.total_time_ms) for r in patient_results if r.total_time_ms > 0]
        slowest_id = None
        fastest_id = None
        min_latency = None
        max_latency = None
        
        if patient_times:
            sorted_times = sorted(patient_times, key=lambda x: x[1])
            fastest_id = sorted_times[0][0]
            min_latency = float(sorted_times[0][1])
            slowest_id = sorted_times[-1][0]
            max_latency = float(sorted_times[-1][1])
        
        return cls(
            throughput_patients_per_minute=throughput,
            avg_latency_ms=avg_latency,
            error_rate=error_rate,
            pix_add_avg_latency_ms=pix_add_avg,
            iti41_avg_latency_ms=iti41_avg,
            slowest_patient_id=slowest_id,
            fastest_patient_id=fastest_id,
            total_processing_time_ms=total_time_ms,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
        )


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
        statistics: Batch processing statistics (Story 6.6)
        
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
    statistics: Optional[BatchStatistics] = None
    
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
        result = {
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
        
        # Include statistics if available (Story 6.6)
        if self.statistics:
            result["statistics"] = self.statistics.to_dict()
        
        return result
    
    def calculate_statistics(self) -> BatchStatistics:
        """Calculate and attach batch statistics.
        
        Calculates throughput, latency, and error metrics from patient results.
        Updates the statistics field and returns the calculated statistics.
        
        Returns:
            BatchStatistics instance with calculated metrics
        """
        total_time_ms = int(self.duration_seconds * 1000) if self.duration_seconds else 0
        self.statistics = BatchStatistics.calculate_from_results(
            self.patient_results, total_time_ms
        )
        return self.statistics


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
