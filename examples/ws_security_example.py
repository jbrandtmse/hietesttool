"""Example: WS-Security Header Construction for IHE Transactions.

This example demonstrates how to:
1. Generate SAML assertions (template-based and programmatic)
2. Sign SAML assertions with X.509 certificates
3. Build WS-Security headers with signed SAML
4. Create complete SOAP envelopes for IHE transactions (PIX Add, ITI-41)
5. Add WS-Addressing headers for transaction routing
"""

from pathlib import Path
from lxml import etree

from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
from ihe_test_util.saml.template_loader import SAMLTemplatePersonalizer
from ihe_test_util.saml.signer import SAMLSigner
from ihe_test_util.saml.ws_security import WSSecurityHeaderBuilder


def example_basic_ws_security_header():
    """Example 1: Build basic WS-Security header with signed SAML."""
    print("=" * 80)
    print("Example 1: Basic WS-Security Header Construction")
    print("=" * 80)
    
    # Step 1: Load certificate for signing
    cert_path = Path("tests/fixtures/test_cert.pem")
    cert_bundle = load_certificate(cert_path)
    print(f"✓ Loaded certificate: {cert_bundle.info.subject}")
    
    # Step 2: Generate SAML assertion programmatically
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="dr.smith@hospital.org",
        issuer="https://idp.hospital.org",
        audience="https://pix.regional-hie.org"
    )
    print(f"✓ Generated SAML assertion: {assertion.assertion_id}")
    
    # Step 3: Sign the SAML assertion
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    print(f"✓ Signed SAML assertion with certificate")
    
    # Step 4: Build WS-Security header
    builder = WSSecurityHeaderBuilder()
    ws_security_header = builder.build_ws_security_header(
        signed_assertion,
        timestamp_validity_minutes=10  # 10 minute validity
    )
    print(f"✓ Built WS-Security header with timestamp")
    
    # Step 5: Validate the WS-Security header
    is_valid = builder.validate_ws_security_header(ws_security_header)
    print(f"✓ WS-Security header validation: {is_valid}")
    
    # Display the WS-Security header XML
    ws_security_str = etree.tostring(
        ws_security_header,
        encoding='unicode',
        pretty_print=True
    )
    print("\nWS-Security Header XML:")
    print("-" * 80)
    print(ws_security_str[:500] + "..." if len(ws_security_str) > 500 else ws_security_str)
    print()


def example_pix_add_soap_envelope():
    """Example 2: Create complete PIX Add SOAP envelope."""
    print("=" * 80)
    print("Example 2: Complete PIX Add SOAP Envelope")
    print("=" * 80)
    
    # Step 1: Load certificate
    cert_path = Path("tests/fixtures/test_cert.pem")
    cert_bundle = load_certificate(cert_path)
    
    # Step 2: Generate and sign SAML assertion
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="integration-user@hospital.org",
        issuer="https://idp.hospital.org",
        audience="https://pix-manager.hie.org"
    )
    
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    print(f"✓ Created signed SAML assertion: {signed_assertion.assertion_id}")
    
    # Step 3: Create PIX Add message (dummy for this example)
    pix_message = etree.Element(
        "{urn:hl7-org:v3}PRPA_IN201301UV02",
        attrib={"ITSVersion": "XML_1.0"}
    )
    etree.SubElement(pix_message, "{urn:hl7-org:v3}id", attrib={
        "root": "2.16.840.1.113883.3.72.5.9.1",
        "extension": "MSG12345"
    })
    print("✓ Created PIX Add message")
    
    # Step 4: Build complete SOAP envelope with WS-Security
    builder = WSSecurityHeaderBuilder()
    soap_envelope = builder.create_pix_add_soap_envelope(
        signed_assertion,
        pix_message,
        endpoint_url="http://pix.regional-hie.org/pix/add"
    )
    print("✓ Built complete PIX Add SOAP envelope with WS-Security and WS-Addressing")
    
    # Display the SOAP envelope (first 1000 chars)
    print("\nPIX Add SOAP Envelope (preview):")
    print("-" * 80)
    print(soap_envelope[:1000] + "..." if len(soap_envelope) > 1000 else soap_envelope)
    print()
    
    # Parse and verify structure
    parsed = etree.fromstring(soap_envelope.encode('utf-8'))
    
    # Verify WS-Addressing headers
    ns = {'wsa': 'http://www.w3.org/2005/08/addressing'}
    action = parsed.find(".//wsa:Action", namespaces=ns)
    to = parsed.find(".//wsa:To", namespaces=ns)
    message_id = parsed.find(".//wsa:MessageID", namespaces=ns)
    
    print("WS-Addressing Headers:")
    print(f"  Action: {action.text if action is not None else 'N/A'}")
    print(f"  To: {to.text if to is not None else 'N/A'}")
    print(f"  MessageID: {message_id.text if message_id is not None else 'N/A'}")
    print()


def example_iti41_soap_envelope():
    """Example 3: Create complete ITI-41 SOAP envelope."""
    print("=" * 80)
    print("Example 3: Complete ITI-41 SOAP Envelope")
    print("=" * 80)
    
    # Step 1: Load certificate
    cert_path = Path("tests/fixtures/test_cert.pem")
    cert_bundle = load_certificate(cert_path)
    
    # Step 2: Generate and sign SAML assertion
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="dr.jane.smith@hospital.org",
        issuer="https://idp.hospital.org",
        audience="https://xds-repository.hie.org"
    )
    
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    print(f"✓ Created signed SAML assertion: {signed_assertion.assertion_id}")
    
    # Step 3: Create ITI-41 request (dummy for this example)
    iti41_request = etree.Element(
        "{urn:ihe:iti:xds-b:2007}ProvideAndRegisterDocumentSetRequest"
    )
    submission_set = etree.SubElement(iti41_request, "SubmissionSet")
    etree.SubElement(submission_set, "id", attrib={"value": "SS-12345"})
    print("✓ Created ITI-41 request")
    
    # Step 4: Build complete SOAP envelope with WS-Security
    builder = WSSecurityHeaderBuilder()
    soap_envelope = builder.create_iti41_soap_envelope(
        signed_assertion,
        iti41_request,
        endpoint_url="http://xds.regional-hie.org/xds-repository"
    )
    print("✓ Built complete ITI-41 SOAP envelope with WS-Security and WS-Addressing")
    
    # Display the SOAP envelope (first 1000 chars)
    print("\nITI-41 SOAP Envelope (preview):")
    print("-" * 80)
    print(soap_envelope[:1000] + "..." if len(soap_envelope) > 1000 else soap_envelope)
    print()
    
    # Parse and verify structure
    parsed = etree.fromstring(soap_envelope.encode('utf-8'))
    
    # Verify WS-Addressing headers
    ns = {'wsa': 'http://www.w3.org/2005/08/addressing'}
    action = parsed.find(".//wsa:Action", namespaces=ns)
    to = parsed.find(".//wsa:To", namespaces=ns)
    
    print("WS-Addressing Headers:")
    print(f"  Action: {action.text if action is not None else 'N/A'}")
    print(f"  To: {to.text if to is not None else 'N/A'}")
    print()


def example_template_based_saml_ws_security():
    """Example 4: WS-Security with template-based SAML."""
    print("=" * 80)
    print("Example 4: WS-Security with Template-Based SAML")
    print("=" * 80)
    
    # Step 1: Load certificate
    cert_path = Path("tests/fixtures/test_cert.pem")
    cert_bundle = load_certificate(cert_path)
    
    # Step 2: Generate SAML from template
    template_path = Path("templates/saml-template.xml")
    personalizer = SAMLTemplatePersonalizer()
    
    parameters = {
        "issuer": "https://idp.hospital.org",
        "subject": "dr.smith@hospital.org",
        "audience": "https://xds.regional-hie.org",
        "attr_username": "dr.smith",
        "attr_role": "physician",
        "attr_organization": "General Hospital",
        "attr_purpose_of_use": "TREATMENT",
    }
    
    # This returns a SAMLAssertion model
    assertion = personalizer.personalize_to_model(template_path, parameters)
    print(f"✓ Generated SAML from template: {assertion.assertion_id}")
    
    # Step 3: Sign assertion
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    print(f"✓ Signed template-based SAML assertion")
    
    # Step 4: Build WS-Security header
    builder = WSSecurityHeaderBuilder()
    ws_security_header = builder.build_ws_security_header(signed_assertion)
    print(f"✓ Built WS-Security header from template-based SAML")
    
    # Step 5: Validate
    is_valid = builder.validate_ws_security_header(ws_security_header)
    print(f"✓ Validation result: {is_valid}")
    print()


def example_custom_soap_envelope():
    """Example 5: Custom SOAP envelope with manual WS-Addressing."""
    print("=" * 80)
    print("Example 5: Custom SOAP Envelope with Manual WS-Addressing")
    print("=" * 80)
    
    # Step 1: Create signed SAML
    cert_path = Path("tests/fixtures/test_cert.pem")
    cert_bundle = load_certificate(cert_path)
    
    generator = SAMLProgrammaticGenerator()
    assertion = generator.generate(
        subject="system@hospital.org",
        issuer="https://idp.hospital.org",
        audience="https://custom-service.hie.org"
    )
    
    signer = SAMLSigner(cert_bundle)
    signed_assertion = signer.sign_assertion(assertion)
    print(f"✓ Created signed SAML assertion")
    
    # Step 2: Build WS-Security header
    builder = WSSecurityHeaderBuilder()
    ws_security = builder.build_ws_security_header(signed_assertion)
    
    # Step 3: Create custom body
    custom_body = etree.Element("CustomRequest")
    etree.SubElement(custom_body, "Operation").text = "query"
    etree.SubElement(custom_body, "PatientID").text = "PAT-12345"
    print("✓ Created custom SOAP body")
    
    # Step 4: Embed in SOAP envelope
    envelope = builder.embed_in_soap_envelope(custom_body, ws_security)
    
    # Step 5: Manually add WS-Addressing headers
    ns = {'SOAP-ENV': 'http://www.w3.org/2003/05/soap-envelope'}
    header = envelope.find(".//SOAP-ENV:Header", namespaces=ns)
    
    builder.add_ws_addressing_headers(
        header,
        action="urn:custom:query:v1",
        to="http://custom-service.hie.org/query",
        message_id="urn:uuid:custom-12345-67890"
    )
    print("✓ Added custom WS-Addressing headers")
    
    # Serialize
    envelope_str = etree.tostring(envelope, encoding='unicode', pretty_print=True)
    print("\nCustom SOAP Envelope (preview):")
    print("-" * 80)
    print(envelope_str[:800] + "..." if len(envelope_str) > 800 else envelope_str)
    print()


def example_error_handling():
    """Example 6: Error handling and validation."""
    print("=" * 80)
    print("Example 6: Error Handling and Validation")
    print("=" * 80)
    
    builder = WSSecurityHeaderBuilder()
    
    # Test 1: Invalid timestamp validity
    print("Test 1: Invalid timestamp validity")
    try:
        timestamp = builder._create_timestamp(-5)
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Caught expected error: {str(e)[:60]}...")
    
    # Test 2: None SAML assertion
    print("\nTest 2: None SAML assertion")
    try:
        ws_security = builder.build_ws_security_header(None)
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Caught expected error: {str(e)[:60]}...")
    
    # Test 3: Invalid header validation
    print("\nTest 3: Invalid WS-Security header")
    try:
        invalid_header = etree.Element("NotSecurity")
        builder.validate_ws_security_header(invalid_header)
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Caught expected error: {str(e)[:60]}...")
    
    print("\n✓ All error handling tests passed")
    print()


def main():
    """Run all examples."""
    print("\n")
    print("*" * 80)
    print("WS-Security Header Construction Examples")
    print("*" * 80)
    print()
    
    try:
        # Run examples
        example_basic_ws_security_header()
        example_pix_add_soap_envelope()
        example_iti41_soap_envelope()
        example_template_based_saml_ws_security()
        example_custom_soap_envelope()
        example_error_handling()
        
        print("=" * 80)
        print("✓ All examples completed successfully")
        print("=" * 80)
        print()
        
    except FileNotFoundError as e:
        print(f"\n⚠ File not found: {e}")
        print("Note: Some examples require test certificates and templates.")
        print("Run from project root directory: python examples/ws_security_example.py")
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
