"""SAML template loading and personalization.

This module provides functionality for loading, validating, and personalizing
SAML 2.0 assertion templates with runtime values. It supports automatic
timestamp generation, unique assertion ID creation, and certificate-based
issuer extraction.
"""

import logging
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from lxml import etree

from ihe_test_util.models.saml import CertificateBundle
from ihe_test_util.utils.exceptions import (
    MalformedXMLError,
    MissingPlaceholderValueError,
    TemplateLoadError,
)

logger = logging.getLogger(__name__)

# SAML 2.0 namespace
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"

# Required SAML 2.0 elements
REQUIRED_SAML_ELEMENTS = ["Assertion", "Issuer", "Subject"]


class ValidationResult:
    """Result of SAML template validation.
    
    Attributes:
        is_valid: True if template passes all validation checks
        errors: List of validation errors (blocking issues)
        warnings: List of validation warnings (non-blocking concerns)
    """
    
    def __init__(self, is_valid: bool, errors: list[str], warnings: list[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings


def load_saml_template(template_path: Path) -> str:
    """Load SAML assertion template from file.
    
    Validates that the template is well-formed XML and contains
    required SAML 2.0 structure elements.
    
    Args:
        template_path: Path to SAML template XML file
        
    Returns:
        Template XML content as string
        
    Raises:
        FileNotFoundError: If template file does not exist
        TemplateLoadError: If template is invalid or malformed
        MalformedXMLError: If XML is not well-formed
        
    Example:
        >>> template = load_saml_template(Path("templates/saml-template.xml"))
        >>> assert "{{assertion_id}}" in template
    """
    try:
        logger.info(f"Loading SAML template from file: {template_path}")
        
        if not template_path.exists():
            raise TemplateLoadError(
                f"SAML template file not found: {template_path}. "
                f"Check that the file path is correct and the file exists."
            )
        
        content = template_path.read_text(encoding="utf-8")
        
        # Validate XML well-formedness
        try:
            etree.fromstring(content.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            error_msg = (
                f"Malformed XML in SAML template at line {e.lineno}: {e.msg}. "
                f"Check for unclosed tags or invalid characters."
            )
            logger.exception(error_msg)
            raise MalformedXMLError(error_msg) from e
        
        logger.debug(f"SAML template loaded successfully: {template_path}")
        return content
        
    except FileNotFoundError as e:
        error_msg = (
            f"SAML template file not found: {template_path}. "
            f"Check that the file path is correct and the file exists."
        )
        logger.exception(error_msg)
        raise TemplateLoadError(error_msg) from e
    except PermissionError as e:
        error_msg = (
            f"Permission denied reading SAML template file: {template_path}. "
            f"Check file permissions."
        )
        logger.exception(error_msg)
        raise TemplateLoadError(error_msg) from e
    except UnicodeDecodeError as e:
        error_msg = (
            f"Template encoding error in {template_path}: {e}. "
            f"Ensure file is UTF-8 encoded or convert it using a text editor."
        )
        logger.exception(error_msg)
        raise TemplateLoadError(error_msg) from e


def validate_saml_template(template_xml: str) -> ValidationResult:
    """Validate SAML template structure and content.
    
    Checks for required SAML 2.0 namespace and elements.
    
    Args:
        template_xml: SAML template XML string
        
    Returns:
        ValidationResult with validation status and messages
        
    Example:
        >>> result = validate_saml_template(template_xml)
        >>> if not result.is_valid:
        ...     print(f"Errors: {result.errors}")
    """
    errors = []
    warnings = []
    
    try:
        # Parse XML
        root = etree.fromstring(template_xml.encode("utf-8"))
        
        # Check for SAML 2.0 namespace
        nsmap = root.nsmap
        saml_ns_found = False
        for prefix, uri in nsmap.items():
            if uri == SAML_NS:
                saml_ns_found = True
                break
        
        if not saml_ns_found:
            errors.append(
                f"Missing SAML 2.0 namespace: {SAML_NS}. "
                f"Add xmlns:saml=\"{SAML_NS}\" to the Assertion element."
            )
        
        # Check for required elements
        for element_name in REQUIRED_SAML_ELEMENTS:
            # Check if root is the element or find it in descendants
            element_found = False
            
            # Check root tag
            if isinstance(root.tag, str) and root.tag.endswith(f"}}{element_name}"):
                element_found = True
            else:
                # Search descendants
                for elem in root.iter():
                    if isinstance(elem.tag, str) and elem.tag.endswith(f"}}{element_name}"):
                        element_found = True
                        break
            
            if not element_found:
                errors.append(
                    f"Missing required SAML element: <saml:{element_name}>. "
                    f"This element is required for valid SAML 2.0 assertions."
                )
        
        # Check for valid placeholder syntax
        placeholders = extract_saml_placeholders(template_xml)
        if not placeholders:
            warnings.append(
                "No placeholders found in template. "
                "Template may be static or use a different placeholder format."
            )
        
        # Log validation results
        if errors:
            logger.warning(f"SAML template validation failed with {len(errors)} errors")
        elif warnings:
            logger.info(f"SAML template validation passed with {len(warnings)} warnings")
        else:
            logger.debug("SAML template validation passed")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)
        
    except etree.XMLSyntaxError as e:
        errors.append(f"XML syntax error at line {e.lineno}: {e.msg}")
        return ValidationResult(False, errors, warnings)


def extract_saml_placeholders(template_xml: str) -> set[str]:
    """Extract all placeholder names from SAML template.
    
    Placeholders use the pattern {{placeholder_name}}.
    
    Args:
        template_xml: SAML template XML string
        
    Returns:
        Set of unique placeholder names (without {{ }} delimiters)
        
    Example:
        >>> placeholders = extract_saml_placeholders(template_xml)
        >>> assert "assertion_id" in placeholders
        >>> assert "issuer" in placeholders
    """
    pattern = r"\{\{(\w+)\}\}"
    matches = re.findall(pattern, template_xml)
    placeholders = set(matches)
    
    logger.debug(f"Extracted {len(placeholders)} unique placeholders from SAML template")
    if placeholders:
        logger.debug(f"Placeholders: {sorted(placeholders)}")
    
    return placeholders


def generate_saml_timestamps(validity_minutes: int = 5) -> dict[str, str]:
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
    from datetime import timezone
    
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


def personalize_saml_template(
    template_path: Path,
    parameters: dict[str, str],
    validity_minutes: int = 5
) -> str:
    """Personalize SAML template by replacing placeholders with values.
    
    Automatically generates assertion_id and timestamps if not provided.
    Validates template structure and checks for missing required parameters.
    
    Args:
        template_path: Path to SAML template XML file
        parameters: Dictionary mapping placeholder names to values
        validity_minutes: Assertion validity period in minutes (default: 5)
        
    Returns:
        Personalized SAML assertion XML string
        
    Raises:
        TemplateLoadError: If template cannot be loaded
        MalformedXMLError: If template XML is invalid
        MissingPlaceholderValueError: If required placeholders are missing values
        
    Example:
        >>> params = {"issuer": "https://idp.example.com", "subject": "user@example.com"}
        >>> saml_xml = personalize_saml_template(Path("templates/saml-template.xml"), params)
        >>> assert "https://idp.example.com" in saml_xml
    """
    logger.info(f"Personalizing SAML template: {template_path}")
    
    # Load template
    template_xml = load_saml_template(template_path)
    
    # Validate template
    validation = validate_saml_template(template_xml)
    if not validation.is_valid:
        error_msg = f"Invalid SAML template: {'; '.join(validation.errors)}"
        logger.error(error_msg)
        raise TemplateLoadError(error_msg)
    
    # Log warnings
    for warning in validation.warnings:
        logger.warning(f"SAML template warning: {warning}")
    
    # Extract placeholders
    placeholders = extract_saml_placeholders(template_xml)
    
    # Auto-generate assertion_id if not provided
    if "assertion_id" in placeholders and "assertion_id" not in parameters:
        parameters["assertion_id"] = generate_assertion_id()
        logger.debug("Auto-generated assertion_id")
    
    # Auto-generate timestamps if not provided
    timestamp_fields = {"issue_instant", "not_before", "not_on_or_after"}
    missing_timestamps = timestamp_fields & placeholders - parameters.keys()
    if missing_timestamps:
        timestamps = generate_saml_timestamps(validity_minutes)
        for field in missing_timestamps:
            if field in timestamps:
                parameters[field] = timestamps[field]
        logger.debug(f"Auto-generated timestamps: {missing_timestamps}")
    
    # Check for missing required parameters (after auto-generation)
    missing = placeholders - parameters.keys()
    if missing:
        missing_list = sorted(missing)
        raise MissingPlaceholderValueError(
            f"Missing required placeholder values: {missing_list}. "
            f"Provide these values in the parameters dictionary."
        )
    
    # Replace placeholders
    result = template_xml
    for placeholder, value in parameters.items():
        result = result.replace(f"{{{{{placeholder}}}}}", value)
    
    logger.info("SAML template personalization complete")
    return result


def canonicalize_saml(saml_xml: str) -> str:
    """Canonicalize SAML assertion for signing.
    
    Uses C14N (Canonical XML) algorithm to normalize XML for digital signatures.
    
    Args:
        saml_xml: SAML assertion XML string
        
    Returns:
        Canonicalized XML string (C14N format)
        
    Raises:
        MalformedXMLError: If XML is malformed
        
    Example:
        >>> canonical = canonicalize_saml(saml_xml)
        >>> # Canonical XML is ready for signing
    """
    try:
        logger.debug("Canonicalizing SAML assertion")
        tree = etree.fromstring(saml_xml.encode("utf-8"))
        canonical = etree.tostring(tree, method="c14n").decode("utf-8")
        logger.debug("SAML canonicalization complete")
        return canonical
    except etree.XMLSyntaxError as e:
        error_msg = f"Cannot canonicalize malformed XML at line {e.lineno}: {e.msg}"
        logger.exception(error_msg)
        raise MalformedXMLError(error_msg) from e


class SAMLTemplatePersonalizer:
    """Personalizes SAML assertion templates with caching support.
    
    This class provides methods to load, validate, and personalize SAML templates
    with automatic template caching for improved performance in batch operations.
    
    Attributes:
        _cache: Dictionary mapping template paths to cached content
        _cache_enabled: Whether template caching is enabled
        
    Example:
        >>> personalizer = SAMLTemplatePersonalizer()
        >>> params = {"issuer": "https://idp.example.com", "subject": "user"}
        >>> saml_xml = personalizer.personalize(Path("templates/saml-template.xml"), params)
    """
    
    def __init__(self, template_cache_enabled: bool = True):
        """Initialize SAML template personalizer.
        
        Args:
            template_cache_enabled: Enable template caching for performance
        """
        self._cache: dict[str, str] = {}
        self._cache_enabled = template_cache_enabled
        logger.debug(f"SAMLTemplatePersonalizer initialized (cache_enabled={template_cache_enabled})")
    
    def load_template(self, template_path: Path) -> str:
        """Load SAML template from file with optional caching.
        
        Args:
            template_path: Path to SAML template XML file
            
        Returns:
            Template XML content as string
            
        Raises:
            TemplateLoadError: If template cannot be loaded
        """
        cache_key = str(template_path.resolve())
        
        # Check cache
        if self._cache_enabled and cache_key in self._cache:
            logger.debug(f"Cache hit for SAML template: {template_path}")
            return self._cache[cache_key]
        
        # Load from file
        template_xml = load_saml_template(template_path)
        
        # Cache if enabled
        if self._cache_enabled:
            self._cache[cache_key] = template_xml
            logger.debug(f"SAML template cached: {template_path}")
        
        return template_xml
    
    def personalize(
        self,
        template_path: Path,
        parameters: dict[str, str],
        validity_minutes: int = 5
    ) -> str:
        """Personalize SAML template with parameters.
        
        Args:
            template_path: Path to SAML template XML file
            parameters: Dictionary mapping placeholder names to values
            validity_minutes: Assertion validity period in minutes
            
        Returns:
            Personalized SAML assertion XML string
            
        Raises:
            TemplateLoadError: If template cannot be loaded or is invalid
            MissingPlaceholderValueError: If required parameters are missing
        """
        logger.info(f"Personalizing SAML template: {template_path}")
        
        # Load template (with caching support)
        template_xml = self.load_template(template_path)
        
        # Validate template
        validation = validate_saml_template(template_xml)
        if not validation.is_valid:
            error_msg = f"Invalid SAML template: {'; '.join(validation.errors)}"
            logger.error(error_msg)
            raise TemplateLoadError(error_msg)
        
        # Log warnings
        for warning in validation.warnings:
            logger.warning(f"SAML template warning: {warning}")
        
        # Extract placeholders
        placeholders = extract_saml_placeholders(template_xml)
        
        # Auto-generate assertion_id if not provided
        if "assertion_id" in placeholders and "assertion_id" not in parameters:
            parameters["assertion_id"] = generate_assertion_id()
            logger.debug("Auto-generated assertion_id")
        
        # Auto-generate timestamps if not provided
        timestamp_fields = {"issue_instant", "not_before", "not_on_or_after"}
        missing_timestamps = timestamp_fields & placeholders - parameters.keys()
        if missing_timestamps:
            timestamps = generate_saml_timestamps(validity_minutes)
            for field in missing_timestamps:
                if field in timestamps:
                    parameters[field] = timestamps[field]
            logger.debug(f"Auto-generated timestamps: {missing_timestamps}")
        
        # Check for missing required parameters (after auto-generation)
        missing = placeholders - parameters.keys()
        if missing:
            missing_list = sorted(missing)
            raise MissingPlaceholderValueError(
                f"Missing required placeholder values: {missing_list}. "
                f"Provide these values in the parameters dictionary."
            )
        
        # Replace placeholders
        result = template_xml
        for placeholder, value in parameters.items():
            result = result.replace(f"{{{{{placeholder}}}}}", value)
        
        logger.info("SAML template personalization complete")
        return result
    
    def personalize_with_certificate_info(
        self,
        template_path: Path,
        cert_bundle: CertificateBundle,
        parameters: dict[str, str],
        validity_minutes: int = 5
    ) -> str:
        """Personalize SAML template with certificate issuer information.
        
        Automatically extracts issuer from certificate subject DN if not provided.
        
        Args:
            template_path: Path to SAML template XML file
            cert_bundle: Certificate bundle from certificate_manager
            parameters: Dictionary mapping placeholder names to values
            validity_minutes: Assertion validity period in minutes
            
        Returns:
            Personalized SAML assertion XML string
            
        Example:
            >>> from ihe_test_util.saml.certificate_manager import load_certificate
            >>> cert = load_certificate(Path("certs/saml.p12"), password=b"secret")
            >>> params = {"subject": "user@example.com", "audience": "https://sp.example.com"}
            >>> saml = personalizer.personalize_with_certificate_info(
            ...     Path("templates/saml-template.xml"), cert, params
            ... )
        """
        logger.info("Personalizing SAML template with certificate info")
        
        # Extract issuer from certificate if not provided
        if "issuer" not in parameters:
            parameters["issuer"] = cert_bundle.info.subject
            logger.debug(f"Extracted issuer from certificate: {cert_bundle.info.subject}")
        
        # Add certificate subject for reference
        if "certificate_subject" not in parameters:
            parameters["certificate_subject"] = cert_bundle.info.subject
        
        return self.personalize(template_path, parameters, validity_minutes)
    
    def clear_cache(self) -> None:
        """Clear all cached templates.
        
        Useful for freeing memory after batch processing or when templates
        may have been modified.
        """
        cache_size = len(self._cache)
        logger.info(f"Clearing SAML template cache ({cache_size} entries)")
        self._cache.clear()
    
    @property
    def cache_size(self) -> int:
        """Get the number of templates currently cached.
        
        Returns:
            Number of cached templates
        """
        return len(self._cache)
