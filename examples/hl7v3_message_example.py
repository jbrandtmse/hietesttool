"""Example demonstrating HL7v3 PRPA_IN201301UV02 message construction and acknowledgment parsing.

This example shows:
1. Building a PIX Add message with patient demographics
2. Parsing the message to verify structure
3. Creating a sample acknowledgment
4. Parsing acknowledgment responses
"""

from lxml import etree
from src.ihe_test_util.ihe_transactions.pix_add import (
    PatientDemographics,
    build_pix_add_message,
)
from src.ihe_test_util.ihe_transactions.parsers import (
    parse_acknowledgment,
    AcknowledgmentResponse,
)


def example_build_pix_add_message():
    """Example: Building a PIX Add message."""
    print("=" * 80)
    print("Example 1: Building PRPA_IN201301UV02 PIX Add Message")
    print("=" * 80)
    
    # Create patient demographics
    patient = PatientDemographics(
        patient_id="12345678",
        patient_id_root="2.16.840.1.113883.3.72.5.9.1",
        given_name="John",
        family_name="Doe",
        gender="M",
        birth_date="19800101",
        street_address="123 Main Street",
        city="Portland",
        state="OR",
        postal_code="97201",
        country="US",
    )
    
    # Build the message
    message_xml = build_pix_add_message(patient)
    
    # Display the message
    print("\nGenerated PIX Add Message:")
    print("-" * 80)
    print(message_xml)
    
    # Parse and verify structure
    root = etree.fromstring(message_xml.encode("utf-8"))
    hl7_ns = "urn:hl7-org:v3"
    
    print("\nMessage Structure Verification:")
    print("-" * 80)
    print(f"Root Element: {root.tag}")
    print(f"Default Namespace: {root.nsmap[None]}")
    print(f"ITSVersion: {root.get('ITSVersion')}")
    
    # Extract key elements
    patient_id_elem = root.find(f".//{{{hl7_ns}}}patient/{{{hl7_ns}}}id")
    if patient_id_elem is not None:
        print(f"\nPatient Identifier:")
        print(f"  - Root (OID): {patient_id_elem.get('root')}")
        print(f"  - Extension (ID): {patient_id_elem.get('extension')}")
    
    given_name = root.find(f".//{{{hl7_ns}}}given")
    family_name = root.find(f".//{{{hl7_ns}}}family")
    if given_name is not None and family_name is not None:
        print(f"\nPatient Name:")
        print(f"  - Given: {given_name.text}")
        print(f"  - Family: {family_name.text}")
    
    gender = root.find(f".//{{{hl7_ns}}}administrativeGenderCode")
    if gender is not None:
        print(f"\nDemographics:")
        print(f"  - Gender: {gender.get('code')}")
    
    birth_time = root.find(f".//{{{hl7_ns}}}birthTime")
    if birth_time is not None:
        print(f"  - Birth Date: {birth_time.get('value')}")


def example_parse_acknowledgment_success():
    """Example: Parsing successful acknowledgment."""
    print("\n" + "=" * 80)
    print("Example 2: Parsing AA (Application Accept) Acknowledgment")
    print("=" * 80)
    
    # Sample AA acknowledgment
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
  <id root="2.16.840.1.113883.3.72.5.2" extension="ACK-SUCCESS-001"/>
  <creationTime value="20251103200000"/>
  <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
  <processingCode code="P"/>
  <processingModeCode code="T"/>
  <acceptAckCode code="NE"/>
  <acknowledgement>
    <typeCode code="AA"/>
    <targetMessage>
      <id root="original-message-id-123"/>
    </targetMessage>
  </acknowledgement>
</MCCI_IN000002UV01>"""
    
    # Parse the acknowledgment
    result = parse_acknowledgment(ack_xml)
    
    print("\nParsed Acknowledgment:")
    print("-" * 80)
    print(f"Status: {result.status}")
    print(f"Is Success: {result.is_success}")
    print(f"Message ID: {result.message_id}")
    print(f"Target Message ID: {result.target_message_id}")
    print(f"Details Count: {len(result.details)}")
    
    if result.is_success:
        print("\n✓ Patient successfully registered in PIX Manager")


def example_parse_acknowledgment_error():
    """Example: Parsing error acknowledgment with details."""
    print("\n" + "=" * 80)
    print("Example 3: Parsing AE (Application Error) Acknowledgment")
    print("=" * 80)
    
    # Sample AE acknowledgment with error details
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
  <id root="2.16.840.1.113883.3.72.5.2" extension="ACK-ERROR-002"/>
  <creationTime value="20251103200100"/>
  <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
  <processingCode code="P"/>
  <processingModeCode code="T"/>
  <acceptAckCode code="NE"/>
  <acknowledgement>
    <typeCode code="AE"/>
    <targetMessage>
      <id root="failed-message-id-456" extension="MSG-456"/>
    </targetMessage>
    <acknowledgementDetail typeCode="E">
      <text>Patient identifier 12345678 already exists in registry</text>
      <code code="DUPLICATE_PATIENT_ID" codeSystem="2.16.840.1.113883.3.72.5.99"/>
    </acknowledgementDetail>
    <acknowledgementDetail typeCode="W">
      <text>Address validation warning: State code 'XX' is not valid</text>
    </acknowledgementDetail>
  </acknowledgement>
</MCCI_IN000002UV01>"""
    
    # Parse the acknowledgment
    result = parse_acknowledgment(ack_xml)
    
    print("\nParsed Acknowledgment:")
    print("-" * 80)
    print(f"Status: {result.status}")
    print(f"Is Success: {result.is_success}")
    print(f"Message ID: {result.message_id}")
    print(f"Target Message ID: {result.target_message_id}")
    print(f"Details Count: {len(result.details)}")
    
    if not result.is_success:
        print("\n✗ Patient registration failed")
        print("\nError Details:")
        for i, detail in enumerate(result.details, 1):
            print(f"\n  Detail {i}:")
            print(f"    Type: {detail.type_code} ({'Error' if detail.type_code == 'E' else 'Warning'})")
            print(f"    Message: {detail.text}")
            if detail.code:
                print(f"    Code: {detail.code}")
            if detail.code_system:
                print(f"    Code System: {detail.code_system}")


def example_parse_acknowledgment_reject():
    """Example: Parsing rejection acknowledgment."""
    print("\n" + "=" * 80)
    print("Example 4: Parsing AR (Application Reject) Acknowledgment")
    print("=" * 80)
    
    # Sample AR acknowledgment
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
  <id root="2.16.840.1.113883.3.72.5.2" extension="ACK-REJECT-003"/>
  <creationTime value="20251103200200"/>
  <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
  <processingCode code="P"/>
  <processingModeCode code="T"/>
  <acceptAckCode code="NE"/>
  <acknowledgement>
    <typeCode code="AR"/>
    <targetMessage>
      <id root="rejected-message-id-789"/>
    </targetMessage>
    <acknowledgementDetail typeCode="E">
      <text>PIX Manager temporarily unavailable due to maintenance. Retry after 2025-11-03 21:00:00 UTC</text>
      <code code="SYSTEM_UNAVAILABLE" codeSystem="2.16.840.1.113883.3.72.5.99"/>
    </acknowledgementDetail>
  </acknowledgement>
</MCCI_IN000002UV01>"""
    
    # Parse the acknowledgment
    result = parse_acknowledgment(ack_xml)
    
    print("\nParsed Acknowledgment:")
    print("-" * 80)
    print(f"Status: {result.status}")
    print(f"Is Success: {result.is_success}")
    print(f"Message ID: {result.message_id}")
    print(f"Target Message ID: {result.target_message_id}")
    
    if not result.is_success:
        print("\n✗ Message rejected by PIX Manager")
        print("\nRejection Reason:")
        for detail in result.details:
            print(f"  {detail.text}")
        print("\n  Action: Retry message after maintenance window")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("HL7v3 Message Construction and Parsing Examples")
    print("=" * 80)
    
    # Run examples
    example_build_pix_add_message()
    example_parse_acknowledgment_success()
    example_parse_acknowledgment_error()
    example_parse_acknowledgment_reject()
    
    print("\n" + "=" * 80)
    print("Examples completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
