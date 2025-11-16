"""PIX Add Submission Example.

This example demonstrates using the PIXAddSOAPClient class to submit
patient registration messages to IHE PIX endpoints via SOAP.

Key features demonstrated:
- Basic PIX Add submission with minimal configuration
- Custom timeout and retry configuration
- Complete end-to-end workflow from CSV to acknowledgment
- Error handling for common scenarios
- HTTPS vs HTTP endpoint configuration
- Integration with SAML authentication

Prerequisites:
- Mock PIX Add endpoint running (or real IHE endpoint configured)
- Test certificates for SAML signing (tests/fixtures/)
- Configuration file with endpoint URLs
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path for running as standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ihe_test_util.config.schema import Config, EndpointsConfig, TransportConfig
from ihe_test_util.ihe_transactions.pix_add import build_pix_add_message
from ihe_test_util.ihe_transactions.soap_client import PIXAddSOAPClient
from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.models.responses import TransactionStatus
from ihe_test_util.models.saml import SAMLAssertion, SAMLGenerationMethod


def create_test_config():
    """Create test configuration for PIX Add client.
    
    Returns:
        Config: Configuration with mock endpoint URLs
    """
    return Config(
        endpoints=EndpointsConfig(
            pix_add_url="http://localhost:8080/pix/add",
            iti41_url="http://localhost:8080/iti41"
        ),
        transport=TransportConfig(
            verify_tls=False,  # Disable for local mock server
            timeout_connect=30,
            timeout_read=30,
            max_retries=3
        )
    )


def create_mock_signed_saml():
    """Create mock signed SAML assertion for examples.
    
    Note: In production, use SAMLProgrammaticGenerator.generate() from
    Story 4.3 followed by SAMLSigner.sign_assertion() from Story 4.4.
    
    Returns:
        SAMLAssertion: Mock signed SAML assertion
    """
    return SAMLAssertion(
        assertion_id="example-saml-001",
        issuer="urn:example:hospital",
        subject="test-user",
        audience="urn:example:hie",
        issue_instant="2025-01-15T12:00:00Z",
        not_before="2025-01-15T12:00:00Z",
        not_on_or_after="2025-01-15T13:00:00Z",
        xml_content="""<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="example-saml-001">
  <saml:Issuer>urn:example:hospital</saml:Issuer>
  <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <ds:SignedInfo>
      <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
      <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
    </ds:SignedInfo>
    <ds:SignatureValue>mock-signature</ds:SignatureValue>
  </ds:Signature>
  <saml:Subject>
    <saml:NameID>test-user</saml:NameID>
  </saml:Subject>
</saml:Assertion>""",
        signature="<ds:Signature>mock</ds:Signature>",
        certificate_subject="CN=Example Hospital",
        generation_method=SAMLGenerationMethod.PROGRAMMATIC
    )


def example_basic_pix_add_submission():
    """Example 1: Submit single patient to PIX Add endpoint.
    
    This is the most basic PIX Add workflow:
    1. Create patient demographics
    2. Build HL7v3 PIX Add message
    3. Create SAML assertion
    4. Submit via SOAP client
    5. Check acknowledgment
    """
    print("\n" + "=" * 70)
    print("Example 1: Basic PIX Add Submission")
    print("=" * 70)
    
    # Step 1: Create patient demographics
    patient = PatientDemographics(
        patient_id="EXAMPLE-001",
        first_name="John",
        last_name="Doe",
        birth_date="19800101",
        gender="M",
        street="123 Main Street",
        city="Springfield",
        state="IL",
        postal_code="62701"
    )
    
    print(f"\n✓ Patient Demographics:")
    print(f"  • Patient ID: {patient.patient_id}")
    print(f"  • Name: {patient.first_name} {patient.last_name}")
    print(f"  • DOB: {patient.birth_date}")
    print(f"  • Gender: {patient.gender}")
    
    # Step 2: Build HL7v3 PIX Add message
    hl7v3_message = build_pix_add_message(
        patient=patient,
        sender_oid="1.2.3.4.5.6",
        receiver_oid="1.2.840.114350"
    )
    
    print(f"\n✓ HL7v3 Message Built:")
    print(f"  • Message Type: PRPA_IN201301UV02")
    print(f"  • Message Length: {len(hl7v3_message)} bytes")
    
    # Step 3: Create SAML assertion (mock for example)
    saml_assertion = create_mock_signed_saml()
    
    print(f"\n✓ SAML Assertion:")
    print(f"  • Assertion ID: {saml_assertion.assertion_id}")
    print(f"  • Issuer: {saml_assertion.issuer}")
    
    # Step 4: Create SOAP client
    config = create_test_config()
    client = PIXAddSOAPClient(config)
    
    print(f"\n✓ SOAP Client Initialized:")
    print(f"  • Endpoint: {client.endpoint_url}")
    print(f"  • Timeout: {client.timeout}s")
    print(f"  • Max Retries: {client.max_retries}")
    
    # Step 5: Submit PIX Add transaction
    print(f"\n📤 Submitting PIX Add transaction...")
    
    try:
        response = client.submit_pix_add(hl7v3_message, saml_assertion)
        
        # Step 6: Check acknowledgment
        print(f"\n✅ Transaction Successful!")
        print(f"  • Status: {response.status.value}")
        print(f"  • Status Code: {response.status_code}")
        print(f"  • Response ID: {response.response_id}")
        print(f"  • Processing Time: {response.processing_time_ms}ms")
        
        if response.is_success:
            print(f"\n✓ Patient registered successfully")
        else:
            print(f"\n⚠️  Transaction completed with errors:")
            for error in response.error_messages:
                print(f"  • {error}")
        
        return response
        
    except Exception as e:
        print(f"\n❌ Transaction Failed: {e}")
        return None


def example_custom_timeout_and_retries():
    """Example 2: Submit PIX Add with custom timeout and retry configuration.
    
    Demonstrates:
    - Custom timeout values
    - Custom retry configuration
    - Handling of slow endpoints
    """
    print("\n" + "=" * 70)
    print("Example 2: Custom Timeout and Retries")
    print("=" * 70)
    
    # Create patient
    patient = PatientDemographics(
        patient_id="EXAMPLE-002",
        first_name="Jane",
        last_name="Smith",
        birth_date="19900515",
        gender="F"
    )
    
    # Build message
    hl7v3_message = build_pix_add_message(
        patient=patient,
        sender_oid="1.2.3.4.5.6",
        receiver_oid="1.2.840.114350"
    )
    
    # Create SAML
    saml_assertion = create_mock_signed_saml()
    
    # Create client with custom configuration
    config = create_test_config()
    client = PIXAddSOAPClient(
        config,
        timeout=60,  # 60 second timeout for slow endpoints
        max_retries=5  # 5 retry attempts
    )
    
    print(f"\n✓ Client Configuration:")
    print(f"  • Timeout: {client.timeout}s (default: 30s)")
    print(f"  • Max Retries: {client.max_retries} (default: 3)")
    print(f"  • Retry delays: 1s, 2s, 4s, 8s, 16s (exponential backoff)")
    
    # Submit transaction
    print(f"\n📤 Submitting with custom configuration...")
    
    try:
        response = client.submit_pix_add(hl7v3_message, saml_assertion)
        
        print(f"\n✅ Transaction Successful!")
        print(f"  • Status: {response.status.value}")
        print(f"  • Processing Time: {response.processing_time_ms}ms")
        
        return response
        
    except Exception as e:
        print(f"\n❌ Transaction Failed: {e}")
        return None


def example_error_handling():
    """Example 3: Comprehensive error handling for PIX Add transactions.
    
    Demonstrates handling of:
    - Connection errors
    - Timeout errors
    - Unsigned SAML assertions
    - Malformed responses
    """
    print("\n" + "=" * 70)
    print("Example 3: Error Handling")
    print("=" * 70)
    
    # Create patient and message
    patient = PatientDemographics(
        patient_id="EXAMPLE-003",
        first_name="Bob",
        last_name="Johnson",
        birth_date="19750320",
        gender="M"
    )
    
    hl7v3_message = build_pix_add_message(
        patient=patient,
        sender_oid="1.2.3.4.5.6",
        receiver_oid="1.2.840.114350"
    )
    
    saml_assertion = create_mock_signed_saml()
    config = create_test_config()
    client = PIXAddSOAPClient(config)
    
    print(f"\n✓ Demonstrating Error Handling Scenarios:")
    
    # Scenario 1: Successful submission
    print(f"\n1. Normal Submission (Expected: Success)")
    try:
        response = client.submit_pix_add(hl7v3_message, saml_assertion)
        print(f"   ✅ Status: {response.status.value}")
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")
    
    # Scenario 2: Unsigned SAML (will fail validation)
    print(f"\n2. Unsigned SAML Assertion (Expected: ValidationError)")
    try:
        from ihe_test_util.utils.exceptions import ValidationError
        
        unsigned_saml = SAMLAssertion(
            assertion_id="unsigned",
            issuer="urn:example",
            subject="test",
            audience="urn:example",
            issue_instant="2025-01-15T12:00:00Z",
            not_before="2025-01-15T12:00:00Z",
            not_on_or_after="2025-01-15T13:00:00Z",
            xml_content="<saml:Assertion>unsigned</saml:Assertion>",
            signature="",  # No signature!
            certificate_subject="CN=Test",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC
        )
        
        response = client.submit_pix_add(hl7v3_message, unsigned_saml)
        print(f"   ⚠️  Unexpected success")
    except ValidationError as e:
        print(f"   ✅ Caught ValidationError: {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {type(e).__name__}: {e}")
    
    # Scenario 3: Connection error (unreachable endpoint)
    print(f"\n3. Unreachable Endpoint (Expected: ConnectionError)")
    try:
        import requests
        
        unreachable_config = Config(
            endpoints=EndpointsConfig(
                pix_add_url="http://invalid-endpoint-does-not-exist.local:9999/pix/add",
                iti41_url="http://localhost:8080/iti41"
            ),
            transport=TransportConfig(
                verify_tls=False,
                timeout_connect=1,
                timeout_read=1,
                max_retries=1
            )
        )
        
        unreachable_client = PIXAddSOAPClient(unreachable_config, timeout=1, max_retries=1)
        response = unreachable_client.submit_pix_add(hl7v3_message, saml_assertion)
        print(f"   ⚠️  Unexpected success")
    except requests.ConnectionError as e:
        print(f"   ✅ Caught ConnectionError: Connection failed as expected")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {type(e).__name__}: {e}")
    
    print(f"\n✓ Error Handling Summary:")
    print(f"  • Always catch specific exceptions (ConnectionError, Timeout, ValidationError)")
    print(f"  • Check response.is_success before processing")
    print(f"  • Review response.error_messages for details")
    print(f"  • Configure appropriate timeout and retry values")


def example_complete_workflow():
    """Example 4: Complete end-to-end workflow from CSV to acknowledgment.
    
    This example shows the complete production workflow:
    1. Load patient from CSV (simulated)
    2. Build HL7v3 message
    3. Generate and sign SAML assertion
    4. Submit via SOAP client
    5. Process acknowledgment
    6. Log results
    """
    print("\n" + "=" * 70)
    print("Example 4: Complete End-to-End Workflow")
    print("=" * 70)
    
    print(f"\n📋 Workflow Steps:")
    print(f"  1. Parse patient demographics from CSV")
    print(f"  2. Build HL7v3 PIX Add message")
    print(f"  3. Generate and sign SAML assertion")
    print(f"  4. Submit via PIX Add SOAP client")
    print(f"  5. Process acknowledgment response")
    print(f"  6. Log transaction results")
    
    # Step 1: Parse patient from CSV (simulated)
    print(f"\n[Step 1] Parsing patient from CSV...")
    # In production: from ihe_test_util.csv_parser import parse_csv
    patient = PatientDemographics(
        patient_id="CSV-PATIENT-001",
        first_name="Alice",
        last_name="Williams",
        birth_date="19851210",
        gender="F",
        street="456 Oak Avenue",
        city="Portland",
        state="OR",
        postal_code="97201"
    )
    print(f"  ✓ Patient loaded: {patient.first_name} {patient.last_name} ({patient.patient_id})")
    
    # Step 2: Build HL7v3 message
    print(f"\n[Step 2] Building HL7v3 PIX Add message...")
    hl7v3_message = build_pix_add_message(
        patient=patient,
        sender_oid="1.2.3.4.5.6.7",
        receiver_oid="1.2.840.114350.1.13"
    )
    print(f"  ✓ HL7v3 PRPA_IN201301UV02 message built ({len(hl7v3_message)} bytes)")
    
    # Step 3: Generate and sign SAML assertion
    print(f"\n[Step 3] Generating and signing SAML assertion...")
    # In production:
    # from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
    # from ihe_test_util.saml.signer import SAMLSigner
    # generator = SAMLProgrammaticGenerator()
    # saml = generator.generate(subject="user", issuer="urn:issuer", audience="urn:audience")
    # signer = SAMLSigner(cert_bundle)
    # signed_saml = signer.sign_assertion(saml)
    
    saml_assertion = create_mock_signed_saml()
    print(f"  ✓ SAML assertion generated and signed")
    print(f"    • Assertion ID: {saml_assertion.assertion_id}")
    print(f"    • Issuer: {saml_assertion.issuer}")
    
    # Step 4: Submit via SOAP client
    print(f"\n[Step 4] Submitting PIX Add transaction...")
    config = create_test_config()
    client = PIXAddSOAPClient(config)
    
    start_time = datetime.now()
    response = client.submit_pix_add(hl7v3_message, saml_assertion)
    end_time = datetime.now()
    
    print(f"  ✓ Transaction submitted")
    print(f"    • Endpoint: {client.endpoint_url}")
    print(f"    • Request ID: {response.request_id}")
    
    # Step 5: Process acknowledgment
    print(f"\n[Step 5] Processing acknowledgment response...")
    print(f"  ✓ Acknowledgment received")
    print(f"    • Response ID: {response.response_id}")
    print(f"    • Status: {response.status.value}")
    print(f"    • Status Code: {response.status_code}")
    print(f"    • Processing Time: {response.processing_time_ms}ms")
    
    if response.is_success:
        print(f"\n  ✅ Patient successfully registered in PIX!")
    else:
        print(f"\n  ⚠️  Registration completed with errors:")
        for error in response.error_messages:
            print(f"    • {error}")
    
    # Step 6: Log transaction results
    print(f"\n[Step 6] Logging transaction results...")
    print(f"  ✓ Transaction logged to audit trail")
    print(f"    • Log file: logs/transactions/pix-add-{datetime.now().strftime('%Y%m%d')}.log")
    print(f"    • Complete SOAP request and response logged")
    
    # Summary
    total_time = (end_time - start_time).total_seconds()
    print(f"\n✅ Workflow Complete!")
    print(f"  • Total time: {total_time:.2f}s")
    print(f"  • Patient ID: {patient.patient_id}")
    print(f"  • Transaction Status: {response.status.value}")
    
    return response


def example_https_configuration():
    """Example 5: HTTPS endpoint configuration with TLS validation.
    
    Demonstrates:
    - HTTPS endpoint configuration
    - TLS 1.2+ enforcement
    - Certificate verification
    - Security warnings for HTTP
    """
    print("\n" + "=" * 70)
    print("Example 5: HTTPS Configuration")
    print("=" * 70)
    
    # HTTPS configuration with certificate verification
    https_config = Config(
        endpoints=EndpointsConfig(
            pix_add_url="https://pix.example.com/pix/add",  # HTTPS
            iti41_url="https://xds.example.com/iti41"
        ),
        transport=TransportConfig(
            verify_tls=True,  # Enable certificate verification
            timeout_connect=30,
            timeout_read=30,
            max_retries=3
        )
    )
    
    print(f"\n✓ HTTPS Configuration:")
    print(f"  • PIX Add URL: {https_config.endpoints.pix_add_url}")
    print(f"  • Protocol: HTTPS (secure)")
    print(f"  • TLS Version: 1.2+ (enforced)")
    print(f"  • Certificate Verification: {https_config.transport.verify_tls}")
    
    # HTTP configuration (triggers security warning)
    http_config = Config(
        endpoints=EndpointsConfig(
            pix_add_url="http://localhost:8080/pix/add",  # HTTP
            iti41_url="http://localhost:8080/iti41"
        ),
        transport=TransportConfig(verify_tls=False)
    )
    
    print(f"\n⚠️  HTTP Configuration (Development Only):")
    print(f"  • PIX Add URL: {http_config.endpoints.pix_add_url}")
    print(f"  • Protocol: HTTP (insecure - triggers warning)")
    print(f"  • Should only be used for local mock servers")
    
    # Create client (will log security warning for HTTP)
    print(f"\n📝 Creating client with HTTP endpoint...")
    print(f"  (Watch for SECURITY WARNING in logs)")
    
    http_client = PIXAddSOAPClient(http_config)
    
    print(f"\n✓ Security Best Practices:")
    print(f"  • Always use HTTPS in production")
    print(f"  • Enable certificate verification (verify_tls=True)")
    print(f"  • HTTP should only be used for local development/testing")
    print(f"  • TLS 1.2+ is automatically enforced for HTTPS")
    print(f"  • Monitor security warnings in logs")


def main():
    """Run all PIX Add submission examples."""
    print("\n" + "=" * 70)
    print("PIX Add SOAP Client Examples")
    print("=" * 70)
    print("\nThis script demonstrates PIX Add patient registration transactions")
    print("using the PIXAddSOAPClient with mock or real IHE endpoints.")
    
    print("\n⚠️  Prerequisites:")
    print("  • Mock PIX Add server running on http://localhost:8080")
    print("  • Start server with: python -m ihe_test_util.mock_server.app")
    print("  • Or configure real IHE endpoint in config file")
    
    try:
        # Run examples
        example_basic_pix_add_submission()
        example_custom_timeout_and_retries()
        example_error_handling()
        example_complete_workflow()
        example_https_configuration()
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ All Examples Completed Successfully!")
        print("=" * 70)
        print("\nKey Takeaways:")
        print("  • PIXAddSOAPClient handles complete SOAP workflow")
        print("  • Supports custom timeout and retry configuration")
        print("  • Provides comprehensive error handling")
        print("  • Integrates with HL7v3 message builder and SAML authentication")
        print("  • Logs complete transactions to audit trail")
        print("  • Enforces TLS 1.2+ for HTTPS endpoints")
        print("\nNext Steps:")
        print("  • Review logs/transactions/pix-add-*.log for audit trail")
        print("  • Configure production endpoint URLs in config file")
        print("  • Generate real SAML assertions with SAMLSigner (Story 4.4)")
        print("  • Parse patient data from CSV files (Story 1.5)")
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
