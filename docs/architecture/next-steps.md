# Next Steps

### Immediate Actions (Post-Architecture Approval)

**1. Technical Validation Spikes (1 week)**

**IMPORTANT:** All technical spikes listed below MUST be formalized as user stories and added to the project plan as part of Epic 0 (Technical Validation Spikes) or integrated into Epic 1 (Foundation & CSV Processing) before development begins.

Conduct focused technical spikes to validate critical architectural decisions:

- **SOAP/MTOM Spike:** Validate zeep library can handle MTOM attachments for ITI-41
  - Create minimal PIX Add and ITI-41 transactions
  - Test against mock endpoints
  - Confirm SOAP envelope structure matches IHE requirements
  - **Action Required:** Create story in Epic 0 or Epic 1

- **XML Signing Spike:** Validate python-xmlsec integration
  - Generate test certificate
  - Sign sample SAML assertion
  - Verify signature validation works correctly
  - Test with different certificate formats (PEM, PKCS12, DER)
  - **Action Required:** Create story in Epic 0 or Epic 1

- **HL7v3 Message Spike:** Validate HL7v3 message construction
  - Build sample PRPA_IN201301UV02 message
  - Parse response MCCI_IN000002UV01
  - Confirm namespace and structure correctness
  - **Action Required:** Create story in Epic 0 or Epic 1

**2. Development Environment Setup**

Prepare development infrastructure:

- Set up project repository following source tree structure
- Configure CI/CD pipeline (GitHub Actions)
- Create development dependencies file
- Generate self-signed certificates for testing
- Set up pre-commit hooks (black, ruff, mypy)

**3. Epic Prioritization for Development**

Based on PRD epic structure and architectural dependencies:

**Phase 1 - Foundation (Weeks 1-2):**
- Epic 1: Foundation & CSV Processing
- Epic 2: Mock IHE Endpoints (enables parallel development)

**Phase 2 - Core Functionality (Weeks 3-5):**
- Epic 3: Template Engine & CCD Personalization
- Epic 4: SAML Generation & XML Signing

**Phase 3 - IHE Transactions (Weeks 6-9):**
- Epic 5: PIX Add Transaction Implementation
- Epic 6: ITI-41 Document Submission & Complete Workflow

**Phase 4 - Quality & Documentation (Weeks 10-12):**
- Epic 7: Integration Testing & Documentation

### Handoff to Development Team

**For Scrum Master (@sm) - Story Creation:**

Use this architecture document in conjunction with the PRD to create detailed user stories:

```
Story Creation Prompt:

"Using the architecture document (docs/architecture.md) and PRD (docs/prd.md), 
create detailed implementation stories for [Epic Name]. 

For each story, include:
- Technical implementation details from the architecture
- Component dependencies from architecture diagrams
- Data models and interfaces to use
- Error handling patterns to follow
- Testing requirements from test strategy section
- Specific coding standards from coding standards section

Ensure stories reference the exact modules from the source tree structure."
```

**For Development Agent - Implementation Guidance:**

When implementing stories, developers should:

1. **Always reference these architecture sections:**
   - Source Tree (for file placement)
   - Components (for module responsibilities and interfaces)
   - Data Models (for data structure definitions)
   - Coding Standards (MANDATORY rules)
   - Error Handling Strategy (for exception patterns)

2. **Follow dependency order:**
   - Config Manager → Logging → CSV Parser → Others
   - Mock Server (independent, can be parallel)
   - Template Engine → SAML Module → IHE Transactions

3. **Use defined interfaces:**
   - Don't invent new interfaces without architectural review
   - Follow type signatures from data models exactly
   - Use exception hierarchy defined in error handling section

4. **Maintain test coverage:**
   - Unit tests for every public function
   - Integration tests for component interactions
   - Follow test organization from test strategy section

### Documentation Tasks

**User Documentation:**
- CSV format specification guide (from data models)
- CCD template creation guide (from template engine specs)
- SAML configuration guide (from SAML module specs)
- Troubleshooting guide (from error handling patterns)

**Developer Documentation:**
- API reference (from component interfaces)
- Contributing guide (coding standards + test strategy)
- Architecture decision records (ADRs) for major decisions

### Ongoing Architectural Governance

**Change Management:**
- Significant architectural changes require update to this document
- New components require architecture review
- External API integrations require security review

**Architecture Review Triggers:**
- Adding new IHE transaction types (Phase 2)
- Changing security implementation (certificates, SAML)
- Modifying error handling strategy
- Introducing new external dependencies

### Success Criteria

**Architecture is successful when:**
- ✅ Development team can implement stories without architectural ambiguity
- ✅ AI agents can generate code following exact patterns specified
- ✅ 95%+ transaction success rate achieved (PRD goal)
- ✅ 100 patient batch processing < 5 minutes (NFR1)
- ✅ 80%+ test coverage maintained (NFR13)
- ✅ All IHE transactions conform to specifications
- ✅ Security requirements met (TLS 1.2+, signed SAML, certificate validation)

---

**Architecture Document Status:** COMPLETE

This architecture document is now ready for stakeholder review and approval. Upon approval, development can proceed with Epic 1 (Foundation & CSV Processing) while the Mock IHE Endpoints (Epic 2) are developed in parallel.
