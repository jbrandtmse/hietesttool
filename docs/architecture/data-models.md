# Data Models

The IHE Test Utility processes several key data entities throughout its workflow. These models represent the conceptual structure of data as it flows from CSV input through personalization, security, and SOAP submission.

### Patient Demographics

**Purpose:** Represents patient demographic information imported from CSV files and used to personalize CCD documents and PIX Add messages.

**Key Attributes:**
- `patient_id`: str - Unique patient identifier (auto-generated if not provided)
- `patient_id_oid`: str - OID for patient identifier domain (required in CSV)
- `first_name`: str - Patient first name (required)
- `last_name`: str - Patient last name (required)
- `dob`: date - Date of birth in YYYY-MM-DD format (required)
- `gender`: str - Administrative gender code: M, F, O, U (required)
- `mrn`: str (optional) - Medical record number
- `ssn`: str (optional) - Social security number
- `address`: str (optional) - Street address
- `city`: str (optional) - City
- `state`: str (optional) - State/province
- `zip`: str (optional) - Postal code
- `phone`: str (optional) - Contact phone number
- `email`: str (optional) - Contact email

**Relationships:**
- One Patient has one personalized CCD Document
- One Patient generates one PIX Add Message
- One Patient generates one ITI-41 Transaction

**Python Type Representation:**
```python
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class PatientDemographics:
    patient_id: str
    patient_id_oid: str
    first_name: str
    last_name: str
    dob: date
    gender: str  # M, F, O, U
    mrn: Optional[str] = None
    ssn: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
```

### CCD Document

**Purpose:** Represents a personalized HL7 Continuity of Care Document (CCDA) generated from template with patient-specific data.

**Key Attributes:**
- `document_id`: str - Unique document identifier (UUID)
- `patient_id`: str - Reference to patient demographics
- `template_path`: str - Path to XML template used
- `xml_content`: str - Personalized XML document content
- `creation_timestamp`: datetime - Document generation timestamp
- `mime_type`: str - Always "text/xml" for CCDs
- `size_bytes`: int - Document size for metadata
- `sha256_hash`: str - Document hash for integrity verification

**Relationships:**
- Belongs to one Patient
- Referenced in one ITI-41 Transaction

**Python Type Representation:**
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CCDDocument:
    document_id: str
    patient_id: str
    template_path: str
    xml_content: str
    creation_timestamp: datetime
    mime_type: str = "text/xml"
    size_bytes: int = 0
    sha256_hash: str = ""
```

### SAML Assertion

**Purpose:** Represents a SAML 2.0 authentication assertion used to secure SOAP transactions.

**Key Attributes:**
- `assertion_id`: str - Unique assertion ID
- `issuer`: str - SAML assertion issuer identifier
- `subject`: str - Subject (user) identifier
- `audience`: str - Intended audience (endpoint URL)
- `issue_instant`: datetime - Issuance timestamp
- `not_before`: datetime - Validity start time
- `not_on_or_after`: datetime - Validity end time
- `xml_content`: str - Complete SAML assertion XML
- `signature`: str - XML signature element
- `certificate_subject`: str - Signing certificate subject DN
- `generation_method`: str - "template" or "programmatic"

**Relationships:**
- Embedded in PIX Add Message
- Embedded in ITI-41 Transaction

**Python Type Representation:**
```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class SAMLGenerationMethod(Enum):
    TEMPLATE = "template"
    PROGRAMMATIC = "programmatic"

@dataclass
class SAMLAssertion:
    assertion_id: str
    issuer: str
    subject: str
    audience: str
    issue_instant: datetime
    not_before: datetime
    not_on_or_after: datetime
    xml_content: str
    signature: str
    certificate_subject: str
    generation_method: SAMLGenerationMethod
```

### PIX Add Message

**Purpose:** Represents an HL7v3 PRPA_IN201301UV02 patient registration message for PIX Add transactions.

**Key Attributes:**
- `message_id`: str - Unique message identifier (UUID)
- `patient`: PatientDemographics - Patient demographics
- `message_creation_time`: datetime - Message creation timestamp
- `sender_oid`: str - Sending application OID
- `receiver_oid`: str - Receiving application OID
- `hl7v3_xml`: str - Complete HL7v3 message XML
- `saml_assertion`: SAMLAssertion - Embedded SAML for authentication

**Relationships:**
- Contains one PatientDemographics
- Contains one SAMLAssertion
- Results in one PIX Add Acknowledgment

**Python Type Representation:**
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PIXAddMessage:
    message_id: str
    patient: PatientDemographics
    message_creation_time: datetime
    sender_oid: str
    receiver_oid: str
    hl7v3_xml: str
    saml_assertion: SAMLAssertion
```

### ITI-41 Transaction

**Purpose:** Represents a Provide and Register Document Set-b transaction for submitting CCD documents to XDSb repository.

**Key Attributes:**
- `transaction_id`: str - Unique transaction identifier
- `submission_set_id`: str - XDSb submission set unique ID
- `patient_id`: str - Patient identifier from PIX Add
- `patient_id_oid`: str - Patient ID OID
- `ccd_document`: CCDDocument - CCD document to submit
- `submission_timestamp`: datetime - Submission timestamp
- `source_id`: str - Submission source OID
- `saml_assertion`: SAMLAssertion - SAML for authentication
- `mtom_content_id`: str - MTOM attachment content ID
- `soap_xml`: str - Complete SOAP envelope with metadata

**Relationships:**
- Contains one CCDDocument
- Contains one SAMLAssertion
- References one Patient (via patient_id)
- Results in one Registry Response

**Python Type Representation:**
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ITI41Transaction:
    transaction_id: str
    submission_set_id: str
    patient_id: str
    patient_id_oid: str
    ccd_document: CCDDocument
    submission_timestamp: datetime
    source_id: str
    saml_assertion: SAMLAssertion
    mtom_content_id: str
    soap_xml: str
```

### Transaction Response

**Purpose:** Represents acknowledgment or error response from IHE endpoints (PIX Add or ITI-41).

**Key Attributes:**
- `response_id`: str - Response message ID
- `request_id`: str - Original request message ID for correlation
- `transaction_type`: str - "PIX_ADD" or "ITI_41"
- `status`: str - "SUCCESS", "ERROR", "PARTIAL_SUCCESS"
- `status_code`: str - HL7/XDSb status code (e.g., "AA", "AE", "AR")
- `response_timestamp`: datetime - Response receipt timestamp
- `response_xml`: str - Complete SOAP response
- `extracted_identifiers`: dict - Patient IDs from acknowledgment
- `error_messages`: list[str] - Error details if status is ERROR
- `processing_time_ms`: int - Round-trip latency

**Relationships:**
- Corresponds to one PIX Add Message or ITI-41 Transaction

**Python Type Representation:**
```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class TransactionType(Enum):
    PIX_ADD = "PIX_ADD"
    ITI_41 = "ITI_41"

class TransactionStatus(Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"

@dataclass
class TransactionResponse:
    response_id: str
    request_id: str
    transaction_type: TransactionType
    status: TransactionStatus
    status_code: str
    response_timestamp: datetime
    response_xml: str
    extracted_identifiers: dict = field(default_factory=dict)
    error_messages: list[str] = field(default_factory=list)
    processing_time_ms: int = 0
```

### Batch Processing Result

**Purpose:** Aggregates results from processing multiple patients in a batch operation.

**Key Attributes:**
- `batch_id`: str - Unique batch identifier
- `csv_file_path`: str - Source CSV file
- `start_timestamp`: datetime - Batch processing start time
- `end_timestamp`: datetime - Batch processing end time
- `total_patients`: int - Total patients in CSV
- `successful_patients`: int - Patients successfully processed
- `failed_patients`: int - Patients that failed processing
- `pix_add_success_count`: int - Successful PIX Add transactions
- `iti41_success_count`: int - Successful ITI-41 transactions
- `patient_results`: list[PatientResult] - Per-patient results
- `error_summary`: dict - Categorized error statistics

**Relationships:**
- Contains multiple PatientResult entries

**Python Type Representation:**
```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class PatientResult:
    patient_id: str
    pix_add_status: TransactionStatus
    pix_add_message: str
    iti41_status: TransactionStatus
    iti41_message: str
    processing_time_ms: int

@dataclass
class BatchProcessingResult:
    batch_id: str
    csv_file_path: str
    start_timestamp: datetime
    end_timestamp: datetime
    total_patients: int
    successful_patients: int
    failed_patients: int
    pix_add_success_count: int
    iti41_success_count: int
    patient_results: list[PatientResult] = field(default_factory=list)
    error_summary: dict = field(default_factory=dict)
```
