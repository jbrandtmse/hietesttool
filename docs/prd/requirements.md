# Requirements

### Functional

**FR1**: System shall parse CSV files containing patient demographics (name, DOB, gender, identifiers) and validate required fields with clear error messages for malformed data

**FR2**: System shall auto-generate unique patient IDs when not provided in CSV input

**FR3**: System shall accept user-provided HL7 CCDA/XDSb XML template documents and perform simple string replacement for patient-specific data (names, IDs, dates, OIDs)

**FR4**: System shall generate personalized CCD documents for multiple patients in batch mode

**FR5**: System shall construct HL7v3 PRPA_IN201301UV02 patient registration messages and submit to IHE PIX Add endpoints via SOAP

**FR6**: System shall parse and log PIX Add acknowledgment and error responses

**FR7**: System shall construct SOAP-based ITI-41 (Provide and Register Document Set-b) transactions encapsulating personalized CCDs with proper XDSb metadata

**FR8**: System shall use MTOM (MIME attachment) for all ITI-41 document submissions

**FR9**: System shall support two SAML approaches: (1) user-provided SAML XML templates with runtime value substitution, or (2) programmatic generation of SAML 2.0 assertions

**FR10**: System shall sign SAML assertions with X.509 certificates using XML Signature standards and embed in WS-Security SOAP headers

**FR11**: System shall support HTTP and HTTPS transport configuration via CLI flag or configuration file

**FR12**: System shall display security warnings when HTTP transport is selected

**FR13**: System shall support TLS verification disable for testing environments

**FR14**: System shall provide CLI interface for batch processing with flags for input files, endpoints, certificates, and transport mode

**FR15**: System shall display real-time processing status during batch operations

**FR16**: System shall log full SOAP request/response payloads to local files with timestamps

**FR17**: System shall track batch processing progress with success/failure counts per patient

**FR18**: System shall provide detailed error messages with troubleshooting guidance for transaction failures

**FR19**: System shall include mock PIX Add endpoint that responds with static acknowledgments containing pre-defined identifiers

**FR20**: System shall include mock ITI-41 endpoint that performs simple validation and returns static acknowledgments

**FR21**: System shall support HTTP and HTTPS for mock endpoints with configurable certificates

**FR22**: System shall process PIX Add transactions sequentially before ITI-41 submissions (PIX Add must complete successfully first)

### Non Functional

**NFR1**: System shall process 100 patient records through PIX Add and ITI-41 in under 5 minutes (assuming adequate network performance)

**NFR2**: Individual transaction latency shall be under 3 seconds excluding network time

**NFR3**: Mock endpoints shall support 10+ simultaneous connections

**NFR4**: System shall use memory-efficient streaming for large document processing

**NFR5**: System shall run on Python 3.10+ across Windows, macOS, and Linux platforms

**NFR6**: System shall operate in standard Python virtual environment without requiring Docker or containerization

**NFR7**: System shall support X.509 certificates in PEM, PKCS12, and DER formats (prioritized in that order)

**NFR8**: System shall enforce TLS 1.2+ when using HTTPS transport

**NFR9**: System shall use XML canonicalization to prevent XML wrapping attacks

**NFR10**: System shall verify SAML signature validity and timestamp freshness

**NFR11**: System shall maintain comprehensive audit logs for compliance purposes

**NFR12**: System shall provide exit codes and structured output suitable for CI/CD integration

**NFR13**: System shall achieve 80%+ unit test coverage

**NFR14**: System shall include integration tests for all IHE transactions
