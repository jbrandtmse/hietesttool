"""Programmatic SAML Generation Example.

This example demonstrates using the SAMLProgrammaticGenerator class
to generate SAML 2.0 assertions without requiring XML templates.

Key features demonstrated:
- Basic SAML generation with required parameters only
- SAML generation with custom attributes
- SAML generation with multi-valued attributes
- Certificate-based issuer extraction
- Custom validity periods
- Comparison with template-based approach
"""

import sys
from pathlib import Path
from lxml import etree

# Add src to path for running as standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ihe_test_util.saml.programmatic_generator import SAMLProgrammaticGenerator
from ihe_test_util.saml.certificate_manager import load_certificate
from ihe_test_util.models.saml import SAMLGenerationMethod


def example_basic_saml():
    """Example 1: Basic SAML generation with required parameters only."""
    print("\n" + "=" * 70)
    print("Example 1: Basic Programmatic SAML Generation")
    print("=" * 70)
    
    # Create generator
    generator = SAMLProgrammaticGenerator()
    
    # Generate basic SAML assertion
    assertion = generator.generate(
        subject="patient-12345",
        issuer="https://hospital-a.example.com",
        audience="https://regional-hie.example.com"
    )
    
    # Display results
    print(f"\n✓ SAML Assertion Generated:")
    print(f"  • Assertion ID: {assertion.assertion_id}")
    print(f"  • Subject: {assertion.subject}")
    print(f"  • Issuer: {assertion.issuer}")
    print(f"  • Audience: {assertion.audience}")
    print(f"  • Issue Instant: {assertion.issue_instant}")
    print(f"  • Expires: {assertion.not_on_or_after}")
    print(f"  • Generation Method: {assertion.generation_method.value}")
    
    # Display XML excerpt
    print(f"\n✓ XML Structure (first 500 chars):")
    print("-" * 70)
    print(assertion.xml_content[:500] + "...")
    print("-" * 70)
    
    return assertion


def example_saml_with_attributes():
    """Example 2: SAML generation with custom attributes."""
    print("\n" + "=" * 70)
    print("Example 2: SAML Generation with Custom Attributes")
    print("=" * 70)
    
    # Create generator
    generator = SAMLProgrammaticGenerator()
    
    # Generate SAML with custom attributes
    assertion = generator.generate(
        subject="dr.smith@hospital-a.example.com",
        issuer="https://hospital-a.example.com",
        audience="https://regional-hie.example.com",
        attributes={
            "username": "dr.smith",
            "role": "physician",
            "organization": "Hospital A",
            "department": "Cardiology",
            "npi": "1234567890"
        },
        validity_minutes=10
    )
    
    # Display results
    print(f"\n✓ SAML Assertion with Attributes Generated:")
    print(f"  • Assertion ID: {assertion.assertion_id}")
    print(f"  • Subject: {assertion.subject}")
    print(f"  • Validity: 10 minutes")
    
    # Parse and display attributes
    tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
    attr_statement = tree.find(".//{*}AttributeStatement")
    
    if attr_statement is not None:
        print(f"\n✓ Custom Attributes:")
        for attr in attr_statement.findall(".//{*}Attribute"):
            attr_name = attr.get("Name")
            attr_value = attr.find(".//{*}AttributeValue").text
            print(f"  • {attr_name}: {attr_value}")
    
    return assertion


def example_saml_with_multi_valued_attributes():
    """Example 3: SAML generation with multi-valued attributes."""
    print("\n" + "=" * 70)
    print("Example 3: SAML Generation with Multi-Valued Attributes")
    print("=" * 70)
    
    # Create generator
    generator = SAMLProgrammaticGenerator()
    
    # Generate SAML with multi-valued attributes
    assertion = generator.generate(
        subject="dr.jones@hospital-a.example.com",
        issuer="https://hospital-a.example.com",
        audience="https://regional-hie.example.com",
        attributes={
            "username": "dr.jones",
            "roles": ["physician", "administrator", "researcher"],
            "specialties": ["Cardiology", "Internal Medicine"],
            "facilities": ["Main Campus", "Satellite Clinic"]
        }
    )
    
    # Display results
    print(f"\n✓ SAML Assertion with Multi-Valued Attributes Generated:")
    print(f"  • Assertion ID: {assertion.assertion_id}")
    print(f"  • Subject: {assertion.subject}")
    
    # Parse and display multi-valued attributes
    tree = etree.fromstring(assertion.xml_content.encode("utf-8"))
    attr_statement = tree.find(".//{*}AttributeStatement")
    
    if attr_statement is not None:
        print(f"\n✓ Multi-Valued Attributes:")
        for attr in attr_statement.findall(".//{*}Attribute"):
            attr_name = attr.get("Name")
            attr_values = [v.text for v in attr.findall(".//{*}AttributeValue")]
            
            if len(attr_values) == 1:
                print(f"  • {attr_name}: {attr_values[0]}")
            else:
                print(f"  • {attr_name}: [{', '.join(attr_values)}]")
    
    return assertion


def example_saml_with_certificate():
    """Example 4: SAML generation with certificate-based issuer extraction."""
    print("\n" + "=" * 70)
    print("Example 4: SAML Generation with Certificate Integration")
    print("=" * 70)
    
    # Load certificate
    cert_path = Path(__file__).parent.parent / "tests" / "fixtures" / "test_cert.pem"
    
    if not cert_path.exists():
        print("\n⚠️  Test certificate not available, skipping this example")
        return None
    
    cert_bundle = load_certificate(cert_path)
    
    # Create generator with certificate
    generator = SAMLProgrammaticGenerator(cert_bundle=cert_bundle)
    
    # Generate SAML with automatic issuer extraction
    assertion = generator.generate_with_certificate(
        subject="patient-67890",
        audience="https://regional-hie.example.com",
        attributes={
            "source": "Hospital B",
            "facility_id": "FAC-001"
        }
    )
    
    # Display results
    print(f"\n✓ SAML Assertion with Certificate Integration:")
    print(f"  • Assertion ID: {assertion.assertion_id}")
    print(f"  • Subject: {assertion.subject}")
    print(f"  • Issuer (from cert): {assertion.issuer}")
    print(f"  • Certificate Subject: {assertion.certificate_subject}")
    
    # Display certificate info
    print(f"\n✓ Certificate Information:")
    print(f"  • Subject: {cert_bundle.info.subject}")
    print(f"  • Expiration: {cert_bundle.info.not_after.strftime('%Y-%m-%d')}")
    print(f"  • Key Size: {cert_bundle.info.key_size} bits")
    
    return assertion


def example_comparison_programmatic_vs_template():
    """Example 5: Compare programmatic and template-based approaches."""
    print("\n" + "=" * 70)
    print("Example 5: Programmatic vs Template-Based Comparison")
    print("=" * 70)
    
    # Generate programmatic SAML
    prog_gen = SAMLProgrammaticGenerator()
    prog_assertion = prog_gen.generate(
        subject="user@example.com",
        issuer="https://idp.example.com",
        audience="https://sp.example.com"
    )
    
    print(f"\n✓ Programmatic SAML:")
    print(f"  • Assertion ID: {prog_assertion.assertion_id}")
    print(f"  • Generation Method: {prog_assertion.generation_method.value}")
    print(f"  • XML Length: {len(prog_assertion.xml_content)} bytes")
    
    # Both produce valid SAML 2.0 assertions
    prog_tree = etree.fromstring(prog_assertion.xml_content.encode("utf-8"))
    
    print(f"\n✓ SAML 2.0 Structure Validation:")
    print(f"  • Assertion element: {'✓' if prog_tree.tag.endswith('}Assertion') else '✗'}")
    print(f"  • Issuer element: {'✓' if prog_tree.find('.//{*}Issuer') is not None else '✗'}")
    print(f"  • Subject element: {'✓' if prog_tree.find('.//{*}Subject') is not None else '✗'}")
    print(f"  • Conditions element: {'✓' if prog_tree.find('.//{*}Conditions') is not None else '✗'}")
    print(f"  • AuthnStatement element: {'✓' if prog_tree.find('.//{*}AuthnStatement') is not None else '✗'}")
    
    return prog_assertion


def example_batch_generation():
    """Example 6: Batch SAML generation for multiple patients."""
    print("\n" + "=" * 70)
    print("Example 6: Batch SAML Generation")
    print("=" * 70)
    
    # Create generator
    generator = SAMLProgrammaticGenerator()
    
    # Generate SAML for multiple patients
    patients = [
        {"id": "patient-001", "name": "John Doe", "mrn": "MRN-12345"},
        {"id": "patient-002", "name": "Jane Smith", "mrn": "MRN-67890"},
        {"id": "patient-003", "name": "Bob Johnson", "mrn": "MRN-11111"},
    ]
    
    assertions = []
    for patient in patients:
        assertion = generator.generate(
            subject=patient["id"],
            issuer="https://hospital-c.example.com",
            audience="https://regional-hie.example.com",
            attributes={
                "patient_name": patient["name"],
                "mrn": patient["mrn"]
            }
        )
        assertions.append(assertion)
    
    # Display results
    print(f"\n✓ Generated {len(assertions)} SAML Assertions:")
    for i, assertion in enumerate(assertions, 1):
        print(f"  {i}. {assertion.subject} (ID: {assertion.assertion_id})")
    
    # Verify all have unique IDs
    assertion_ids = {a.assertion_id for a in assertions}
    print(f"\n✓ All assertions have unique IDs: {len(assertion_ids) == len(assertions)}")
    
    return assertions


def example_when_to_use_programmatic():
    """Example 7: When to use programmatic vs template-based SAML generation."""
    print("\n" + "=" * 70)
    print("Example 7: When to Use Programmatic SAML Generation")
    print("=" * 70)
    
    print("\n📝 Use Programmatic Generation When:")
    print("  ✓ Standard SAML 2.0 structure is sufficient")
    print("  ✓ No organization-specific SAML template available")
    print("  ✓ Need maximum flexibility to customize structure in code")
    print("  ✓ Generating SAML dynamically with runtime parameters")
    print("  ✓ Building automated test fixtures")
    print("  ✓ Rapid prototyping and development")
    
    print("\n📝 Use Template-Based Generation When:")
    print("  ✓ Organization provides specific SAML template")
    print("  ✓ Complex custom SAML structure with many conditional elements")
    print("  ✓ Need to match exact XML structure from existing system")
    print("  ✓ Non-technical users need to modify SAML structure")
    print("  ✓ Template is managed separately from code")
    
    print("\n📝 Both Approaches:")
    print("  ✓ Produce valid SAML 2.0 assertions")
    print("  ✓ Use same SAMLAssertion dataclass")
    print("  ✓ Can be signed with signxml (Story 4.4)")
    print("  ✓ Can be embedded in WS-Security headers (Story 4.5)")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("Programmatic SAML Generation Examples")
    print("=" * 70)
    print("\nThis script demonstrates various ways to generate SAML 2.0 assertions")
    print("programmatically using the SAMLProgrammaticGenerator class.")
    
    try:
        # Run examples
        example_basic_saml()
        example_saml_with_attributes()
        example_saml_with_multi_valued_attributes()
        example_saml_with_certificate()
        example_comparison_programmatic_vs_template()
        example_batch_generation()
        example_when_to_use_programmatic()
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ All Examples Completed Successfully!")
        print("=" * 70)
        print("\nKey Takeaways:")
        print("  • Programmatic generation is flexible and doesn't require templates")
        print("  • Supports custom attributes (single and multi-valued)")
        print("  • Integrates with certificate management for issuer extraction")
        print("  • Suitable for batch processing and dynamic generation")
        print("  • Produces valid SAML 2.0 assertions ready for signing")
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
