# Epic List

**Epic 1: Foundation & CSV Processing**
Establish project infrastructure through technical validation spikes, then build Python package structure, CSV demographic data import with validation and ID generation, and basic CLI for CSV processing operations. This epic begins with focused technical spikes to validate critical architectural decisions (SOAP/MTOM, XML signing, HL7v3 messaging) before proceeding with foundation implementation.

**Epic 2: Mock IHE Endpoints**
Create Flask-based mock PIX Add and ITI-41 endpoints with HTTP/HTTPS support, including CLI commands to start/stop/configure mock servers for isolated testing.

**Epic 3: Template Engine & CCD Personalization**
Implement XML template processing with string replacement for CCD personalization, batch generation from CSV demographics, and CLI for template processing operations.

**Epic 4: SAML Generation & XML Signing**
Implement dual SAML approach (template-based and programmatic) with X.509 certificate signing, WS-Security header embedding, and CLI for SAML generation and testing.

**Epic 5: PIX Add Transaction Implementation**
Build HL7v3 PRPA_IN201301UV02 message construction, SOAP-based submission to PIX Add endpoints with acknowledgment parsing/logging, and CLI for patient registration workflows.

**Epic 6: ITI-41 Document Submission & Complete Workflow**
Implement ITI-41 Provide and Register Document Set-b transaction with MTOM support, XDSb metadata, integration with PIX Add, and complete CLI for end-to-end patient submission workflows with batch processing and configuration management.

**Epic 7: Integration Testing & Documentation**
Implement comprehensive test suite (unit, integration, end-to-end), CI/CD pipeline with GitHub Actions, and complete user documentation with examples and troubleshooting guides.
