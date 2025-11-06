# CSV Format Specification

## Introduction

This document defines the CSV format for patient demographic data used by the IHE Test Utility. The CSV format is used to import patient records for testing IHE transactions (PIX Add, ITI-41 document submission).

**Purpose:**
- Define patient demographics for IHE transaction testing
- Support both manual patient IDs and auto-generated IDs
- Enable batch processing of multiple patients

**Quick Links:**
- [Sample CSV Files](../examples/) - Example files to get started
- [Quick Start Guide](../README.md#quick-start) - Step-by-step tutorial

## CSV Format Basics

The CSV file must follow these standard rules:

- **Encoding:** UTF-8 without BOM (Byte Order Mark)
- **Header Row:** First row must contain column names (case-sensitive)
- **Line Endings:** LF (Unix-style) or CRLF (Windows-style) both accepted
- **Field Delimiter:** Comma (`,`)
- **Quoting:** Fields containing commas, quotes, or newlines must be enclosed in double quotes (`"`)
- **Special Characters:** Full Unicode support for international names (accents, diacritics, etc.)

**Standard CSV Format (RFC 4180):**
```csv
first_name,last_name,dob,gender,patient_id_oid
John,Doe,1980-01-15,M,2.16.840.1.113883.3.9999.1
"O'Brien, Mary",1985-06-20,F,2.16.840.1.113883.3.9999.1
```

## Required Columns

All CSV files must include these columns. Missing any required column will cause validation failure.

### first_name

- **Type:** String
- **Required:** Yes
- **Length:** 1-100 characters
- **Validation:** Cannot be empty
- **Unicode:** Full Unicode support (accents, diacritics)
- **Examples:** `John`, `José`, `François`, `Mary-Jane`

### last_name

- **Type:** String
- **Required:** Yes
- **Length:** 1-100 characters
- **Validation:** Cannot be empty
- **Unicode:** Full Unicode support
- **Examples:** `Doe`, `García`, `O'Brien`, `Müller`

### dob

- **Type:** Date
- **Required:** Yes
- **Format:** `YYYY-MM-DD` (ISO 8601)
- **Validation:** Must be a valid past date (not future)
- **Examples:** `1980-01-15`, `2010-03-15`, `1945-11-10`
- **Common Errors:**
  - ❌ `01/15/1980` (US format not accepted)
  - ❌ `15-01-1980` (DD-MM-YYYY not accepted)
  - ❌ `2030-01-15` (future date not accepted)
  - ✅ `1980-01-15` (correct format)

### gender

- **Type:** String (single character)
- **Required:** Yes
- **Allowed Values:**
  - `M` - Male
  - `F` - Female
  - `O` - Other
  - `U` - Unknown
- **Case:** Case-insensitive (both `M` and `m` accepted)
- **Examples:** `M`, `F`, `O`, `U`
- **Common Errors:**
  - ❌ `Male` (full word not accepted)
  - ❌ `X` (not a valid code)
  - ✅ `M` (correct single character)

### patient_id_oid

- **Type:** String (OID format)
- **Required:** Yes
- **Format:** Numeric dotted notation (e.g., `2.16.840.1.113883.3.9999.1`)
- **Validation:** Must be valid OID format (numbers and dots only)
- **Purpose:** Identifies the assigning authority/organization for the patient ID
- **Examples:** See [Common OID Values](#common-oid-values) section below
- **Common Errors:**
  - ❌ `12345` (not OID format)
  - ❌ `oid:2.16.840.1.113883.3.9999.1` (no prefix)
  - ✅ `2.16.840.1.113883.3.9999.1` (correct format)

## Optional Columns

These columns are optional. If not needed, they can be omitted from the CSV file entirely or left empty.

### patient_id

- **Type:** String
- **Required:** No
- **Auto-Generation:** If empty, automatically generated as `TEST-{UUID}`
- **Purpose:** Unique patient identifier within the assigning authority
- **Examples:** `PAT001`, `MRN-12345`, or empty for auto-generation
- **Note:** Auto-generated IDs are reproducible when using seed parameter

### mrn

- **Type:** String
- **Required:** No
- **Purpose:** Medical Record Number
- **Examples:** `MRN10001`, `123456789`

### ssn

- **Type:** String
- **Required:** No
- **Format:** Typically `XXX-XX-XXXX` but flexible
- **Validation:** Basic format check (9 digits with optional dashes)
- **Examples:** `111-11-1111`, `123456789`
- **Note:** Test data should use fake SSNs (e.g., `111-11-1111`)

### address

- **Type:** String
- **Required:** No
- **Purpose:** Street address
- **Examples:** `123 Main Street`, `"456 Oak Ave, Apt 2B"` (quoted if contains comma)

### city

- **Type:** String
- **Required:** No
- **Examples:** `Springfield`, `Los Angeles`

### state

- **Type:** String
- **Required:** No
- **Format:** 2-letter US state code (recommended but not enforced)
- **Examples:** `IL`, `CA`, `NY`

### zip

- **Type:** String
- **Required:** No
- **Format:** `XXXXX` or `XXXXX-XXXX`
- **Examples:** `62701`, `90001-1234`

### phone

- **Type:** String
- **Required:** No
- **Format:** Flexible (various phone formats accepted)
- **Examples:** `555-0100`, `(555) 123-4567`, `+1-555-123-4567`

### email

- **Type:** String
- **Required:** No
- **Validation:** Basic email format check (contains `@` and `.`)
- **Examples:** `john.doe@email.com`, `patient@example.org`

## Validation Rules

The CSV parser validates data according to these rules:

### Column Validation

- **Missing Required Columns:** Parser will fail if any required column is missing
- **Extra Columns:** Extra columns are ignored (allows for future extensibility)
- **Column Order:** Columns can appear in any order

### Data Type Validation

- **Date Format:** Must be `YYYY-MM-DD`, must be valid calendar date, must be in the past
- **Gender Codes:** Must be one of `M`, `F`, `O`, `U` (case-insensitive)
- **OID Format:** Must match numeric dotted notation pattern
- **Email Format:** If provided, must contain `@` and domain

### Patient ID Validation

- **Auto-Generation Trigger:** Empty `patient_id` column triggers auto-generation
- **Whitespace Handling:** Whitespace-only values treated as empty (triggers auto-generation)
- **Format:** Auto-generated IDs follow format `TEST-{UUID}` (e.g., `TEST-a1b2c3d4-e5f6-7890-abcd-ef1234567890`)

### Error Reporting

When validation fails, the parser provides:
- Clear error message indicating which row and column failed
- Specific validation rule that was violated
- Suggested fix for the error

## Common OID Values

OIDs (Object Identifiers) identify healthcare organizations and assigning authorities. Use these test OIDs for development and testing.

### Test OIDs (For Development)

| OID | Description | Use Case |
|-----|-------------|----------|
| `2.16.840.1.113883.3.9999.1` | Generic Test Organization A | General testing |
| `2.16.840.1.113883.3.9999.10` | Test Hospital A | Multi-facility testing |
| `2.16.840.1.113883.3.9999.20` | Test Clinic B | Multi-facility testing |

### Real-World OID Examples

| OID Prefix | Description |
|------------|-------------|
| `2.16.840.1.113883.4.1` | US Social Security Number |
| `2.16.840.1.113883.4.6` | US National Provider Identifier (NPI) |
| `1.2.840.114350.1.13.x.x.x` | Epic Systems patient identifiers |

### OID Resources

- **OID Registry:** [HL7 OID Registry](https://www.hl7.org/oid/index.cfm)
- **OID Format Spec:** Numeric dotted notation (e.g., `2.16.840.1.113883.3.9999.1`)
- **Custom OIDs:** For testing, use OIDs under `2.16.840.1.113883.3.9999.x`

## Examples

### Minimal Example (Required Columns Only)

File: `examples/patients_minimal.csv`

```csv
first_name,last_name,dob,gender,patient_id_oid
John,Doe,1980-01-15,M,2.16.840.1.113883.3.9999.1
Jane,Smith,1975-06-20,F,2.16.840.1.113883.3.9999.1
Robert,Johnson,1990-03-10,M,2.16.840.1.113883.3.9999.1
```

**Note:** All `patient_id` values are empty, so all will be auto-generated.

### Comprehensive Example (All Columns)

File: `examples/patients_sample.csv`

```csv
first_name,last_name,dob,gender,patient_id_oid,patient_id,mrn,ssn,address,city,state,zip,phone,email
José,García,2010-03-15,M,2.16.840.1.113883.3.9999.1,PAT001,MRN10001,111-11-1111,123 Main Street,Springfield,IL,62701,555-0100,jose.garcia@email.com
Mary-Jane,O'Brien,1985-06-20,F,2.16.840.1.113883.3.9999.10,PAT002,MRN10002,222-22-2222,456 Oak Avenue,Chicago,IL,60601,555-0101,maryj.obrien@email.com
```

**Features demonstrated:**
- UTF-8 special characters (José, Mary-Jane)
- Mix of provided patient IDs and empty IDs
- Complete addresses and partial addresses
- Various demographic data

## Troubleshooting

### Common CSV Errors

#### Missing Required Column

**Error:** `Missing required column: dob`

**Cause:** CSV file does not include a required column

**Fix:** Add the missing column to your CSV header row

#### Invalid Date Format

**Error:** `Invalid date format for dob: '01/15/1980'. Expected YYYY-MM-DD`

**Cause:** Date is in US format (MM/DD/YYYY) instead of ISO format

**Fix:** Change date format to `1980-01-15`

#### Invalid Gender Value

**Error:** `Invalid gender value: 'Male'. Must be M, F, O, or U`

**Cause:** Gender column contains full word instead of single character code

**Fix:** Use `M` instead of `Male`

#### Future Date of Birth

**Error:** `Date of birth cannot be in the future: '2030-01-15'`

**Cause:** Date of birth is set to a future date

**Fix:** Use a past date (e.g., `1990-01-15`)

#### Invalid OID Format

**Error:** `Invalid OID format: '12345'. Must be numeric dotted notation`

**Cause:** OID is not in proper format

**Fix:** Use proper OID format like `2.16.840.1.113883.3.9999.1`

### CSV Encoding Issues

#### BOM (Byte Order Mark) Issues

**Symptom:** First column name not recognized, validation fails on first row

**Cause:** CSV file saved with UTF-8 BOM marker

**Fix:**
- **Excel:** Save As → Tools → Web Options → Encoding → Unicode (UTF-8) without BOM
- **Notepad++:** Encoding → Convert to UTF-8 without BOM
- **VS Code:** Click encoding in status bar → Save with Encoding → UTF-8

#### Non-UTF-8 Encoding

**Symptom:** Special characters appear garbled (� or ?)

**Cause:** CSV file saved with wrong encoding (e.g., Windows-1252, ISO-8859-1)

**Fix:** Re-save file with UTF-8 encoding

### Special Character Handling

#### Commas in Fields

**Problem:** Address like `"123 Main St, Apt 2B"` breaks CSV parsing

**Fix:** Enclose field in double quotes:
```csv
address
"123 Main St, Apt 2B"
```

#### Quotes in Fields

**Problem:** Name like `John "Johnny" Doe` breaks CSV parsing

**Fix:** Escape quotes by doubling them and enclosing in quotes:
```csv
first_name
"John ""Johnny"" Doe"
```

#### Line Breaks in Fields

**Problem:** Multi-line address breaks CSV parsing

**Fix:** Enclose field in double quotes:
```csv
address
"123 Main St
Apt 2B"
```

### Patient ID Generation Not Triggering

**Symptom:** Expected auto-generation but patient_id stays empty

**Cause:** Cell contains whitespace instead of being truly empty

**Fix:** Ensure cells are completely empty (no spaces, no tabs)

### Date Format Confusion

**Common Issue:** Different regions use different date formats

**Examples:**
- US Format: `01/15/1980` (MM/DD/YYYY) ❌
- European: `15/01/1980` (DD/MM/YYYY) ❌
- ISO Format: `1980-01-15` (YYYY-MM-DD) ✅

**Fix:** Always use ISO 8601 format: `YYYY-MM-DD`

## CSV Creation Tips

### Recommended Tools

#### Excel (Microsoft Office)

**Creating CSV:**
1. Create data in Excel spreadsheet
2. File → Save As
3. Choose "CSV UTF-8 (Comma delimited) (*.csv)"
4. ⚠️ **Important:** Regular "CSV (Comma delimited)" may not preserve UTF-8

**Avoiding Issues:**
- Use "CSV UTF-8" option, not regular "CSV"
- Excel may add BOM marker - verify with text editor if issues occur
- Test CSV after saving to ensure encoding is correct

#### Google Sheets

**Creating CSV:**
1. Create data in Google Sheets
2. File → Download → Comma Separated Values (.csv)
3. Google Sheets exports as UTF-8 by default

**Advantages:**
- Automatically handles UTF-8 encoding
- No BOM issues
- Good for collaboration

#### LibreOffice Calc

**Creating CSV:**
1. Create data in Calc
2. File → Save As
3. File Type: "Text CSV (.csv)"
4. In dialog: Character set = "Unicode (UTF-8)", Field delimiter = ","

**Advantages:**
- Free and open source
- Explicit encoding control
- No hidden formatting issues

#### Text Editors (VS Code, Notepad++, Sublime)

**Advantages:**
- Complete control over encoding
- Can verify exact file contents
- Good for troubleshooting

**Creating CSV:**
1. Create text file with `.csv` extension
2. Set encoding to UTF-8
3. Format data following CSV rules
4. Save

### Best Practices

#### Data Entry

- **Use consistent date format:** Always `YYYY-MM-DD`
- **Use gender codes:** `M`, `F`, `O`, `U` (not full words)
- **Test OIDs:** Use `2.16.840.1.113883.3.9999.x` prefix for testing
- **Fake data:** Use obviously fake data (names like "John Doe", SSNs like "111-11-1111")

#### File Management

- **UTF-8 encoding:** Always save as UTF-8 without BOM
- **Version control:** Keep CSV files in version control (Git)
- **Backup:** Keep backup copies before bulk edits
- **Validation:** Run `ihe-test-util csv validate` after creating/editing

#### Testing Workflow

1. **Create CSV:** Use recommended tool with UTF-8 encoding
2. **Validate:** Run `ihe-test-util csv validate your-file.csv`
3. **Fix errors:** Address any validation errors reported
4. **Process:** Run `ihe-test-util csv process your-file.csv`
5. **Verify:** Check that patient IDs generated correctly

### Avoiding Common Spreadsheet Issues

#### Auto-Formatting Problems

**Problem:** Excel converts data automatically (e.g., `123-45-6789` becomes date)

**Fix:** 
- Format cells as "Text" before entering data
- Prefix with single quote: `'123-45-6789`
- Use CSV UTF-8 export option

#### Leading Zeros Removed

**Problem:** ZIP code `01234` becomes `1234`

**Fix:**
- Format cell as Text
- In Excel: Custom format `00000` for ZIP codes

#### Date Auto-Conversion

**Problem:** `2010-03-15` displayed as `3/15/2010` or converted to serial number

**Fix:**
- Format cell as Text before entering
- Verify in text editor after saving CSV that format is `YYYY-MM-DD`

## See Also

- [Quick Start Guide](../README.md#quick-start) - Step-by-step tutorial
- [Sample CSV Files](../examples/) - Example files
- [CSV Parser Documentation](../README.md#csv-validation) - CLI command reference
