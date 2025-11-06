# Logging Guide

## Overview

The IHE Test Utility uses Python's built-in `logging` module with comprehensive configuration for audit trails, debugging, and compliance. This guide explains how to use, configure, and analyze logs.

## Quick Start

### Basic Usage

```bash
# Use default logging (INFO level, logs to ./logs/ihe-test-util.log)
ihe-test-util csv validate patients.csv

# Enable verbose/debug logging
ihe-test-util --verbose csv validate patients.csv

# Specify custom log file location
ihe-test-util --log-file /path/to/custom.log csv validate patients.csv

# Enable PII redaction for compliance
ihe-test-util --redact-pii csv validate patients.csv
```

### Environment Variables

```bash
# Override default log file location
export IHE_TEST_LOG_FILE=/var/log/ihe-test-util.log
ihe-test-util csv validate patients.csv
```

## Log Levels

### Level Hierarchy

| Level | When to Use | Examples |
|-------|-------------|----------|
| **DEBUG** | Detailed diagnostic information | Full SOAP envelopes, detailed processing steps |
| **INFO** | Confirmation of expected operation | Patient processed, file loaded, validation complete |
| **WARNING** | Something unexpected but recoverable | Retry initiated, optional field missing, format issue |
| **ERROR** | Operation failed | Patient skipped, validation error, transaction failed |
| **CRITICAL** | System-level failure | Cannot create log directory, halting batch |

### Log Level Configuration

**Console Output:**
- Default: INFO and above
- With `--verbose`: DEBUG and above

**File Output:**
- Always: DEBUG and above (regardless of verbose flag)

## Log Format

### Standard Format

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### Example Output

```
2025-11-05 20:00:00,123 - ihe_test_util.csv_parser.parser - INFO - CSV file loaded: patients.csv
2025-11-05 20:00:00,456 - ihe_test_util.csv_parser.validator - INFO - Validation started
2025-11-05 20:00:01,789 - ihe_test_util.csv_parser.validator - INFO - Validation complete: 100 patients
```

### Field Descriptions

| Field | Description | Example |
|-------|-------------|---------|
| `asctime` | Timestamp in YYYY-MM-DD HH:MM:SS,milliseconds format | `2025-11-05 20:00:00,123` |
| `name` | Module name (Python module path) | `ihe_test_util.csv_parser.parser` |
| `levelname` | Log level | `INFO`, `WARNING`, `ERROR` |
| `message` | Log message content | `CSV file loaded: patients.csv` |

## Audit Trail

### Audit Event Format

Audit events use structured logging with standard fields:

```
AUDIT [EVENT_TYPE] | status=<status> | input_file=<file> | record_count=<count> | duration=<seconds>s | correlation_id=<uuid>
```

### Example Audit Events

```
2025-11-05 20:00:05,000 - ihe_test_util.logging_audit.audit - INFO - AUDIT [CSV_PROCESSED] | status=success | input_file=patients.csv | record_count=100 | duration=2.50s | correlation_id=a1b2c3d4-e5f6-4789-a0b1-c2d3e4f5a6b7
```

### Common Audit Event Types

| Event Type | Description | Status Values |
|------------|-------------|---------------|
| `CSV_PROCESSED` | CSV file successfully processed | success, failure |
| `VALIDATION_FAILED` | CSV validation found errors | failure |
| `PIX_ADD_SUBMITTED` | PIX Add transaction submitted | success, failure |
| `ITI41_SUBMITTED` | ITI-41 document submission | success, failure |

### Audit Fields

| Field | Description | Example |
|-------|-------------|---------|
| `event_type` | Type of operation | `CSV_PROCESSED` |
| `status` | Operation result | `success` or `failure` |
| `input_file` | Input file path | `patients.csv` |
| `record_count` | Number of records processed | `100` |
| `duration` | Operation duration in seconds | `2.50s` |
| `error_count` | Number of errors (if applicable) | `5` |
| `error_message` | Error description (if status=failure) | `5 validation errors found` |
| `correlation_id` | UUID for tracking related events | `a1b2c3d4-...` |

## Transaction Logging

### Transaction Format

IHE transactions (PIX Add, ITI-41) are logged at two levels:

**INFO Level - Transaction Summary:**
```
TRANSACTION [TRANSACTION_TYPE] | status=<status> | correlation_id=<uuid> | request_size=<bytes> bytes | response_size=<bytes> bytes
```

**DEBUG Level - Full Request/Response:**
```
TRANSACTION REQUEST [TRANSACTION_TYPE] | correlation_id=<uuid>
<full SOAP envelope>

TRANSACTION RESPONSE [TRANSACTION_TYPE] | correlation_id=<uuid>
<full SOAP envelope>
```

### Example Transaction Logs

```
2025-11-05 20:05:00,000 - ihe_test_util.logging_audit.audit - INFO - TRANSACTION [PIX_ADD] | status=success | correlation_id=x1y2z3 | request_size=4096 bytes | response_size=2048 bytes

2025-11-05 20:05:00,001 - ihe_test_util.logging_audit.audit - DEBUG - TRANSACTION REQUEST [PIX_ADD] | correlation_id=x1y2z3
<soap:Envelope xmlns:soap="...">
  ...
</soap:Envelope>

2025-11-05 20:05:00,002 - ihe_test_util.logging_audit.audit - DEBUG - TRANSACTION RESPONSE [PIX_ADD] | correlation_id=x1y2z3
<soap:Envelope xmlns:soap="...">
  ...
</soap:Envelope>
```

## PII Redaction

### Enabling Redaction

```bash
# Enable PII redaction for all logs
ihe-test-util --redact-pii csv validate patients.csv
```

### Redaction Patterns

| Data Type | Pattern | Replacement |
|-----------|---------|-------------|
| SSN | `123-45-6789` | `[SSN-REDACTED]` |
| Patient Name | `name="John Doe"` | `name=[NAME-REDACTED]` |
| Patient Name | `Patient: John Doe` | `Patient: [NAME-REDACTED]` |

### Example with Redaction

**Without `--redact-pii`:**
```
INFO - Processing patient name="John Doe" ssn=123-45-6789
```

**With `--redact-pii`:**
```
INFO - Processing patient name=[NAME-REDACTED] ssn=[SSN-REDACTED]
```

### Compliance Notes

- Redaction applies to both console and file output
- Use `--redact-pii` when sharing logs externally
- Redaction is pattern-based and may not catch all PII variations
- Review logs before sharing to ensure compliance

## Log Rotation

### Configuration

Logs automatically rotate to prevent unbounded file growth:

- **Max file size:** 10MB per log file
- **Backup count:** 5 rotated files kept
- **Encoding:** UTF-8

### Rotation Behavior

When `ihe-test-util.log` reaches 10MB:

1. Current log renamed to `ihe-test-util.log.1`
2. Previous rotated files shifted: `.1` → `.2`, `.2` → `.3`, etc.
3. Oldest backup (`.5`) is deleted
4. New log file created: `ihe-test-util.log`

### File Listing Example

```
logs/
├── ihe-test-util.log       # Current log (0-10MB)
├── ihe-test-util.log.1     # Previous rotation (10MB)
├── ihe-test-util.log.2     # Older rotation (10MB)
├── ihe-test-util.log.3     # Older rotation (10MB)
├── ihe-test-util.log.4     # Older rotation (10MB)
└── ihe-test-util.log.5     # Oldest rotation (10MB)
```

**Total disk usage:** ~60MB maximum (6 files × 10MB)

## Log File Locations

### Default Location

```
./logs/ihe-test-util.log
```

### Custom Locations

**Via CLI flag:**
```bash
ihe-test-util --log-file /var/log/ihe-test-util.log csv validate patients.csv
```

**Via environment variable:**
```bash
export IHE_TEST_LOG_FILE=/var/log/ihe-test-util.log
ihe-test-util csv validate patients.csv
```

**Priority:** CLI flag > Environment variable > Default location

## Parsing Logs for Analysis

### Extracting Audit Events

```bash
# Extract all audit events
grep "AUDIT \[" logs/ihe-test-util.log

# Extract failed operations
grep "AUDIT \[.*status=failure" logs/ihe-test-util.log

# Extract specific event type
grep "AUDIT \[CSV_PROCESSED\]" logs/ihe-test-util.log
```

### Extracting Transaction Logs

```bash
# Extract transaction summaries
grep "TRANSACTION \[" logs/ihe-test-util.log | grep -v "REQUEST\|RESPONSE"

# Extract failed transactions
grep "TRANSACTION \[.*status=failure" logs/ihe-test-util.log

# Extract full transaction by correlation ID
grep "correlation_id=a1b2c3d4" logs/ihe-test-util.log
```

### Parsing with Python

```python
import re
from pathlib import Path

log_file = Path("logs/ihe-test-util.log")

# Parse audit events
audit_pattern = re.compile(r'AUDIT \[(.*?)\].*?status=(.*?)\s')
with log_file.open() as f:
    for line in f:
        match = audit_pattern.search(line)
        if match:
            event_type, status = match.groups()
            print(f"{event_type}: {status}")
```

### Analyzing with Tools

**grep and awk:**
```bash
# Count events by type
grep "AUDIT \[" logs/ihe-test-util.log | awk -F'[][]' '{print $2}' | sort | uniq -c

# Calculate average duration
grep "duration=" logs/ihe-test-util.log | grep -oP 'duration=\K[0-9.]+' | awk '{sum+=$1; count++} END {print sum/count}'
```

**jq (convert to JSON first):**
```python
# Convert audit events to JSON
import json
import re

pattern = re.compile(r'AUDIT \[(.*?)\](.*)') 
events = []

with open("logs/ihe-test-util.log") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            event_type, details = match.groups()
            # Parse details into dict...
            events.append({"event_type": event_type, ...})

with open("audit-events.json", "w") as f:
    json.dump(events, f)
```

## Troubleshooting

### Issue: Log file not created

**Symptom:**
```
WARNING - Failed to create file handler for logs/ihe-test-util.log: [Errno 13] Permission denied
```

**Solution:**
1. Check directory permissions: `ls -ld logs/`
2. Create directory manually: `mkdir -p logs && chmod 755 logs`
3. Or specify alternate location: `--log-file ~/ihe-logs/app.log`

### Issue: Log rotation not working

**Symptom:**
Single log file growing beyond 10MB without rotation

**Solution:**
1. Verify rotation is enabled (it is by default)
2. Check file system has write permissions
3. Verify no other process has log file open exclusively

### Issue: PII redaction not working

**Symptom:**
PII visible in logs despite `--redact-pii` flag

**Solution:**
1. Verify flag is specified: `ihe-test-util --redact-pii ...`
2. Check if PII matches redaction patterns (see Redaction Patterns table)
3. Custom PII formats may not be caught - modify patterns in `formatters.py`

### Issue: Verbose logging too noisy

**Symptom:**
Too much DEBUG output cluttering console

**Solution:**
1. Remove `--verbose` flag for normal operation
2. DEBUG logs still written to file for later analysis
3. Use `tail -f logs/ihe-test-util.log | grep -v DEBUG` to filter console

### Issue: Cannot find specific transaction

**Symptom:**
Need to correlate request and response for a transaction

**Solution:**
1. Each transaction has unique `correlation_id`
2. Search by correlation ID: `grep "correlation_id=<uuid>" logs/*.log`
3. This returns INFO summary + DEBUG request + DEBUG response

## Best Practices

### For Development

```bash
# Use verbose logging to see detailed processing
ihe-test-util --verbose csv validate patients.csv
```

### For Production

```bash
# Use default INFO level, no PII in logs
ihe-test-util --log-file /var/log/ihe-test-util.log csv process patients.csv
```

### For Compliance/Sharing

```bash
# Redact PII before sharing logs
ihe-test-util --redact-pii csv validate patients.csv

# Or post-process existing logs
grep -v "ssn=" logs/ihe-test-util.log > logs/shareable.log
```

### For Troubleshooting IHE Transactions

```bash
# Enable verbose to capture full SOAP envelopes
ihe-test-util --verbose pix-add register patients.csv

# Then search for specific correlation ID
grep "correlation_id=<uuid>" logs/ihe-test-util.log
```

## Programmatic Usage

### Configuring Logging in Code

```python
from pathlib import Path
from ihe_test_util.logging_audit import configure_logging, get_logger

# Configure logging (typically in main/CLI entry point)
configure_logging(
    level="DEBUG",
    log_file=Path("custom/app.log"),
    redact_pii=True
)

# Get logger for your module
logger = get_logger(__name__)

# Use logger
logger.info("Processing started")
logger.debug("Detailed processing info")
logger.error("An error occurred")
```

### Logging Audit Events

```python
from ihe_test_util.logging_audit import log_audit_event

log_audit_event("CSV_PROCESSED", {
    "input_file": "patients.csv",
    "record_count": 100,
    "status": "success",
    "duration": 2.5
})
```

### Logging Transactions

```python
from ihe_test_util.logging_audit import log_transaction

request_xml = "<soap:Envelope>...</soap:Envelope>"
response_xml = "<soap:Envelope>...</soap:Envelope>"

log_transaction(
    transaction_type="PIX_ADD",
    request=request_xml,
    response=response_xml,
    status="success"
)
```

## Additional Resources

- [Python logging documentation](https://docs.python.org/3/library/logging.html)
- [IHE Test Utility README](../README.md)
- [Architecture Documentation](architecture/index.md)
