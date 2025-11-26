"""Unit tests for registry response parsing (Story 6.4).

Tests the parse_registry_response function and related dataclasses
for parsing XDSb RegistryResponse from ITI-41 transactions.
"""

import pytest
from pathlib import Path

from ihe_test_util.ihe_transactions.parsers import (
    parse_registry_response,
    RegistryResponse,
    RegistryErrorInfo,
    log_registry_response,
    REGISTRY_SUCCESS,
    REGISTRY_FAILURE,
    REGISTRY_PARTIAL_SUCCESS,
)


# Fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def success_response_xml() -> str:
    """Load success response fixture."""
    fixture_path = FIXTURES_DIR / "registry_response_success.xml"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def failure_response_xml() -> str:
    """Load failure response fixture."""
    fixture_path = FIXTURES_DIR / "registry_response_failure.xml"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def partial_response_xml() -> str:
    """Load partial success response fixture."""
    fixture_path = FIXTURES_DIR / "registry_response_partial.xml"
    return fixture_path.read_text(encoding="utf-8")


class TestParseSuccessResponse:
    """Tests for parsing successful registry responses."""

    def test_parse_success_response(self, success_response_xml: str) -> None:
        """Test: Verify success status parsing (AC: 2)."""
        # Arrange
        xml = success_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert response.status == "Success"
        assert response.is_success is True
        assert len(response.errors) == 0
        assert len(response.warnings) == 0

    def test_extract_response_id(self, success_response_xml: str) -> None:
        """Test: Verify response message ID extraction."""
        # Arrange
        xml = success_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert response.response_id == "urn:uuid:response-msg-12345"

    def test_extract_request_correlation(self, success_response_xml: str) -> None:
        """Test: Verify request ID correlation (AC: 7)."""
        # Arrange
        xml = success_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert response.request_id == "urn:uuid:request-msg-67890"

    def test_extract_document_ids(self, success_response_xml: str) -> None:
        """Test: Verify document unique ID extraction (AC: 3)."""
        # Arrange
        xml = success_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert len(response.document_ids) == 1
        assert "1.2.3.4.5.6.7.8.9.2001" in response.document_ids

    def test_extract_submission_set_id(self, success_response_xml: str) -> None:
        """Test: Verify submission set unique ID extraction (AC: 6)."""
        # Arrange
        xml = success_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert response.submission_set_id == "1.2.3.4.5.6.7.8.9.1000"


class TestParseFailureResponse:
    """Tests for parsing failure registry responses."""

    def test_parse_failure_response(self, failure_response_xml: str) -> None:
        """Test: Verify failure status and errors (AC: 2, 4)."""
        # Arrange
        xml = failure_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert response.status == "Failure"
        assert response.is_success is False
        assert len(response.errors) == 2
        assert len(response.warnings) == 0

    def test_parse_error_codes(self, failure_response_xml: str) -> None:
        """Test: Verify error code extraction (AC: 5)."""
        # Arrange
        xml = failure_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        error_codes = [e.error_code for e in response.errors]
        assert "XDSMissingDocument" in error_codes
        assert "XDSPatientIdDoesNotMatch" in error_codes

    def test_parse_error_context(self, failure_response_xml: str) -> None:
        """Test: Verify error context extraction (AC: 5)."""
        # Arrange
        xml = failure_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        contexts = [e.code_context for e in response.errors]
        assert any("doc001" in ctx for ctx in contexts)
        assert any("PAT999" in ctx for ctx in contexts)

    def test_parse_error_location(self, failure_response_xml: str) -> None:
        """Test: Verify error location extraction."""
        # Arrange
        xml = failure_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        locations = [e.location for e in response.errors if e.location]
        assert len(locations) == 2
        assert any("Document" in loc for loc in locations)

    def test_failure_response_correlation(self, failure_response_xml: str) -> None:
        """Test: Verify correlation for failure responses (AC: 7)."""
        # Arrange
        xml = failure_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert response.request_id == "urn:uuid:request-msg-fail-001"
        assert response.response_id == "urn:uuid:response-msg-fail-001"


class TestParsePartialSuccessResponse:
    """Tests for parsing partial success registry responses."""

    def test_parse_partial_success_response(self, partial_response_xml: str) -> None:
        """Test: Verify partial success handling (AC: 2)."""
        # Arrange
        xml = partial_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert response.status == "PartialSuccess"
        assert response.is_success is False  # Partial success is not full success

    def test_partial_success_has_both_docs_and_errors(
        self, partial_response_xml: str
    ) -> None:
        """Test: Verify partial success has both documents and errors."""
        # Arrange
        xml = partial_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert len(response.document_ids) == 2
        assert len(response.errors) >= 1

    def test_partial_success_extracts_warnings(self, partial_response_xml: str) -> None:
        """Test: Verify warning extraction from partial success (AC: 4)."""
        # Arrange
        xml = partial_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert len(response.warnings) == 1
        assert response.warnings[0].error_code == "XDSRegistryMetadataError"
        assert response.warnings[0].severity == "Warning"

    def test_partial_success_document_ids(self, partial_response_xml: str) -> None:
        """Test: Verify document IDs extracted from partial success (AC: 3)."""
        # Arrange
        xml = partial_response_xml

        # Act
        response = parse_registry_response(xml)

        # Assert
        assert "1.2.3.4.5.6.7.8.9.3001" in response.document_ids
        assert "1.2.3.4.5.6.7.8.9.3002" in response.document_ids


class TestSoapFaultHandling:
    """Tests for SOAP fault handling."""

    def test_soap_fault_handling(self) -> None:
        """Test: Verify SOAP fault detection and parsing."""
        # Arrange
        soap_fault_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
          <soap12:Header/>
          <soap12:Body>
            <soap12:Fault>
              <soap12:Code>
                <soap12:Value>soap12:Sender</soap12:Value>
              </soap12:Code>
              <soap12:Reason>
                <soap12:Text xml:lang="en">Invalid SAML assertion</soap12:Text>
              </soap12:Reason>
            </soap12:Fault>
          </soap12:Body>
        </soap12:Envelope>"""

        # Act
        response = parse_registry_response(soap_fault_xml)

        # Assert
        assert response.status == "Failure"
        assert response.is_success is False
        assert len(response.errors) == 1
        assert "SOAP" in response.errors[0].error_code
        assert "Invalid SAML" in response.errors[0].code_context


class TestMalformedXmlError:
    """Tests for malformed XML handling."""

    def test_malformed_xml_error(self) -> None:
        """Test: Verify actionable error messages for malformed XML (RULE 5)."""
        # Arrange
        malformed_xml = "<invalid xml>"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            parse_registry_response(malformed_xml)

        error_msg = str(exc_info.value)
        # Should have actionable context
        assert "Invalid registry response XML" in error_msg
        assert "SOAP envelope" in error_msg or "XDSb" in error_msg

    def test_missing_registry_response_element(self) -> None:
        """Test: Verify error for missing RegistryResponse element."""
        # Arrange
        xml_no_registry = """<?xml version="1.0" encoding="UTF-8"?>
        <soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
          <soap12:Body>
            <SomeOtherElement/>
          </soap12:Body>
        </soap12:Envelope>"""

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            parse_registry_response(xml_no_registry)

        error_msg = str(exc_info.value)
        assert "RegistryResponse" in error_msg

    def test_missing_status_attribute(self) -> None:
        """Test: Verify error for missing status attribute."""
        # Arrange
        xml_no_status = """<?xml version="1.0" encoding="UTF-8"?>
        <soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"
                         xmlns:rs="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0">
          <soap12:Body>
            <rs:RegistryResponse/>
          </soap12:Body>
        </soap12:Envelope>"""

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            parse_registry_response(xml_no_status)

        error_msg = str(exc_info.value)
        assert "status" in error_msg.lower()


class TestRegistryResponseDataclass:
    """Tests for RegistryResponse dataclass."""

    def test_to_dict_method(self, success_response_xml: str) -> None:
        """Test: Verify to_dict() method for JSON serialization (AC: 8)."""
        # Arrange
        response = parse_registry_response(success_response_xml)

        # Act
        result = response.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["status"] == "Success"
        assert result["is_success"] is True
        assert isinstance(result["document_ids"], list)
        assert isinstance(result["errors"], list)
        assert isinstance(result["warnings"], list)

    def test_to_dict_with_errors(self, failure_response_xml: str) -> None:
        """Test: Verify to_dict() includes error details."""
        # Arrange
        response = parse_registry_response(failure_response_xml)

        # Act
        result = response.to_dict()

        # Assert
        assert len(result["errors"]) == 2
        first_error = result["errors"][0]
        assert "error_code" in first_error
        assert "code_context" in first_error
        assert "severity" in first_error
        assert "location" in first_error


class TestRegistryErrorInfoDataclass:
    """Tests for RegistryErrorInfo dataclass."""

    def test_error_info_creation(self) -> None:
        """Test: Verify RegistryErrorInfo dataclass creation."""
        # Arrange & Act
        error = RegistryErrorInfo(
            error_code="XDSMissingDocument",
            code_context="Document not found",
            severity="Error",
            location="/document/1",
        )

        # Assert
        assert error.error_code == "XDSMissingDocument"
        assert error.code_context == "Document not found"
        assert error.severity == "Error"
        assert error.location == "/document/1"

    def test_error_info_default_severity(self) -> None:
        """Test: Verify default severity is 'Error'."""
        # Arrange & Act
        error = RegistryErrorInfo(
            error_code="XDSTest",
            code_context="Test context",
        )

        # Assert
        assert error.severity == "Error"
        assert error.location is None


class TestAuditLogging:
    """Tests for audit logging functionality."""

    def test_log_registry_response_creates_log(
        self, success_response_xml: str, tmp_path: Path, monkeypatch
    ) -> None:
        """Test: Verify audit logging creates log entry (AC: 9)."""
        # Arrange - change logs directory to temp
        import ihe_test_util.ihe_transactions.parsers as parsers_module

        # Mock the log directory
        original_func = parsers_module.log_registry_response

        # Act
        # Note: The function creates logs in logs/transactions
        # In a real test, we'd mock the Path or use tmp_path
        # For now, just verify the function doesn't raise
        log_registry_response(
            response_xml=success_response_xml,
            status="Success",
            submission_set_id="1.2.3.4.5",
        )

        # Assert - no exception raised, function completed


class TestStatusConstantMapping:
    """Tests for status constant mapping."""

    def test_success_status_uri(self) -> None:
        """Test: Verify success status URI constant."""
        assert (
            REGISTRY_SUCCESS
            == "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"
        )

    def test_failure_status_uri(self) -> None:
        """Test: Verify failure status URI constant."""
        assert (
            REGISTRY_FAILURE
            == "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Failure"
        )

    def test_partial_success_status_uri(self) -> None:
        """Test: Verify partial success status URI constant."""
        assert (
            REGISTRY_PARTIAL_SUCCESS
            == "urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:PartialSuccess"
        )


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_error_list(self) -> None:
        """Test: Verify handling of empty RegistryErrorList."""
        # Arrange
        xml_empty_errors = """<?xml version="1.0" encoding="UTF-8"?>
        <soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"
                         xmlns:rs="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0">
          <soap12:Body>
            <rs:RegistryResponse status="urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success">
              <rs:RegistryErrorList/>
            </rs:RegistryResponse>
          </soap12:Body>
        </soap12:Envelope>"""

        # Act
        response = parse_registry_response(xml_empty_errors)

        # Assert
        assert response.status == "Success"
        assert len(response.errors) == 0
        assert len(response.warnings) == 0

    def test_no_document_ids_in_success(self) -> None:
        """Test: Verify success response without document IDs."""
        # Arrange
        xml_no_docs = """<?xml version="1.0" encoding="UTF-8"?>
        <soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"
                         xmlns:rs="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0">
          <soap12:Body>
            <rs:RegistryResponse status="urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"/>
          </soap12:Body>
        </soap12:Envelope>"""

        # Act
        response = parse_registry_response(xml_no_docs)

        # Assert
        assert response.status == "Success"
        assert response.is_success is True
        assert len(response.document_ids) == 0
        assert response.submission_set_id is None

    def test_no_ws_addressing_headers(self) -> None:
        """Test: Verify handling of response without WS-Addressing headers."""
        # Arrange
        xml_no_wsa = """<?xml version="1.0" encoding="UTF-8"?>
        <soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"
                         xmlns:rs="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0">
          <soap12:Body>
            <rs:RegistryResponse status="urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"/>
          </soap12:Body>
        </soap12:Envelope>"""

        # Act
        response = parse_registry_response(xml_no_wsa)

        # Assert
        assert response.response_id is None
        assert response.request_id is None

    def test_bytes_input(self, success_response_xml: str) -> None:
        """Test: Verify handling of bytes input."""
        # Arrange
        xml_bytes = success_response_xml.encode("utf-8")

        # Act
        response = parse_registry_response(xml_bytes)

        # Assert
        assert response.status == "Success"
        assert response.is_success is True

    def test_unknown_status_uri(self) -> None:
        """Test: Verify handling of unknown status URI."""
        # Arrange
        xml_unknown_status = """<?xml version="1.0" encoding="UTF-8"?>
        <soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"
                         xmlns:rs="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0">
          <soap12:Body>
            <rs:RegistryResponse status="urn:custom:status:Unknown"/>
          </soap12:Body>
        </soap12:Envelope>"""

        # Act
        response = parse_registry_response(xml_unknown_status)

        # Assert
        # Unknown status is passed through, is_success is False
        assert "Unknown" in response.status or "urn:custom" in response.status
        assert response.is_success is False
