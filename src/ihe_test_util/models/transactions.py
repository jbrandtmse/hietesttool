"""Transaction models for IHE transactions.

This module defines dataclasses for IHE transaction messages and responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ihe_test_util.models.ccd import CCDDocument
from ihe_test_util.models.saml import SAMLAssertion


@dataclass
class PIXAddMessage:
    """PIX Add (ITI-8/ITI-44) message.
    
    Attributes:
        message_id: Unique message identifier
        patient_id: Patient identifier
        patient_id_oid: Patient identifier domain OID
        given_name: Patient given name
        family_name: Patient family name
        gender: Patient gender (M, F, O, U)
        birth_date: Patient birth date (YYYYMMDD format)
        street_address: Patient street address
        city: Patient city
        state: Patient state/province
        postal_code: Patient postal code
        sender_oid: Sender facility OID
        receiver_oid: Receiver facility OID
        timestamp: Message timestamp
        soap_xml: Complete SOAP message XML
    """
    
    message_id: str
    patient_id: str
    patient_id_oid: str
    given_name: str
    family_name: str
    gender: str
    birth_date: str
    street_address: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    sender_oid: str = ""
    receiver_oid: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    soap_xml: str = ""


@dataclass
class ITI41Transaction:
    """ITI-41 Provide and Register Document Set-b transaction.
    
    Attributes:
        transaction_id: Unique transaction identifier
        submission_set_id: Generated submission set ID
        document_entry_id: Generated document entry ID
        patient_id: Patient identifier
        patient_id_oid: Patient identifier domain OID
        ccd_document: CCD document being submitted
        submission_timestamp: Timestamp of submission
        source_id: Source facility OID
        saml_assertion: Optional SAML assertion for security
        mtom_content_id: Content-ID for MTOM attachment
        metadata_xml: Generated XDSb metadata XML
        soap_xml: Complete SOAP envelope XML
    """
    
    transaction_id: str
    submission_set_id: str
    document_entry_id: str
    patient_id: str
    patient_id_oid: str
    ccd_document: CCDDocument
    submission_timestamp: datetime
    source_id: str
    saml_assertion: Optional[SAMLAssertion] = None
    mtom_content_id: str = ""
    metadata_xml: str = ""
    soap_xml: str = ""


@dataclass
class TransactionResponse:
    """Generic response from IHE transaction.
    
    Attributes:
        transaction_id: Original transaction ID
        success: Whether transaction succeeded
        status_code: Response status code
        status_message: Human-readable status message
        response_xml: Full response XML
        timestamp: Response timestamp
        errors: List of error messages if failed
    """
    
    transaction_id: str
    success: bool
    status_code: str = ""
    status_message: str = ""
    response_xml: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    errors: list[str] = field(default_factory=list)
