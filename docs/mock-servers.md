# Mock IHE Endpoints Documentation

## Table of Contents

- [Quick Start](#quick-start)
- [Overview](#overview)
- [Server Setup](#server-setup)
  - [HTTP Mode](#http-mode)
  - [HTTPS Mode](#https-mode)
- [Available Endpoints](#available-endpoints)
  - [Health Check](#health-check)
  - [PIX Add Endpoint](#pix-add-endpoint)
  - [ITI-41 Endpoint](#iti-41-endpoint)
- [CLI Commands Reference](#cli-commands-reference)
- [Configuration](#configuration)
- [HTTP vs HTTPS - When to Use Each](#http-vs-https---when-to-use-each)
- [Security Warnings](#security-warnings)
- [Integration with Main Utility](#integration-with-main-utility)
- [CI/CD Integration](#cicd-integration)
- [Performance Considerations](#performance-considerations)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [See Also](#see-also)

## Quick Start

Get up and running with the mock server in 5 steps:

**Step 1: Install the utility**
```bash
pip install -e .
```

**Step 2: Start the mock server**
```bash
ihe-test-util mock start
```

**Step 3: Verify server is running**
```bash
ihe-test-util mock status
# Expected output: Mock server is running (PID: 12345) at http://localhost:8080
```

**Step 4: Send a test request**
```bash
curl http://localhost:8080/health
# Expected output: {"status": "healthy", "endpoints": [...]}
```

**Step 5: Check logs**
```bash
ihe-test-util mock logs
```

That's it! Your mock IHE endpoints are now running locally. See [Available Endpoints](#available-endpoints) for request examples.

## Overview

The IHE Test Utility includes a built-in Flask-based mock server that simulates IHE endpoints for local testing. This eliminates the need for external test systems during development and enables fast, repeatable testing workflows.

**What the mock server provides:**
- **PIX Add endpoint** (`/pix/add`) - Simulates patient registration
- **ITI-41 endpoint** (`/iti41/submit`) - Simulates document submission with MTOM
- **Configurable behaviors** - Response delays, failure rates, validation modes
- **Request logging** - All requests logged for debugging
- **No external dependencies** - Runs entirely on your local machine

**Use cases:**
- Local development without access to test HIE systems
- CI/CD pipelines requiring reliable test endpoints
- Error scenario testing (network failures, validation errors)
- Learning IHE transaction workflows

## Server Setup

### HTTP Mode

HTTP mode is the default and simplest way to run the mock server. No certificates required.

**Start HTTP server (default port 8080):**
```bash
ihe-test-util mock start
```

**Start on custom port:**
```bash
ihe-test-util mock start --port 9090
```

**Endpoints available at:**
- `http://localhost:8080/health`
- `http://localhost:8080/pix/add`
- `http://localhost:8080/iti41/submit`

### HTTPS Mode

HTTPS mode simulates TLS-enabled endpoints using self-signed certificates.

**Step 1: Generate self-signed certificate**
```bash
./scripts/generate_cert.sh
```

This creates `mocks/certs/server.crt` and `mocks/certs/server.key`.

**Step 2: Start HTTPS server (default port 8443):**
```bash
ihe-test-util mock start --https
```

**Step 3: Test with curl (using -k to skip certificate verification):**
```bash
curl -k https://localhost:8443/health
```

**Endpoints available at:**
- `https://localhost:8443/health`
- `https://localhost:8443/pix/add`
- `https://localhost:8443/iti41/submit`

⚠️ **See [Security Warnings](#security-warnings) before using HTTPS mode.**

## Available Endpoints

### Health Check

**Endpoint:** `GET /health`

Returns server status and available endpoints.

**Example request:**
```bash
curl http://localhost:8080/health
```

**Example response:**
```json
{
  "status": "healthy",
  "endpoints": ["/pix/add", "/iti41/submit"],
  "uptime_seconds": 127.4
}
```

### PIX Add Endpoint

**Endpoint:** `POST /pix/add`

Simulates IHE PIX Add (ITI-8) patient registration transaction.

**Request format:** SOAP 1.2 envelope containing `PRPA_IN201301UV02` message

**Response format:** SOAP acknowledgment (`MCCI_IN000002UV01`)

**Example request:**
```bash
curl -X POST http://localhost:8080/pix/add \
  -H "Content-Type: application/soap+xml" \
  -d @examples/mock-requests/pix-add-request.xml
```

**Example response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.2" extension="ACK-123"/>
      <creationTime value="20250108201500"/>
      <acknowledgement>
        <typeCode code="AA"/>
        <targetMessage>
          <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSGID123"/>
        </targetMessage>
      </acknowledgement>
    </MCCI_IN000002UV01>
  </soap:Body>
</soap:Envelope>
```

**Configuration options:**
- Response delay (0-5000ms)
- Failure rate (0-100%)
- Validation mode (strict vs lenient)

See [Configuration](#configuration) for details.

**Logs:** Requests logged to `mocks/logs/pix-add.log`

### ITI-41 Endpoint

**Endpoint:** `POST /iti41/submit`

Simulates IHE ITI-41 (Provide and Register Document Set-b) transaction with MTOM attachments.

**Request format:** SOAP 1.2 with MTOM multipart encoding

**Response format:** XDSb RegistryResponse with document IDs

**Example request (simplified - full MTOM requires multipart construction):**
```bash
# Note: ITI-41 requires MTOM encoding, which is complex for curl
# See examples/tutorials/05-mock-endpoints.md for Python examples
curl -X POST http://localhost:8080/iti41/submit \
  -H "Content-Type: multipart/related" \
  -H "SOAPAction: urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b" \
  --data-binary @examples/mock-requests/iti41-request-sample.xml
```

**Example response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <RegistryResponse xmlns="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0"
                      status="urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success">
      <RegistryObjectList>
        <ExternalIdentifier id="doc-12345"/>
      </RegistryObjectList>
    </RegistryResponse>
  </soap:Body>
</soap:Envelope>
```

**Configuration options:**
- Response delay
- Failure rate
- Validation mode
- Document saving enabled/disabled
- Custom document IDs

**Logs:** Requests logged to `mocks/logs/iti41-submissions/`

**Saved documents:** If enabled, documents saved to `mocks/data/documents/`

## CLI Commands Reference

The mock server is controlled via CLI commands.

### `mock start`

Start the mock server.

**Syntax:**
```bash
ihe-test-util mock start [OPTIONS]
```

**Options:**
- `--https` - Start in HTTPS mode (default: HTTP)
- `--port <port>` - Custom port (default: 8080 for HTTP, 8443 for HTTPS)
- `--config <file>` - Custom configuration file (default: `mocks/config.json`)
- `--host <host>` - Bind address (default: `localhost`)

**Examples:**
```bash
# Start HTTP server on default port 8080
ihe-test-util mock start

# Start HTTPS server on default port 8443
ihe-test-util mock start --https

# Start on custom port
ihe-test-util mock start --port 9090

# Start with custom configuration
ihe-test-util mock start --config mocks/config-examples/config-unreliable.json

# Start with all options
ihe-test-util mock start --https --port 9443 --config custom-config.json
```

The server runs in the background with PID stored in `mocks/.mock-server.pid`.

### `mock stop`

Stop the running mock server.

**Syntax:**
```bash
ihe-test-util mock stop
```

**Example:**
```bash
ihe-test-util mock stop
# Output: Mock server stopped (PID: 12345)
```

### `mock status`

Check if the mock server is running.

**Syntax:**
```bash
ihe-test-util mock status
```

**Example outputs:**
```bash
# Server running
Mock server is running (PID: 12345) at http://localhost:8080

# Server not running
Mock server is not running
```

### `mock logs`

View recent mock server logs.

**Syntax:**
```bash
ihe-test-util mock logs [OPTIONS]
```

**Options:**
- `--tail <n>` - Show last N lines (default: 50)
- `--follow` - Follow log output (like `tail -f`)

**Examples:**
```bash
# View last 50 lines
ihe-test-util mock logs

# View last 100 lines
ihe-test-util mock logs --tail 100

# Follow logs in real-time
ihe-test-util mock logs --follow
```

## Configuration

The mock server is configured via `mocks/config.json` or environment variables.

### Quick Reference

Common configuration settings:

| Setting | Description | Default |
|---------|-------------|---------|
| `host` | Bind address | `localhost` |
| `port` | Server port | `8080` (HTTP) / `8443` (HTTPS) |
| `log_level` | Logging verbosity | `INFO` |
| `pix_add.response_delay_ms` | PIX Add response delay | `0` |
| `pix_add.failure_rate` | PIX Add failure rate (0-1) | `0.0` |
| `iti41.response_delay_ms` | ITI-41 response delay | `0` |
| `iti41.save_documents` | Save submitted documents | `true` |
| `validation.mode` | Validation strictness | `strict` |

### Configuration Precedence

Configuration is loaded in this order (later overrides earlier):

1. **Default values** (hardcoded in `src/ihe_test_util/mock_server/config.py`)
2. **JSON file** (`mocks/config.json` or `--config <file>`)
3. **Environment variables** (`MOCK_SERVER_PORT`, `MOCK_SERVER_HOST`, etc.)
4. **CLI arguments** (`--port`, `--https`, etc.)

### Example Configurations

Pre-configured examples available in `mocks/config-examples/`:

- **config-default.json** - Standard behavior, suitable for most testing
- **config-network-latency.json** - Simulates slow network (500-2000ms delays)
- **config-unreliable.json** - Random failures (30% failure rate) for error testing
- **config-strict-validation.json** - Strict SOAP validation
- **config-lenient-validation.json** - Relaxed validation for quick testing
- **config-custom-ids.json** - Custom patient ID prefixes

See `mocks/config-examples/README.md` for usage examples.

### Comprehensive Configuration Reference

For complete configuration documentation including all fields and advanced options, see:

📖 **[Mock Server Configuration Guide](./mock-server-configuration.md)**

This guide covers:
- All configuration fields with detailed descriptions
- Validation rules and constraints
- Environment variable mappings
- Hot-reload configuration changes
- Advanced customization scenarios

## HTTP vs HTTPS - When to Use Each

### Use HTTP Mode When:

✅ **Local development** - Fast iteration, no certificate hassles
✅ **CI/CD pipelines** - Simpler setup, faster builds
✅ **Unit/integration testing** - Focus on functionality, not TLS
✅ **Learning IHE workflows** - Reduce complexity while learning

**Benefits:**
- No certificate generation required
- Faster startup
- Simpler curl/requests commands
- No certificate verification warnings

### Use HTTPS Mode When:

✅ **Testing TLS configurations** - Validate certificate handling
✅ **Simulating production-like environments** - Match production setup
✅ **Testing certificate validation logic** - Verify error handling
✅ **End-to-end security testing** - Include encryption in test scenarios

**Requirements:**
- Self-signed certificate generated (`./scripts/generate_cert.sh`)
- Certificate paths configured in `mocks/config.json`
- Clients must skip certificate verification (`curl -k`, `verify=False`)

**Recommendation:** Start with HTTP for development, use HTTPS only when explicitly testing TLS-related features.

## Security Warnings

⚠️ **CRITICAL SECURITY NOTICES - READ CAREFULLY**

### Self-Signed Certificates Are NOT Trusted

The mock server uses self-signed certificates generated by `scripts/generate_cert.sh`. These certificates:
- ❌ Are **NOT** trusted by default by any system or browser
- ❌ Will **FAIL** certificate verification unless explicitly bypassed
- ❌ Should **NEVER** be used in production environments
- ❌ Do **NOT** provide real security guarantees

**To use HTTPS mock endpoints, you MUST disable certificate verification:**

```bash
# curl: Use -k flag
curl -k https://localhost:8443/health

# Python requests: Use verify=False
import requests
response = requests.post("https://localhost:8443/pix/add", data=xml, verify=False)
```

### Testing Only - Not Production Ready

⚠️ **The mock server is for TESTING PURPOSES ONLY. It is NOT suitable for production use.**

**Why not production:**
- No authentication or authorization
- No access control or rate limiting
- Development WSGI server (Werkzeug), not production-grade
- Single-threaded, limited concurrency
- Static responses, no real data persistence
- Verbose logging may expose sensitive test data

### Privacy and Logging

⚠️ **All requests are logged in full, including SOAP bodies.**

If testing with realistic patient data (even synthetic):
- Logs may contain PHI-like information
- Logs are stored unencrypted in `mocks/logs/`
- Secure log files appropriately
- Use obviously fake data (e.g., "John Doe", test IDs)

### Certificate Management

⚠️ **Never use production certificates with the mock server.**

- Generate separate test certificates: `./scripts/generate_cert.sh`
- Keep production certificates separate and secure
- Do not commit private keys to version control (`.gitignore` protects `mocks/certs/*.key`)

### Disabling Certificate Verification Risks

⚠️ **Disabling certificate verification (`curl -k`, `verify=False`) is DANGEROUS in production.**

- Only use for local testing against known mock servers
- Never disable verification for production endpoints
- Exposes you to man-in-the-middle attacks

**Safe approach:**
```python
# Good: Disable verification ONLY for localhost testing
import requests
MOCK_SERVER = "https://localhost:8443"
if "localhost" in MOCK_SERVER:
    verify = False  # Safe: Testing against local mock
else:
    verify = True   # Production: Always verify certificates
```

## Integration with Main Utility

The mock server is designed to work seamlessly with the main IHE Test Utility commands.

### Basic Workflow

**Terminal 1: Start mock server**
```bash
ihe-test-util mock start
# Mock server running at http://localhost:8080
```

**Terminal 2: Run utility commands**
```bash
# Configure utility to use mock endpoints
export PIX_ADD_ENDPOINT="http://localhost:8080/pix/add"
export ITI41_ENDPOINT="http://localhost:8080/iti41/submit"

# Test PIX Add registration
ihe-test-util pix-add register --csv examples/patients_sample.csv

# Test ITI-41 submission
ihe-test-util submit --csv examples/patients_sample.csv --template templates/ccd-template.xml
```

### Complete Workflow Example

**Full CSV → PIX Add → ITI-41 workflow using mocks:**

```bash
# Terminal 1: Start mock server
ihe-test-util mock start

# Terminal 2: Run complete workflow
# Step 1: Validate CSV
ihe-test-util csv validate examples/patients_sample.csv

# Step 2: Register patients via PIX Add (mock)
ihe-test-util pix-add register \
  --csv examples/patients_sample.csv \
  --endpoint http://localhost:8080/pix/add

# Step 3: Submit CCD documents via ITI-41 (mock)
ihe-test-util submit \
  --csv examples/patients_sample.csv \
  --template templates/ccd-template.xml \
  --endpoint http://localhost:8080/iti41/submit

# Step 4: Check mock server logs
ihe-test-util mock logs

# Step 5: Verify saved documents
ls -l mocks/data/documents/
```

**Expected output:**
- PIX Add: Acknowledgments logged in `mocks/logs/pix-add.log`
- ITI-41: Submissions logged in `mocks/logs/iti41-submissions/`
- Documents: Saved to `mocks/data/documents/patient-*.xml`

### Benefits of Using Mocks During Development

✅ **No external dependencies** - Work offline, no VPN required
✅ **Fast feedback** - No network latency, instant responses
✅ **Repeatable** - Same behavior every test run
✅ **Configurable** - Test error scenarios easily
✅ **Privacy** - No real PHI sent to external systems
✅ **Cost** - No test system costs or quotas

### Verifying Requests in Logs

After running commands against mock endpoints, verify requests were received:

```bash
# View PIX Add requests
cat mocks/logs/pix-add.log

# View ITI-41 submissions
ls mocks/logs/iti41-submissions/

# View saved documents
ls mocks/data/documents/

# Follow logs in real-time
ihe-test-util mock logs --follow
```

For complete tutorial with step-by-step examples, see:

📖 **[Tutorial: Using Mock Endpoints](../examples/tutorials/05-mock-endpoints.md)**

## CI/CD Integration

The mock server is ideal for CI/CD pipelines, providing reliable test endpoints without external dependencies.

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install -r requirements-dev.txt

      - name: Start Mock Server
        run: |
          ihe-test-util mock start --port 8080 &
          sleep 2
          # Wait for server to be healthy
          curl --retry 5 --retry-delay 1 http://localhost:8080/health

      - name: Run Integration Tests
        run: |
          pytest tests/integration/
        env:
          PIX_ADD_ENDPOINT: http://localhost:8080/pix/add
          ITI41_ENDPOINT: http://localhost:8080/iti41/submit

      - name: Collect Mock Server Logs
        if: always()
        run: |
          mkdir -p test-artifacts
          cp -r mocks/logs/ test-artifacts/mock-logs/

      - name: Upload Artifacts
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: mock-server-logs
          path: test-artifacts/

      - name: Stop Mock Server
        if: always()
        run: ihe-test-util mock stop
```

### Key CI/CD Patterns

**1. Background Mode with Health Check**
```bash
# Start server in background
ihe-test-util mock start &

# Wait for server to be ready
sleep 2
curl --retry 5 --retry-delay 1 http://localhost:8080/health
```

**2. Environment Variable Configuration**
```bash
export PIX_ADD_ENDPOINT="http://localhost:8080/pix/add"
export ITI41_ENDPOINT="http://localhost:8080/iti41/submit"
pytest tests/integration/
```

**3. Log Collection for Debugging**
```bash
# Always collect logs, even on failure
if: always()
  cp -r mocks/logs/ ci-artifacts/
```

**4. Cleanup After Tests**
```bash
# Ensure server stops even if tests fail
if: always()
  ihe-test-util mock stop
```

### Why Mocks Are Better Than External Test Endpoints in CI

✅ **Reliability** - No external system downtime or network issues
✅ **Speed** - No network latency, faster build times
✅ **Consistency** - Same behavior every run, no flaky tests
✅ **Isolation** - No shared state between CI runs
✅ **Cost** - No external system costs or rate limits
✅ **Offline** - Works without internet access (self-hosted runners)

## Performance Considerations

### Response Delay Simulation

The mock server can simulate network latency for realistic testing:

```json
{
  "pix_add": {
    "response_delay_ms": 500
  },
  "iti41": {
    "response_delay_ms": 2000
  }
}
```

**Use cases:**
- Test timeout handling
- Simulate slow networks
- Verify progress indicators

**Range:** 0-5000ms (0-5 seconds)

### Failure Rate Simulation

Simulate unreliable networks for error testing:

```json
{
  "pix_add": {
    "failure_rate": 0.3
  }
}
```

**Use cases:**
- Test retry logic
- Verify error handling
- Simulate intermittent failures

**Range:** 0.0-1.0 (0% to 100%)

### Throughput Limitations

⚠️ **The mock server is NOT designed for load testing.**

**Limitations:**
- **Single-threaded** - Werkzeug development server
- **No connection pooling** - One request at a time
- **File I/O overhead** - Document saving impacts throughput
- **Logging overhead** - Full request/response logging

**Typical performance:**
- ~10-50 requests/second for simple PIX Add
- ~5-20 requests/second for ITI-41 with document saving
- Performance degrades with verbose logging

**For load testing, use production-grade WSGI server (gunicorn, uwsgi) - NOT SUPPORTED YET.**

### Suitable Use Cases

✅ **Functional testing** - Verify correct behavior
✅ **Integration testing** - Test component interactions
✅ **Error scenario testing** - Test failure handling
✅ **Development** - Fast iteration during coding

❌ **NOT suitable for:**
- Load testing / stress testing
- Performance benchmarking
- High-concurrency scenarios
- Production use

## Limitations

Understanding the mock server's limitations helps set appropriate expectations.

### Architecture Limitations

1. **Development Server (Werkzeug)**
   - Single-threaded, limited concurrency
   - Not suitable for production traffic
   - No multi-process support

2. **No Persistent Storage**
   - In-memory only (except document files)
   - Restart clears all state
   - No database or persistent patient registry

3. **Static Responses**
   - Acknowledgments are static (always success, unless failure rate configured)
   - Response content doesn't vary based on patient data
   - Document IDs are generated, not semantically meaningful

### Validation Limitations

1. **Basic SOAP Structure Validation**
   - Validates SOAP envelope structure
   - Does NOT perform deep HL7v3 semantic validation
   - Does NOT validate OIDs, codes, or vocabularies

2. **MTOM Handling**
   - Validates MTOM multipart structure
   - Extracts attachments
   - Does NOT parse or validate CCD content deeply

3. **No Business Logic**
   - Does NOT check for duplicate patient IDs
   - Does NOT validate referential integrity
   - Does NOT enforce real-world constraints

### Security Limitations

1. **No Authentication**
   - No username/password
   - No API keys
   - No OAuth/SAML

2. **No Authorization**
   - No role-based access control
   - No endpoint-level permissions
   - All requests accepted (unless validation fails)

3. **No Rate Limiting**
   - No protection against abuse
   - No request throttling

### What This Means

The mock server is a **simulation tool for testing**, not a real IHE endpoint implementation.

✅ **Good for:** Learning, development, CI/CD, error testing
❌ **Not good for:** Production, security testing, compliance validation

For production testing, use real IHE-compliant test systems.

## Troubleshooting

Common issues and solutions:

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **Port already in use** | `OSError: [Errno 48] Address already in use` | **Option 1:** Use different port: `ihe-test-util mock start --port 9090`<br>**Option 2:** Kill process using port:<br>`lsof -ti:8080 \| xargs kill` (macOS/Linux)<br>`netstat -ano \| findstr :8080` (Windows) |
| **Server won't start** | No output, no error message | Check logs: `cat mocks/logs/mock-server.log`<br>Verify configuration: `cat mocks/config.json`<br>Check permissions on `mocks/` directory |
| **HTTPS certificate error** | `SSL: CERTIFICATE_VERIFY_FAILED` | **curl:** Use `-k` flag: `curl -k https://...`<br>**Python:** Use `verify=False`: `requests.post(..., verify=False)`<br>**Note:** Only for testing! See [Security Warnings](#security-warnings) |
| **SOAP fault responses** | HTTP 500, SOAP fault in response | **Check request XML syntax** - Validate with lxml<br>**Try lenient mode** - `config-lenient-validation.json`<br>**Check logs** - `mocks/logs/pix-add.log` for details<br>**Verify SOAP namespace** - Must use SOAP 1.2 |
| **Config validation error** | Startup fails with Pydantic ValidationError | **Fix JSON syntax** - Check for trailing commas, quotes<br>**Check field types** - Numbers must be numeric, not strings<br>**Check ranges** - `failure_rate` must be 0.0-1.0, delays 0-5000<br>**See:** [Configuration Reference](./mock-server-configuration.md) |
| **Connection refused** | `ConnectionRefusedError: [Errno 61] Connection refused` | **Verify server is running:** `ihe-test-util mock status`<br>**Check port:** Default is 8080 (HTTP) or 8443 (HTTPS)<br>**Check host:** Default is `localhost`, not `0.0.0.0` |
| **Health check fails** | `/health` returns 500 or timeout | **Check configuration** - Invalid config can crash endpoints<br>**Check logs** - `mocks/logs/mock-server.log`<br>**Restart server** - `ihe-test-util mock stop && ihe-test-util mock start` |
| **Documents not saving** | ITI-41 succeeds but no files in `mocks/data/documents/` | **Check config** - `iti41.save_documents` must be `true`<br>**Check permissions** - `mocks/data/documents/` must be writable<br>**Check logs** - May contain file I/O errors |
| **Logs not showing requests** | Logs empty or missing requests | **Check log level** - Set `log_level: "DEBUG"` in config<br>**Check file permissions** - `mocks/logs/` must be writable<br>**Verify correct log file** - PIX Add uses `pix-add.log`, ITI-41 uses `iti41-submissions/` |

### Enabling Debug Logging

For detailed troubleshooting, enable debug logging:

**Option 1: Configuration file**
```json
{
  "log_level": "DEBUG"
}
```

**Option 2: Environment variable**
```bash
export MOCK_SERVER_LOG_LEVEL=DEBUG
ihe-test-util mock start
```

Debug logs include:
- Full request headers
- Full request bodies
- Validation steps
- Configuration loading
- File I/O operations

### Getting Help

If troubleshooting doesn't resolve your issue:

1. **Check logs** - `mocks/logs/mock-server.log` contains detailed errors
2. **Enable debug logging** - See above
3. **Verify configuration** - Compare against `mocks/config-examples/config-default.json`
4. **Check example requests** - Use provided examples in `examples/mock-requests/`
5. **Review documentation** - [Configuration Guide](./mock-server-configuration.md)

## See Also

**Related Documentation:**
- **[Mock Server Configuration Guide](./mock-server-configuration.md)** - Comprehensive configuration reference
- **[Tutorial: Using Mock Endpoints](../examples/tutorials/05-mock-endpoints.md)** - Step-by-step tutorial
- **[Configuration Guide](./configuration-guide.md)** - Main utility configuration
- **[Logging Guide](./logging-guide.md)** - Logging and audit trails

**Example Files:**
- **Example Configurations:** `mocks/config-examples/`
- **Example SOAP Requests:** `examples/mock-requests/`
- **Example Patient Data:** `examples/patients_sample.csv`

**Source Code (for advanced customization):**
- **Mock Server Application:** `src/ihe_test_util/mock_server/app.py`
- **PIX Add Endpoint:** `src/ihe_test_util/mock_server/pix_add_endpoint.py`
- **ITI-41 Endpoint:** `src/ihe_test_util/mock_server/iti41_endpoint.py`
- **CLI Commands:** `src/ihe_test_util/cli/mock_commands.py`
