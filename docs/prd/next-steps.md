# Next Steps

### UX Expert Prompt

*Note: This project is primarily CLI-focused with minimal UI/UX requirements. UX involvement is optional but could provide value for CLI command structure and error message design.*

**Prompt for UX Expert (@ux-expert):**

"Review the Python Utility for IHE Test Patient Creation and CCD Submission PRD (docs/prd.md) and provide recommendations for:

1. CLI command structure and naming conventions for optimal developer experience
2. Error message templates for common failure scenarios (CSV validation errors, network failures, certificate issues)
3. Progress indicators and status reporting for batch operations (text-based, suitable for terminal output)
4. Help text structure and examples for CLI commands

Focus on creating a developer-friendly command-line experience with clear, actionable error messages and intuitive command hierarchies."

### Architect Prompt

**Prompt for Architect (@architect):**

"Create a comprehensive architecture document for the Python Utility for IHE Test Patient Creation and CCD Submission based on the PRD in docs/prd.md and Project Brief in docs/brief.md.

The architecture document should include:

1. **System Architecture Overview** - Component interaction diagrams showing data flow from CSV → Template → SAML → SOAP → IHE endpoints
2. **Module Specifications** - Detailed design for each module (csv_parser, template_engine, saml, ihe_transactions, transport, cli, mocks)
3. **HL7v3 Message Structure** - PIX Add (PRPA_IN201301UV02) and Acknowledgment (MCCI_IN000002UV01) message specifications
4. **XDSb Metadata Structure** - ITI-41 ProvideAndRegisterDocumentSetRequest with MTOM attachment handling
5. **SAML Assertion Architecture** - Dual approach (template-based and programmatic) with XML signing workflow
6. **Mock Endpoint Design** - Flask server architecture for PIX Add and ITI-41 simulation
7. **Error Handling Strategy** - Classification (transient/permanent/critical) and retry logic
8. **Logging & Audit Architecture** - Comprehensive audit trail design with PII redaction
9. **Testing Strategy** - Unit, integration, and E2E testing approach
10. **Deployment Architecture** - PyPI distribution, virtual environment setup, optional Docker support

Key Technical Constraints:
- Python 3.10+, monorepo structure, sequential processing (no multi-threading in MVP)
- Libraries: pandas, lxml, zeep, click, flask, python-xmlsec, requests, pytest
- Certificate priority: PEM > PKCS12 > DER
- Configuration: JSON format with environment variable overrides

Deliverable: Create docs/architecture.md using the architecture template (brownfield-architecture-tmpl.yaml or architecture-tmpl.yaml)."
