# Mock Request Examples

This directory contains example SOAP requests for testing the IHE Test Utility mock server endpoints.

## Available Examples

- **pix-add-request.xml** - Full PIX Add request with complete patient demographics
- **pix-add-request-minimal.xml** - Minimal PIX Add request with only required fields
- **iti41-request-sample.xml** - ITI-41 SOAP structure (MTOM encoding note included)

## Using the Examples

### Prerequisites

1. **Start the mock server:**
   ```bash
   ihe-test-util mock start
   ```

2. **Verify server is running:**
   ```bash
   ihe-test-util mock status
   # Should show: Mock server is running (PID: xxxxx) at http://localhost:8080
   ```

### Testing PIX Add Endpoint with curl

**Full PIX Add Request:**
```bash
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml; charset=UTF-8" \
  -d @examples/mock-requests/pix-add-request.xml
```

**Minimal PIX Add Request:**
```bash
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml; charset=UTF-8" \
  -d @examples/mock-requests/pix-add-request-minimal.xml
```

**Expected Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.2" extension="ACK-xxxxx"/>
      <creationTime value="20250108..."/>
      <acknowledgement>
        <typeCode code="AA"/>
        ...
      </acknowledgement>
    </MCCI_IN000002UV01>
  </soap:Body>
</soap:Envelope>
```

### Testing PIX Add Endpoint with Python

**Using requests library:**

```python
import requests
from pathlib import Path

# Load the example XML
xml_file = Path("examples/mock-requests/pix-add-request.xml")
xml_content = xml_file.read_text()

# Send request to mock server
response = requests.post(
    "http://localhost:8080/pix/add",
    data=xml_content,
    headers={"Content-Type": "application/soap+xml; charset=UTF-8"}
)

print(f"Status Code: {response.status_code}")
print(f"Response:\n{response.text}")
```

**Expected Output:**
```
Status Code: 200
Response:
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  ...
</soap:Envelope>
```

### Testing ITI-41 Endpoint

**Note:** ITI-41 requires MTOM (MIME multipart) encoding, which is complex to construct manually with curl. The `iti41-request-sample.xml` file shows the SOAP structure, but real ITI-41 submissions require multipart packaging.

**For functional ITI-41 testing, use:**

1. **Integration tests (recommended):**
   ```bash
   pytest tests/integration/test_iti41_endpoint_flow.py -v
   ```

2. **Python example (from integration tests):**
   ```python
   from email.mime.multipart import MIMEMultipart
   from email.mime.text import MIMEText
   import requests
   
   # Create multipart message
   msg = MIMEMultipart('related', boundary='boundary123')
   
   # Add SOAP envelope part
   soap_part = MIMEText(soap_envelope_xml, 'xml')
   soap_part.add_header('Content-Type', 'application/xop+xml')
   msg.attach(soap_part)
   
   # Add document attachment
   doc_part = MIMEText(ccd_document_xml, 'xml')
   doc_part.add_header('Content-Type', 'text/xml')
   doc_part.add_header('Content-ID', '<document-content@example.org>')
   msg.attach(doc_part)
   
   # Send MTOM request
   response = requests.post(
       "http://localhost:8080/iti41/submit",
       data=msg.as_string(),
       headers={
           'Content-Type': f'multipart/related; boundary="boundary123"',
           'SOAPAction': 'urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b'
       }
   )
   ```

3. **See full tutorial:**
   - [Tutorial: Using Mock Endpoints](../tutorials/05-mock-endpoints.md)

### Verifying Requests Were Received

After sending requests, check the mock server logs:

**PIX Add requests:**
```bash
# View PIX Add log
cat mocks/logs/pix-add.log

# Or use CLI command
ihe-test-util mock logs
```

**ITI-41 submissions:**
```bash
# View submission logs
ls -l mocks/logs/iti41-submissions/

# View saved documents (if enabled in config)
ls -l mocks/data/documents/
```

## Customizing Examples

### Modify Patient Data

Edit the XML files to change patient demographics:

```xml
<!-- In pix-add-request.xml -->
<hl7:name>
  <hl7:given>YourFirstName</hl7:given>
  <hl7:family>YourLastName</hl7:family>
</hl7:name>

<hl7:administrativeGenderCode code="M"/>  <!-- M, F, O, U -->
<hl7:birthTime value="19900101"/>  <!-- YYYYMMDD format -->
```

### Change Message IDs

Update message IDs to avoid duplicates:

```xml
<!-- Message ID -->
<hl7:id root="2.16.840.1.113883.3.72.5.9.1" extension="YOUR_UNIQUE_ID"/>

<!-- Patient ID -->
<hl7:id root="1.2.3.4.5" extension="YOUR_PATIENT_ID"/>
```

### Validate XML Syntax

Before sending, validate XML syntax:

```bash
# Using Python's lxml
python -c "from lxml import etree; etree.parse('examples/mock-requests/pix-add-request.xml')"

# Or use xmllint
xmllint --noout examples/mock-requests/pix-add-request.xml
```

## Testing Error Scenarios

### Invalid XML Syntax

Remove a closing tag to trigger validation error:

```bash
# Edit file to break XML, then:
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml" \
  -d @examples/mock-requests/broken-request.xml
```

**Expected:** HTTP 500 with SOAP fault

### Network Latency Simulation

Use configuration with response delay:

```bash
# Start server with latency config
ihe-test-util mock stop
ihe-test-util mock start --config mocks/config-examples/config-network-latency.json

# Send request (will be delayed 500-2000ms)
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml" \
  -d @examples/mock-requests/pix-add-request.xml
```

### Failure Simulation

Use unreliable configuration:

```bash
# Start server with 30% failure rate
ihe-test-util mock stop
ihe-test-util mock start --config mocks/config-examples/config-unreliable.json

# Send multiple requests - some will fail randomly
for i in {1..10}; do
  curl -X POST http://localhost:8080/pix/add \
    -H "Content-Type: application/soap+xml" \
    -d @examples/mock-requests/pix-add-request.xml
  echo "Request $i completed"
done
```

## Troubleshooting

### Connection Refused

**Problem:** `curl: (7) Failed to connect to localhost port 8080: Connection refused`

**Solution:** Start the mock server first:
```bash
ihe-test-util mock start
ihe-test-util mock status
```

### SOAP Fault Response

**Problem:** HTTP 500 with `<soap:Fault>` in response

**Solutions:**
1. **Check XML syntax:** Validate the XML file
2. **Use lenient mode:** `ihe-test-util mock start --config mocks/config-examples/config-lenient-validation.json`
3. **Check logs:** `cat mocks/logs/pix-add.log` for error details

### Empty Response

**Problem:** curl returns nothing

**Solutions:**
1. **Add verbose flag:** `curl -v -X POST ...`
2. **Check Content-Type:** Must be `application/soap+xml`
3. **Check file path:** Ensure `@examples/mock-requests/...` path is correct

### Wrong Endpoint

**Problem:** HTTP 404 Not Found

**Solution:** Verify endpoint URL:
- PIX Add: `http://localhost:8080/pix/add` (not `/pix-add` or `/pixadd`)
- ITI-41: `http://localhost:8080/iti41/submit` (not `/iti-41` or `/submit`)

## Next Steps

- **Tutorial:** [Using Mock Endpoints](../tutorials/05-mock-endpoints.md)
- **Documentation:** [Mock Server Guide](../../docs/mock-servers.md)
- **Configuration:** [Mock Server Configuration](../../docs/mock-server-configuration.md)
- **Integration Tests:** `tests/integration/test_pix_add_endpoint_flow.py`

## See Also

- **Example patient CSV:** `examples/patients_sample.csv`
- **Example configurations:** `mocks/config-examples/`
- **Integration tests:** `tests/integration/`
