"""CCD template personalization with patient demographics."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from ihe_test_util.models.ccd import CCDDocument
from ihe_test_util.template_engine.loader import TemplateLoader
from ihe_test_util.template_engine.personalizer import (
    MissingValueStrategy,
    TemplatePersonalizer,
)
from ihe_test_util.template_engine.validators import validate_xml
from ihe_test_util.utils.exceptions import CCDPersonalizationError

logger = logging.getLogger(__name__)


class CCDPersonalizer:
    """Personalizes CCD templates with patient demographics from CSV data.
    
    This class orchestrates the CCD personalization workflow by:
    1. Loading CCD templates using TemplateLoader (with caching)
    2. Generating document metadata (UUID, timestamp)
    3. Personalizing templates with patient data using TemplatePersonalizer
    4. Validating personalized XML for well-formedness
    5. Creating CCDDocument objects with complete metadata
    
    Supports both single patient and batch processing modes.
    """
    
    def __init__(self) -> None:
        """Initialize CCD personalizer with template loader and personalizer.
        
        The personalizer is configured with:
        - HL7 date format (YYYYMMDD) for CCD dates
        - USE_EMPTY strategy for optional patient fields
        - Maximum nesting depth of 3 for nested placeholders
        """
        self.template_loader = TemplateLoader()
        self.template_personalizer = TemplatePersonalizer(
            date_format="HL7",
            missing_value_strategy=MissingValueStrategy.USE_EMPTY,
            max_nesting_depth=3
        )
        logger.debug("CCDPersonalizer initialized")
    
    def personalize_from_dataframe_row(
        self, 
        template_path: Path, 
        patient_row: pd.Series
    ) -> CCDDocument:
        """Personalize CCD template with patient data from DataFrame row.
        
        This method:
        1. Loads the CCD template (uses cache if available)
        2. Generates unique document_id and creation_timestamp
        3. Converts DataFrame row to dictionary for personalization
        4. Personalizes template with patient data and document metadata
        5. Validates personalized XML is well-formed
        6. Returns CCDDocument with all metadata populated
        
        Args:
            template_path: Path to CCD XML template file
            patient_row: pandas Series containing patient demographics
            
        Returns:
            CCDDocument with personalized XML content and metadata
            
        Raises:
            CCDPersonalizationError: If personalization or validation fails
            TemplateLoadError: If template cannot be loaded
            MalformedXMLError: If personalized XML is not well-formed
        """
        patient_id = patient_row.get('patient_id', 'UNKNOWN')
        
        try:
            logger.info(f"Personalizing CCD for patient {patient_id}")
            
            # Load template (uses cache if available)
            template_content = self.template_loader.load_from_file(template_path)
            
            # Generate document metadata
            document_id = str(uuid4())
            creation_timestamp = datetime.now(timezone.utc)
            
            # Prepare values dictionary from patient row
            values = patient_row.to_dict()
            
            # Add document metadata to values
            values['document_id'] = document_id
            values['creation_timestamp'] = creation_timestamp.strftime("%Y%m%d%H%M%S")
            
            # Personalize template
            personalized_xml = self.template_personalizer.personalize(
                template_content, 
                values
            )
            
            # Validate personalized XML
            validate_xml(personalized_xml)
            
            # Create CCDDocument
            ccd = CCDDocument(
                document_id=document_id,
                patient_id=str(values.get('patient_id', '')),
                template_path=str(template_path),
                xml_content=personalized_xml,
                creation_timestamp=creation_timestamp
            )
            
            logger.info(
                f"CCD personalization complete for patient {ccd.patient_id} "
                f"(document_id: {document_id})"
            )
            return ccd
            
        except Exception as e:
            error_msg = (
                f"Failed to personalize CCD for patient {patient_id}: {e}. "
                f"Verify required fields (patient_id, patient_id_oid, first_name, "
                f"last_name, dob, gender) are present in DataFrame."
            )
            logger.error(error_msg)
            raise CCDPersonalizationError(error_msg) from e
    
    def personalize_batch(
        self, 
        template_path: Path, 
        df: pd.DataFrame
    ) -> list[CCDDocument]:
        """Personalize CCD template for all patients in DataFrame.
        
        This method processes all patients in batch mode:
        1. Iterates through all DataFrame rows
        2. Personalizes CCD for each patient individually
        3. Reuses cached template for performance
        4. Logs progress every 10 patients
        5. Handles individual patient errors without failing entire batch
        6. Returns list of successfully personalized CCDs
        
        Args:
            template_path: Path to CCD XML template file
            df: pandas DataFrame with patient demographics
            
        Returns:
            List of CCDDocument objects for successfully personalized patients
            
        Raises:
            CCDPersonalizationError: If all patients fail personalization
        """
        logger.info(f"Starting batch personalization for {len(df)} patients")
        
        ccds: list[CCDDocument] = []
        errors: list[tuple[Any, str]] = []
        
        for idx, row in df.iterrows():
            patient_id = row.get('patient_id', f'row_{idx}')
            
            try:
                ccd = self.personalize_from_dataframe_row(template_path, row)
                ccds.append(ccd)
                
                # Log progress every 10 patients
                if (idx + 1) % 10 == 0:
                    logger.info(f"Processed {idx + 1}/{len(df)} patients")
                    
            except Exception as e:
                logger.error(f"Failed to personalize CCD for patient {patient_id}: {e}")
                errors.append((patient_id, str(e)))
        
        logger.info(
            f"Batch personalization complete: {len(ccds)} successful, "
            f"{len(errors)} failed"
        )
        
        if errors and len(ccds) == 0:
            raise CCDPersonalizationError(
                f"All {len(errors)} patients failed personalization"
            )
        
        return ccds
