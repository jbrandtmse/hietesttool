# Tutorial 04: Complete Patient Submission Workflow

This tutorial covers the integrated PIX Add + ITI-41 workflow that processes patients from CSV through document submission in a single command.

## Overview

The integrated workflow orchestrates the complete patient submission process:

```
CSV File → CCD Generation → PIX Add Registration → ITI-41 Document Submission
```

Each patient is processed sequentially through all four steps, with comprehensive status tracking and error handling.

## Prerequisites

Before using the integrated workflow, ensure you have:

1. **Configuration file** with both endpoint URLs configured
2. **Certificates** for SAML signing
3. **CCD template** for document generation
4. **CSV file** with patient demographics

## Quick Start

### Basic Usage

```bash
# Process patients through complete workflow
ihe-test-util submit batch examples/patients_sample.csv
```

### With Custom Options

```bash
# Use custom CCD template
ihe-test-util submit batch patients.csv --ccd-template templates/ccd-custom.xml

# Save results to JSON file
ihe-test-util submit batch patients.csv --output results.json

# Dry-run validation (no actual submissions)
ihe-test-util submit batch patients.csv --dry-run
```

## Configuration

### Required Configuration

The integrated workflow requires both PIX Add and ITI-41 endpoints configured:

```json
{
  "endpoints": {
    "pix_add_url": "https://pix.example.com/pix/add",
    "iti41_url": "https://xds.example.com/xdsrepository"
  },
  "certificates": {
    "cert_path": "config/certs/signing.pem",
    "key_path": "config/certs/signing.key"
  }
}
```

### Using Custom Configuration

```bash
ihe-test-util submit batch patients.csv --config config/production.json
```

## Workflow Steps

For each patient, the workflow executes these steps in order:

### 1. CSV Parsing

Patient demographics are extracted from the CSV file:
- Patient ID and OID
- Name (first, last)
- Date of birth
- Gender
- Address (optional)

### 2. CCD Generation

A personalized CCD document is generated using the template:
- Patient demographics inserted into template placeholders
- Unique document ID generated
- Document validated for XML well-formedness

### 3. PIX Add Registration (ITI-44)

Patient is registered with the PIX Manager:
- HL7v3 PRPA_IN201301UV02 message constructed
- SAML assertion generated and signed
- SOAP request submitted to PIX Add endpoint
- Enterprise identifier extracted from acknowledgment

### 4. ITI-41 Document Submission

CCD document submitted to XDS Repository:
- XDS.b metadata constructed using PIX enterprise ID
- MTOM-encoded SOAP request built
- Document submitted to ITI-41 endpoint
- Registry response parsed for document ID

## Error Handling

### PIX Add Failure → ITI-41 Skip

If PIX Add fails for a patient, ITI-41 is automatically skipped:

```
Patient PAT002: ✗ Failed (PIX Add: Duplicate patient identifier - ITI-41 skipped)
```

The workflow continues processing remaining patients.

### ITI-41 Failure After Successful PIX Add

If PIX Add succeeds but ITI-41 fails:

```
Patient PAT003: ⚠ Partial (PIX OK, ITI-41: Repository unavailable)
```

The patient is registered but document not submitted.

### Critical Errors

Critical errors (SSL failures, connection refused to all endpoints) will halt the workflow:

```
✗ Critical Error: Connection refused to https://pix.example.com/pix/add
```

## Output

### Console Output

Real-time progress with color-coded status:

```
================================================================================
INTEGRATED PIX ADD + ITI-41 WORKFLOW
================================================================================

CSV File:           patients.csv
Total Patients:     5
PIX Add Endpoint:   https://pix.example.com/pix/add
ITI-41 Endpoint:    https://xds.example.com/xdsrepository
CCD Template:       templates/ccd-template.xml

Processing patients...

Patient   1/5: PAT001               ✓ Complete (PIX ID: EID123456, Doc: 1.2.3.4.5)
Patient   2/5: PAT002               ✗ Failed (PIX Add: Duplicate - ITI-41 skipped)
Patient   3/5: PAT003               ✓ Complete (PIX ID: EID123457, Doc: 1.2.3.4.6)
Patient   4/5: PAT004               ⚠ Partial (PIX OK, ITI-41: Repository error)
Patient   5/5: PAT005               ✓ Complete (PIX ID: EID123458, Doc: 1.2.3.4.7)

================================================================================
WORKFLOW SUMMARY
================================================================================

Processing Results
--------------------------------------------------------------------------------
Total Patients:         5
Fully Successful:       3 (60.0%)
PIX Add Success:        4 (80.0%)
ITI-41 Success:         3 (60.0%)
PIX Add Failed:         1
ITI-41 Failed:          1
ITI-41 Skipped:         1 (PIX Add failed)
Duration:               15.3s
Avg Time/Patient:       3.06s

================================================================================
```

### JSON Output

Use `--output` to save detailed results:

```bash
ihe-test-util submit batch patients.csv --output results.json
```

JSON structure:

```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "csv_file": "patients.csv",
  "ccd_template": "templates/ccd-template.xml",
  "start_timestamp": "2025-11-26T10:00:00Z",
  "end_timestamp": "2025-11-26T10:00:15Z",
  "summary": {
    "total_patients": 5,
    "fully_successful": 3,
    "pix_add_success": 4,
    "pix_add_failed": 1,
    "iti41_success": 3,
    "iti41_failed": 1,
    "iti41_skipped": 1,
    "full_success_rate": 60.0,
    "pix_add_success_rate": 80.0,
    "iti41_success_rate": 75.0
  },
  "patients": [
    {
      "patient_id": "PAT001",
      "pix_add": {
        "status": "success",
        "enterprise_id": "EID123456",
        "enterprise_id_oid": "1.2.840.114350.1.13.99998.8734",
        "time_ms": 250
      },
      "iti41": {
        "status": "success",
        "document_id": "1.2.3.4.5",
        "time_ms": 350
      },
      "total_time_ms": 600
    },
    {
      "patient_id": "PAT002",
      "pix_add": {
        "status": "failed",
        "message": "Duplicate patient identifier"
      },
      "iti41": {
        "status": "skipped",
        "message": "Skipped due to PIX Add failure"
      }
    }
  ]
}
```

## Dry Run Mode

Validate configuration and CSV without submitting:

```bash
ihe-test-util submit batch patients.csv --dry-run
```

Output:

```
DRY RUN MODE - Validation Only
================================================================================

Validating CSV file...
✓ CSV validated: 5 patients

Validating configuration...
✓ Config validated: PIX Add @ https://pix.example.com/pix/add
✓ Config validated: ITI-41 @ https://xds.example.com/xdsrepository

Validating certificate...
✓ Certificate validated: expires 2026-11-26

Validating CCD template...
✓ CCD template validated: templates/ccd-template.xml

Sample patient validation (first 3):
✓ John Doe - Ready for workflow
✓ Jane Smith - Ready for workflow
✓ Bob Johnson - Ready for workflow
... and 2 more patients

DRY RUN COMPLETE - No errors detected

Workflow steps for each patient:
  1. Parse patient from CSV
  2. Generate personalized CCD document
  3. Register patient via PIX Add (ITI-44)
  4. Submit document via ITI-41 (Provide and Register)
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All patients processed successfully |
| 1 | Validation error (CSV, config, certificates) |
| 2 | Some transactions failed (partial success) |
| 3 | Critical error (SSL, missing config) |

## Programmatic Usage

Use the workflow from Python code:

```python
from ihe_test_util.config import load_config
from ihe_test_util.ihe_transactions.workflows import (
    IntegratedWorkflow,
    generate_integrated_workflow_summary,
    save_workflow_results_to_json,
)

# Load configuration
config = load_config("config/config.json")

# Create workflow
workflow = IntegratedWorkflow(config, "templates/ccd-template.xml")

# Process batch
result = workflow.process_batch("patients.csv")

# Check results
print(f"Total: {result.total_patients}")
print(f"Successful: {result.fully_successful_count}")
print(f"PIX Add failures: {result.pix_add_failed_count}")
print(f"ITI-41 failures: {result.iti41_failed_count}")

# Generate summary report
summary = generate_integrated_workflow_summary(result)
print(summary)

# Save JSON output
save_workflow_results_to_json(result, "output/results.json")

# Process individual patient results
for patient in result.patient_results:
    if patient.is_fully_successful:
        print(f"{patient.patient_id}: Complete - PIX ID: {patient.pix_enterprise_id}")
    elif patient.pix_add_status == "failed":
        print(f"{patient.patient_id}: PIX Add failed - {patient.pix_add_message}")
    else:
        print(f"{patient.patient_id}: ITI-41 failed - {patient.iti41_message}")
```

## Testing with Mock Endpoints

Start the mock server for local testing:

```bash
# Start mock server in background
ihe-test-util mock start --background

# Run workflow against mock endpoints
ihe-test-util submit batch examples/patients_sample.csv

# Stop mock server
ihe-test-util mock stop
```

## Troubleshooting

### "Missing required configuration: endpoints.pix_add_url"

Ensure your config.json has the PIX Add endpoint URL:

```json
{
  "endpoints": {
    "pix_add_url": "https://your-pix-server/pix/add"
  }
}
```

### "Certificate file not found"

Generate test certificates:

```bash
./scripts/generate_cert.sh
```

Or specify the path in config.json:

```json
{
  "certificates": {
    "cert_path": "/path/to/your/cert.pem",
    "key_path": "/path/to/your/key.pem"
  }
}
```

### "CCD template not found"

Specify the template path:

```bash
ihe-test-util submit batch patients.csv --ccd-template templates/ccd-template.xml
```

### Connection Errors

Check network connectivity and endpoint URLs:

```bash
# Verify endpoint is reachable
curl -I https://pix.example.com/pix/add
```

For local testing, use the mock server.

## Best Practices

1. **Always run dry-run first** to validate configuration
2. **Use JSON output** for production workflows to track results
3. **Monitor logs** for detailed debugging information
4. **Test with mock endpoints** before connecting to production systems
5. **Keep CSV files small** for initial testing (5-10 patients)
6. **Review partial failures** - patients may need re-submission

## Related Tutorials

- [03-pix-add-workflow.md](03-pix-add-workflow.md) - PIX Add only workflow
- [05-mock-endpoints.md](05-mock-endpoints.md) - Using mock endpoints for testing

## API Reference

- `IntegratedWorkflow` - Main workflow orchestrator class
- `BatchWorkflowResult` - Batch processing results with statistics
- `PatientWorkflowResult` - Per-patient workflow status
- `generate_integrated_workflow_summary()` - Summary report generation
- `save_workflow_results_to_json()` - JSON output serialization
