"""Generate test certificates for XML signing tests.

This script generates test certificates using the cryptography library,
avoiding shell/path issues with openssl on Windows.
"""

from pathlib import Path
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import pkcs12


def generate_test_certificates():
    """Generate all test certificates needed for XML signing tests."""
    
    fixtures_dir = Path(__file__).parent
    cert_chain_dir = fixtures_dir / "cert_chain"
    cert_chain_dir.mkdir(exist_ok=True)
    
    print("Generating test certificates...")
    
    # Generate basic test certificate
    print("1. Generating basic test certificate (PEM format)...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "TestState"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "TestCity"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TestOrg"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "TestUnit"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Test Certificate"),
    ])
    
    # Add required X.509 extensions for signxml validation
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
        critical=False,
    ).add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(private_key.public_key()),
        critical=False,
    ).sign(private_key, hashes.SHA256(), default_backend())
    
    # Write PEM files
    with open(fixtures_dir / "test_key.pem", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(fixtures_dir / "test_cert.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    print("   ✓ Created test_key.pem and test_cert.pem")
    
    # Convert to DER
    print("2. Converting certificate to DER format...")
    with open(fixtures_dir / "test_cert.der", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.DER))
    
    print("   ✓ Created test_cert.der")
    
    # Create PKCS12
    print("3. Creating PKCS12 certificate...")
    p12_password = b"testpass"
    
    p12_data = serialization.pkcs12.serialize_key_and_certificates(
        name=b"Test Certificate",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(p12_password)
    )
    
    with open(fixtures_dir / "test_cert.p12", "wb") as f:
        f.write(p12_data)
    
    print(f"   ✓ Created test_cert.p12 (password: {p12_password.decode()})")
    
    # Generate certificate chain
    print("4. Generating certificate chain...")
    
    # Root CA
    print("   Generating Root CA...")
    root_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    root_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "TestState"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "TestCity"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TestOrg"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Root CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Test Root CA"),
    ])
    
    root_cert = x509.CertificateBuilder().subject_name(
        root_subject
    ).issuer_name(
        root_subject
    ).public_key(
        root_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True,
    ).sign(root_key, hashes.SHA256(), default_backend())
    
    with open(cert_chain_dir / "root_key.pem", "wb") as f:
        f.write(root_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(cert_chain_dir / "root_cert.pem", "wb") as f:
        f.write(root_cert.public_bytes(serialization.Encoding.PEM))
    
    print("   ✓ Created root_cert.pem and root_key.pem")
    
    # Intermediate CA
    print("   Generating Intermediate CA...")
    intermediate_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    intermediate_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "TestState"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "TestCity"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TestOrg"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Intermediate CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Test Intermediate CA"),
    ])
    
    intermediate_cert = x509.CertificateBuilder().subject_name(
        intermediate_subject
    ).issuer_name(
        root_subject
    ).public_key(
        intermediate_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=0),
        critical=True,
    ).sign(root_key, hashes.SHA256(), default_backend())
    
    with open(cert_chain_dir / "intermediate_key.pem", "wb") as f:
        f.write(intermediate_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(cert_chain_dir / "intermediate_cert.pem", "wb") as f:
        f.write(intermediate_cert.public_bytes(serialization.Encoding.PEM))
    
    print("   ✓ Created intermediate_cert.pem and intermediate_key.pem")
    
    # Leaf certificate
    print("   Generating Leaf certificate...")
    leaf_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    leaf_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "TestState"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "TestCity"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TestOrg"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Leaf"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Test Leaf Certificate"),
    ])
    
    leaf_cert = x509.CertificateBuilder().subject_name(
        leaf_subject
    ).issuer_name(
        intermediate_subject
    ).public_key(
        leaf_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).sign(intermediate_key, hashes.SHA256(), default_backend())
    
    with open(cert_chain_dir / "leaf_key.pem", "wb") as f:
        f.write(leaf_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(cert_chain_dir / "leaf_cert.pem", "wb") as f:
        f.write(leaf_cert.public_bytes(serialization.Encoding.PEM))
    
    print("   ✓ Created leaf_cert.pem and leaf_key.pem")
    
    # Create chain file
    with open(cert_chain_dir / "chain.pem", "wb") as f:
        f.write(leaf_cert.public_bytes(serialization.Encoding.PEM))
        f.write(intermediate_cert.public_bytes(serialization.Encoding.PEM))
        f.write(root_cert.public_bytes(serialization.Encoding.PEM))
    
    print("   ✓ Created chain.pem")
    
    print("\n✅ Certificate generation complete!")
    print(f"\nGenerated files in: {fixtures_dir}")
    print("  - test_cert.pem, test_key.pem")
    print("  - test_cert.der")
    print("  - test_cert.p12")
    print(f"  - {cert_chain_dir}/ (root, intermediate, leaf)")
    print("\n⚠️  Remember: These are TEST CERTIFICATES for development only!")


if __name__ == "__main__":
    generate_test_certificates()
