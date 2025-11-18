# Troubleshooting Guide

This guide provides troubleshooting steps for common errors encountered when using the IHE Test Utilities.

## Table of Contents

- [Error Categories](#error-categories)
- [Common Errors and Remediation](#common-errors-and-remediation)
  - [Network Errors](#network-errors)
  - [Certificate Errors](#certificate-errors)
  - [SOAP Faults](#soap-faults)
  - [HL7 Acknowledgment Errors](#hl7-acknowledgment-errors)
  - [Validation Errors](#validation-errors)
- [Error Summary Reports](#error-summary-reports)
- [Debugging Tips](#debugging-tips)

---

## Error Categories

The system categorizes errors into three types to determine appropriate handling:

### TRANSIENT (Retry)
Temporary errors that are automatically retried with exponential backoff.

**Examples:**
- `ConnectionError` - Network unreachable
- `Timeout` - Request timeout
- HTTP 5xx - Server errors

**Behavior:**
- Automatically retried up to 3 times (configurable)
- Exponential backoff delays: 1s, 2s, 4s, 8s, 16s
- Continues processing after successful retry

### PERMANENT (Skip)
Errors that won't succeed with retry; patient is skipped but batch continues.

**Examples:**
- `ValidationError` - Invalid patient data
- HTTP 4xx - Client errors (bad request, unauthorized)
- HL7 AE/AR - Application error/reject
- Duplicate patient error

**Behavior:**
- No retry attempted
- Patient marked as failed
- Batch processing continues with remaining patients

### CRITICAL (Halt)
Errors requiring immediate attention; batch processing halts.

**Examples:**
- `SSLError` - Certificate validation failed
- `CertificateError` - Certificate expired/invalid
- Endpoint configuration invalid
- Missing required configuration

**Behavior:**
- Batch processing halts immediately
- No further patients processed
- Detailed error message with remediation steps

---

## Common Errors and Remediation

### Network Errors

#### ConnectionError: Network Unreachable

**Symptom:**
```
ConnectionError: Network unreachable
```

**Root Causes:**
1. PIX Add endpoint is not running
2. Incorrect endpoint URL in configuration
3. Network connectivity issues
4. Firewall blocking connection

**Remediation Steps:**

1. **Verify endpoint URL:**
   ```bash
   # Check config.json
   cat config.json | grep pix_add_url
   ```

2. **Test connectivity:**
   ```bash
   curl -I http://localhost:8080/pix/add
   ```

3. **Check if endpoint is running:**
   ```bash
   # For mock server
   ps aux | grep mock_server
   
   # Or check logs
   tail -f logs/mock_server.log
   ```

4. **Verify firewall rules:**
   ```bash
   # Check if port is open
   netstat -an | grep 8080
   ```

5. **Start mock server if needed:**
   ```bash
   python -m ihe_test_util.mock_server
   ```

---

#### Timeout: Request Timeout

**Symptom:**
```
Timeout: Request timeout after 30s
```

**Root Causes:**
1. Endpoint is slow or overloaded
2. Network latency issues
3. Timeout configuration too low

**Remediation Steps:**

1. **Increase timeout in config.json:**
   ```json
   {
     "transport": {
       "timeout": 60
     }
   }
   ```

2. **Check endpoint health:**
   ```bash
   curl -w "@curl-format.txt" http://localhost:8080/health
   ```

3. **Monitor endpoint logs for slow operations**

4. **Check network latency:**
   ```bash
   ping pix.endpoint.com
   ```

---

### Certificate Errors

#### Certificate Expired

**Symptom:**
```
CertificateError: Certificate expired 15 days ago on 2025-11-02
```

**Remediation Steps:**

1. **Generate new certificate:**
   ```bash
   scripts/generate_cert.sh
   ```

2. **Update config.json with new certificate path:**
   ```json
   {
     "saml": {
       "cert_path": "config/certificates/cert.pem",
       "key_path": "config/certificates/key.pem"
     }
   }
   ```

3. **Verify certificate validity:**
   ```bash
   openssl x509 -in config/certificates/cert.pem -noout -dates
   ```

---

#### SSLError: Certificate Verification Failed

**Symptom:**
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

**Root Causes:**
1. Self-signed certificate used in production
2. Certificate chain incomplete
3. Server certificate doesn't match hostname

**Remediation Steps:**

**For Development (Self-Signed Certificates):**

Update config.json to disable TLS verification:
```json
{
  "transport": {
    "verify_tls": false
  }
}
```

**⚠️ WARNING:** Only use `verify_tls: false` in development environments!

**For Production:**

1. **Use valid certificate from trusted CA**

2. **Verify certificate chain:**
   ```bash
   openssl verify -CAfile ca-bundle.crt cert.pem
   ```

3. **Check certificate Subject Alternative Name (SAN):**
   ```bash
   openssl x509 -in cert.pem -noout -text | grep -A1 "Subject Alternative Name"
   ```

---

#### Certificate Expiring Soon

**Symptom:**
```
WARNING: Certificate expires in 15 days on 2025-12-01
```

**Remediation Steps:**

1. **Generate new certificate before expiration:**
   ```bash
   scripts/generate_cert.sh
   ```

2. **Plan certificate rotation:**
   - Update configuration with new certificate
   - Test in development environment first
   - Deploy to production during maintenance window

---

### SOAP Faults

#### SOAP-ENV:Sender - Invalid SAML Assertion

**Symptom:**
```
SOAP Fault: soap:Sender
Reason: Invalid SAML assertion
Detail: SAML signature verification failed
```

**Root Causes:**
1. SAML assertion signature invalid
2. Wrong certificate used for signing
3. SAML timestamp expired

**Remediation Steps:**

1. **Verify SAML configuration:**
   ```json
   {
     "saml": {
       "cert_path": "config/certificates/cert.pem",
       "key_path": "config/certificates/key.pem",
       "issuer": "YourIssuerName",
       "subject": "YourSubjectName"
     }
   }
   ```

2. **Check SAML timestamp validity:**
   - SAML assertions expire after 5 minutes by default
   - Ensure system clocks are synchronized (use NTP)

3. **Verify certificate matches expected:**
   ```bash
   openssl x509 -in config/certificates/cert.pem -noout -subject
   ```

4. **Enable debug logging to see full SAML assertion:**
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

5. **Review logs/transactions/ for complete request XML**

---

#### SOAP-ENV:Receiver - Internal Server Error

**Symptom:**
```
SOAP Fault: soap:Receiver
Reason: Internal server error
```

**Root Causes:**
1. Server-side error in PIX Manager
2. Database connectivity issues
3. Server misconfiguration

**Remediation Steps:**

1. **This is a TRANSIENT error** - will retry automatically

2. **Check server logs** for root cause

3. **Contact PIX Manager administrator** if persists

4. **Verify server is operational:**
   ```bash
   curl -I http://pix.endpoint.com/health
   ```

---

### HL7 Acknowledgment Errors

#### HL7 AE: Unknown Key Identifier

**Symptom:**
```
HL7 Application Error (AE)
Code: 204
Text: Unknown key identifier
Location: patient/id
```

**Root Causes:**
1. Patient ID domain (OID) not recognized by PIX Manager
2. Invalid patient identifier format
3. Missing patient identifier domain configuration

**Remediation Steps:**

1. **Verify patient_id_oid in CSV:**
   ```csv
   patient_id,patient_id_oid,first_name,last_name,dob,gender
   PAT001,2.16.840.1.113883.3.test,John,Doe,1980-01-15,M
   ```

2. **Check configured OIDs in config.json:**
   ```json
   {
     "sender_oid": "2.16.840.1.113883.3.test",
     "receiver_oid": "2.16.840.1.113883.3.pix"
   }
   ```

3. **Verify PIX Manager recognizes domain:**
   - Contact PIX Manager administrator
   - Register patient identifier domain if needed

4. **Use correct domain from PIX Manager documentation**

---

#### HL7 AR: Duplicate Patient

**Symptom:**
```
HL7 Application Reject (AR)
Text: Patient already exists
```

**Root Causes:**
1. Patient already registered in PIX Manager
2. Duplicate patient_id in CSV file

**Remediation Steps:**

1. **Use PIX Query to check existing patients first**

2. **Update workflow to handle duplicates:**
   - Skip already registered patients
   - Use different patient IDs

3. **Clear test data from PIX Manager** if in development

---

### Validation Errors

#### Invalid Gender Code

**Symptom:**
```
ValidationError: Invalid gender code: X. Must be M, F, O, or U
```

**Remediation Steps:**

1. **Fix CSV data:**
   ```csv
   # Before (INVALID)
   patient_id,first_name,last_name,dob,gender
   PAT001,John,Doe,1980-01-15,X
   
   # After (VALID)
   patient_id,first_name,last_name,dob,gender
   PAT001,John,Doe,1980-01-15,M
   ```

2. **Valid gender codes:**
   - `M` - Male
   - `F` - Female
   - `O` - Other
   - `U` - Unknown

---

#### Invalid Date Format

**Symptom:**
```
ValidationError: Invalid date format for dob. Must be YYYY-MM-DD
```

**Remediation Steps:**

1. **Fix date format in CSV:**
   ```csv
   # Before (INVALID)
   patient_id,first_name,last_name,dob,gender
   PAT001,John,Doe,01/15/1980,M
   
   # After (VALID)
   patient_id,first_name,last_name,dob,gender
   PAT001,John,Doe,1980-01-15,M
   ```

2. **Required format:** `YYYY-MM-DD`

---

#### Missing Required Field

**Symptom:**
```
ValidationError: Missing required field: patient_id
```

**Remediation Steps:**

1. **Verify CSV has all required columns:**
   ```csv
   patient_id,patient_id_oid,first_name,last_name,dob,gender
   ```

2. **Required fields:**
   - `patient_id`
   - `patient_id_oid`
   - `first_name`
   - `last_name`
   - `dob`
   - `gender`

3. **Reference sample CSV:**
   ```bash
   cat examples/patients_sample.csv
   ```

---

## Error Summary Reports

When batch processing encounters errors, an error summary report is automatically generated:

```
================================================================================
ERROR SUMMARY REPORT
================================================================================

CATEGORY BREAKDOWN
--------------------------------------------------------------------------------
Transient Errors (Retry):     15 (60%)
Permanent Errors (Skip):       8 (32%)
Critical Errors (Halt):        2 (8%)

ERROR TYPE FREQUENCIES
--------------------------------------------------------------------------------
1. ConnectionError:           10 (40%) - Endpoint unreachable
2. Timeout:                    5 (20%) - Request timeout
3. ValidationError:            5 (20%) - Invalid patient data
4. HL7 AE Status:              3 (12%) - HL7 application error
5. SSLError:                   2 (8%)  - Certificate validation failed

TOP REMEDIATIONS
--------------------------------------------------------------------------------
1. ConnectionError (10 occurrences):
   → Check endpoint URL in config.json
   → Verify network connectivity: ping pix.endpoint.com
   → Check firewall rules for port 443
   → Verify endpoint is running and accessible

AFFECTED PATIENTS
--------------------------------------------------------------------------------
ConnectionError: PAT001, PAT005, PAT012, PAT015, PAT020 (+5 more)
Timeout: PAT003, PAT008, PAT019, PAT022, PAT025
================================================================================
```

### Interpreting Error Summary

**Category Breakdown:**
- Shows distribution of error types
- Helps identify if errors are systemic (all CRITICAL) or mixed

**Error Type Frequencies:**
- Most common errors listed first
- Percentage helps prioritize remediation efforts

**Top Remediations:**
- Actionable steps for most common errors
- Start with highest frequency errors

**Affected Patients:**
- List of patient IDs that failed
- Use to reprocess failed patients after fixing issues

---

## Debugging Tips

### Enable Debug Logging

Add to your script:
```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Review Transaction Logs

Complete request/response XML is logged to:
```
logs/transactions/pix-add-YYYYMMDD.log
```

**View recent transactions:**
```bash
tail -f logs/transactions/pix-add-$(date +%Y%m%d).log
```

### Inspect Malformed Responses

When malformed XML is received, the raw response is saved to:
```
logs/transactions/malformed-response-<timestamp>.xml
```

**Find malformed responses:**
```bash
ls -lt logs/transactions/malformed-response-*.xml | head -5
```

### Test Individual Components

**Test SAML generation:**
```python
python examples/programmatic_saml_example.py
```

**Test PIX Add message building:**
```python
python examples/hl7v3_message_example.py
```

**Test acknowledgment parsing:**
```python
python examples/acknowledgment_parsing_example.py
```

### Use Mock Server for Testing

Start mock server with specific behavior:

**Success responses:**
```bash
python -m ihe_test_util.mock_server --config mocks/config-examples/config-default.json
```

**Simulate failures:**
```bash
python -m ihe_test_util.mock_server --config mocks/config-examples/config-unreliable.json
```

**Strict validation:**
```bash
python -m ihe_test_util.mock_server --config mocks/config-examples/config-strict-validation.json
```

### Verify Configuration

**Check current configuration:**
```python
from ihe_test_util.config.manager import ConfigManager

config_manager = ConfigManager()
config = config_manager.load_config()

print(f"PIX Add URL: {config.endpoints.pix_add_url}")
print(f"Sender OID: {config.sender_oid}")
print(f"Certificate: {config.saml.cert_path}")
print(f"Timeout: {config.transport.timeout}s")
print(f"Verify TLS: {config.transport.verify_tls}")
```

### Common Configuration Issues

**Issue:** Config file not found

**Solution:**
```bash
# Copy example config
cp examples/config.example.json config.json

# Edit with your settings
nano config.json
```

**Issue:** Relative paths not resolving

**Solution:** Use absolute paths or paths relative to project root:
```json
{
  "saml": {
    "cert_path": "config/certificates/cert.pem",
    "key_path": "config/certificates/key.pem"
  }
}
```

---

## Getting Help

If you encounter an error not covered in this guide:

1. **Check logs:** `logs/transactions/` for complete details
2. **Review examples:** `examples/` for working code
3. **Run tests:** `python -m pytest tests/` to verify installation
4. **Consult documentation:** `docs/` for detailed guides
5. **Report bug:** Use `/reportbug` command with error details

### Information to Include in Bug Reports

- Error message and stack trace
- Configuration (redact sensitive data)
- Sample CSV data (if applicable)
- Steps to reproduce
- Expected vs actual behavior
- Relevant log excerpts from `logs/transactions/`
