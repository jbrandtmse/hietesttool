# SAML CLI Guide

This guide demonstrates how to use the SAML CLI commands for generating, verifying, and testing SAML 2.0 assertions in IHE workflows.

## Table of Contents

- [Overview](#overview)
- [SAML Generation](#saml-generation)
- [SAML Verification](#saml-verification)
- [Demo Workflows](#demo-workflows)
- [Certificate Management](#certificate-management)
- [Examples](#examples)

## Overview

The SAML CLI provides three main commands:

- `saml generate` - Create SAML 2.0 assertions (template-based or programmatic)
- `saml verify` - Validate SAML assertion structure and signatures
- `saml demo` - Generate sample WS-Security SOAP envelopes for IHE transactions

## SAML Generation

### Programmatic Generation

Generate SAML assertions programmatically with custom parameters:

```bash
# Basic unsigned assertion
ihe-test-util saml generate --programmatic \
  --subject "user@example.com" \
  --issuer "https://idp.example.com" \
  --audience "https://sp.example.com" \
  --output assertion.xml

# Signed assertion with PEM certificate
ihe-test-util saml generate --programmatic \
  --subject "patient@hospital.org" \
  --issuer "https://hospital-idp.org" \
  --audience "https://hie-service.org" \
  --sign \
  --cert certs/saml-signing.pem \
  --key certs/saml-signing-key.pem \
  --output signed-assertion.xml

# Signed assertion with PKCS12 certificate
ihe-test-util saml generate --programmatic \
  --subject "clinician@clinic.com" \
  --issuer "https://clinic-idp.com" \
  --audience "https://registry.example.com" \
  --sign \
  --cert certs/saml.p12 \
  --cert-password "secretpass" \
  --validity 10 \
  --output assertion-10min.xml
```

### Template-Based Generation

Use XML templates for customized SAML structures:

```bash
# Generate from template
ihe-test-util saml generate \
  --template templates/saml-custom.xml \
  --subject "admin@system.org" \
  --issuer "https://auth.system.org" \
  --audience "https://app.system.org" \
  --output custom-assertion.xml

# Signed template-based assertion
ihe-test-util saml generate \
  --template templates/saml-with-attributes.xml \
  --subject "user@example.com" \
  --issuer "https://idp.example.com" \
  --audience "https://sp.example.com" \
  --sign \
  --cert certs/signing.pem \
  --key certs/signing-key.pem \
  --output signed-custom.xml
```

### Generation Options

| Option | Description | Default |
|--------|-------------|---------|
| `--programmatic` | Use programmatic generation | Auto if no template |
| `--template PATH` | Path to SAML template XML | None |
| `--subject TEXT` | Subject identifier (NameID) | Required |
| `--issuer TEXT` | Issuer identifier | Required |
| `--audience TEXT` | Audience restriction | Required |
| `--validity INT` | Validity period in minutes | 5 |
| `--sign` | Sign the assertion | False |
| `--cert PATH` | Certificate file (PEM/PKCS12/DER) | Required if signing |
| `--key PATH` | Private key file (if separate) | None |
| `--cert-password TEXT` | Certificate password (PKCS12) | None |
| `--output PATH` | Save assertion to file | stdout |
| `--format` | Output format (xml/pretty) | pretty |

## SAML Verification

Verify SAML assertion structure, signatures, and timestamps:

```bash
# Basic verification
ihe-test-util saml verify assertion.xml

# Verbose verification with metadata
ihe-test-util saml verify signed-assertion.xml --verbose
```

### Verification Checks

The verify command validates:

1. **XML Structure** - Well-formed XML syntax
2. **SAML 2.0 Compliance** - Proper SAML assertion structure
3. **Digital Signatures** - XML signature validation (if signed)
4. **Timestamps** - NotBefore and NotOnOrAfter validity
5. **Certificate Info** - Embedded certificate details (verbose mode)

### Verification Output

```
✓ SAML 2.0 structure valid
✓ Signature valid
✓ Timestamps valid

=== Assertion Metadata ===
ID:            _abc123...
Issue Instant: 2025-11-14T12:00:00Z
Issuer:        https://idp.example.com
Subject:       user@example.com
Audience:      https://sp.example.com
```

## Demo Workflows

Generate complete WS-Security SOAP envelopes for IHE testing:

### PIX Add (Patient Identity Cross-Referencing)

```bash
# Generate PIX Add demo envelope
ihe-test-util saml demo \
  --scenario pix-add \
  --cert certs/saml.pem \
  --key certs/saml-key.pem \
  --output demo-pix-add.xml

# With PKCS12 certificate
ihe-test-util saml demo \
  --scenario pix-add \
  --cert certs/saml.p12 \
  --cert-password "pass123" \
  --output pix-add-envelope.xml
```

### ITI-41 (Provide and Register Document Set)

```bash
# Generate ITI-41 demo envelope
ihe-test-util saml demo \
  --scenario iti41 \
  --cert certs/document-signing.pem \
  --key certs/document-signing-key.pem \
  --output demo-iti41.xml
```

### Demo Output

Demo commands generate complete SOAP envelopes with:

- WS-Security header with signed SAML assertion
- Sample IHE transaction payload (PIX Add or ITI-41)
- Usage notes for sending to IHE endpoints

```xml
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Header>
    <wsse:Security>
      <saml:Assertion>
        <!-- Signed SAML assertion -->
      </saml:Assertion>
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <!-- IHE transaction payload -->
  </soap:Body>
</soap:Envelope>
```

## Certificate Management

### Supported Certificate Formats

- **PEM** - Separate certificate and private key files
  - Use `--cert cert.pem --key key.pem`
- **PKCS12** - Certificate and key in one file
  - Use `--cert cert.p12 --cert-password "password"`
- **DER** - Binary certificate format
  - Use `--cert cert.der --key key.pem`

### Certificate Requirements for Signing

1. X.509 certificate with signing capability
2. Matching private key (RSA 2048-bit or higher recommended)
3. Valid not-before/not-after dates
4. For production: Certificate issued by trusted CA

### Generating Test Certificates

For testing purposes, generate certificates using the included script:

```bash
python tests/fixtures/generate_test_certs.py
```

This creates:
- `test_cert.pem` and `test_key.pem` (PEM format)
- `test_cert.p12` (PKCS12 format, password: "testpass")
- `test_cert.der` (DER format)

**⚠️ Warning:** Test certificates are for development only. Use proper CA-issued certificates in production.

## Examples

### Complete Workflow Example

```bash
# 1. Generate signed SAML assertion
ihe-test-util saml generate --programmatic \
  --subject "patient123@hospital.org" \
  --issuer "https://hospital-auth.org" \
  --audience "https://hie-registry.org" \
  --sign \
  --cert certs/hospital-saml.pem \
  --key certs/hospital-saml-key.pem \
  --validity 10 \
  --output patient-assertion.xml

# 2. Verify the assertion
ihe-test-util saml verify patient-assertion.xml --verbose

# 3. Generate demo SOAP envelope for testing
ihe-test-util saml demo \
  --scenario pix-add \
  --cert certs/hospital-saml.pem \
  --key certs/hospital-saml-key.pem \
  --output pix-test-envelope.xml
```

### Integration Testing Example

```bash
# Generate multiple assertions with different validity periods
for minutes in 5 10 30 60; do
  ihe-test-util saml generate --programmatic \
    --subject "test@example.com" \
    --issuer "https://test-idp.com" \
    --audience "https://test-sp.com" \
    --validity $minutes \
    --output "assertion-${minutes}min.xml"
done

# Verify all assertions
for file in assertion-*.xml; do
  echo "Verifying $file..."
  ihe-test-util saml verify "$file"
done
```

### Custom Template Example

Create a custom SAML template (`templates/my-saml.xml`):

```xml
<?xml version="1.0"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="{{assertion_id}}"
                IssueInstant="{{issue_instant}}"
                Version="2.0">
  <saml:Issuer>{{issuer}}</saml:Issuer>
  <saml:Subject>
    <saml:NameID>{{subject}}</saml:NameID>
  </saml:Subject>
  <saml:Conditions NotBefore="{{not_before}}"
                   NotOnOrAfter="{{not_on_or_after}}">
    <saml:AudienceRestriction>
      <saml:Audience>{{audience}}</saml:Audience>
    </saml:AudienceRestriction>
  </saml:Conditions>
  <saml:AttributeStatement>
    <saml:Attribute Name="Role">
      <saml:AttributeValue>Clinician</saml:AttributeValue>
    </saml:Attribute>
  </saml:AttributeStatement>
</saml:Assertion>
```

Use the template:

```bash
ihe-test-util saml generate \
  --template templates/my-saml.xml \
  --subject "doctor@clinic.org" \
  --issuer "https://clinic-sso.org" \
  --audience "https://ehr-system.org" \
  --output custom-role-assertion.xml
```

## Troubleshooting

### Common Issues

**"Signing requires --cert parameter"**
- Add `--cert` and optionally `--key` parameters when using `--sign`

**"Invalid password or PKCS12 data"**
- Verify PKCS12 password with `--cert-password`
- Ensure certificate file is valid PKCS12 format

**"Certificate bundle must contain a private key"**
- For PEM certificates, provide both `--cert` and `--key`
- Or use PKCS12 format which contains both

**"Signature invalid"**
- Certificate may be expired or not yet valid
- Private key doesn't match certificate
- Certificate is self-signed (warning only for test certs)

### Getting Help

```bash
# General SAML help
ihe-test-util saml --help

# Command-specific help
ihe-test-util saml generate --help
ihe-test-util saml verify --help
ihe-test-util saml demo --help
```

## Additional Resources

- [SAML 2.0 Specification](https://docs.oasis-open.org/security/saml/v2.0/)
- [IHE ITI Technical Framework](https://www.ihe.net/resources/technical_frameworks/#IT)
- [XML Signature Syntax](https://www.w3.org/TR/xmldsig-core/)
- [WS-Security Specification](https://docs.oasis-open.org/wss/v1.1/)
