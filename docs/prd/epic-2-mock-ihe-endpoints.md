# Epic 2: Mock IHE Endpoints

**Epic Goal:** Create Flask-based mock PIX Add and ITI-41 endpoints with HTTP/HTTPS support, enabling isolated testing and development without external dependencies. This epic delivers critical infrastructure that allows developers to test IHE transactions locally, accelerating development velocity and reducing dependency on external test environments.

### Story 2.1: Flask Mock Server Foundation

**As a** developer,
**I want** a Flask-based mock server framework with HTTP/HTTPS support,
**so that** I can simulate IHE endpoints locally for testing.

**Acceptance Criteria:**

1. Flask application created in `mocks/` directory with modular structure
2. Server supports both HTTP and HTTPS with configurable port (defaults: HTTP 8080, HTTPS 8443)
3. Self-signed certificate generation script provided for HTTPS testing
4. Server configuration loaded from JSON file or environment variables
5. Health check endpoint (`/health`) returns server status and configuration summary
6. Request logging captures all incoming SOAP requests with timestamps
7. Response headers include appropriate SOAP/XML content-type
8. Server handles graceful shutdown with cleanup
9. Error handling returns proper SOAP fault messages for malformed requests
10. Unit tests verify HTTP/HTTPS operation, configuration loading, health check

### Story 2.2: Mock PIX Add Endpoint Implementation

**As a** developer,
**I want** a mock PIX Add endpoint that simulates patient registration,
**so that** I can test PIX Add transaction logic without external dependencies.

**Acceptance Criteria:**

1. Endpoint implements `/pix/add` route accepting SOAP requests
2. Validates incoming SOAP envelope structure (basic validation, not deep semantic)
3. Extracts patient identifiers and demographics from HL7v3 PRPA_IN201301UV02 messages
4. Returns static acknowledgment (MCCI_IN000002UV01) with pre-configured patient ID in response
5. Acknowledgment contains success status code and echoes back patient identifiers
6. Invalid SOAP structure returns SOAP fault with error description
7. Request/response pairs logged to `mocks/logs/pix-add.log` with timestamps
8. Configurable response delays simulate network latency (default 0ms, max 5000ms)
9. Response includes correlation IDs for request tracking
10. Unit and integration tests verify SOAP handling, validation, acknowledgments

### Story 2.3: Mock ITI-41 Endpoint Implementation

**As a** developer,
**I want** a mock ITI-41 endpoint that simulates document submission,
**so that** I can test document submission logic without external XDSb repositories.

**Acceptance Criteria:**

1. Endpoint implements `/iti41/submit` route accepting SOAP with MTOM
2. Validates incoming SOAP envelope and MTOM attachment structure
3. Extracts document metadata from XDSb Provide and Register transaction
4. Validates presence of CCD document in MTOM attachment
5. Returns static Registry Response with success status and document unique ID
6. Response includes submission set unique ID and document entry unique IDs
7. Invalid structure or missing attachments return appropriate SOAP faults
8. Documents and metadata logged to `mocks/logs/iti41-submissions/` directory
9. Submitted documents optionally saved to `mocks/data/documents/` for inspection
10. Unit and integration tests verify MTOM handling, metadata extraction, responses

### Story 2.4: Mock Server CLI Commands

**As a** developer,
**I want** CLI commands to manage mock servers,
**so that** I can easily start/stop/configure mock endpoints during testing.

**Acceptance Criteria:**

1. CLI command `mock start` launches mock server (HTTP by default)
2. Option `--https` enables HTTPS mode with certificate configuration
3. Option `--port <port>` specifies custom port (default 8080 for HTTP, 8443 for HTTPS)
4. Option `--config <file>` loads custom mock server configuration
5. Command `mock stop` gracefully shuts down running mock server
6. Command `mock status` displays running status, endpoints, port, protocol
7. Command `mock logs` displays recent mock server logs with filtering options
8. Server runs in background with PID file for management
9. Clear console output shows server URL, available endpoints, and status
10. Help documentation includes usage examples for common scenarios

### Story 2.5: Mock Endpoint Configuration & Customization

**As a** QA engineer,
**I want** to customize mock endpoint responses and behavior,
**so that** I can test various scenarios including failures and edge cases.

**Acceptance Criteria:**

1. Configuration file (`mocks/config.json`) defines response templates and behavior
2. Configurable response delay per endpoint (simulate network latency)
3. Configurable success/failure rates (e.g., 10% failure rate for testing error handling)
4. Custom SOAP fault messages for different error scenarios
5. Pre-defined patient IDs and document IDs used in acknowledgments
6. Toggle for strict vs. lenient validation modes
7. Configuration hot-reload without server restart
8. Example configurations provided for common test scenarios
9. Configuration validation on load with clear error messages
10. Documentation explains all configuration options with examples

### Story 2.6: Mock Server Documentation & Examples

**As a** new user,
**I want** comprehensive mock server documentation,
**so that** I can quickly set up local testing environments.

**Acceptance Criteria:**

1. Mock server documentation created in `docs/mock-servers.md`
2. Quick start guide with step-by-step server setup and basic usage
3. Example SOAP requests for PIX Add and ITI-41 included in `examples/`
4. Troubleshooting guide for common issues (port conflicts, certificate errors)
5. Documentation covers HTTP vs HTTPS setup and when to use each
6. Configuration reference documents all options with defaults
7. Examples show integration with main utility CLI commands
8. Security warnings about using self-signed certificates
9. Guide for running mock servers in CI/CD pipelines
10. Performance considerations and limitations documented
