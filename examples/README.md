# Examples Directory

This directory contains sample files and example scripts to help you get started with the IHE Test Utility.

## Sample CSV Files

### patients_sample.csv

**Purpose:** Comprehensive sample demonstrating all CSV features and column types.

**Contains:**
- 10 diverse patient records
- All required columns (first_name, last_name, dob, gender, patient_id_oid)
- All optional columns (patient_id, mrn, ssn, address, city, state, zip, phone, email)
- Mix of provided patient IDs (5 records) and empty IDs for auto-generation (5 records)
- Diverse demographics:
  - Genders: M (3), F (4), O (2), U (1)
  - Age ranges: Child (2), Adult (5), Senior (3)
  - Complete addresses (5) and partial addresses (5)
- UTF-8 special characters (José, François, Mary-Jane, Amélie, Müller, Bjørnsson)
- Various address formats including apartment numbers
- Test OIDs from three different organizations

**Usage:**

```bash
# Validate the comprehensive sample
ihe-test-util csv validate examples/patients_sample.csv

# Process and view parsed data
ihe-test-util csv process examples/patients_sample.csv

# Process with reproducible ID generation
ihe-test-util csv process examples/patients_sample.csv --seed 42
```

**What You'll Learn:**
- How to structure CSV files with all columns
- How patient ID auto-generation works (empty patient_id fields)
- How UTF-8 special characters are handled
- How to use different OIDs for multi-facility scenarios
- How to include complete vs. partial demographic data

### patients_minimal.csv

**Purpose:** Minimal example with only required columns for simplest use case.

**Contains:**
- 3 patient records
- Only required columns (first_name, last_name, dob, gender, patient_id_oid)
- All patient IDs empty (demonstrates auto-generation for all records)
- Simple, straightforward demographic data

**Usage:**

```bash
# Validate the minimal sample
ihe-test-util csv validate examples/patients_minimal.csv

# Process minimal sample
ihe-test-util csv process examples/patients_minimal.csv
```

**What You'll Learn:**
- Minimum required CSV structure
- How to rely entirely on auto-generated patient IDs
- Simplest possible CSV format for quick testing

**When to Use:**
- Getting started with CSV processing
- Creating test data quickly
- Learning the bare minimum CSV requirements

## Configuration Files

### config.example.json

**Purpose:** Example configuration file template showing all available settings.

**Contains:**
- IHE endpoint URLs (PIX Add, ITI-41)
- Certificate and key paths for SAML signing
- Transport settings (TLS, timeouts, retries)
- Logging configuration
- Comments explaining each setting

**Usage:**

```bash
# Copy to create your configuration
cp examples/config.example.json config/config.json

# Edit config/config.json with your settings
# Then use it:
ihe-test-util --config config/config.json csv validate patients.csv
```

**Documentation:** See [Configuration Guide](../docs/configuration-guide.md) for detailed configuration reference.

## Python Example Scripts

### hl7v3_message_example.py

**Purpose:** Demonstrates programmatic HL7v3 message construction for PIX Add transactions.

**What It Shows:**
- How to create PRPA_IN201301UV02 messages (PIX Add)
- HL7v3 message structure and required elements
- Patient identifier construction
- Message ID and timestamp generation

**Usage:**

```bash
python examples/hl7v3_message_example.py
```

**Documentation:** See [docs/spike-findings-1.3-hl7v3-messages.md](../docs/spike-findings-1.3-hl7v3-messages.md)

### signxml_saml_example.py

**Purpose:** Demonstrates SAML 2.0 assertion generation and XML signing.

**What It Shows:**
- SAML assertion structure
- XML digital signatures with X.509 certificates
- Signature canonicalization
- Certificate handling (PEM, PKCS12, DER formats)

**Usage:**

```bash
python examples/signxml_saml_example.py
```

**Documentation:** See [docs/spike-findings-1.2-xml-signing-validation.md](../docs/spike-findings-1.2-xml-signing-validation.md)

## Quick Start Workflow

**New User Getting Started:**

1. **Start with minimal example:**
   ```bash
   ihe-test-util csv validate examples/patients_minimal.csv
   ihe-test-util csv process examples/patients_minimal.csv
   ```

2. **Try comprehensive example:**
   ```bash
   ihe-test-util csv validate examples/patients_sample.csv
   ihe-test-util csv process examples/patients_sample.csv
   ```

3. **Create your own CSV:**
   - Use `patients_minimal.csv` or `patients_sample.csv` as template
   - Follow format from [CSV Format Guide](../docs/csv-format.md)
   - Validate your CSV: `ihe-test-util csv validate your-file.csv`

4. **Configure for your environment:**
   ```bash
   cp examples/config.example.json config/config.json
   # Edit config/config.json with your endpoint URLs and settings
   ```

## File Format Reference

### CSV Format
- **Encoding:** UTF-8 without BOM
- **Format:** Standard CSV (RFC 4180)
- **Required Columns:** first_name, last_name, dob, gender, patient_id_oid
- **Detailed Specification:** [docs/csv-format.md](../docs/csv-format.md)

### Configuration Format
- **Format:** JSON
- **Schema:** Pydantic validation with type checking
- **Detailed Specification:** [docs/configuration-guide.md](../docs/configuration-guide.md)

## Testing OID Values

The sample CSV files use test OIDs that are safe for development and testing:

| OID | Description | Used In |
|-----|-------------|---------|
| `2.16.840.1.113883.3.9999.1` | Generic Test Organization A | Both samples |
| `2.16.840.1.113883.3.9999.10` | Test Hospital A | patients_sample.csv |
| `2.16.840.1.113883.3.9999.20` | Test Clinic B | patients_sample.csv |

**Important:** These are test OIDs only. For production use, obtain proper OIDs from your healthcare organization or use registered OIDs from the [HL7 OID Registry](https://www.hl7.org/oid/index.cfm).

## Additional Resources

- **CSV Format Specification:** [docs/csv-format.md](../docs/csv-format.md)
- **Configuration Guide:** [docs/configuration-guide.md](../docs/configuration-guide.md)
- **Quick Start Tutorial:** [README.md - Quick Start](../README.md#quick-start)
- **Architecture Documentation:** [docs/architecture/](../docs/architecture/)
- **PRD and Requirements:** [docs/prd/](../docs/prd/)

## Need Help?

- **CSV Format Issues:** See [CSV Format Troubleshooting](../docs/csv-format.md#troubleshooting)
- **Validation Errors:** Run with `--verbose` flag for detailed error messages
- **Configuration Problems:** See [Configuration Guide](../docs/configuration-guide.md)

## Contributing Examples

If you've created helpful examples or sample files, consider contributing them back to the project:

1. Ensure examples follow the established format and style
2. Include clear documentation explaining purpose and usage
3. Test examples before submitting
4. Use fake/test data only (no real patient information)
