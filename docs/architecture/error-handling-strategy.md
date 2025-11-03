# Error Handling Strategy

### General Approach

**Error Model:** Exception-based with categorization
- **TransportError:** Network, timeout, connection issues (retryable)
- **ValidationError:** CSV, XML, configuration validation (non-retryable)
- **TransactionError:** IHE transaction failures (may be retryable)
- **SecurityError:** Certificate, SAML, signing issues (non-retryable)
- **SystemError:** Unexpected failures (non-retryable)

**Exception Hierarchy:**
```python
class IHETestUtilError(Exception):
    """Base exception for all utility errors"""
    pass

class ValidationError(IHETestUtilError):
    """Data validation failures"""
    pass

class TransportError(IHETestUtilError):
    """Network and transport failures"""
    pass

class TransactionError(IHETestUtilError):
    """IHE transaction failures"""
    pass

class SecurityError(IHETestUtilError):
    """Certificate and signing failures"""
    pass
```

**Error Propagation:** 
- Exceptions bubble up to CLI layer
- CLI layer catches, logs, displays user-friendly messages
- Exit codes indicate error category

### Logging Standards

**Library:** Python `logging` module
**Format:** `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
**Levels:**
- **DEBUG:** Detailed diagnostic information (request/response details)
- **INFO:** Confirmation of expected operation (patient processed)
- **WARNING:** Something unexpected but recoverable (retry initiated)
- **ERROR:** Operation failed (patient skipped)
- **CRITICAL:** System-level failure (halting batch)

**Required Context:**
- **Correlation ID:** Unique ID per batch operation
- **Service Context:** Module name (csv_parser, ihe_transactions, etc.)
- **User Context:** Redacted patient identifiers (when applicable)

### Error Handling Patterns

#### External API Errors

**Retry Policy:**
- Max retries: 3
- Backoff strategy: Exponential (1s, 2s, 4s)
- Retry on: Connection errors, timeouts, 502/503/504
- No retry on: 4xx client errors, SOAP faults

**Circuit Breaker:** Not implemented in MVP (sequential processing)

**Timeout Configuration:**
- PIX Add: 30 seconds
- ITI-41: 60 seconds
- Configurable via configuration file

**Error Translation:**
```python
# SOAP fault → TransactionError with parsed details
# Network timeout → TransportError with retry indication
# HL7 AE/AR status → TransactionError with HL7 error details
```

#### Business Logic Errors

**Custom Exceptions:**
- `PatientValidationError`: Invalid demographics data
- `TemplateProcessingError`: Template personalization failures
- `SAMLGenerationError`: SAML assertion creation failures

**User-Facing Errors:** Clear, actionable messages with troubleshooting steps

**Error Codes:** Structured format: `{category}-{code}` (e.g., `VAL-001`, `TXN-042`)

#### Data Consistency

**Transaction Strategy:** No database transactions (file-based operations)

**Compensation Logic:**
- Failed PIX Add → Skip patient, log, continue batch
- Failed ITI-41 → Log error, continue to next patient
- Critical failures → Halt batch, preserve processed results

**Idempotency:** 
- Patient ID generation is deterministic with seed
- IHE transactions are NOT idempotent by specification
- Retry logic must account for potential duplicates
