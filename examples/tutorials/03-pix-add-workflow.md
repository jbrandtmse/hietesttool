# Tutorial: PIX Add Workflow

This tutorial demonstrates the complete PIX Add workflow for patient registration using the IHE Test Utility.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Understanding the Workflow](#understanding-the-workflow)
3. [Single Patient Workflow](#single-patient-workflow)
4. [Batch Processing Workflow](#batch-processing-workflow)
5. [Error Handling and Recovery](#error-handling-and-recovery)
6. [Interpreting Results and Logs](#interpreting-results-and-logs)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

Before starting this tutorial, ensure you have:

1. **Python Environment**: Python 3.10+ installed with all dependencies
2. **Configuration File**: Valid `config.json` with PIX Add endpoint
3. **Certificates**: Valid certificate and private key for SAML signing
4. **CSV File**: Patient demographics in correct format
5. **Mock Server** (optional): Running mock PIX Add endpoint for testing

### Required Configuration

Your `config.json` should include:

```json
{
  "endpoints": {
    "pix_add_url": "https://pix.example.com/pix/add"
  },
  "saml": {
    "cert_path": "tests/fixtures/test_cert.pem",
    "key_path": "tests/fixtures/test_key.pem",
    "issuer": "urn:myorg:issuer",
    "subject": "user@example.com"
  },
  "sender_oid": "2.16.840.1.113883.3.72.5.1",
  "receiver_oid": "2.16.840.1.113883.3.72.5.2",
  "sender_application": "IHE_TEST_UTIL",
  "receiver_application": "PIX_MANAGER"
}
```

## Understanding the Workflow

The PIX Add workflow orchestrates five key steps:

```
CSV File → HL7v3 Message → SAML Signing → SOAP Submission → Acknowledgment
```

### Step-by-Step Process

1. **CSV Parsing**: Read and validate patient demographics
2. **SAML Generation**: Create signed SAML assertion for authentication
3. **HL7v3 Message Building**: Construct PIX Add PRPA_IN201301UV02 message
4. **SOAP Submission**: Submit message to PIX Manager endpoint
5. **Acknowledgment Parsing**: Parse MCCI_IN000002UV01 response

### Sequential Processing

**Important**: Patients are processed sequentially (one at a time), not in parallel. This ensures:
- Reliable processing order
- Easier troubleshooting
- Consistent audit trail

## Single Patient Workflow

### Step 1: Prepare CSV File

Create `patients.csv` with minimum required fields:

```csv
patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-01,M
```

### Step 2: Load Configuration

```python
from pathlib import Path
from ihe_test_util.config.manager import ConfigManager

config_manager = ConfigManager()
config = config_manager.load_config(Path("config/config.json"))
```

### Step 3: Initialize Workflow

```python
from ihe_test_util.ihe_transactions.workflows import PIXAddWorkflow

workflow = PIXAddWorkflow(config)
```

### Step 4: Process Patient

```python
csv_path = Path("patients.csv")
result = workflow.process_batch(csv_path)
```

### Step 5: Check Results

```python
print(f"Total Patients: {result.total_patients}")
print(f"Successful: {result.successful_patients}")
print(f"Failed: {result.failed_patients}")

if result.successful_patients > 0:
    patient = result.patient_results[0]
    print(f"Enterprise ID: {patient.enterprise_id}")
```

## Batch Processing Workflow

### Processing Multiple Patients

Create CSV with multiple patients:

```csv
patient_id,patient_id_oid,first_name,last_name,dob,gender,address,city,state,zip
PAT001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-01,M,123 Main St,Boston,MA,02101
PAT002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1985-05-15,F,456 Oak Ave,Cambridge,MA,02138
PAT003,2.16.840.1.113883.3.72.5.9.1,Bob,Johnson,1990-10-20,M,789 Elm St,Somerville,MA,02144
```

### Run Batch Processing

```python
from ihe_test_util.ihe_transactions.workflows import (
    PIXAddWorkflow,
    save_registered_identifiers,
    generate_summary_report
)

# Initialize workflow
workflow = PIXAddWorkflow(config)

# Process batch
result = workflow.process_batch(Path("patients.csv"))

# Save registered identifiers
output_path = Path("output/registered-patients.json")
save_registered_identifiers(result, output_path)

# Generate summary report
report = generate_summary_report(result)
print(report)
```

### Expected Output

```
================================================================================
PIX ADD WORKFLOW SUMMARY
================================================================================

Batch ID: 550e8400-e29b-41d4-a716-446655440000
CSV File: patients.csv
Started:  2025-11-17 02:30:00 UTC
Finished: 2025-11-17 02:31:45 UTC
Duration: 1m 45s

--------------------------------------------------------------------------------
RESULTS
--------------------------------------------------------------------------------
Total Patients:       3
✓ Successful:         3 (100.0%)
✗ Failed:             0 (0.0%)

Average Processing Time: 350.0 ms per patient

--------------------------------------------------------------------------------
SUCCESSFUL REGISTRATIONS
--------------------------------------------------------------------------------
✓ PAT001 - Registered (Enterprise ID: EID123456)
✓ PAT002 - Registered (Enterprise ID: EID123457)
✓ PAT003 - Registered (Enterprise ID: EID123458)

--------------------------------------------------------------------------------
OUTPUT FILES
--------------------------------------------------------------------------------
Registered Identifiers: output/registered-patients-550e8400.json
Full Audit Log:         logs/transactions/pix-add-workflow-20251117.log

================================================================================
```

## Error Handling and Recovery

### Error Categories

The workflow handles two types of errors:

#### 1. Critical Errors (Halt Workflow)

These errors stop batch processing immediately:

- **Endpoint Unreachable**: PIX Add endpoint cannot be contacted
- **Certificate Invalid**: Certificate expired or invalid
- **Configuration Missing**: Required configuration values missing

**Example**:
```python
try:
    result = workflow.process_batch(csv_path)
except ConnectionError as e:
    print(f"CRITICAL: {e}")
    print("Remediation: Check network and endpoint configuration")
```

#### 2. Non-Critical Errors (Continue Workflow)

These errors log the failure but continue processing:

- **Validation Error**: Single patient data invalid
- **AE/AR Status**: PIX Manager rejected patient (duplicate, etc.)
- **Patient-Specific Issues**: Individual patient processing failures

**Example**:
```python
result = workflow.process_batch(csv_path)

# Workflow completes even with failures
for patient_result in result.patient_results:
    if not patient_result.is_success:
        print(f"Patient {patient_result.patient_id} failed:")
        print(f"  Error: {patient_result.pix_add_message}")
        print(f"  Details: {patient_result.error_details}")
```

### Common Error Scenarios

#### Endpoint Unreachable

**Error Message**:
```
ConnectionError: Could not connect to PIX Add endpoint at https://pix.example.com/pix/add
```

**Remediation**:
1. Check network connectivity: `curl -I https://pix.example.com/pix/add`
2. Verify endpoint URL in config.json
3. Ensure PIX Manager is running and accessible

#### Certificate Validation Failed

**Error Message**:
```
SSLError: Certificate verification failed
```

**Remediation**:
1. For self-signed certificates: Set `verify_tls=false` in config (development only)
2. For production: Generate valid certificate: `scripts/generate_cert.sh`
3. Check certificate expiration: `openssl x509 -in cert.pem -noout -dates`

#### Patient Validation Error

**Error Message**:
```
ValidationError: Invalid gender code 'X'. Must be M, F, O, or U.
```

**Remediation**:
1. Fix patient data in CSV file
2. Review CSV format: `examples/patients_sample.csv`
3. Re-run workflow with corrected CSV

## Interpreting Results and Logs

### Batch Processing Result

The `BatchProcessingResult` object contains:

```python
result.batch_id                    # Unique batch identifier
result.total_patients              # Total patients in CSV
result.successful_patients         # Successfully registered
result.failed_patients             # Registration failures
result.success_rate                # Success percentage
result.duration_seconds            # Total processing time
result.average_processing_time_ms  # Average time per patient
result.patient_results             # List of individual results
```

### Patient Result

Each `PatientResult` contains:

```python
patient_result.patient_id          # Patient ID from CSV
patient_result.pix_add_status      # SUCCESS or ERROR
patient_result.pix_add_message     # Status message
patient_result.enterprise_id       # Assigned enterprise ID
patient_result.enterprise_id_oid   # Enterprise ID domain
patient_result.processing_time_ms  # Time to process
patient_result.registration_timestamp  # When registered
patient_result.error_details       # Error information (if failed)
```

### Audit Logs

Complete transaction logs are saved to:

```
logs/transactions/pix-add-workflow-YYYYMMDD.log
```

Logs include:
- Workflow start/end timestamps
- Per-patient processing events
- Complete SOAP request/response XML
- Error messages and stack traces
- Processing statistics

**Example Log Entry**:
```
2025-11-17 02:30:00 - INFO - Starting PIX Add batch workflow: batch_id=550e8400
2025-11-17 02:30:01 - INFO - Processing patient 1/3
2025-11-17 02:30:01 - INFO - Patient PAT001 registered successfully (Enterprise ID: EID123456, Time: 250ms)
```

### Output Files

#### Registered Identifiers JSON

```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-11-17T02:31:45Z",
  "total_registered": 2,
  "patients": [
    {
      "patient_id": "PAT001",
      "enterprise_id": "EID123456",
      "enterprise_id_oid": "1.2.840.114350.1.13.99998.8734",
      "registration_timestamp": "2025-11-17T02:30:10Z"
    }
  ]
}
```

This file can be used for:
- Downstream ITI-41 document submission
- Cross-referencing patient identifiers
- Audit and compliance reporting

## Troubleshooting

### Problem: All Patients Fail with Same Error

**Symptoms**: Every patient returns same error message

**Likely Causes**:
- SAML generation failure
- Certificate invalid
- Endpoint configuration incorrect

**Solution**:
1. Check logs for first patient failure
2. Verify certificate: `openssl verify cert.pem`
3. Test endpoint connectivity: `curl -I <endpoint-url>`

### Problem: Slow Processing

**Symptoms**: Processing takes longer than expected

**Likely Causes**:
- Network latency to PIX Manager
- Endpoint overloaded
- Complex HL7v3 messages

**Solution**:
1. Check average processing time in results
2. Review endpoint health and performance
3. Consider increasing timeout in config.json

### Problem: Inconsistent Failures

**Symptoms**: Some patients succeed, others fail randomly

**Likely Causes**:
- Data quality issues in CSV
- PIX Manager validation rules
- Duplicate patient identifiers

**Solution**:
1. Review error details for failed patients
2. Check for duplicate patient IDs
3. Validate CSV data quality
4. Review PIX Manager logs

### Problem: Certificate Expired

**Symptoms**: SSLError or certificate validation failures

**Solution**:
```bash
# Generate new test certificate
cd scripts
./generate_cert.sh

# Or use existing certificate
# Update cert_path and key_path in config.json
```

### Getting Help

If problems persist:

1. **Check Documentation**: Review `docs/troubleshooting.md`
2. **Review Logs**: Check `logs/transactions/` for detailed error information
3. **Enable Debug Logging**: Set log level to DEBUG in logging configuration
4. **Use Mock Server**: Test against local mock PIX Add endpoint first

## Best Practices

1. **Always Test with Mock Server First**: Validate workflow before production
2. **Review CSV Data**: Ensure all required fields are present and valid
3. **Monitor Success Rates**: Track success rates over time
4. **Keep Audit Logs**: Maintain logs for compliance and troubleshooting
5. **Handle Errors Gracefully**: Plan for both critical and non-critical errors
6. **Use Batch IDs**: Track batches for correlation and audit

## Next Steps

After mastering the PIX Add workflow:

1. **ITI-41 Workflow**: Submit clinical documents (Story 6.x)
2. **Complete Integration**: Combine PIX Add with document submission
3. **Production Deployment**: Configure for production endpoints
4. **Monitoring**: Set up monitoring and alerting for workflows

## Additional Resources

- **Example Code**: `examples/pix_add_workflow_example.py`
- **Sample CSV**: `examples/patients_sample.csv`
- **Mock Server**: `examples/tutorials/05-mock-endpoints.md`
- **Architecture**: `docs/architecture.md`
