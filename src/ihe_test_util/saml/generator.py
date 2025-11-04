"""SAML 2.0 assertion generation module.

This module provides functionality for generating SAML 2.0 assertions
with proper namespace handling and required elements.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from lxml import etree

logger = logging.getLogger(__name__)

# SAML 2.0 Namespaces
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"

NSMAP = {
    "saml": SAML_NS,
    "samlp": SAMLP_NS,
}


def generate_saml_assertion(
    issuer: str,
    subject: str,
    not_before: Optional[datetime] = None,
    not_on_or_after: Optional[datetime] = None,
    assertion_id: Optional[str] = None,
) -> etree._Element:
    """Generate a minimal SAML 2.0 assertion.

    Args:
        issuer: Entity issuing the assertion (e.g., organization identifier)
        subject: Subject of the assertion (e.g., user/patient identifier)
        not_before: Start of validity period (defaults to now)
        not_on_or_after: End of validity period (defaults to now + 5 minutes)
        assertion_id: Unique assertion ID (auto-generated if not provided)

    Returns:
        lxml Element representing the SAML assertion

    Raises:
        ValueError: If issuer or subject is empty
    """
    if not issuer:
        raise ValueError("Issuer cannot be empty")
    if not subject:
        raise ValueError("Subject cannot be empty")

    # Set default times
    if not_before is None:
        not_before = datetime.utcnow()
    if not_on_or_after is None:
        not_on_or_after = not_before + timedelta(minutes=5)

    # Generate unique ID if not provided
    if assertion_id is None:
        assertion_id = f"_{uuid4()}"

    logger.info(f"Generating SAML assertion for subject: {subject}")

    # Create assertion root element
    assertion = etree.Element(
        f"{{{SAML_NS}}}Assertion",
        nsmap=NSMAP,
        ID=assertion_id,
        Version="2.0",
        IssueInstant=not_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # Add Issuer element
    issuer_elem = etree.SubElement(assertion, f"{{{SAML_NS}}}Issuer")
    issuer_elem.text = issuer

    # Add Subject element
    subject_elem = etree.SubElement(assertion, f"{{{SAML_NS}}}Subject")
    name_id = etree.SubElement(subject_elem, f"{{{SAML_NS}}}NameID")
    name_id.text = subject

    # Add Conditions element
    conditions = etree.SubElement(
        assertion,
        f"{{{SAML_NS}}}Conditions",
        NotBefore=not_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
        NotOnOrAfter=not_on_or_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # Add AuthnStatement element
    authn_statement = etree.SubElement(
        assertion,
        f"{{{SAML_NS}}}AuthnStatement",
        AuthnInstant=not_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    authn_context = etree.SubElement(
        authn_statement, f"{{{SAML_NS}}}AuthnContext"
    )
    authn_context_class_ref = etree.SubElement(
        authn_context, f"{{{SAML_NS}}}AuthnContextClassRef"
    )
    authn_context_class_ref.text = (
        "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified"
    )

    logger.debug(f"Generated SAML assertion with ID: {assertion_id}")
    return assertion
