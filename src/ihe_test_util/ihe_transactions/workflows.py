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
    get_remediation_message,
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


# =============================================================================
# Integrated Workflow (Story 6.5)
# =============================================================================

from ihe_test_util.ihe_transactions.iti41_client import ITI41SOAPClient
from ihe_test_util.ihe_transactions.xdsb_metadata import XDSbMetadataBuilder
from ihe_test_util.models.batch import BatchWorkflowResult, PatientWorkflowResult
from ihe_test_util.models.ccd import CCDDocument
from ihe_test_util.models.transactions import ITI41Transaction
from ihe_test_util.template_engine.personalizer import TemplatePersonalizer, MissingValueStrategy
from ihe_test_util.utils.exceptions import (
    ITI41TransportError,
    ITI41TimeoutError,
    ITI41SOAPError,
)


class IntegratedWorkflow:
    """Orchestrates complete CSV → CCD → PIX Add → ITI-41 workflow.
    
    This workflow implements the primary use case: processing a CSV file
    of patient demographics, generating personalized CCDs, registering
    patients via PIX Add, and submitting documents via ITI-41.
    
    The workflow follows this sequence for each patient:
    1. Parse patient demographics from CSV
    2. Generate personalized CCD from template
    3. Execute PIX Add transaction to register patient
    4. If PIX Add succeeds, extract patient identifiers
    5. Build ITI-41 transaction with patient IDs from PIX Add
    6. Execute ITI-41 document submission
    7. Track per-patient status at each step
    
    Attributes:
        config: Application configuration with endpoints and OIDs
        ccd_template_path: Path to CCD XML template
        pix_add_workflow: PIX Add workflow instance for patient registration
        iti41_client: ITI-41 SOAP client for document submission
        
    Example:
        >>> from ihe_test_util.config.manager import ConfigManager
        >>> config = ConfigManager().load_config()
        >>> workflow = IntegratedWorkflow(config, Path("templates/ccd.xml"))
        >>> results = workflow.process_batch(Path("patients.csv"))
        >>> print(f"Success rate: {results.get_overall_success_rate():.1f}%")
    """
    
    def __init__(self, config: Config, ccd_template_path: Path) -> None:
        """Initialize integrated workflow orchestrator.
        
        Args:
            config: Application configuration with PIX Add and ITI-41 endpoints,
                   certificates, and OID configuration
            ccd_template_path: Path to CCD XML template for personalization
            
        Raises:
            ValidationError: If configuration is invalid or missing required fields
            FileNotFoundError: If CCD template file does not exist
        """
        logger.info("Initializing integrated workflow orchestrator")
        
        self._config = config
        self._ccd_template_path = ccd_template_path
        
        # Validate CCD template exists
        if not ccd_template_path.exists():
            raise ValidationError(
                f"CCD template file not found: {ccd_template_path}. "
                "Provide valid path to CCD template XML file."
            )
        
        # Load CCD template content
        self._ccd_template_content = ccd_template_path.read_text(encoding="utf-8")
        logger.debug(f"Loaded CCD template: {len(self._ccd_template_content)} bytes")
        
        # Initialize PIX Add workflow (reuse existing implementation from Story 5.4)
        self._pix_add_workflow = PIXAddWorkflow(config)
        
        # Initialize ITI-41 client (from Story 6.3)
        self._iti41_client = ITI41SOAPClient(
            endpoint_url=config.endpoints.iti41_url,
            timeout=config.endpoints.timeout,
            verify_tls=config.endpoints.verify_tls,
            ca_bundle_path=config.certificates.ca_bundle_path if hasattr(config.certificates, 'ca_bundle_path') else None,
        )
        
        # Initialize template personalizer (from Story 3.x)
        self._personalizer = TemplatePersonalizer(
            date_format="HL7",
            missing_value_strategy=MissingValueStrategy.ERROR,
        )
        
        # Initialize XDSb metadata builder (from Story 6.1)
        # Note: XDSbMetadataBuilder uses fluent API - patient/document set per transaction
        self._metadata_builder = XDSbMetadataBuilder()
        
        logger.info("Integrated workflow orchestrator initialized successfully")
    
    @property
    def config(self) -> Config:
        """Get workflow configuration."""
        return self._config
    
    @property
    def ccd_template_path(self) -> Path:
        """Get CCD template path."""
        return self._ccd_template_path
    
    def process_batch(self, csv_path: Path) -> BatchWorkflowResult:
        """Process all patients from CSV file through complete workflow.
        
        Orchestrates: CSV → CCD generation → PIX Add → ITI-41 submission
        for all patients in the CSV file. Processes patients sequentially
        to maintain registration order.
        
        Args:
            csv_path: Path to CSV file with patient demographics
            
        Returns:
            BatchWorkflowResult with per-patient results and statistics
            
        Raises:
            ValidationError: If CSV file is invalid
            ConnectionError: If endpoint unreachable (CRITICAL - halts batch)
            Timeout: If requests time out repeatedly (CRITICAL - halts batch)
            SSLError: If certificate validation fails (CRITICAL - halts batch)
            
        Example:
            >>> results = workflow.process_batch(Path("patients.csv"))
            >>> print(f"Processed: {results.total_patients}")
            >>> print(f"PIX Add success: {results.get_pix_add_success_rate():.1f}%")
            >>> print(f"ITI-41 success: {results.get_iti41_success_rate():.1f}%")
        """
        # Generate batch ID
        batch_id = f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        start_timestamp = datetime.now(timezone.utc)
        
        logger.info(
            f"Starting integrated workflow batch: batch_id={batch_id}, "
            f"csv_file={csv_path}"
        )
        
        # Log workflow start for audit (AC: 9)
        self._log_workflow_step(
            patient_id="BATCH",
            step="BATCH_START",
            status="STARTED",
            duration_ms=0,
            details=f"Processing CSV: {csv_path}"
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
            logger.info("Generating SAML assertion for batch")
            saml_assertion = self._generate_saml_assertion()
            logger.info("SAML assertion generated and signed")
            
            # Step 4: Initialize batch result
            batch_result = BatchWorkflowResult(
                batch_id=batch_id,
                csv_file=str(csv_path),
                ccd_template=str(self._ccd_template_path),
                start_timestamp=start_timestamp
            )
            
            error_collector = ErrorSummaryCollector()
            error_collector.set_patient_count(total_patients)
            
            # Step 5: Process patients sequentially (AC: 4)
            logger.info(f"Processing {total_patients} patients sequentially")
            
            for idx, row in df.iterrows():
                patient_num = idx + 1
                logger.info(f"Processing patient {patient_num}/{total_patients}")
                
                try:
                    # Convert DataFrame row to PatientDemographics
                    patient = self._row_to_patient_demographics(row)
                    
                    # Process patient through complete workflow
                    patient_result = self.process_patient(
                        patient=patient,
                        saml_assertion=saml_assertion,
                        error_collector=error_collector
                    )
                    
                    # Aggregate results - counts are computed properties from patient_results
                    batch_result.patient_results.append(patient_result)
                    
                except (ConnectionError, Timeout, SSLError) as critical_error:
                    # CRITICAL error - halt workflow, return partial results
                    logger.error(
                        f"CRITICAL ERROR on patient {patient_num}: {critical_error}. "
                        "Halting batch processing."
                    )
                    
                    batch_result.end_timestamp = datetime.now(timezone.utc)
                    
                    # Log critical error for audit
                    self._log_workflow_step(
                        patient_id=patient.patient_id if 'patient' in dir() else f"patient_{patient_num}",
                        step="CRITICAL_ERROR",
                        status="HALTED",
                        duration_ms=0,
                        details=str(critical_error)
                    )
                    
                    logger.warning(
                        f"Batch processing halted early: {patient_num-1}/{total_patients} "
                        f"patients processed before critical error"
                    )
                    
                    # Re-raise critical error
                    raise
            
            # Step 6: Complete batch processing
            batch_result.end_timestamp = datetime.now(timezone.utc)
            
            # Log batch completion for audit (AC: 9)
            self._log_workflow_step(
                patient_id="BATCH",
                step="BATCH_COMPLETE",
                status="COMPLETED",
                duration_ms=int(batch_result.duration_seconds * 1000) if batch_result.duration_seconds else 0,
                details=f"PIX Add: {batch_result.pix_add_success_count}/{total_patients}, "
                       f"ITI-41: {batch_result.iti41_success_count}/{total_patients}"
            )
            
            logger.info(
                f"Integrated workflow complete: batch_id={batch_id}, "
                f"total={total_patients}, "
                f"pix_add_success={batch_result.pix_add_success_count}, "
                f"iti41_success={batch_result.iti41_success_count}, "
                f"complete_success={batch_result.fully_successful_count}, "
                f"duration={batch_result.duration_seconds:.2f}s"
            )
            
            return batch_result
            
        except ValidationError as e:
            logger.error(f"CSV validation failed: {e}")
            raise
        
        except (ConnectionError, Timeout, SSLError):
            # Critical error already logged above, just re-raise
            raise
        
        except Exception as e:
            logger.error(f"Unexpected error in batch processing: {e}", exc_info=True)
            raise
    
    def process_patient(
        self,
        patient: PatientDemographics,
        saml_assertion: SAMLAssertion,
        error_collector: Optional[ErrorSummaryCollector] = None
    ) -> PatientWorkflowResult:
        """Process single patient through complete workflow.
        
        Orchestrates: CCD generation → PIX Add → ITI-41 submission.
        Tracks status at each step and handles errors appropriately.
        
        Steps:
        1. Generate CCD from template
        2. Execute PIX Add transaction
        3. If PIX Add succeeds, extract patient identifiers
        4. Build ITI-41 transaction with patient IDs
        5. Execute ITI-41 submission
        
        Args:
            patient: Patient demographics from CSV
            saml_assertion: SAML assertion for authentication
            error_collector: Optional error collector for tracking
            
        Returns:
            PatientWorkflowResult with status at each step
            
        Note:
            If PIX Add fails, ITI-41 is skipped (AC: 6)
        """
        start_time = time.time()
        patient_id = patient.patient_id
        
        logger.info(f"Processing patient through integrated workflow: {patient_id}")
        
        # Initialize result with CSV parsed
        result = PatientWorkflowResult(
            patient_id=patient_id,
            csv_parsed=True
        )
        
        # Log workflow start for this patient (AC: 9)
        self._log_workflow_step(
            patient_id=patient_id,
            step="WORKFLOW_START",
            status="STARTED",
            duration_ms=0
        )
        
        try:
            # Step 1: Generate CCD from template
            ccd_start = time.time()
            logger.debug(f"Generating CCD for patient {patient_id}")
            
            ccd_document = self._generate_ccd(patient)
            result.ccd_generated = True
            
            ccd_time_ms = int((time.time() - ccd_start) * 1000)
            
            self._log_workflow_step(
                patient_id=patient_id,
                step="CCD_GENERATED",
                status="SUCCESS",
                duration_ms=ccd_time_ms
            )
            
            logger.info(f"CCD generated for patient {patient_id} ({ccd_time_ms}ms)")
            
        except Exception as ccd_error:
            # CCD generation failed - skip remaining steps
            ccd_time_ms = int((time.time() - ccd_start) * 1000)
            result.pix_add_status = "skipped"
            result.pix_add_message = "Skipped due to CCD generation failure"
            result.iti41_status = "skipped"
            result.iti41_message = "Skipped due to CCD generation failure"
            result.total_time_ms = int((time.time() - start_time) * 1000)
            result.error_message = f"CCD generation error: {ccd_error}"
            
            self._log_workflow_step(
                patient_id=patient_id,
                step="CCD_GENERATION",
                status="FAILED",
                duration_ms=ccd_time_ms,
                details=str(ccd_error)
            )
            
            logger.error(f"CCD generation failed for patient {patient_id}: {ccd_error}")
            
            if error_collector:
                error_info = create_error_info(ccd_error, patient_id=patient_id)
                error_collector.add_error(error_info, patient_id)
            
            return result
        
        # Step 2: Execute PIX Add transaction
        pix_add_start = time.time()
        logger.debug(f"Executing PIX Add for patient {patient_id}")
        
        try:
            pix_result = self._pix_add_workflow.process_patient(
                patient=patient,
                saml_assertion=saml_assertion,
                error_collector=error_collector
            )
            
            pix_add_time_ms = int((time.time() - pix_add_start) * 1000)
            result.pix_add_time_ms = pix_add_time_ms
            
            if pix_result.is_success:
                result.pix_add_status = "success"
                result.pix_add_message = "Patient registered successfully"
                
                # Extract patient identifiers from PIX Add response (AC: 3)
                identifiers = self._extract_patient_identifiers(pix_result)
                result.pix_enterprise_id = identifiers.get("patient_id")
                result.pix_enterprise_id_oid = identifiers.get("patient_id_oid")
                
                self._log_workflow_step(
                    patient_id=patient_id,
                    step="PIX_ADD",
                    status="SUCCESS",
                    duration_ms=pix_add_time_ms,
                    details=f"Enterprise ID: {result.pix_enterprise_id}"
                )
                
                logger.info(
                    f"PIX Add successful for patient {patient_id} "
                    f"(Enterprise ID: {result.pix_enterprise_id}, {pix_add_time_ms}ms)"
                )
            else:
                # PIX Add failed - skip ITI-41 (AC: 6)
                result.pix_add_status = "failed"
                result.pix_add_message = pix_result.pix_add_message
                result.iti41_status = "skipped"
                result.iti41_message = "Skipped due to PIX Add failure"
                result.total_time_ms = int((time.time() - start_time) * 1000)
                result.error_message = pix_result.error_details
                
                self._log_workflow_step(
                    patient_id=patient_id,
                    step="PIX_ADD",
                    status="FAILED",
                    duration_ms=pix_add_time_ms,
                    details=pix_result.pix_add_message
                )
                
                logger.warning(
                    f"PIX Add failed for patient {patient_id}: {pix_result.pix_add_message}. "
                    "Skipping ITI-41 submission."
                )
                
                return result
                
        except (ConnectionError, Timeout, SSLError) as critical_error:
            # Critical PIX Add errors - re-raise to halt batch
            pix_add_time_ms = int((time.time() - pix_add_start) * 1000)
            result.pix_add_time_ms = pix_add_time_ms
            result.pix_add_status = "failed"
            result.pix_add_message = f"Critical error: {critical_error}"
            result.total_time_ms = int((time.time() - start_time) * 1000)
            
            self._log_workflow_step(
                patient_id=patient_id,
                step="PIX_ADD",
                status="CRITICAL_ERROR",
                duration_ms=pix_add_time_ms,
                details=str(critical_error)
            )
            
            raise
        
        # Step 3: Build and execute ITI-41 transaction
        iti41_start = time.time()
        logger.debug(f"Executing ITI-41 for patient {patient_id}")
        
        try:
            # Build ITI-41 transaction using patient IDs from PIX Add (AC: 3)
            transaction = self._build_iti41_transaction(
                patient=patient,
                ccd_document=ccd_document,
                pix_add_patient_id=result.pix_enterprise_id,
                pix_add_patient_id_oid=result.pix_enterprise_id_oid or patient.patient_id_oid
            )
            
            # Submit ITI-41
            iti41_response = self._iti41_client.submit(transaction, saml_assertion)
            
            iti41_time_ms = int((time.time() - iti41_start) * 1000)
            result.iti41_time_ms = iti41_time_ms
            
            if iti41_response.is_success:
                result.iti41_status = "success"
                result.iti41_message = "Document submitted successfully"
                
                # Extract document ID from response
                document_ids = iti41_response.extracted_identifiers.get("document_ids", [])
                if document_ids:
                    result.document_id = document_ids[0]
                
                self._log_workflow_step(
                    patient_id=patient_id,
                    step="ITI41",
                    status="SUCCESS",
                    duration_ms=iti41_time_ms,
                    details=f"Document ID: {result.document_id}"
                )
                
                logger.info(
                    f"ITI-41 successful for patient {patient_id} "
                    f"(Document ID: {result.document_id}, {iti41_time_ms}ms)"
                )
            else:
                result.iti41_status = "failed"
                result.iti41_message = "; ".join(iti41_response.error_messages) if iti41_response.error_messages else "ITI-41 submission failed"
                result.error_message = f"ITI-41 status: {iti41_response.status_code}"
                
                self._log_workflow_step(
                    patient_id=patient_id,
                    step="ITI41",
                    status="FAILED",
                    duration_ms=iti41_time_ms,
                    details=result.iti41_message
                )
                
                logger.warning(
                    f"ITI-41 failed for patient {patient_id}: {result.iti41_message}"
                )
                
                if error_collector:
                    error_info = create_error_info(
                        Exception(result.iti41_message),
                        patient_id=patient_id
                    )
                    error_collector.add_error(error_info, patient_id)
                    
        except (ITI41TransportError, ITI41TimeoutError, ITI41SOAPError) as iti41_error:
            # ITI-41 errors - continue batch, don't halt
            iti41_time_ms = int((time.time() - iti41_start) * 1000)
            result.iti41_time_ms = iti41_time_ms
            result.iti41_status = "failed"
            result.iti41_message = str(iti41_error)
            result.error_message = f"ITI-41 error: {iti41_error}"
            
            self._log_workflow_step(
                patient_id=patient_id,
                step="ITI41",
                status="FAILED",
                duration_ms=iti41_time_ms,
                details=str(iti41_error)
            )
            
            logger.error(f"ITI-41 failed for patient {patient_id}: {iti41_error}")
            
            if error_collector:
                error_info = create_error_info(iti41_error, patient_id=patient_id)
                error_collector.add_error(error_info, patient_id)
                
        except Exception as unexpected_error:
            # Unexpected ITI-41 errors - continue batch
            iti41_time_ms = int((time.time() - iti41_start) * 1000)
            result.iti41_time_ms = iti41_time_ms
            result.iti41_status = "failed"
            result.iti41_message = f"Unexpected error: {unexpected_error}"
            result.error_message = f"Unexpected ITI-41 error: {unexpected_error}"
            
            self._log_workflow_step(
                patient_id=patient_id,
                step="ITI41",
                status="FAILED",
                duration_ms=iti41_time_ms,
                details=str(unexpected_error)
            )
            
            logger.error(
                f"Unexpected ITI-41 error for patient {patient_id}: {unexpected_error}",
                exc_info=True
            )
            
            if error_collector:
                error_info = create_error_info(unexpected_error, patient_id=patient_id)
                error_collector.add_error(error_info, patient_id)
        
        # Calculate total time
        result.total_time_ms = int((time.time() - start_time) * 1000)
        
        # Log workflow completion for this patient
        self._log_workflow_step(
            patient_id=patient_id,
            step="WORKFLOW_COMPLETE",
            status="SUCCESS" if result.is_fully_successful else "PARTIAL",
            duration_ms=result.total_time_ms
        )
        
        logger.info(
            f"Patient {patient_id} workflow complete: "
            f"PIX Add={result.pix_add_status}, "
            f"ITI-41={result.iti41_status}, "
            f"total_time={result.total_time_ms}ms"
        )
        
        return result
    
    def _generate_ccd(self, patient: PatientDemographics) -> CCDDocument:
        """Generate personalized CCD document for patient.
        
        Args:
            patient: Patient demographics
            
        Returns:
            CCDDocument with personalized XML content
        """
        # Build replacement values from patient demographics
        values = {
            "patient_id": patient.patient_id,
            "patient_id_oid": patient.patient_id_oid,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "dob": patient.dob,
            "gender": patient.gender,
            "mrn": patient.mrn or "",
            "ssn": patient.ssn or "",
            "address": patient.address or "",
            "city": patient.city or "",
            "state": patient.state or "",
            "zip": patient.zip or "",
            "phone": patient.phone or "",
            "email": patient.email or "",
            "document_id": str(uuid.uuid4()),
            "creation_timestamp": datetime.now(timezone.utc),
        }
        
        # Personalize template
        xml_content = self._personalizer.personalize(self._ccd_template_content, values)
        
        # Create CCDDocument
        return CCDDocument(
            document_id=values["document_id"],
            patient_id=patient.patient_id,
            template_path=str(self._ccd_template_path),
            xml_content=xml_content,
            creation_timestamp=datetime.now(timezone.utc)
        )
    
    def _extract_patient_identifiers(self, pix_result: PatientResult) -> dict:
        """Extract patient identifiers from PIX Add response.
        
        Args:
            pix_result: PIX Add workflow result
            
        Returns:
            Dictionary with patient_id and patient_id_oid
        """
        return {
            "patient_id": pix_result.enterprise_id,
            "patient_id_oid": pix_result.enterprise_id_oid,
        }
    
    def _build_iti41_transaction(
        self,
        patient: PatientDemographics,
        ccd_document: CCDDocument,
        pix_add_patient_id: Optional[str],
        pix_add_patient_id_oid: str
    ) -> ITI41Transaction:
        """Build ITI-41 transaction with patient IDs from PIX Add.
        
        Args:
            patient: Patient demographics
            ccd_document: Personalized CCD document
            pix_add_patient_id: Patient ID from PIX Add (if available)
            pix_add_patient_id_oid: Patient ID OID
            
        Returns:
            ITI41Transaction ready for submission
        """
        # Use PIX Add patient ID if available, otherwise use original
        patient_id = pix_add_patient_id or patient.patient_id
        
        # Generate XDSb metadata using fluent builder API
        builder = XDSbMetadataBuilder()
        builder.set_patient_identifier(patient_id, pix_add_patient_id_oid)
        builder.set_document(ccd_document)
        metadata_element = builder.build()
        
        # Convert to XML string
        metadata_xml = etree.tostring(metadata_element, encoding="unicode")
        
        return ITI41Transaction(
            transaction_id=str(uuid.uuid4()),
            submission_set_id=str(uuid.uuid4()),
            document_entry_id=ccd_document.document_id,
            patient_id=patient_id,
            patient_id_oid=pix_add_patient_id_oid,
            ccd_document=ccd_document,
            submission_timestamp=datetime.now(timezone.utc),
            source_id=self._config.sender_oid,
            mtom_content_id=f"{uuid.uuid4()}@ihe-test-util.local",
            metadata_xml=metadata_xml,
        )
    
    def _validate_configuration(self) -> None:
        """Validate configuration before starting workflow.
        
        Raises:
            ValidationError: If required configuration is missing or invalid
        """
        logger.debug("Validating configuration for integrated workflow")
        
        # Check PIX Add endpoint
        if not self._config.endpoints.pix_add_url:
            raise ValidationError(
                "Missing required configuration: endpoints.pix_add_url. "
                "Add PIX Add endpoint URL to config.json."
            )
        
        # Check ITI-41 endpoint
        if not self._config.endpoints.iti41_url:
            raise ValidationError(
                "Missing required configuration: endpoints.iti41_url. "
                "Add ITI-41 endpoint URL to config.json."
            )
        
        # Check certificates
        if not self._config.certificates.cert_path:
            raise ValidationError(
                "Missing required configuration: certificates.cert_path. "
                "Add certificate path to config.json."
            )
        
        if not Path(self._config.certificates.cert_path).exists():
            raise ValidationError(
                f"Certificate file not found: {self._config.certificates.cert_path}. "
                "Generate certificate with: scripts/generate_cert.sh"
            )
        
        logger.debug("Configuration validation passed")
    
    def _generate_saml_assertion(self) -> SAMLAssertion:
        """Generate and sign SAML assertion for workflow.
        
        Returns:
            Signed SAML assertion ready for use
        """
        return self._pix_add_workflow._generate_saml_assertion()
    
    def _row_to_patient_demographics(self, row: pd.Series) -> PatientDemographics:
        """Convert DataFrame row to PatientDemographics object.
        
        Args:
            row: DataFrame row with patient data
            
        Returns:
            PatientDemographics object
        """
        return self._pix_add_workflow._row_to_patient_demographics(row)
    
    def _log_workflow_step(
        self,
        patient_id: str,
        step: str,
        status: str,
        duration_ms: int,
        details: str = ""
    ) -> None:
        """Log workflow step for audit trail.
        
        Args:
            patient_id: Patient identifier
            step: Workflow step name (e.g., "PIX_ADD", "ITI41", "CCD_GENERATED")
            status: Step status (e.g., "SUCCESS", "FAILED", "SKIPPED")
            duration_ms: Step duration in milliseconds
            details: Optional details about the step
        """
        logger.info(
            f"WORKFLOW_AUDIT: patient_id={patient_id}, step={step}, "
            f"status={status}, duration_ms={duration_ms}, details={details}"
        )


def save_workflow_results_to_json(
    results: BatchWorkflowResult,
    output_path: Path
) -> None:
    """Save integrated workflow results to JSON file.
    
    Creates JSON file with batch metadata, summary statistics, and
    per-patient workflow results.
    
    Args:
        results: Batch workflow results
        output_path: Path to output JSON file
        
    Example:
        >>> save_workflow_results_to_json(results, Path("output/workflow-results.json"))
    """
    logger.info(f"Saving workflow results to {output_path}")
    
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict and write
    output_data = results.to_dict()
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Saved workflow results to {output_path}")


def generate_integrated_workflow_summary(results: BatchWorkflowResult) -> str:
    """Generate human-readable summary report of integrated workflow.
    
    Creates formatted terminal output with batch information, patient
    processing results, PIX Add statistics, ITI-41 statistics, error
    breakdown, and performance metrics.
    
    Args:
        results: Batch workflow results
        
    Returns:
        Formatted summary report string
        
    Example:
        >>> report = generate_integrated_workflow_summary(results)
        >>> print(report)
    """
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("INTEGRATED WORKFLOW SUMMARY")
    lines.append("=" * 80)
    lines.append("")
    
    # Batch information
    lines.append("Batch Information")
    lines.append("-" * 80)
    lines.append(f"Batch ID:              {results.batch_id}")
    lines.append(f"CSV File:              {results.csv_file}")
    lines.append(f"Start Time:            {results.start_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if results.end_timestamp:
        lines.append(f"End Time:              {results.end_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"Total Duration:        {results.duration_formatted}")
    lines.append("")
    
    # Patient processing results
    lines.append("Patient Processing Results")
    lines.append("-" * 80)
    lines.append(f"Total Patients:        {results.total_patients}")
    
    complete_pct = results.get_overall_success_rate()
    partial_count = results.pix_add_success_count - results.fully_successful_count
    partial_pct = (partial_count / results.total_patients * 100) if results.total_patients > 0 else 0
    failed_count = results.total_patients - results.pix_add_success_count
    failed_pct = (failed_count / results.total_patients * 100) if results.total_patients > 0 else 0
    
    lines.append(f"Complete Success:      {results.fully_successful_count:3d} ({complete_pct:5.1f}%)  ← Both PIX Add AND ITI-41 succeeded")
    lines.append(f"Partial Success:       {partial_count:3d} ({partial_pct:5.1f}%)   ← PIX Add succeeded, ITI-41 failed")
    lines.append(f"Complete Failure:      {failed_count:3d} ({failed_pct:5.1f}%)   ← PIX Add failed, ITI-41 skipped")
    lines.append("")
    
    # PIX Add results
    lines.append("PIX Add Transaction Results")
    lines.append("-" * 80)
    pix_add_pct = results.get_pix_add_success_rate()
    pix_add_failed = results.total_patients - results.pix_add_success_count
    pix_add_failed_pct = (pix_add_failed / results.total_patients * 100) if results.total_patients > 0 else 0
    lines.append(f"Successful:            {results.pix_add_success_count:3d} ({pix_add_pct:5.1f}%)")
    lines.append(f"Failed:                {pix_add_failed:3d} ({pix_add_failed_pct:5.1f}%)")
    lines.append("")
    
    # ITI-41 results
    lines.append("ITI-41 Transaction Results")
    lines.append("-" * 80)
    iti41_pct = results.get_iti41_success_rate()
    iti41_failed = results.pix_add_success_count - results.iti41_success_count
    iti41_failed_pct = (iti41_failed / results.total_patients * 100) if results.total_patients > 0 else 0
    iti41_skipped = results.total_patients - results.pix_add_success_count
    iti41_skipped_pct = (iti41_skipped / results.total_patients * 100) if results.total_patients > 0 else 0
    
    lines.append(f"Successful:            {results.iti41_success_count:3d} ({iti41_pct:5.1f}%)")
    lines.append(f"Failed:                {iti41_failed:3d} ({iti41_failed_pct:5.1f}%)")
    lines.append(f"Skipped:               {iti41_skipped:3d} ({iti41_skipped_pct:5.1f}%)  ← Due to PIX Add failures")
    lines.append("")
    
    # Error breakdown - compute from patient results
    pix_add_failed = results.pix_add_failed_count
    iti41_failed = results.iti41_failed_count
    
    if pix_add_failed > 0 or iti41_failed > 0:
        lines.append("Error Breakdown")
        lines.append("-" * 80)
        
        if pix_add_failed > 0:
            lines.append("PIX Add Errors:")
            lines.append(f"  - FAILED               {pix_add_failed:3d} errors")
            lines.append("")
        
        if iti41_failed > 0:
            lines.append("ITI-41 Errors:")
            lines.append(f"  - FAILED               {iti41_failed:3d} errors")
            lines.append("")
    
    # Performance metrics
    lines.append("Performance Metrics")
    lines.append("-" * 80)
    if results.average_processing_time_ms:
        lines.append(f"Average Time per Patient:    {results.average_processing_time_ms / 1000:.1f} seconds")
    if results.throughput_per_minute:
        lines.append(f"Throughput:                  {results.throughput_per_minute:.1f} patients/minute")
    lines.append("")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)
