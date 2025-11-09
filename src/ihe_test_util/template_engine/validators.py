"""XML template validation functions.

This module provides validation functions for XML templates including:
- XML well-formedness checking
- Placeholder extraction
- CCD-specific placeholder validation
"""

import logging
import re

from lxml import etree

from ihe_test_util.utils.exceptions import MalformedXMLError


logger = logging.getLogger(__name__)

# Required placeholders for CCD templates
REQUIRED_CCD_FIELDS = {
    "patient_id",
    "patient_id_oid",
    "first_name",
    "last_name",
    "dob",
    "gender",
}


def validate_xml(xml_content: str) -> bool:
    """Validate that XML content is well-formed.

    Args:
        xml_content: XML string to validate

    Returns:
        True if XML is well-formed

    Raises:
        MalformedXMLError: If XML syntax is invalid, includes line number and description
    """
    try:
        etree.fromstring(xml_content.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        error_msg = (
            f"Malformed XML at line {e.lineno}: {e.msg}. "
            f"Check for unclosed tags or invalid characters."
        )
        logger.exception(error_msg)
        raise MalformedXMLError(error_msg) from e
    else:
        logger.debug("XML validation passed")
        return True


def extract_placeholders(xml_content: str) -> set[str]:
    """Extract all placeholders from XML template.

    Placeholders are identified by the pattern {{field_name}}.

    Args:
        xml_content: XML template content

    Returns:
        Set of unique placeholder names (without {{ }} delimiters)
    """
    pattern = r"\{\{(\w+)\}\}"
    matches = re.findall(pattern, xml_content)
    placeholders = set(matches)
    logger.info(f"Extracted {len(placeholders)} unique placeholders")
    if placeholders:
        logger.debug(f"Placeholders found: {sorted(placeholders)}")
    return placeholders


def validate_ccd_placeholders(placeholders: set[str]) -> tuple[bool, list[str]]:
    """Validate that CCD template contains all required placeholders.

    Args:
        placeholders: Set of placeholder names found in template

    Returns:
        Tuple of (is_valid, missing_fields) where:
            - is_valid: True if all required fields are present
            - missing_fields: Sorted list of missing required field names
    """
    missing = REQUIRED_CCD_FIELDS - placeholders
    is_valid = len(missing) == 0

    if not is_valid:
        logger.warning(
            f"Missing required CCD fields: {sorted(missing)}. "
            f"Required fields are: {sorted(REQUIRED_CCD_FIELDS)}"
        )
    else:
        logger.debug("All required CCD placeholders are present")

    return is_valid, sorted(missing)
