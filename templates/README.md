# CCD and SAML Templates

This directory contains XML templates for CCD (Continuity of Care Document) and SAML assertions.

## Purpose

Templates are used by the template engine to generate personalized clinical documents
and SAML assertions for IHE transactions.

## Structure

- `ccd_templates/` - CCD document templates for ITI-41 submissions
- `saml_templates/` - SAML 2.0 assertion templates
- `hl7v3_templates/` - HL7v3 message templates

## Template Format

Templates use placeholder syntax for variable substitution:
- `{{patient_id}}` - Patient identifier
- `{{first_name}}` - Patient first name
- `{{last_name}}` - Patient last name
- `{{date_of_birth}}` - Patient date of birth
- `{{gender}}` - Patient gender code

## Usage

Templates are loaded by the `ihe_test_util.template_engine` module and populated
with patient demographics from CSV input files.

## Example Template Structure

```xml
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <recordTarget>
    <patientRole>
      <id extension="{{patient_id}}" root="{{patient_id_root}}"/>
      <patient>
        <name>
          <given>{{first_name}}</given>
          <family>{{last_name}}</family>
        </name>
        <birthTime value="{{date_of_birth}}"/>
        <administrativeGenderCode code="{{gender}}"/>
      </patient>
    </patientRole>
  </recordTarget>
</ClinicalDocument>
