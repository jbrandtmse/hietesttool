# Quick Start Guide: Your First Personalized CCD

This guide walks you through creating your first personalized Continuity of Care Document (CCD) using the IHE Test Utility's template engine.

## Prerequisites

### Required Software

- Python 3.10 or higher
- IHE Test Utility installed (from Epic 1-3)

### Verify Installation

```bash
# Check Python version
python --version  # Should be 3.10+

# Verify IHE Test Utility is installed
python -c "from ihe_test_util.template_engine import CCDPersonalizer; print('✓ Ready')"
```

### Required Files

The following files should already exist in your project:

- `templates/ccd-minimal.xml` - The minimal CCD template
- `examples/patients_sample.csv` - Sample patient data

## Step 1: Choose a Template

For this tutorial, we'll use the **minimal template** which includes only required patient demographics.

**File:** `templates/ccd-minimal.xml`

**What it includes:**
- Document header with metadata
- Patient demographics (name, DOB, gender, ID)
- Document author and custodian
- Empty clinical sections

**Preview the template:**

```bash
cat templates/ccd-minimal.xml
```

You'll see placeholders like `{{patient_id}}`, `{{first_name}}`, etc.

## Step 2: Prepare Patient Data

Create a CSV file with patient information or use the provided sample.

### Using the Sample CSV

The project includes a sample CSV with diverse patient data:

```bash
head -n 3 examples/patients_sample.csv
```

**Expected format:**
```csv
patient_id,patient_id_oid,first_name,last_name,dob,gender,mrn,ssn,address,city,state,zip,phone,email
P001,2.16.840.1.113883.4.357,John,Doe,1980-05-15,M,MRN001,123-45-6789,123 Main St,Springfield,IL,62701,555-123-4567,john.doe@example.com
P002,2.16.840.1.113883.4.357,Jane,Smith,1975-08-22,F,MRN002,234-56-7890,456 Oak Ave,Chicago,IL,60601,555-234-5678,jane.smith@example.com
```

### Creating Your Own CSV

**Minimum required fields:**
- `patient_id` - Patient identifier (e.g., "P001")
- `patient_id_oid` - OID for patient ID domain (e.g., "2.16.840.1.113883.4.357")
- `first_name` - Patient's first name
- `last_name` - Patient's last name
- `dob` - Date of birth (format: YYYY-MM-DD)
- `gender` - Gender code: M, F, O, or U

**Example minimal CSV:**

```csv
patient_id,patient_id_oid,first_name,last_name,dob,gender
P001,2.16.840.1.113883.4.357,John,Doe,1980-05-15,M
P002,2.16.840.1.113883.4.357,Jane,Smith,1975-08-22,F
```

Save this as `my-patients.csv`.

## Step 3: Validate the Template

Before personalizing, let's verify the template is valid:

### Option A: Using Python (Recommended)

```python
from pathlib import Path
from ihe_test_util.template_engine import (
    TemplateLoader,
    validate_xml,
    extract_placeholders,
    validate_ccd_placeholders
)

# Load the template
template_path = Path("templates/ccd-minimal.xml")
loader = TemplateLoader()
template_content = loader.load_from_file(template_path)

# Validate XML structure
try:
    validate_xml(template_content)
    print("✓ Template is well-formed XML")
except Exception as e:
    print(f"✗ XML validation failed: {e}")

# Extract and validate placeholders
placeholders = extract_placeholders(template_content)
print(f"✓ Found {len(placeholders)} placeholders: {placeholders}")

is_valid, missing = validate_ccd_placeholders(placeholders)
if is_valid:
    print("✓ All required CCD placeholders present")
else:
    print(f"✗ Missing required placeholders: {missing}")
```

Save this as `validate_template.py` and run:

```bash
python validate_template.py
```

**Expected output:**
```
✓ Template is well-formed XML
✓ Found 8 placeholders: {'patient_id', 'patient_id_oid', 'first_name', 'last_name', 'dob', 'gender', 'document_id', 'creation_timestamp'}
✓ All required CCD placeholders present
```

### Option B: Using lxml directly

```bash
python -c "from lxml import etree; etree.parse('templates/ccd-minimal.xml'); print('✓ Valid XML')"
```

## Step 4: Personalize the Template

Now we'll personalize the template with actual patient data.

### Single Patient Personalization

```python
from pathlib import Path
from ihe_test_util.template_engine import CCDPersonalizer
from ihe_test_util.csv_parser import parse_csv

# Load patient data from CSV
csv_path = Path("examples/patients_sample.csv")
df = parse_csv(csv_path)

print(f"Loaded {len(df)} patients from CSV")

# Initialize the personalizer
personalizer = CCDPersonalizer()

# Personalize template for the first patient
template_path = Path("templates/ccd-minimal.xml")
ccd_document = personalizer.personalize_from_dataframe_row(
    template_path=template_path,
    patient_row=df.iloc[0]  # First patient
)

# Display results
print(f"\n✓ Successfully generated CCD document!")
print(f"  Document ID: {ccd_document.document_id}")
print(f"  Patient ID: {ccd_document.patient_id}")
print(f"  Created: {ccd_document.creation_timestamp}")
print(f"  Size: {ccd_document.size_bytes} bytes")
print(f"  SHA256: {ccd_document.sha256_hash[:16]}...")
```

Save this as `personalize_single.py` and run:

```bash
python personalize_single.py
```

**Expected output:**
```
Loaded 30 patients from CSV

✓ Successfully generated CCD document!
  Document ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Patient ID: P001
  Created: 2025-11-10 13:18:00
  Size: 2847 bytes
  SHA256: f4d2c8b9a1e3c7d6...
```

### Batch Personalization

To personalize templates for multiple patients:

```python
from pathlib import Path
from ihe_test_util.template_engine import CCDPersonalizer
from ihe_test_util.csv_parser import parse_csv

# Load patient data
csv_path = Path("examples/patients_sample.csv")
df = parse_csv(csv_path)

# Initialize personalizer
personalizer = CCDPersonalizer()
template_path = Path("templates/ccd-minimal.xml")

# Process all patients
ccd_documents = []
for index, patient_row in df.iterrows():
    ccd = personalizer.personalize_from_dataframe_row(
        template_path=template_path,
        patient_row=patient_row
    )
    ccd_documents.append(ccd)
    print(f"✓ Generated CCD for {patient_row['first_name']} {patient_row['last_name']}")

print(f"\n✓ Total documents generated: {len(ccd_documents)}")
```

Save this as `personalize_batch.py` and run:

```bash
python personalize_batch.py
```

## Step 5: Verify the Output

Let's verify the generated CCD document is valid and contains the correct data.

```python
from pathlib import Path
from ihe_test_util.template_engine import CCDPersonalizer, validate_xml
from ihe_test_util.csv_parser import parse_csv

# Generate a document (same as Step 4)
csv_path = Path("examples/patients_sample.csv")
df = parse_csv(csv_path)

personalizer = CCDPersonalizer()
template_path = Path("templates/ccd-minimal.xml")
ccd = personalizer.personalize_from_dataframe_row(template_path, df.iloc[0])

# Verify the XML is valid
try:
    validate_xml(ccd.xml_content)
    print("✓ Generated XML is well-formed")
except Exception as e:
    print(f"✗ XML validation failed: {e}")

# Check that placeholders were replaced
patient_row = df.iloc[0]
expected_values = {
    "patient_id": patient_row["patient_id"],
    "first_name": patient_row["first_name"],
    "last_name": patient_row["last_name"]
}

for field, expected in expected_values.items():
    placeholder = f"{{{{{field}}}}}"
    if placeholder in ccd.xml_content:
        print(f"✗ Placeholder {placeholder} was not replaced!")
    else:
        print(f"✓ {field} = {expected}")

# Verify document metadata was auto-generated
assert ccd.document_id, "✗ Document ID not generated"
assert ccd.creation_timestamp, "✗ Creation timestamp not generated"
print(f"✓ Document metadata auto-generated")
print(f"  ID: {ccd.document_id}")
print(f"  Timestamp: {ccd.creation_timestamp}")

# Save the document to file for inspection
output_path = Path("output_ccd.xml")
output_path.write_text(ccd.xml_content, encoding="utf-8")
print(f"\n✓ Saved personalized CCD to: {output_path}")
```

Save this as `verify_output.py` and run:

```bash
python verify_output.py
```

**Expected output:**
```
✓ Generated XML is well-formed
✓ patient_id = P001
✓ first_name = John
✓ last_name = Doe
✓ Document metadata auto-generated
  ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Timestamp: 2025-11-10 13:18:00

✓ Saved personalized CCD to: output_ccd.xml
```

### Inspect the Generated Document

Open the generated document in a text editor:

```bash
cat output_ccd.xml | head -n 30
```

You should see:
- XML declaration: `<?xml version="1.0" encoding="UTF-8"?>`
- ClinicalDocument root element with namespaces
- Document ID with the auto-generated UUID
- effectiveTime with the timestamp
- recordTarget section with patient demographics
- Patient name, DOB, and gender filled in

## Step 6: Using the Comprehensive Template

Now let's try the comprehensive template with clinical sections.

```python
from pathlib import Path
from ihe_test_util.template_engine import CCDPersonalizer
from ihe_test_util.csv_parser import parse_csv

# Load patient data
csv_path = Path("examples/patients_sample.csv")
df = parse_csv(csv_path)

# Use the COMPREHENSIVE template
personalizer = CCDPersonalizer()
template_path = Path("templates/ccd-template.xml")  # Note: ccd-template.xml

ccd = personalizer.personalize_from_dataframe_row(
    template_path=template_path,
    patient_row=df.iloc[0]
)

print(f"✓ Generated comprehensive CCD document")
print(f"  Size: {ccd.size_bytes} bytes (larger due to clinical sections)")

# Save to file
output_path = Path("output_ccd_comprehensive.xml")
output_path.write_text(ccd.xml_content, encoding="utf-8")
print(f"✓ Saved to: {output_path}")

# Count the sections
sections = ccd.xml_content.count("<section>")
print(f"✓ Document contains {sections} clinical sections")
print("  (Allergies, Medications, Problems, Procedures)")
```

Save as `comprehensive_example.py` and run:

```bash
python comprehensive_example.py
```

## Troubleshooting

### Error: "Missing required placeholders"

**Problem:** Template is missing required fields like `patient_id` or `dob`.

**Solution:** Ensure your template includes all required placeholders:
```
{{patient_id}}, {{patient_id_oid}}, {{first_name}}, {{last_name}}, {{dob}}, {{gender}}
```

### Error: "Invalid OID format"

**Problem:** The `patient_id_oid` value doesn't match the expected format.

**Solution:** Use a valid OID format (numbers separated by dots):
```
2.16.840.1.113883.4.357
```

### Error: "FileNotFoundError: Template not found"

**Problem:** The template file path is incorrect.

**Solution:** Use `Path` objects and verify the file exists:
```python
from pathlib import Path
template_path = Path("templates/ccd-minimal.xml")
assert template_path.exists(), f"Template not found: {template_path}"
```

### Placeholders Not Replaced

**Problem:** Output XML still contains `{{field_name}}` placeholders.

**Solution:** Check that your CSV has columns matching the placeholder names:
```python
# Check CSV columns
df = parse_csv(Path("my-patients.csv"))
print(f"CSV columns: {list(df.columns)}")

# Must include: patient_id, patient_id_oid, first_name, last_name, dob, gender
```

### XML Special Characters Error

**Problem:** Patient names with apostrophes or special characters cause errors.

**Solution:** The engine automatically escapes XML characters. If you see this error, it's likely a bug. Example that should work:
```csv
patient_id,first_name,last_name,...
P001,John,O'Brien,...
P002,María,García,...
```

## Next Steps

Now that you've successfully created personalized CCD documents:

1. **Try with your own data**: Create a CSV with your test patients
2. **Customize templates**: Learn to add custom sections (see [ccd-templates.md](ccd-templates.md#creating-custom-templates))
3. **Batch processing**: Process larger datasets (100+ patients)
4. **Integration testing**: Use generated CCDs in ITI-41 transactions (Epic 6)
5. **Explore the comprehensive template**: Add medications, problems, and allergies data

## Additional Resources

- **[CCD Template Documentation](ccd-templates.md)** - Comprehensive template reference
- **[CSV Format Specification](csv-format.md)** - Patient data format details
- **[Template Validation Checklist](ccd-templates.md#template-validation-checklist)** - Verify custom templates
- **[Troubleshooting Guide](ccd-templates.md#common-issues--troubleshooting)** - Common issues and solutions

## Complete Working Example

Here's a complete, ready-to-run script combining all the steps:

```python
#!/usr/bin/env python3
"""
Complete example: Generate personalized CCD documents from CSV data.
"""

from pathlib import Path
from ihe_test_util.template_engine import CCDPersonalizer, validate_xml
from ihe_test_util.csv_parser import parse_csv


def main():
    # Configuration
    template_path = Path("templates/ccd-minimal.xml")
    csv_path = Path("examples/patients_sample.csv")
    output_dir = Path("output_ccds")
    output_dir.mkdir(exist_ok=True)
    
    # Load patient data
    print(f"Loading patient data from {csv_path}...")
    df = parse_csv(csv_path)
    print(f"✓ Loaded {len(df)} patients")
    
    # Initialize personalizer
    personalizer = CCDPersonalizer()
    
    # Process each patient
    for index, patient_row in df.iterrows():
        # Generate CCD
        ccd = personalizer.personalize_from_dataframe_row(
            template_path=template_path,
            patient_row=patient_row
        )
        
        # Validate output
        validate_xml(ccd.xml_content)
        
        # Save to file
        patient_id = patient_row["patient_id"]
        output_file = output_dir / f"{patient_id}_ccd.xml"
        output_file.write_text(ccd.xml_content, encoding="utf-8")
        
        print(f"✓ {patient_id}: {patient_row['first_name']} {patient_row['last_name']} "
              f"-> {output_file} ({ccd.size_bytes} bytes)")
    
    print(f"\n✓ Successfully generated {len(df)} CCD documents in {output_dir}/")


if __name__ == "__main__":
    main()
```

Save as `generate_ccds.py` and run:

```bash
python generate_ccds.py
```

You now have personalized CCD documents for all patients in your CSV file!

---

**Version:** 1.0  
**Last Updated:** 2025-11-10  
**Related Documentation:** [ccd-templates.md](ccd-templates.md), [csv-format.md](csv-format.md)
