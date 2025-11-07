"""Flask application for mock IHE endpoints."""

import logging
import signal
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, Response, jsonify, request

from .config import MockServerConfig, load_config


# Server state tracking
_server_start_time: datetime | None = None
_request_count: int = 0
_config: MockServerConfig | None = None

# Create Flask app
app = Flask(__name__)


def setup_logging(config: MockServerConfig) -> logging.Logger:
    """Configure logging for mock server with rotation.
    
    Args:
        config: Mock server configuration
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("ihe_test_util.mock_server")
    logger.setLevel(config.log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (DEBUG and above) with rotation
    log_path = Path(config.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


logger = logging.getLogger("ihe_test_util.mock_server")


def generate_soap_fault(
    faultcode: str,
    faultstring: str,
    detail: str | None = None,
    http_status: int = 400
) -> tuple[Response, int]:
    """Generate SOAP 1.2 fault response.
    
    Args:
        faultcode: SOAP fault code (e.g., 'soap:Sender', 'soap:Receiver')
        faultstring: Human-readable fault description
        detail: Optional detailed error information
        http_status: HTTP status code (default: 400)
        
    Returns:
        Tuple of (Response object, HTTP status code)
    """
    detail_xml = ""
    if detail:
        detail_xml = f"""
      <soap:Detail>
        <error>{detail}</error>
      </soap:Detail>"""

    fault_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <soap:Fault>
      <soap:Code>
        <soap:Value>{faultcode}</soap:Value>
      </soap:Code>
      <soap:Reason>
        <soap:Text xml:lang="en">{faultstring}</soap:Text>
      </soap:Reason>{detail_xml}
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""

    logger.warning(f"SOAP Fault generated: {faultcode} - {faultstring}")

    response = Response(fault_xml, mimetype="text/xml; charset=utf-8")
    return response, http_status


@app.before_request
def log_request():
    """Log all incoming requests."""
    global _request_count
    _request_count += 1

    logger.info(
        f"Request #{_request_count}: {request.method} {request.path} "
        f"(Content-Length: {request.content_length or 0})"
    )

    # Log request body at DEBUG level
    if request.data and logger.isEnabledFor(logging.DEBUG):
        try:
            body = request.data.decode("utf-8")
            logger.debug(f"Request body: {body[:500]}...")  # Truncate for readability
        except Exception as e:
            logger.debug(f"Could not decode request body: {e}")


@app.after_request
def add_soap_headers(response: Response) -> Response:
    """Add appropriate SOAP/XML headers to responses.
    
    Args:
        response: Flask response object
        
    Returns:
        Modified response with headers
    """
    # Only add XML content-type if not already set and response is XML
    if not response.content_type and request.path != "/health":
        response.headers["Content-Type"] = "text/xml; charset=utf-8"
    return response


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint.
    
    Returns JSON with server status, version, protocol, port, endpoints,
    uptime, request count, and timestamp.
    """
    global _server_start_time, _request_count, _config

    uptime_seconds = 0
    if _server_start_time:
        uptime_seconds = int((datetime.now(timezone.utc) - _server_start_time).total_seconds())

    # Determine protocol from config (will be set during server start)
    protocol = "http"  # Default
    port = 8080
    if _config:
        port = _config.http_port  # This will be overridden in CLI if HTTPS is used

    # Get available endpoints
    endpoints = ["/health"]
    if _config:
        endpoints.append(_config.pix_add_endpoint)
        endpoints.append(_config.iti41_endpoint)

    health_response = {
        "status": "healthy",
        "version": "1.0.0",
        "protocol": protocol,
        "port": port,
        "endpoints": endpoints,
        "uptime_seconds": uptime_seconds,
        "request_count": _request_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    return jsonify(health_response), 200


@app.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request errors with SOAP fault."""
    return generate_soap_fault(
        "soap:Sender",
        "Bad Request",
        detail=str(error),
        http_status=400
    )


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server errors with SOAP fault."""
    return generate_soap_fault(
        "soap:Receiver",
        "Internal Server Error",
        detail=str(error),
        http_status=500
    )


def setup_graceful_shutdown():
    """Setup graceful shutdown handlers for SIGTERM and SIGINT.
    
    Note: Signal handlers can only be registered in the main thread.
    In test scenarios or when running in background threads, this will
    log a warning but continue gracefully.
    """
    def shutdown_handler(signum, frame):
        logger.info(f"Received shutdown signal ({signum}), cleaning up...")
        # Perform cleanup here if needed
        logger.info("Mock server shutdown complete")
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)
        logger.info("Graceful shutdown handlers registered successfully")
    except ValueError as e:
        # Signal registration only works in main thread
        logger.warning(
            f"Could not register signal handlers (not in main thread): {e}. "
            f"Graceful shutdown via signals will not be available."
        )


def initialize_app(config: MockServerConfig) -> None:
    """Initialize Flask app with configuration.
    
    Args:
        config: Mock server configuration
    """
    global _config, _server_start_time
    _config = config
    _server_start_time = datetime.now(timezone.utc)

    # Setup logging
    setup_logging(config)
    logger.info("Mock server application initialized")

    # Setup graceful shutdown
    setup_graceful_shutdown()

    # Register endpoint blueprints
    try:
        from .pix_add_endpoint import register_pix_add_endpoint
        register_pix_add_endpoint(app, config)
    except ImportError:
        logger.warning("PIX Add endpoint not available (Story 2.2)")

    # ITI-41 endpoint registration temporarily disabled for Story 2.2
    # Will be enabled in Story 2.3
    # try:
    #     from .iti41_endpoint import register_iti41_endpoint
    #     register_iti41_endpoint(app)
    #     logger.info(f"Registered ITI-41 endpoint: {config.iti41_endpoint}")
    # except ImportError:
    #     logger.warning("ITI-41 endpoint not available (Story 2.3)")

    # Create required directories
    Path("mocks/data").mkdir(parents=True, exist_ok=True)
    Path("mocks/logs").mkdir(parents=True, exist_ok=True)


def run_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    protocol: str = "http",
    config: MockServerConfig | None = None,
    debug: bool = False
) -> None:
    """Run the Flask mock server.
    
    Args:
        host: Host address (default: 0.0.0.0)
        port: Port number (default: 8080)
        protocol: Protocol to use ('http' or 'https')
        config: Mock server configuration (loads from file if not provided)
        debug: Enable debug mode (default: False)
        
    Raises:
        FileNotFoundError: If HTTPS enabled but certificates not found
    """
    # Load config if not provided
    if config is None:
        config = load_config()

    # Initialize app
    initialize_app(config)

    # Update health check protocol info
    global _config
    if _config:
        _config.http_port = port  # Update port for health check

    # Configure SSL context for HTTPS
    ssl_context = None
    if protocol.lower() == "https":
        cert_path = Path(config.cert_path)
        key_path = Path(config.key_path)

        if not cert_path.exists():
            raise FileNotFoundError(
                f"Certificate not found at '{cert_path}'. "
                f"Run 'bash scripts/generate_cert.sh' to create self-signed certificates."
            )
        if not key_path.exists():
            raise FileNotFoundError(
                f"Private key not found at '{key_path}'. "
                f"Run 'bash scripts/generate_cert.sh' to create self-signed certificates."
            )

        ssl_context = (str(cert_path), str(key_path))
        logger.info(f"HTTPS enabled with certificate: {cert_path}")

    logger.info(f"Starting IHE Mock Server on {protocol}://{host}:{port}")
    logger.info(f"Health check available at: {protocol}://{host}:{port}/health")

    # Run server
    app.run(
        host=host,
        port=port,
        debug=debug,
        ssl_context=ssl_context,
        use_reloader=False  # Disable reloader to avoid duplicate startup
    )


if __name__ == "__main__":
    run_server()
