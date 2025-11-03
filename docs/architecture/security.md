# Security

### Input Validation

**Validation Library:** pydantic (runtime), mypy (static)
**Validation Location:** At API boundary (CSV parsing, configuration loading)
**Required Rules:**
- All external inputs (CSV, config files, templates) MUST be validated
- Validation at entry points before processing
- Whitelist approach preferred over blacklist
- Reject invalid data with clear error messages

**Example:**
```python
class PatientSchema(BaseModel):
    patient_id: str
    first_name: str = Field(min_length=1, max_length=100)
    dob: date = Field(lt=date.today())
    gender: Literal["M", "F", "O", "U"]
```

### Authentication & Authorization

**Auth Method:** X.509 certificate-based (for SAML signing)
**Session Management:** N/A (CLI tool, no sessions)
**Required Patterns:**
- Certificates loaded only from configured paths
- Certificate expiration validated before use
- Private keys never logged or displayed

### Secrets Management

**Development:** `.env` files (gitignored)
**Production:** Environment variables or OS keychain
**Code Requirements:**
- NEVER hardcode certificates, keys, or endpoints
- Access via Config Manager only
- No secrets in logs or error messages
- No secrets in version control

**Example .env:**
```bash
IHE_TEST_PIX_ADD_ENDPOINT=https://internal-test.org/pix/add
IHE_TEST_CERT_PATH=/path/to/cert.pem
IHE_TEST_KEY_PATH=/path/to/key.pem
```

### API Security

**Rate Limiting:** N/A (client-side tool)
**CORS Policy:** N/A (no web API)
**Security Headers:** N/A (CLI tool)
**HTTPS Enforcement:** Configurable, warnings for HTTP

### Data Protection

**Encryption at Rest:** User responsibility (OS-level encryption)
**Encryption in Transit:** 
- TLS 1.2+ enforced when using HTTPS
- Certificate verification enabled by default
- Disable verification only with explicit flag and warning

**PII Handling:**
- CSV files contain test/synthetic data only (assumption)
- Optional PII redaction in logs via `--redact-pii` flag
- Regex-based redaction for SSN, names in logs

**Logging Restrictions:**
- Never log passwords, private keys, or full certificates
- Log only certificate subject DN, expiration date
- Redact sensitive fields when `--redact-pii` enabled

### Dependency Security

**Scanning Tool:** GitHub Dependabot (automated)
**Update Policy:** 
- Security updates applied within 1 week
- Minor updates quarterly
- Major updates evaluated before adoption

**Approval Process:** 
- New dependencies require PR review
- Justification in PR description
- License compatibility check (MIT/Apache/BSD)

### Security Testing

**SAST Tool:** ruff with security rules, bandit (optional)
**DAST Tool:** N/A (CLI tool, not web service)
**Penetration Testing:** Not applicable for MVP
