"""Example demonstrating HL7v3 PRPA_IN201301UV02 message construction and acknowledgment parsing.

This example shows:
1. Building a PIX Add message with patient demographics
2. Parsing the message to verify structure
3. Creating a sample acknowledgment
4. Parsing acknowledgment responses
"""

from datetime import date
from lxml import etree

from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.ihe_transactions.pix_add import (
    build_pix_add_message,
    format_hl7_timestamp,
    format_hl7_date,
)
from ihe_test_util.ihe_transactions.parsers import (
    parse_acknowledgment,
    AcknowledgmentResponse,
)


def example_build_pix_add_message():
    """Example: Building a PIX Add message."""
    print("=" * 80)
    print("Example 1: Building PRPA_IN201301UV02 PIX Add Message")
    print("=" * 80)
    
    # Create patient demographics using standardized model
    patient = PatientDemographics(
        patient_id="12345678",
        patient_id_oid="2.16.840.1.113883.3.72.5.9.1",
        first_name="John",
        last_name="Doe",
        dob=date(1980, 1, 1),
        gender="M",
        address="123 Main Street",
        city="Portland",
        state="OR",
        zip="97201",
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
    soap_ns = "http://schemas.xmlsoap.org/soap/envelope/"
    
    # Extract HL7v3 message from SOAP envelope
    body = root.find(f"{{{soap_ns}}}Body")
    hl7_msg = body[0] if body is not None else root
    
    print("\nMessage Structure Verification:")
    print("-" * 80)
    print(f"Root Element: {hl7_msg.tag}")
    print(f"Default Namespace: {hl7_msg.nsmap[None]}")
    print(f"ITSVersion: {hl7_msg.get('ITSVersion')}")
    
    # Extract key elements
    patient_id_elem = hl7_msg.find(f".//{{{hl7_ns}}}patient/{{{hl7_ns}}}id")
    if patient_id_elem is not None:
        print(f"\nPatient Identifier:")
        print(f"  - Root (OID): {patient_id_elem.get('root')}")
        print(f"  - Extension (ID): {patient_id_elem.get('extension')}")
    
    given_name = hl7_msg.find(f".//{{{hl7_ns}}}given")
    family_name = hl7_msg.find(f".//{{{hl7_ns}}}family")
    if given_name is not None and family_name is not None:
        print(f"\nPatient Name:")
        print(f"  - Given: {given_name.text}")
        print(f"  - Family: {family_name.text}")
    
    gender = hl7_msg.find(f".//{{{hl7_ns}}}administrativeGenderCode")
    birth_time = hl7_msg.find(f".//{{{hl7_ns}}}birthTime")
    if gender is not None and birth_time is not None:
        print(f"\nDemographics:")
        print(f"  - Gender: {gender.get('code')}")
        print(f"  - Birth Date: {birth_time.get('value')}")


def example_helper_functions():
    """Example: Using HL7 formatting helper functions."""
    print("\n" + "=" * 80)
    print("Example 2: Using HL7 Formatting Helper Functions")
    print("=" * 80)
    
    from datetime import datetime, timezone
    
    # Format HL7 timestamp
    dt = datetime(2025, 11, 14, 15, 30, 0, tzinfo=timezone.utc)
    hl7_timestamp = format_hl7_timestamp(dt)
    print(f"\nHL7 Timestamp:")
    print(f"  Input: {dt}")
    print(f"  Output: {hl7_timestamp}")
    
    # Format HL7 date
    d = date(1980, 1, 1)
    hl7_date = format_hl7_date(d)
    print(f"\nHL7 Date:")
    print(f"  Input: {d}")
    print(f"  Output: {hl7_date}")


def example_parse_acknowledgment_success():
    """Example: Parsing successful acknowledgment."""
    print("\n" + "=" * 80)
    print("Example 3: Parsing AA (Application Accept) Acknowledgment")
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
    print("Example 4: Parsing AE (Application Error) Acknowledgment")
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


def example_minimal_demographics():
    """Example: Building message with minimal demographics."""
    print("\n" + "=" * 80)
    print("Example 5: Building PIX Add Message with Minimal Demographics")
    print("=" * 80)
    
    # Create patient with only required fields
    minimal_patient = PatientDemographics(
        patient_id="MIN001",
        patient_id_oid="1.2.3.4.5",
        first_name="Jane",
        last_name="Smith",
        dob=date(1990, 5, 15),
        gender="F",
    )
    
    # Build the message
    message_xml = build_pix_add_message(minimal_patient)
    
    print("\nGenerated message with minimal demographics (first 500 chars):")
    print("-" * 80)
    print(message_xml[:500] + "...")
    
    print("\n✓ Successfully built message with only required fields")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("HL7v3 Message Construction and Parsing Examples")
    print("=" * 80)
    
    # Run examples
    example_build_pix_add_message()
    example_helper_functions()
    example_parse_acknowledgment_success()
    example_parse_acknowledgment_error()
    example_minimal_demographics()
    
    print("\n" + "=" * 80)
    print("Examples completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
