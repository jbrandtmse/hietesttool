"""PIX Add workflow orchestration module.

This module provides end-to-end workflow orchestration for PIX Add transactions,
integrating CSV parsing, HL7v3 message building, SAML generation, SOAP submission,
and acknowledgment parsing.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from lxml import etree
from requests import ConnectionError, Timeout
from requests.exceptions import SSLError

from ihe_test_util.config.schema import Config
from ihe_test_util.csv_parser.parser import parse_csv
from ihe_test_util.ihe_transactions.pix_add import build_pix_add_message
from ihe_test_util.ihe_transactions.soap_client import PIXAddSOAPClient
from ihe_test_util.models.batch import BatchProcessingResult, PatientResult
from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.models.responses import TransactionStatus
from ihe_test_util.models.saml import SAMLAssertion
from ihe_test_util.saml.generator import generate_saml_assertion
from ihe_test_util.saml.signer import SAMLSigner
from ihe_test_util.utils.exceptions import (
    ValidationError,
    ErrorCategory,
    categorize_error,
    create_error_info,
)
from ihe_test_util.ihe_transactions.error_summary import (
    ErrorSummaryCollector,
    generate_error_report,
)

logger = logging.getLogger(__name__)


class PIXAddWorkflow:
    """Orchestrator for complete PIX Add workflow.
    
    Manages end-to-end workflow from CSV parsing through patient registration,
    including SAML generation, HL7v3 message construction, SOAP submission,
    and acknowledgment parsing.
    
    Attributes:
        config: Application configuration
        soap_client: Configured SOAP client for PIX Add transactions
        
    Example:
        >>> from ihe_test_util.config.manager import ConfigManager
        >>> config = ConfigManager().load_config()
        >>> workflow = PIXAddWorkflow(config)
        >>> result = workflow.process_batch(Path("patients.csv"))
        >>> print(f"Success: {result.successful_patients}/{result.total_patients}")
    """
    
    def __init__(self, config: Config) -> None:
        """Initialize PIX Add workflow orchestrator.
        
        Args:
            config: Application configuration with endpoints, certificates, OIDs
            
        Raises:
            ValidationError: If configuration is invalid or missing required fields
        """
        logger.info("Initializing PIX Add workflow orchestrator")
        self.config = config
        
        # Create SOAP client
        self.soap_client = PIXAddSOAPClient(config)
        
        logger.info("PIX Add workflow orchestrator initialized successfully")
    
    def process_patient(
        self,
        patient: PatientDemographics,
        saml_assertion: SAMLAssertion,
        error_collector: Optional[ErrorSummaryCollector] = None
    ) -> PatientResult:
        """Process single patient through complete PIX Add workflow.
        
        Orchestrates: HL7v3 message building → SOAP submission → acknowledgment parsing.
        Handles both critical errors (halt workflow) and non-critical errors (continue).
        
        Args:
            patient: Patient demographics from CSV
            saml_assertion: Pre-generated and signed SAML assertion
            
        Returns:
            PatientResult with registration outcome
            
        Raises:
            ConnectionError: If endpoint unreachable (CRITICAL)
            Timeout: If request times out (CRITICAL)
            SSLError: If certificate validation fails (CRITICAL)
            
        Example:
            >>> result = workflow.process_patient(patient, saml)
            >>> if result.is_success:
            ...     print(f"Registered: {result.enterprise_id}")
        """
        start_time = time.time()
        patient_id = patient.patient_id
        
        logger.info(f"Processing patient: {patient_id}")
        
        try:
            # Step 1: Build HL7v3 PIX Add message
            logger.debug(f"Building HL7v3 message for patient {patient_id}")
            message_xml = build_pix_add_message(
                demographics=patient,
                sending_application=self.config.sender_application,
                sending_facility=self.config.sender_oid,
                receiver_application=self.config.receiver_application,
                receiver_facility=self.config.receiver_oid
            )
            logger.info(f"HL7v3 message built for patient {patient_id}")
            
            # Step 2: Submit via SOAP client
            logger.debug(f"Submitting PIX Add for patient {patient_id}")
            response = self.soap_client.submit_pix_add(message_xml, saml_assertion)
            logger.info(f"PIX Add submitted for patient {patient_id}, status: {response.status}")
            
            # Step 3: Extract patient identifiers and create result
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            if response.is_success:
                # Extract enterprise ID from response
                enterprise_id = response.extracted_identifiers.get("patient_id")
                enterprise_id_oid = response.extracted_identifiers.get("patient_id_root")
                
                result = PatientResult(
                    patient_id=patient_id,
                    pix_add_status=TransactionStatus.SUCCESS,
                    pix_add_message="Patient registered successfully",
                    processing_time_ms=processing_time_ms,
                    enterprise_id=enterprise_id,
                    enterprise_id_oid=enterprise_id_oid,
                    registration_timestamp=datetime.now(timezone.utc)
                )
                
                logger.info(
                    f"Patient {patient_id} registered successfully "
                    f"(Enterprise ID: {enterprise_id}, Time: {processing_time_ms}ms)"
                )
            else:
                # Registration failed with AE/AR status
                error_msg = "; ".join(response.error_messages) if response.error_messages else "Unknown error"
                
                result = PatientResult(
                    patient_id=patient_id,
                    pix_add_status=TransactionStatus.ERROR,
                    pix_add_message=f"PIX Add rejected: {error_msg}",
                    processing_time_ms=processing_time_ms,
                    error_details=f"Status: {response.status_code}, Details: {error_msg}"
                )
                
                logger.warning(
                    f"Patient {patient_id} registration failed: {error_msg} "
                    f"(Status: {response.status_code})"
                )
            
            return result
            
        except (ConnectionError, Timeout, SSLError) as critical_error:
            # CRITICAL errors - halt workflow
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create error info with remediation
            error_info = create_error_info(critical_error, patient_id=patient_id)
            
            logger.error(
                f"CRITICAL ERROR processing patient {patient_id}: {critical_error}. "
                f"Remediation: {error_info.remediation}"
            )
            
            # Track error in collector
            if error_collector:
                error_collector.add_error(error_info, patient_id)
            
            # Re-raise to halt workflow
            raise
            
        except ValidationError as non_critical_error:
            # NON-CRITICAL errors - continue workflow
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create error info with remediation
            error_info = create_error_info(non_critical_error, patient_id=patient_id)
            
            logger.warning(
                f"Patient {patient_id} validation failed: {non_critical_error}. "
                f"Remediation: {error_info.remediation}"
            )
            
            # Track error in collector
            if error_collector:
                error_collector.add_error(error_info, patient_id)
            
            result = PatientResult(
                patient_id=patient_id,
                pix_add_status=TransactionStatus.ERROR,
                pix_add_message=str(non_critical_error),
                processing_time_ms=processing_time_ms,
                error_details=f"Validation error: {non_critical_error}. {error_info.remediation}"
            )
            
            return result
            
        except Exception as unexpected_error:
            # Unexpected errors - treat as non-critical, continue workflow
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create error info with remediation
            error_info = create_error_info(unexpected_error, patient_id=patient_id)
            
            logger.error(
                f"Unexpected error processing patient {patient_id}: {unexpected_error}. "
                f"Remediation: {error_info.remediation}",
                exc_info=True
            )
            
            # Track error in collector
            if error_collector:
                error_collector.add_error(error_info, patient_id)
            
            result = PatientResult(
                patient_id=patient_id,
                pix_add_status=TransactionStatus.ERROR,
                pix_add_message=f"Unexpected error: {unexpected_error}",
                processing_time_ms=processing_time_ms,
                error_details=f"Error: {unexpected_error}. {error_info.remediation}"
            )
            
            return result
    
    def process_batch(self, csv_path: Path) -> BatchProcessingResult:
        """Process all patients from CSV file through PIX Add workflow.
        
        Processes patients sequentially (not parallel) with comprehensive error
        handling. Critical errors halt processing; non-critical errors continue.
        
        Args:
            csv_path: Path to CSV file with patient demographics
            
        Returns:
            BatchProcessingResult with aggregate statistics and per-patient results
            
        Raises:
            ConnectionError: If endpoint unreachable (CRITICAL)
            Timeout: If requests time out repeatedly (CRITICAL)
            SSLError: If certificate validation fails (CRITICAL)
            ValidationError: If CSV file is invalid
            
        Example:
            >>> result = workflow.process_batch(Path("patients.csv"))
            >>> print(f"Processed: {result.total_patients}")
            >>> print(f"Success: {result.successful_patients}")
            >>> print(f"Failed: {result.failed_patients}")
        """
        # Generate batch ID
        batch_id = str(uuid.uuid4())
        start_timestamp = datetime.now(timezone.utc)
        
        logger.info(
            f"Starting PIX Add batch workflow: batch_id={batch_id}, "
            f"csv_file={csv_path}"
        )
        
        try:
            # Step 1: Parse CSV
            logger.info("Parsing CSV file")
            df, validation_result = parse_csv(csv_path, validate=True)
            total_patients = len(df)
            
            logger.info(f"CSV parsed successfully: {total_patients} patients")
            
            # Step 2: Validate configuration before starting
            self._validate_configuration()
            
            # Step 3: Generate SAML assertion (reuse for all patients)
            logger.info("Generating SAML assertion")
            saml_assertion = self._generate_saml_assertion()
            logger.info("SAML assertion generated and signed")
            
            # Step 4: Initialize batch result and error collector
            batch_result = BatchProcessingResult(
                batch_id=batch_id,
                csv_file_path=str(csv_path),
                start_timestamp=start_timestamp,
                total_patients=total_patients
            )
            
            error_collector = ErrorSummaryCollector()
            error_collector.set_patient_count(total_patients)
            
            # Step 5: Process patients sequentially
            logger.info(f"Processing {total_patients} patients sequentially")
            
            for idx, row in df.iterrows():
                patient_num = idx + 1
                logger.info(f"Processing patient {patient_num}/{total_patients}")
                
                try:
                    # Convert DataFrame row to PatientDemographics
                    patient = self._row_to_patient_demographics(row)
                    
                    # Process patient through workflow with error tracking
                    patient_result = self.process_patient(patient, saml_assertion, error_collector)
                    
                    # Aggregate results
                    batch_result.patient_results.append(patient_result)
                    
                    if patient_result.is_success:
                        batch_result.successful_patients += 1
                        batch_result.pix_add_success_count += 1
                    else:
                        batch_result.failed_patients += 1
                        
                        # Track error types
                        error_type = patient_result.pix_add_message.split(":")[0]
                        batch_result.error_summary[error_type] = \
                            batch_result.error_summary.get(error_type, 0) + 1
                    
                except (ConnectionError, Timeout, SSLError) as critical_error:
                    # CRITICAL error - halt workflow, return partial results
                    logger.error(
                        f"CRITICAL ERROR on patient {patient_num}: {critical_error}. "
                        "Halting batch processing."
                    )
                    
                    batch_result.end_timestamp = datetime.now(timezone.utc)
                    
                    logger.warning(
                        f"Batch processing halted early: {patient_num-1}/{total_patients} "
                        f"patients processed before critical error"
                    )
                    
                    # Re-raise critical error
                    raise
            
            # Step 6: Complete batch processing and generate error summary
            batch_result.end_timestamp = datetime.now(timezone.utc)
            
            logger.info(
                f"Batch processing complete: batch_id={batch_id}, "
                f"total={total_patients}, success={batch_result.successful_patients}, "
                f"failed={batch_result.failed_patients}, "
                f"duration={batch_result.duration_seconds:.2f}s"
            )
            
            # Generate error summary report if there were errors
            if batch_result.failed_patients > 0:
                error_summary = error_collector.get_summary()
                error_report = generate_error_report(error_summary)
                
                logger.info("Error Summary Report:\n" + error_report)
                
                # Store error summary in batch result for downstream use
                batch_result.error_summary["_error_report"] = error_report
                batch_result.error_summary["_error_statistics"] = {
                    "total_errors": error_summary.total_errors,
                    "by_category": error_summary.errors_by_category,
                    "by_type": error_summary.errors_by_type,
                    "error_rate": error_summary.error_rate
                }
            
            return batch_result
            
        except ValidationError as e:
            logger.error(f"CSV validation failed: {e}")
            raise
        
        except (ConnectionError, Timeout, SSLError) as critical_error:
            # Critical error already logged above, just re-raise
            raise
        
        except Exception as e:
            logger.error(f"Unexpected error in batch processing: {e}", exc_info=True)
            raise
    
    def _validate_configuration(self) -> None:
        """Validate configuration before starting workflow.
        
        Raises:
            ValidationError: If required configuration is missing or invalid
        """
        logger.debug("Validating configuration")
        
        # Check required endpoints
        if not self.config.endpoints.pix_add_url:
            raise ValidationError(
                "Missing required configuration: endpoints.pix_add_url. "
                "Add PIX Add endpoint URL to config.json."
            )
        
        # Check required certificates
        if not self.config.certificates.cert_path:
            raise ValidationError(
                "Missing required configuration: certificates.cert_path. "
                "Add certificate path to config.json or generate with: scripts/generate_cert.sh"
            )
        
        if not Path(self.config.certificates.cert_path).exists():
            raise ValidationError(
                f"Certificate file not found: {self.config.certificates.cert_path}. "
                "Generate certificate with: scripts/generate_cert.sh"
            )
        
        if not self.config.certificates.key_path:
            raise ValidationError(
                "Missing required configuration: certificates.key_path. "
                "Add private key path to config.json."
            )
        
        if not Path(self.config.certificates.key_path).exists():
            raise ValidationError(
                f"Private key file not found: {self.config.certificates.key_path}. "
                "Ensure private key exists alongside certificate."
            )
        
        # Check required OIDs
        if not self.config.sender_oid:
            raise ValidationError(
                "Missing required configuration: sender_oid. "
                "Add sender OID to config.json."
            )
        
        if not self.config.receiver_oid:
            raise ValidationError(
                "Missing required configuration: receiver_oid. "
                "Add receiver OID to config.json."
            )
        
        logger.debug("Configuration validation passed")
    
    def _generate_saml_assertion(self) -> SAMLAssertion:
        """Generate and sign SAML assertion for workflow.
        
        Returns:
            Signed SAML assertion ready for use
            
        Raises:
            ValidationError: If certificate is invalid or expired
        """
        logger.debug("Generating SAML assertion")
        
        # Generate SAML assertion element
        # Note: issuer and subject should be configured elsewhere or use defaults
        assertion_element = generate_saml_assertion(
            issuer="urn:test:issuer",  # TODO: Add to config
            subject="urn:test:subject"  # TODO: Add to config
        )
        
        # Convert element to SAMLAssertion object
        assertion_id = assertion_element.get("ID", "")
        assertion_xml = etree.tostring(assertion_element, encoding='unicode')
        
        now = datetime.now(timezone.utc)
        
        from ihe_test_util.models.saml import SAMLGenerationMethod
        
        unsigned_assertion = SAMLAssertion(
            assertion_id=assertion_id,
            xml_content=assertion_xml,
            issuer="urn:test:issuer",
            subject="urn:test:subject",
            audience="urn:test:audience",
            issue_instant=now,
            not_before=now,
            not_on_or_after=now + timedelta(hours=1),
            signature="",
            certificate_subject="",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC
        )
        
        # Load certificate bundle
        from ihe_test_util.saml.certificate_manager import load_certificate
        cert_bundle = load_certificate(
            cert_source=Path(self.config.certificates.cert_path),
            key_path=Path(self.config.certificates.key_path)
        )
        
        # Sign assertion
        signer = SAMLSigner(cert_bundle)
        signed_assertion = signer.sign_assertion(unsigned_assertion)
        
        logger.debug("SAML assertion signed successfully")
        
        return signed_assertion
    
    def _row_to_patient_demographics(self, row: pd.Series) -> PatientDemographics:
        """Convert DataFrame row to PatientDemographics object.
        
        Args:
            row: DataFrame row with patient data
            
        Returns:
            PatientDemographics object
        """
        # Convert date of birth to date object if string
        dob = row["dob"]
        if isinstance(dob, str):
            dob = pd.to_datetime(dob).date()
        
        return PatientDemographics(
            patient_id=row["patient_id"],
            patient_id_oid=row["patient_id_oid"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            dob=dob,
            gender=row["gender"],
            mrn=row.get("mrn"),
            ssn=row.get("ssn"),
            address=row.get("address"),
            city=row.get("city"),
            state=row.get("state"),
            zip=row.get("zip"),
            phone=row.get("phone"),
            email=row.get("email")
        )


def save_registered_identifiers(
    results: BatchProcessingResult,
    output_path: Path
) -> None:
    """Save registered patient identifiers to JSON file.
    
    Creates JSON file with all successfully registered patients and their
    assigned enterprise IDs for downstream use.
    
    Args:
        results: Batch processing results
        output_path: Path to output JSON file
        
    Example:
        >>> save_registered_identifiers(results, Path("output/registered.json"))
    """
    logger.info(f"Saving registered patient identifiers to {output_path}")
    
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Filter successful registrations
    successful_patients = [
        r for r in results.patient_results if r.is_success
    ]
    
    # Build output structure
    output_data = {
        "batch_id": results.batch_id,
        "timestamp": results.end_timestamp.isoformat() if results.end_timestamp else datetime.now(timezone.utc).isoformat(),
        "total_registered": len(successful_patients),
        "patients": [
            {
                "patient_id": p.patient_id,
                "enterprise_id": p.enterprise_id,
                "enterprise_id_oid": p.enterprise_id_oid,
                "registration_timestamp": p.registration_timestamp.isoformat() if p.registration_timestamp else None
            }
            for p in successful_patients
        ]
    }
    
    # Write to file
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Saved {len(successful_patients)} registered patient identifiers")


def generate_summary_report(results: BatchProcessingResult) -> str:
    """Generate human-readable summary report of batch processing.
    
    Creates formatted terminal output with statistics, successful registrations,
    failed registrations with error details, and output file locations.
    
    Args:
        results: Batch processing results
        
    Returns:
        Formatted summary report string
        
    Example:
        >>> report = generate_summary_report(results)
        >>> print(report)
    """
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("PIX ADD WORKFLOW SUMMARY")
    lines.append("=" * 80)
    lines.append("")
    
    # Batch information
    lines.append(f"Batch ID: {results.batch_id}")
    lines.append(f"CSV File: {results.csv_file_path}")
    lines.append(f"Started:  {results.start_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if results.end_timestamp:
        lines.append(f"Finished: {results.end_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        duration_min = int(results.duration_seconds // 60)
        duration_sec = int(results.duration_seconds % 60)
        lines.append(f"Duration: {duration_min}m {duration_sec}s")
    lines.append("")
    
    # Results summary
    lines.append("-" * 80)
    lines.append("RESULTS")
    lines.append("-" * 80)
    lines.append(f"Total Patients:       {results.total_patients}")
    lines.append(f"✓ Successful:         {results.successful_patients} ({results.success_rate:.1f}%)")
    lines.append(f"✗ Failed:             {results.failed_patients} ({100-results.success_rate:.1f}%)")
    lines.append("")
    
    if results.average_processing_time_ms:
        lines.append(f"Average Processing Time: {results.average_processing_time_ms:.1f} ms per patient")
        lines.append("")
    
    # Successful registrations
    if results.successful_patients > 0:
        lines.append("-" * 80)
        lines.append("SUCCESSFUL REGISTRATIONS")
        lines.append("-" * 80)
        
        successful = [r for r in results.patient_results if r.is_success]
        for result in successful:
            lines.append(f"✓ {result.patient_id} - Registered (Enterprise ID: {result.enterprise_id})")
        lines.append("")
    
    # Failed registrations
    if results.failed_patients > 0:
        lines.append("-" * 80)
        lines.append("FAILED REGISTRATIONS")
        lines.append("-" * 80)
        
        failed = [r for r in results.patient_results if not r.is_success]
        for result in failed:
            lines.append(f"✗ {result.patient_id} - {result.pix_add_message}")
            if result.error_details:
                # Indent error details
                detail_lines = result.error_details.split(". ")
                for detail_line in detail_lines:
                    if detail_line.strip():
                        lines.append(f"  {detail_line.strip()}")
            lines.append("")
    
    # Output files
    lines.append("-" * 80)
    lines.append("OUTPUT FILES")
    lines.append("-" * 80)
    
    # Registered identifiers file
    output_file = f"output/registered-patients-{results.batch_id[:8]}.json"
    lines.append(f"Registered Identifiers: {output_file}")
    
    # Audit log file
    audit_log = f"logs/transactions/pix-add-workflow-{results.start_timestamp.strftime('%Y%m%d')}.log"
    lines.append(f"Full Audit Log:         {audit_log}")
    lines.append("")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)
