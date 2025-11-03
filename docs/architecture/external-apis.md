# External APIs

This utility integrates with **IHE (Integrating the Healthcare Enterprise) endpoints** for healthcare interoperability testing. These are SOAP-based web services implementing standard IHE profiles.

### PIX Add (Patient Identity Feed) API

**Purpose:** Patient registration and identity management. Registers patient demographics with a Patient Identifier Cross-reference Manager.

**Documentation:** 
- IHE ITI TF-2b: Patient Identifier Cross-referencing HL7 V3 (ITI-44)
- HL7 Version 3 PRPA_IN201301UV02 Message Specification
- https://profiles.ihe.net/ITI/TF/Volume2/ITI-44.html

**Base URL(s):** Configurable per environment
- Development: `http://localhost:8080/pix/add` (mock server)
- Internal Testing: Organization-specific test endpoints
- Production: Varies by organization

**Authentication:** WS-Security with SAML 2.0 assertion (signed with X.509 certificate)

**Rate Limits:** 
- Test environments: Typically no limits
- Production: Organization-specific, generally 100-1000 requests/minute

**Key Endpoints Used:**
- `POST /pix/add` - Submit HL7v3 PRPA_IN201301UV02 patient registration message

**Integration Notes:**
- **Message Format:** HL7 Version 3 XML (not HL7 v2 pipe-delimited)
- **Required Elements:** Patient ID with OID, demographics (name, DOB, gender)
- **Response Format:** HL7v3 MCCI_IN000002UV01 acknowledgment
- **Status Codes:** AA (accepted), AE (error), AR (rejected)
- **Timeout Recommendation:** 30 seconds
- **Idempotency:** Not guaranteed - duplicate submissions may create duplicate records
- **Error Handling:** Parse acknowledgment status, extract error details from response
- **Testing:** Mock endpoint provides static acknowledgments with pre-configured IDs

### ITI-41 (Provide and Register Document Set-b) API

**Purpose:** Submit clinical documents (CCDs) to an XDSb Document Repository with metadata registration.

**Documentation:**
- IHE ITI TF-2b: Provide and Register Document Set-b (ITI-41)
- XDS.b Document Sharing Infrastructure
- https://profiles.ihe.net/ITI/TF/Volume2/ITI-41.html

**Base URL(s):** Configurable per environment
- Development: `http://localhost:8080/iti41/submit` (mock server)
- Internal Testing: Organization-specific test endpoints
- Production: Varies by organization

**Authentication:** WS-Security with SAML 2.0 assertion (signed with X.509 certificate)

**Rate Limits:**
- Test environments: Typically no limits
- Production: Organization-specific, generally 10-100 documents/minute (lower due to document size)

**Key Endpoints Used:**
- `POST /DocumentRepository_Service` - Submit ProvideAndRegisterDocumentSetRequest with MTOM attachment

**Integration Notes:**
- **Message Format:** SOAP with MTOM (MIME multipart) for document attachment
- **Required Metadata:** Patient ID, document unique ID, submission set ID, classCode, typeCode, formatCode
- **Document Format:** HL7 CCD (CCDA R2.1) as XML attachment
- **Response Format:** XDSb RegistryResponse with status and unique IDs
- **Status Values:** Success, Failure, PartialSuccess
- **Timeout Recommendation:** 60 seconds (documents can be large)
- **MTOM Handling:** CCD attached with Content-ID reference in metadata
- **Document Hash:** SHA-256 hash included in metadata for integrity verification
- **Error Handling:** Parse RegistryErrorList for detailed error information
- **Testing:** Mock endpoint validates MTOM structure, saves documents locally

### Test Environments

**Local Mock Endpoints (Included in Utility):**
- **URL:** `http://localhost:8080` or `https://localhost:8443`
- **Purpose:** Isolated testing without external dependencies
- **Access:** No authentication required (or configurable)
- **Advantages:** Fast, reliable, no network dependencies, perfect for CI/CD
- **Limitations:** Static responses, minimal validation, does not test against real IHE implementations

**Internal Organization Test Endpoints:**
- **URL:** Varies by organization (configured via config.json)
- **Purpose:** Integration testing against organization-specific IHE infrastructure
- **Access:** Organization-specific authentication and certificates required
- **Usage:** Primary environment for integration testing

### External API Integration Strategy

1. **Development Phase:** Use local mock endpoints exclusively for rapid iteration
2. **Integration Testing:** Validate against internal organization test endpoints
3. **Pre-Production:** Test against organization-specific staging environments
4. **Continuous Integration:** Use mock endpoints in CI/CD pipelines for speed and reliability

**Security Considerations:**
- All production endpoints MUST use HTTPS with valid certificates
- HTTP allowed only for local mock endpoints (with warnings)
- SAML assertions MUST be signed with valid X.509 certificates
- Certificate expiration monitoring recommended
- Audit logs MUST capture all external API interactions
