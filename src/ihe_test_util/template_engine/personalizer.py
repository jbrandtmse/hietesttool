"""Template personalization engine for replacing placeholders with values.

This module provides functionality to personalize XML templates by replacing
{{field_name}} placeholders with actual values from patient demographics or
other data sources.
"""

import re
from datetime import date, datetime
from enum import Enum
from html import escape as html_escape
from typing import Any, Optional
import logging

from ihe_test_util.utils.exceptions import (
    MissingPlaceholderValueError,
    MaxNestingDepthError,
    InvalidOIDFormatError,
)

logger = logging.getLogger(__name__)


class MissingValueStrategy(Enum):
    """Strategy for handling missing placeholder values."""

    ERROR = "error"  # Raise exception
    USE_DEFAULT = "default"  # Use default value map
    USE_EMPTY = "empty"  # Use empty string


class TemplatePersonalizer:
    """Personalizes XML templates by replacing placeholders with values.

    This class provides efficient string replacement for batch processing,
    with support for nested placeholders, XML escaping, date formatting,
    and configurable missing value handling.

    Example:
        >>> personalizer = TemplatePersonalizer()
        >>> template = "<name>{{first_name}} {{last_name}}</name>"
        >>> values = {"first_name": "John", "last_name": "Doe"}
        >>> result = personalizer.personalize(template, values)
        >>> print(result)
        <name>John Doe</name>
    """

    # Class-level compiled regex for performance (reused across all instances)
    PLACEHOLDER_PATTERN = re.compile(r"{{(\w+)}}")

    def __init__(
        self,
        date_format: str = "HL7",
        missing_value_strategy: MissingValueStrategy = MissingValueStrategy.ERROR,
        default_value_map: Optional[dict[str, str]] = None,
        max_nesting_depth: int = 3,
    ):
        """Initialize template personalizer.

        Args:
            date_format: Date format to use. Options:
                - "HL7": YYYYMMDD for dates, YYYYMMDDHHMMSS for datetimes
                - "ISO": ISO 8601 format (YYYY-MM-DD)
                - Custom strftime format string
            missing_value_strategy: How to handle missing values.
            default_value_map: Default values for missing fields.
            max_nesting_depth: Maximum nesting depth for nested placeholders.
        """
        self.date_format = date_format
        self.missing_value_strategy = missing_value_strategy
        self.default_value_map = default_value_map or {}
        self.max_nesting_depth = max_nesting_depth
        logger.debug(
            f"TemplatePersonalizer initialized with format={date_format}, "
            f"strategy={missing_value_strategy.value}"
        )

    def personalize(self, template: str, values: dict[str, Any]) -> str:
        """Personalize template by replacing placeholders with values.

        Args:
            template: XML template with {{field_name}} placeholders.
            values: Dictionary mapping field names to values.

        Returns:
            Personalized XML string with all placeholders replaced.

        Raises:
            MissingPlaceholderValueError: If required value missing and
                strategy is ERROR.
            MaxNestingDepthError: If nesting depth exceeded.
        """
        logger.info(
            f"Personalizing template ({len(template)} chars, {len(values)} values)"
        )

        # Extract placeholders from template
        placeholders = self._extract_placeholders(template)
        logger.debug(f"Found {len(placeholders)} unique placeholders: {placeholders}")

        # Check for missing values
        missing = placeholders - values.keys()
        if missing:
            self._handle_missing_values(missing, values)

        # Perform replacement with nesting support
        result = self._replace_placeholders(template, values, depth=0)

        logger.info("Template personalization complete")
        return result

    def _extract_placeholders(self, template: str) -> set[str]:
        """Extract all placeholder names from template.

        Args:
            template: Template string with placeholders.

        Returns:
            Set of placeholder field names.
        """
        matches = self.PLACEHOLDER_PATTERN.findall(template)
        return set(matches)

    def _handle_missing_values(
        self, missing: set[str], values: dict[str, Any]
    ) -> None:
        """Handle missing placeholder values based on strategy.

        Args:
            missing: Set of missing placeholder names.
            values: Values dictionary (modified in place for defaults).

        Raises:
            MissingPlaceholderValueError: If strategy is ERROR.
        """
        if self.missing_value_strategy == MissingValueStrategy.ERROR:
            missing_list = sorted(missing)
            raise MissingPlaceholderValueError(
                f"Missing required placeholder values: {missing_list}. "
                f"Ensure all required fields are provided in the values dictionary."
            )
        elif self.missing_value_strategy == MissingValueStrategy.USE_DEFAULT:
            for field in missing:
                if field in self.default_value_map:
                    values[field] = self.default_value_map[field]
                    logger.debug(f"Using default value for {field}")
                else:
                    values[field] = ""
                    logger.warning(
                        f"No default value for {field}, using empty string"
                    )
        elif self.missing_value_strategy == MissingValueStrategy.USE_EMPTY:
            for field in missing:
                values[field] = ""
                logger.debug(f"Using empty string for missing field: {field}")

    def _replace_placeholders(
        self, text: str, values: dict[str, Any], depth: int
    ) -> str:
        """Replace placeholders with values, supporting nesting.

        Args:
            text: Text containing placeholders.
            values: Dictionary of values.
            depth: Current nesting depth.

        Returns:
            Text with placeholders replaced.

        Raises:
            MaxNestingDepthError: If max depth exceeded.
        """
        if depth > self.max_nesting_depth:
            raise MaxNestingDepthError(
                f"Maximum nesting depth ({self.max_nesting_depth}) exceeded. "
                f"Check for circular placeholder references."
            )

        def replacer(match):
            field_name = match.group(1)
            value = values.get(field_name)

            # Format value based on type
            formatted_value = self._format_value(value, field_name)

            # Check if formatted value contains placeholders (nesting)
            if "{{" in formatted_value:
                return self._replace_placeholders(formatted_value, values, depth + 1)

            return formatted_value

        return self.PLACEHOLDER_PATTERN.sub(replacer, text)

    def _format_value(self, value: Any, field_name: str) -> str:
        """Format value based on type.

        Args:
            value: Value to format.
            field_name: Name of the field (for logging).

        Returns:
            Formatted string value.
        """
        if value is None:
            return ""

        # Date/datetime formatting
        if isinstance(value, (date, datetime)):
            return self._format_date(value)

        # OID validation for fields ending in _oid
        if field_name.endswith("_oid"):
            value_str = str(value)
            if not validate_oid(value_str):
                logger.warning(
                    f"Field {field_name} has invalid OID format: {value_str}"
                )
            return value_str  # Return without XML escaping (OIDs don't need it)

        # String values: XML escape
        value_str = str(value)
        return escape_xml_value(value_str)

    def _format_date(self, value: date | datetime) -> str:
        """Format date/datetime based on configured format.

        Args:
            value: Date or datetime to format.

        Returns:
            Formatted date string.
        """
        if self.date_format == "HL7":
            if isinstance(value, datetime):
                return value.strftime("%Y%m%d%H%M%S")
            return value.strftime("%Y%m%d")
        elif self.date_format == "ISO":
            if isinstance(value, datetime):
                return value.isoformat()
            return value.isoformat()
        else:
            # Custom strftime format
            return value.strftime(self.date_format)


def escape_xml_value(value: str) -> str:
    """Escape XML special characters in value.

    Escapes the following characters:
    - & → &amp;
    - < → &lt;
    - > → &gt;
    - " → &quot;
    - ' → &apos;

    Args:
        value: String value to escape.

    Returns:
        XML-safe string with special characters escaped.

    Example:
        >>> escape_xml_value("Fish & Chips")
        'Fish &amp; Chips'
        >>> escape_xml_value("<tag>")
        '&lt;tag&gt;'
    """
    # html.escape handles &, <, >, and " (with quote=True)
    escaped = html_escape(value, quote=True)
    # Convert numeric entity to named entity for single quotes
    # html.escape with quote=True converts ' to &#x27;, but XML prefers &apos;
    escaped = escaped.replace("&#x27;", "&apos;")
    return escaped


def format_date_value(value: date | datetime, format_type: str = "HL7") -> str:
    """Format date value for XML insertion.

    Args:
        value: Date or datetime to format.
        format_type: Format type. Options:
            - "HL7": YYYYMMDD for dates, YYYYMMDDHHMMSS for datetimes
            - "ISO": ISO 8601 format
            - Custom strftime format string

    Returns:
        Formatted date string.

    Example:
        >>> from datetime import date
        >>> format_date_value(date(1980, 1, 15), "HL7")
        '19800115'
        >>> format_date_value(date(1980, 1, 15), "ISO")
        '1980-01-15'
    """
    if format_type == "HL7":
        if isinstance(value, datetime):
            return value.strftime("%Y%m%d%H%M%S")
        return value.strftime("%Y%m%d")
    elif format_type == "ISO":
        if isinstance(value, datetime):
            return value.isoformat()
        return value.isoformat()
    else:
        return value.strftime(format_type)


def validate_oid(oid: str) -> bool:
    """Validate OID format.

    OIDs must consist of numeric components separated by dots.
    Format: digit+ ("." digit+)*

    Args:
        oid: OID string to validate.

    Returns:
        True if valid OID format, False otherwise.

    Example:
        >>> validate_oid("1.2.3.4.5")
        True
        >>> validate_oid("1.2.abc.4")
        False
        >>> validate_oid("1.2.3.")
        False
    """
    if not oid:
        return False

    # OID pattern: must start with digit, contain only digits and dots,
    # and not end with a dot
    pattern = re.compile(r"^\d+(\.\d+)*$")
    return bool(pattern.match(oid))
