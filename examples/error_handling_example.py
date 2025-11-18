"""Error handling examples for PIX Add workflows.

This module demonstrates how to handle different error scenarios when
processing PIX Add transactions, including transient errors (retry),
permanent errors (skip), and critical errors (halt).
"""

import logging
from pathlib import Path

from ihe_test_util.config.manager import ConfigManager
from ihe_test_util.ihe_transactions.workflows import PIXAddWorkflow
from ihe_test_util.utils.exceptions import ErrorCategory, categorize_error
from ihe_test_util.ihe_transactions.error_summary import generate_error_report

# Configure logging to see error handling in action
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_1_handle_transient_errors():
    """Example 1: Handle transient errors with automatic retry.
    
    Transient errors (ConnectionError, Timeout) are automatically retried
    with exponential backoff. The workflow continues after successful retry.
    """
    print("=" * 80)
    print("EXAMPLE 1: Handling Transient Errors (Automatic Retry)")
    print("=" * 80)
    print()
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Create workflow
    workflow = PIXAddWorkflow(config)
    
    # Process patients - transient errors will be retried automatically
    csv_path = Path("examples/patients_sample.csv")
    
    try:
        result = workflow.process_batch(csv_path)
        
        print(f"Batch processing completed:")
        print(f"  Total patients: {result.total_patients}")
        print(f"  Successful: {result.successful_patients}")
        print(f"  Failed: {result.failed_patients}")
        print()
        
        # Check for errors in summary
        if "_error_statistics" in result.error_summary:
            stats = result.error_summary["_error_statistics"]
            print("Error Statistics:")
            print(f"  Total errors: {stats['total_errors']}")
            print(f"  Error rate: {stats['error_rate']:.1f}%")
            print()
            
            # Show errors by category
            print("Errors by Category:")
            for category, count in stats["by_category"].items():
                print(f"  {category}: {count}")
            print()
        
    except Exception as e:
        # Critical errors that halt processing
        category = categorize_error(e)
        print(f"CRITICAL ERROR: {e}")
        print(f"Error Category: {category}")
        print()


def example_2_handle_permanent_errors():
    """Example 2: Handle permanent errors (skip and continue).
    
    Permanent errors (ValidationError, HL7 AE) skip the failed patient
    but continue processing remaining patients in the batch.
    """
    print("=" * 80)
    print("EXAMPLE 2: Handling Permanent Errors (Skip and Continue)")
    print("=" * 80)
    print()
    
    config_manager = ConfigManager()
    config = config_manager.load_config()
    workflow = PIXAddWorkflow(config)
    
    csv_path = Path("examples/patients_sample.csv")
    
    try:
        result = workflow.process_batch(csv_path)
        
        # Show which patients failed
        if result.failed_patients > 0:
            print("Failed Patients:")
            for patient_result in result.patient_results:
                if not patient_result.is_success:
                    print(f"  {patient_result.patient_id}: {patient_result.pix_add_message}")
                    if patient_result.error_details:
                        print(f"    Details: {patient_result.error_details}")
            print()
        
        # Show which patients succeeded
        if result.successful_patients > 0:
            print("Successful Patients:")
            for patient_result in result.patient_results:
                if patient_result.is_success:
                    print(f"  {patient_result.patient_id}: Enterprise ID = {patient_result.enterprise_id}")
            print()
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}", exc_info=True)


def example_3_handle_critical_errors():
    """Example 3: Handle critical errors (halt processing).
    
    Critical errors (SSLError, CertificateError, endpoint unreachable)
    halt batch processing immediately with clear error messages.
    """
    print("=" * 80)
    print("EXAMPLE 3: Handling Critical Errors (Halt Processing)")
    print("=" * 80)
    print()
    
    config_manager = ConfigManager()
    config = config_manager.load_config()
    workflow = PIXAddWorkflow(config)
    
    csv_path = Path("examples/patients_sample.csv")
    
    try:
        result = workflow.process_batch(csv_path)
        print("Batch processing completed successfully")
        
    except ConnectionError as e:
        # Endpoint unreachable - critical error
        print("CRITICAL ERROR: Endpoint Unreachable")
        print(f"Error: {e}")
        print()
        print("Remediation Steps:")
        print("  1. Check network connectivity")
        print("  2. Verify endpoint URL in config.json")
        print("  3. Ensure PIX Add endpoint is running")
        print("  4. Test connectivity: curl -I <endpoint-url>")
        print()
        
    except Exception as e:
        # Check if it's a certificate error
        if "certificate" in str(e).lower():
            print("CRITICAL ERROR: Certificate Issue")
            print(f"Error: {e}")
            print()
            print("Remediation Steps:")
            print("  1. Check certificate expiration: openssl x509 -in cert.pem -noout -dates")
            print("  2. Generate new certificate: scripts/generate_cert.sh")
            print("  3. Update config.json with new certificate path")
            print()
        else:
            print(f"CRITICAL ERROR: {e}")
            logger.error("Unexpected critical error", exc_info=True)


def example_4_error_summary_report():
    """Example 4: Generate and display error summary report.
    
    The error summary report provides actionable insights into
    error patterns, affected patients, and remediation guidance.
    """
    print("=" * 80)
    print("EXAMPLE 4: Error Summary Report")
    print("=" * 80)
    print()
    
    config_manager = ConfigManager()
    config = config_manager.load_config()
    workflow = PIXAddWorkflow(config)
    
    csv_path = Path("examples/patients_sample.csv")
    
    try:
        result = workflow.process_batch(csv_path)
        
        # Display error summary report if errors occurred
        if result.failed_patients > 0 and "_error_report" in result.error_summary:
            error_report = result.error_summary["_error_report"]
            print(error_report)
            print()
            
            # Additional analysis
            stats = result.error_summary["_error_statistics"]
            
            print("Key Metrics:")
            print(f"  Error Rate: {stats['error_rate']:.1f}%")
            print(f"  Total Errors: {stats['total_errors']}")
            print()
            
            print("Top Error Types:")
            for error_type, count in list(stats['by_type'].items())[:3]:
                print(f"  {error_type}: {count} occurrences")
            print()
            
        else:
            print("✓ All patients processed successfully - no errors!")
            print()
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}", exc_info=True)


def example_5_error_categorization():
    """Example 5: Using error categorization in custom code.
    
    Demonstrates how to use error categorization to implement
    custom error handling logic.
    """
    print("=" * 80)
    print("EXAMPLE 5: Error Categorization")
    print("=" * 80)
    print()
    
    from ihe_test_util.utils.exceptions import (
        categorize_error,
        create_error_info,
        ErrorCategory
    )
    from requests.exceptions import ConnectionError, Timeout
    
    # Example errors
    errors = [
        ConnectionError("Network unreachable"),
        Timeout("Request timeout"),
        ValidationError("Invalid patient data"),
        SSLError("Certificate verification failed"),
    ]
    
    print("Error Classification:")
    print()
    
    for error in errors:
        # Categorize error
        category = categorize_error(error)
        
        # Create detailed error info
        error_info = create_error_info(error, patient_id="PAT001")
        
        # Display categorization
        print(f"Error: {error.__class__.__name__}")
        print(f"  Category: {category.value}")
        print(f"  Retryable: {error_info.is_retryable}")
        print(f"  Remediation: {error_info.remediation}")
        print()
        
        # Custom handling based on category
        if category == ErrorCategory.TRANSIENT:
            print("  → Action: Retry with exponential backoff")
        elif category == ErrorCategory.PERMANENT:
            print("  → Action: Skip patient, continue batch")
        elif category == ErrorCategory.CRITICAL:
            print("  → Action: Halt processing, investigate")
        print()


def example_6_remediation_guidance():
    """Example 6: Extracting remediation guidance from errors.
    
    Shows how to get actionable remediation steps for common errors.
    """
    print("=" * 80)
    print("EXAMPLE 6: Remediation Guidance")
    print("=" * 80)
    print()
    
    from ihe_test_util.utils.exceptions import create_error_info, _generate_remediation
    
    # Common error scenarios
    scenarios = {
        "Network Unreachable": ConnectionError("Network unreachable"),
        "Request Timeout": Timeout("Request timeout after 30s"),
        "Certificate Expired": Exception("Certificate expired"),
        "Invalid Patient Data": ValidationError("Invalid gender code: X"),
    }
    
    for scenario_name, error in scenarios.items():
        print(f"Scenario: {scenario_name}")
        print("-" * 80)
        
        # Get remediation guidance
        error_info = create_error_info(error)
        
        print(f"Error Type: {error_info.error_type}")
        print(f"Category: {error_info.category.value}")
        print()
        print("Remediation Steps:")
        
        # Split remediation into actionable steps
        steps = error_info.remediation.split(". ")
        for i, step in enumerate(steps, 1):
            if step.strip():
                print(f"  {i}. {step.strip()}")
        
        print()
        print()


if __name__ == "__main__":
    print()
    print("PIX Add Error Handling Examples")
    print("=" * 80)
    print()
    print("This script demonstrates various error handling scenarios:")
    print("  1. Transient errors with automatic retry")
    print("  2. Permanent errors (skip and continue)")
    print("  3. Critical errors (halt processing)")
    print("  4. Error summary report generation")
    print("  5. Error categorization usage")
    print("  6. Remediation guidance extraction")
    print()
    print("=" * 80)
    print()
    
    # Run examples
    try:
        # Example 1: Transient errors
        # example_1_handle_transient_errors()
        
        # Example 2: Permanent errors
        # example_2_handle_permanent_errors()
        
        # Example 3: Critical errors
        # example_3_handle_critical_errors()
        
        # Example 4: Error summary report
        # example_4_error_summary_report()
        
        # Example 5: Error categorization
        example_5_error_categorization()
        
        # Example 6: Remediation guidance
        example_6_remediation_guidance()
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}", exc_info=True)
    
    print()
    print("=" * 80)
    print("Examples completed")
    print("=" * 80)
