# Core Workflows

This section illustrates key system workflows using sequence diagrams to show component interactions and data flow.

### Workflow 1: CSV Validation and Patient Import

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant CSVParser
    participant ConfigMgr
    participant Logger
    participant FileSystem

    User->>CLI: ihe-test-util csv validate patients.csv
    CLI->>ConfigMgr: load_config()
    ConfigMgr->>FileSystem: read config.json
    FileSystem-->>ConfigMgr: configuration
    ConfigMgr-->>CLI: Config
    
    CLI->>CSVParser: parse_csv("patients.csv")
    CSVParser->>FileSystem: read patients.csv
    FileSystem-->>CSVParser: raw CSV data
    
    CSVParser->>CSVParser: validate_structure()
    CSVParser->>Logger: log("Validating CSV structure...")
    
    alt Valid Structure
        CSVParser->>CSVParser: validate_demographics()
        CSVParser->>CSVParser: check required fields
        CSVParser->>CSVParser: validate date formats
        CSVParser->>CSVParser: validate gender codes
        
        alt All Valid
            CSVParser-->>CLI: ValidationResult(success=True, patients=DataFrame)
            CLI->>Logger: log("✓ CSV validation successful: 10 patients")
            CLI->>User: Success message + patient summary
        else Validation Errors
            CSVParser-->>CLI: ValidationResult(success=False, errors=list)
            CLI->>Logger: log("✗ CSV validation failed")
            CLI->>FileSystem: export_errors("errors.csv")
            CLI->>User: Error report with row numbers
        end
    else Invalid Structure
        CSVParser-->>CLI: ValidationException
        CLI->>Logger: log("✗ Malformed CSV")
        CLI->>User: Error message
    end
```

### Workflow 2: CCD Document Generation from Template

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant CSVParser
    participant TemplateEngine
    participant Logger
    participant FileSystem

    User->>CLI: ihe-test-util template process ccd-template.xml patients.csv
    CLI->>CSVParser: parse_csv("patients.csv")
    CSVParser-->>CLI: DataFrame(patients)
    
    CLI->>TemplateEngine: load_template("ccd-template.xml")
    TemplateEngine->>FileSystem: read template
    FileSystem-->>TemplateEngine: XML template
    TemplateEngine->>TemplateEngine: validate_xml()
    TemplateEngine->>TemplateEngine: extract_placeholders()
    TemplateEngine-->>CLI: Template
    
    loop For each patient in DataFrame
        CLI->>TemplateEngine: personalize_ccd(template, patient)
        TemplateEngine->>TemplateEngine: replace placeholders
        TemplateEngine->>TemplateEngine: format dates
        TemplateEngine->>TemplateEngine: escape XML entities
        TemplateEngine->>TemplateEngine: generate document_id
        TemplateEngine->>TemplateEngine: calculate hash
        TemplateEngine-->>CLI: CCDDocument
        
        CLI->>FileSystem: write_file(f"output/{patient_id}.xml", ccd)
        CLI->>Logger: log(f"✓ Generated CCD for {patient_id}")
    end
    
    CLI->>Logger: log("Batch complete: 10 CCDs generated")
    CLI->>User: Success summary
```

### Workflow 3: SAML Assertion Generation and Signing

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant SAMLModule
    participant ConfigMgr
    participant Logger
    participant FileSystem

    User->>CLI: ihe-test-util saml generate --programmatic
    CLI->>ConfigMgr: get_certificate_paths()
    ConfigMgr-->>CLI: (cert_path, key_path)
    
    CLI->>SAMLModule: generate_programmatic(subject, issuer, audience)
    SAMLModule->>SAMLModule: create assertion structure
    SAMLModule->>SAMLModule: set timestamps (NotBefore, NotOnOrAfter)
    SAMLModule->>SAMLModule: generate assertion_id
    SAMLModule->>SAMLModule: add AuthnStatement
    SAMLModule-->>CLI: unsigned SAML XML
    
    CLI->>SAMLModule: load_certificate(cert_path)
    SAMLModule->>FileSystem: read certificate (PEM/PKCS12/DER)
    FileSystem-->>SAMLModule: certificate data
    SAMLModule->>SAMLModule: parse certificate
    SAMLModule->>SAMLModule: validate expiration
    
    alt Certificate Valid
        SAMLModule-->>CLI: Certificate
        CLI->>SAMLModule: sign_assertion(saml_xml, cert, key)
        SAMLModule->>SAMLModule: canonicalize XML (C14N)
        SAMLModule->>SAMLModule: compute signature (RSA-SHA256)
        SAMLModule->>SAMLModule: embed KeyInfo
        SAMLModule-->>CLI: signed SAML assertion
        
        CLI->>FileSystem: write_file("saml-assertion.xml", signed_saml)
        CLI->>Logger: log("✓ SAML assertion signed successfully")
        CLI->>User: Success + assertion details
    else Certificate Expired/Invalid
        SAMLModule-->>CLI: CertificateException
        CLI->>Logger: log("✗ Certificate validation failed")
        CLI->>User: Error message + troubleshooting guidance
    end
```

### Workflow 4: Complete PIX Add + ITI-41 Submission (Primary Workflow)

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant CSVParser
    participant TemplateEngine
    participant SAMLModule
    participant IHETransactions
    participant Transport
    participant PIXAdd
    participant ITI41
    participant Logger
    participant FileSystem

    User->>CLI: ihe-test-util submit patients.csv --config config.json
    CLI->>CSVParser: parse_csv("patients.csv")
    CSVParser-->>CLI: DataFrame(patients)
    
    CLI->>TemplateEngine: load_template("ccd-template.xml")
    TemplateEngine-->>CLI: Template
    
    CLI->>SAMLModule: generate_and_sign_assertion()
    SAMLModule-->>CLI: SAMLAssertion
    
    loop For each patient (sequential)
        Note over CLI: Step 1: Generate CCD
        CLI->>TemplateEngine: personalize_ccd(template, patient)
        TemplateEngine-->>CLI: CCDDocument
        CLI->>Logger: log("CCD generated for patient {id}")
        
        Note over CLI: Step 2: PIX Add Registration
        CLI->>IHETransactions: build_pix_add_message(patient, saml)
        IHETransactions->>IHETransactions: construct HL7v3 XML
        IHETransactions->>IHETransactions: embed WS-Security header
        IHETransactions-->>CLI: PIXAddMessage
        
        CLI->>IHETransactions: submit_pix_add(message, endpoint)
        IHETransactions->>Transport: send_request(url, soap_envelope)
        Transport->>Logger: log("→ SOAP Request")
        Transport->>FileSystem: write_audit("pix-add-request.xml")
        Transport->>PIXAdd: POST /pix/add
        
        alt PIX Add Success
            PIXAdd-->>Transport: MCCI_IN000002UV01 (AA)
            Transport->>Logger: log("← SOAP Response (AA)")
            Transport->>FileSystem: write_audit("pix-add-response.xml")
            Transport-->>IHETransactions: Response
            IHETransactions->>IHETransactions: parse_pix_acknowledgment()
            IHETransactions-->>CLI: TransactionResponse(SUCCESS, patient_ids)
            CLI->>Logger: log("✓ PIX Add successful for {patient_id}")
            
            Note over CLI: Step 3: ITI-41 Document Submission
            CLI->>IHETransactions: build_iti41_transaction(patient_id, ccd, saml)
            IHETransactions->>IHETransactions: construct XDSb metadata
            IHETransactions->>IHETransactions: create MTOM attachment
            IHETransactions->>IHETransactions: embed WS-Security header
            IHETransactions-->>CLI: ITI41Transaction
            
            CLI->>IHETransactions: submit_iti41(transaction, endpoint)
            IHETransactions->>Transport: send_request(url, mtom_envelope)
            Transport->>Logger: log("→ MTOM Request")
            Transport->>FileSystem: write_audit("iti41-request.xml")
            Transport->>ITI41: POST /iti41/submit
            
            alt ITI-41 Success
                ITI41-->>Transport: RegistryResponse (Success)
                Transport->>Logger: log("← RegistryResponse (Success)")
                Transport->>FileSystem: write_audit("iti41-response.xml")
                Transport-->>IHETransactions: Response
                IHETransactions->>IHETransactions: parse_registry_response()
                IHETransactions-->>CLI: TransactionResponse(SUCCESS, document_ids)
                CLI->>Logger: log("✓ ITI-41 successful for {patient_id}")
                CLI->>CLI: increment success_count
            else ITI-41 Failure
                ITI41-->>Transport: RegistryResponse (Failure)
                Transport->>Logger: log("← RegistryResponse (Failure)")
                Transport-->>IHETransactions: Response
                IHETransactions->>IHETransactions: parse_error_details()
                IHETransactions-->>CLI: TransactionResponse(ERROR, error_msg)
                CLI->>Logger: log("✗ ITI-41 failed: {error_msg}")
                CLI->>CLI: increment failed_count
            end
        else PIX Add Failure
            PIXAdd-->>Transport: MCCI_IN000002UV01 (AE/AR)
            Transport->>Logger: log("← SOAP Response (AE)")
            Transport-->>IHETransactions: Response
            IHETransactions->>IHETransactions: parse_error_details()
            IHETransactions-->>CLI: TransactionResponse(ERROR, error_msg)
            CLI->>Logger: log("✗ PIX Add failed: {error_msg}")
            CLI->>Logger: log("⊘ Skipping ITI-41 for {patient_id}")
            CLI->>CLI: increment failed_count
        end
    end
    
    CLI->>CLI: generate BatchProcessingResult
    CLI->>FileSystem: write_file("results.json", results)
    CLI->>Logger: log("Batch complete: {success}/{total} patients")
    CLI->>User: Display summary report
```

### Workflow 5: Error Handling with Retry Logic

```mermaid
sequenceDiagram
    participant IHETransactions
    participant Transport
    participant Endpoint
    participant Logger

    IHETransactions->>Transport: send_request(url, body)
    Transport->>Logger: log("Attempt 1/3")
    Transport->>Endpoint: POST request
    
    alt Network Timeout
        Endpoint--xTransport: Timeout (no response)
        Transport->>Logger: log("⚠ Timeout on attempt 1")
        Transport->>Transport: sleep(1s backoff)
        Transport->>Logger: log("Attempt 2/3")
        Transport->>Endpoint: POST request (retry)
        
        alt Success on Retry
            Endpoint-->>Transport: 200 OK
            Transport->>Logger: log("✓ Success on attempt 2")
            Transport-->>IHETransactions: Response
        else Timeout Again
            Endpoint--xTransport: Timeout
            Transport->>Logger: log("⚠ Timeout on attempt 2")
            Transport->>Transport: sleep(2s backoff)
            Transport->>Logger: log("Attempt 3/3")
            Transport->>Endpoint: POST request (retry)
            
            alt Final Success
                Endpoint-->>Transport: 200 OK
                Transport->>Logger: log("✓ Success on attempt 3")
                Transport-->>IHETransactions: Response
            else Final Failure
                Endpoint--xTransport: Timeout
                Transport->>Logger: log("✗ All retries exhausted")
                Transport-->>IHETransactions: TransportException
            end
        end
    else SOAP Fault
        Endpoint-->>Transport: 500 SOAP Fault
        Transport->>Logger: log("✗ SOAP Fault received")
        Transport->>Transport: parse_soap_fault()
        Transport-->>IHETransactions: SOAPException(fault_details)
        Note over IHETransactions: No retry for SOAP faults
    else Server Error (502/503/504)
        Endpoint-->>Transport: 503 Service Unavailable
        Transport->>Logger: log("⚠ Server error 503")
        Transport->>Transport: sleep(1s backoff)
        Transport->>Endpoint: POST request (retry)
        Note over Transport: Retry up to 3 times for server errors
    end
```

### Workflow 6: Mock Server Testing

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant MockServer
    participant IHETransactions
    participant Logger

    User->>CLI: ihe-test-util mock start --https
    CLI->>MockServer: start_server(host="localhost", port=8443, protocol="https")
    MockServer->>MockServer: load_config()
    MockServer->>MockServer: setup_routes(/pix/add, /iti41/submit)
    MockServer->>MockServer: configure_ssl()
    MockServer-->>CLI: Server started
    CLI->>Logger: log("✓ Mock server running on https://localhost:8443")
    CLI->>User: "Mock endpoints ready"
    
    Note over User,Logger: Separate terminal: run tests
    User->>CLI: ihe-test-util submit patients.csv --endpoint https://localhost:8443
    
    CLI->>IHETransactions: submit_pix_add(message, "https://localhost:8443/pix/add")
    IHETransactions->>MockServer: POST /pix/add
    MockServer->>Logger: log("Mock: Received PIX Add request")
    MockServer->>MockServer: validate_soap_structure()
    MockServer->>MockServer: generate_static_response()
    MockServer->>MockServer: apply_configured_delay(100ms)
    MockServer-->>IHETransactions: MCCI_IN000002UV01 (AA)
    MockServer->>Logger: log("Mock: Returned PIX Add acknowledgment")
    
    IHETransactions->>MockServer: POST /iti41/submit
    MockServer->>Logger: log("Mock: Received ITI-41 request")
    MockServer->>MockServer: validate_mtom_structure()
    MockServer->>MockServer: extract_document()
    MockServer->>MockServer: save_document("mocks/data/documents/")
    MockServer->>MockServer: generate_registry_response()
    MockServer-->>IHETransactions: RegistryResponse (Success)
    MockServer->>Logger: log("Mock: Returned ITI-41 response")
    
    Note over User,Logger: After testing
    User->>CLI: ihe-test-util mock stop
    CLI->>MockServer: stop_server()
    MockServer->>MockServer: cleanup()
    MockServer-->>CLI: Server stopped
    CLI->>Logger: log("✓ Mock server stopped")
    CLI->>User: "Mock endpoints stopped"
```

---
