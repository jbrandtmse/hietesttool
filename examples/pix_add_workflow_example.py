"""PIX Add Workflow Example.

This example demonstrates the complete PIX Add workflow from CSV to patient
registration, including batch processing, error handling, and result reporting.
"""

from pathlib import Path

from ihe_test_util.config.manager import ConfigManager
from ihe_test_util.ihe_transactions.workflows import (
    PIXAddWorkflow,
    save_registered_identifiers,
    generate_summary_report
)

# Example 1: Process single patient CSV
def example_single_patient():
    """Process a single patient through PIX Add workflow."""
    print("=" * 80)
    print("EXAMPLE 1: Single Patient Workflow")
    print("=" * 80)
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config(Path("config/config.json"))
    
    # Initialize workflow
    workflow = PIXAddWorkflow(config)
    
    # Process batch (even with one patient)
    csv_path = Path("examples/patients_minimal.csv")
    result = workflow.process_batch(csv_path)
    
    # Display results
    print(f"\nProcessed: {result.total_patients} patient(s)")
    print(f"Successful: {result.successful_patients}")
    print(f"Failed: {result.failed_patients}")
    
    if result.successful_patients > 0:
        patient_result = result.patient_results[0]
        print(f"\nPatient {patient_result.patient_id} registered:")
        print(f"  Enterprise ID: {patient_result.enterprise_id}")
        print(f"  Processing Time: {patient_result.processing_time_ms}ms")


# Example 2: Process batch of patients
def example_batch_processing():
    """Process multiple patients from CSV file."""
    print("\n")
    print("=" * 80)
    print("EXAMPLE 2: Batch Processing Workflow")
    print("=" * 80)
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config(Path("config/config.json"))
    
    # Initialize workflow
    workflow = PIXAddWorkflow(config)
    
    # Process batch
    csv_path = Path("examples/patients_sample.csv")
    result = workflow.process_batch(csv_path)
    
    # Display summary statistics
    print(f"\nBatch Processing Complete:")
    print(f"  Total Patients: {result.total_patients}")
    print(f"  Successful: {result.successful_patients} ({result.success_rate:.1f}%)")
    print(f"  Failed: {result.failed_patients}")
    print(f"  Duration: {result.duration_seconds:.2f} seconds")
    
    if result.average_processing_time_ms:
        print(f"  Average Time: {result.average_processing_time_ms:.1f}ms per patient")


# Example 3: Handle errors gracefully
def example_error_handling():
    """Demonstrate error handling in workflow."""
    print("\n")
    print("=" * 80)
    print("EXAMPLE 3: Error Handling")
    print("=" * 80)
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config(Path("config/config.json"))
        
        # Initialize workflow
        workflow = PIXAddWorkflow(config)
        
        # Process batch
        csv_path = Path("examples/patients_sample.csv")
        result = workflow.process_batch(csv_path)
        
        # Check for failures
        if result.failed_patients > 0:
            print(f"\nFound {result.failed_patients} failed registration(s):")
            
            for patient_result in result.patient_results:
                if not patient_result.is_success:
                    print(f"\n  Patient {patient_result.patient_id}:")
                    print(f"    Error: {patient_result.pix_add_message}")
                    if patient_result.error_details:
                        print(f"    Details: {patient_result.error_details}")
        else:
            print("\nAll patients registered successfully!")
            
    except ConnectionError as e:
        print(f"\nCRITICAL ERROR: Endpoint unreachable")
        print(f"Error: {e}")
        print("Remediation: Check network connectivity and endpoint configuration")
        
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Check logs/transactions/ for detailed error information")


# Example 4: Save registered identifiers to file
def example_save_identifiers():
    """Save registered patient identifiers to JSON file."""
    print("\n")
    print("=" * 80)
    print("EXAMPLE 4: Save Registered Identifiers")
    print("=" * 80)
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config(Path("config/config.json"))
    
    # Initialize workflow
    workflow = PIXAddWorkflow(config)
    
    # Process batch
    csv_path = Path("examples/patients_sample.csv")
    result = workflow.process_batch(csv_path)
    
    # Save registered identifiers
    output_path = Path("output") / f"registered-{result.batch_id[:8]}.json"
    save_registered_identifiers(result, output_path)
    
    print(f"\nRegistered identifiers saved to: {output_path}")
    print(f"Total registered: {result.successful_patients} patient(s)")
    
    # Display sample of saved data
    if result.successful_patients > 0:
        first_patient = result.patient_results[0]
        print(f"\nSample registered patient:")
        print(f"  Patient ID: {first_patient.patient_id}")
        print(f"  Enterprise ID: {first_patient.enterprise_id}")
        print(f"  Registered: {first_patient.registration_timestamp}")


# Example 5: Generate and display summary report
def example_summary_report():
    """Generate comprehensive summary report."""
    print("\n")
    print("=" * 80)
    print("EXAMPLE 5: Summary Report Generation")
    print("=" * 80)
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config(Path("config/config.json"))
    
    # Initialize workflow
    workflow = PIXAddWorkflow(config)
    
    # Process batch
    csv_path = Path("examples/patients_sample.csv")
    result = workflow.process_batch(csv_path)
    
    # Generate summary report
    report = generate_summary_report(result)
    
    # Display report
    print(report)


if __name__ == "__main__":
    # Run all examples
    print("PIX Add Workflow Examples")
    print("=" * 80)
    
    # Uncomment the examples you want to run:
    
    # example_single_patient()
    # example_batch_processing()
    # example_error_handling()
    # example_save_identifiers()
    example_summary_report()
    
    print("\n" + "=" * 80)
    print("Examples complete!")
    print("=" * 80)
