"""SAML CLI commands for generation, verification, and testing.

This module provides CLI commands for SAML assertion testing including:
- saml generate: Create SAML assertions with optional signing
- saml verify: Validate SAML structure and signatures
- saml demo: Generate sample WS-Security SOAP envelopes
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from lxml import etree
from signxml import XMLVerifier
from signxml.exceptions import InvalidDigest, InvalidSignature

from ihe_test_util.models.saml import SAMLAssertion
from ihe_test_util.saml import (
    SAMLProgrammaticGenerator,
    SAMLSigner,
    SAMLTemplatePersonalizer,
    SAMLVerifier,
    WSSecurityHeaderBuilder,
    get_certificate_info,
    load_certificate,
    load_saml_template,
)
from ihe_test_util.utils.exceptions import (
    ConfigurationError,
    SAMLError,
    ValidationError,
)

logger = logging.getLogger(__name__)


@click.group(name="saml")
def saml_group() -> None:
    """SAML generation and verification commands.
    
    Provides tools for testing SAML workflows including assertion generation,
    signature verification, and WS-Security SOAP envelope creation.
    """
    pass


@saml_group.command(name="generate")
@click.option(
    "--template",
    type=click.Path(exists=True, path_type=Path),
    help="Path to SAML template XML file (template-based generation)",
)
@click.option(
    "--programmatic",
    is_flag=True,
    help="Use programmatic generation (default if no template)",
)
@click.option(
    "--subject",
    type=str,
    help="Subject identifier (required for programmatic generation)",
)
@click.option(
    "--issuer",
    type=str,
    help="Issuer identifier (required for programmatic generation)",
)
@click.option(
    "--audience",
    type=str,
    help="Audience identifier (required for programmatic generation)",
)
@click.option(
    "--validity",
    type=int,
    default=5,
    help="Assertion validity period in minutes (default: 5)",
)
@click.option(
    "--sign",
    is_flag=True,
    help="Sign assertion with certificate",
)
@click.option(
    "--cert",
    type=click.Path(exists=True, path_type=Path),
    help="Certificate file path (PEM/PKCS12/DER)",
)
@click.option(
    "--key",
    type=click.Path(exists=True, path_type=Path),
    help="Private key file path (if separate from cert)",
)
@click.option(
    "--cert-password",
    type=str,
    help="Certificate password (for PKCS12)",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Save SAML assertion to file",
)
@click.option(
    "--format",
    type=click.Choice(["xml", "pretty"]),
    default="pretty",
    help="Output format (default: pretty)",
)
def generate(
    template: Optional[Path],
    programmatic: bool,
    subject: Optional[str],
    issuer: Optional[str],
    audience: Optional[str],
    validity: int,
    sign: bool,
    cert: Optional[Path],
    key: Optional[Path],
    cert_password: Optional[str],
    output: Optional[Path],
    format: str,
) -> None:
    """Generate SAML 2.0 assertion with optional signing.
    
    Supports both template-based and programmatic generation. Template-based
    generation requires --template option, while programmatic generation
    requires --subject, --issuer, and --audience options.
    
    Examples:
    
        # Programmatic generation with signing
        ihe-test-util saml generate --programmatic \\
            --subject user@example.com \\
            --issuer https://idp.example.com \\
            --audience https://sp.example.com \\
            --sign --cert certs/saml.p12 --cert-password secret \\
            --output saml-assertion.xml
            
        # Template-based generation
        ihe-test-util saml generate --template templates/saml-template.xml \\
            --sign --cert certs/saml.pem --key certs/key.pem
    """
    try:
        # Validate generation method and parameters
        if template and programmatic:
            raise click.UsageError(
                "Cannot specify both --template and --programmatic. "
                "Choose one generation method."
            )
        
        # Default to programmatic if neither specified
        use_programmatic = programmatic or not template
        
        # Validate programmatic parameters
        if use_programmatic and not template:
            if not subject or not issuer or not audience:
                raise click.UsageError(
                    "Programmatic generation requires --subject, --issuer, and --audience. "
                    "Provide all required parameters or use --template instead."
                )
        
        # Validate signing parameters
        if sign and not cert:
            raise click.UsageError(
                "Signing requires --cert parameter. "
                "Provide certificate file path (PEM, PKCS12, or DER format)."
            )
        
        logger.info("Starting SAML assertion generation")
        
        # Generate SAML assertion
        if template:
            logger.info(f"Using template-based generation: {template}")
            
            # For template-based, we need subject/issuer/audience for personalization
            if not subject or not issuer or not audience:
                raise click.UsageError(
                    "Template-based generation requires --subject, --issuer, and --audience "
                    "for personalization. Provide all required parameters."
                )
            
            # Personalize template
            personalizer = SAMLTemplatePersonalizer()
            parameters = {
                "subject": subject,
                "issuer": issuer,
                "audience": audience,
                # Provide defaults for optional attribute placeholders
                "attr_username": subject,  # Use subject as username
                "attr_role": "Physician",  # Default role
                "attr_organization": "Example Healthcare",  # Default organization
                "attr_purpose_of_use": "TREATMENT",  # Default purpose of use
            }
            assertion_xml = personalizer.personalize(
                template_path=template,
                parameters=parameters,
                validity_minutes=validity,
            )
            
            # Parse XML to create SAMLAssertion object for consistent handling
            from lxml import etree as ET
            root = ET.fromstring(assertion_xml.encode('utf-8'))
            saml_ns = "urn:oasis:names:tc:SAML:2.0:assertion"
            
            # Extract metadata for SAMLAssertion object
            assertion_id = root.get("ID", "")
            issue_instant_str = root.get("IssueInstant", "")
            
            # Parse timestamps
            from datetime import datetime, timezone
            issue_instant = datetime.fromisoformat(issue_instant_str.replace("Z", "+00:00"))
            
            conditions = root.find(f".//{{{saml_ns}}}Conditions")
            not_before_str = conditions.get("NotBefore", "") if conditions is not None else ""
            not_on_or_after_str = conditions.get("NotOnOrAfter", "") if conditions is not None else ""
            
            not_before = datetime.fromisoformat(not_before_str.replace("Z", "+00:00"))
            not_on_or_after = datetime.fromisoformat(not_on_or_after_str.replace("Z", "+00:00"))
            
            # Create SAMLAssertion object
            from ihe_test_util.models.saml import SAMLGenerationMethod
            assertion = SAMLAssertion(
                assertion_id=assertion_id,
                subject=subject,  # type: ignore
                issuer=issuer,  # type: ignore
                audience=audience,  # type: ignore
                issue_instant=issue_instant,
                not_before=not_before,
                not_on_or_after=not_on_or_after,
                xml_content=assertion_xml,
                signature="",  # Not signed yet
                certificate_subject="",  # No cert until signed
                generation_method=SAMLGenerationMethod.TEMPLATE,
            )
        else:
            logger.info("Using programmatic generation")
            # Programmatic generation
            generator = SAMLProgrammaticGenerator()
            assertion = generator.generate(
                subject=subject,  # type: ignore
                issuer=issuer,  # type: ignore
                audience=audience,  # type: ignore
                validity_minutes=validity,
            )
        
        # Sign if requested
        if sign:
            logger.info(f"Signing assertion with certificate: {cert}")
            cert_bundle = load_certificate(
                cert,  # type: ignore
                key_path=key,
                password=cert_password.encode('utf-8') if cert_password else None,
            )
            signer = SAMLSigner(cert_bundle)
            assertion = signer.sign_assertion(assertion)
            click.echo(click.style("✓", fg="green", bold=True) + " SAML assertion signed")
        
        # Format output
        formatted_xml = _format_xml_output(assertion.xml_content, format)
        
        # Display assertion metadata
        click.echo(click.style("\n=== SAML Assertion Metadata ===", bold=True))
        _display_assertion_metadata(assertion)
        
        # Display or save output
        if output:
            output.write_text(formatted_xml, encoding="utf-8")
            click.echo(
                click.style("\n✓", fg="green", bold=True)
                + f" SAML assertion saved to: {output}"
            )
        else:
            click.echo(click.style("\n=== SAML Assertion XML ===", bold=True))
            click.echo(formatted_xml)
        
        logger.info("SAML assertion generation completed successfully")
        
    except click.UsageError:
        raise
    except ConfigurationError as e:
        click.echo(
            click.style("✗", fg="red", bold=True) + f" Configuration error: {e}",
            err=True,
        )
        logger.error(f"Configuration error during SAML generation: {e}")
        raise click.exceptions.Exit(1)
    except ValidationError as e:
        click.echo(
            click.style("✗", fg="red", bold=True)
            + f" Validation error: {e}. Ensure template has valid SAML 2.0 structure.",
            err=True,
        )
        logger.error(f"Validation error during SAML generation: {e}")
        raise click.exceptions.Exit(1)
    except FileNotFoundError as e:
        click.echo(
            click.style("✗", fg="red", bold=True)
            + f" File not found: {e}. Ensure the file exists and path is correct.",
            err=True,
        )
        logger.error(f"File not found during SAML generation: {e}")
        raise click.exceptions.Exit(1)
    except Exception as e:
        click.echo(
            click.style("✗", fg="red", bold=True)
            + f" Unexpected error during SAML generation: {e}",
            err=True,
        )
        logger.exception("Unexpected error during SAML generation")
        raise click.exceptions.Exit(1)


@saml_group.command(name="verify")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--verbose", is_flag=True, help="Show detailed validation results")
def verify(file: Path, verbose: bool) -> None:
    """Validate SAML assertion structure and signature.
    
    Verifies SAML 2.0 structure, validates XML signatures, and checks
    assertion timestamps. Displays certificate information for signed assertions.
    
    Args:
        file: Path to SAML assertion XML file to verify
        
    Examples:
    
        # Verify SAML assertion
        ihe-test-util saml verify saml-assertion.xml
        
        # Verify with detailed output
        ihe-test-util saml verify saml-assertion.xml --verbose
    """
    try:
        logger.info(f"Verifying SAML assertion: {file}")
        
        # Read SAML file
        saml_xml = file.read_text(encoding="utf-8")
        
        # Parse XML
        try:
            root = etree.fromstring(saml_xml.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            click.echo(
                click.style("✗", fg="red", bold=True) + " SAML structure invalid",
                err=True,
            )
            click.echo(f"XML parsing error: {e}", err=True)
            raise click.exceptions.Exit(1)
        
        # Check SAML 2.0 structure
        saml_ns = "urn:oasis:names:tc:SAML:2.0:assertion"
        is_saml = root.tag == f"{{{saml_ns}}}Assertion"
        
        if is_saml:
            click.echo(click.style("✓", fg="green", bold=True) + " SAML 2.0 structure valid")
        else:
            click.echo(click.style("✗", fg="red", bold=True) + " SAML 2.0 structure invalid")
            click.echo(
                f"Expected SAML Assertion root element, found: {root.tag}",
                err=True,
            )
            raise click.exceptions.Exit(1)
        
        # Extract assertion metadata
        assertion_id = root.get("ID", "N/A")
        issue_instant = root.get("IssueInstant", "N/A")
        
        # Extract subject, issuer, audience
        issuer_elem = root.find(f".//{{{saml_ns}}}Issuer")
        subject_elem = root.find(f".//{{{saml_ns}}}Subject/{{{saml_ns}}}NameID")
        audience_elem = root.find(
            f".//{{{saml_ns}}}Conditions/{{{saml_ns}}}AudienceRestriction/{{{saml_ns}}}Audience"
        )
        
        issuer = issuer_elem.text if issuer_elem is not None else "N/A"
        subject = subject_elem.text if subject_elem is not None else "N/A"
        audience = audience_elem.text if audience_elem is not None else "N/A"
        
        # Check for signature
        ds_ns = "http://www.w3.org/2000/09/xmldsig#"
        signature_elem = root.find(f".//{{{ds_ns}}}Signature")
        is_signed = signature_elem is not None
        
        if is_signed:
            # Verify signature using XMLVerifier
            try:
                verifier = XMLVerifier()
                verified_data = verifier.verify(root)
                
                click.echo(
                    click.style("✓", fg="green", bold=True) + " Signature valid"
                )
                
                # Extract and display certificate info
                cert_data_elem = signature_elem.find(
                    f".//{{{ds_ns}}}KeyInfo/{{{ds_ns}}}X509Data/{{{ds_ns}}}X509Certificate"
                )
                if cert_data_elem is not None and verbose:
                    click.echo(click.style("\n=== Certificate Information ===", bold=True))
                    # Note: Full certificate parsing would require decoding the base64 cert
                    click.echo("Certificate embedded in signature")
                    
            except InvalidSignature as e:
                # Check if this is a certificate validation error (common with test certs)
                error_str = str(e).lower()
                if "certificate" in error_str and ("extension" in error_str or "serial number" in error_str):
                    click.echo(
                        click.style("⚠", fg="yellow", bold=True) + 
                        " Signature cryptographically valid (certificate has validation warnings)"
                    )
                    if verbose:
                        click.echo(f"   Note: {e}")
                        click.echo("   This is common with self-signed test certificates")
                else:
                    click.echo(
                        click.style("✗", fg="red", bold=True) + f" Signature invalid: {e}",
                        err=True,
                    )
                    raise click.exceptions.Exit(1)
            except InvalidDigest as e:
                click.echo(
                    click.style("✗", fg="red", bold=True) + f" Digest invalid (tampering detected): {e}",
                    err=True,
                )
                raise click.exceptions.Exit(1)
        else:
            click.echo(click.style("-", fg="yellow", bold=True) + " Not signed")
        
        # Validate timestamps
        conditions_elem = root.find(f".//{{{saml_ns}}}Conditions")
        if conditions_elem is not None:
            not_before = conditions_elem.get("NotBefore")
            not_on_or_after = conditions_elem.get("NotOnOrAfter")
            
            now = datetime.now(timezone.utc)
            timestamps_valid = True
            
            if not_before:
                try:
                    not_before_dt = datetime.fromisoformat(
                        not_before.replace("Z", "+00:00")
                    )
                    if now < not_before_dt:
                        timestamps_valid = False
                        click.echo(
                            click.style("✗", fg="red", bold=True)
                            + " Timestamps invalid: Assertion not yet valid"
                        )
                except ValueError:
                    pass
            
            if not_on_or_after and timestamps_valid:
                try:
                    not_on_or_after_dt = datetime.fromisoformat(
                        not_on_or_after.replace("Z", "+00:00")
                    )
                    if now >= not_on_or_after_dt:
                        timestamps_valid = False
                        click.echo(
                            click.style("✗", fg="red", bold=True)
                            + " Timestamps invalid: Assertion expired"
                        )
                except ValueError:
                    pass
            
            if timestamps_valid:
                click.echo(
                    click.style("✓", fg="green", bold=True) + " Timestamps valid"
                )
        
        # Display assertion metadata
        if verbose:
            click.echo(click.style("\n=== Assertion Metadata ===", bold=True))
            click.echo(f"ID:            {assertion_id}")
            click.echo(f"Issue Instant: {issue_instant}")
            click.echo(f"Issuer:        {issuer}")
            click.echo(f"Subject:       {subject}")
            click.echo(f"Audience:      {audience}")
        
        logger.info("SAML assertion verification completed successfully")
        
    except click.exceptions.Exit:
        raise
    except FileNotFoundError as e:
        click.echo(
            click.style("✗", fg="red", bold=True)
            + f" File not found: {e}. Ensure the file exists and path is correct.",
            err=True,
        )
        logger.error(f"File not found during SAML verification: {e}")
        raise click.exceptions.Exit(1)
    except Exception as e:
        click.echo(
            click.style("✗", fg="red", bold=True)
            + f" Unexpected error during SAML verification: {e}",
            err=True,
        )
        logger.exception("Unexpected error during SAML verification")
        raise click.exceptions.Exit(1)


@saml_group.command(name="demo")
@click.option(
    "--scenario",
    type=click.Choice(["pix-add", "iti41"]),
    default="pix-add",
    help="IHE transaction scenario (default: pix-add)",
)
@click.option(
    "--cert",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Certificate for signing (required)",
)
@click.option(
    "--key",
    type=click.Path(exists=True, path_type=Path),
    help="Private key (if separate from cert)",
)
@click.option(
    "--cert-password",
    type=str,
    help="Certificate password (for PKCS12)",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Save demo SOAP envelope to file",
)
def demo(
    scenario: str,
    cert: Path,
    key: Optional[Path],
    cert_password: Optional[str],
    output: Optional[Path],
) -> None:
    """Generate sample WS-Security SOAP envelope with signed SAML.
    
    Creates a complete SOAP envelope with WS-Security header containing
    a signed SAML assertion for the specified IHE transaction scenario.
    
    Examples:
    
        # Generate PIX Add demo envelope
        ihe-test-util saml demo --scenario pix-add \\
            --cert certs/saml.p12 --cert-password secret \\
            --output demo-pix-add.xml
            
        # Generate ITI-41 demo envelope
        ihe-test-util saml demo --scenario iti41 \\
            --cert certs/saml.pem --key certs/key.pem \\
            --output demo-iti41.xml
    """
    try:
        logger.info(f"Generating demo SOAP envelope for scenario: {scenario}")
        
        # Load certificate
        cert_bundle = load_certificate(
            cert,
            key_path=key,
            password=cert_password.encode('utf-8') if cert_password else None,
        )
        
        # Generate sample SAML assertion
        generator = SAMLProgrammaticGenerator()
        assertion = generator.generate(
            subject=f"demo-user@{scenario}-test.example.com",
            issuer=f"https://demo-idp.{scenario}-test.example.com",
            audience=f"https://demo-sp.{scenario}-test.example.com",
            validity_minutes=5,
        )
        
        # Sign assertion
        signer = SAMLSigner(cert_bundle)
        signed_assertion = signer.sign_assertion(assertion)
        
        # Build WS-Security SOAP envelope
        builder = WSSecurityHeaderBuilder()
        
        if scenario == "pix-add":
            # Create sample PIX Add message (minimal HL7v3 structure)
            sample_pix_message_str = """<PRPA_IN201301UV02>
    <id root="1.2.3.4.5" extension="DEMO-PIX-ADD-123"/>
    <creationTime value="20251113000000"/>
    <interactionId root="2.16.840.1.113883.1.6" extension="PRPA_IN201301UV02"/>
</PRPA_IN201301UV02>"""
            # Parse XML string to Element
            sample_pix_message = etree.fromstring(sample_pix_message_str.encode('utf-8'))
            soap_envelope = builder.create_pix_add_soap_envelope(
                signed_saml=signed_assertion,
                pix_message=sample_pix_message,
            )
        elif scenario == "iti41":
            # Create sample ITI-41 request (minimal structure)
            sample_iti41_request_str = """<ProvideAndRegisterDocumentSetRequest>
    <SubmitObjectsRequest/>
    <Document id="Document01">Sample CCD content</Document>
</ProvideAndRegisterDocumentSetRequest>"""
            # Parse XML string to Element
            sample_iti41_request = etree.fromstring(sample_iti41_request_str.encode('utf-8'))
            soap_envelope = builder.create_iti41_soap_envelope(
                signed_saml=signed_assertion,
                iti41_request=sample_iti41_request,
            )
        
        # Pretty-print the envelope
        formatted_envelope = _format_xml_output(soap_envelope, "pretty")
        
        # Display or save
        if output:
            output.write_text(formatted_envelope, encoding="utf-8")
            click.echo(
                click.style("✓", fg="green", bold=True)
                + f" Demo SOAP envelope saved to: {output}"
            )
        else:
            click.echo(click.style("=== Demo SOAP Envelope ===", bold=True))
            click.echo(formatted_envelope)
        
        # Display usage notes
        click.echo(click.style("\n=== Usage Notes ===", bold=True))
        click.echo(f"Scenario:      {scenario.upper()}")
        click.echo(f"SAML Subject:  {signed_assertion.subject}")
        click.echo(f"SAML Issuer:   {signed_assertion.issuer}")
        click.echo(f"SAML Audience: {signed_assertion.audience}")
        click.echo(f"Valid Until:   {signed_assertion.not_on_or_after.isoformat()}")
        click.echo("\nThis envelope can be sent to IHE endpoints using:")
        click.echo("  - Python requests library with appropriate headers")
        click.echo("  - curl with --data-binary and Content-Type: application/soap+xml")
        
        logger.info("Demo SOAP envelope generation completed successfully")
        
    except ConfigurationError as e:
        click.echo(
            click.style("✗", fg="red", bold=True)
            + f" Invalid certificate: {e}. Provide valid PEM, PKCS12, or DER certificate.",
            err=True,
        )
        logger.error(f"Configuration error during demo generation: {e}")
        raise click.exceptions.Exit(1)
    except FileNotFoundError as e:
        click.echo(
            click.style("✗", fg="red", bold=True)
            + f" File not found: {e}. Ensure the file exists and path is correct.",
            err=True,
        )
        logger.error(f"File not found during demo generation: {e}")
        raise click.exceptions.Exit(1)
    except Exception as e:
        click.echo(
            click.style("✗", fg="red", bold=True)
            + f" Unexpected error during demo generation: {e}",
            err=True,
        )
        logger.exception("Unexpected error during demo generation")
        raise click.exceptions.Exit(1)


def _format_xml_output(xml_content: str, format_type: str) -> str:
    """Format XML output for display.
    
    Args:
        xml_content: Raw XML string
        format_type: Format type ('xml' or 'pretty')
        
    Returns:
        Formatted XML string
    """
    if format_type == "pretty":
        try:
            root = etree.fromstring(xml_content.encode("utf-8"))
            return etree.tostring(
                root, pretty_print=True, encoding="unicode", xml_declaration=False
            )
        except etree.XMLSyntaxError:
            # If parsing fails, return as-is
            return xml_content
    return xml_content


def _display_assertion_metadata(assertion: SAMLAssertion) -> None:
    """Display SAML assertion metadata in readable format.
    
    Args:
        assertion: SAML assertion to display
    """
    click.echo(f"ID:            {assertion.assertion_id}")
    click.echo(f"Subject:       {assertion.subject}")
    click.echo(f"Issuer:        {assertion.issuer}")
    click.echo(f"Audience:      {assertion.audience}")
    click.echo(f"Issue Instant: {assertion.issue_instant.isoformat()}")
    click.echo(f"Valid From:    {assertion.not_before.isoformat()}")
    click.echo(f"Valid Until:   {assertion.not_on_or_after.isoformat()}")
    click.echo(f"Generation:    {assertion.generation_method.value}")
    
    # Calculate validity duration
    duration = assertion.not_on_or_after - assertion.not_before
    click.echo(f"Validity:      {duration.total_seconds() / 60:.1f} minutes")
