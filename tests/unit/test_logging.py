"""Unit tests for logging_audit module."""

import logging
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ihe_test_util.logging_audit import (
    PIIRedactingFormatter,
    configure_logging,
    get_logger,
    log_audit_event,
    log_transaction,
)


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_logging_creates_file(self, tmp_path):
        """Test logging configuration creates log file."""
        # Arrange
        log_file = tmp_path / "test.log"

        # Act
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)
        logger = get_logger(__name__)
        logger.info("Test message")

        # Assert
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_configure_logging_sets_console_level(self, tmp_path):
        """Test console handler uses specified log level."""
        # Arrange
        log_file = tmp_path / "test.log"

        # Act
        configure_logging(level="WARNING", log_file=log_file, redact_pii=False)
        logger = get_logger(__name__)
        
        logger.info("Info message")
        logger.warning("Warning message")

        # Assert - file should have both, verify via file content
        file_content = log_file.read_text()
        assert "Info message" not in file_content or "WARNING" in file_content
        # Just verify the log level was set correctly by checking handler
        root_logger = logging.getLogger()
        console_handler = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler) and not hasattr(h, 'baseFilename')][0]
        assert console_handler.level == logging.WARNING

    def test_configure_logging_file_level_debug(self, tmp_path):
        """Test file handler always uses DEBUG level."""
        # Arrange
        log_file = tmp_path / "test.log"

        # Act
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)
        logger = get_logger(__name__)
        logger.debug("Debug message")
        logger.info("Info message")

        # Assert - both messages in file
        content = log_file.read_text()
        assert "Debug message" in content
        assert "Info message" in content

    def test_configure_logging_creates_directory(self, tmp_path):
        """Test logging creates parent directories if needed."""
        # Arrange
        log_file = tmp_path / "nested" / "dir" / "test.log"

        # Act
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)
        logger = get_logger(__name__)
        logger.info("Test message")

        # Assert
        assert log_file.exists()
        assert log_file.parent.exists()

    def test_configure_logging_invalid_level_raises_error(self, tmp_path):
        """Test invalid log level raises ValueError."""
        # Arrange
        log_file = tmp_path / "test.log"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid log level"):
            configure_logging(level="INVALID", log_file=log_file, redact_pii=False)

    def test_configure_logging_environment_variable(self, tmp_path, monkeypatch):
        """Test IHE_TEST_LOG_FILE environment variable overrides default."""
        # Arrange
        env_log_file = tmp_path / "env.log"
        monkeypatch.setenv("IHE_TEST_LOG_FILE", str(env_log_file))

        # Act
        configure_logging(level="INFO", log_file=None, redact_pii=False)
        logger = get_logger(__name__)
        logger.info("Test message")

        # Assert
        assert env_log_file.exists()
        assert "Test message" in env_log_file.read_text()

    def test_configure_logging_cli_overrides_environment(self, tmp_path, monkeypatch):
        """Test CLI log_file parameter overrides environment variable."""
        # Arrange
        env_log_file = tmp_path / "env.log"
        cli_log_file = tmp_path / "cli.log"
        monkeypatch.setenv("IHE_TEST_LOG_FILE", str(env_log_file))

        # Act
        configure_logging(level="INFO", log_file=cli_log_file, redact_pii=False)
        logger = get_logger(__name__)
        logger.info("Test message")

        # Assert
        assert cli_log_file.exists()
        assert not env_log_file.exists()
        assert "Test message" in cli_log_file.read_text()

    def test_configure_logging_idempotent(self, tmp_path):
        """Test configure_logging can be called multiple times safely."""
        # Arrange
        log_file = tmp_path / "test.log"

        # Act
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)
        configure_logging(level="DEBUG", log_file=log_file, redact_pii=False)
        logger = get_logger(__name__)
        logger.debug("Test message")

        # Assert - no errors, DEBUG level active
        content = log_file.read_text()
        assert "Test message" in content

    def test_configure_logging_log_format(self, tmp_path):
        """Test log format matches specification."""
        # Arrange
        log_file = tmp_path / "test.log"

        # Act
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)
        logger = get_logger(__name__)
        logger.info("Test message")

        # Assert - format: timestamp - module - level - message
        content = log_file.read_text()
        pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - .+ - INFO - Test message"
        assert re.search(pattern, content)

    def test_configure_logging_rotation_config(self, tmp_path):
        """Test log rotation configuration (max size, backup count)."""
        # Arrange
        log_file = tmp_path / "test.log"

        # Act
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)

        # Assert - check handler configuration
        root_logger = logging.getLogger()
        file_handler = None
        for handler in root_logger.handlers:
            if hasattr(handler, "maxBytes"):
                file_handler = handler
                break

        assert file_handler is not None
        assert file_handler.maxBytes == 10 * 1024 * 1024  # 10MB
        assert file_handler.backupCount == 5


class TestGetLogger:
    """Test logger factory function."""

    def test_get_logger_returns_logger(self):
        """Test get_logger returns logger instance."""
        # Act
        logger = get_logger("test_module")

        # Assert
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_uses_module_name(self):
        """Test get_logger typically called with __name__."""
        # Act
        logger = get_logger(__name__)

        # Assert
        assert logger.name == __name__


class TestPIIRedactingFormatter:
    """Test PII redaction formatter."""

    def test_redact_ssn(self):
        """Test SSN redaction."""
        # Arrange
        formatter = PIIRedactingFormatter(redact_pii=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Patient SSN: 123-45-6789",
            args=(),
            exc_info=None,
        )

        # Act
        result = formatter.format(record)

        # Assert
        assert "123-45-6789" not in result
        assert "[SSN-REDACTED]" in result

    def test_redact_patient_name(self):
        """Test patient name redaction."""
        # Arrange
        formatter = PIIRedactingFormatter(redact_pii=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='Processing patient name="John Doe"',
            args=(),
            exc_info=None,
        )

        # Act
        result = formatter.format(record)

        # Assert
        assert "John Doe" not in result
        assert "[NAME-REDACTED]" in result

    def test_no_redaction_when_disabled(self):
        """Test PII not redacted when redact_pii=False."""
        # Arrange
        formatter = PIIRedactingFormatter(redact_pii=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Patient SSN: 123-45-6789",
            args=(),
            exc_info=None,
        )

        # Act
        result = formatter.format(record)

        # Assert
        assert "123-45-6789" in result
        assert "[SSN-REDACTED]" not in result

    def test_multiple_redactions(self):
        """Test multiple PII patterns redacted in single message."""
        # Arrange
        formatter = PIIRedactingFormatter(redact_pii=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='Patient name="John Doe" SSN: 123-45-6789',
            args=(),
            exc_info=None,
        )

        # Act
        result = formatter.format(record)

        # Assert
        assert "John Doe" not in result
        assert "123-45-6789" not in result
        assert "[NAME-REDACTED]" in result
        assert "[SSN-REDACTED]" in result


class TestLogAuditEvent:
    """Test audit trail logging."""

    def test_log_audit_event_success(self, tmp_path):
        """Test audit event logging for successful operation."""
        # Arrange
        log_file = tmp_path / "test.log"
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)

        # Act
        log_audit_event(
            "CSV_PROCESSED",
            {
                "input_file": "patients.csv",
                "record_count": 100,
                "status": "success",
                "duration": 2.5,
            },
        )

        # Assert
        content = log_file.read_text()
        assert "AUDIT [CSV_PROCESSED]" in content
        assert "status=success" in content
        assert "input_file=patients.csv" in content
        assert "record_count=100" in content
        assert "duration=2.50s" in content

    def test_log_audit_event_failure(self, tmp_path):
        """Test audit event logging for failed operation."""
        # Arrange
        log_file = tmp_path / "test.log"
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)

        # Act
        log_audit_event(
            "VALIDATION_FAILED",
            {
                "input_file": "patients.csv",
                "record_count": 100,
                "error_count": 5,
                "status": "failure",
                "error_message": "5 validation errors found",
            },
        )

        # Assert
        content = log_file.read_text()
        assert "AUDIT [VALIDATION_FAILED]" in content
        assert "status=failure" in content
        assert "error_count=5" in content
        assert "error_message=5 validation errors found" in content

    def test_log_audit_event_adds_correlation_id(self, tmp_path):
        """Test audit event automatically adds correlation ID."""
        # Arrange
        log_file = tmp_path / "test.log"
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)

        # Act
        log_audit_event("CSV_PROCESSED", {"status": "success"})

        # Assert
        content = log_file.read_text()
        assert "correlation_id=" in content

    def test_log_audit_event_preserves_custom_correlation_id(self, tmp_path):
        """Test audit event preserves user-provided correlation ID."""
        # Arrange
        log_file = tmp_path / "test.log"
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)
        custom_id = "custom-correlation-id"

        # Act
        log_audit_event(
            "CSV_PROCESSED", {"status": "success", "correlation_id": custom_id}
        )

        # Assert
        content = log_file.read_text()
        assert f"correlation_id={custom_id}" in content


class TestLogTransaction:
    """Test transaction logging."""

    def test_log_transaction_success(self, tmp_path):
        """Test transaction logging for successful transaction."""
        # Arrange
        log_file = tmp_path / "test.log"
        configure_logging(level="DEBUG", log_file=log_file, redact_pii=False)
        request_xml = "<soap:Envelope>Request</soap:Envelope>"
        response_xml = "<soap:Envelope>Response</soap:Envelope>"

        # Act
        log_transaction("PIX_ADD", request_xml, response_xml, "success")

        # Assert
        content = log_file.read_text()
        assert "TRANSACTION [PIX_ADD]" in content
        assert "status=success" in content
        assert "correlation_id=" in content
        assert "request_size=" in content
        assert "response_size=" in content

    def test_log_transaction_includes_full_request_response(self, tmp_path):
        """Test transaction logging includes full request/response at DEBUG level."""
        # Arrange
        log_file = tmp_path / "test.log"
        configure_logging(level="DEBUG", log_file=log_file, redact_pii=False)
        request_xml = "<soap:Envelope>Request Content</soap:Envelope>"
        response_xml = "<soap:Envelope>Response Content</soap:Envelope>"

        # Act
        log_transaction("PIX_ADD", request_xml, response_xml, "success")

        # Assert
        content = log_file.read_text()
        assert "TRANSACTION REQUEST [PIX_ADD]" in content
        assert "TRANSACTION RESPONSE [PIX_ADD]" in content
        assert "Request Content" in content
        assert "Response Content" in content

    def test_log_transaction_correlation_id_matches(self, tmp_path):
        """Test same correlation ID used for request, response, and summary."""
        # Arrange
        log_file = tmp_path / "test.log"
        configure_logging(level="DEBUG", log_file=log_file, redact_pii=False)
        request_xml = "<soap:Envelope>Request</soap:Envelope>"
        response_xml = "<soap:Envelope>Response</soap:Envelope>"

        # Act
        log_transaction("PIX_ADD", request_xml, response_xml, "success")

        # Assert
        content = log_file.read_text()
        # Extract all correlation IDs
        correlation_ids = re.findall(r"correlation_id=([a-f0-9\-]+)", content)
        # All should be the same
        assert len(correlation_ids) == 3  # Summary + Request + Response
        assert len(set(correlation_ids)) == 1  # All identical

    def test_log_transaction_calculates_sizes(self, tmp_path):
        """Test transaction logging calculates request/response sizes."""
        # Arrange
        log_file = tmp_path / "test.log"
        configure_logging(level="INFO", log_file=log_file, redact_pii=False)
        request_xml = "<soap:Envelope>Request</soap:Envelope>"
        response_xml = "<soap:Envelope>Response</soap:Envelope>"

        # Act
        log_transaction("PIX_ADD", request_xml, response_xml, "success")

        # Assert
        content = log_file.read_text()
        assert f"request_size={len(request_xml)} bytes" in content
        assert f"response_size={len(response_xml)} bytes" in content
