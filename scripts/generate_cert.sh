#!/bin/bash
# Certificate generation script for testing XML signing
# Generates self-signed certificates in multiple formats (PEM, PKCS12, DER)
# and creates a certificate chain (root, intermediate, leaf)

set -e  # Exit on error

# Prevent Git Bash on Windows from converting Unix paths
export MSYS_NO_PATHCONV=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FIXTURES_DIR="$PROJECT_ROOT/tests/fixtures"
CERT_CHAIN_DIR="$FIXTURES_DIR/cert_chain"

# Create directories if they don't exist
mkdir -p "$FIXTURES_DIR"
mkdir -p "$CERT_CHAIN_DIR"

echo "Generating test certificates for XML signing spike..."
echo "Output directory: $FIXTURES_DIR"
echo ""

# Configuration
DAYS_VALID=365
KEY_SIZE=2048
COUNTRY="US"
STATE="TestState"
CITY="TestCity"
ORG="TestOrg"
OU="TestUnit"

# ============================================================================
# Generate basic test certificate and key (PEM format)
# ============================================================================
echo "1. Generating basic test certificate (PEM format)..."

openssl req -x509 -newkey rsa:$KEY_SIZE -nodes \
    -keyout "$FIXTURES_DIR/test_key.pem" \
    -out "$FIXTURES_DIR/test_cert.pem" \
    -days $DAYS_VALID \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=Test Certificate"

echo "   ✓ Created test_key.pem"
echo "   ✓ Created test_cert.pem"
echo ""

# ============================================================================
# Convert to DER format
# ============================================================================
echo "2. Converting certificate to DER format..."

openssl x509 -in "$FIXTURES_DIR/test_cert.pem" \
    -outform DER -out "$FIXTURES_DIR/test_cert.der"

echo "   ✓ Created test_cert.der"
echo ""

# ============================================================================
# Create PKCS12 format (with password)
# ============================================================================
echo "3. Creating PKCS12 certificate..."

PKCS12_PASSWORD="testpass"

openssl pkcs12 -export \
    -in "$FIXTURES_DIR/test_cert.pem" \
    -inkey "$FIXTURES_DIR/test_key.pem" \
    -out "$FIXTURES_DIR/test_cert.p12" \
    -name "Test Certificate" \
    -password "pass:$PKCS12_PASSWORD"

echo "   ✓ Created test_cert.p12 (password: $PKCS12_PASSWORD)"
echo ""

# ============================================================================
# Generate certificate chain (root -> intermediate -> leaf)
# ============================================================================
echo "4. Generating certificate chain..."

# Root CA
echo "   Generating Root CA..."
openssl req -x509 -newkey rsa:$KEY_SIZE -nodes \
    -keyout "$CERT_CHAIN_DIR/root_key.pem" \
    -out "$CERT_CHAIN_DIR/root_cert.pem" \
    -days $DAYS_VALID \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=Root CA/CN=Test Root CA"

echo "   ✓ Created root_cert.pem and root_key.pem"

# Intermediate CA - Create key and CSR
echo "   Generating Intermediate CA..."
openssl req -newkey rsa:$KEY_SIZE -nodes \
    -keyout "$CERT_CHAIN_DIR/intermediate_key.pem" \
    -out "$CERT_CHAIN_DIR/intermediate_csr.pem" \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=Intermediate CA/CN=Test Intermediate CA"

# Sign intermediate with root
openssl x509 -req \
    -in "$CERT_CHAIN_DIR/intermediate_csr.pem" \
    -CA "$CERT_CHAIN_DIR/root_cert.pem" \
    -CAkey "$CERT_CHAIN_DIR/root_key.pem" \
    -CAcreateserial \
    -out "$CERT_CHAIN_DIR/intermediate_cert.pem" \
    -days $DAYS_VALID \
    -extensions v3_ca

echo "   ✓ Created intermediate_cert.pem and intermediate_key.pem"

# Leaf certificate - Create key and CSR
echo "   Generating Leaf certificate..."
openssl req -newkey rsa:$KEY_SIZE -nodes \
    -keyout "$CERT_CHAIN_DIR/leaf_key.pem" \
    -out "$CERT_CHAIN_DIR/leaf_csr.pem" \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=Leaf/CN=Test Leaf Certificate"

# Sign leaf with intermediate
openssl x509 -req \
    -in "$CERT_CHAIN_DIR/leaf_csr.pem" \
    -CA "$CERT_CHAIN_DIR/intermediate_cert.pem" \
    -CAkey "$CERT_CHAIN_DIR/intermediate_key.pem" \
    -CAcreateserial \
    -out "$CERT_CHAIN_DIR/leaf_cert.pem" \
    -days $DAYS_VALID

echo "   ✓ Created leaf_cert.pem and leaf_key.pem"

# Create certificate chain file
cat "$CERT_CHAIN_DIR/leaf_cert.pem" \
    "$CERT_CHAIN_DIR/intermediate_cert.pem" \
    "$CERT_CHAIN_DIR/root_cert.pem" \
    > "$CERT_CHAIN_DIR/chain.pem"

echo "   ✓ Created chain.pem (full certificate chain)"
echo ""

# ============================================================================
# Create README with certificate information
# ============================================================================
echo "5. Creating README..."

cat > "$FIXTURES_DIR/README.md" << EOF
# Test Certificates

This directory contains test certificates generated for XML signing spike testing.

**⚠️ WARNING: These are TEST CERTIFICATES ONLY. Never use in production!**

## Files

### Basic Test Certificates
- \`test_cert.pem\` - X.509 certificate in PEM format
- \`test_key.pem\` - Private key in PEM format (unencrypted)
- \`test_cert.der\` - X.509 certificate in DER format
- \`test_cert.p12\` - PKCS12 bundle (password: testpass)

### Certificate Chain
Located in \`cert_chain/\`:
- \`root_cert.pem\` / \`root_key.pem\` - Root CA
- \`intermediate_cert.pem\` / \`intermediate_key.pem\` - Intermediate CA
- \`leaf_cert.pem\` / \`leaf_key.pem\` - Leaf certificate
- \`chain.pem\` - Complete chain (leaf -> intermediate -> root)

## Certificate Details

**Subject**: C=$COUNTRY, ST=$STATE, L=$CITY, O=$ORG, OU=$OU/Root CA/Intermediate CA/Leaf
**Key Size**: $KEY_SIZE bits RSA
**Validity**: $DAYS_VALID days from generation date
**Algorithm**: RSA with SHA-256

## Usage in Tests

\`\`\`python
from pathlib import Path
from ihe_test_util.saml.certificate_manager import CertificateManager

fixtures_dir = Path("tests/fixtures")

# Load PEM certificate
cert = CertificateManager.load_pem_certificate(fixtures_dir / "test_cert.pem")
key = CertificateManager.load_pem_private_key(fixtures_dir / "test_key.pem")

# Load DER certificate
cert_der = CertificateManager.load_der_certificate(fixtures_dir / "test_cert.der")

# Load PKCS12
key, cert, chain = CertificateManager.load_pkcs12(
    fixtures_dir / "test_cert.p12",
    password=b"testpass"
)
\`\`\`

## Regenerating Certificates

To regenerate all test certificates:

\`\`\`bash
cd scripts
./generate_cert.sh
\`\`\`

## Security Notes

- Private keys are NOT encrypted (for testing convenience)
- PKCS12 uses weak password "testpass"
- Certificates are self-signed
- **NEVER commit real private keys or production certificates to version control**
EOF

echo "   ✓ Created README.md"
echo ""

# ============================================================================
# Display certificate information
# ============================================================================
echo "6. Certificate Information"
echo "   ========================"
echo ""
echo "   Basic Certificate:"
openssl x509 -in "$FIXTURES_DIR/test_cert.pem" -noout -subject -dates
echo ""
echo "   Root CA:"
openssl x509 -in "$CERT_CHAIN_DIR/root_cert.pem" -noout -subject -dates
echo ""
echo "   Intermediate CA:"
openssl x509 -in "$CERT_CHAIN_DIR/intermediate_cert.pem" -noout -subject -dates
echo ""
echo "   Leaf Certificate:"
openssl x509 -in "$CERT_CHAIN_DIR/leaf_cert.pem" -noout -subject -dates
echo ""

echo "✅ Certificate generation complete!"
echo ""
echo "Generated files:"
echo "  - $FIXTURES_DIR/test_cert.pem"
echo "  - $FIXTURES_DIR/test_key.pem"
echo "  - $FIXTURES_DIR/test_cert.der"
echo "  - $FIXTURES_DIR/test_cert.p12"
echo "  - $CERT_CHAIN_DIR/ (root, intermediate, leaf certificates)"
echo ""
echo "⚠️  Remember: These are TEST CERTIFICATES for development only!"
