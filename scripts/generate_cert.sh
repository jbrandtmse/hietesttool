#!/bin/bash

# Self-Signed Certificate Generation Script for IHE Mock Server
# 
# This script generates a self-signed SSL certificate and private key
# for testing the mock server with HTTPS support.
#
# WARNING: These certificates are for TESTING ONLY. Do NOT use in production.
#
# Usage:
#   bash scripts/generate_cert.sh
#
# Output:
#   - mocks/cert.pem: Self-signed certificate (valid 365 days)
#   - mocks/key.pem: Private key (2048-bit RSA, unencrypted)
#

set -e  # Exit on error

CERT_DIR="mocks"
CERT_FILE="${CERT_DIR}/cert.pem"
KEY_FILE="${CERT_DIR}/key.pem"

# Create mocks directory if it doesn't exist
mkdir -p "${CERT_DIR}"

echo "============================================"
echo "IHE Mock Server Certificate Generation"
echo "============================================"
echo ""

# Check if OpenSSL is available
if ! command -v openssl &> /dev/null; then
    echo "ERROR: OpenSSL is not installed or not in PATH."
    echo "Please install OpenSSL to generate certificates."
    exit 1
fi

# Check if certificates already exist
if [ -f "${CERT_FILE}" ] || [ -f "${KEY_FILE}" ]; then
    echo "WARNING: Certificates already exist:"
    [ -f "${CERT_FILE}" ] && echo "  - ${CERT_FILE}"
    [ -f "${KEY_FILE}" ] && echo "  - ${KEY_FILE}"
    echo ""
    read -p "Overwrite existing certificates? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Certificate generation cancelled."
        exit 0
    fi
fi

echo "Generating 2048-bit RSA private key and self-signed certificate..."
echo ""

# Generate private key and self-signed certificate
# -x509: Output self-signed certificate instead of certificate request
# -newkey rsa:2048: Generate new 2048-bit RSA key
# -keyout: Output file for private key
# -out: Output file for certificate
# -days 365: Certificate valid for 365 days
# -nodes: Don't encrypt private key (no passphrase)
# -subj: Certificate subject information
openssl req -x509 -newkey rsa:2048 \
    -keyout "${KEY_FILE}" \
    -out "${CERT_FILE}" \
    -days 365 \
    -nodes \
    -subj "/CN=localhost/O=IHE Test Utility/C=US" \
    2>/dev/null

if [ $? -eq 0 ]; then
    echo "✓ Certificate generation successful!"
    echo ""
    echo "Generated files:"
    echo "  - Certificate: ${CERT_FILE}"
    echo "  - Private Key: ${KEY_FILE}"
    echo ""
    echo "Certificate details:"
    openssl x509 -in "${CERT_FILE}" -noout -subject -dates
    echo ""
    echo "To use HTTPS with the mock server:"
    echo "  ihe-test-util mock start --https"
    echo ""
    echo "⚠️  WARNING: Self-signed certificates will trigger browser warnings."
    echo "    This is normal and expected for testing purposes."
else
    echo "✗ Certificate generation failed!"
    exit 1
fi
