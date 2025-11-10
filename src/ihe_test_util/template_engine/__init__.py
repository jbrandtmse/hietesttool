"""Template Engine module.

This module provides CCD template processing and personalization functionality.
"""

from ihe_test_util.template_engine.ccd_personalizer import CCDPersonalizer
from ihe_test_util.template_engine.loader import TemplateLoader
from ihe_test_util.template_engine.personalizer import (
    MissingValueStrategy,
    TemplatePersonalizer,
    escape_xml_value,
    format_date_value,
    validate_oid,
)
from ihe_test_util.template_engine.validators import (
    REQUIRED_CCD_FIELDS,
    extract_placeholders,
    validate_ccd_placeholders,
    validate_xml,
)


__all__ = [
    "CCDPersonalizer",
    "MissingValueStrategy",
    "REQUIRED_CCD_FIELDS",
    "TemplateLoader",
    "TemplatePersonalizer",
    "escape_xml_value",
    "extract_placeholders",
    "format_date_value",
    "validate_ccd_placeholders",
    "validate_oid",
    "validate_xml",
]
