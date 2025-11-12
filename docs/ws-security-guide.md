# WS-Security Header Construction Guide

## Overview

This guide covers the WS-Security header construction implementation for IHE transactions in the HIE Test Tool. WS-Security headers provide authentication and message integrity for SOAP-based IHE transactions by embedding signed SAML assertions.

**Module:** `ihe_test_util.saml.ws_security`  
**Primary Class:** `WSSecurityHeaderBuilder`  
**Specification:** WS-Security 1.1, WS-Addressing, IHE ITI Technical Framework

## Table of Contents

- [WS-Security Header Structure](#ws-security-header-structure)
- [WS-Addressing Requirements](#ws-addressing-requirements)
- [Basic Usage](#basic-usage)
- [Complete SOAP Envelope Examples](#complete-soap-envelope-examples)
- [Timestamp Configuration](#timestamp-configuration)
- [Integration with zeep SOAP Client](#integration-with-zeep-soap-client)
- [IHE Transaction Requirements](#ihe-transaction-requirements)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

---

## WS-Security Header Structure

### Required Elements

A WS-Security 1.1 compliant header for IHE transactions must contain:

1. **`<wsse:Security>` root element** - Contains all security-related information
2. **`<wsu:Timestamp>`** - Validity period for the message
3. **`<saml:Assertion>`** - Signed SAML assertion with user identity/credentials
4. **`mustUnderstand` attribute** - Ensures recipient processes security header

### Complete Structure

```xml
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope">
  <SOAP-ENV:Header>
    <!-- WS-Security Header (MUST be first child of SOAP:Header) -->
    <wsse:Security 
        xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
        xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
        SOAP-ENV:mustUnderstand="1">
      
      <!-- Timestamp Element -->
      <wsu:Timestamp wsu:Id="TS-12345678-1234-1234-1234-123456789abc">
        <wsu:Created>2025-11-12T13:45:30.123Z</wsu:Created>
        <wsu:Expires>2025-11-12T13:50:30.123Z</wsu:Expires>
      </wsu:Timestamp>
      
      <!-- Signed SAML Assertion -->
      <saml:Assertion 
          xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
          ID="_a1b2c3d4e5f6..." 
          Version="2.0" 
          IssueInstant="2025-11-12T13:45:30Z">
        <saml:Issuer>https://idp.hospital.org</saml:Issuer>
        <saml:Subject>
          <saml:NameID>dr.smith@hospital.org</saml:NameID>
        </saml:Subject>
        <saml:Conditions 
            NotBefore="2025-11-12T13:45:30Z" 
            NotOnOrAfter="2025-11-12T14:45:30Z">
          <saml:AudienceRestriction>
            <saml:Audience>https://pix.regional-hie.org</saml:Audience>
          </saml:AudienceRestriction>
        </saml:Conditions>
        <!-- Digital Signature -->
        <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
          <!-- Signature details -->
        </ds:Signature>
      </saml:Assertion>
    </wsse:Security>
    
    <!-- WS-Addressing Headers (after wsse:Security) -->
    <wsa:Action xmlns:wsa="http://www.w3.org/2005/08/addressing">
      urn:hl7-org:v3:PRPA_IN201301UV02
    </wsa:Action>
    <wsa:To xmlns:wsa="http://www.w3.org/2005/08/addressing">
      http://pix.regional-hie.org/pix/add
    </wsa:To>
    <wsa:MessageID xmlns:wsa="http://www.w3.org/2005/08/addressing">
      urn:uuid:87654321-4321-4321-4321-210987654321
    </wsa:MessageID>
    <wsa:ReplyTo xmlns:wsa="http://www.w3.org/2005/08/addressing">
      <wsa:Address>http://www.w3.org/2005/08/addressing/anonymous</wsa:Address>
    </wsa:ReplyTo>
  </SOAP-ENV:Header>
  
  <SOAP-ENV:Body>
    <!-- Transaction-specific message (PIX Add, ITI-41, etc.) -->
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
```

### Key Requirements

- **SOAP 1.2 Envelope:** Use namespace `http://www.w3.org/2003/05/soap-envelope`
- **Header Positioning:** `<wsse:Security>` MUST be first child of `<SOAP-ENV:Header>`
- **mustUnderstand Attribute:** Must be set to `"1"` to ensure processing
- **Timestamp Format:** ISO 8601 with UTC timezone (suffix `Z`)
- **Complete SAML:** Embed entire signed SAML assertion including `<ds:Signature>`

---

## WS-Addressing Requirements

### IHE Transaction Routing

WS-Addressing headers provide routing and correlation information for IHE transactions. These headers are added AFTER the `<wsse:Security>` element in the SOAP header.

### Required WS-Addressing Elements

1. **`<wsa:Action>`** - Transaction-specific action URI
2. **`<wsa:To>`** - Endpoint URL
3. **`<wsa:MessageID>`** - Unique message identifier (UUID format)
4. **`<wsa:ReplyTo>`** - Reply endpoint (typically anonymous for synchronous transactions)

### Action URIs by Transaction Type

| IHE Transaction | Action URI |
|----------------|------------|
| PIX Add (ITI-44) | `urn:hl7-org:v3:PRPA_IN201301UV02` |
| ITI-41 (Provide and Register) | `urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b` |
| XCPD Query (ITI-55) | `urn:hl7-org:v3:PRPA_IN201305UV02` |

### Anonymous Reply Pattern

For synchronous IHE transactions, use the anonymous reply pattern:

```xml
<wsa:ReplyTo xmlns:wsa="http://www.w3.org/2005/08/addressing">
  <wsa:Address>http://www.w3.org/2005/08/addressing/anonymous</wsa:Address>
</wsa:ReplyTo>
```

This indicates the response should be sent back on the same HTTP connection.

---

## Basic Usage

### Step 1: Generate and Sign SAML Assertion

```python
from pathlib import Path
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
from ihe_test_util.saml.signer import SAMLSigner

# Load signing certificate
cert_bundle = load_certificate(
    Path("certs/saml-signing.p12"),
    password=b"secret"
)

# Generate SAML assertion
generator = SAMLProgrammaticGenerator()
assertion = generator.generate(
    subject="dr.smith@hospital.org",
    issuer="https://idp.hospital.org",
    audience="https://pix.regional-hie.org"
)

# Sign assertion
signer = SAMLSigner(cert_bundle)
signed_assertion = signer.sign_assertion(assertion)
```

### Step 2: Build WS-Security Header

```python
from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder

builder = WSSecurityHeaderBuilder()

# Build WS-Security header with 10-minute timestamp validity
ws_security_header = builder.build_ws_security_header(
    signed_assertion,
    timestamp_validity_minutes=10
)
```

### Step 3: Create SOAP Envelope

```python
from lxml import etree

# Create transaction-specific message body
pix_message = etree.Element(
    "{urn:hl7-org:v3}PRPA_IN201301UV02",
    attrib={"ITSVersion": "XML_1.0"}
)
# ... add PIX message content ...

# Embed in SOAP envelope
envelope = builder.embed_in_soap_envelope(pix_message, ws_security_header)

# Add WS-Addressing headers
ns = {'SOAP-ENV': 'http://www.w3.org/2003/05/soap-envelope'}
header = envelope.find(".//SOAP-ENV:Header", namespaces=ns)

builder.add_ws_addressing_headers(
    header,
    action="urn:hl7-org:v3:PRPA_IN201301UV02",
    to="http://pix.regional-hie.org/pix/add"
)

# Serialize to string
soap_envelope_str = etree.tostring(envelope, encoding='unicode', pretty_print=True)
```

---

## Complete SOAP Envelope Examples

### Example 1: PIX Add (ITI-44) Transaction

```python
from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder

builder = WSSecurityHeaderBuilder()

# Use convenience method for PIX Add
soap_envelope = builder.create_pix_add_soap_envelope(
    signed_assertion,
    pix_message,
    endpoint_url="http://pix.regional-hie.org/pix/add"
)

# Send to IHE endpoint
import requests
response = requests.post(
    "http://pix.regional-hie.org/pix/add",
    data=soap_envelope,
    headers={'Content-Type': 'application/soap+xml; charset=utf-8'}
)
```

**Generated SOAP Envelope Structure:**

```xml
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope">
  <SOAP-ENV:Header>
    <wsse:Security SOAP-ENV:mustUnderstand="1">
      <wsu:Timestamp wsu:Id="TS-...">...</wsu:Timestamp>
      <saml:Assertion>...</saml:Assertion>
    </wsse:Security>
    <wsa:Action>urn:hl7-org:v3:PRPA_IN201301UV02</wsa:Action>
    <wsa:To>http://pix.regional-hie.org/pix/add</wsa:To>
    <wsa:MessageID>urn:uuid:...</wsa:MessageID>
    <wsa:ReplyTo><wsa:Address>http://www.w3.org/2005/08/addressing/anonymous</wsa:Address></wsa:ReplyTo>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3">...</PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
```

### Example 2: ITI-41 (Provide and Register Document Set)

```python
# Create ITI-41 SOAP envelope
soap_envelope = builder.create_iti41_soap_envelope(
    signed_assertion,
    iti41_request,
    endpoint_url="http://xds.regional-hie.org/xds-repository"
)

# Send to XDS repository
response = requests.post(
    "http://xds.regional-hie.org/xds-repository",
    data=soap_envelope,
    headers={'Content-Type': 'application/soap+xml; charset=utf-8'}
)
```

### Example 3: Custom Transaction with Manual Headers

```python
# Build WS-Security header
ws_security = builder.build_ws_security_header(signed_assertion)

# Create custom body
custom_body = etree.Element("CustomRequest")
etree.SubElement(custom_body, "Operation").text = "query"

# Embed in SOAP envelope
envelope = builder.embed_in_soap_envelope(custom_body, ws_security)

# Add custom WS-Addressing
ns = {'SOAP-ENV': 'http://www.w3.org/2003/05/soap-envelope'}
header = envelope.find(".//SOAP-ENV:Header", namespaces=ns)

builder.add_ws_addressing_headers(
    header,
    action="urn:custom:action:v1",
    to="http://custom.example.com/endpoint",
    message_id="urn:uuid:custom-message-id"
)
```

---

## Timestamp Configuration

### Default Timestamp Settings

By default, WS-Security timestamps are valid for **5 minutes** from creation:

```python
# Default 5-minute validity
ws_security = builder.build_ws_security_header(signed_assertion)
```

### Custom Validity Period

Adjust timestamp validity based on your requirements:

```python
# Short validity (2 minutes) for high-security transactions
ws_security = builder.build_ws_security_header(
    signed_assertion,
    timestamp_validity_minutes=2
)

# Extended validity (30 minutes) for batch operations
ws_security = builder.build_ws_security_header(
    signed_assertion,
    timestamp_validity_minutes=30
)
```

### Timestamp Format

Timestamps use **ISO 8601 format with UTC timezone**:

- Format: `YYYY-MM-DDTHH:MM:SS.sssZ`
- Example: `2025-11-12T13:45:30.123Z`
- Timezone: Always `Z` (UTC), never local time

### Best Practices

1. **Keep validity short** - 5-10 minutes is typical for real-time transactions
2. **Account for clock skew** - Allow 1-2 minutes tolerance for server time differences
3. **Never exceed 1 hour** - Long-lived timestamps increase security risks
4. **Monitor expiration** - Log warnings if messages are sent close to timestamp expiry

---

## Integration with zeep SOAP Client

### Using zeep for IHE Transactions

The `zeep` library is a modern SOAP client for Python. While our implementation provides manual SOAP envelope construction, you can also integrate with zeep.

### Basic zeep Integration

```python
from zeep import Client
from zeep.plugins import HistoryPlugin
from lxml import etree

# Create zeep client
history = HistoryPlugin()
client = Client(
    'http://pix.regional-hie.org/pix/add?wsdl',
    plugins=[history]
)

# Build WS-Security header
builder = WSSecurityHeaderBuilder()
ws_security = builder.build_ws_security_header(signed_assertion)

# Convert to zeep header
from zeep import xsd
header_element = xsd.AnyObject(ws_security, ws_security.tag)

# Make request with custom header
client.service.PixAdd(
    _soapheaders=[header_element],
    # ... PIX Add parameters ...
)
```

### Custom Transport with WS-Security

For more control, use zeep's Transport with pre-built SOAP envelopes:

```python
from zeep.transports import Transport
import requests

# Build complete SOAP envelope
soap_envelope = builder.create_pix_add_soap_envelope(
    signed_assertion,
    pix_message,
    endpoint_url="http://pix.regional-hie.org/pix/add"
)

# Send via requests (bypass zeep for full control)
session = requests.Session()
response = session.post(
    "http://pix.regional-hie.org/pix/add",
    data=soap_envelope.encode('utf-8'),
    headers={
        'Content-Type': 'application/soap+xml; charset=utf-8',
        'SOAPAction': 'urn:hl7-org:v3:PRPA_IN201301UV02'
    }
)
```

### Recommended Approach

For IHE transactions with WS-Security:

1. **Use WSSecurityHeaderBuilder** to create complete SOAP envelopes
2. **Send via requests library** for full control over headers and content
3. **Parse responses manually** using lxml or zeep's XML parser
4. **Avoid zeep's automatic envelope generation** - it may not match IHE requirements exactly

---

## IHE Transaction Requirements

### PIX Add (ITI-44) Requirements

**Transaction:** Patient Identity Cross-reference Add  
**Action URI:** `urn:hl7-org:v3:PRPA_IN201301UV02`

**Requirements:**
- WS-Security header with signed SAML assertion
- WS-Addressing headers (Action, To, MessageID, ReplyTo)
- SOAP 1.2 envelope
- HL7v3 PRPA_IN201301UV02 message in body
- Patient demographics in HL7v3 format

**Example:**

```python
from ihe_test_util.ihe_transactions.pix_add import build_pix_add_message, PatientDemographics

# Build PIX message
patient = PatientDemographics(
    patient_id="PAT123456",
    patient_id_root="2.16.840.1.113883.3.72.5.9.1",
    given_name="John",
    family_name="Doe",
    gender="M",
    birth_date="19800101"
)
pix_message = build_pix_add_message(patient)

# Create SOAP envelope
builder = WSSecurityHeaderBuilder()
soap_envelope = builder.create_pix_add_soap_envelope(
    signed_assertion,
    pix_message,
    endpoint_url="http://pix.example.com/pix/add"
)
```

### ITI-41 (Provide and Register Document Set-b) Requirements

**Transaction:** XDS Document Submission  
**Action URI:** `urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b`

**Requirements:**
- WS-Security header with signed SAML assertion
- WS-Addressing headers
- SOAP 1.2 envelope with MTOM attachments (for documents)
- XDS SubmitObjectsRequest metadata in body
- Clinical documents as MTOM attachments

**Example:**

```python
# Build ITI-41 request
iti41_request = etree.Element(
    "{urn:ihe:iti:xds-b:2007}ProvideAndRegisterDocumentSetRequest"
)
# ... add metadata and document references ...

# Create SOAP envelope
soap_envelope = builder.create_iti41_soap_envelope(
    signed_assertion,
    iti41_request,
    endpoint_url="http://xds.example.com/repository"
)

# For MTOM attachments, use additional processing
# See docs/spike-findings-1.1-soap-mtom.md
```

### XCPD Query (ITI-55) Requirements

**Transaction:** Cross-Gateway Patient Discovery  
**Action URI:** `urn:hl7-org:v3:PRPA_IN201305UV02`

**Requirements:**
- WS-Security with signed SAML (similar to PIX Add)
- Patient discovery query parameters
- May require homeCommunityId in SAML attributes

**Example:**

```python
# Build XCPD query message
xcpd_query = etree.Element(
    "{urn:hl7-org:v3}PRPA_IN201305UV02",
    attrib={"ITSVersion": "XML_1.0"}
)
# ... add query parameters ...

# Build WS-Security and envelope manually
ws_security = builder.build_ws_security_header(signed_assertion)
envelope = builder.embed_in_soap_envelope(xcpd_query, ws_security)

# Add WS-Addressing
ns = {'SOAP-ENV': 'http://www.w3.org/2003/05/soap-envelope'}
header = envelope.find(".//SOAP-ENV:Header", namespaces=ns)
builder.add_ws_addressing_headers(
    header,
    action="urn:hl7-org:v3:PRPA_IN201305UV02",
    to="http://xcpd.example.com/gateway"
)
```

---

## Security Best Practices

### 1. Certificate Management

**DO:**
- Use separate certificates for signing vs. TLS/SSL
- Rotate certificates before expiration
- Store private keys in secure key stores (HSM, Azure Key Vault)
- Use strong key lengths (2048-bit RSA minimum, 256-bit ECC preferred)

**DON'T:**
- Store private keys in code or configuration files
- Use self-signed certificates in production
- Share certificates across environments

```python
# Good: Load from secure location with password
cert_bundle = load_certificate(
    Path("/secure/certs/saml-signing.p12"),
    password=os.environ['CERT_PASSWORD'].encode()
)

# Bad: Hardcoded paths and passwords
# cert_bundle = load_certificate(Path("cert.pem"), password=b"password123")
```

### 2. Timestamp Validation

**DO:**
- Keep timestamp validity short (5-10 minutes)
- Validate timestamps on received messages
- Account for clock skew between systems
- Reject messages with expired timestamps

**DON'T:**
- Use timestamps longer than 1 hour
- Ignore timestamp validation
- Accept messages with future Created times

### 3. SAML Assertion Security

**DO:**
- Always sign SAML assertions before embedding
- Validate SAML signatures on received messages
- Include specific audience restrictions
- Use short validity periods (1 hour typical)

**DON'T:**
- Embed unsigned SAML assertions
- Use overly broad audience values
- Reuse SAML assertions across transactions

```python
# Verify SAML is signed before embedding
if not signed_assertion.signature:
    raise ValueError("SAML assertion must be signed before WS-Security embedding")

ws_security = builder.build_ws_security_header(signed_assertion)
```

### 4. Transport Security

**DO:**
- Always use HTTPS (TLS 1.2+) for IHE transactions
- Validate server certificates
- Use mutual TLS (mTLS) when available
- Log all transaction attempts for audit

**DON'T:**
- Send WS-Security headers over HTTP
- Disable certificate validation
- Skip hostname verification

```python
# Good: HTTPS with certificate validation
response = requests.post(
    "https://pix.regional-hie.org/pix/add",
    data=soap_envelope,
    headers={'Content-Type': 'application/soap+xml'},
    verify=True,  # Validate server certificate
    cert=('/path/to/client-cert.pem', '/path/to/client-key.pem')  # mTLS
)

# Bad: HTTP without validation
# response = requests.post("http://...", verify=False)
```

### 5. Logging and Monitoring

**DO:**
- Log transaction IDs (MessageID) for correlation
- Log SAML assertion IDs and subjects for audit
- Monitor timestamp expiration rates
- Alert on signature validation failures

**DON'T:**
- Log complete SAML assertions (may contain PHI)
- Log private keys or passwords
- Ignore validation errors

```python
import logging
logger = logging.getLogger(__name__)

# Good: Log relevant details without sensitive data
logger.info(
    f"Created WS-Security SOAP envelope: "
    f"MessageID={message_id}, "
    f"SAML ID={signed_assertion.assertion_id}, "
    f"Subject={signed_assertion.subject}"
)

# Bad: Logging full SAML XML (may contain PHI/PII)
# logger.debug(f"SAML XML: {signed_assertion.xml_content}")
```

### 6. Error Handling

**DO:**
- Provide actionable error messages
- Catch specific exceptions
- Validate inputs before processing
- Return appropriate SOAP faults

**DON'T:**
- Expose internal implementation details in errors
- Use bare `except:` clauses
- Ignore validation errors

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: "Missing wsu:Timestamp element"

**Symptom:** Validation fails with missing timestamp error

**Cause:** WS-Security header built without timestamp or timestamp not properly embedded

**Solution:**
```python
# Ensure build_ws_security_header is called (creates timestamp automatically)
ws_security = builder.build_ws_security_header(signed_assertion)

# Verify timestamp is present
from lxml import etree
timestamp = ws_security.find(".//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd}Timestamp")
assert timestamp is not None, "Timestamp missing"
```

#### Issue 2: "Invalid SAML XML structure"

**Symptom:** `ValueError: Invalid SAML XML structure` when building WS-Security header

**Cause:** SAML assertion xml_content is malformed or empty

**Solution:**
```python
# Verify SAML assertion has valid xml_content
assert signed_assertion.xml_content, "SAML xml_content is empty"

# Try parsing to verify it's valid XML
try:
    etree.fromstring(signed_assertion.xml_content.encode('utf-8'))
except etree.XMLSyntaxError as e:
    print(f"SAML XML is malformed: {e}")
    # Re-generate SAML assertion
```

#### Issue 3: "SOAP:Header not found in envelope"

**Symptom:** Error when adding WS-Addressing headers

**Cause:** Trying to add headers to incorrect element or envelope structure is invalid

**Solution:**
```python
# Use proper namespace when finding header
ns = {'SOAP-ENV': 'http://www.w3.org/2003/05/soap-envelope'}
header = envelope.find(".//SOAP-ENV:Header", namespaces=ns)

if header is None:
    # Re-build envelope properly
    envelope = builder.embed_in_soap_envelope(body, ws_security)
    header = envelope.find(".//SOAP-ENV:Header", namespaces=ns)
```

#### Issue 4: "mustUnderstand attribute missing"

**Symptom:** IHE endpoint rejects message due to missing mustUnderstand

**Cause:** Manually constructed WS-Security header without required attribute

**Solution:**
```python
# Always use WSSecurityHeaderBuilder instead of manual construction
# It automatically adds mustUnderstand="1"
ws_security = builder.build_ws_security_header(signed_assertion)

# Verify attribute is present
must_understand = ws_security.get(
    "{http://www.w3.org/2003/05/soap-envelope}mustUnderstand"
)
assert must_understand == "1", "mustUnderstand attribute missing or invalid"
```

#### Issue 5: Signature not found in SAML

**Symptom:** Warning about unsigned SAML assertion

**Cause:** SAML assertion was not signed before embedding

**Solution:**
```python
# Always sign before embedding
from ihe_test_util.saml.signer import SAMLSigner

signer = SAMLSigner(cert_bundle)
signed_assertion = signer.sign_assertion(assertion)

# Verify signature is present
assert "<ds:Signature" in signed_assertion.xml_content, "SAML not signed"

# Then build WS-Security
ws_security = builder.build_ws_security_header(signed_assertion)
```

#### Issue 6: Clock skew / Timestamp expired

**Symptom:** Recipient rejects message due to expired timestamp

**Cause:** Server clocks out of sync or message took too long to send

**Solution:**
```python
# Increase timestamp validity
ws_security = builder.build_ws_security_header(
    signed_assertion,
    timestamp_validity_minutes=10  # Increase from default 5
)

# Send message immediately after construction
# Don't delay between building envelope and sending

# On recipient side, allow clock skew tolerance (typically 5 minutes)
```

#### Issue 7: WS-Addressing headers in wrong order

**Symptom:** Some IHE endpoints reject messages due to header ordering

**Cause:** WS-Addressing headers added before WS-Security

**Solution:**
```python
# ALWAYS add WS-Security first, then WS-Addressing
envelope = builder.embed_in_soap_envelope(body, ws_security)

# Then add WS-Addressing
ns = {'SOAP-ENV': 'http://www.w3.org/2003/05/soap-envelope'}
header = envelope.find(".//SOAP-ENV:Header", namespaces=ns)
builder.add_ws_addressing_headers(header, action, to)

# Or use convenience methods which handle ordering correctly
soap_envelope = builder.create_pix_add_soap_envelope(...)
```

### Debugging Tips

#### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show all WS-Security construction steps
builder = WSSecurityHeaderBuilder()
ws_security = builder.build_ws_security_header(signed_assertion)
```

#### Inspect Generated XML

```python
from lxml import etree

# Pretty-print WS-Security header
ws_security_str = etree.tostring(
    ws_security,
    encoding='unicode',
    pretty_print=True
)
print(ws_security_str)

# Validate against expected structure
assert "<wsse:Security" in ws_security_str
assert "<wsu:Timestamp" in ws_security_str
assert "<saml:Assertion" in ws_security_str
```

#### Test with Mock Endpoints

```python
# Use built-in mock server for testing
# See docs/mock-server-configuration.md

# Start mock PIX endpoint
# python -m ihe_test_util.mock_server --port 5000

# Send test message
response = requests.post(
    "http://localhost:5000/pix/add",
    data=soap_envelope,
    headers={'Content-Type': 'application/soap+xml'}
)

# Mock server logs will show validation results
print(response.status_code)
print(response.text)
```

---

## API Reference

### WSSecurityHeaderBuilder Class

```python
class WSSecurityHeaderBuilder:
    """Build WS-Security headers with SAML assertions for IHE transactions."""
```

#### Constructor

```python
def __init__(self) -> None:
    """Initialize WS-Security header builder.
    
    Registers XML namespaces for clean serialization.
    """
```

#### Methods

##### build_ws_security_header

```python
def build_ws_security_header(
    self,
    signed_saml: SAMLAssertion,
    timestamp_validity_minutes: int = 5
) -> etree.Element:
    """Build WS-Security header with signed SAML assertion.
    
    Args:
        signed_saml: Signed SAML assertion from SAMLSigner
        timestamp_validity_minutes: Timestamp validity period (default 5 min)
        
    Returns:
        lxml.etree.Element for wsse:Security header
        
    Raises:
        ValueError: If signed_saml is invalid or missing required fields
    """
```

##### embed_in_soap_envelope

```python
def embed_in_soap_envelope(
    self,
    body: etree.Element,
    ws_security_header: etree.Element
) -> etree.Element:
    """Embed WS-Security header and body in SOAP 1.2 envelope.
    
    Args:
        body: SOAP body content (e.g., PIX Add message, ITI-41 request)
        ws_security_header: WS-Security header from build_ws_security_header()
        
    Returns:
        Complete SOAP envelope as lxml.etree.Element
        
    Raises:
        ValueError: If body or header are invalid
    """
```

##### add_ws_addressing_headers

```python
def add_ws_addressing_headers(
    self,
    header: etree.Element,
    action: str,
    to: str,
    message_id: Optional[str] = None
) -> None:
    """Add WS-Addressing headers to SOAP header.
    
    Args:
        header: SOAP header element
        action: IHE transaction action URI
        to: Endpoint URL
        message_id: Optional message ID (generates UUID if not provided)
        
    Raises:
        ValueError: If required parameters are missing
    """
```

##### create_pix_add_soap_envelope

```python
def create_pix_add_soap_envelope(
    self,
    signed_saml: SAMLAssertion,
    pix_message: etree.Element,
    endpoint_url: str = "http://localhost:5000/pix/add"
) -> str:
    """Create complete PIX Add SOAP envelope with WS-Security.
    
    Args:
        signed_saml: Signed SAML assertion
        pix_message: PIX Add message element
        endpoint_url: PIX Add endpoint URL
        
    Returns:
        Serialized SOAP envelope as string
        
    Raises:
        ValueError: If parameters are invalid
    """
```

##### create_iti41_soap_envelope

```python
def create_iti41_soap_envelope(
    self,
    signed_saml: SAMLAssertion,
    iti41_request: etree.Element,
    endpoint_url: str = "http://localhost:5000/iti41/submit"
) -> str:
    """Create complete ITI-41 SOAP envelope with WS-Security.
    
    Args:
        signed_saml: Signed SAML assertion
        iti41_request: ITI-41 request element
        endpoint_url: ITI-41 endpoint URL
        
    Returns:
        Serialized SOAP envelope as string
        
    Raises:
        ValueError: If parameters are invalid
    """
```

##### validate_ws_security_header

```python
def validate_ws_security_header(self, header: etree.Element) -> bool:
    """Validate WS-Security header against specification.
    
    Args:
        header: WS-Security header element to validate
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If header is invalid with detailed error message
    """
```

### Namespace Constants

```python
WSSecurityHeaderBuilder.WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSSecurityHeaderBuilder.WSU_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
WSSecurityHeaderBuilder.WSA_NS = "http://www.w3.org/2005/08/addressing"
WSSecurityHeaderBuilder.SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
WSSecurityHeaderBuilder.SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
WSSecurityHeaderBuilder.DS_NS = "http://www.w3.org/2000/09/xmldsig#"
```

---

## Related Documentation

- [SAML Generation Guide](saml-guide.md) - SAML assertion generation (template-based and programmatic)
- [Certificate Management](certificate-management.md) - Loading and managing X.509 certificates
- [Mock Server Configuration](mock-server-configuration.md) - Testing with mock IHE endpoints
- [SOAP/MTOM Spike Findings](spike-findings-1.1-soap-mtom.md) - SOAP and MTOM implementation details

---

## References

- **WS-Security 1.1 Specification:** [OASIS WSS 1.1](http://docs.oasis-open.org/wss/v1.1/)
- **WS-Addressing:** [W3C WS-Addressing](https://www.w3.org/TR/ws-addr-core/)
- **IHE ITI Technical Framework:** [IHE ITI TF](https://www.ihe.net/resources/technical_frameworks/#IT)
- **SAML 2.0 Core:** [OASIS SAML 2.0](http://docs.oasis-open.org/security/saml/v2.0/)
- **lxml Documentation:** [lxml.de](https://lxml.de/)
