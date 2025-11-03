# Research Protocol for Technical Uncertainty

## Purpose

This rule establishes the protocol for conducting technical research when encountering uncertainty about project-specific technologies and standards.

## Rule Definition

**MANDATORY RESEARCH REQUIREMENT:** When you are not 100% certain about technical details, standards, specifications, or implementation approaches related to this project, you MUST use the Perplexity MCP tool to research and verify information before proceeding.

## When to Use Perplexity MCP Research

You MUST research using Perplexity MCP when encountering ANY of the following:

### IHE (Integrating the Healthcare Enterprise) Standards
- IHE transaction specifications (ITI-41, PIX Add, PIX Query, XCPD, ITI-18, ITI-43, etc.)
- IHE profile requirements and constraints
- XDSb (Cross-Enterprise Document Sharing) specifications
- IHE message structure and format requirements
- IHE endpoint configuration and communication patterns
- MTOM (MIME-based SOAP attachment) implementation details for IHE

### HL7 Standards
- HL7v3 message structure (PRPA_IN201301UV02, MCCI_IN000002UV01, etc.)
- HL7 CCDA/CCD document structure and requirements
- HL7 data types, codes, and vocabularies
- HL7v3 namespace and schema requirements

### SAML (Security Assertion Markup Language)
- SAML 2.0 assertion structure and requirements
- SAML signing and verification processes
- SAML timestamp and validity requirements
- WS-Security header construction with SAML
- SAML attribute statements and conditions

### XML Security
- XML Signature (XMLDSig) standards and implementation
- XML canonicalization (C14N) requirements
- X.509 certificate handling and validation
- Certificate formats (PEM, PKCS12, DER) and conversion

### SOAP and Web Services
- SOAP envelope structure and namespacing
- WS-Addressing header requirements
- WS-Security implementation details
- MTOM attachment packaging and Content-ID referencing
- SOAP fault handling

### Python Libraries and Implementation
- `zeep` library capabilities and limitations for IHE transactions
- `lxml` XML processing best practices
- `python-xmlsec` signing and verification workflows
- `python-saml` or `pysaml2` implementation patterns
- `pandas` CSV processing optimization

### Healthcare Interoperability
- Patient identifier domains and OID management
- Clinical document metadata requirements
- Healthcare data exchange security requirements
- Compliance and audit trail requirements

## How to Use Perplexity MCP

### Available Tools

1. **For general research and questions:**
   ```
   <use_mcp_tool>
   <server_name>github.com/pashpashpash/perplexity-mcp</server_name>
   <tool_name>search</tool_name>
   <arguments>
   {
     "query": "your detailed question here",
     "detail_level": "detailed"
   }
   </arguments>
   </use_mcp_tool>
   ```

2. **For specific technology/library documentation:**
   ```
   <use_mcp_tool>
   <server_name>github.com/pashpashpash/perplexity-mcp</server_name>
   <tool_name>get_documentation</tool_name>
   <arguments>
   {
     "query": "technology or library name",
     "context": "specific aspect or use case"
   }
   </arguments>
   </use_mcp_tool>
   ```

3. **For ongoing technical discussions (maintains conversation context):**
   ```
   <use_mcp_tool>
   <server_name>github.com/pashpashpash/perplexity-mcp</server_name>
   <tool_name>chat_perplexity</tool_name>
   <arguments>
   {
     "message": "your question or follow-up",
     "chat_id": "optional - use for follow-ups in same research session"
   }
   </arguments>
   </use_mcp_tool>
   ```

## Research Protocol

1. **Identify Uncertainty:** Recognize when you lack complete certainty about technical details
2. **Formulate Query:** Create specific, detailed research questions
3. **Use Perplexity MCP:** Execute research using appropriate tool (search, get_documentation, or chat_perplexity)
4. **Review Results:** Analyze the research findings carefully
5. **Apply Knowledge:** Incorporate verified information into your work
6. **Document:** If significant, consider noting key findings in project documentation

## Examples

### Example 1: IHE Transaction Research
```
When implementing PIX Add transaction and uncertain about exact SOAP header requirements:

<use_mcp_tool>
<server_name>github.com/pashpashpash/perplexity-mcp</server_name>
<tool_name>search</tool_name>
<arguments>
{
  "query": "IHE PIX Add ITI-8 SOAP header requirements WS-Addressing MessageID",
  "detail_level": "detailed"
}
</arguments>
</use_mcp_tool>
```

### Example 2: SAML Implementation Research
```
When uncertain about SAML assertion signing requirements:

<use_mcp_tool>
<server_name>github.com/pashpashpash/perplexity-mcp</server_name>
<tool_name>get_documentation</tool_name>
<arguments>
{
  "query": "SAML 2.0 XML Signature",
  "context": "signing assertions with X.509 certificates using python-xmlsec"
}
</arguments>
</use_mcp_tool>
```

### Example 3: Library Capability Verification
```
When uncertain if zeep library supports MTOM for ITI-41:

<use_mcp_tool>
<server_name>github.com/pashpashpash/perplexity-mcp</server_name>
<tool_name>get_documentation</tool_name>
<arguments>
{
  "query": "zeep python library",
  "context": "MTOM attachment support for IHE ITI-41 transactions"
}
</arguments>
</use_mcp_tool>
```

## Enforcement

- **Do NOT guess** about technical specifications
- **Do NOT assume** standard behavior without verification
- **Do NOT skip research** to save time
- **DO research first** when uncertain
- **DO verify** critical implementation details
- **DO use detailed queries** for better results

## Scope

This rule applies to:
- All agent personas (@architect, @po, @sm, @ux-expert, and base Cline)
- All modes (Plan Mode and Act Mode)
- All phases of development (planning, architecture, implementation, testing)

## Priority

This is a HIGH PRIORITY rule that takes precedence over efficiency concerns. Accurate technical implementation is more important than speed.
