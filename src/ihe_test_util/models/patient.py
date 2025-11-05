"""Patient demographics data model.

This module defines the PatientDemographics dataclass used throughout the application
for representing patient demographic information.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class PatientDemographics:
    """Patient demographic information for IHE transactions.

    Attributes:
        patient_id: Unique patient identifier (auto-generated if empty during import)
        patient_id_oid: OID for patient identifier domain (required)
        first_name: Patient's first name
        last_name: Patient's last name
        dob: Date of birth
        gender: Administrative gender (M=Male, F=Female, O=Other, U=Unknown)
        mrn: Medical record number (optional)
        ssn: Social security number (optional)
        address: Street address (optional)
        city: City (optional)
        state: State/province (optional)
        zip: Postal code (optional)
        phone: Contact phone number (optional)
        email: Contact email (optional)
    """

    patient_id: str
    patient_id_oid: str
    first_name: str
    last_name: str
    dob: date
    gender: str  # M, F, O, U
    mrn: str | None = None
    ssn: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    phone: str | None = None
    email: str | None = None
