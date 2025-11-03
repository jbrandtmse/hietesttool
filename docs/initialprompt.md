# PROJECT BRIEF: Python Utility for IHE Test Patient Creation and CCD Submission

## Executive Summary

This project develops a lightweight, standalone Python utility for automated creation of test patient data and associated Continuity of Care Documents (CCD) based on demographics provided in CSV files. The utility submits patient registrations and CCD documents securely to IHE endpoints—including PIX Add for patient registration and ITI-41 XDSb for document submission—via signed, SOAP-based HTTP(S) calls, with optional submission over plain HTTP. The tool supports flexible template-based CCD and SAML assertion personalization, supports query & retrieval workflows, and runs locally in a Python virtual environment.

---

## Project Objectives

- Parse CSV demographic data and generate test patient profiles.
- Accept user-provided template CCD/XDSb XML documents and personalize identifiers and demographics.
- Implement IHE PIX Add (Patient Identity Feed) transactions to register patients.
- Generate ITI-41 Provide and Register Document Set-b submissions with personalized CCDs.
- Support digitally signed SAML assertions embedded in SOAP headers; accept either templated or dynamically generated SAML.
- Provide option to submit transactions over HTTP or HTTPS.
- Support PIX Query or XCPD queries and ITI-18 document queries with single-document ITI-43 retrieval in Phase Two.
- Provide robust error handling, transaction logging, and audit trails.
- Operate locally without containerization, runnable in a Python virtual environment.
- Develop mock endpoints to enable comprehensive, isolated testing of all IHE transactions.

---

## Functional Requirements

### F1. CSV Patient Data Import

- Use Python `pandas` or built-in `csv` to ingest and validate demographic data.
- Automatically generate unique patient identifiers if needed.

### F2. Template-Based CCD Document Personalization

- Accept a base XML template document for ITI-41 submissions.
- Substitute placeholders with patient-specific data (names, IDs, birth dates, OIDs).
- Maintain valid HL7 CCDA/XDSb XML structure and validate output.
- Support iterative generation for batch patient processing.

### F3. PIX Add Transaction Implementation

- Implement HL7v3 PIX Add `PRPA_IN201301UV02` patient registration messages.
- Use Python SOAP client (e.g., `zeep`) to construct and submit Patient Identity Feed transactions.
- Process acknowledgment and error responses.

### F4. ITI-41 Document Submission

- Build SOAP Provide and Register Document Set-b transactions encapsulating personalized CCDs.
- Support MTOM for large document submission.
- Use TLS-secured HTTP or optionally plain HTTP transport.

### F5. Flexible SAML Assertion Handling

- Allow users to provide a SAML XML template with runtime value substitution and optional signing.
- Alternatively, dynamically generate standard-compliant SAML 2.0 assertions programmatically.
- Sign assertions with X.509 certificates using XML Signature standards.
- Embed SAML assertions in WS-Security SOAP headers.

### F6. Transport Protocol Flexibility

- Allow configuration or CLI flag to specify HTTP or HTTPS submission.
- Warn users about security implications when using HTTP.
- Support disabling TLS verification when necessary for testing.

### F7. Robust CLI and Logging Support

- Command-line interface for configuration, batch processing, and reporting.
- Log full inbound/outbound SOAP transactions and errors to local files.
- Track batch progress and summarize successes and failures.

### F8. Mock Endpoint Infrastructure (Testing)

- Develop mock servers replicating PIX Add, PIX Query/XCPD, ITI-41, ITI-18, and ITI-43 endpoints.
- Support HTTP and HTTPS bindings with configurable certificates.
- Validate incoming SOAP requests and SAML assertions.
- Provide configurable success and failure responses for comprehensive testing.
- Enable CI/CD integration with automated tests against mocks.

---

## Phase Two: IHE Query and Document Retrieve Enhancements

- Implement PIX Query (ITI-45) and/or Cross-Community Patient Discovery (XCPD, ITI-55) to retrieve patient identifiers.
- Use retrieved identifiers to perform ITI-18 Document Queries to obtain document metadata.
- Perform ITI-43 Retrieve Document Set operations **one document at a time** to download full patient documents.
- Support chained query and retrieve workflows with detailed progress and error reporting.

---

## Technology Stack

| Layer                  | Technology               | Justification                                           |
|------------------------|--------------------------|--------------------------------------------------------|
| Language & Runtime      | Python 3.10+             | Popular, powerful scripting language                    |
| CSV Processing          | `pandas` / `csv`         | Robust data transformation and validation              |
| XML Processing          | `lxml`, `jinja2` (optional) | Flexible XML parsing and templating                     |
| SOAP Client            | `zeep`                   | Mature SOAP client with WS-Addressing support           |
| SAML Assertion & Signing| `python-saml`, `python-xmlsec` | Standards-compliant SAML generation and XML signing     |
| HTTP Transport         | `requests`               | Reliable HTTP/HTTPS communication with TLS and HTTP options |
| CLI Framework          | `argparse` / `click`     | User-friendly command line interface                     |
| Logging                | Python `logging`         | Standardized logging to files                            |
| Mock Servers           | `Flask` or `FastAPI`     | Lightweight HTTP server to simulate IHE endpoints       |

---

## Architecture Overview

- Modular CLI-driven Python application.
- Input layer reads CSVs and optional CCD/SAML templates.
- Data mapping layer personalizes documents and assertions.
- IHE transaction layer builds PIX Add, ITI-41, ITI-45/XCPD, ITI-18 queries, and ITI-43 retrieves.
- Transport layer sends messages securely or unsecurely based on configuration.
- Output layer logs detailed transaction info and supports audit.
- Mock environment to validate all transaction types in isolation.

---

## Security Considerations

- Secure storage of certificates and keys; use environment variables or OS vaults.
- XML canonicalization and signature to prevent XML wrapping attacks.
- TLS 1.2+ enforcement when HTTPS is used; option to disable TLS verification for testing.
- Inform users of security risks when submitting over plain HTTP.

---

## Testing Strategy

- Unit test CSV parsing, template substitution, and validation.
- Integration tests with mock endpoints covering submission, query, retrieve, and SAML verification.
- End-to-end manual tests via public NIST IHE test beds.
- Security tests validating XML signature and TLS enforcement.
- Batch processing test with large CSV input files.

---

## Success Metrics

- Reliable patient record creation and registration via PIX Add.
- Accurate CCDA document personalization and ITI-41 submission.
- Proper embedding and signing of SAML assertions (template or generated).
- Flexible HTTP/HTTPS transport option implemented.
- Query and retrieval workflows perform accurately with single-document retrieves.
- Robust error handling with comprehensive local logging.
- Successful execution of test cases against mock endpoints.
- Easy local setup and operation without container dependencies.

---

This file can guide development, testing, and deployment of your comprehensive Python IHE test patient utility.

If you want, I can provide this content as a downloadable markdown file for your convenience. Just ask!
