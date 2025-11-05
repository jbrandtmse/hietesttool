# CSV Format Specification

This document describes the CSV file format for patient demographics used by the IHE Test Utility.

## Overview

The CSV parser validates patient demographic data and prepares it for IHE transactions (PIX Add, ITI-41). The parser supports both required and optional fields, performs comprehensive validation, and can automatically generate patient IDs when not provided.

## Required Columns

The following columns **must** be present in every CSV file:

| Column | Type | Format | Description | Example |
|--------|------|--------|-------------|---------|
| `first_name` | String | UTF-8 text | Patient's first/given name | `John` |
| `last_name` | String | UTF-8 text | Patient's last/family name | `Doe` |
| `dob` | Date | `YYYY-MM-DD` | Date of birth | `1980-01-15` |
| `gender` | String | `M`, `F`, `O`, `U` | Gender (case-insensitive) | `M` |
| `patient_id_oid` | String | OID format | Patient ID OID/domain | `1.2.3.4.5` |

### Required Column Notes

- **dob**: Must be in ISO 8601 date format (`YYYY-MM-DD`). Dates before 1900 will be rejected. Future dates generate a warning but are accepted.
- **gender**: Accepts `M` (Male), `F` (Female), `O` (Other), `U` (Unknown). Values are case-insensitive and normalized to uppercase.
- **patient_id_oid**: Required for all patients. This OID identifies the patient ID domain and is never auto-generated.

## Optional Columns

The following columns are optional and can be included for richer patient data:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `patient_id` | String | Patient identifier (auto-generated if missing) | `PAT-12345` or `TEST-{UUID}` |
| `mrn` | String | Medical Record Number | `MRN-001` |
| `ssn` | String | Social Security Number | `123-45-6789` |
| `address` | String | Street address | `123 Main St, Apt 4` |
| `city` | String | City | `San Francisco` |
| `state` | String | State/province | `CA` |
| `zip` | String | Postal code | `94102` |
| `phone` | String | Phone number | `555-1234` |
| `email` | String | Email address | `john.doe@example.com` |

## Patient ID Auto-Generation

### Overview

The parser can automatically generate unique patient IDs for rows where `patient_id` is missing or empty. This feature simplifies test data creation by eliminating the need to manually assign IDs.

### ID Format

Auto-generated patient IDs follow the format:

```
TEST-{UUID}
```

Where `{UUID}` is a standard UUID v4 (36 characters: 8-4-4-4-12 hexadecimal).

**Example:** `TEST-a1b2c3d4-e5f6-7890-abcd-ef1234567890`

### When IDs Are Generated

Patient IDs are auto-generated in the following cases:

1. The `patient_id` column is missing from the CSV entirely
2. The `patient_id` value is empty (blank cell)
3. The `patient_id` value contains only whitespace

### Deterministic Generation (Seed Parameter)

The parser supports a `seed` parameter for deterministic ID generation, enabling reproducible test data:

```python
from pathlib import Path
from ihe_test_util.csv_parser.parser import parse_csv

# Generate deterministic IDs (same seed = same IDs)
df = parse_csv(Path("patients.csv"), seed=42)
```

**Use Cases for Seeds:**
- Automated testing requiring consistent patient IDs across runs
- Generating reproducible test datasets
- Debugging and troubleshooting with predictable data

**Without a seed**, IDs are randomly generated and will differ each time the CSV is parsed.

### Mixed Scenarios

CSV files can contain a mix of:
- Provided patient IDs (preserved as-is)
- Empty patient IDs (auto-generated)
- Missing `patient_id` column (all IDs auto-generated)

**Example CSV with mixed IDs:**

```csv
first_name,last_name,dob,gender,patient_id_oid,patient_id
John,Doe,1980-01-01,M,1.2.3.4,
Jane,Smith,1975-05-15,F,1.2.3.4,PROVIDED-123
Bob,Jones,1990-10-20,M,1.2.3.4,
```

**Result:**
- Row 1 (John): Auto-generated `TEST-{UUID}`
- Row 2 (Jane): Preserved `PROVIDED-123`
- Row 3 (Bob): Auto-generated `TEST-{UUID}` (different from Row 1)

### Important Notes

- **patient_id_oid is always required**: Even when `patient_id` is auto-generated, you must provide `patient_id_oid`
- **Uniqueness**: Generated IDs are unique within a batch (single parse operation)
- **Logging**: All generated and provided IDs are logged for audit purposes

## CSV Format Requirements

### Encoding

- **Required encoding**: UTF-8
- UTF-8 special characters are fully supported (é, ñ, ü, etc.)

### Delimiters

- **Column delimiter**: Comma (`,`)
- **Quote character**: Double quote (`"`) for fields containing commas or quotes

### Header Row

- First row must contain column names
- Column names are case-sensitive
- Unknown columns generate a warning but do not cause failure

### Data Rows

- Each row represents one patient
- Empty optional fields are allowed
- Missing required field values cause validation errors

## Example CSV Files

### Minimal Valid CSV (All Required Fields)

```csv
first_name,last_name,dob,gender,patient_id_oid
John,Doe,1980-01-15,M,1.2.3.4.5
Jane,Smith,1975-06-20,F,1.2.3.4.6
```

### CSV with Optional Fields

```csv
first_name,last_name,dob,gender,patient_id_oid,patient_id,mrn,email
John,Doe,1980-01-15,M,1.2.3.4.5,PAT001,MRN001,john@example.com
Jane,Smith,1975-06-20,F,1.2.3.4.6,PAT002,MRN002,jane@example.com
```

### CSV with Auto-Generated IDs

```csv
first_name,last_name,dob,gender,patient_id_oid,patient_id
John,Doe,1980-01-15,M,1.2.3.4.5,
Jane,Smith,1975-06-20,F,1.2.3.4.6,
```

**Note:** Empty `patient_id` values will be auto-generated as `TEST-{UUID}`.

### CSV without patient_id Column

```csv
first_name,last_name,dob,gender,patient_id_oid
John,Doe,1980-01-15,M,1.2.3.4.5
Jane,Smith,1975-06-20,F,1.2.3.4.6
```

**Note:** The `patient_id` column will be created automatically with generated IDs.

### CSV with UTF-8 Special Characters

```csv
first_name,last_name,dob,gender,patient_id_oid,patient_id
José,García,1980-01-15,M,1.2.3.4.5,PAT001
François,O'Neill,1975-06-20,F,1.2.3.4.6,PAT002
Müller,Schmidt-Weber,1990-03-10,O,1.2.3.4.7,PAT003
```

### CSV with Commas in Fields

```csv
first_name,last_name,dob,gender,patient_id_oid,address
John,Doe,1980-01-15,M,1.2.3.4.5,"123 Main St, Apt 4"
Jane,Smith,1975-06-20,F,1.2.3.4.6,"456 Oak Ave, Suite 200"
```

## Validation Rules

### Date of Birth (dob)

- **Format**: `YYYY-MM-DD` (ISO 8601)
- **Minimum year**: 1900 (earlier dates rejected)
- **Future dates**: Warning logged but accepted
- **Invalid format**: Error with example of correct format

**Valid:** `1980-01-15`, `2024-12-31`  
**Invalid:** `01/15/1980`, `1980-1-15`, `1850-01-01`

### Gender

- **Valid values**: `M`, `F`, `O`, `U` (case-insensitive)
- Automatically normalized to uppercase
- Invalid values cause validation error

**Valid:** `M`, `m`, `F`, `f`, `O`, `o`, `U`, `u`  
**Invalid:** `Male`, `X`, `1`, `Unknown`

### Patient ID OID

- Always required (even when patient_id is auto-generated)
- Typically in OID format (e.g., `1.2.3.4.5`)
- No strict format validation (allows flexibility for different domains)

## Error Handling

### Validation Errors

The parser collects all validation errors and reports them together:

```
Found 3 validation error(s) in CSV:
  - Row 2: Missing required field 'dob'. Expected format: YYYY-MM-DD
  - Row 3: Invalid gender 'X'. Must be one of: M, F, O, U (case-insensitive)
  - Row 4: Invalid date format '01/15/1980'. Expected format: YYYY-MM-DD (e.g., 1980-01-15)
```

### File Errors

- **File not found**: Clear error message with file path
- **Invalid CSV format**: Error with encoding/format details
- **Missing required columns**: List of missing columns with required columns reference

## Usage Example

```python
from pathlib import Path
from ihe_test_util.csv_parser.parser import parse_csv

# Parse CSV with auto-generated IDs (random)
df = parse_csv(Path("patients.csv"))

# Parse CSV with deterministic IDs (reproducible)
df = parse_csv(Path("patients.csv"), seed=42)

# Access data
for idx, row in df.iterrows():
    patient_id = row["patient_id"]  # Either provided or auto-generated
    patient_id_oid = row["patient_id_oid"]  # Always present
    first_name = row["first_name"]
    # ... process patient data
```

## Logging

The parser logs comprehensive information:

- **INFO**: CSV loading, validation start, successful parsing, ID generation summary
- **WARNING**: Unknown columns, future dates of birth
- **ERROR**: Validation failures, file not found

**ID Generation Logging Example:**

```
INFO: Loading CSV from patients.csv
INFO: Using seed 42 for deterministic ID generation
INFO: Validating CSV structure and data
INFO: Starting patient ID generation for batch
INFO: Generated patient ID TEST-a1b2c3d4-e5f6-7890-abcd-ef1234567890 for row 2
INFO: Using provided patient ID PAT001 for row 3
INFO: Generated patient ID TEST-b2c3d4e5-f6a7-8901-bcde-f12345678901 for row 4
INFO: ID generation summary: 2 generated, 1 provided
INFO: Successfully parsed 3 patient record(s)
```

## Best Practices

1. **Always include all required columns** even if some values will be auto-generated
2. **Use UTF-8 encoding** to support international characters
3. **Use consistent date format** (YYYY-MM-DD) throughout your CSV
4. **Provide patient_id_oid** for all patients (never leave empty)
5. **Use seeds for testing** when you need reproducible test data
6. **Quote fields with commas** to avoid parsing issues
7. **Review parser logs** for warnings about data quality issues

## Troubleshooting

### "Missing required columns" Error

**Cause:** CSV is missing one or more required columns.  
**Solution:** Ensure your CSV has: `first_name`, `last_name`, `dob`, `gender`, `patient_id_oid`

### "Invalid date format" Error

**Cause:** Date is not in YYYY-MM-DD format.  
**Solution:** Convert dates to ISO format (e.g., `1980-01-15` not `01/15/1980`)

### "Invalid gender" Error

**Cause:** Gender value is not M, F, O, or U.  
**Solution:** Use only valid gender codes (case-insensitive)

### All Patient IDs Are Generated

**Cause:** `patient_id` column missing or all values empty.  
**Solution:** This is expected behavior. If you want to provide IDs, add non-empty values to the `patient_id` column.

### Generated IDs Differ Between Runs

**Cause:** No seed parameter provided to parser.  
**Solution:** Use `parse_csv(file_path, seed=42)` for deterministic generation.

## See Also

- [Architecture Documentation](architecture.md) - Overall system architecture
- [PRD](prd.md) - Product requirements and specifications
- [Test Strategy](architecture/test-strategy-and-standards.md) - Testing approach and standards
