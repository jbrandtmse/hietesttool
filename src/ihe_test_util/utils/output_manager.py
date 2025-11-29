"""Output directory management for batch processing results.

This module provides organized output directory structure for batch processing,
ensuring consistent file organization for logs, documents, results, and audit trails.

Directory Structure:
    output/
    ├── logs/           # Batch processing logs
    ├── documents/      # Generated CCD documents
    │   └── ccds/       # CCD XML files
    ├── results/        # Batch results and checkpoints
    └── audit/          # Audit trail files
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class OutputPaths:
    """Paths to output subdirectories for batch processing.
    
    Attributes:
        base_dir: Base output directory.
        logs_dir: Directory for log files.
        documents_dir: Directory for generated documents.
        ccds_dir: Subdirectory for CCD XML files.
        results_dir: Directory for results and checkpoints.
        audit_dir: Directory for audit trail files.
        
    Example:
        >>> paths = OutputPaths.from_base(Path("output/batch-001"))
        >>> print(paths.logs_dir)
        output/batch-001/logs
    """
    base_dir: Path
    logs_dir: Path = field(init=False)
    documents_dir: Path = field(init=False)
    ccds_dir: Path = field(init=False)
    results_dir: Path = field(init=False)
    audit_dir: Path = field(init=False)
    
    def __post_init__(self) -> None:
        """Initialize derived paths from base directory."""
        self.logs_dir = self.base_dir / "logs"
        self.documents_dir = self.base_dir / "documents"
        self.ccds_dir = self.documents_dir / "ccds"
        self.results_dir = self.base_dir / "results"
        self.audit_dir = self.base_dir / "audit"
    
    @classmethod
    def from_base(cls, base_dir: Path) -> "OutputPaths":
        """Create OutputPaths from a base directory.
        
        Args:
            base_dir: Base output directory path.
            
        Returns:
            OutputPaths instance with all subdirectory paths.
            
        Example:
            >>> paths = OutputPaths.from_base(Path("output/batch-001"))
        """
        return cls(base_dir=base_dir)
    
    def all_dirs(self) -> list[Path]:
        """Get list of all output directories.
        
        Returns:
            List of all directory paths.
        """
        return [
            self.logs_dir,
            self.documents_dir,
            self.ccds_dir,
            self.results_dir,
            self.audit_dir,
        ]


class OutputManager:
    """Manages output directory structure for batch processing.
    
    Creates and manages organized output directories for batch processing
    results, including logs, documents, results, and audit trails.
    
    Attributes:
        paths: OutputPaths instance with directory paths.
        
    Example:
        >>> manager = OutputManager(Path("output/batch-001"))
        >>> manager.setup_directories()
        >>> manager.write_result_file(result, "batch-results.json")
    """
    
    def __init__(self, base_dir: Path) -> None:
        """Initialize output manager with base directory.
        
        Args:
            base_dir: Base output directory path.
        """
        self.paths = OutputPaths.from_base(base_dir)
        logger.debug("OutputManager initialized with base_dir=%s", base_dir)
    
    def setup_directories(self) -> OutputPaths:
        """Create all output directories.
        
        Creates the complete directory structure if it doesn't exist.
        Safe to call multiple times - uses exist_ok=True.
        
        Returns:
            OutputPaths instance with all directory paths.
            
        Raises:
            OSError: If directory creation fails.
            PermissionError: If insufficient permissions.
            
        Example:
            >>> manager = OutputManager(Path("output/batch-001"))
            >>> paths = manager.setup_directories()
            >>> paths.logs_dir.exists()
            True
        """
        for dir_path in self.paths.all_dirs():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.debug("Created directory: %s", dir_path)
            except (OSError, PermissionError) as e:
                logger.error("Failed to create directory %s: %s", dir_path, e)
                raise OSError(
                    f"Failed to create output directory: {dir_path}. "
                    f"Ensure write permissions are available. Error: {e}"
                ) from e
        
        logger.info("Output directories created at: %s", self.paths.base_dir)
        return self.paths
    
    def write_result_file(
        self,
        data: Dict[str, Any],
        filename: str,
        pretty: bool = True,
    ) -> Path:
        """Write a result file to the results directory.
        
        Args:
            data: Dictionary data to write as JSON.
            filename: Name of the output file.
            pretty: Whether to pretty-print JSON (default: True).
            
        Returns:
            Path to the written file.
            
        Raises:
            OSError: If file write fails.
            
        Example:
            >>> manager = OutputManager(Path("output"))
            >>> manager.setup_directories()
            >>> path = manager.write_result_file(
            ...     {"status": "success", "count": 100},
            ...     "batch-results.json"
            ... )
        """
        file_path = self.paths.results_dir / filename
        try:
            indent = 2 if pretty else None
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, default=str)
            logger.debug("Wrote result file: %s", file_path)
            return file_path
        except (OSError, PermissionError) as e:
            logger.error("Failed to write result file %s: %s", file_path, e)
            raise OSError(
                f"Failed to write result file: {file_path}. Error: {e}"
            ) from e
    
    def write_checkpoint_file(
        self,
        data: Dict[str, Any],
        batch_id: str,
    ) -> Path:
        """Write a checkpoint file for batch resume capability.
        
        Args:
            data: Checkpoint data to write as JSON.
            batch_id: Batch identifier for filename.
            
        Returns:
            Path to the checkpoint file.
            
        Example:
            >>> manager = OutputManager(Path("output"))
            >>> manager.setup_directories()
            >>> path = manager.write_checkpoint_file(
            ...     {"last_index": 50, "completed": ["P001", "P002"]},
            ...     "batch-001"
            ... )
        """
        filename = f"checkpoint-{batch_id}.json"
        return self.write_result_file(data, filename, pretty=True)
    
    def write_summary_file(
        self,
        content: str,
        batch_id: str,
    ) -> Path:
        """Write a human-readable summary file.
        
        Args:
            content: Text content for the summary.
            batch_id: Batch identifier for filename.
            
        Returns:
            Path to the summary file.
            
        Example:
            >>> manager = OutputManager(Path("output"))
            >>> manager.setup_directories()
            >>> path = manager.write_summary_file(
            ...     "Batch completed: 100 patients processed",
            ...     "batch-001"
            ... )
        """
        filename = f"batch-{batch_id}-summary.txt"
        file_path = self.paths.results_dir / filename
        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(content)
            logger.debug("Wrote summary file: %s", file_path)
            return file_path
        except (OSError, PermissionError) as e:
            logger.error("Failed to write summary file %s: %s", file_path, e)
            raise OSError(
                f"Failed to write summary file: {file_path}. Error: {e}"
            ) from e
    
    def write_audit_log(
        self,
        entry: Dict[str, Any],
        batch_id: str,
    ) -> Path:
        """Append an entry to the audit log file.
        
        Creates the audit file if it doesn't exist. Each entry is
        written as a JSON line (JSONL format).
        
        Args:
            entry: Audit entry dictionary.
            batch_id: Batch identifier for filename.
            
        Returns:
            Path to the audit log file.
            
        Example:
            >>> manager = OutputManager(Path("output"))
            >>> manager.setup_directories()
            >>> path = manager.write_audit_log(
            ...     {"action": "patient_processed", "patient_id": "P001"},
            ...     "batch-001"
            ... )
        """
        filename = f"audit-{batch_id}.log"
        file_path = self.paths.audit_dir / filename
        
        # Add timestamp if not present
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now().isoformat()
        
        try:
            with file_path.open("a", encoding="utf-8") as f:
                json.dump(entry, f, default=str)
                f.write("\n")
            logger.debug("Appended audit entry to: %s", file_path)
            return file_path
        except (OSError, PermissionError) as e:
            logger.error("Failed to write audit log %s: %s", file_path, e)
            raise OSError(
                f"Failed to write audit log: {file_path}. Error: {e}"
            ) from e
    
    def write_ccd_document(
        self,
        content: str,
        patient_id: str,
    ) -> Path:
        """Write a CCD document for a patient.
        
        Args:
            content: CCD XML content.
            patient_id: Patient identifier for filename.
            
        Returns:
            Path to the CCD file.
            
        Example:
            >>> manager = OutputManager(Path("output"))
            >>> manager.setup_directories()
            >>> path = manager.write_ccd_document(
            ...     "<ClinicalDocument>...</ClinicalDocument>",
            ...     "P001"
            ... )
        """
        filename = f"patient-{patient_id}-ccd.xml"
        file_path = self.paths.ccds_dir / filename
        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(content)
            logger.debug("Wrote CCD document: %s", file_path)
            return file_path
        except (OSError, PermissionError) as e:
            logger.error("Failed to write CCD document %s: %s", file_path, e)
            raise OSError(
                f"Failed to write CCD document: {file_path}. Error: {e}"
            ) from e
    
    def write_batch_log(
        self,
        content: str,
        batch_id: str,
        log_type: str = "batch",
    ) -> Path:
        """Write a batch processing log file.
        
        Args:
            content: Log content.
            batch_id: Batch identifier for filename.
            log_type: Type of log (batch, pix-add, iti41).
            
        Returns:
            Path to the log file.
            
        Example:
            >>> manager = OutputManager(Path("output"))
            >>> manager.setup_directories()
            >>> path = manager.write_batch_log(
            ...     "Processing started at 2024-01-15 10:00:00",
            ...     "batch-001",
            ...     "batch"
            ... )
        """
        filename = f"{log_type}-{batch_id}.log"
        file_path = self.paths.logs_dir / filename
        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(content)
            logger.debug("Wrote batch log: %s", file_path)
            return file_path
        except (OSError, PermissionError) as e:
            logger.error("Failed to write batch log %s: %s", file_path, e)
            raise OSError(
                f"Failed to write batch log: {file_path}. Error: {e}"
            ) from e
    
    def get_checkpoint_path(self, batch_id: str) -> Path:
        """Get the path for a checkpoint file.
        
        Args:
            batch_id: Batch identifier.
            
        Returns:
            Path where checkpoint file would be stored.
            
        Example:
            >>> manager = OutputManager(Path("output"))
            >>> path = manager.get_checkpoint_path("batch-001")
            >>> print(path)
            output/results/checkpoint-batch-001.json
        """
        return self.paths.results_dir / f"checkpoint-{batch_id}.json"
    
    def load_checkpoint(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint data if it exists.
        
        Args:
            batch_id: Batch identifier.
            
        Returns:
            Checkpoint data dictionary or None if not found.
            
        Example:
            >>> manager = OutputManager(Path("output"))
            >>> checkpoint = manager.load_checkpoint("batch-001")
            >>> if checkpoint:
            ...     print(f"Resuming from index {checkpoint['last_index']}")
        """
        checkpoint_path = self.get_checkpoint_path(batch_id)
        if not checkpoint_path.exists():
            logger.debug("No checkpoint found at: %s", checkpoint_path)
            return None
        
        try:
            with checkpoint_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded checkpoint from: %s", checkpoint_path)
            return data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load checkpoint %s: %s", checkpoint_path, e)
            return None


def setup_output_directories(base_dir: Path) -> OutputPaths:
    """Convenience function to set up output directories.
    
    Creates an OutputManager and sets up all directories.
    
    Args:
        base_dir: Base output directory path.
        
    Returns:
        OutputPaths instance with all directory paths.
        
    Example:
        >>> paths = setup_output_directories(Path("output/batch-001"))
        >>> print(paths.logs_dir)
        output/batch-001/logs
    """
    manager = OutputManager(base_dir)
    return manager.setup_directories()
