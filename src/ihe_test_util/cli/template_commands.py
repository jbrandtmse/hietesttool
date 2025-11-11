"""Template validation and processing CLI commands.

This module provides Click commands for validating CCD templates and generating
personalized CCDs from CSV patient data.

Commands:
    template validate <file> - Validate template structure and placeholders
    template process <template> <csv> - Generate personalized CCDs from CSV
"""

import logging
from pathlib import Path

import click

from ihe_test_util.csv_parser.parser import parse_csv
from ihe_test_util.template_engine.ccd_personalizer import CCDPersonalizer
from ihe_test_util.template_engine.loader import TemplateLoader
from ihe_test_util.template_engine.validators import (
    extract_placeholders,
    validate_ccd_placeholders,
    validate_xml,
)
from ihe_test_util.utils.exceptions import (
    CCDPersonalizationError,
    TemplateError,
    ValidationError,
)


logger = logging.getLogger(__name__)


@click.group(name="template")
def template_group() -> None:
    """Template validation and processing commands.
    
    Use these commands to validate CCD templates and generate personalized
    clinical documents from patient CSV data.
    """


@template_group.command(name="validate")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
def validate_command(file: Path) -> None:
    """Validate template structure and placeholders.
    
    Checks that the template is well-formed XML and contains all required
    CCD placeholders (patient_id, patient_id_oid, first_name, last_name,
    dob, gender).
    
    Args:
        file: Path to template XML file
        
    Exit Codes:
        0: Template is valid
        1: Template validation failed
        
    Example:
        ihe-test-util template validate templates/ccd-template.xml
    """
    try:
        # Load template
        loader = TemplateLoader()
        template_content = loader.load_from_file(file)
        logger.info(f"Loaded template from {file}")

        # Validate XML
        validate_xml(template_content)
        click.secho("✓ Template is well-formed XML", fg="green")

        # Extract and validate placeholders
        placeholders = extract_placeholders(template_content)
        click.echo(f"\nFound {len(placeholders)} placeholders:")
        for placeholder in sorted(placeholders):
            click.echo(f"  - {placeholder}")

        # Check required CCD fields
        is_valid, missing = validate_ccd_placeholders(placeholders)
        if is_valid:
            click.secho("\n✓ All required CCD placeholders present", fg="green")
            logger.info(f"Template {file} validation successful")
        else:
            click.secho(
                f"\n✗ Missing required placeholders: {', '.join(missing)}", fg="red"
            )
            logger.error(f"Template {file} missing placeholders: {missing}")
            raise click.exceptions.Exit(1)

    except TemplateError as e:
        click.secho(f"✗ Validation failed: {e}", fg="red")
        logger.error(f"Template validation failed for {file}: {e}")
        raise click.exceptions.Exit(1)
    except Exception as e:
        click.secho(f"✗ Unexpected error: {e}", fg="red")
        logger.exception(f"Unexpected error validating template {file}")
        raise click.exceptions.Exit(1)


@template_group.command(name="process")
@click.argument("template", type=click.Path(exists=True, path_type=Path))
@click.argument("csv", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("output"),
    help="Output directory for generated CCDs (default: ./output)",
)
@click.option(
    "--format",
    "-f",
    "filename_format",
    default="{patient_id}.xml",
    help="Output filename format (default: {patient_id}.xml)",
)
@click.option(
    "--validate-output/--no-validate-output",
    default=True,
    help="Validate generated CCDs as well-formed XML (default: enabled)",
)
def process_command(
    template: Path,
    csv: Path,
    output: Path,
    filename_format: str,
    validate_output: bool,
) -> None:
    """Generate personalized CCDs from template and CSV.
    
    Processes each patient row in the CSV file and generates a personalized
    CCD document using the specified template. Displays progress bar and
    generates a summary report.
    
    Args:
        template: Path to CCD template XML file
        csv: Path to patient demographics CSV file
        output: Output directory for generated CCDs
        filename_format: Filename format with placeholders (e.g., {patient_id}.xml)
        validate_output: Whether to validate generated CCDs
        
    Exit Codes:
        0: All patients processed successfully
        1: Complete failure (no patients processed)
        2: Partial failure (some patients succeeded, some failed)
        
    Examples:
        # Basic usage
        ihe-test-util template process templates/ccd-template.xml patients.csv
        
        # Custom output directory and filename format
        ihe-test-util template process templates/ccd-template.xml patients.csv \\
            --output ccds/ --format "{last_name}_{first_name}.xml"
            
        # Disable output validation for faster processing
        ihe-test-util template process templates/ccd-template.xml patients.csv \\
            --no-validate-output
    """
    try:
        # Create output directory
        output.mkdir(parents=True, exist_ok=True)
        click.echo(f"Output directory: {output}")
        logger.info(f"Created output directory: {output}")

        # Validate filename format
        if not _has_valid_placeholder(filename_format):
            click.secho(
                "✗ Invalid filename format. Must contain at least one placeholder "
                "(e.g., {patient_id}, {first_name}, {last_name}, {mrn})",
                fg="red",
            )
            raise click.exceptions.Exit(1)

        # Load CSV
        click.echo(f"Loading CSV: {csv}")
        df, validation_result = parse_csv(csv)

        # Check for validation errors
        if validation_result and validation_result.all_errors:
            error_list = validation_result.all_errors
            error_msg = f"Found {len(error_list)} validation error(s) in CSV:\n"
            for error in error_list:
                error_msg += f"  - Row {error.row_number} [{error.column_name}]: {error.message}\n"
            click.secho(f"✗ CSV validation error: {error_msg.strip()}", fg="red")
            logger.error(f"CSV validation failed: {error_msg.strip()}")
            raise click.exceptions.Exit(1)

        total_patients = len(df)
        click.echo(f"Found {total_patients} patients\n")
        logger.info(f"Loaded {total_patients} patients from {csv}")

        # Initialize personalizer
        personalizer = CCDPersonalizer()

        # Process patients with progress bar
        successful: list[str] = []
        failed: list[tuple[str, str]] = []
        used_filenames: dict[str, int] = {}

        with click.progressbar(
            df.iterrows(),
            length=total_patients,
            label="Processing patients",
            show_eta=True,
            show_pos=True,
        ) as bar:
            for idx, row in bar:
                try:
                    # Personalize CCD
                    ccd = personalizer.personalize_from_dataframe_row(template, row)

                    # Generate output filename
                    filename = format_filename(
                        filename_format, row.to_dict(), used_filenames
                    )
                    output_file = output / filename

                    # Save CCD
                    ccd.to_file(output_file)

                    # Optionally validate
                    if validate_output:
                        validate_xml(ccd.xml_content)

                    successful.append(ccd.patient_id)
                    logger.debug(f"Successfully processed patient {ccd.patient_id}")

                except (CCDPersonalizationError, ValidationError) as e:
                    patient_id = row.get("patient_id", f"row_{idx}")
                    failed.append((patient_id, str(e)))
                    logger.error(f"Failed to process patient {patient_id}: {e}")

                except Exception as e:
                    patient_id = row.get("patient_id", f"row_{idx}")
                    error_msg = f"Unexpected error: {e}"
                    failed.append((patient_id, error_msg))
                    logger.exception(f"Unexpected error processing patient {patient_id}")

        # Display summary
        display_summary(total_patients, len(successful), len(failed), failed)
        logger.info(
            f"Processing complete: {len(successful)} successful, {len(failed)} failed"
        )

        # Return appropriate exit code
        if len(failed) == 0:
            raise click.exceptions.Exit(0)  # All success
        if len(successful) > 0:
            raise click.exceptions.Exit(2)  # Partial failure
        raise click.exceptions.Exit(1)  # Complete failure

    except ValidationError as e:
        click.secho(f"✗ CSV validation error: {e}", fg="red")
        logger.error(f"CSV validation failed: {e}")
        raise click.exceptions.Exit(1)
    except TemplateError as e:
        click.secho(f"✗ Template error: {e}", fg="red")
        logger.error(f"Template processing failed: {e}")
        raise click.exceptions.Exit(1)
    except click.exceptions.Exit:
        # Re-raise Exit exceptions (these are intentional exits)
        raise
    except Exception as e:
        click.secho(f"✗ Unexpected error: {e}", fg="red")
        logger.exception("Unexpected error during template processing")
        raise click.exceptions.Exit(1)


def _has_valid_placeholder(format_string: str) -> bool:
    """Check if format string contains at least one valid placeholder.
    
    Args:
        format_string: Format string to validate
        
    Returns:
        True if format string contains valid placeholders
    """
    valid_placeholders = {
        "{patient_id}",
        "{first_name}",
        "{last_name}",
        "{mrn}",
        "{gender}",
    }
    return any(placeholder in format_string for placeholder in valid_placeholders)


def format_filename(
    format_string: str, patient_data: dict[str, str], used_filenames: dict[str, int]
) -> str:
    """Format output filename using patient data with uniqueness guarantee.
    
    Replaces placeholders in format string with patient data values and
    sanitizes the result for filesystem compatibility. If a filename has
    already been used, appends a counter to ensure uniqueness.
    
    Args:
        format_string: Format with placeholders like {patient_id}
        patient_data: Dictionary of patient demographics
        used_filenames: Dictionary tracking used filenames and their counts
        
    Returns:
        Formatted and sanitized filename string
        
    Example:
        >>> format_filename("{patient_id}.xml", {"patient_id": "PAT-001"}, {})
        'PAT-001.xml'
        >>> format_filename("{last_name}_{first_name}.xml", 
        ...                 {"last_name": "Smith", "first_name": "John"}, {})
        'Smith_John.xml'
    """
    # Convert None values to empty strings for formatting
    safe_data = {k: str(v) if v is not None else "" for k, v in patient_data.items()}

    try:
        # Format with patient data
        filename = format_string.format(**safe_data)
    except KeyError as e:
        # If a placeholder is missing, use a fallback
        patient_id = safe_data.get("patient_id", "unknown")
        filename = f"{patient_id}.xml"
        logger.warning(
            f"Missing placeholder {e} in format string, using fallback: {filename}"
        )

    # Sanitize filename (remove invalid filesystem characters)
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Ensure uniqueness
    if filename in used_filenames:
        used_filenames[filename] += 1
        # Insert counter before file extension
        base, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = f"{base}_{used_filenames[filename]}.{ext}" if ext else f"{base}_{used_filenames[filename]}"
    else:
        used_filenames[filename] = 0

    return filename


def display_summary(
    total: int, successful: int, failed: int, errors: list[tuple[str, str]]
) -> None:
    """Display processing summary report.
    
    Outputs a formatted summary showing total patients, successful
    personalizations, failures, and detailed error information.
    
    Args:
        total: Total patients processed
        successful: Count of successful personalizations
        failed: Count of failed personalizations
        errors: List of (patient_id, error_message) tuples
        
    Example Output:
        ==================================================
        SUMMARY
        ==================================================
        Total patients: 30
        Successful: 28
        Failed: 2
        
        Errors:
          - PAT-015: Missing required field 'dob'
          - PAT-022: Invalid date format
        ==================================================
    """
    click.echo("\n" + "=" * 50)
    click.echo("SUMMARY")
    click.echo("=" * 50)
    click.echo(f"Total patients: {total}")
    click.secho(f"Successful: {successful}", fg="green" if successful > 0 else None)

    if failed > 0:
        click.secho(f"Failed: {failed}", fg="red")
        click.echo("\nErrors:")
        for patient_id, error in errors:
            # Truncate very long error messages for readability
            error_display = error if len(error) <= 100 else error[:97] + "..."
            click.echo(f"  - {patient_id}: {error_display}")
    else:
        click.secho("Failed: 0", fg="green")

    click.echo("=" * 50)

    # Machine-parseable output for scripting
    logger.info(f"SUMMARY: total={total} successful={successful} failed={failed}")
