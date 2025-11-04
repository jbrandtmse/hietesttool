# ADR-003: HL7v3 Message Construction with lxml

**Status:** Accepted  
**Date:** 2025-11-03  
**Deciders:** Winston (Architect), James (Dev)  
**Related:** Story 1.3 HL7v3 Message Construction Spike

## Context and Problem Statement

The IHE Test Utility must construct spec-compliant HL7v3 messages for IHE PIX Add (ITI-44) transactions and parse acknowledgment responses. The message construction approach must:

1. Support complex nested HL7v3 structures (PRPA_IN201301UV02)
2. Handle patient demographic data insertion with validation
3. Manage HL7v3 namespaces correctly
4. Parse acknowledgment responses (MCCI_IN000002UV01) with error details
5. Be maintainable and extensible for future IHE transactions
6. Validate against HL7v3 specifications

Story 1.1 implemented a working PIX Add message builder using lxml. Story 1.3 validated this approach and added comprehensive acknowledgment parsing.

## Decision Drivers

- **Spec Compliance:** IHE ITI-44 requires exact HL7v3 PRPA_IN201301UV02 structure
- **Namespace Management:** HL7v3 uses `urn:hl7-org:v3` default namespace plus XSD instance namespace
- **Validation Requirements:** Must validate gender codes, OIDs, and required fields
- **Acknowledgment Parsing:** Must extract status codes (AA/AE/AR/CA/CE/CR) and error details
- **Extensibility:** Pattern must work for future HL7v3 transactions
- **Error Handling:** Actionable error messages for debugging
- **Testing:** Must support comprehensive test coverage

## Considered Options

### Option 1: WSDL-Based Code Generation
Use WSDL parsing tools to generate message classes from HL7v3 schemas.

**Pros:**
- Auto-generated classes from official schemas
- Type safety from generated code
- Schema validation built-in

**Cons:**
- Complex generated code hard to debug
- HL7v3 WSDL schemas complex and large
- Overkill for simple message construction
- Reduces flexibility for IHE-specific constraints
- Generated code may not match IHE profiles exactly

### Option 2: Manual lxml Construction (CHOSEN)
Build HL7v3 messages programmatically using lxml with explicit element creation.

**Pros:**
- Full control over message structure
- Clear, readable code
- Easy to debug and modify
- Supports IHE-specific constraints
- Excellent namespace management
- Proven in other healthcare integrations
- No schema dependencies for development

**Cons:**
- More verbose than auto-generated code
- Requires understanding HL7v3 structure
- Manual namespace declarations

### Option 3: Template-Based Approach
Use XML templates with placeholder substitution.

**Pros:**
- Simple for basic messages
- Non-developers can edit templates

**Cons:**
- Brittle for complex nested structures
- No type safety
- Difficult to validate before rendering
- Not suitable for conditional elements (optional address)
- Hard to maintain for multiple message types

## Decision Outcome

**Chosen Option: Manual lxml Construction (Option 2)**

### Implementation Pattern

**Message Construction:**
```python
from lxml import etree

# Define namespaces
HL7_NS = "urn:hl7-org:v3"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

NSMAP = {
    None: HL7_NS,  # Default namespace
    "xsi": XSI_NS,
}

# Build message hierarchically
root = etree.Element(f"{{{HL7_NS}}}PRPA_IN201301UV02", nsmap=NSMAP, ITSVersion="XML_1.0")

# Add elements with namespace
id_elem = etree.SubElement(root, f"{{{HL7_NS}}}id")
id_elem.set("root", message_id)

# Build control act process hierarchy
control_act = etree.SubElement(root, f"{{{HL7_NS}}}controlActProcess")
control_act.set("classCode", "CACT")
control_act.set("moodCode", "EVN")

# Convert to XML string
xml_string = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8")
```

**Acknowledgment Parsing:**
```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class AcknowledgmentDetail:
    type_code: str  # E=Error, W=Warning, I=Information
    text: str
    code: Optional[str] = None
    code_system: Optional[str] = None

@dataclass
class AcknowledgmentResponse:
    status: str  # AA, AE, AR, CA, CE, CR
    is_success: bool
    message_id: Optional[str] = None
    target_message_id: Optional[str] = None
    details: List[AcknowledgmentDetail] = None

def parse_acknowledgment(ack_xml: str) -> AcknowledgmentResponse:
    """Parse HL7v3 acknowledgment with error details."""
    root = etree.fromstring(ack_xml.encode("utf-8"))
    
    # Extract status code
    type_code_elem = root.find(f".//{{{HL7_NS}}}typeCode")
    status = type_code_elem.get("code")
    
    # Determine success
    is_success = status in ["AA", "CA"]
    
    # Extract error details
    details = []
    for detail_elem in root.findall(f".//{{{HL7_NS}}}acknowledgementDetail"):
        detail = AcknowledgmentDetail(
            type_code=detail_elem.get("typeCode", "E"),
            text=detail_elem.find(f".//{{{HL7_NS}}}text").text,
            # ... extract code and code_system
        )
        details.append(detail)
    
    return AcknowledgmentResponse(status=status, is_success=is_success, details=details)
```

### Architectural Principles

1. **Separation of Concerns**
   - Message construction: `ihe_transactions/pix_add.py`
   - Response parsing: `ihe_transactions/parsers.py`
   - Data models: Dataclasses for structured data

2. **Namespace Management**
   - All HL7v3 elements use `urn:hl7-org:v3` default namespace
   - XSI namespace for schema metadata
   - Namespace map defined once, reused across all messages

3. **Validation Strategy**
   - Input validation: Validate demographics before construction
   - Structural validation: Integration tests verify message structure
   - Optional XSD validation: Can add schema validation as defense-in-depth

4. **Error Handling**
   - Actionable error messages with context
   - Specific exception types (ValueError for validation)
   - Parser raises clear errors for malformed acknowledgments

5. **Extensibility Pattern**
   - PatientDemographics dataclass easily extended
   - Common HL7v3 patterns (header, namespaces) can be extracted to base builder
   - Acknowledgment parser supports all HL7v3 status codes

### Technology Stack

- **lxml 5.1+:** XML construction and parsing
  - High performance C-based library
  - Excellent namespace support
  - XPath and XSLT capabilities
  - Optional XSD schema validation

- **Python dataclasses:** Structured response data
  - Type-safe acknowledgment responses
  - Clear API for consumers

- **pytest 7.4+:** Comprehensive testing
  - 16 integration tests validating message structure
  - All acknowledgment scenarios tested

### Validation Approach

**Primary Validation (Integration Tests):**
- Test all required HL7v3 elements present
- Verify namespace declarations
- Validate demographic data insertion
- Test acknowledgment parsing for all status codes
- Edge case handling

**Optional Validation (Future Enhancement):**
- HL7v3 XSD schema validation using lxml.etree.XMLSchema
- Schemas available from HL7 International
- Can validate against Edition2008/processable/multicacheschemas/PRPA_IN201301UV02.xsd

### Code Quality Standards

- ✅ Type hints on all function signatures
- ✅ Google-style docstrings
- ✅ Logging instead of print statements
- ✅ Path objects for file I/O
- ✅ Specific exception handling
- ✅ Actionable error messages
- ✅ datetime.now(timezone.utc) (not deprecated utcnow)

## Consequences

### Positive

- **Proven Approach:** lxml successfully constructs spec-compliant HL7v3 messages (validated in spike)
- **Maintainable:** Clear, readable code structure
- **Debuggable:** Easy to inspect and modify generated XML
- **Flexible:** Handles IHE-specific constraints and optional elements
- **Testable:** Comprehensive integration test suite (16 tests, all passing)
- **Extensible:** Pattern works for future HL7v3 transactions
- **Performance:** lxml is high-performance for healthcare transaction volumes
- **Acknowledgment Parsing:** Robust parser extracts all error details

### Negative

- **Verbosity:** More code than auto-generated approach
- **HL7v3 Knowledge:** Developers need to understand HL7v3 structure
- **Manual Updates:** Schema changes require manual code updates

### Neutral

- **No WSDL Dependency:** IHE specifications provide sufficient guidance
- **Optional XSD Validation:** Can add as enhancement without code changes

## Validation Results

Story 1.3 spike validated:

✅ **Message Construction:**
- All required HL7v3 elements present
- Correct namespace declarations
- Patient demographics correctly inserted
- Optional address components handled

✅ **Acknowledgment Parsing:**
- All status codes supported (AA, AE, AR, CA, CE, CR)
- Error details extracted with type, text, code, code_system
- Message ID tracking (both acknowledgment and target)
- Handles malformed acknowledgments with clear errors

✅ **Testing:**
- 16 integration tests, all passing (0.17s runtime)
- Message construction: 7 tests
- Acknowledgment parsing: 7 tests
- Validation: 2 tests

✅ **Code Quality:**
- No datetime deprecation warnings
- Full type hints
- Google-style docstrings
- Actionable error messages

## Future Enhancements

**Short-term (Story 1.4+):**
1. Extract common HL7v3 patterns to base message builder
2. Add optional XSD schema validation for compliance verification
3. Create reusable acknowledgment generator for mock endpoints

**Long-term:**
1. Apply pattern to other HL7v3 transactions (ITI-45 PIX Query, etc.)
2. Create HL7v3 message library with reusable components
3. Consider contributing patterns to open-source healthcare integration projects

## Links

- [Story 1.3 Spike Findings](../spike-findings-1.3-hl7v3-messages.md)
- [Acknowledgment Parser](../../src/ihe_test_util/ihe_transactions/parsers.py)
- [PIX Add Message Builder](../../src/ihe_test_util/ihe_transactions/pix_add.py)
- [Integration Tests](../../tests/integration/test_hl7v3_message_flow.py)
- [Working Examples](../../examples/hl7v3_message_example.py)
- [IHE ITI-44 Specification](https://profiles.ihe.net/ITI/TF/Volume2/ITI-44.html)
- [lxml Documentation](https://lxml.de/)

## Notes

- Pattern established in this ADR is foundation for all HL7v3 transactions
- Acknowledgment parser is reusable across all IHE transactions
- lxml namespace management is critical for HL7v3 compliance
- Integration tests provide excellent validation without requiring HL7 schema licensing
