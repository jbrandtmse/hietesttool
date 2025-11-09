"""XML template loading and caching.

This module provides the TemplateLoader class for loading XML templates
from files or strings with automatic validation and caching support.
"""

import logging
from pathlib import Path

from ihe_test_util.template_engine.validators import validate_xml
from ihe_test_util.utils.exceptions import MalformedXMLError, TemplateLoadError


logger = logging.getLogger(__name__)


class TemplateLoader:
    """Loads and caches XML templates for personalization.

    This class provides methods to load XML templates from files or strings,
    with automatic validation and caching for batch processing efficiency.

    Attributes:
        _cache: Dictionary mapping file paths to cached template content
    """

    def __init__(self) -> None:
        """Initialize template loader with empty cache."""
        self._cache: dict[str, str] = {}
        logger.debug("TemplateLoader initialized")

    def load_from_file(self, file_path: Path) -> str:
        """Load XML template from file.

        Args:
            file_path: Path to XML template file

        Returns:
            Template content as UTF-8 string

        Raises:
            TemplateLoadError: If file cannot be read or has encoding issues
            MalformedXMLError: If XML is not well-formed
        """
        # Check cache first
        cache_key = str(file_path.resolve())
        if cache_key in self._cache:
            logger.debug(f"Cache hit for template: {file_path}")
            return self._cache[cache_key]

        # Load from file
        try:
            logger.info(f"Loading template from file: {file_path}")

            if not file_path.exists():
                raise TemplateLoadError(
                    f"Template file not found: {file_path}. "
                    f"Check that the file path is correct and the file exists."
                )

            content = file_path.read_text(encoding="utf-8")

            # Validate XML
            validate_xml(content)  # Raises MalformedXMLError if invalid

        except FileNotFoundError as e:
            error_msg = (
                f"Template file not found: {file_path}. "
                f"Check that the file path is correct and the file exists."
            )
            logger.exception(error_msg)
            raise TemplateLoadError(error_msg) from e
        except PermissionError as e:
            error_msg = (
                f"Permission denied reading template file: {file_path}. "
                f"Check file permissions."
            )
            logger.exception(error_msg)
            raise TemplateLoadError(error_msg) from e
        except UnicodeDecodeError as e:
            error_msg = (
                f"Template encoding error in {file_path}: {e}. "
                f"Ensure file is UTF-8 encoded or convert it using a text editor."
            )
            logger.exception(error_msg)
            raise TemplateLoadError(error_msg) from e
        except MalformedXMLError:
            # Re-raise MalformedXMLError as-is (already has good error message)
            raise
        else:
            # Cache the template
            self._cache[cache_key] = content
            logger.debug(f"Template cached: {file_path}")
            return content

    def load_from_string(self, template_str: str) -> str:
        """Load XML template from string.

        Args:
            template_str: XML template content as string

        Returns:
            Template content (same as input after validation)

        Raises:
            MalformedXMLError: If XML is not well-formed
        """
        logger.info("Loading template from string")

        # Validate XML
        validate_xml(template_str)  # Raises MalformedXMLError if invalid

        logger.debug("Template string validated successfully")
        return template_str

    def get_cached_template(self, file_path: Path) -> str | None:
        """Get cached template if available.

        Args:
            file_path: Path to template file

        Returns:
            Cached template content if available, None otherwise
        """
        cache_key = str(file_path.resolve())
        cached = self._cache.get(cache_key)

        if cached:
            logger.debug(f"Retrieved cached template: {file_path}")
        else:
            logger.debug(f"No cached template for: {file_path}")

        return cached

    def clear_cache(self) -> None:
        """Clear all cached templates.

        This is useful for freeing memory after batch processing
        or when templates may have been modified.
        """
        cache_size = len(self._cache)
        logger.info(f"Clearing template cache ({cache_size} entries)")
        self._cache.clear()
        logger.debug("Template cache cleared")

    @property
    def cache_size(self) -> int:
        """Get the number of templates currently cached.

        Returns:
            Number of cached templates
        """
        return len(self._cache)
