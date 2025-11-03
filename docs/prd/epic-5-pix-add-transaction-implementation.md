# Epic 5: PIX Add Transaction Implementation

**Epic Goal:** Build HL7v3 PRPA_IN201301UV02 message construction and SOAP-based submission to PIX Add endpoints with acknowledgment parsing and logging. This epic delivers the first complete IHE transaction workflow, enabling patient registration.

### Story 5.1: HL7v3 Message Builder Foundation

**As a** developer,
**I want** to build HL7v3 message structures programmatically,
**so that** I can construct valid PIX Add messages.

**Acceptance Criteria:**

1. Message builder creates HL7v3 XML structure with proper namespaces
2. Support for HL7v3 PRPA_IN201301UV02 message type
3. Required elements populated: message ID, creation time, sender, receiver
4. Patient identifier construction with root OID and extension
5. Patient demographics mapped from parsed CSV data
6. Administrative gender coded values (M, F, O, U) mapped to HL7 codes
7. Birth time formatted in HL7 TS format (YYYYMMDDHHmmss)
8. Message control ID generation (unique per message)
9. XML output properly formatted and indented for readability
10. Unit tests verify message structure, required elements, HL7 conformance

### Story 5.2: PIX Add SOAP Client

**As a** developer,
**I want** a SOAP client for PIX Add transactions,
**so that** I can submit patient registration messages to IHE endpoints.

**Acceptance Criteria:**

1. SOAP client implementation using `zeep` library
2. PIX Add endpoint URL configurable via configuration file
3. HTTP and HTTPS transport support with TLS 1.2+ enforcement
4. Security warning displayed when HTTP transport used
5. WS-Addressing headers included in SOAP envelope (Action, MessageID, To)
6. Signed SAML assertion embedded in WS-Security header
7. Complete SOAP request logged to audit file before transmission
8. Request timeout configurable (default 30 seconds)
9. Network error handling with retry logic (configurable retries, default 3)
10. Unit tests with mock SOAP server verify client behavior

### Story 5.3: PIX Add Acknowledgment Parsing

**As a** developer,
**I want** to parse PIX Add acknowledgment responses,
**so that** I can determine transaction success and extract patient identifiers.

**Acceptance Criteria:**

1. Acknowledgment parser handles HL7v3 MCCI_IN000002UV01 response messages
2. Response validation checks for proper HL7v3 structure and namespaces
3. Acknowledgment status extracted: success (AA), error (AE), rejected (AR)
4. Patient identifiers extracted from acknowledgment when present
5. Error messages and details extracted for failed transactions
6. Query continuation information extracted if present
7. Response correlation with request via message ID
8. Parsed response data returned as structured dictionary
9. Full SOAP response logged to audit file after reception
10. Unit tests verify parsing success, error, and malformed responses

### Story 5.4: PIX Add Workflow Integration

**As a** healthcare integration developer,
**I want** end-to-end PIX Add workflow from CSV to acknowledgment,
**so that** I can register patients with a single command.

**Acceptance Criteria:**

1. Workflow orchestrates: CSV parsing → HL7v3 message building → SAML signing → SOAP submission → acknowledgment parsing
2. Sequential processing for multiple patients (per technical requirements)
3. Success/failure status tracked per patient with detailed logging
4. Patient registration summary displayed: total patients, successful, failed
5. Failed registrations include error details and suggested remediation
6. Registered patient identifiers saved to output file for downstream use
7. Workflow halts on critical errors (endpoint unreachable, certificate invalid)
8. Non-critical errors (single patient failure) continue processing remaining patients
9. Comprehensive audit log captures complete workflow execution
10. Integration test verifies complete workflow against mock PIX Add endpoint

### Story 5.5: PIX Add Error Handling & Resilience

**As a** developer,
**I want** robust error handling for PIX Add transactions,
**so that** transient failures don't halt batch processing.

**Acceptance Criteria:**

1. Network errors trigger configurable retry logic with exponential backoff
2. SOAP faults parsed and logged with detailed error information
3. HL7 application-level errors (AE, AR status) handled gracefully
4. Certificate errors (expired, invalid) halt processing with clear guidance
5. Endpoint unreachable errors suggest troubleshooting steps
6. Malformed response errors logged with raw response for debugging
7. Timeout errors include timing information and retry status
8. Error categorization: transient (retry), permanent (skip), critical (halt)
9. Error summary report shows categories and frequencies
10. Unit tests simulate various error scenarios and verify handling

### Story 5.6: PIX Add CLI Commands

**As a** healthcare integration developer,
**I want** CLI commands for PIX Add operations,
**so that** I can register patients from the terminal.

**Acceptance Criteria:**

1. CLI command `pix-add register <csv>` registers patients from CSV file
2. Option `--endpoint <url>` specifies PIX Add endpoint (overrides config)
3. Option `--cert <path>` specifies certificate for SAML signing
4. Option `--http` enables HTTP transport (with security warning)
5. Option `--output <file>` saves registration results to JSON file
6. Real-time status display shows progress through patient list
7. Color-coded output: green (success), red (failed), yellow (warning)
8. Summary report displays success rate and error breakdown
9. Option `--dry-run` validates without actually submitting
10. Detailed help documentation with usage examples
