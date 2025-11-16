"""Unit tests for PIX Add SOAP client."""

import logging
import pytest
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path

import requests
from requests.exceptions import ConnectionError, Timeout, SSLError, HTTPError

from ihe_test_util.ihe_transactions.soap_client import PIXAddSOAPClient, TLS12Adapter
from ihe_test_util.models.responses import TransactionResponse, TransactionStatus, TransactionType
from ihe_test_util.models.saml import SAMLAssertion, SAMLGenerationMethod
from ihe_test_util.models.patient import PatientDemographics
from ihe_test_util.config.schema import Config, EndpointsConfig, TransportConfig
from ihe_test_util.utils.exceptions import ValidationError


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return Config(
        endpoints=EndpointsConfig(
            pix_add_url="http://localhost:8080/pix/add",
            iti41_url="http://localhost:8080/iti41/submit"
        ),
        transport=TransportConfig(
            verify_tls=True,
            timeout_connect=10,
            timeout_read=30,
            max_retries=3,
            backoff_factor=1.0
        )
    )


@pytest.fixture
def mock_signed_saml():
    """Create mock signed SAML assertion."""
    return SAMLAssertion(
        assertion_id="SAML-12345",
        issuer="https://test.example.com",
        subject="testuser@example.com",
        audience="http://localhost:8080",
        issue_instant=datetime.now(),
        not_before=datetime.now(),
        not_on_or_after=datetime.now(),
        xml_content="<saml:Assertion xmlns:saml=\"urn:oasis:names:tc:SAML:2.0:assertion\">...</saml:Assertion>",
        signature="<ds:Signature xmlns:ds=\"http://www.w3.org/2000/09/xmldsig#\">...</ds:Signature>",
        certificate_subject="CN=Test Cert",
        generation_method=SAMLGenerationMethod.PROGRAMMATIC
    )


@pytest.fixture
def sample_pix_message():
    """Sample PIX Add message XML."""
    return """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <PRPA_IN201301UV02 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
      <id root="test-message-123"/>
      <creationTime value="20251115120000"/>
      <interactionId root="2.16.840.1.113883.1.6" extension="PRPA_IN201301UV02"/>
    </PRPA_IN201301UV02>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""


@pytest.fixture
def sample_aa_response():
    """Sample AA (success) acknowledgment response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
  <id root="ACK-123456" extension="ACK-001"/>
  <creationTime value="20251115120100"/>
  <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
  <acknowledgement>
    <typeCode code="AA"/>
    <targetMessage>
      <id root="test-message-123"/>
    </targetMessage>
  </acknowledgement>
</MCCI_IN000002UV01>"""


@pytest.fixture
def sample_ae_response():
    """Sample AE (error) acknowledgment response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<MCCI_IN000002UV01 xmlns="urn:hl7-org:v3" ITSVersion="XML_1.0">
  <id root="ACK-ERROR" extension="ACK-ERR-001"/>
  <creationTime value="20251115120100"/>
  <interactionId root="2.16.840.1.113883.1.6" extension="MCCI_IN000002UV01"/>
  <acknowledgement>
    <typeCode code="AE"/>
    <targetMessage>
      <id root="test-message-123"/>
    </targetMessage>
    <acknowledgementDetail typeCode="E">
      <text>Patient identifier already exists</text>
    </acknowledgementDetail>
  </acknowledgement>
</MCCI_IN000002UV01>"""


class TestPIXAddSOAPClientInitialization:
    """Test SOAP client initialization and configuration."""
    
    def test_soap_client_initialization_with_defaults(self, mock_config):
        """Test client initialization with default parameters.
        
        Acceptance Criteria: AC 1, 2
        """
        # Act
        client = PIXAddSOAPClient(mock_config)
        
        # Assert
        assert client.config == mock_config
        assert client.endpoint_url == "http://localhost:8080/pix/add"
        assert client.timeout == 30
        assert client.max_retries == 3
        assert client.session is not None
    
    def test_soap_client_with_custom_endpoint(self, mock_config):
        """Test client with explicit endpoint URL override.
        
        Acceptance Criteria: AC 2
        """
        # Arrange
        custom_url = "http://custom.example.com/pix"
        
        # Act
        client = PIXAddSOAPClient(mock_config, endpoint_url=custom_url)
        
        # Assert
        assert client.endpoint_url == custom_url
    
    def test_soap_client_with_custom_timeout_and_retries(self, mock_config):
        """Test client with custom timeout and retry configuration.
        
        Acceptance Criteria: AC 8, 9
        """
        # Act
        client = PIXAddSOAPClient(
            mock_config,
            timeout=60,
            max_retries=5
        )
        
        # Assert
        assert client.timeout == 60
        assert client.max_retries == 5
    
    def test_http_endpoint_logs_security_warning(self, mock_config, caplog):
        """Test that HTTP endpoints trigger security warning.
        
        Acceptance Criteria: AC 4
        """
        # Act
        with caplog.at_level("WARNING"):
            client = PIXAddSOAPClient(mock_config)
        
        # Assert
        assert "SECURITY WARNING" in caplog.text
        assert "HTTP transport (not HTTPS)" in caplog.text
    
    def test_https_endpoint_no_warning(self, mock_config, caplog):
        """Test that HTTPS endpoints do not trigger security warning."""
        # Arrange
        https_config = Config(
            endpoints=EndpointsConfig(
                pix_add_url="https://secure.example.com/pix/add",
                iti41_url="https://secure.example.com/iti41"
            ),
            transport=TransportConfig()
        )
        
        # Act
        with caplog.at_level("WARNING"):
            client = PIXAddSOAPClient(https_config)
        
        # Assert
        assert "SECURITY WARNING" not in caplog.text
    
    def test_invalid_timeout_raises_error(self, mock_config):
        """Test that invalid timeout raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid timeout"):
            PIXAddSOAPClient(mock_config, timeout=0)
        
        with pytest.raises(ValidationError, match="Invalid timeout"):
            PIXAddSOAPClient(mock_config, timeout=-5)
    
    def test_invalid_max_retries_raises_error(self, mock_config):
        """Test that invalid max_retries raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid max_retries"):
            PIXAddSOAPClient(mock_config, max_retries=-1)
    
    def test_invalid_endpoint_url_raises_error(self, mock_config):
        """Test that invalid endpoint URL raises validation error."""
        # Act & Assert - pydantic validates the URL format in config
        # So we test the client validation by passing invalid URL directly
        with pytest.raises(ValidationError, match="Invalid endpoint URL"):
            PIXAddSOAPClient(mock_config, endpoint_url="ftp://invalid.com/pix")
    
    def test_tls_adapter_mounted_for_https(self, mock_config):
        """Test that TLS 1.2+ adapter is mounted for HTTPS connections.
        
        Acceptance Criteria: AC 3
        """
        # Act
        client = PIXAddSOAPClient(mock_config)
        
        # Assert
        assert 'https://' in client.session.adapters
        assert isinstance(client.session.adapters['https://'], TLS12Adapter)


class TestSOAPEnvelopeConstruction:
    """Test SOAP envelope building with WS-Security headers."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.WSSecurityHeaderBuilder')
    def test_build_soap_envelope_structure(
        self,
        mock_builder_class,
        mock_config,
        sample_pix_message,
        mock_signed_saml
    ):
        """Test SOAP envelope construction with WS-Security headers.
        
        Acceptance Criteria: AC 5, 6
        """
        # Arrange
        mock_builder = Mock()
        mock_builder_class.return_value = mock_builder
        mock_builder.create_pix_add_soap_envelope.return_value = "<SOAP>...</SOAP>"
        
        client = PIXAddSOAPClient(mock_config)
        
        # Act
        result = client._build_soap_envelope(sample_pix_message, mock_signed_saml)
        
        # Assert
        mock_builder.create_pix_add_soap_envelope.assert_called_once()
        assert result == "<SOAP>...</SOAP>"
    
    def test_build_soap_envelope_with_unsigned_saml_raises_error(
        self,
        mock_config,
        sample_pix_message
    ):
        """Test that unsigned SAML assertion raises validation error.
        
        Acceptance Criteria: AC 6
        """
        # Arrange
        unsigned_saml = SAMLAssertion(
            assertion_id="SAML-123",
            issuer="test",
            subject="user",
            audience="aud",
            issue_instant=datetime.now(),
            not_before=datetime.now(),
            not_on_or_after=datetime.now(),
            xml_content="<saml>...</saml>",
            signature="",  # No signature
            certificate_subject="CN=Test",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC
        )
        
        client = PIXAddSOAPClient(mock_config)
        
        # Act & Assert
        with pytest.raises(ValidationError, match="SAML assertion is not signed"):
            client.submit_pix_add(sample_pix_message, unsigned_saml)


class TestPIXAddSubmission:
    """Test PIX Add transaction submission."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.parse_acknowledgment')
    def test_submit_pix_add_success(
        self,
        mock_parse_ack,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        sample_aa_response,
        mocker
    ):
        """Test successful PIX Add submission with AA acknowledgment.
        
        Acceptance Criteria: AC 1, 7, 8, 10
        """
        # Arrange
        mock_response = Mock()
        mock_response.text = sample_aa_response
        mock_response.status_code = 200
        
        mock_post = mocker.patch('requests.Session.post', return_value=mock_response)
        
        mock_ack = Mock()
        mock_ack.status = "AA"
        mock_ack.is_success = True
        mock_ack.acknowledgment_id = "ACK-123456"
        mock_ack.details = []
        mock_parse_ack.return_value = mock_ack
        
        client = PIXAddSOAPClient(mock_config)
        
        # Act
        response = client.submit_pix_add(sample_pix_message, mock_signed_saml)
        
        # Assert
        assert response.status == TransactionStatus.SUCCESS
        assert response.status_code == "AA"
        assert response.transaction_type == TransactionType.PIX_ADD
        assert response.processing_time_ms > 0
        assert mock_post.called
    
    @patch('ihe_test_util.ihe_transactions.soap_client.parse_acknowledgment')
    def test_submit_pix_add_with_ae_acknowledgment(
        self,
        mock_parse_ack,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        sample_ae_response,
        mocker
    ):
        """Test PIX Add submission with AE (error) acknowledgment.
        
        Acceptance Criteria: AC 10
        """
        # Arrange
        mock_response = Mock()
        mock_response.text = sample_ae_response
        mock_response.status_code = 200
        
        mocker.patch('requests.Session.post', return_value=mock_response)
        
        mock_detail = Mock()
        mock_detail.text = "Patient identifier already exists"
        
        mock_ack = Mock()
        mock_ack.status = "AE"
        mock_ack.is_success = False
        mock_ack.acknowledgment_id = "ACK-ERROR"
        mock_ack.details = [mock_detail]
        mock_parse_ack.return_value = mock_ack
        
        client = PIXAddSOAPClient(mock_config)
        
        # Act
        response = client.submit_pix_add(sample_pix_message, mock_signed_saml)
        
        # Assert
        assert response.status == TransactionStatus.ERROR
        assert response.status_code == "AE"
        assert len(response.error_messages) == 1
        assert "already exists" in response.error_messages[0]
    
    def test_submit_pix_add_timeout(
        self,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        mocker
    ):
        """Test PIX Add submission timeout handling.
        
        Acceptance Criteria: AC 8, 9
        """
        # Arrange
        mocker.patch('requests.Session.post', side_effect=Timeout("Request timed out"))
        
        client = PIXAddSOAPClient(mock_config, timeout=5, max_retries=1)
        
        # Act & Assert
        with pytest.raises(Timeout):
            client.submit_pix_add(sample_pix_message, mock_signed_saml)
    
    def test_submit_pix_add_connection_error(
        self,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        mocker
    ):
        """Test PIX Add submission with connection error.
        
        Acceptance Criteria: AC 9
        """
        # Arrange
        mocker.patch('requests.Session.post', side_effect=ConnectionError("Network unreachable"))
        
        client = PIXAddSOAPClient(mock_config, max_retries=1)
        
        # Act & Assert
        with pytest.raises(ConnectionError, match="Network unreachable"):
            client.submit_pix_add(sample_pix_message, mock_signed_saml)
    
    def test_submit_pix_add_ssl_error(
        self,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        mocker
    ):
        """Test PIX Add submission with SSL certificate error.
        
        Acceptance Criteria: AC 3
        """
        # Arrange
        https_config = Config(
            endpoints=EndpointsConfig(
                pix_add_url="https://secure.example.com/pix/add",
                iti41_url="https://secure.example.com/iti41"
            ),
            transport=TransportConfig()
        )
        
        mocker.patch('requests.Session.post', side_effect=SSLError("Certificate verification failed"))
        
        client = PIXAddSOAPClient(https_config)
        
        # Act & Assert
        with pytest.raises(SSLError, match="Certificate verification failed"):
            client.submit_pix_add(sample_pix_message, mock_signed_saml)


class TestRetryLogic:
    """Test retry logic with exponential backoff."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.time.sleep')
    @patch('ihe_test_util.ihe_transactions.soap_client.parse_acknowledgment')
    def test_retry_with_exponential_backoff(
        self,
        mock_parse_ack,
        mock_sleep,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        sample_aa_response,
        mocker
    ):
        """Test retry logic with exponential backoff delays.
        
        Acceptance Criteria: AC 9
        """
        # Arrange
        mock_response = Mock()
        mock_response.text = sample_aa_response
        mock_response.status_code = 200
        
        mock_post = mocker.patch('requests.Session.post')
        mock_post.side_effect = [
            ConnectionError("Network error"),
            ConnectionError("Network error"),
            mock_response
        ]
        
        mock_ack = Mock()
        mock_ack.status = "AA"
        mock_ack.is_success = True
        mock_ack.acknowledgment_id = "ACK-123"
        mock_ack.details = []
        mock_parse_ack.return_value = mock_ack
        
        client = PIXAddSOAPClient(mock_config, max_retries=3)
        
        # Act
        response = client.submit_pix_add(sample_pix_message, mock_signed_saml)
        
        # Assert
        assert response.status == TransactionStatus.SUCCESS
        assert mock_sleep.call_count == 2  # 2 retries before success
        mock_sleep.assert_has_calls([call(1), call(2)])  # 1s, 2s delays
    
    @patch('ihe_test_util.ihe_transactions.soap_client.parse_acknowledgment')
    def test_max_retries_configurable(
        self,
        mock_parse_ack,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        mocker
    ):
        """Test that max_retries is configurable and enforced.
        
        Acceptance Criteria: AC 9
        """
        # Arrange
        mock_post = mocker.patch('requests.Session.post', side_effect=ConnectionError("Network error"))
        
        client = PIXAddSOAPClient(mock_config, max_retries=5)
        
        # Act & Assert
        with pytest.raises(ConnectionError):
            client.submit_pix_add(sample_pix_message, mock_signed_saml)
        
        # Should have tried 5 times
        assert mock_post.call_count == 5
    
    @patch('ihe_test_util.ihe_transactions.soap_client.parse_acknowledgment')
    def test_no_retry_on_4xx_client_errors(
        self,
        mock_parse_ack,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        mocker
    ):
        """Test that 4xx errors do not trigger retries."""
        # Arrange
        mock_response = Mock()
        mock_response.text = "Bad Request"
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = HTTPError("400 Client Error")
        
        mock_post = mocker.patch('requests.Session.post', return_value=mock_response)
        
        client = PIXAddSOAPClient(mock_config, max_retries=3)
        
        # Act & Assert
        with pytest.raises(HTTPError):
            client.submit_pix_add(sample_pix_message, mock_signed_saml)
        
        # Should only try once (no retries)
        assert mock_post.call_count == 1


class TestAuditLogging:
    """Test audit logging functionality."""
    
    @patch('ihe_test_util.ihe_transactions.soap_client.parse_acknowledgment')
    def test_audit_logging_request_and_response(
        self,
        mock_parse_ack,
        mock_config,
        sample_pix_message,
        mock_signed_saml,
        sample_aa_response,
        caplog,
        mocker
    ):
        """Test that complete request/response is logged to audit trail.
        
        Acceptance Criteria: AC 7 (RULE 2 - MANDATORY)
        """
        # Arrange
        mock_response = Mock()
        mock_response.text = sample_aa_response
        mock_response.status_code = 200
        
        mocker.patch('requests.Session.post', return_value=mock_response)
        
        mock_ack = Mock()
        mock_ack.status = "AA"
        mock_ack.is_success = True
        mock_ack.acknowledgment_id = "ACK-123"
        mock_ack.details = []
        mock_parse_ack.return_value = mock_ack
        
        client = PIXAddSOAPClient(mock_config)
        
        # Act
        with caplog.at_level(logging.DEBUG, logger='ihe_test_util.audit.pix_add'):
            response = client.submit_pix_add(sample_pix_message, mock_signed_saml)
        
        # Assert - verify audit logging occurred via caplog
        log_text = caplog.text
        assert "PIX Add Transaction" in log_text
        assert "Status: SENDING" in log_text
        assert "Status: SUCCESS" in log_text
        assert "Request XML:" in log_text
        assert "Response XML:" in log_text
        assert "PRPA_IN201301UV02" in log_text  # Verify request content logged
        assert "MCCI_IN000002UV01" in log_text  # Verify response content logged


class TestTransactionResponseParsing:
    """Test transaction response parsing."""
    
    def test_transaction_response_is_success_property(self):
        """Test TransactionResponse.is_success property."""
        # Arrange
        success_response = TransactionResponse(
            response_id="ACK-1",
            request_id="REQ-1",
            transaction_type=TransactionType.PIX_ADD,
            status=TransactionStatus.SUCCESS,
            status_code="AA",
            response_timestamp=datetime.now(),
            response_xml="<xml/>",
            processing_time_ms=100
        )
        
        error_response = TransactionResponse(
            response_id="ACK-2",
            request_id="REQ-2",
            transaction_type=TransactionType.PIX_ADD,
            status=TransactionStatus.ERROR,
            status_code="AE",
            response_timestamp=datetime.now(),
            response_xml="<xml/>",
            error_messages=["Error occurred"],
            processing_time_ms=50
        )
        
        # Assert
        assert success_response.is_success is True
        assert error_response.is_success is False
    
    def test_transaction_response_has_errors_property(self):
        """Test TransactionResponse.has_errors property."""
        # Arrange
        response_with_errors = TransactionResponse(
            response_id="ACK-1",
            request_id="REQ-1",
            transaction_type=TransactionType.PIX_ADD,
            status=TransactionStatus.ERROR,
            status_code="AE",
            response_timestamp=datetime.now(),
            response_xml="<xml/>",
            error_messages=["Error 1", "Error 2"],
            processing_time_ms=100
        )
        
        response_no_errors = TransactionResponse(
            response_id="ACK-2",
            request_id="REQ-2",
            transaction_type=TransactionType.PIX_ADD,
            status=TransactionStatus.SUCCESS,
            status_code="AA",
            response_timestamp=datetime.now(),
            response_xml="<xml/>",
            processing_time_ms=50
        )
        
        # Assert
        assert response_with_errors.has_errors is True
        assert response_no_errors.has_errors is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
