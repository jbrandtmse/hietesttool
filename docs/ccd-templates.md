# CCD Template Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [HL7 CCDA R2.1 Overview](#hl7-ccda-r21-overview)
3. [Placeholder Reference](#placeholder-reference)
4. [Template Files](#template-files)
5. [Creating Custom Templates](#creating-custom-templates)
6. [Template Validation Checklist](#template-validation-checklist)
7. [Common Issues & Troubleshooting](#common-issues--troubleshooting)

---

## Introduction

### What are CCD Templates?

**CCD (Continuity of Care Document)** templates are XML-based document structures that follow the HL7 Clinical Document Architecture (CDA) Release 2.1 standard. These templates provide a structured format for representing patient clinical information in a standardized, interoperable manner.

### Why Use Templates?

Templates provide several key benefits:

- **Consistency**: Ensures all generated documents follow the same structure
- **Compliance**: Adheres to HL7 CCDA R2.1 standards for healthcare interoperability
- **Efficiency**: Enables batch processing of patient data through placeholder substitution
- **Flexibility**: Allows customization while maintaining standards compliance
- **Testing**: Facilitates IHE transaction testing with consistent, valid clinical documents

### Template Engine Overview

The IHE Test Utility includes a complete template processing pipeline implemented in Stories 3.1-3.3:

**Story 3.1: XML Template Loader & Validator**
- Loads templates from XML files
- Validates XML well-formedness
- Extracts placeholder definitions
- Caches templates for performance

**Story 3.2: String Replacement Engine**
- Replaces `{{field_name}}` placeholders with actual values
- Automatically formats dates to HL7 format (YYYYMMDD)
- Automatically escapes XML special characters (&, <, >, ", ')
- Validates OID formats
- Handles missing values with configurable strategies

**Story 3.3: CCD Template Personalization**
- Integrates loader and replacement engine
- Works with CSV patient data (from Epic 1)
- Auto-generates document IDs and timestamps
- Returns complete CCDDocument objects
- Supports batch processing

---

## HL7 CCDA R2.1 Overview

### Document Structure

Every CCDA document follows a hierarchical structure with two primary components:

```
ClinicalDocument (root)
├── Header (administrative metadata)
│   ├── Document ID
│   ├── Document Type
│   ├── Effective Time
│   ├── Confidentiality Code
│   ├── recordTarget (patient demographics)
│   ├── author (document creator)
│   └── custodian (responsible organization)
└── Body (clinical content)
    └── structuredBody
        └── component (repeatable)
            └── section (clinical sections)
                ├── code (LOINC code)
                ├── title
                ├── text (human-readable)
                └── entry (structured data)
```

### Required vs Optional Sections

**REQUIRED Elements (must be present in all documents):**
- Document ID (`<id>`)
- Document creation time (`<effectiveTime>`)
- Document code (`<code>`)
- Confidentiality code (`<confidentialityCode>`)
- recordTarget (patient demographics)
- author (document creator)
- custodian (responsible organization)

**OPTIONAL Sections (commonly included):**
- Allergies and Intolerances
- Medications
- Problem List
- Procedures
- Immunizations
- Vital Signs
- Lab Results

### Namespace Requirements

All CCDA documents must declare the HL7 CDA namespace:

```xml
<ClinicalDocument xmlns="urn:hl7-org:v3" 
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xmlns:sdtc="urn:hl7-org:sdtc">
```

**Namespace Breakdown:**
- `xmlns="urn:hl7-org:v3"` - Default namespace for all CDA elements
- `xmlns:xsi` - XML Schema instance namespace for validation
- `xmlns:sdtc` - HL7 Structured Document Work Group extensions

### LOINC Codes for Common Sections

LOINC (Logical Observation Identifiers Names and Codes) are used to identify clinical sections:

| Section | LOINC Code | Display Name |
|---------|------------|--------------|
| Allergies | 48765-2 | Allergies, Adverse Reactions, Alerts |
| Medications | 10160-0 | History of Medication Use |
| Problems | 11450-4 | Problem List |
| Procedures | 47519-4 | History of Procedures |
| Immunizations | 11369-6 | History of Immunization |
| Vital Signs | 8716-3 | Vital Signs |
| Lab Results | 30954-2 | Relevant Diagnostic Tests/Laboratory Data |

---

## Placeholder Reference

### Overview

Placeholders use the format `{{field_name}}` and are replaced with actual patient data during personalization. All placeholders are case-sensitive and must match the field names from the `PatientDemographics` model.

### Required Placeholders

These placeholders **MUST** have values or personalization will fail:

| Placeholder | Data Type | Description | Example Value |
|-------------|-----------|-------------|---------------|
| `{{patient_id}}` | String | Patient identifier | "P123456" |
| `{{patient_id_oid}}` | String (OID) | OID for patient ID domain | "2.16.840.1.113883.4.357" |
| `{{first_name}}` | String | Patient first/given name | "John" |
| `{{last_name}}` | String | Patient family/last name | "Doe" |
| `{{dob}}` | Date | Date of birth | "1980-05-15" → "19800515" |
| `{{gender}}` | String | Gender code | "M", "F", "O", "U" |
| `{{document_id}}` | String (UUID) | Unique document identifier | Auto-generated |
| `{{creation_timestamp}}` | DateTime | Document creation time | Auto-generated |

### Optional Placeholders

These placeholders are optional and will be replaced with empty strings if not provided:

| Placeholder | Data Type | Description | Example Value |
|-------------|-----------|-------------|---------------|
| `{{mrn}}` | String | Medical record number | "MRN-789012" |
| `{{ssn}}` | String | Social security number | "123-45-6789" |
| `{{address}}` | String | Street address | "123 Main St" |
| `{{city}}` | String | City name | "Springfield" |
| `{{state}}` | String | State code (2-letter) | "IL" |
| `{{zip}}` | String | ZIP/Postal code | "62701" |
| `{{phone}}` | String | Phone number | "555-123-4567" |
| `{{email}}` | String | Email address | "john.doe@example.com" |

### Automatic Formatting

The template engine automatically formats certain field types:

**Date Fields:**
- Input: Python `datetime` or `date` object, or ISO string (YYYY-MM-DD)
- Output: HL7 format YYYYMMDD
- Example: `datetime(1980, 5, 15)` → `"19800515"`

**Timestamp Fields:**
- Input: Python `datetime` object
- Output: HL7 format YYYYMMDDHHmmss
- Example: `datetime(2025, 1, 9, 14, 30, 0)` → `"20250109143000"`

**XML Escaping:**
All string values are automatically escaped for XML:
- `&` → `&amp;`
- `<` → `&lt;`
- `>` → `&gt;`
- `"` → `&quot;`
- `'` → `&apos;`

**OID Validation:**
OID fields (like `patient_id_oid`) are validated to ensure proper format:
- Must match pattern: `^\d+(\.\d+)*$`
- Example valid OID: `"2.16.840.1.113883.4.357"`

### Document Metadata Fields

These fields are **automatically generated** by the personalization engine:

**`{{document_id}}`**
- Type: UUID4 string
- Purpose: Unique identifier for the document
- Auto-generated: Yes
- Format: Standard UUID (e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890")

**`{{creation_timestamp}}`**
- Type: DateTime string
- Purpose: Document creation timestamp
- Auto-generated: Yes
- Format: HL7 YYYYMMDDHHmmss (UTC timezone)
- Example: "20250109143000"

---

## Template Files

The IHE Test Utility provides two standard templates:

### ccd-template.xml - Comprehensive Template

**Location:** `templates/ccd-template.xml`

**Use When:**
- You need a complete clinical document
- You want to include medications, problems, and allergies sections
- You're simulating realistic clinical data exchange
- You need examples of optional sections

**Includes:**
- Complete document header with all metadata
- Patient demographics (recordTarget) with optional fields
- Document author and custodian information
- **Allergies and Intolerances section** (LOINC 48765-2)
- **Medications section** (LOINC 10160-0)
- **Problem List section** (LOINC 11450-4)
- **Procedures section** (LOINC 47519-4)
- Inline documentation and comments
- Example structures for entry templates

**Placeholder Count:** All required + all optional placeholders

### ccd-minimal.xml - Minimal Template

**Location:** `templates/ccd-minimal.xml`

**Use When:**
- You only need basic patient demographics
- You're testing core functionality without clinical sections
- You want the simplest valid CCDA document
- You're getting started with template personalization

**Includes:**
- Minimal document header
- Patient demographics (recordTarget) with required fields only
- Document author and custodian (required elements)
- Empty structured body (no clinical sections)

**Placeholder Count:** Only required placeholders

### When to Use Each Template

| Scenario | Recommended Template |
|----------|---------------------|
| Testing PIX Add + ITI-41 workflow | `ccd-minimal.xml` |
| Demonstrating full CCDA capabilities | `ccd-template.xml` |
| Batch processing 100+ patients | `ccd-minimal.xml` (faster) |
| Creating realistic test data | `ccd-template.xml` |
| Learning template structure | `ccd-minimal.xml` → `ccd-template.xml` |

---

## Creating Custom Templates

### Starting from an Existing Template

The easiest way to create a custom template is to start from one of the provided templates:

1. **Copy the template file:**
   ```bash
   cp templates/ccd-template.xml templates/my-custom-template.xml
   ```

2. **Edit the template** in your favorite XML editor

3. **Validate your changes** (see Validation Checklist below)

4. **Test with sample data** using the personalization engine

### Adding Custom Sections

To add a new clinical section to your template:

**Step 1: Identify the LOINC code for your section**

Example: Adding a "Procedures" section (LOINC 47519-4)

**Step 2: Add the section within `<structuredBody>`**

```xml
<component>
  <structuredBody>
    
    <!-- ... existing sections ... -->
    
    <!-- NEW PROCEDURES SECTION -->
    <component>
      <section>
        <!-- Template ID for Procedures Section -->
        <templateId root="2.16.840.1.113883.10.20.22.2.7.1" extension="2014-06-09"/>
        
        <!-- LOINC code identifying this section -->
        <code code="47519-4" 
              codeSystem="2.16.840.1.113883.6.1" 
              codeSystemName="LOINC" 
              displayName="History of Procedures"/>
        
        <!-- Human-readable title -->
        <title>Procedures</title>
        
        <!-- Human-readable content -->
        <text>
          <paragraph>No procedures on record.</paragraph>
        </text>
        
        <!-- Structured data entries would go here -->
      </section>
    </component>
    
  </structuredBody>
</component>
```

**Step 3: Add custom placeholders if needed**

If your custom section needs patient-specific data, add placeholders:

```xml
<text>
  <paragraph>Procedure performed: {{procedure_name}}</paragraph>
  <paragraph>Date: {{procedure_date}}</paragraph>
</text>
```

**Step 4: Update your data source**

Ensure your CSV or data dictionary includes the new fields:
```csv
patient_id,first_name,last_name,dob,gender,procedure_name,procedure_date
P001,John,Doe,1980-05-15,M,Appendectomy,2024-03-15
```

### Namespace Considerations

When adding sections from external standards (e.g., DICOM imaging):

**Step 1: Add the namespace declaration to the root element**

```xml
<ClinicalDocument xmlns="urn:hl7-org:v3" 
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xmlns:dicom="urn:dicom-org:ps3-20">
```

**Step 2: Use the namespace prefix in your elements**

```xml
<component>
  <section>
    <title>Imaging Studies</title>
    <text>
      <paragraph>Accession Number: <dicom:accessionNumber>{{accession_id}}</dicom:accessionNumber></paragraph>
    </text>
  </section>
</component>
```

### Example: Adding an Immunizations Section

Here's a complete example of adding an Immunizations section:

```xml
<component>
  <section>
    <!-- Immunizations Section Template -->
    <templateId root="2.16.840.1.113883.10.20.22.2.2.1" extension="2015-08-01"/>
    
    <!-- LOINC Code for Immunizations -->
    <code code="11369-6" 
          codeSystem="2.16.840.1.113883.6.1" 
          codeSystemName="LOINC" 
          displayName="History of Immunization"/>
    
    <title>Immunizations</title>
    
    <text>
      <table>
        <thead>
          <tr>
            <th>Vaccine</th>
            <th>Date</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{{vaccine_name}}</td>
            <td>{{vaccine_date}}</td>
            <td>{{vaccine_status}}</td>
          </tr>
        </tbody>
      </table>
    </text>
    
    <!-- Structured entries would include full immunization details -->
  </section>
</component>
```

---

## Template Validation Checklist

Use this checklist to verify your custom templates before using them in production:

### XML Structure Validation

- [ ] **Well-formed XML**: Template parses without errors
  - Test: `python -c "from lxml import etree; etree.fromstring(open('my-template.xml').read())"`
- [ ] **UTF-8 encoding**: File saved with UTF-8 encoding
  - Check: File starts with `<?xml version="1.0" encoding="UTF-8"?>`
- [ ] **Proper namespaces**: All required namespaces declared
  - Check: `xmlns="urn:hl7-org:v3"` present on root element

### Placeholder Validation

- [ ] **Required placeholders present**: All required fields included
  - Test using validator: `validate_ccd_placeholders(extract_placeholders(template_content))`
  - Required: `patient_id`, `patient_id_oid`, `first_name`, `last_name`, `dob`, `gender`
- [ ] **Placeholder format correct**: All use `{{field_name}}` format
  - Check: No `{field_name}` or `${field_name}` formats
- [ ] **Matching CSV fields**: All placeholders have corresponding CSV columns
  - Compare placeholder names with CSV header row

### HL7 CCDA Compliance

- [ ] **Valid document structure**: Follows CDA R2 hierarchy
  - Check: `<ClinicalDocument>` → `<component>` → `<structuredBody>` → `<component>` → `<section>`
- [ ] **Valid template IDs**: Template IDs match CCDA specification
  - Verify template IDs at [HL7 CDA Templates](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=447)
- [ ] **Valid LOINC codes**: Section codes are correct
  - Verify codes at [LOINC.org](https://loinc.org)
- [ ] **Valid OIDs**: All OID references use proper format
  - Format: `^\d+(\.\d+)*$`

### Testing with Sample Data

- [ ] **Single patient test**: Personalize with one patient record
  ```python
  from pathlib import Path
  from ihe_test_util.template_engine import CCDPersonalizer
  
  personalizer = CCDPersonalizer()
  template_path = Path("templates/my-custom-template.xml")
  
  patient_data = {
      "patient_id": "P001",
      "patient_id_oid": "2.16.840.1.113883.4.357",
      "first_name": "John",
      "last_name": "Doe",
      "dob": "1980-05-15",
      "gender": "M"
  }
  
  ccd = personalizer.personalize(template_path, patient_data)
  print(f"Generated document: {ccd.document_id}")
  ```

- [ ] **Validate output XML**: Ensure personalized document is valid
  ```python
  from ihe_test_util.template_engine import validate_xml
  validate_xml(ccd.xml_content)  # Should not raise exception
  ```

- [ ] **Batch processing test**: Test with multiple patients (e.g., 10 records)
- [ ] **Missing optional fields**: Test with minimal required fields only
- [ ] **Special characters**: Test with patient names containing XML special characters
  - Example: `O'Brien`, `Smith & Jones`, `García`

### CLI Validation Command

The CLI provides a validation command (implemented in future stories):

```bash
# Validate template structure
ihe-test-util template validate templates/my-custom-template.xml

# Test personalization with sample CSV
ihe-test-util template test templates/my-custom-template.xml examples/patients_sample.csv
```

---

## Common Issues & Troubleshooting

### Issue: "Malformed XML" Error

**Symptoms:**
```
lxml.etree.XMLSyntaxError: Opening and ending tag mismatch
```

**Common Causes:**
1. Unclosed XML tags
2. Mismatched opening/closing tags
3. Invalid XML characters in text content
4. Missing namespace declarations

**Solutions:**
- Use an XML validator or IDE with XML support
- Ensure all `<tag>` elements have matching `</tag>` closings
- Check for special characters in comments or text (use `&amp;`, `&lt;`, etc.)
- Validate with: `xmllint --noout my-template.xml` (if xmllint installed)

### Issue: "Missing Required Placeholder" Error

**Symptoms:**
```
ValidationError: Missing required placeholders: ['dob', 'gender']
```

**Common Causes:**
1. Required placeholder not present in template
2. Typo in placeholder name
3. Incorrect placeholder format

**Solutions:**
- Check that all required placeholders are present:
  - `{{patient_id}}`, `{{patient_id_oid}}`, `{{first_name}}`, `{{last_name}}`, `{{dob}}`, `{{gender}}`
- Verify placeholder format uses double curly braces: `{{field_name}}`
- Ensure placeholder names match exactly (case-sensitive)

### Issue: "Invalid OID Format" Error

**Symptoms:**
```
ValidationError: Invalid OID format for patient_id_oid: 'ABC.123'
```

**Common Causes:**
1. OID contains non-numeric characters
2. OID format doesn't match pattern

**Solutions:**
- Ensure OID uses only numbers and dots: `2.16.840.1.113883.4.357`
- Verify OID doesn't start or end with a dot
- Check that OID comes from a valid registry

### Issue: Placeholder Not Replaced in Output

**Symptoms:**
Output XML still contains `{{field_name}}` instead of actual value

**Common Causes:**
1. Field name mismatch between template and data source
2. Value is `None` or empty in data source
3. Using wrong personalization strategy

**Solutions:**
- Check CSV header matches placeholder name exactly
- For optional fields, use `MissingValueStrategy.USE_EMPTY` strategy
- Verify field is present in patient data dictionary:
  ```python
  print(patient_data.keys())  # Should include 'field_name'
  ```

### Issue: Date Format Error

**Symptoms:**
```
ValueError: Invalid date format for dob: '05/15/1980'
```

**Common Causes:**
1. Date format doesn't match expected ISO format
2. Date is provided as string instead of date object

**Solutions:**
- Use ISO format in CSV: `YYYY-MM-DD` (e.g., `1980-05-15`)
- Or use Python date objects: `datetime(1980, 5, 15).date()`
- The engine automatically converts to HL7 format (YYYYMMDD)

### Issue: Namespace Errors

**Symptoms:**
```
XMLSyntaxError: Namespace prefix dicom for accessionNumber on ... is not defined
```

**Common Causes:**
1. Using namespace prefix without declaring namespace
2. Typo in namespace URI
3. Missing namespace declaration on root element

**Solutions:**
- Add namespace declaration to `<ClinicalDocument>` element:
  ```xml
  <ClinicalDocument xmlns="urn:hl7-org:v3"
                    xmlns:dicom="urn:dicom-org:ps3-20">
  ```
- Ensure namespace prefix matches declaration
- Verify namespace URI is correct for the standard

### Issue: Template Not Found

**Symptoms:**
```
FileNotFoundError: Template not found: templates/my-template.xml
```

**Common Causes:**
1. Incorrect file path
2. File doesn't exist
3. Working directory is not project root

**Solutions:**
- Use absolute paths or Path objects:
  ```python
  from pathlib import Path
  template_path = Path(__file__).parent / "templates" / "my-template.xml"
  ```
- Verify file exists: `ls -l templates/my-template.xml`
- Check current working directory: `pwd`

### Getting Help

If you encounter issues not covered here:

1. **Check the logs**: Review application logs for detailed error messages
2. **Validate template**: Use the validation checklist above
3. **Test with minimal.xml**: Verify the engine works with the minimal template
4. **Review examples**: Check `examples/` directory for working examples
5. **Consult HL7 documentation**: [HL7 CDA Release 2.1](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=447)

---

## Quick Reference

### Template File Locations

```
templates/
├── ccd-template.xml     # Comprehensive template with clinical sections
├── ccd-minimal.xml      # Minimal template (demographics only)
└── README.md            # Quick start guide
```

### Related Documentation

- [Quick Start Guide](quickstart-templates.md) - Step-by-step tutorial
- [CSV Format Specification](csv-format.md) - Patient data format
- [Configuration Guide](configuration-guide.md) - System configuration
- [Architecture Documentation](architecture.md) - System design

### Key Python Imports

```python
from pathlib import Path
from ihe_test_util.template_engine import (
    TemplateLoader,
    TemplatePersonalizer,
    CCDPersonalizer,
    validate_xml,
    extract_placeholders,
    validate_ccd_placeholders
)
from ihe_test_util.csv_parser import parse_csv
```

### Quick Commands

```bash
# List available templates
ls -l templates/*.xml

# Validate template XML
python -c "from lxml import etree; etree.parse('templates/ccd-template.xml')"

# Test personalization (Python)
python -c "
from pathlib import Path
from ihe_test_util.template_engine import CCDPersonalizer
from ihe_test_util.csv_parser import parse_csv

df = parse_csv(Path('examples/patients_sample.csv'))
personalizer = CCDPersonalizer()
ccd = personalizer.personalize_from_dataframe_row(
    Path('templates/ccd-minimal.xml'), 
    df.iloc[0]
)
print(f'Success! Document ID: {ccd.document_id}')
"
```

---

**Version:** 1.0  
**Last Updated:** 2025-11-10  
**Related Stories:** 3.1 (Loader), 3.2 (Replacement), 3.3 (Personalization), 3.4 (Templates)
