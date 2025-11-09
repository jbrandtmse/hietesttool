# Tutorial: Using Mock Endpoints

This tutorial demonstrates how to use the IHE Test Utility mock server for local testing and development.

## Table of Contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Example 1: Testing PIX Add Registration](#example-1-testing-pix-add-registration)
- [Example 2: Testing ITI-41 Submission](#example-2-testing-iti-41-submission)
- [Example 3: Complete Workflow (CSV → PIX Add → ITI-41)](#example-3-complete-workflow-csv--pix-add--iti-41)
- [Example 4: Testing Error Scenarios](#example-4-testing-error-scenarios)
- [Next Steps](#next-steps)

## Introduction

**Why use mock endpoints?**

Mock endpoints allow you to test IHE workflows without requiring access to external test systems. Benefits include:

- ✅ Work offline without VPN or network access
- ✅ Fast feedback with instant responses
- ✅ Repeatable tests (same behavior every time)
- ✅ Configurable error scenarios for testing edge cases
- ✅ No cost or quotas from external test systems
- ✅ Privacy (no real PHI sent externally)

**What you'll learn:**

By the end of this tutorial, you'll know how to:
1. Start and configure the mock server
2. Test PIX Add patient registration
3. Test ITI-41 document submission
4. Run complete end-to-end workflows
5. Simulate and test error scenarios

## Prerequisites

**1. Install the IHE Test Utility:**

```bash
# Clone the repository (if not already done)
cd /path/to/ihe-test-utility

# Install in development mode
pip install -e .

# Verify installation
ihe-test-util --version
```

**2. Verify project structure:**

```bash
# Check that examples exist
ls examples/patients_sample.csv
ls examples/mock-requests/

# Check that mock directories exist
ls mocks/config-examples/
```

**3. (Optional) Create test CCD template:**

For ITI-41 testing, you'll need a CCD template. For this tutorial, we'll use a minimal example.

```bash
# Check if templates exist
ls templates/
```

## Example 1: Testing PIX Add Registration

This example demonstrates patient registration using the PIX Add (ITI-8) transaction against the mock endpoint.

### Step 1: Start the Mock Server

```bash
# Terminal 1: Start mock server in HTTP mode
ihe-test-util mock start

# Expected output:
# Mock server started (PID: 12345) at http://localhost:8080
```

### Step 2: Verify Server is Running

```bash
# Check server status
ihe-test-util mock status

# Expected output:
# Mock server is running (PID: 12345) at http://localhost:8080

# Test health check
curl http://localhost:8080/health

# Expected output:
# {"status":"healthy","endpoints":["/pix/add","/iti41/submit"],"uptime_seconds":5.2}
```

### Step 3: Send a PIX Add Request

**Option A: Using curl with example XML:**

```bash
# Send the example request
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml; charset=UTF-8" \
  -d @examples/mock-requests/pix-add-request.xml

# Expected response: SOAP acknowledgment (HTTP 200)
```

**Option B: Using Python:**

Create a test script `test_pix_add.py`:

```python
import requests
from pathlib import Path

# Load example request
xml_file = Path("examples/mock-requests/pix-add-request.xml")
xml_content = xml_file.read_text()

# Send request
response = requests.post(
    "http://localhost:8080/pix/add",
    data=xml_content,
    headers={"Content-Type": "application/soap+xml; charset=UTF-8"}
)

# Print results
print(f"Status Code: {response.status_code}")
print(f"Response:\n{response.text}")
```

Run the script:

```bash
python test_pix_add.py
```

**Expected Output:**

```
Status Code: 200
Response:
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.2" extension="ACK-..."/>
      <creationTime value="20250108..."/>
      <acknowledgement>
        <typeCode code="AA"/>
        ...
      </acknowledgement>
    </MCCI_IN000002UV01>
  </soap:Body>
</soap:Envelope>
```

### Step 4: Verify Request in Logs

```bash
# View PIX Add logs
cat mocks/logs/pix-add.log

# Or use the CLI command
ihe-test-util mock logs
```

**What to look for:**
- Request timestamp
- Patient ID (PAT12345)
- Patient name (John Doe)
- Acknowledgment sent

### Step 5: Test with Different Patient Data

Edit the XML or use the minimal example:

```bash
# Use minimal request (less verbose)
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml; charset=UTF-8" \
  -d @examples/mock-requests/pix-add-request-minimal.xml
```

### Step 6: Stop the Mock Server

```bash
# When done testing
ihe-test-util mock stop

# Expected output:
# Mock server stopped (PID: 12345)
```

**✅ Example 1 Complete!** You've successfully tested PIX Add patient registration against the mock server.

---

## Example 2: Testing ITI-41 Submission

This example demonstrates document submission using the ITI-41 (Provide and Register Document Set-b) transaction.

**Note:** ITI-41 requires MTOM (MIME multipart) encoding, which is complex. We'll use Python with the `email.mime` library.

### Step 1: Start Mock Server with Document Saving

```bash
# Start server (document saving enabled by default)
ihe-test-util mock start

# Check status
ihe-test-util mock status
```

### Step 2: Create Test Document

Create a minimal CCD document `test-ccd.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <typeId root="2.16.840.1.113883.1.3" extension="POCD_HD000040"/>
  <templateId root="2.16.840.1.113883.10.20.22.1.1"/>
  <id root="2.16.840.1.113883.3.72.5.9.100" extension="DOC-12345"/>
  <code code="34133-9" displayName="Summarization of Episode Note" 
        codeSystem="2.16.840.1.113883.6.1" codeSystemName="LOINC"/>
  <title>Continuity of Care Document</title>
  <effectiveTime value="20250108150000"/>
  <confidentialityCode code="N" codeSystem="2.16.840.1.113883.5.25"/>
  <recordTarget>
    <patientRole>
      <id root="1.2.3.4.5" extension="PAT12345"/>
      <patient>
        <name>
          <given>John</given>
          <family>Doe</family>
        </name>
        <administrativeGenderCode code="M"/>
        <birthTime value="19800101"/>
      </patient>
    </patientRole>
  </recordTarget>
</ClinicalDocument>
```

### Step 3: Create Python Script for ITI-41 Submission

Create `test_iti41.py`:

```python
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import uuid

# Read the CCD document
ccd_file = Path("test-ccd.xml")
ccd_content = ccd_file.read_text()

# Create SOAP envelope with XDSb metadata
soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:xop="http://www.w3.org/2004/08/xop/include"
               xmlns:ihe="urn:ihe:iti:xds-b:2007"
               xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
  <soap:Header/>
  <soap:Body>
    <ihe:ProvideAndRegisterDocumentSetRequest>
      <rim:SubmitObjectsRequest>
        <rim:RegistryObjectList>
          <rim:ExtrinsicObject id="Document01" mimeType="text/xml"
                               objectType="urn:uuid:7edca82f-054d-47f2-a032-9b2a5b5186c1">
            <rim:Name><rim:LocalizedString value="Test CCD"/></rim:Name>
            <rim:ExternalIdentifier 
              identificationScheme="urn:uuid:58a6f841-87b3-4a3e-92fd-a8ffeff98427"
              registryObject="Document01"
              value="PAT12345^^^&amp;1.2.3.4.5&amp;ISO">
              <rim:Name><rim:LocalizedString value="XDSDocumentEntry.patientId"/></rim:Name>
            </rim:ExternalIdentifier>
          </rim:ExtrinsicObject>
        </rim:RegistryObjectList>
      </rim:SubmitObjectsRequest>
      <ihe:Document id="Document01">
        <xop:Include href="cid:document-content@example.org"/>
      </ihe:Document>
    </ihe:ProvideAndRegisterDocumentSetRequest>
  </soap:Body>
</soap:Envelope>"""

# Create multipart MTOM message
boundary = f"----boundary-{uuid.uuid4()}"
msg = MIMEMultipart('related', boundary=boundary)

# Part 1: SOAP envelope
soap_part = MIMEText(soap_envelope, 'xml', 'utf-8')
soap_part.add_header('Content-Type', 'application/xop+xml; charset=UTF-8; type="application/soap+xml"')
soap_part.add_header('Content-Transfer-Encoding', '8bit')
soap_part.add_header('Content-ID', '<soap-envelope@example.org>')
msg.attach(soap_part)

# Part 2: CCD document
doc_part = MIMEText(ccd_content, 'xml', 'utf-8')
doc_part.add_header('Content-Type', 'text/xml; charset=UTF-8')
doc_part.add_header('Content-Transfer-Encoding', '8bit')
doc_part.add_header('Content-ID', '<document-content@example.org>')
msg.attach(doc_part)

# Send MTOM request
response = requests.post(
    "http://localhost:8080/iti41/submit",
    data=msg.as_string(),
    headers={
        'Content-Type': f'multipart/related; boundary="{boundary}"; type="application/xop+xml"; start="<soap-envelope@example.org>"',
        'SOAPAction': 'urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b'
    }
)

# Print results
print(f"Status Code: {response.status_code}")
print(f"Response:\n{response.text}")
```

### Step 4: Run the ITI-41 Test

```bash
# Run the script
python test_iti41.py
```

**Expected Output:**

```
Status Code: 200
Response:
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <RegistryResponse xmlns="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"
                      status="urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success">
      <RegistryObjectList>
        <ExternalIdentifier id="doc-xxxxx"/>
      </RegistryObjectList>
    </RegistryResponse>
  </soap:Body>
</soap:Envelope>
```

### Step 5: Verify Document Was Saved

```bash
# Check saved documents
ls -l mocks/data/documents/

# Expected: Files like patient-PAT12345-timestamp.xml

# View a saved document
cat mocks/data/documents/patient-PAT12345-*.xml
```

### Step 6: Check ITI-41 Logs

```bash
# View submission logs
ls mocks/logs/iti41-submissions/

# View log contents
cat mocks/logs/iti41-submissions/*.log
```

**✅ Example 2 Complete!** You've successfully submitted a document via ITI-41 to the mock server.

---

## Example 3: Complete Workflow (CSV → PIX Add → ITI-41)

This example demonstrates the full workflow: load patient data from CSV, register via PIX Add, then submit documents via ITI-41.

**Note:** This requires the main utility commands (pix-add, submit) which may not be fully implemented yet. This example shows the intended workflow.

### Step 1: Prepare Patient CSV

Use the example CSV:

```bash
# View sample patients
head -5 examples/patients_sample.csv
```

### Step 2: Start Mock Server

```bash
# Terminal 1: Start mock server
ihe-test-util mock start
```

### Step 3: Validate CSV Data

```bash
# Terminal 2: Validate CSV before processing
ihe-test-util csv validate examples/patients_sample.csv

# Expected output: Validation successful
```

### Step 4: Register Patients via PIX Add

```bash
# Register patients against mock endpoint
ihe-test-util pix-add register \
  --csv examples/patients_sample.csv \
  --endpoint http://localhost:8080/pix/add

# Expected: Success messages for each patient
```

### Step 5: Submit CCD Documents via ITI-41

```bash
# Submit documents (requires template)
ihe-test-util submit \
  --csv examples/patients_sample.csv \
  --template templates/ccd-template.xml \
  --endpoint http://localhost:8080/iti41/submit

# Expected: Success messages for each submission
```

### Step 6: Verify Complete Workflow

```bash
# Check PIX Add registrations
cat mocks/logs/pix-add.log | grep "Patient registered"

# Check ITI-41 submissions
ls mocks/logs/iti41-submissions/

# Check saved documents
ls mocks/data/documents/

# Count successful operations
echo "PIX Add registrations: $(grep -c 'AA' mocks/logs/pix-add.log)"
echo "Documents submitted: $(ls mocks/data/documents/ | wc -l)"
```

### Step 7: Review Mock Server Logs

```bash
# View recent activity
ihe-test-util mock logs --tail 100

# Follow logs in real-time (in separate terminal)
ihe-test-util mock logs --follow
```

**✅ Example 3 Complete!** You've executed a complete end-to-end workflow using mock endpoints.

---

## Example 4: Testing Error Scenarios

This example demonstrates how to test error handling using mock server configurations.

### Scenario A: Network Latency Simulation

Test how your application handles slow responses.

```bash
# Stop existing server
ihe-test-util mock stop

# Start with network latency config (500-2000ms delays)
ihe-test-util mock start --config mocks/config-examples/config-network-latency.json

# Send request and measure time
time curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml" \
  -d @examples/mock-requests/pix-add-request.xml

# Expected: Response takes 500-2000ms (note the "real" time)
```

### Scenario B: Intermittent Failures

Test retry logic and error handling.

```bash
# Stop existing server
ihe-test-util mock stop

# Start with 30% failure rate
ihe-test-util mock start --config mocks/config-examples/config-unreliable.json

# Send multiple requests - some will fail randomly
for i in {1..10}; do
  echo "Request $i:"
  curl -X POST http://localhost:8080/pix/add \
    -H "Content-Type: application/soap+xml" \
    -d @examples/mock-requests/pix-add-request.xml \
    -w "\nHTTP Status: %{http_code}\n\n"
done

# Expected: ~3 failures (HTTP 500), ~7 successes (HTTP 200)
```

### Scenario C: Strict Validation Mode

Test with strict SOAP validation to catch malformed requests.

```bash
# Stop existing server
ihe-test-util mock stop

# Start with strict validation
ihe-test-util mock start --config mocks/config-examples/config-strict-validation.json

# Try to send invalid request (missing required fields)
# Create invalid-request.xml with missing elements, then:
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml" \
  -d @invalid-request.xml

# Expected: HTTP 500 with SOAP fault describing validation error
```

### Scenario D: Lenient Validation Mode

Test with relaxed validation for quick prototyping.

```bash
# Stop existing server
ihe-test-util mock stop

# Start with lenient validation
ihe-test-util mock start --config mocks/config-examples/config-lenient-validation.json

# Send minimal request (would fail in strict mode)
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml" \
  -d @examples/mock-requests/pix-add-request-minimal.xml

# Expected: HTTP 200 (accepted even with minimal fields)
```

### Scenario E: Custom Configuration

Create your own configuration for specific test scenarios.

Create `custom-test-config.json`:

```json
{
  "host": "localhost",
  "port": 8080,
  "log_level": "DEBUG",
  "pix_add": {
    "response_delay_ms": 1000,
    "failure_rate": 0.1,
    "validation_mode": "lenient"
  },
  "iti41": {
    "response_delay_ms": 2000,
    "failure_rate": 0.0,
    "save_documents": true,
    "validation_mode": "strict"
  }
}
```

Start with custom config:

```bash
ihe-test-util mock stop
ihe-test-util mock start --config custom-test-config.json
```

**✅ Example 4 Complete!** You've tested various error scenarios and configuration options.

---

## Next Steps

**Congratulations!** You've learned how to use the IHE Test Utility mock server for local testing.

### Continue Learning

1. **Explore Configuration Options:**
   - Read [Mock Server Configuration Guide](../../docs/mock-server-configuration.md)
   - Review example configurations in `mocks/config-examples/`

2. **Review Integration Tests:**
   - Study `tests/integration/test_pix_add_endpoint_flow.py`
   - Study `tests/integration/test_iti41_endpoint_flow.py`

3. **Use in CI/CD:**
   - See [CI/CD Integration](../../docs/mock-servers.md#cicd-integration) in docs

4. **Advanced Topics:**
   - HTTPS mode with self-signed certificates
   - Hot-reloading configuration changes
   - Custom response templates

### Helpful Resources

- **Documentation:** [Mock Server Guide](../../docs/mock-servers.md)
- **Example Requests:** [Mock Requests README](../mock-requests/README.md)
- **Configuration:** `mocks/config-examples/README.md`
- **Troubleshooting:** [Mock Server Troubleshooting](../../docs/mock-servers.md#troubleshooting)

### Best Practices

1. **Always start with HTTP mode** - simpler and faster
2. **Use lenient validation during development** - strict for final testing
3. **Check logs after each test** - understand what happened
4. **Test error scenarios early** - don't just test happy path
5. **Use mock server in CI/CD** - reliable, fast, no external dependencies

### Questions or Issues?

- Check logs: `ihe-test-util mock logs`
- Enable debug logging: Set `log_level: "DEBUG"` in config
- Review troubleshooting guide in documentation
- Examine integration tests for working examples

Happy testing! 🎉
