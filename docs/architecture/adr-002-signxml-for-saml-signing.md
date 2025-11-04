# ADR-002: SignXML for SAML Assertion Signing

## Status
Accepted

## Context

Story 1.2 (XML Signing Validation Spike) evaluated XML signing libraries for SAML 2.0 assertion signing required by Epic 4. The project needs to:

1. Sign SAML 2.0 assertions with RSA-SHA256 and XML Signature (XMLDSig)
2. Implement XML Canonicalization (C14N) 
3. Support multiple certificate formats (PEM, PKCS12, DER)
4. Embed signed SAML in WS-Security SOAP headers for IHE transactions
5. Work reliably on Windows development environments without complex setup

### Original Technology Selection

The initial architecture (tech-stack.md v1.0) specified:
- **python-xmlsec 1.3+**: Python bindings to xmlsec C library, industry standard
- **pysaml2 7.4+**: Enterprise-grade SAML 2.0 library

### Installation Challenges Discovered

During spike implementation, python-xmlsec installation on Windows encountered critical blockers:

1. **Missing Build Tools**: Requires Microsoft Visual C++ 14.0 Build Tools
   - 2-3 GB download size
   - 15-30 minute installation time
   - Permanent system modification
   - Requires administrative privileges

2. **libxml2 Version Mismatch**: Pre-built lxml wheels use different libxml2 version than xmlsec
   - Error: `version 'LIBXML2_2.10.0' not found`
   - Would require compiling lxml from source (additional complexity)

3. **System Library Dependencies**: Requires libxmlsec1 system library
   - Complex cross-platform installation (apt-get, brew, manual Windows)
   - Version compatibility issues across platforms

This creates significant friction for:
- Developer onboarding (hours of setup vs minutes)
- CI/CD pipelines (must install build tools)
- Cross-platform development (different installation per OS)
- Deployment complexity (must ensure build environment available)

### Alternative Evaluated: SignXML

**SignXML** is a pure Python implementation of W3C XML Signature standard:
- Installation: `pip install signxml` (completes in <5 seconds)
- Dependencies: Only lxml + cryptography (both have pre-built wheels)
- Zero compilation required on any platform
- Actively maintained (Python 3.9-3.13 support)
- Standards-compliant (W3C XML Signature Version 1.1)
- Tested against XMLDSig interoperability suite
- Used in production SAML implementations

**Spike Results** (see `docs/spike-findings-1.2-xml-signing-validation.md`):
- ✅ SAML 2.0 assertion generation (lxml)
- ✅ XML signing with RSA-SHA256 (SignXML)
- ✅ Signature verification (SignXML)
- ✅ Tampering detection (SignXML)
- ✅ Certificate loading PEM/PKCS12/DER (cryptography)
- ✅ Certificate chain generation
- ✅ WS-Security integration architecture validated

## Decision

**We will use SignXML for XML signing instead of python-xmlsec.**

We will implement SAML 2.0 assertion generation using a lightweight custom generator built on lxml, rather than adopting the heavyweight pysaml2 library. This approach:
- Meets all project requirements (minimal SAML assertions for IHE transactions)
- Avoids unnecessary complexity (pysaml2 includes features we don't need)
- Provides full control over assertion structure
- Uses SignXML for signing (same signing library either way)

**Technology Stack Changes**:
- **Remove**: python-xmlsec, pysaml2
- **Add**: signxml 3.2+
- **Use**: lxml 5.1+ (already in stack for XML processing)
- **Use**: cryptography 41.0+ (already in stack as transitive dependency)

## Consequences

### Positive

1. **Developer Experience**: 
   - Zero installation friction on Windows
   - Simple `pip install signxml` works on all platforms
   - No administrative privileges required
   - Onboarding measured in minutes, not hours

2. **CI/CD Simplification**:
   - No build environment setup in pipelines
   - Faster CI builds (no compilation)
   - Smaller Docker images (no build tools)

3. **Cross-Platform Compatibility**:
   - Identical installation on Windows, macOS, Linux
   - No platform-specific build issues
   - No system library version conflicts

4. **Maintenance**:
   - Pure Python is easier to debug
   - No C library version compatibility issues
   - Simpler dependency tree

5. **Standards Compliance**:
   - Full W3C XML Signature Version 1.1 implementation
   - Tested against XMLDSig interoperability suite
   - Supports all required features (RSA-SHA256, C14N, SAML 2.0)

6. **Security**:
   - Secure defaults (no network calls, no XSLT/XPath transforms)
   - Modern algorithms (RSA-SHA256, SHA256)
   - Active maintenance (latest release 2024)

### Negative

1. **Performance**: 
   - Pure Python may be slower than C bindings
   - **Mitigation**: Performance is adequate for test utility use case (<50ms signing, <30ms verification). This is not a high-throughput production system.

2. **Enterprise Recognition**:
   - Less "battle-tested" than python-xmlsec in large enterprises
   - **Mitigation**: SignXML is used in production SAML systems, actively maintained since 2014, and standards-compliant. If specific IHE certification requires python-xmlsec, we can switch libraries with minimal code changes (similar APIs).

3. **Not Industry "Standard"**:
   - python-xmlsec is considered the industry standard
   - **Mitigation**: SignXML implements the same W3C XML Signature standard. The output XML is identical and interoperable. Standards compliance matters more than library popularity.

### Neutral

1. **Learning Curve**: 
   - Team must learn SignXML API instead of python-xmlsec API
   - Both libraries have similar concepts and APIs
   - Comprehensive documentation available

2. **pysaml2 Removal**:
   - Lose enterprise-grade SAML library features
   - Our requirements are simple (basic assertions for IHE transactions)
   - Custom lxml generator is <100 lines, fully understood

## Implementation Impact

### Files Created/Modified

**New Modules**:
- `src/ihe_test_util/saml/generator.py` - SAML assertion generation
- `src/ihe_test_util/saml/certificate_manager.py` - Certificate handling
- `src/ihe_test_util/saml/__init__.py` - Module exports

**Dependencies**:
- `requirements.txt` - Added signxml==3.2.2

**Architecture Documentation**:
- `docs/architecture/tech-stack.md` - Updated XML signing and SAML entries
- `docs/architecture/adr-002-signxml-for-saml-signing.md` - This ADR
- `docs/architecture/components.md` - Will be updated with SAML module

**Spike Documentation**:
- `docs/spike-findings-1.2-xml-signing-validation.md` - Detailed evaluation
- `examples/signxml_saml_example.py` - Working demonstration

### Epic 4 Impact

Epic 4 (SAML Generation & XML Signing) will use:
- SignXML for signing SAML assertions
- lxml for SAML assertion structure generation
- cryptography library for certificate handling
- WS-Security header construction with lxml

No changes to Epic 4 user stories needed - implementation approach changes, but functionality remains identical.

## Alternatives Considered

### Alternative 1: python-xmlsec with Windows Build Environment

**Approach**: Install Visual C++ Build Tools on all Windows development machines

**Rejected because**:
- Creates significant developer onboarding friction
- Requires administrative privileges
- 2-3 GB download per developer machine
- Permanent system modification
- CI/CD complexity
- libxml2 version conflicts remain

### Alternative 2: pysaml2 + python-xmlsec

**Approach**: Use pysaml2 for SAML generation, python-xmlsec for signing

**Rejected because**:
- Still has python-xmlsec installation issues
- pysaml2 is heavyweight for our simple needs
- Adds complexity we don't need

### Alternative 3: Manual XML Signature with cryptography Library

**Approach**: Implement XMLDSig manually using cryptography primitives

**Rejected because**:
- Significant development effort
- High risk of security bugs
- Must implement C14N, XMLDSig structure, verification
- Reinventing the wheel when SignXML exists

## Validation

The decision was validated through:
1. **Spike Implementation**: Complete working code demonstrates all requirements
2. **Cross-Platform Testing**: Verified on Windows (primary challenge platform)
3. **Standards Compliance**: SignXML tested against W3C interoperability suite
4. **Research**: Perplexity MCP research confirmed SignXML capabilities and production use

## Migration Path

If future requirements demand python-xmlsec (e.g., for specific IHE certification):

1. **Development**: Continue using SignXML (fast iteration, no setup)
2. **Production**: Add python-xmlsec option via configuration flag
3. **Code Changes**: Minimal - create adapter layer for two signing backends
4. **Testing**: Verify both libraries produce identical XML output

Both libraries produce W3C XML Signature standard output, ensuring interoperability.

## References

- [SignXML Documentation](https://xml-security.github.io/signxml/)
- [W3C XML Signature Syntax and Processing Version 1.1](https://www.w3.org/TR/xmldsig-core1/)
- [Spike Findings: Story 1.2](../spike-findings-1.2-xml-signing-validation.md)
- [SignXML GitHub](https://github.com/XML-Security/signxml)

## Related ADRs

- [ADR-001: Hybrid MTOM Implementation](adr-001-hybrid-mtom-implementation.md) - Similar pattern of pragmatic technology selection over "standard" choice

---

**Date**: 2025-11-03  
**Author**: Winston (Architect)  
**Reviewers**: Development Team  
**Status**: Accepted
