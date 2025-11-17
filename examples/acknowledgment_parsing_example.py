"""Example: PIX Add Acknowledgment Parsing

This example demonstrates how to parse PIX Add acknowledgment responses
from IHE PIX Manager endpoints, extract patient identifiers, handle errors,
and convert parsed data to JSON.

Run this example:
    python examples/acknowledgment_parsing_example.py
"""

from src.ihe_test_util.ihe_transactions.parsers import (
    parse_acknowledgment,
    log_acknowledgment_response,
)
import json


def example_1_parse_successful_acknowledgment():
    """Example 1: Parse successful AA acknowledgment with patient identifiers."""
    print("=" * 80)
    print("Example 1: Parse Successful Acknowledgment")
    print("=" * 80)
    
    # Sample successful acknowledgment from PIX Manager
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
      <id root="2.16.840.1.113883.3.72.5.9.2" extension="ACK-20251116-001"/>
      <creationTime value="20251116144530"/>
      <acknowledgement>
        <typeCode code="AA"/>
        <targetMessage>
          <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-20251116-001"/>
        </targetMessage>
      </acknowledgement>
      <controlActProcess>
        <subject typeCode="SUBJ">
          <registrationEvent>
            <subject1 typeCode="SBJ">
              <patient>
                <id root="2.16.840.1.113883.3.72.5.9.1" extension="PAT123456"/>
                <id root="1.2.840.114350.1.13.99998.8734" extension="ENTERPRISE-789"/>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </MCCI_IN000002UV01>"""
    
    # Parse acknowledgment
    result = parse_acknowledgment(ack_xml)
    
    # Display results
    print(f"\nStatus: {result.status}")
    print(f"Success: {result.is_success}")
    print(f"Message ID: {result.message_id}")
    print(f"Target Message ID: {result.target_message_id}")
    
    # Extract patient identifiers
    print("\nPatient Identifiers:")
    print(f"  Primary Patient ID: {result.patient_identifiers.get('patient_id')}")
    print(f"  Patient ID Root: {result.patient_identifiers.get('patient_id_root')}")
    
    if 'additional_ids' in result.patient_identifiers:
        print(f"\n  Additional IDs ({len(result.patient_identifiers['additional_ids'])}):")
        for idx, alt_id in enumerate(result.patient_identifiers['additional_ids'], 1):
            print(f"    {idx}. ID: {alt_id['extension']} (Root: {alt_id['root']})")
    
    print("\n" + "=" * 80 + "\n")


def example_2_parse_error_acknowledgment():
    """Example 2: Parse error AE acknowledgment with error details."""
    print("=" * 80)
    print("Example 2: Parse Error Acknowledgment with Details")
    print("=" * 80)
    
    # Sample error acknowledgment
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.2" extension="ACK-ERROR-001"/>
      <acknowledgement>
        <typeCode code="AE"/>
        <targetMessage>
          <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-ERROR-001"/>
        </targetMessage>
        <acknowledgementDetail typeCode="E">
          <code code="204" codeSystem="2.16.840.1.113883.12.357"/>
          <text>Unknown patient identifier domain: 9.9.9.9.9</text>
        </acknowledgementDetail>
        <acknowledgementDetail typeCode="E">
          <code code="207" codeSystem="2.16.840.1.113883.12.357"/>
          <text>Application internal error occurred</text>
        </acknowledgementDetail>
        <acknowledgementDetail typeCode="W">
          <text>Patient identifier domain not recognized but accepted</text>
        </acknowledgementDetail>
      </acknowledgement>
    </MCCI_IN000002UV01>"""
    
    # Parse acknowledgment
    result = parse_acknowledgment(ack_xml)
    
    # Display results
    print(f"\nStatus: {result.status}")
    print(f"Success: {result.is_success}")
    print(f"Message ID: {result.message_id}")
    
    # Display error details
    print(f"\nError Details ({len(result.details)} found):")
    for idx, detail in enumerate(result.details, 1):
        detail_type = {
            'E': 'Error',
            'W': 'Warning',
            'I': 'Information'
        }.get(detail.type_code, 'Unknown')
        
        print(f"\n  {idx}. Type: {detail_type}")
        print(f"     Text: {detail.text}")
        if detail.code:
            print(f"     Code: {detail.code}")
        if detail.code_system:
            print(f"     Code System: {detail.code_system}")
    
    print("\n" + "=" * 80 + "\n")


def example_3_extract_patient_identifiers():
    """Example 3: Extract and work with patient identifiers."""
    print("=" * 80)
    print("Example 3: Extract Patient Identifiers")
    print("=" * 80)
    
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <acknowledgement>
        <typeCode code="AA"/>
      </acknowledgement>
      <controlActProcess>
        <subject typeCode="SUBJ">
          <registrationEvent>
            <subject1 typeCode="SBJ">
              <patient>
                <id root="2.16.840.1.113883.3.72.5.9.1" extension="LOCAL-12345"/>
                <id root="1.2.840.114350.1.13.99998.8734" extension="EPIC-67890"/>
                <id root="2.16.840.1.113883.4.1" extension="SSN-123456789"/>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
      </controlActProcess>
    </MCCI_IN000002UV01>"""
    
    result = parse_acknowledgment(ack_xml)
    
    # Access primary patient ID
    primary_id = result.patient_identifiers.get('patient_id')
    primary_root = result.patient_identifiers.get('patient_id_root')
    
    print(f"\nPrimary Patient Identifier:")
    print(f"  ID: {primary_id}")
    print(f"  Assigning Authority (OID): {primary_root}")
    
    # Access additional identifiers
    additional_ids = result.patient_identifiers.get('additional_ids', [])
    print(f"\nAdditional Identifiers ({len(additional_ids)}):")
    
    for alt_id in additional_ids:
        print(f"  - {alt_id['extension']} (Authority: {alt_id['root']})")
    
    # Example: Look up identifier by authority
    print("\nLookup by Authority:")
    epic_oid = "1.2.840.114350.1.13.99998.8734"
    
    # Check primary
    if primary_root == epic_oid:
        print(f"  Epic ID (primary): {primary_id}")
    else:
        # Check additional
        for alt_id in additional_ids:
            if alt_id['root'] == epic_oid:
                print(f"  Epic ID: {alt_id['extension']}")
                break
    
    print("\n" + "=" * 80 + "\n")


def example_4_convert_to_dictionary():
    """Example 4: Convert acknowledgment to dictionary for JSON export."""
    print("=" * 80)
    print("Example 4: Convert to Dictionary/JSON")
    print("=" * 80)
    
    ack_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3">
      <id root="2.16.840.1.113883.3.72.5.9.2" extension="ACK-JSON-001"/>
      <acknowledgement>
        <typeCode code="AA"/>
        <targetMessage>
          <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-JSON-001"/>
        </targetMessage>
      </acknowledgement>
      <controlActProcess>
        <subject typeCode="SUBJ">
          <registrationEvent>
            <subject1 typeCode="SBJ">
              <patient>
                <id root="2.16.840.1.113883.3.72.5.9.1" extension="PATIENT-001"/>
              </patient>
            </subject1>
          </registrationEvent>
        </subject>
        <queryAck>
          <queryResponseCode code="OK"/>
          <resultTotalQuantity value="1"/>
          <resultCurrentQuantity value="1"/>
          <resultRemainingQuantity value="0"/>
        </queryAck>
      </controlActProcess>
    </MCCI_IN000002UV01>"""
    
    # Parse acknowledgment
    result = parse_acknowledgment(ack_xml)
    
    # Convert to dictionary
    data = result.to_dict()
    
    # Display as formatted JSON
    print("\nAcknowledgment as JSON:")
    print(json.dumps(data, indent=2))
    
    # Example: Save to file
    # with open('acknowledgment.json', 'w') as f:
    #     json.dump(data, f, indent=2)
    
    # Example: Send as API response
    # return jsonify(data)
    
    print("\n" + "=" * 80 + "\n")


def example_5_complete_workflow():
    """Example 5: Complete workflow from SOAP response to parsed data."""
    print("=" * 80)
    print("Example 5: Complete PIX Add Workflow")
    print("=" * 80)
    
    # Simulated SOAP response from PIX Manager
    soap_response = """<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
      <soap:Header/>
      <soap:Body>
        <MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
          <id root="2.16.840.1.113883.3.72.5.9.2" extension="ACK-WORKFLOW-001"/>
          <creationTime value="20251116144530"/>
          <acknowledgement>
            <typeCode code="AA"/>
            <targetMessage>
              <id root="2.16.840.1.113883.3.72.5.9.1" extension="MSG-WORKFLOW-001"/>
            </targetMessage>
          </acknowledgement>
          <controlActProcess>
            <subject typeCode="SUBJ">
              <registrationEvent>
                <subject1 typeCode="SBJ">
                  <patient>
                    <id root="2.16.840.1.113883.3.72.5.9.1" extension="WORKFLOW-12345"/>
                  </patient>
                </subject1>
              </registrationEvent>
            </subject>
          </controlActProcess>
        </MCCI_IN000002UV01>
      </soap:Body>
    </soap:Envelope>"""
    
    # Step 1: Extract acknowledgment from SOAP envelope
    from lxml import etree
    
    root = etree.fromstring(soap_response.encode("utf-8"))
    namespaces = {
        'soap': 'http://www.w3.org/2003/05/soap-envelope',
        'hl7': 'urn:hl7-org:v3'
    }
    
    ack_elem = root.find('.//hl7:MCCI_IN000002UV01', namespaces)
    if ack_elem is not None:
        ack_xml = etree.tostring(ack_elem, encoding='unicode')
    else:
        ack_xml = soap_response
    
    print("\nStep 1: Extracted acknowledgment from SOAP envelope")
    
    # Step 2: Parse acknowledgment
    result = parse_acknowledgment(ack_xml)
    print(f"Step 2: Parsed acknowledgment - Status: {result.status}")
    
    # Step 3: Log to audit trail (optional)
    # Uncomment to actually log:
    # log_acknowledgment_response(
    #     response_xml=ack_xml,
    #     status=result.status,
    #     message_id=result.message_id
    # )
    print("Step 3: (Would log to audit trail)")
    
    # Step 4: Extract patient identifiers
    patient_id = result.patient_identifiers.get('patient_id')
    print(f"Step 4: Extracted patient ID: {patient_id}")
    
    # Step 5: Check transaction success
    if result.is_success:
        print("\n✓ PIX Add transaction successful!")
        print(f"  Patient registered with ID: {patient_id}")
    else:
        print("\n✗ PIX Add transaction failed!")
        for detail in result.details:
            print(f"  - {detail.text}")
    
    # Step 6: Convert to JSON for storage/API
    data = result.to_dict()
    print("\nStep 6: Converted to JSON format")
    print(f"  Keys: {list(data.keys())}")
    
    print("\n" + "=" * 80 + "\n")


def main():
    """Run all examples."""
    print("\n")
    print("*" * 80)
    print("PIX Add Acknowledgment Parsing Examples")
    print("*" * 80)
    print("\n")
    
    # Run examples
    example_1_parse_successful_acknowledgment()
    example_2_parse_error_acknowledgment()
    example_3_extract_patient_identifiers()
    example_4_convert_to_dictionary()
    example_5_complete_workflow()
    
    print("*" * 80)
    print("All examples completed!")
    print("*" * 80)
    print("\n")


if __name__ == "__main__":
    main()
