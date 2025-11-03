# Epic 6: ITI-41 Document Submission & Complete Workflow

**Epic Goal:** Implement ITI-41 Provide and Register Document Set-b transaction with MTOM support, XDSb metadata, and integration with PIX Add to deliver complete end-to-end patient submission workflow with batch processing capabilities.

### Story 6.1: XDSb Metadata Construction

**As a** developer,
**I want** to construct XDSb metadata for document submissions,
**so that** I can create valid ITI-41 transactions.

**Acceptance Criteria:**

1. Metadata builder creates ProvideAndRegisterDocumentSetRequest structure
2. Submission set metadata with unique ID, timestamp, source ID
3. Document entry metadata with unique ID, MIME type, hash, size
4. Patient identifier mapping from PIX Add registration results
5. Document classification codes (classCode, typeCode, formatCode) configurable
6. Author information populated from configuration or defaults
7. Metadata associations between submission set and document entries
8. XDSb slot elements for custom metadata attributes
9. Unique IDs generated using UUID or OID-based schemes
10. Unit tests verify metadata structure, required elements, XDSb conformance

### Story 6.2: MTOM Attachment Handling

**As a** developer,
**I want** to attach CCD documents using MTOM,
**so that** I can submit large documents efficiently.

**Acceptance Criteria:**

1. MTOM attachment creation for CCD XML documents
2. Content-ID generation and reference in metadata
3. Base64 encoding applied for binary transport
4. Document hash (SHA256) calculation for integrity verification
5. Document size calculation and inclusion in metadata
6. Multiple document support for future extensibility
7. MTOM packaging with proper MIME multipart boundaries
8. Memory-efficient streaming for large documents (per NFR4)
9. MTOM structure validation before transmission
10. Unit tests verify MTOM packaging, hash calculation, size accuracy

### Story 6.3: ITI-41 SOAP Client Implementation

**As a** developer,
**I want** a SOAP client for ITI-41 transactions,
**so that** I can submit documents to XDSb repositories.

**Acceptance Criteria:**

1. SOAP client implementation using `zeep` with MTOM plugin
2. ITI-41 endpoint URL configurable via configuration file
3. HTTP and HTTPS transport support with TLS 1.2+ enforcement
4. WS-Addressing headers included (Action, MessageID, To, ReplyTo)
5. Signed SAML assertion embedded in WS-Security header
6. Complete SOAP request with MTOM attachment logged to audit file
7. Request timeout configurable (default 60 seconds for large documents)
8. Network error handling with retry logic for transient failures
9. Response correlation with request via message ID
10. Integration test submits CCD to mock ITI-41 endpoint

### Story 6.4: Registry Response Parsing

**As a** developer,
**I want** to parse ITI-41 registry responses,
**so that** I can determine submission success and extract document identifiers.

**Acceptance Criteria:**

1. Response parser handles RegistryResponse from XDSb repository
2. Response status extraction: Success, Failure, PartialSuccess
3. Document unique IDs extracted from successful submissions
4. Error list parsed for failed or partial success responses
5. Error codes and context information extracted and logged
6. Submission set unique ID extracted from response
7. Response correlation with request via submission set ID
8. Structured response data returned for downstream processing
9. Full SOAP response logged to audit file
10. Unit tests verify parsing success, failure, and partial success responses

### Story 6.5: PIX Add + ITI-41 Integration Workflow

**As a** healthcare integration developer,
**I want** complete workflow from CSV to document submission,
**so that** I can create and submit test patients with one command.

**Acceptance Criteria:**

1. Workflow orchestrates: CSV → CCD generation → PIX Add → ITI-41 submission
2. PIX Add must complete successfully before ITI-41 (per FR22)
3. Patient identifiers from PIX Add acknowledgment used in ITI-41 metadata
4. Sequential processing maintains patient registration order
5. Per-patient workflow status tracking: CSV parsed, CCD generated, PIX Add success, ITI-41 success
6. Failed PIX Add registration skips ITI-41 for that patient
7. Complete workflow results saved to JSON output file
8. Summary report shows pipeline metrics: patients processed, PIX Add success rate, ITI-41 success rate
9. Workflow audit log captures all operations with timing information
10. End-to-end integration test verifies complete workflow against mock endpoints

### Story 6.6: Batch Processing & Configuration Management

**As a** QA engineer,
**I want** batch processing with comprehensive configuration,
**so that** I can efficiently test large patient datasets.

**Acceptance Criteria:**

1. Batch mode processes entire CSV file without manual intervention
2. Configuration file consolidates all settings: endpoints, certificates, templates, transport
3. Environment variable overrides for sensitive values (per technical requirements)
4. Processing checkpoint/resume capability for very large batches
5. Concurrent connection limit to mock endpoints (respects NFR3: 10+ connections)
6. Configurable logging verbosity per operation type
7. Batch processing statistics: throughput, average latency, error rates
8. Output directory organization: logs/, documents/, results/, audit/
9. Batch configuration templates for common scenarios (development, testing, staging)
10. Documentation covers batch processing best practices and performance tuning

### Story 6.7: Complete Workflow CLI

**As a** healthcare integration developer,
**I want** a single CLI command for complete patient submission,
**so that** I can execute end-to-end workflow easily.

**Acceptance Criteria:**

1. CLI command `submit <csv>` executes complete workflow (PIX Add + ITI-41)
2. Option `--ccd-template <file>` specifies CCD template to use
3. Option `--config <file>` loads complete workflow configuration
4. Option `--pix-only` executes only PIX Add registration
5. Option `--iti41-only` executes only ITI-41 (requires prior PIX Add results)
6. Real-time progress display with patient count and success rates
7. Color-coded status output with detailed error reporting
8. Option `--output <dir>` specifies output directory for all artifacts
9. Final summary report with breakdown by workflow stage
10. Comprehensive help documentation with examples for all scenarios
