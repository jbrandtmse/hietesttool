# ADR-001: Hybrid MTOM Implementation Strategy

**Status:** Accepted  
**Date:** 2025-11-03  
**Deciders:** Winston (Architect), James (Dev)  
**Related:** Story 1.1 SOAP/MTOM Integration Spike

## Context and Problem Statement

The IHE Test Utility requires implementation of two key IHE transactions:
1. **PIX Add (ITI-44):** Patient registration using HL7v3 SOAP messages
2. **ITI-41 (Provide and Register Document Set-b):** Document submission using SOAP with MTOM attachments

Initial assumption was to use zeep library for all SOAP operations, including MTOM attachment handling. The spike (Story 1.1) validated this approach and identified limitations.

## Decision Drivers

- **Zeep MTOM Support:** Documented as "experimental" with limited examples for IHE transactions
- **IHE Compliance:** Must match ITI-41 specification exactly for interoperability
- **Maintainability:** Code must be debuggable and understandable by team
- **Risk Mitigation:** Cannot rely on experimental features for production
- **Performance:** Must handle CCD documents efficiently (10KB+)

## Considered Options

### Option 1: Full Zeep Implementation (Original Plan)
Use zeep for both PIX Add and ITI-41 including MTOM.

**Pros:**
- Single library for all SOAP operations
- WSDL parsing benefits
- Consistent API

**Cons:**
- Experimental MTOM support - insufficient documentation
- No clear IHE ITI-41 examples
- Risk of production issues with attachment handling
- Limited control over multipart MIME formatting

### Option 2: Manual SOAP Construction (All Transactions)
Use lxml + requests for all IHE transactions.

**Pros:**
- Full control over message formatting
- Clear multipart MIME handling
- No dependency on experimental features

**Cons:**
- More code to maintain
- Manual SOAP envelope construction for ALL transactions
- Loses WSDL benefits
- Overkill for simple transactions like PIX Add

### Option 3: Hybrid Approach (CHOSEN)
Use lxml for message construction + hybrid transport:
- Standard SOAP transactions: Use requests with manually constructed messages
- MTOM transactions (ITI-41): Use requests with manual multipart MIME packaging

**Pros:**
- Best of both worlds - simplicity where possible, control where needed
- lxml proven for HL7v3 and XDSb metadata construction (validated in spike)
- Full control over MTOM multipart formatting
- No dependency on experimental zeep MTOM features
- Clear separation of concerns
- Proven approach in other IHE implementations

**Cons:**
- Mixed approach requires clear documentation
- More code than pure zeep solution (minimal increase)
- No WSDL parsing benefits (not needed for IHE - specs are sufficient)

## Decision Outcome

**Chosen Option: Hybrid Approach (Option 3)**

### Implementation Strategy

**For PIX Add (ITI-44) and standard SOAP transactions:**
```python
# Message construction with lxml
message_xml = build_pix_add_message(patient)

# Direct HTTP POST with requests
response = requests.post(
    endpoint_url,
    data=message_xml.encode('utf-8'),
    headers={'Content-Type': 'application/soap+xml; charset=utf-8'}
)
```

**For ITI-41 and MTOM transactions:**
```python
# 1. Build XDSb metadata with lxml
metadata_xml, attachment = build_iti41_request(request, document_path)

# 2. Package as multipart MIME with email.mime
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

multipart = MIMEMultipart('related', type='application/xop+xml')

# Add SOAP envelope part
soap_part = MIMEApplication(metadata_xml, 'xop+xml')
soap_part.add_header('Content-ID', '<root@example.com>')
multipart.attach(soap_part)

# Add document attachment part
doc_part = MIMEApplication(attachment.content, 'xml')
doc_part.add_header('Content-ID', f'<{attachment.content_id}>')
multipart.attach(doc_part)

# 3. Submit with requests
response = requests.post(
    endpoint_url,
    data=multipart.as_string(),
    headers={'Content-Type': multipart.get_content_type()}
)
```

### Technology Stack Updates

- **lxml 5.1+:** Primary XML construction for all IHE transactions
- **requests 2.31+:** HTTP transport for all SOAP submissions
- **email.mime (stdlib):** Multipart MIME packaging for MTOM
- **zeep 4.2+:** RETAINED but limited use (may use for future non-MTOM transactions if WSDL benefits needed)

### Impacted Components

1. **IHE Transactions Module** (`src/ihe_test_util/ihe_transactions/`)
   - `pix_add.py` - HL7v3 construction complete ✅
   - `iti41.py` - XDSb metadata construction complete ✅
   - NEW: `iti41_submit.py` - MTOM multipart packaging (to be implemented)

2. **Transport Module** (`src/ihe_test_util/transport/`)
   - NEW: `mtom_transport.py` - MTOM multipart submission handler

3. **Test Suite**
   - Integration tests for MTOM submission workflow
   - Validation against mock endpoints

### Migration Path

**Phase 1 (Completed - Story 1.1):**
- ✅ PIX Add message construction
- ✅ ITI-41 metadata construction
- ✅ MTOM attachment class
- ✅ Mock endpoints

**Phase 2 (Next Sprint):**
- Implement `mtom_transport.py` for multipart MIME packaging
- Complete ITI-41 end-to-end submission workflow
- Integration tests for MTOM submission

**Phase 3 (Future):**
- Apply pattern to other MTOM-based transactions if needed

## Consequences

### Positive

- **De-risked:** No reliance on experimental features
- **Maintainable:** Standard library components (email.mime) with extensive documentation
- **Debuggable:** Clear visibility into multipart message structure
- **IHE Compliant:** Full control ensures exact specification match
- **Proven:** Pattern used successfully in other IHE implementations
- **Testable:** Mock endpoints validate complete workflow

### Negative

- **Code Volume:** Slightly more code than pure zeep approach
- **Mixed Approach:** Requires clear documentation of when to use what
- **Learning Curve:** Team needs to understand multipart MIME structure

### Neutral

- **No WSDL Parsing:** IHE transactions use well-defined specs, WSDL parsing not critical
- **Performance:** lxml + requests are both high-performance libraries
- **Zeep Retained:** Can still use zeep for future non-MTOM SOAP transactions if beneficial

## Validation

Story 1.1 spike validated:
- ✅ lxml successfully constructs HL7v3 and XDSb metadata
- ✅ Mock endpoints handle multipart MTOM requests
- ✅ Integration tests pass
- ✅ 13.6 KB CCD document exceeds 10KB requirement
- ✅ Content-ID reference mechanism works correctly

## Links

- [Story 1.1 Spike Findings](../spike-findings-1.1-soap-mtom.md)
- [Tech Stack Documentation](./tech-stack.md)
- [IHE ITI-41 Specification](https://profiles.ihe.net/ITI/TF/Volume2/ITI-41.html)
- [Python email.mime Documentation](https://docs.python.org/3/library/email.mime.html)

## Notes

- Monitor zeep library for improved MTOM support in future releases
- Consider contributing MTOM examples/plugin back to zeep community
- Pattern established here is reusable for any future MTOM-based IHE transactions
