# Template Library

This directory contains XML templates for generating personalized healthcare documents and SAML assertions.

## Template Types

- **CCD Templates** - HL7 CCDA R2.1 (Continuity of Care Document) for clinical documents
- **SAML Templates** - SAML 2.0 Assertions for authentication and authorization

---

# CCD Templates

HL7 CCDA R2.1 (Continuity of Care Document) templates for generating personalized clinical documents.

## Available Templates

### 📄 ccd-template.xml - Comprehensive Template
**Full-featured CCD with clinical sections**

- ✅ Complete document header with metadata
- ✅ Patient demographics (all fields)
- ✅ Allergies and Intolerances section (LOINC 48765-2)
- ✅ Medications section (LOINC 10160-0)
- ✅ Problem List section (LOINC 11450-4)
- ✅ Procedures section (LOINC 47519-4)
- ✅ Inline documentation and examples

**Use when:**
- You need a complete clinical document
- Demonstrating full CCDA capabilities
- Creating realistic test data with clinical sections

**Size:** ~9KB (with comments)

### 📄 ccd-minimal.xml - Minimal Template
**Simplest valid CCD with demographics only**

- ✅ Document header (required elements only)
- ✅ Patient demographics (required fields)
- ✅ Empty structured body (no clinical sections)

**Use when:**
- Quick testing with minimal data
- Learning template personalization
- Batch processing (faster, smaller files)
- Testing PIX Add + ITI-41 workflow

**Size:** ~2KB (with comments)

## Quick Start

### 1. Validate a Template

```bash
python -c "from lxml import etree; etree.parse('templates/ccd-minimal.xml'); print('✓ Valid')"
```

### 2. Personalize with Patient Data

```python
from pathlib import Path
from ihe_test_util.template_engine import CCDPersonalizer
from ihe_test_util.csv_parser import parse_csv

# Load patient data
df = parse_csv(Path("examples/patients_sample.csv"))

# Personalize template
personalizer = CCDPersonalizer()
ccd = personalizer.personalize_from_dataframe_row(
    Path("templates/ccd-minimal.xml"),
    df.iloc[0]
)

print(f"Generated document: {ccd.document_id}")
```

## Template Format

All templates use the `{{field_name}}` placeholder format:

### Required Placeholders
- `{{patient_id}}` - Patient identifier
- `{{patient_id_oid}}` - OID for patient ID domain
- `{{first_name}}` - Patient first name
- `{{last_name}}` - Patient last name
- `{{dob}}` - Date of birth (auto-formatted to HL7 YYYYMMDD)
- `{{gender}}` - Gender code (M, F, O, U)
- `{{document_id}}` - Document UUID (auto-generated)
- `{{creation_timestamp}}` - Creation time (auto-generated)

### Optional Placeholders
- `{{mrn}}` - Medical record number
- `{{ssn}}` - Social security number
- `{{address}}`, `{{city}}`, `{{state}}`, `{{zip}}` - Address fields
- `{{phone}}`, `{{email}}` - Contact information

## Automatic Processing

The template engine automatically:

✅ **Formats dates** to HL7 format (YYYYMMDD)
✅ **Escapes XML** special characters (&, <, >, ", ')
✅ **Validates OIDs** for proper format
✅ **Generates** document IDs and timestamps
✅ **Handles missing** optional fields gracefully

## Usage with CSV Data

### Minimal CSV Format
```csv
patient_id,patient_id_oid,first_name,last_name,dob,gender
P001,2.16.840.1.113883.4.357,John,Doe,1980-05-15,M
```

### Full CSV Format (for ccd-template.xml)
```csv
patient_id,patient_id_oid,first_name,last_name,dob,gender,mrn,ssn,address,city,state,zip,phone,email
P001,2.16.840.1.113883.4.357,John,Doe,1980-05-15,M,MRN001,123-45-6789,123 Main St,Springfield,IL,62701,555-123-4567,john.doe@example.com
```

## Comparison

| Feature | ccd-minimal.xml | ccd-template.xml |
|---------|----------------|------------------|
| **Required fields only** | ✅ | ✅ |
| **Optional fields** | ❌ | ✅ |
| **Clinical sections** | ❌ | ✅ (4 sections) |
| **File size** | ~2KB | ~9KB |
| **Best for** | Quick testing | Full demos |
| **Processing speed** | Faster | Slower |

## Documentation

📖 **Full Documentation:** [docs/ccd-templates.md](../docs/ccd-templates.md)
- Placeholder reference
- HL7 CCDA R2.1 overview
- Creating custom templates
- Troubleshooting guide

🚀 **Quick Start Tutorial:** [docs/quickstart-templates.md](../docs/quickstart-templates.md)
- Step-by-step guide
- Complete working examples
- Validation and testing

## Creating Custom Templates

1. **Copy an existing template:**
   ```bash
   cp templates/ccd-template.xml templates/my-template.xml
   ```

2. **Edit the template** (add/remove sections)

3. **Validate:**
   ```python
   from ihe_test_util.template_engine import validate_xml, extract_placeholders
   
   template = Path("templates/my-template.xml").read_text()
   validate_xml(template)
   placeholders = extract_placeholders(template)
   print(f"Placeholders: {placeholders}")
   ```

4. **Test with sample data:**
   ```python
   personalizer = CCDPersonalizer()
   ccd = personalizer.personalize_from_dataframe_row(
       Path("templates/my-template.xml"),
       df.iloc[0]
   )
   ```

## Standards Compliance

✅ **HL7 CCDA R2.1** - Follows Clinical Document Architecture Release 2.1
✅ **XML Namespaces** - Proper urn:hl7-org:v3 namespace declarations
✅ **LOINC Codes** - Standard codes for clinical sections
✅ **OID Format** - Valid Object Identifiers for patient domains
✅ **UTF-8 Encoding** - Proper character encoding

## Related Files

- `examples/patients_sample.csv` - Sample patient data (30 patients)
- `tests/fixtures/test_ccd_template.xml` - Test template
- `src/ihe_test_util/template_engine/` - Template processing code

## Support

For issues or questions:
- See [docs/ccd-templates.md](../docs/ccd-templates.md#common-issues--troubleshooting)
- Check the integration tests: `tests/integration/test_ccd_personalization_workflow.py`
- Review example scripts in [docs/quickstart-templates.md](../docs/quickstart-templates.md)

---

**Version:** 1.0 (Story 3.4)  
**Last Updated:** 2025-11-10  
**Related Stories:** 3.1 (Loader), 3.2 (Replacement), 3.3 (Personalization), 3.4 (Templates)

---

# SAML Templates

SAML 2.0 assertion templates for authentication in healthcare IHE transactions.

## Available SAML Templates

### 🔐 saml-template.xml - Standard SAML Assertion
**Complete SAML 2.0 assertion with healthcare attributes**

- ✅ Complete SAML 2.0 structure
- ✅ Subject with bearer confirmation
- ✅ Conditions with validity period and audience restriction
- ✅ Authentication statement
- ✅ Attribute statement with healthcare context
- ✅ Standard attributes: username, role, organization, purpose of use

**Use when:**
- Authenticating IHE transactions (PIX Add, ITI-41)
- Standard healthcare interoperability scenarios
- Testing with realistic SAML assertions

**Size:** ~2KB (with comments)

### 🔐 saml-minimal.xml - Minimal SAML Assertion
**Bare minimum SAML 2.0 assertion**

- ✅ Required SAML 2.0 elements only
- ✅ Subject with bearer confirmation
- ✅ Basic conditions and authentication
- ❌ No attribute statement

**Use when:**
- Simple authentication without attributes
- Quick testing with minimal data
- Learning SAML template structure

**Size:** ~1KB (with comments)

### 🔐 saml-with-attributes.xml - Extended SAML Assertion
**Comprehensive SAML with extensive healthcare attributes**

- ✅ All features of saml-template.xml
- ✅ Extended user identity attributes (given name, family name, email)
- ✅ Organization identifiers and facility information
- ✅ Healthcare provider attributes (NPI, specialty)
- ✅ Detailed role and authorization context

**Use when:**
- Complex healthcare workflows requiring detailed user context
- NHIN/IHE scenarios with extensive attribute requirements
- Full-featured demonstrations

**Size:** ~3KB (with comments)

## Quick Start

### 1. Validate a SAML Template

```bash
python -c "from lxml import etree; etree.parse('templates/saml-template.xml'); print('✓ Valid')"
```

### 2. Personalize with User Data

```python
from pathlib import Path
from ihe_test_util.saml.template_loader import SAMLTemplatePersonalizer

# Initialize personalizer
personalizer = SAMLTemplatePersonalizer()

# Define parameters
parameters = {
    'issuer': 'https://idp.hospital.org',
    'subject': 'dr.smith@hospital.org',
    'audience': 'https://xds.regional-hie.org',
    'attr_username': 'dr.smith',
    'attr_role': 'physician',
    'attr_organization': 'General Hospital',
    'attr_purpose_of_use': 'TREATMENT'
}

# Personalize template
saml_xml = personalizer.personalize(
    Path("templates/saml-template.xml"),
    parameters,
    validity_minutes=5
)

print(f"Generated SAML assertion ({len(saml_xml)} bytes)")
```

### 3. Personalize with Certificate Info

```python
from pathlib import Path
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.saml.template_loader import SAMLTemplatePersonalizer

# Load certificate
cert_bundle = load_certificate(
    Path("tests/fixtures/test_cert.p12"),
    password=b"password"
)

# Personalize with certificate issuer
personalizer = SAMLTemplatePersonalizer()
parameters = {
    'subject': 'user@example.com',
    'audience': 'https://xds-registry.example.com',
    'attr_username': 'user',
    'attr_role': 'physician'
}

saml_xml = personalizer.personalize_with_certificate_info(
    Path("templates/saml-template.xml"),
    cert_bundle,
    parameters
)

# Issuer automatically extracted from certificate subject DN
```

## SAML Template Format

All SAML templates use the `{{field_name}}` placeholder format:

### Auto-Generated Placeholders
These are automatically generated if not provided:
- `{{assertion_id}}` - Unique assertion ID (UUID with _ prefix)
- `{{issue_instant}}` - Current UTC time (ISO 8601)
- `{{not_before}}` - Validity start time (current UTC)
- `{{not_on_or_after}}` - Validity end time (current + validity_minutes)

### Required Placeholders
Must be provided in parameters:
- `{{issuer}}` - Identity provider identifier
- `{{subject}}` - Subject/user identifier
- `{{audience}}` - Intended audience (service provider URL)

### Optional Attribute Placeholders
- `{{attr_username}}` - Username/login ID
- `{{attr_role}}` - User role (physician, nurse, admin, etc.)
- `{{attr_organization}}` - Organization name
- `{{attr_purpose_of_use}}` - Purpose of use code

### Extended Attributes (saml-with-attributes.xml)
- `{{attr_given_name}}` - First name
- `{{attr_family_name}}` - Last name
- `{{attr_email}}` - Email address
- `{{attr_organization_id}}` - Organization identifier
- `{{attr_facility}}` - Facility/department name
- `{{attr_npi}}` - National Provider Identifier
- `{{attr_specialty}}` - Medical specialty

## Automatic Processing

The SAML template engine automatically:

✅ **Generates assertion IDs** - Unique UUID-based IDs with _ prefix
✅ **Generates timestamps** - ISO 8601 format with Z suffix (UTC)
✅ **Validates templates** - Checks for required SAML 2.0 structure
✅ **Extracts placeholders** - Identifies all template fields
✅ **Validates XML** - Ensures well-formed XML
✅ **Caches templates** - Improves performance for batch operations

## SAML Template Comparison

| Feature | saml-minimal.xml | saml-template.xml | saml-with-attributes.xml |
|---------|------------------|-------------------|--------------------------|
| **Required elements** | ✅ | ✅ | ✅ |
| **Basic attributes** | ❌ | ✅ (4 attrs) | ✅ (11 attrs) |
| **User identity** | ❌ | ✅ Basic | ✅ Extended |
| **Healthcare context** | ❌ | ✅ Standard | ✅ Comprehensive |
| **File size** | ~1KB | ~2KB | ~3KB |
| **Best for** | Simple auth | Standard IHE | Complex workflows |
| **Processing speed** | Fastest | Fast | Fast |

## Usage Scenarios

### Scenario 1: PIX Add Transaction
```python
# Use saml-template.xml with basic healthcare context
parameters = {
    'issuer': 'https://idp.hospital.org',
    'subject': 'integration-user@hospital.org',
    'audience': 'https://pix-manager.hie.org',
    'attr_username': 'integration-user',
    'attr_role': 'system',
    'attr_organization': 'General Hospital',
    'attr_purpose_of_use': 'SYSADMIN'
}
```

### Scenario 2: ITI-41 Document Submission
```python
# Use saml-with-attributes.xml for full provider context
parameters = {
    'issuer': 'https://idp.hospital.org',
    'subject': 'dr.jane.smith@hospital.org',
    'audience': 'https://xds-repository.hie.org',
    'attr_username': 'jsmith',
    'attr_given_name': 'Jane',
    'attr_family_name': 'Smith',
    'attr_email': 'jane.smith@hospital.org',
    'attr_role': 'physician',
    'attr_organization': 'General Hospital',
    'attr_organization_id': '2.16.840.1.113883.4.6.12345',
    'attr_facility': 'Cardiology Department',
    'attr_purpose_of_use': 'TREATMENT',
    'attr_npi': '1234567890',
    'attr_specialty': 'Cardiology'
}
```

### Scenario 3: Testing with Minimal Assertion
```python
# Use saml-minimal.xml for quick tests
parameters = {
    'issuer': 'https://test-idp.example.com',
    'subject': 'test-user',
    'audience': 'https://test-sp.example.com'
}
```

## Creating Custom SAML Templates

1. **Copy an existing template:**
   ```bash
   cp templates/saml-template.xml templates/my-saml.xml
   ```

2. **Edit the template** (add/remove attributes)

3. **Validate:**
   ```python
   from pathlib import Path
   from ihe_test_util.saml.template_loader import (
       load_saml_template,
       validate_saml_template,
       extract_saml_placeholders
   )
   
   template = load_saml_template(Path("templates/my-saml.xml"))
   validation = validate_saml_template(template)
   
   if validation.is_valid:
       placeholders = extract_saml_placeholders(template)
       print(f"Valid template with placeholders: {placeholders}")
   else:
       print(f"Validation errors: {validation.errors}")
   ```

4. **Test with sample data:**
   ```python
   from ihe_test_util.saml.template_loader import personalize_saml_template
   
   params = {'issuer': 'test', 'subject': 'user', 'audience': 'sp'}
   saml_xml = personalize_saml_template(
       Path("templates/my-saml.xml"),
       params
   )
   ```

## Standards Compliance

✅ **SAML 2.0** - Follows OASIS SAML 2.0 specification
✅ **XML Namespaces** - Proper urn:oasis:names:tc:SAML:2.0:assertion namespace
✅ **Assertion ID Format** - Valid XML ID type (starts with letter or underscore)
✅ **Timestamp Format** - ISO 8601 with Z suffix (UTC)
✅ **UTF-8 Encoding** - Proper character encoding
✅ **Bearer Confirmation** - Subject confirmation for bearer tokens
✅ **Audience Restriction** - Conditions with audience validation

## Related Files

- `src/ihe_test_util/saml/template_loader.py` - SAML template processing
- `src/ihe_test_util/saml/certificate_manager.py` - Certificate loading (Story 4.1)
- `tests/fixtures/test_saml_template.xml` - Test template fixture
- `tests/unit/test_saml_template.py` - Unit tests
- `tests/integration/test_saml_workflow.py` - Integration tests

## Documentation

📖 **SAML Guide:** [docs/saml-guide.md](../docs/saml-guide.md) (if available)
- SAML 2.0 overview
- Template customization guide
- Integration with IHE transactions

## Support

For issues or questions:
- Review the integration tests: `tests/integration/test_saml_workflow.py`
- Check Story 4.2 documentation: `docs/stories/4.2.template-based-saml-generation.md`
- See related Story 4.1 (Certificate Management)

---

**SAML Templates Version:** 1.0 (Story 4.2)  
**Last Updated:** 2025-11-11  
**Related Stories:** 4.1 (Certificate Management), 4.2 (Template-Based SAML)
