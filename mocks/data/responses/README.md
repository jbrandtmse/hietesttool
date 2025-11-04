# Mock Response Templates

This directory contains mock response templates for IHE transactions.

## Purpose

Response templates are used by the mock IHE endpoints to generate realistic
SOAP responses for testing purposes.

## Structure

- `pix_add_responses/` - PIX Add (ITI-8) response templates
- `iti41_responses/` - ITI-41 (Provide and Register Document Set-b) response templates
- `xcpd_responses/` - XCPD (Cross-Community Patient Discovery) response templates

## Response Types

### Success Responses
- Acknowledgment messages (AA - Application Accept)
- Document submission confirmations

### Error Responses
- Application Error (AE) responses
- Application Reject (AR) responses
- HL7v3 error codes and descriptions

## Usage

Response templates will be loaded by the mock server endpoints during initialization
and used to generate appropriate responses based on the incoming request.
