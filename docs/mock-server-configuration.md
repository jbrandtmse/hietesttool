# Mock Server Configuration Guide

This guide provides comprehensive documentation for configuring the IHE mock server endpoints with customizable behaviors for testing various scenarios.

## Table of Contents

1. [Overview](#overview)
2. [Configuration File Location](#configuration-file-location)
3. [Configuration Precedence](#configuration-precedence)
4. [Configuration Structure](#configuration-structure)
5. [Global Settings](#global-settings)
6. [Per-Endpoint Behavior Configuration](#per-endpoint-behavior-configuration)
7. [Validation Modes](#validation-modes)
8. [Hot-Reload Mechanism](#hot-reload-mechanism)
9. [Common Configuration Patterns](#common-configuration-patterns)
10. [Troubleshooting](#troubleshooting)

## Overview

The mock server configuration system allows you to customize endpoint behaviors including:
- Response delays (simulate network latency)
- Failure rates (test error handling)
- Custom response IDs (predictable test results)
- Validation strictness (strict vs lenient mode)
- Custom SOAP fault messages

Configuration supports hot-reload, allowing behavior changes without server restart.

## Configuration File Location

**Default location**: `mocks/config.json`

**Example configurations**: `mocks/config-examples/`

The server automatically loads configuration from `mocks/config.json` on startup. If the file doesn't exist, default values are used.

## Configuration Precedence

Configuration values are applied in the following order (highest to lowest priority):

1. **Environment Variables** - `MOCK_SERVER_*` prefix
2. **JSON Configuration File** - `mocks/config.json`
3. **Default Values** - Built-in defaults

Example environment variable override:
```bash
export MOCK_SERVER_HTTP_PORT=9090
export MOCK_SERVER_LOG_LEVEL=DEBUG
python -m ihe_test_util.cli mock start
```

## Configuration Structure

```json
{
  "host": "0.0.0.0",
  "http_port": 8080,
  "https_port": 8443,
  "cert_path": "mocks/cert.pem",
  "key_path": "mocks/key.pem",
  "log_level": "INFO",
  "log_path": "mocks/logs/mock-server.log",
  "pix_add_endpoint": "/pix/add",
  "iti41_endpoint": "/iti41/submit",
  "save_submitted_documents": false,
  "pix_add_behavior": {
    "response_delay_ms": 0,
    "failure_rate": 0.0,
    "custom_patient_id": null,
    "custom_fault_message": null,
    "validation_mode": "lenient"
  },
  "iti41_behavior": {
    "response_delay_ms": 0,
    "failure_rate": 0.0,
    "custom_submission_set_id": null,
    "custom_document_id": null,
    "custom_fault_message": null,
    "validation_mode": "lenient"
  }
}
```

## Global Settings

### host
- **Type**: String
- **Default**: `"0.0.0.0"`
- **Description**: Server bind address. Use `"0.0.0.0"` for all interfaces, `"127.0.0.1"` for localhost only.
- **Example**: `"0.0.0.0"`

### http_port
- **Type**: Integer (1-65535)
- **Default**: `8080`
- **Description**: HTTP server port
- **Example**: `8080`

### https_port
- **Type**: Integer (1-65535)
- **Default**: `8443`
- **Description**: HTTPS server port (requires cert_path and key_path)
- **Example**: `8443`

### log_level
- **Type**: String (enum)
- **Default**: `"INFO"`
- **Valid Values**: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`
- **Description**: Logging verbosity level
- **Example**: `"DEBUG"`

### save_submitted_documents
- **Type**: Boolean
- **Default**: `false`
- **Description**: Save ITI-41 submitted CCD documents to `mocks/data/documents/`
- **Example**: `true`

### response_delay_ms (DEPRECATED)
- **Type**: Integer (0-5000)
- **Default**: `0`
- **Description**: **DEPRECATED** - Global response delay. Use per-endpoint behavior configuration instead.
- **Migration**: Move to `pix_add_behavior.response_delay_ms` and `iti41_behavior.response_delay_ms`

## Per-Endpoint Behavior Configuration

### PIX Add Behavior (`pix_add_behavior`)

#### response_delay_ms
- **Type**: Integer (0-5000)
- **Default**: `0`
- **Description**: Artificial response delay in milliseconds
- **Use Case**: Simulate slow network, test timeout handling
- **Example**: `500` (500ms delay)

#### failure_rate
- **Type**: Float (0.0-1.0)
- **Default**: `0.0`
- **Description**: Probability of returning SOAP fault (0.0 = never, 1.0 = always)
- **Use Case**: Test error handling, retry logic, resilience
- **Example**: `0.2` (20% failure rate)
- **Validation**: Must be between 0.0 and 1.0

#### custom_patient_id
- **Type**: String (optional)
- **Default**: `null`
- **Description**: Custom patient ID to return in acknowledgment (overrides request ID)
- **Use Case**: Predictable test assertions, automated testing
- **Example**: `"TEST-PATIENT-12345"`

#### custom_fault_message
- **Type**: String (optional)
- **Default**: `null`
- **Description**: Custom SOAP fault message when failure is triggered
- **Use Case**: Test specific error message handling
- **Example**: `"PIX Manager temporarily unavailable"`
- **Default Message**: `"Simulated PIX Add failure for testing"`

#### validation_mode
- **Type**: String (enum)
- **Default**: `"lenient"`
- **Valid Values**: `"strict"`, `"lenient"`
- **Description**: Validation strictness for PIX Add requests
- **See**: [Validation Modes](#validation-modes) section below

### ITI-41 Behavior (`iti41_behavior`)

#### response_delay_ms
- **Type**: Integer (0-5000)
- **Default**: `0`
- **Description**: Artificial response delay in milliseconds
- **Use Case**: Simulate slow network, test timeout handling
- **Example**: `1000` (1 second delay)

#### failure_rate
- **Type**: Float (0.0-1.0)
- **Default**: `0.0`
- **Description**: Probability of returning SOAP fault (0.0 = never, 1.0 = always)
- **Use Case**: Test error handling, retry logic, resilience
- **Example**: `0.15` (15% failure rate)
- **Validation**: Must be between 0.0 and 1.0

#### custom_submission_set_id
- **Type**: String (optional)
- **Default**: `null`
- **Description**: Custom submission set unique ID in RegistryResponse
- **Use Case**: Predictable test assertions, automated testing
- **Example**: `"1.2.840.113619.1.2.3.4.5.6.7.8.9"`

#### custom_document_id
- **Type**: String (optional)
- **Default**: `null`
- **Description**: Custom document unique ID in RegistryResponse
- **Use Case**: Predictable test assertions, automated testing
- **Example**: `"1.2.840.113619.9.8.7.6.5.4.3.2.1"`

#### custom_fault_message
- **Type**: String (optional)
- **Default**: `null`
- **Description**: Custom SOAP fault message when failure is triggered
- **Use Case**: Test specific error message handling
- **Example**: `"XDS Repository storage fault"`
- **Default Message**: `"Simulated ITI-41 submission failure for testing"`

#### validation_mode
- **Type**: String (enum)
- **Default**: `"lenient"`
- **Valid Values**: `"strict"`, `"lenient"`
- **Description**: Validation strictness for ITI-41 requests
- **See**: [Validation Modes](#validation-modes) section below

## Validation Modes

### Strict Mode (`"strict"`)

#### PIX Add Strict Validation
**Required Fields**:
- Patient identifier (`<id root="" extension="">`)
- Patient name (`<patientPerson><name><given>` and `<family>`)

**Behavior**:
- Returns SOAP fault if required fields are missing
- Error message indicates which fields are missing
- Use for: Standards compliance testing, full HL7v3 message validation

**Example Error**:
```
Strict validation failed: Missing required patient demographics (name).
Enable lenient validation mode or provide complete HL7v3 message.
```

#### ITI-41 Strict Validation
**Required Fields**:
- Patient ID (`patient_id`)
- Document class code (`class_code`)
- Document type code (`type_code`)

**Behavior**:
- Returns SOAP fault if required XDSb metadata fields are missing
- Error message lists missing fields
- Use for: XDSb standards compliance testing, complete metadata validation

**Example Error**:
```
Strict validation failed: Missing required XDSb metadata fields: class_code, type_code.
Enable lenient validation mode or provide complete XDSb metadata.
```

### Lenient Mode (`"lenient"`) - Default

#### PIX Add Lenient Validation
**Required Fields**:
- Patient identifier (`<id extension="">`)

**Behavior**:
- Accepts minimal SOAP envelope with basic patient identifier
- Logs warnings for missing optional fields
- Use for: Rapid prototyping, minimal test data, development

#### ITI-41 Lenient Validation
**Required Fields**:
- MTOM structure (multipart message)
- SubmitObjectsRequest element

**Behavior**:
- Accepts minimal ProvideAndRegisterDocumentSetRequest
- Generates default IDs if not provided
- Use for: Development, basic document submission testing

## Hot-Reload Mechanism

### Overview
The mock server automatically detects configuration file changes and reloads without restart.

### How It Works
1. Server checks `mocks/config.json` modification time before each request
2. If file timestamp changed, configuration is reloaded
3. New configuration applies immediately to subsequent requests
4. Invalid configuration keeps existing config (logs warning)

### Usage

**Modify configuration while server is running**:
```bash
# Terminal 1: Server running
python -m ihe_test_util.cli mock start

# Terminal 2: Update configuration
cp mocks/config-examples/config-unreliable.json mocks/config.json

# Changes apply immediately - no restart needed
```

**Log output**:
```
INFO - Configuration reloaded from mocks/config.json
```

### Error Handling

If reload fails (invalid JSON, validation error):
```
WARNING - Failed to reload configuration from mocks/config.json: <error>.
Keeping existing config.
```

**The server continues running with the previous valid configuration.**

### Best Practices
- Test configuration changes in staging before production
- Monitor logs for reload success/failure
- Use version control for configuration files
- Validate JSON syntax before applying

## Common Configuration Patterns

### Pattern 1: Production-Like Testing
```json
{
  "log_level": "INFO",
  "save_submitted_documents": false,
  "pix_add_behavior": {
    "response_delay_ms": 0,
    "failure_rate": 0.0,
    "validation_mode": "lenient"
  },
  "iti41_behavior": {
    "response_delay_ms": 0,
    "failure_rate": 0.0,
    "validation_mode": "lenient"
  }
}
```
**Use Case**: Basic functional testing, maximum throughput

### Pattern 2: Network Latency Simulation
```json
{
  "pix_add_behavior": {
    "response_delay_ms": 500
  },
  "iti41_behavior": {
    "response_delay_ms": 1000
  }
}
```
**Use Case**: Test timeout handling, performance under latency

### Pattern 3: Intermittent Failure Testing
```json
{
  "pix_add_behavior": {
    "response_delay_ms": 200,
    "failure_rate": 0.2,
    "custom_fault_message": "PIX Manager temporarily unavailable"
  },
  "iti41_behavior": {
    "response_delay_ms": 300,
    "failure_rate": 0.15,
    "custom_fault_message": "XDS Repository storage fault"
  }
}
```
**Use Case**: Test retry logic, error handling, resilience

### Pattern 4: Standards Compliance Testing
```json
{
  "log_level": "DEBUG",
  "pix_add_behavior": {
    "validation_mode": "strict"
  },
  "iti41_behavior": {
    "validation_mode": "strict"
  }
}
```
**Use Case**: Validate IHE standards compliance, complete metadata

### Pattern 5: Automated Testing with Predictable IDs
```json
{
  "pix_add_behavior": {
    "custom_patient_id": "TEST-PATIENT-12345"
  },
  "iti41_behavior": {
    "custom_submission_set_id": "1.2.840.113619.1.2.3.4.5.6.7.8.9",
    "custom_document_id": "1.2.840.113619.9.8.7.6.5.4.3.2.1"
  }
}
```
**Use Case**: Automated tests with expected response assertions

## Troubleshooting

### Configuration Not Loading

**Symptom**: Server uses defaults, ignoring config file

**Solutions**:
1. Verify `mocks/config.json` exists
2. Check JSON syntax: `python -m json.tool mocks/config.json`
3. Check file permissions (must be readable)
4. Review logs for validation errors

**Validation Example**:
```bash
python -m json.tool mocks/config.json
# If valid: formatted JSON output
# If invalid: parse error message
```

### Hot-Reload Not Working

**Symptom**: Configuration changes not applied

**Solutions**:
1. Ensure file modification timestamp changed
2. Check logs for "Configuration reloaded" message
3. Verify no validation errors in logs
4. Confirm server is running (not restarted)

**Debug**:
```bash
# Check file timestamp
stat mocks/config.json

# Monitor server logs
tail -f mocks/logs/mock-server.log | grep -i config
```

### Validation Errors in Strict Mode

**Symptom**: SOAP faults with "Strict validation failed" message

**Solutions**:
1. Review required fields for strict mode (see [Validation Modes](#validation-modes))
2. Add missing fields to request
3. Switch to lenient mode for testing: `"validation_mode": "lenient"`
4. Enable DEBUG logging to see field details

**Example**: PIX Add missing name
```xml
<!-- Add patient name -->
<patientPerson>
  <name>
    <given>John</given>
    <family>Doe</family>
  </name>
</patientPerson>
```

### Invalid failure_rate Value

**Symptom**: Configuration validation fails

**Error Message**:
```
Configuration validation failed: failure_rate must be between 0.0 and 1.0, got 1.5.
Adjust configuration to valid range.
```

**Solution**: Use value between 0.0 and 1.0
```json
{
  "pix_add_behavior": {
    "failure_rate": 0.2
  }
}
```

### Invalid response_delay_ms Value

**Symptom**: Configuration validation fails

**Error Message**:
```
Configuration validation failed: response_delay_ms must be between 0 and 5000.
```

**Solution**: Use value between 0 and 5000
```json
{
  "pix_add_behavior": {
    "response_delay_ms": 500
  }
}
```

### Server Not Responding

**Symptom**: Requests hang or timeout

**Possible Causes**:
1. **High response_delay_ms**: Check configuration delay values
2. **Port conflict**: Verify port not in use
3. **Firewall**: Check firewall rules for configured port

**Debug**:
```bash
# Check if server is running
python -m ihe_test_util.cli mock status

# Check port in use
netstat -an | grep 8080

# Review configuration delays
cat mocks/config.json | grep response_delay_ms
```

### Unexpected Behavior After Config Change

**Symptom**: Behavior doesn't match configuration

**Solutions**:
1. Verify configuration was successfully reloaded (check logs)
2. Confirm no environment variable overrides
3. Test with curl to isolate client issues
4. Review behavior logging at DEBUG level

**Test Configuration**:
```bash
# Set log level to DEBUG
# Check behavior logs for each request
tail -f mocks/logs/pix-add.log | grep -i behavior
```

## See Also

- [Configuration Examples](../mocks/config-examples/README.md)
- [Architecture Documentation](./architecture.md)
- [Coding Standards](./architecture/coding-standards.md)
- [Test Strategy](./architecture/test-strategy-and-standards.md)
