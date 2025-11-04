# Configuration Files

This directory contains configuration files for the IHE Test Utility.

## Purpose

Configuration files define endpoint URLs, certificate paths, SAML settings,
and other runtime parameters for IHE transactions.

## Configuration Files

- `endpoints.json` - IHE endpoint URLs (PIX Manager, Document Repository)
- `certificates.json` - Certificate and key file paths
- `saml_config.json` - SAML assertion configuration
- `logging.json` - Logging configuration

## Environment Variables

Configuration can be overridden using environment variables defined in `.env`:

- `IHE_PIX_ENDPOINT` - PIX Manager SOAP endpoint URL
- `IHE_XDS_ENDPOINT` - XDS Document Repository endpoint URL
- `SAML_ISSUER` - SAML assertion issuer URI
- `CERTIFICATE_PATH` - Path to X.509 certificate file
- `PRIVATE_KEY_PATH` - Path to private key file
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

## Configuration Priority

Configuration is loaded in the following priority order (highest to lowest):

1. Environment variables (`.env` file)
2. Configuration files in this directory
3. Default values in code

## Example Configuration

### endpoints.json

```json
{
  "pix_manager": {
    "url": "https://pix-manager.example.com/PIXManager",
    "receiver_oid": "1.2.3.4.5.6.7.8.9.1",
    "receiver_name": "PIX Manager",
    "sender_oid": "1.2.3.4.5.6.7.8.9.2",
    "sender_name": "Test Utility"
  },
  "xds_repository": {
    "url": "https://xds-repo.example.com/XDSRepository",
    "repository_oid": "1.2.3.4.5.6.7.8.9.3"
  }
}
```

### certificates.json

```json
{
  "signing": {
    "certificate": "certs/signing_cert.pem",
    "private_key": "certs/signing_key.pem",
    "format": "PEM"
  },
  "tls": {
    "client_cert": "certs/client_cert.pem",
    "client_key": "certs/client_key.pem",
    "ca_bundle": "certs/ca_bundle.pem"
  }
}
```

## Security Notes

- **DO NOT** commit sensitive configuration files to version control
- Use `.env.example` as a template for local `.env` files
- Store production certificates and keys securely
- Use environment variables for sensitive values in CI/CD
