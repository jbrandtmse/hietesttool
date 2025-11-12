"""Programmatic SAML 2.0 assertion generation.

This module provides functionality for generating SAML 2.0 assertions
programmatically using lxml, without requiring XML templates. It supports
custom attributes, configurable validity periods, and integration with
certificate management for automatic issuer extraction.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Union

from lxml import etree

from ..models.saml import CertificateBundle, SAMLAssertion, SAMLGenerationMethod
from ..utils.exceptions import CertificateLoadError

logger = logging.getLogger(__name__)

# SAML 2.0 namespace
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"


def generate_assertion_id() -> str:
    """Generate unique SAML assertion ID.
    
    SAML assertion IDs must start with a letter or underscore per XML ID type.
    Uses UUID4 for uniqueness.
    
    Returns:
        Unique assertion ID starting with underscore
        Format: _<32 hex characters>
        
    Example:
        >>> assertion_id = generate_assertion_id()
        >>> assert assertion_id.startswith("_")
        >>> assert len(assertion_id) == 33  # _ + 32 hex chars
    """
    assertion_id = f"_{uuid.uuid4().hex}"
    logger.debug(f"Generated assertion ID: {assertion_id}")
    return assertion_id


def generate_saml_timestamps(validity_minutes: int = 5) -> Dict[str, str]:
    """Generate SAML timestamps in ISO 8601 format.
    
    Args:
        validity_minutes: Assertion validity period in minutes (default: 5)
        
    Returns:
        Dictionary with keys: issue_instant, not_before, not_on_or_after
        All timestamps in ISO 8601 format with Z suffix (UTC)
        
    Example:
        >>> timestamps = generate_saml_timestamps(5)
        >>> assert "issue_instant" in timestamps
        >>> assert timestamps["issue_instant"].endswith("Z")
    """
    now = datetime.now(timezone.utc)
    not_on_or_after = now + timedelta(minutes=validity_minutes)
    
    timestamps = {
        "issue_instant": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "not_before": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "not_on_or_after": not_on_or_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    
    logger.debug(
        f"Generated SAML timestamps: validity={validity_minutes}min, "
        f"expires={timestamps['not_on_or_after']}"
    )
    
    return timestamps


def _validate_required_parameters(subject: str, issuer: str, audience: str) -> None:
    """Validate required SAML assertion parameters.
    
    Args:
        subject: Subject identifier
        issuer: Issuer identifier
        audience: Audience identifier
        
    Raises:
        ValueError: If any required parameter is invalid or empty
        
    Example:
        >>> _validate_required_parameters("user@example.com", "https://idp.example.com", "https://sp.example.com")
        >>> # No exception raised
    """
    if not subject or not isinstance(subject, str):
        raise ValueError(
            f"Subject must be a non-empty string, got: {subject!r}. "
            f"Provide a valid user or patient identifier."
        )
    
    if not issuer or not isinstance(issuer, str):
        raise ValueError(
            f"Issuer must be a non-empty string (URI format recommended), got: {issuer!r}. "
            f"Provide a valid issuer identifier (e.g., https://idp.example.com)."
        )
    
    if not audience or not isinstance(audience, str):
        raise ValueError(
            f"Audience must be a non-empty string (URI format recommended), got: {audience!r}. "
            f"Provide a valid audience identifier (e.g., https://sp.example.com)."
        )
    
    logger.debug(f"Parameter validation passed: subject={subject}, issuer={issuer}, audience={audience}")


def _build_assertion_element(
    assertion_id: str, issue_instant: str, issuer: str
) -> etree.Element:
    """Build SAML Assertion root element.
    
    Args:
        assertion_id: Unique assertion identifier
        issue_instant: ISO 8601 timestamp
        issuer: Issuer identifier
        
    Returns:
        lxml Element representing <saml:Assertion>
        
    Example:
        >>> assertion = _build_assertion_element("_abc123", "2025-11-11T12:00:00Z", "https://idp.example.com")
        >>> assert assertion.get("ID") == "_abc123"
    """
    # Create Assertion root element with SAML 2.0 namespace
    assertion = etree.Element(
        f"{{{SAML_NS}}}Assertion",
        nsmap={"saml": SAML_NS},
        attrib={
            "ID": assertion_id,
            "Version": "2.0",
            "IssueInstant": issue_instant,
        },
    )
    
    # Add Issuer element
    issuer_elem = etree.SubElement(assertion, f"{{{SAML_NS}}}Issuer")
    issuer_elem.text = issuer
    
    logger.debug(f"Built Assertion element: ID={assertion_id}, Issuer={issuer}")
    return assertion


def _add_subject_element(
    assertion: etree.Element, subject: str, not_on_or_after: str
) -> None:
    """Add Subject element to SAML assertion.
    
    Args:
        assertion: SAML Assertion element
        subject: Subject identifier
        not_on_or_after: ISO 8601 timestamp for subject confirmation validity
        
    Example:
        >>> assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        >>> _add_subject_element(assertion, "user@example.com", "2025-11-11T12:05:00Z")
        >>> subject_elem = assertion.find(".//{*}Subject")
        >>> assert subject_elem is not None
    """
    # Create Subject element
    subject_elem = etree.SubElement(assertion, f"{{{SAML_NS}}}Subject")
    
    # Add NameID
    name_id = etree.SubElement(
        subject_elem,
        f"{{{SAML_NS}}}NameID",
        attrib={"Format": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"},
    )
    name_id.text = subject
    
    # Add SubjectConfirmation with bearer method
    subject_confirmation = etree.SubElement(
        subject_elem,
        f"{{{SAML_NS}}}SubjectConfirmation",
        attrib={"Method": "urn:oasis:names:tc:SAML:2.0:cm:bearer"},
    )
    
    # Add SubjectConfirmationData
    etree.SubElement(
        subject_confirmation,
        f"{{{SAML_NS}}}SubjectConfirmationData",
        attrib={"NotOnOrAfter": not_on_or_after},
    )
    
    logger.debug(f"Added Subject element: {subject}")


def _add_conditions_element(
    assertion: etree.Element, not_before: str, not_on_or_after: str, audience: str
) -> None:
    """Add Conditions element to SAML assertion.
    
    Args:
        assertion: SAML Assertion element
        not_before: ISO 8601 timestamp for validity start
        not_on_or_after: ISO 8601 timestamp for validity end
        audience: Audience identifier
        
    Example:
        >>> assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        >>> _add_conditions_element(assertion, "2025-11-11T12:00:00Z", "2025-11-11T12:05:00Z", "https://sp.example.com")
        >>> conditions = assertion.find(".//{*}Conditions")
        >>> assert conditions.get("NotBefore") == "2025-11-11T12:00:00Z"
    """
    # Create Conditions element
    conditions = etree.SubElement(
        assertion,
        f"{{{SAML_NS}}}Conditions",
        attrib={"NotBefore": not_before, "NotOnOrAfter": not_on_or_after},
    )
    
    # Add AudienceRestriction
    audience_restriction = etree.SubElement(
        conditions, f"{{{SAML_NS}}}AudienceRestriction"
    )
    
    # Add Audience
    audience_elem = etree.SubElement(audience_restriction, f"{{{SAML_NS}}}Audience")
    audience_elem.text = audience
    
    logger.debug(
        f"Added Conditions element: NotBefore={not_before}, "
        f"NotOnOrAfter={not_on_or_after}, Audience={audience}"
    )


def _add_authn_statement(
    assertion: etree.Element, authn_instant: str, assertion_id: str
) -> None:
    """Add AuthnStatement element to SAML assertion.
    
    Args:
        assertion: SAML Assertion element
        authn_instant: ISO 8601 timestamp for authentication
        assertion_id: Assertion ID for SessionIndex
        
    Example:
        >>> assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        >>> _add_authn_statement(assertion, "2025-11-11T12:00:00Z", "_abc123")
        >>> authn_stmt = assertion.find(".//{*}AuthnStatement")
        >>> assert authn_stmt.get("AuthnInstant") == "2025-11-11T12:00:00Z"
    """
    # Create AuthnStatement element
    authn_statement = etree.SubElement(
        assertion,
        f"{{{SAML_NS}}}AuthnStatement",
        attrib={"AuthnInstant": authn_instant, "SessionIndex": assertion_id},
    )
    
    # Add AuthnContext
    authn_context = etree.SubElement(authn_statement, f"{{{SAML_NS}}}AuthnContext")
    
    # Add AuthnContextClassRef
    authn_context_class_ref = etree.SubElement(
        authn_context, f"{{{SAML_NS}}}AuthnContextClassRef"
    )
    authn_context_class_ref.text = (
        "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"
    )
    
    logger.debug(f"Added AuthnStatement element: AuthnInstant={authn_instant}")


def _add_attribute_statement(
    assertion: etree.Element, attributes: Dict[str, Union[str, List[str]]]
) -> None:
    """Add AttributeStatement element to SAML assertion.
    
    Supports both single-valued and multi-valued attributes.
    
    Args:
        assertion: SAML Assertion element
        attributes: Dictionary of attribute names to values (string or list of strings)
        
    Example:
        >>> assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        >>> _add_attribute_statement(assertion, {"username": "jsmith", "roles": ["physician", "admin"]})
        >>> attr_stmt = assertion.find(".//{*}AttributeStatement")
        >>> assert attr_stmt is not None
    """
    if not attributes:
        logger.debug("No attributes provided, skipping AttributeStatement")
        return
    
    # Create AttributeStatement element
    attr_statement = etree.SubElement(assertion, f"{{{SAML_NS}}}AttributeStatement")
    
    # Add each attribute
    for attr_name, attr_value in attributes.items():
        # Create Attribute element
        attr_elem = etree.SubElement(
            attr_statement, f"{{{SAML_NS}}}Attribute", attrib={"Name": attr_name}
        )
        
        # Handle multi-valued attributes (list) vs single-valued (string)
        if isinstance(attr_value, list):
            # Multi-valued: create multiple AttributeValue elements
            for value in attr_value:
                attr_value_elem = etree.SubElement(
                    attr_elem, f"{{{SAML_NS}}}AttributeValue"
                )
                attr_value_elem.text = str(value)
            logger.debug(f"Added multi-valued attribute: {attr_name} ({len(attr_value)} values)")
        else:
            # Single-valued: create single AttributeValue element
            attr_value_elem = etree.SubElement(
                attr_elem, f"{{{SAML_NS}}}AttributeValue"
            )
            attr_value_elem.text = str(attr_value)
            logger.debug(f"Added single-valued attribute: {attr_name}={attr_value}")
    
    logger.debug(f"Added AttributeStatement with {len(attributes)} attributes")


def _canonicalize_assertion(assertion: etree.Element) -> str:
    """Canonicalize SAML assertion for signing.
    
    Uses C14N (Canonical XML) algorithm to normalize XML for digital signatures.
    
    Args:
        assertion: SAML Assertion element
        
    Returns:
        Canonicalized XML string (C14N format)
        
    Example:
        >>> assertion = etree.Element("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        >>> canonical = _canonicalize_assertion(assertion)
        >>> assert isinstance(canonical, str)
    """
    logger.debug("Canonicalizing SAML assertion")
    canonical = etree.tostring(assertion, method="c14n").decode("utf-8")
    logger.debug("SAML canonicalization complete")
    return canonical


class SAMLProgrammaticGenerator:
    """Programmatically generate SAML 2.0 assertions.
    
    This class provides methods to generate SAML 2.0 assertions programmatically
    using lxml, without requiring XML templates. Supports custom attributes,
    configurable validity periods, and integration with certificate management.
    
    Attributes:
        cert_bundle: Optional certificate bundle for automatic issuer extraction
        
    Example:
        >>> generator = SAMLProgrammaticGenerator()
        >>> assertion = generator.generate(
        ...     subject="user@example.com",
        ...     issuer="https://idp.example.com",
        ...     audience="https://sp.example.com"
        ... )
        >>> assert assertion.generation_method == SAMLGenerationMethod.PROGRAMMATIC
    """
    
    def __init__(self, cert_bundle: Optional[CertificateBundle] = None) -> None:
        """Initialize SAML programmatic generator.
        
        Args:
            cert_bundle: Optional certificate bundle from certificate_manager
        """
        self.cert_bundle = cert_bundle
        logger.debug(
            f"SAMLProgrammaticGenerator initialized "
            f"(cert_bundle={'provided' if cert_bundle else 'none'})"
        )
    
    def generate(
        self,
        subject: str,
        issuer: str,
        audience: str,
        attributes: Optional[Dict[str, Union[str, List[str]]]] = None,
        validity_minutes: int = 5,
    ) -> SAMLAssertion:
        """Generate SAML 2.0 assertion programmatically.
        
        Creates a complete SAML 2.0 assertion with all required elements
        following the OASIS SAML 2.0 specification. The assertion is
        canonicalized and ready for XML signing.
        
        Args:
            subject: Subject (user) identifier
            issuer: Issuer identifier (URI format recommended)
            audience: Intended audience (endpoint URL or identifier)
            attributes: Optional custom attributes (key-value pairs or key-list pairs)
            validity_minutes: Assertion validity period in minutes (default: 5)
            
        Returns:
            SAMLAssertion dataclass with xml_content ready for signing
            
        Raises:
            ValueError: If required parameters are invalid or empty
            
        Example:
            >>> generator = SAMLProgrammaticGenerator()
            >>> assertion = generator.generate(
            ...     subject="user@example.com",
            ...     issuer="https://idp.example.com",
            ...     audience="https://sp.example.com",
            ...     attributes={"role": "physician"},
            ...     validity_minutes=10
            ... )
            >>> assert assertion.generation_method == SAMLGenerationMethod.PROGRAMMATIC
        """
        logger.info(
            f"Generating programmatic SAML assertion: subject={subject}, "
            f"issuer={issuer}, audience={audience}"
        )
        
        # Validate required parameters
        _validate_required_parameters(subject, issuer, audience)
        
        # Validate validity_minutes
        if not isinstance(validity_minutes, int) or validity_minutes <= 0:
            raise ValueError(
                f"validity_minutes must be a positive integer, got: {validity_minutes!r}"
            )
        
        # Generate assertion ID and timestamps
        assertion_id = generate_assertion_id()
        timestamps = generate_saml_timestamps(validity_minutes)
        
        # Build assertion structure
        assertion_elem = _build_assertion_element(
            assertion_id, timestamps["issue_instant"], issuer
        )
        
        _add_subject_element(assertion_elem, subject, timestamps["not_on_or_after"])
        
        _add_conditions_element(
            assertion_elem,
            timestamps["not_before"],
            timestamps["not_on_or_after"],
            audience,
        )
        
        _add_authn_statement(assertion_elem, timestamps["issue_instant"], assertion_id)
        
        # Add optional attribute statement
        if attributes:
            _add_attribute_statement(assertion_elem, attributes)
        
        # Canonicalize for signing
        xml_content = _canonicalize_assertion(assertion_elem)
        
        # Parse timestamps for dataclass
        issue_instant = datetime.fromisoformat(
            timestamps["issue_instant"].replace("Z", "+00:00")
        )
        not_before = datetime.fromisoformat(
            timestamps["not_before"].replace("Z", "+00:00")
        )
        not_on_or_after = datetime.fromisoformat(
            timestamps["not_on_or_after"].replace("Z", "+00:00")
        )
        
        # Create SAMLAssertion dataclass
        saml_assertion = SAMLAssertion(
            assertion_id=assertion_id,
            issuer=issuer,
            subject=subject,
            audience=audience,
            issue_instant=issue_instant,
            not_before=not_before,
            not_on_or_after=not_on_or_after,
            xml_content=xml_content,
            signature="",  # Signing happens in Story 4.4
            certificate_subject="",
            generation_method=SAMLGenerationMethod.PROGRAMMATIC,
        )
        
        logger.info(
            f"Programmatic SAML assertion generated successfully: ID={assertion_id}"
        )
        return saml_assertion
    
    def generate_with_certificate(
        self,
        subject: str,
        audience: str,
        cert_bundle: Optional[CertificateBundle] = None,
        attributes: Optional[Dict[str, Union[str, List[str]]]] = None,
        validity_minutes: int = 5,
    ) -> SAMLAssertion:
        """Generate SAML assertion with automatic issuer extraction from certificate.
        
        Automatically extracts issuer from certificate subject DN if not provided.
        
        Args:
            subject: Subject (user) identifier
            audience: Intended audience (endpoint URL or identifier)
            cert_bundle: Certificate bundle (uses instance cert_bundle if not provided)
            attributes: Optional custom attributes (key-value pairs)
            validity_minutes: Assertion validity period in minutes (default: 5)
            
        Returns:
            SAMLAssertion dataclass with issuer and certificate_subject populated
            
        Raises:
            ValueError: If no certificate bundle is available
            
        Example:
            >>> from ihe_test_util.saml.certificate_manager import load_certificate
            >>> cert = load_certificate(Path("certs/saml.p12"), password=b"secret")
            >>> generator = SAMLProgrammaticGenerator(cert_bundle=cert)
            >>> assertion = generator.generate_with_certificate(
            ...     subject="user@example.com",
            ...     audience="https://sp.example.com"
            ... )
            >>> # Issuer automatically extracted from certificate
        """
        # Use provided cert_bundle or instance cert_bundle
        active_cert_bundle = cert_bundle or self.cert_bundle
        
        if not active_cert_bundle:
            raise ValueError(
                "No certificate bundle provided. Either pass cert_bundle parameter "
                "or initialize SAMLProgrammaticGenerator with cert_bundle."
            )
        
        logger.info(
            f"Generating SAML assertion with certificate info: "
            f"subject={subject}, cert_subject={active_cert_bundle.info.subject}"
        )
        
        # Extract issuer from certificate subject DN
        issuer = active_cert_bundle.info.subject
        
        # Generate assertion
        assertion = self.generate(
            subject=subject,
            issuer=issuer,
            audience=audience,
            attributes=attributes,
            validity_minutes=validity_minutes,
        )
        
        # Update certificate_subject in assertion
        assertion.certificate_subject = active_cert_bundle.info.subject
        
        logger.info(
            f"SAML assertion generated with certificate issuer: {issuer}"
        )
        return assertion
