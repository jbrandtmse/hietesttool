# Mock Server Configuration Examples

This directory contains example configuration files demonstrating various test scenarios for the IHE mock server endpoints.

## Available Configurations

### 1. config-default.json
**Production-like settings**
- No response delays
- No failure simulation
- Lenient validation mode
- Ideal for: Basic functional testing, development

### 2. config-network-latency.json
**Slow network simulation**
- PIX Add: 500ms delay
- ITI-41: 1000ms delay
- No failures
- Ideal for: Testing timeout handling, performance under network latency

### 3. config-unreliable.json
**Error handling testing**
- PIX Add: 20% failure rate, 200ms delay
- ITI-41: 15% failure rate, 300ms delay
- Custom fault messages
- Ideal for: Testing error handling, retry logic, resilience

### 4. config-strict-validation.json
**Strict standards compliance**
- PIX Add: Requires complete patient demographics (name)
- ITI-41: Requires all XDSb metadata (patient_id, class_code, type_code)
- No delays or failures
- Ideal for: Testing standards compliance, validation logic

### 5. config-lenient-validation.json
**Minimal validation requirements**
- PIX Add: Only requires patient identifier
- ITI-41: Only requires basic document metadata
- No delays or failures
- Ideal for: Rapid prototyping, minimal test data scenarios

### 6. config-custom-ids.json
**Predictable test responses**
- PIX Add: Returns custom patient ID "TEST-PATIENT-12345"
- ITI-41: Returns custom submission_set_id and document_id
- No delays or failures
- Ideal for: Automated testing with expected response values

## Usage

### Apply a Configuration

Copy the desired configuration to `mocks/config.json`:

```bash
cp mocks/config-examples/config-unreliable.json mocks/config.json
```

### Hot-Reload Configuration

The mock server supports configuration hot-reload. Simply modify `mocks/config.json` while the server is running, and changes will be applied on the next request.

```bash
# Server is running...
cp mocks/config-examples/config-network-latency.json mocks/config.json
# Changes applied automatically on next request
```

### Create Custom Configuration

Combine settings from multiple examples:

```json
{
  "host": "0.0.0.0",
  "http_port": 8080,
  "log_level": "DEBUG",
  "pix_add_behavior": {
    "response_delay_ms": 250,
    "failure_rate": 0.05,
    "custom_patient_id": "MY-TEST-ID",
    "custom_fault_message": "Custom error message",
    "validation_mode": "strict"
  },
  "iti41_behavior": {
    "response_delay_ms": 500,
    "failure_rate": 0.1,
    "custom_submission_set_id": "1.2.3.4.5",
    "custom_document_id": "5.4.3.2.1",
    "validation_mode": "lenient"
  }
}
```

## Configuration Fields

### Global Settings
- **host**: Server bind address (default: "0.0.0.0")
- **http_port**: HTTP port (default: 8080)
- **https_port**: HTTPS port (default: 8443)
- **log_level**: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **save_submitted_documents**: Save CCD documents to disk (default: false)

### PIX Add Behavior
- **response_delay_ms**: Artificial delay in milliseconds (0-5000)
- **failure_rate**: Probability of SOAP fault (0.0-1.0)
- **custom_patient_id**: Custom patient ID in acknowledgment
- **custom_fault_message**: Custom SOAP fault message text
- **validation_mode**: "strict" or "lenient"

### ITI-41 Behavior
- **response_delay_ms**: Artificial delay in milliseconds (0-5000)
- **failure_rate**: Probability of SOAP fault (0.0-1.0)
- **custom_submission_set_id**: Custom submission set unique ID
- **custom_document_id**: Custom document unique ID
- **custom_fault_message**: Custom SOAP fault message text
- **validation_mode**: "strict" or "lenient"

## Validation Modes

### Strict Mode
**PIX Add**: Requires complete patient demographics including name
**ITI-41**: Requires all XDSb metadata fields (patient_id, class_code, type_code)

Returns SOAP fault if required fields are missing.

### Lenient Mode (Default)
**PIX Add**: Only requires basic patient identifier
**ITI-41**: Only requires basic document metadata

Accepts minimal request structures, suitable for development and basic testing.

## Testing Scenarios

### Scenario 1: Load Testing
Use `config-default.json` with no delays or failures for maximum throughput testing.

### Scenario 2: Timeout Testing
Use `config-network-latency.json` with high delays to test timeout configurations and handling.

### Scenario 3: Resilience Testing
Use `config-unreliable.json` to simulate intermittent failures and test retry logic.

### Scenario 4: Standards Compliance
Use `config-strict-validation.json` to ensure requests meet IHE specifications.

### Scenario 5: Automated Testing
Use `config-custom-ids.json` to get predictable response values for assertion testing.

## Troubleshooting

### Configuration Not Loading
- Ensure `mocks/config.json` contains valid JSON
- Check server logs for configuration validation errors
- Verify file permissions

### Hot-Reload Not Working
- Ensure file modification timestamp changed
- Check server logs for reload attempts
- Invalid configuration will keep existing config (check logs for warnings)

### Validation Errors
- Check validation_mode setting
- Review required fields for strict vs lenient mode
- Enable DEBUG logging to see validation details

## See Also
- [Mock Server Configuration Guide](../../docs/mock-server-configuration.md)
- [Coding Standards](../../docs/architecture/coding-standards.md)
- [Architecture Documentation](../../docs/architecture.md)
