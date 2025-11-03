# Epic 4: SAML Generation & XML Signing

**Epic Goal:** Implement dual SAML approach (template-based and programmatic) with X.509 certificate signing and WS-Security header embedding. This epic delivers the security infrastructure required for authenticated IHE transactions.

### Story 4.1: Certificate Management & Loading

**As a** developer,
**I want** to load and manage X.509 certificates for signing,
**so that** I can create signed SAML assertions for authenticated transactions.

**Acceptance Criteria:**

1. Certificate loader supports PEM, PKCS12, and DER formats (prioritized in that order)
2. Private key loading with optional password protection
3. Certificate and key loaded from file paths or environment variables
4. Certificate validation checks: expiration, key usage, validity period
5. Clear error messages for invalid certificates, mismatched keys, expired certs
6. Certificate information extraction: subject, issuer, expiration date, key size
7. Support for certificate chains (root, intermediate, leaf)
8. Certificate and key cached in memory for reuse (not persisted to disk)
9. Security warning logged when certificate near expiration (< 30 days)
10. Unit tests verify loading all formats, validation, error handling

### Story 4.2: Template-Based SAML Generation

**As a** developer,
**I want** to personalize SAML assertion templates with runtime values,
**so that** I can use organization-provided SAML templates.

**Acceptance Criteria:**

1. SAML template loader accepts XML template file
2. Template placeholders for common SAML fields: subject, issuer, audience, attributes
3. Timestamp fields automatically populated: IssueInstant, NotBefore, NotOnOrAfter
4. Unique assertion ID generated for each SAML assertion
5. User attributes injected from configuration or runtime parameters
6. Template validation ensures required SAML 2.0 structure present
7. Personalized SAML ready for signing (canonicalized XML)
8. Support for multiple assertion templates for different use cases
9. Example SAML template provided in `templates/saml-template.xml`
10. Unit tests verify personalization, timestamp generation, ID uniqueness

### Story 4.3: Programmatic SAML Generation

**As a** developer,
**I want** to generate SAML assertions programmatically,
**so that** I don't need pre-defined templates for standard scenarios.

**Acceptance Criteria:**

1. SAML generator creates SAML 2.0 assertion from parameters
2. Required parameters: subject, issuer, audience
3. Optional parameters: attributes, conditions, validity duration
4. Generated assertion follows SAML 2.0 specification structure
5. Assertion includes AuthnStatement with timestamp
6. Configurable assertion validity period (default 5 minutes)
7. Support for custom attribute statements
8. Generated SAML properly formatted and canonicalized for signing
9. Integration with certificate management for issuer identity
10. Unit tests verify SAML structure, validity periods, attribute handling

### Story 4.4: XML Signature Implementation

**As a** developer,
**I want** to sign SAML assertions using XML signatures,
**so that** I can create authenticated assertions for IHE transactions.

**Acceptance Criteria:**

1. XML signing using `python-xmlsec` library
2. Signature algorithm configurable (default RSA-SHA256)
3. XML canonicalization (C14N) applied before signing to prevent tampering
4. Signature includes KeyInfo with certificate reference
5. Signed SAML assertion validates against XML signature specification
6. Signature verification function validates signed assertions
7. Clear error messages for signing failures, invalid keys, corrupted XML
8. Timestamp freshness validated when verifying signatures
9. Performance optimization for batch signing operations
10. Unit tests verify signing, verification, canonicalization, error cases

### Story 4.5: WS-Security Header Construction

**As a** developer,
**I want** to embed signed SAML in WS-Security SOAP headers,
**so that** I can create authenticated SOAP requests for IHE transactions.

**Acceptance Criteria:**

1. WS-Security header builder accepts signed SAML assertion
2. Proper WS-Security namespace and structure applied
3. SAML embedded in `<wsse:Security>` header element
4. Timestamp element added to WS-Security header
5. Header positioning correct for SOAP envelope (first child of SOAP:Header)
6. Support for additional WS-Security tokens if needed
7. Generated header validates against WS-Security specification
8. Integration with SOAP client (zeep) for header injection
9. Example SOAP envelope with WS-Security header in documentation
10. Unit and integration tests verify header structure, SOAP integration

### Story 4.6: SAML CLI & Testing Tools

**As a** developer,
**I want** CLI commands for SAML generation and testing,
**so that** I can test SAML workflows independently.

**Acceptance Criteria:**

1. CLI command `saml generate` creates SAML assertion from parameters
2. Option `--template <file>` uses template-based generation
3. Option `--programmatic` uses programmatic generation with parameters
4. Option `--sign` signs assertion with specified certificate
5. Option `--output <file>` saves SAML assertion to file
6. Command `saml verify <file>` validates SAML structure and signature
7. Certificate information displayed when verifying signed assertions
8. Command `saml demo` generates sample WS-Security SOAP envelope
9. Clear output shows SAML structure, validity period, signature status
10. Documentation includes examples for common SAML scenarios
