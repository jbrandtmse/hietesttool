"""Flask application for mock IHE endpoints."""

import logging
from flask import Flask
from pathlib import Path

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create logs directory
LOGS_DIR = Path("mocks/logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ITI41_LOGS_DIR = LOGS_DIR / "iti41-submissions"
ITI41_LOGS_DIR.mkdir(exist_ok=True)

PIX_ADD_LOG = LOGS_DIR / "pix-add.log"


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "IHE Mock Server"}, 200


# Register endpoints
from .iti41_endpoint import register_iti41_endpoint
from .pix_add_endpoint import register_pix_add_endpoint

register_iti41_endpoint(app)
register_pix_add_endpoint(app)


def run_server(host: str = "localhost", port: int = 8080, debug: bool = True):
    """Run the Flask mock server.
    
    Args:
        host: Host address (default: localhost)
        port: Port number (default: 8080)
        debug: Enable debug mode (default: True)
    """
    logger.info(f"Starting IHE Mock Server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server()
