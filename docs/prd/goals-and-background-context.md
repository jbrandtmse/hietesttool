# Goals and Background Context

### Goals

- Automate creation of test patient data and HL7 CCD/CCDA documents from CSV demographics
- Enable rapid, scalable IHE transaction testing (PIX Add, ITI-41) with proper SOAP formatting and security
- Provide template-based flexibility for CCD and SAML assertion personalization
- Support comprehensive query/retrieve workflows (PIX Query, XCPD, ITI-18, ITI-43) in post-MVP phases
- Reduce test data preparation time from hours to minutes (10x improvement)
- Achieve 95%+ transaction success rate against IHE endpoints
- Enable batch processing of 100+ patient records in under 5 minutes
- Support both HTTP and HTTPS transport with appropriate security warnings
- Provide mock IHE endpoints for isolated testing without external dependencies
- Deliver a lightweight, local Python utility requiring no containerization or cloud infrastructure

### Background Context

Healthcare interoperability testing for IHE (Integrating the Healthcare Enterprise) profiles requires extensive test patient data and realistic clinical documents. Current approaches are manual, time-consuming, and don't scale—developers spend hours crafting individual SOAP messages and XML documents instead of focusing on core integration logic. This creates testing bottlenecks, increases costs, and risks inadequate test coverage that can lead to failed certifications and delayed production deployments.

This Python utility solves these challenges by automating the entire IHE test patient lifecycle from data creation through submission, query, and retrieval. It reads CSV demographic data, generates personalized HL7 CCD/CCDA documents from user-provided templates, and executes IHE transactions with proper SOAP formatting, SAML assertion signing, and flexible HTTP/HTTPS transport. Unlike expensive commercial tools or complex containerized solutions, this lightweight CLI application runs locally in a standard Python virtual environment and includes built-in mock endpoints for comprehensive testing without external dependencies.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-11-02 | 0.1 | Initial PRD draft | PM |
| 2025-11-03 | 0.2 | Integrated Epic 0 (Technical Validation Spikes) into Epic 1 as Stories 1.1-1.3; renumbered remaining Epic 1 stories to 1.4-1.11 | PO |
