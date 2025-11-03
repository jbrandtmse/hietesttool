# Epic 3: Template Engine & CCD Personalization

**Epic Goal:** Implement XML template processing with string replacement for CCD personalization, enabling batch generation of personalized clinical documents from CSV demographics. This epic delivers the core document generation capability that transforms patient data into valid HL7 CCDA documents.

### Story 3.1: XML Template Loader & Validator

**As a** developer,
**I want** to load and validate XML template files,
**so that** I can ensure templates are well-formed before personalization.

**Acceptance Criteria:**

1. Template loader accepts file path to XML template
2. XML parsing using `lxml` library validates well-formed XML structure
3. Template validation checks for required placeholder syntax (e.g., `{{field_name}}`)
4. Loader extracts and catalogs all placeholders found in template
5. Validation reports missing required placeholders for CCD documents
6. Support for both file paths and template string input
7. Clear error messages for malformed XML with line numbers
8. Template encoding detection and normalization to UTF-8
9. Loaded templates cached for reuse in batch operations
10. Unit tests cover valid templates, malformed XML, missing placeholders, encoding issues

### Story 3.2: String Replacement Engine

**As a** developer,
**I want** a string replacement engine for personalizing XML templates,
**so that** I can generate patient-specific documents from demographics.

**Acceptance Criteria:**

1. Replacement engine accepts template and dictionary of field values
2. All placeholder instances (`{{field_name}}`) replaced with corresponding values
3. Missing values in dictionary trigger clear error or use configurable default
4. Special character escaping for XML (e.g., &, <, >, quotes)
5. Date formatting applied automatically for date fields (configurable format)
6. OID values properly inserted for patient identifiers
7. Whitespace and indentation preserved from original template
8. Support for nested placeholders and conditional sections
9. Replacement operation efficient for batch processing (100+ patients)
10. Unit tests verify replacement accuracy, escaping, error handling, performance

### Story 3.3: CCD Template Personalization

**As a** healthcare integration developer,
**I want** to personalize CCD templates with patient demographics from CSV,
**so that** I can generate valid clinical documents for testing.

**Acceptance Criteria:**

1. Personalization accepts CCD template and pandas DataFrame row
2. Maps CSV columns to CCD template placeholders automatically
3. Required CCD fields populated: patient name, DOB, gender, identifiers
4. Optional fields populated when available: address, contact info, MRN
5. Generated CCD includes proper HL7 CCDA XML structure and namespaces
6. Document creation timestamp automatically inserted
7. Unique document IDs generated for each personalized CCD
8. Personalized CCDs validated as well-formed XML before output
9. Batch mode personalizes templates for all rows in DataFrame
10. Integration test generates CCDs from sample CSV and validates output

### Story 3.4: Template Library & Examples

**As a** new user,
**I want** example CCD templates and documentation,
**so that** I can understand template structure and create my own.

**Acceptance Criteria:**

1. Sample CCD template provided in `templates/ccd-template.xml`
2. Template includes common clinical sections (demographics, medications, problems, allergies)
3. All required placeholders clearly marked and documented
4. Template follows HL7 CCDA R2.1 structure and namespaces
5. Minimal CCD template provided for simplest use case
6. Template documentation in `docs/ccd-templates.md` explains structure
7. Placeholder reference lists all supported fields and formats
8. Examples show how to add custom sections to templates
9. Template validation checklist helps users verify custom templates
10. Quick start guide walks through creating first personalized CCD

### Story 3.5: Template Processing CLI

**As a** developer,
**I want** CLI commands for template processing,
**so that** I can generate CCDs from the command line.

**Acceptance Criteria:**

1. CLI command `template validate <file>` validates template structure and placeholders
2. Command `template process <template> <csv>` generates personalized CCDs
3. Option `--output <dir>` specifies output directory for generated CCDs
4. Option `--format <format>` controls output naming (e.g., `{patient_id}.xml`)
5. Batch processing displays progress for large CSV files
6. Generated CCDs saved with meaningful names based on patient identifiers
7. Summary report shows: total patients, CCDs generated, errors
8. Option `--validate-output` performs XML validation on generated CCDs
9. Error handling reports which patients failed with specific reasons
10. CLI output suitable for scripting and automation
