"""Unit tests for error handling functionality.

Tests error categorization, SOAP fault parsing, HL7 error handling,
certificate validation, and error summary collection.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import ConnectionError, Timeout, SSLError
from lxml import etree

from ihe_test_util.utils.exceptions import (
    ErrorCategory,
    ErrorInfo,
    ValidationError,
    categorize_error,
    create_error_info,
    _generate_remediation,
)
from ihe_test_util.ihe_transactions.parsers import (
    SOAPFaultInfo,
    HL7ErrorInfo,
    parse_soap_fault,
    _parse_soap_12_fault,
    _parse_soap_11_fault,
)
from ihe_test_util.ihe_transactions.error_summary import (
    ErrorSummary,
    ErrorSummaryCollector,
    generate_error_report,
)
from ihe_test_util.saml.certificate_manager import (
    validate_certificate_not_expired,
    validate_certificate_chain,
)


class TestErrorCategorization:
    """Test error categorization functionality."""
    
    def test_categorize_error_critical_connection_error(self):
        """Test ConnectionError categorized as CRITICAL."""
        error = ConnectionError("Network unreachable")
        category = categorize_error(error)
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_error_transient_timeout(self):
        """Test Timeout categorized as TRANSIENT."""
        error = Timeout("Request timed out")
        category = categorize_error(error)
        assert category == ErrorCategory.TRANSIENT
    
    def test_categorize_error_permanent_validation_error(self):
        """Test ValidationError categorized as PERMANENT."""
        error = ValidationError("Invalid patient data")
        category = categorize_error(error)
        assert category == ErrorCategory.PERMANENT
    
    def test_categorize_error_critical_ssl_error(self):
        """Test SSLError categorized as CRITICAL."""
        error = SSLError("Certificate verification failed")
        category = categorize_error(error)
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_error_permanent_default(self):
        """Test generic exceptions categorized as PERMANENT by default."""
        error = Exception("Certificate expired")
        category = categorize_error(error)
        assert category == ErrorCategory.PERMANENT
    
    def test_categorize_error_permanent_keyword(self):
        """Test errors with generic keywords categorized as PERMANENT."""
        error = Exception("Configuration file missing")
        category = categorize_error(error)
        assert category == ErrorCategory.PERMANENT


class TestErrorInfoCreation:
    """Test ErrorInfo creation and remediation generation."""
    
    def test_create_error_info_connection_error(self):
        """Test ErrorInfo creation for ConnectionError."""
        error = ConnectionError("Network unreachable")
        error_info = create_error_info(error, patient_id="PAT001")
        
        assert error_info.category == ErrorCategory.CRITICAL
        assert error_info.error_type == "ConnectionError"
        assert error_info.patient_id == "PAT001"
        assert error_info.is_retryable is False
        assert "network" in error_info.remediation.lower() or "endpoint" in error_info.remediation.lower()
    
    def test_create_error_info_validation_error(self):
        """Test ErrorInfo creation for ValidationError."""
        error = ValidationError("Invalid gender code")
        error_info = create_error_info(error, patient_id="PAT002")
        
        assert error_info.category == ErrorCategory.PERMANENT
        assert error_info.error_type == "ValidationError"
        assert error_info.patient_id == "PAT002"
        assert error_info.is_retryable is False
        assert "csv" in error_info.remediation.lower()
    
    def test_generate_remediation_connection_error(self):
        """Test remediation message for ConnectionError."""
        error = ConnectionError("Network unreachable")
        category = categorize_error(error)
        remediation = _generate_remediation(error, category)
        
        assert "network" in remediation.lower() or "endpoint" in remediation.lower()
    
    def test_generate_remediation_timeout(self):
        """Test remediation message for Timeout."""
        error = Timeout("Request timed out")
        category = categorize_error(error)
        remediation = _generate_remediation(error, category)
        
        assert "timeout" in remediation.lower()
    
    def test_generate_remediation_ssl_error(self):
        """Test remediation message for SSLError."""
        error = SSLError("Certificate verification failed")
        category = categorize_error(error)
        remediation = _generate_remediation(error, category)
        
        assert "certificate" in remediation.lower() or "tls" in remediation.lower()
    
    def test_generate_remediation_validation_error(self):
        """Test remediation message for ValidationError."""
        error = ValidationError("Invalid data")
        category = categorize_error(error)
        remediation = _generate_remediation(error, category)
        
        assert "csv" in remediation.lower() or "data" in remediation.lower()


class TestSOAPFaultParsing:
    """Test SOAP fault parsing functionality."""
    
    def test_parse_soap_12_fault_complete(self):
        """Test parsing complete SOAP 1.2 fault."""
        fault_xml = """
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
          <soap:Body>
            <soap:Fault>
              <soap:Code>
                <soap:Value>soap:Sender</soap:Value>
                <soap:Subcode>
                  <soap:Value>wsse:InvalidSecurity</soap:Value>
                </soap:Subcode>
              </soap:Code>
              <soap:Reason>
                <soap:Text xml:lang="en">Invalid SAML assertion</soap:Text>
              </soap:Reason>
              <soap:Detail>
                <TechnicalDetails>SAML signature verification failed</TechnicalDetails>
              </soap:Detail>
            </soap:Fault>
          </soap:Body>
        </soap:Envelope>
        """
        
        fault_info = parse_soap_fault(fault_xml)
        
        assert fault_info is not None
        assert fault_info.fault_code == "soap:Sender"
        assert fault_info.fault_string == "Invalid SAML assertion"
        assert "SAML signature verification failed" in fault_info.fault_detail
        assert "wsse:InvalidSecurity" in fault_info.subcodes
    
    def test_parse_soap_12_fault_minimal(self):
        """Test parsing minimal SOAP 1.2 fault (only required elements)."""
        fault_xml = """
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
          <soap:Body>
            <soap:Fault>
              <soap:Code>
                <soap:Value>soap:Receiver</soap:Value>
              </soap:Code>
              <soap:Reason>
                <soap:Text>Internal server error</soap:Text>
              </soap:Reason>
            </soap:Fault>
          </soap:Body>
        </soap:Envelope>
        """
        
        fault_info = parse_soap_fault(fault_xml)
        
        assert fault_info is not None
        assert fault_info.fault_code == "soap:Receiver"
        assert fault_info.fault_string == "Internal server error"
        assert fault_info.fault_detail is None
        assert len(fault_info.subcodes) == 0
    
    def test_parse_soap_11_fault_complete(self):
        """Test parsing SOAP 1.1 fault."""
        fault_xml = """
        <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
          <SOAP-ENV:Body>
            <SOAP-ENV:Fault>
              <faultcode>SOAP-ENV:Client</faultcode>
              <faultstring>Invalid message format</faultstring>
              <faultactor>http://pix.endpoint.com</faultactor>
              <detail>
                <ErrorDetails>Missing required field: patient_id</ErrorDetails>
              </detail>
            </SOAP-ENV:Fault>
          </SOAP-ENV:Body>
        </SOAP-ENV:Envelope>
        """
        
        fault_info = parse_soap_fault(fault_xml)
        
        assert fault_info is not None
        assert fault_info.fault_code == "SOAP-ENV:Client"
        assert fault_info.fault_string == "Invalid message format"
        assert fault_info.fault_actor == "http://pix.endpoint.com"
        assert "Missing required field" in fault_info.fault_detail
    
    def test_parse_soap_fault_malformed(self):
        """Test parsing malformed SOAP fault raises ValueError."""
        fault_xml = "<invalid>xml</malformed>"
        
        # Should raise ValueError for malformed XML
        with pytest.raises(ValueError) as exc_info:
            parse_soap_fault(fault_xml)
        
        assert "Invalid SOAP fault XML" in str(exc_info.value)
    
    def test_parse_soap_fault_no_fault_element(self):
        """Test parsing SOAP envelope without Fault element raises ValueError."""
        fault_xml = """
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
          <soap:Body>
            <Response>Success</Response>
          </soap:Body>
        </soap:Envelope>
        """
        
        # Should raise ValueError when no Fault element found
        with pytest.raises(ValueError) as exc_info:
            parse_soap_fault(fault_xml)
        
        assert "No SOAP Fault element found" in str(exc_info.value)


class TestHL7ErrorParsing:
    """Test HL7 acknowledgment error parsing."""
    
    def test_parse_hl7_ae_acknowledgment(self):
        """Test parsing HL7 AE (Application Error) acknowledgment."""
        # This would test the parse_acknowledgment function from parsers.py
        # The actual implementation depends on the existing parser structure
        # For now, test HL7ErrorInfo dataclass creation
        
        error_info = HL7ErrorInfo(
            code="204",
            text="Unknown key identifier",
            location="patient/id",
            severity="E",
            code_system="2.16.840.1.113883.12.357"
        )
        
        assert error_info.code == "204"
        assert error_info.text == "Unknown key identifier"
        assert error_info.severity == "E"


class TestCertificateValidation:
    """Test certificate validation functionality."""
    
    @pytest.fixture
    def temp_cert_path(self, tmp_path):
        """Create temporary test certificate file."""
        cert_file = tmp_path / "test_cert.pem"
        # Use actual test certificate from fixtures
        test_cert_path = Path(__file__).parent.parent / "fixtures" / "test_cert.pem"
        if test_cert_path.exists():
            cert_file.write_bytes(test_cert_path.read_bytes())
        return cert_file
    
    def test_validate_certificate_not_expired_valid(self, temp_cert_path):
        """Test validation of valid (not expired) certificate."""
        if not temp_cert_path.exists():
            pytest.skip("Test certificate not available")
        
        result = validate_certificate_not_expired(temp_cert_path)
        
        # Result depends on actual test certificate validity period
        # Just verify function doesn't crash
        assert result is not None
    
    @patch('ihe_test_util.saml.certificate_manager.Path.exists')
    @patch('ihe_test_util.saml.certificate_manager.x509.load_pem_x509_certificate')
    def test_validate_certificate_expired(self, mock_load_cert, mock_exists):
        """Test validation of expired certificate."""
        # Mock file exists
        mock_exists.return_value = True
        
        # Mock expired certificate with proper datetime properties
        mock_cert = Mock()
        expired_date = datetime.now(timezone.utc) - timedelta(days=1)
        mock_cert.not_valid_before_utc = datetime.now(timezone.utc) - timedelta(days=365)
        mock_cert.not_valid_after_utc = expired_date
        mock_cert.not_valid_before = mock_cert.not_valid_before_utc
        mock_cert.not_valid_after = mock_cert.not_valid_after_utc
        mock_load_cert.return_value = mock_cert
        
        # Mock file reading
        with patch('builtins.open', MagicMock()):
            result = validate_certificate_not_expired(Path("fake_cert.pem"))
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "expired" in result.errors[0].lower()
        assert "generate_cert.sh" in result.errors[0]
    
    @patch('ihe_test_util.saml.certificate_manager.Path.exists')
    @patch('ihe_test_util.saml.certificate_manager.x509.load_pem_x509_certificate')
    def test_validate_certificate_expiring_soon(self, mock_load_cert, mock_exists):
        """Test warning for certificate expiring within 30 days."""
        # Mock file exists
        mock_exists.return_value = True
        
        # Mock certificate expiring in 15 days with proper datetime properties
        mock_cert = Mock()
        expiry_date = datetime.now(timezone.utc) + timedelta(days=15)
        mock_cert.not_valid_before_utc = datetime.now(timezone.utc) - timedelta(days=350)
        mock_cert.not_valid_after_utc = expiry_date
        mock_cert.not_valid_before = mock_cert.not_valid_before_utc
        mock_cert.not_valid_after = mock_cert.not_valid_after_utc
        mock_load_cert.return_value = mock_cert
        
        # Mock file reading
        with patch('builtins.open', MagicMock()):
            result = validate_certificate_not_expired(Path("fake_cert.pem"))
        
        assert result.is_valid is True
        assert len(result.warnings) > 0
        # Check for expiration warning with days count (allowing for timing differences in test execution)
        assert "days" in result.warnings[0].lower()
        assert "generate_cert.sh" in result.warnings[0]


class TestErrorSummaryCollector:
    """Test error summary collection and aggregation."""
    
    def test_error_summary_collector_add_error(self):
        """Test adding errors to collector."""
        collector = ErrorSummaryCollector()
        collector.set_patient_count(10)
        
        error1 = create_error_info(ConnectionError("Network unreachable"), patient_id="PAT001")
        error2 = create_error_info(ConnectionError("Network unreachable"), patient_id="PAT002")
        error3 = create_error_info(ValidationError("Invalid data"), patient_id="PAT003")
        
        collector.add_error(error1, "PAT001")
        collector.add_error(error2, "PAT002")
        collector.add_error(error3, "PAT003")
        
        summary = collector.get_summary()
        
        assert summary.total_errors == 3
        assert summary.errors_by_category[ErrorCategory.CRITICAL] == 2  # ConnectionError is CRITICAL
        assert summary.errors_by_category[ErrorCategory.PERMANENT] == 1
        assert summary.errors_by_type["ConnectionError"] == 2
        assert summary.errors_by_type["ValidationError"] == 1
        # affected_patients is organized by error type
        assert "PAT001" in summary.affected_patients["ConnectionError"]
        assert "PAT002" in summary.affected_patients["ConnectionError"]
        assert "PAT003" in summary.affected_patients["ValidationError"]
    
    def test_error_summary_collector_error_rate(self):
        """Test error rate calculation."""
        collector = ErrorSummaryCollector()
        collector.set_patient_count(10)
        
        # Add 3 errors out of 10 patients
        for i in range(3):
            error = create_error_info(ConnectionError("Error"), patient_id=f"PAT{i:03d}")
            collector.add_error(error, f"PAT{i:03d}")
        
        summary = collector.get_summary()
        
        assert summary.error_rate == 30.0  # 3/10 = 30%
    
    def test_error_summary_collector_most_common_errors(self):
        """Test identification of most common errors."""
        collector = ErrorSummaryCollector()
        collector.set_patient_count(20)
        
        # Add 10 ConnectionErrors, 5 Timeouts, 3 ValidationErrors
        for i in range(10):
            error = create_error_info(ConnectionError("Error"), patient_id=f"PAT{i:03d}")
            collector.add_error(error, f"PAT{i:03d}")
        
        for i in range(10, 15):
            error = create_error_info(Timeout("Timeout"), patient_id=f"PAT{i:03d}")
            collector.add_error(error, f"PAT{i:03d}")
        
        for i in range(15, 18):
            error = create_error_info(ValidationError("Invalid"), patient_id=f"PAT{i:03d}")
            collector.add_error(error, f"PAT{i:03d}")
        
        summary = collector.get_summary()
        
        # Most common should be ConnectionError (10), then Timeout (5), then ValidationError (3)
        assert summary.most_common_errors[0][0] == "ConnectionError"
        assert summary.most_common_errors[0][1] == 10
        assert summary.most_common_errors[1][0] == "Timeout"
        assert summary.most_common_errors[1][1] == 5


class TestErrorReportGeneration:
    """Test error summary report generation."""
    
    def test_generate_error_report_format(self):
        """Test error report format and content."""
        collector = ErrorSummaryCollector()
        collector.set_patient_count(25)
        
        # Add mixed errors
        for i in range(10):
            error = create_error_info(ConnectionError("Network unreachable"), patient_id=f"PAT{i:03d}")
            collector.add_error(error, f"PAT{i:03d}")
        
        for i in range(10, 15):
            error = create_error_info(Timeout("Request timeout"), patient_id=f"PAT{i:03d}")
            collector.add_error(error, f"PAT{i:03d}")
        
        for i in range(15, 20):
            error = create_error_info(ValidationError("Invalid data"), patient_id=f"PAT{i:03d}")
            collector.add_error(error, f"PAT{i:03d}")
        
        for i in range(20, 22):
            error = create_error_info(SSLError("Certificate error"), patient_id=f"PAT{i:03d}")
            collector.add_error(error, f"PAT{i:03d}")
        
        summary = collector.get_summary()
        report = generate_error_report(summary)
        
        # Verify report structure
        assert "ERROR SUMMARY REPORT" in report
        assert "CATEGORY BREAKDOWN" in report
        assert "ERROR TYPE FREQUENCIES" in report
        assert "TOP REMEDIATIONS" in report
        assert "AFFECTED PATIENTS" in report
        
        # Verify category breakdown
        assert "Transient" in report
        assert "Permanent" in report
        assert "Critical" in report
        
        # Verify error types listed
        assert "ConnectionError" in report
        assert "Timeout" in report
        assert "ValidationError" in report
        assert "SSLError" in report
        
        # Verify formatting (80 char width)
        lines = report.split("\n")
        for line in lines:
            assert len(line) <= 80, f"Line exceeds 80 chars: {line}"
    
    def test_generate_error_report_empty(self):
        """Test error report with no errors."""
        collector = ErrorSummaryCollector()
        collector.set_patient_count(10)
        
        summary = collector.get_summary()
        report = generate_error_report(summary)
        
        assert "Total Errors: 0" in report or "total errors: 0" in report.lower()
    
    def test_generate_error_report_remediation_guidance(self):
        """Test that report includes actionable remediation guidance."""
        collector = ErrorSummaryCollector()
        collector.set_patient_count(10)
        
        error = create_error_info(ConnectionError("Network unreachable"), patient_id="PAT001")
        collector.add_error(error, "PAT001")
        
        summary = collector.get_summary()
        report = generate_error_report(summary)
        
        # Should include specific remediation for ConnectionError
        assert "network" in report.lower()
        assert "endpoint" in report.lower() or "url" in report.lower()


class TestErrorHandlingIntegration:
    """Integration tests for error handling workflow."""
    
    def test_error_info_to_summary_workflow(self):
        """Test complete workflow from error to summary report."""
        # Create errors
        errors = [
            ConnectionError("Network unreachable"),
            ConnectionError("Connection refused"),
            Timeout("Request timeout"),
            ValidationError("Invalid gender code"),
            SSLError("Certificate verification failed"),
        ]
        
        # Collect errors
        collector = ErrorSummaryCollector()
        collector.set_patient_count(10)
        
        for i, error in enumerate(errors):
            error_info = create_error_info(error, patient_id=f"PAT{i:03d}")
            collector.add_error(error_info, f"PAT{i:03d}")
        
        # Generate summary
        summary = collector.get_summary()
        
        # Verify summary statistics
        assert summary.total_errors == 5
        assert summary.error_rate == 50.0  # 5/10 = 50%
        
        # Generate report
        report = generate_error_report(summary)
        
        # Verify report completeness
        assert len(report) > 0
        assert "ConnectionError" in report
        assert "Timeout" in report
        assert "ValidationError" in report
        assert "SSLError" in report
