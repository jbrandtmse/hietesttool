# CCD Templates

This directory contains HL7 CCDA R2.1 (Continuity of Care Document) templates for generating personalized clinical documents.

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
