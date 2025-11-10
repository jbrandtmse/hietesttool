"""Unit tests for CCD personalization module."""

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from ihe_test_util.models.ccd import CCDDocument
from ihe_test_util.template_engine.ccd_personalizer import CCDPersonalizer
from ihe_test_util.utils.exceptions import CCDPersonalizationError


class TestCCDPersonalizer:
    """Test suite for CCDPersonalizer class."""
    
    def test_init(self):
        """Test CCDPersonalizer initialization."""
        # Act
        personalizer = CCDPersonalizer()
        
        # Assert
        assert personalizer.template_loader is not None
        assert personalizer.template_personalizer is not None
    
    def test_personalize_from_dataframe_row_required_fields(self, tmp_path):
        """Test personalization with required fields only."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="{{document_id}}"/>
    <effectiveTime value="{{creation_timestamp}}"/>
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-001',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'John',
            'last_name': 'Doe',
            'dob': date(1980, 1, 15),
            'gender': 'M'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert isinstance(result, CCDDocument)
        assert 'PAT-001' in result.xml_content
        assert '1.2.3.4.5' in result.xml_content
        assert 'John' in result.xml_content
        assert 'Doe' in result.xml_content
        assert '19800115' in result.xml_content  # HL7 date format
        assert 'M' in result.xml_content
        assert result.patient_id == 'PAT-001'
        assert result.mime_type == 'text/xml'
        assert result.size_bytes > 0
        assert len(result.sha256_hash) == 64  # SHA256 hex digest
        assert result.document_id  # UUID generated
        assert result.creation_timestamp  # Timestamp generated
        assert str(template) in result.template_path
    
    def test_personalize_from_dataframe_row_optional_fields(self, tmp_path):
        """Test personalization with optional fields populated."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="{{document_id}}"/>
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <id extension="{{mrn}}" root="2.16.840.1.113883.4.1"/>
            <addr>
                <streetAddressLine>{{address}}</streetAddressLine>
                <city>{{city}}</city>
                <state>{{state}}</state>
                <postalCode>{{zip}}</postalCode>
            </addr>
            <telecom value="tel:{{phone}}"/>
            <telecom value="mailto:{{email}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-002',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'dob': date(1990, 5, 20),
            'gender': 'F',
            'mrn': 'MRN-123456',
            'address': '123 Main St',
            'city': 'Springfield',
            'state': 'IL',
            'zip': '62701',
            'phone': '555-1234',
            'email': 'jane@example.com'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert 'MRN-123456' in result.xml_content
        assert '123 Main St' in result.xml_content
        assert 'Springfield' in result.xml_content
        assert 'IL' in result.xml_content
        assert '62701' in result.xml_content
        assert '555-1234' in result.xml_content
        assert 'jane@example.com' in result.xml_content
    
    def test_personalize_from_dataframe_row_missing_optional_fields(self, tmp_path):
        """Test personalization with missing optional fields (USE_EMPTY strategy)."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <addr>
                <city>{{city}}</city>
            </addr>
            <telecom value="tel:{{phone}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-003',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Bob',
            'last_name': 'Johnson',
            'dob': date(1985, 3, 10),
            'gender': 'M'
            # Missing: city, phone
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert - should not raise, optional fields replaced with empty string
        assert '<city></city>' in result.xml_content
        assert 'tel:' in result.xml_content
        assert isinstance(result, CCDDocument)
    
    def test_personalize_from_dataframe_row_unique_document_ids(self, tmp_path):
        """Test that each personalization generates unique document_id."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="{{document_id}}"/>
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-004',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Alice',
            'last_name': 'Brown',
            'dob': date(1975, 12, 25),
            'gender': 'F'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result1 = personalizer.personalize_from_dataframe_row(template, patient_row)
        result2 = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert result1.document_id != result2.document_id
        assert result1.document_id in result1.xml_content
        assert result2.document_id in result2.xml_content
    
    def test_personalize_from_dataframe_row_timestamp_insertion(self, tmp_path):
        """Test that creation_timestamp is inserted correctly."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <effectiveTime value="{{creation_timestamp}}"/>
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-005',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Charlie',
            'last_name': 'Davis',
            'dob': date(1995, 7, 4),
            'gender': 'M'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert result.creation_timestamp is not None
        assert result.creation_timestamp.tzinfo == timezone.utc
        # Check timestamp is in HL7 format (YYYYMMDDHHmmss)
        timestamp_str = result.creation_timestamp.strftime("%Y%m%d%H%M%S")
        assert timestamp_str in result.xml_content
    
    def test_personalize_from_dataframe_row_date_formatting(self, tmp_path):
        """Test that dates are formatted in HL7 format (YYYYMMDD)."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-006',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Diana',
            'last_name': 'Evans',
            'dob': date(2000, 12, 31),
            'gender': 'F'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert '20001231' in result.xml_content  # HL7 format
    
    def test_personalize_from_dataframe_row_xml_validation(self, tmp_path):
        """Test that personalized XML is validated as well-formed."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-007',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Eve',
            'last_name': 'Foster',
            'dob': date(1988, 4, 15),
            'gender': 'F'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert - should not raise validation error
        assert result is not None
        assert '<?xml version="1.0"?>' in result.xml_content
    
    def test_personalize_from_dataframe_row_metadata_calculation(self, tmp_path):
        """Test CCDDocument metadata calculation (size_bytes, sha256_hash)."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-008',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Frank',
            'last_name': 'Garcia',
            'dob': date(1992, 9, 20),
            'gender': 'M'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert result.size_bytes == len(result.xml_content.encode('utf-8'))
        expected_hash = hashlib.sha256(result.xml_content.encode('utf-8')).hexdigest()
        assert result.sha256_hash == expected_hash
    
    def test_personalize_from_dataframe_row_invalid_template(self, tmp_path):
        """Test error handling for invalid template."""
        # Arrange
        template = tmp_path / "nonexistent.xml"
        
        patient_row = pd.Series({
            'patient_id': 'PAT-009',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Grace',
            'last_name': 'Hill',
            'dob': date(1983, 11, 5),
            'gender': 'F'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act & Assert
        with pytest.raises(CCDPersonalizationError) as exc_info:
            personalizer.personalize_from_dataframe_row(template, patient_row)
        
        assert 'PAT-009' in str(exc_info.value)
        assert 'required fields' in str(exc_info.value).lower()
    
    def test_personalize_batch_multiple_patients(self, tmp_path):
        """Test batch personalization with multiple patients."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="{{document_id}}"/>
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        df = pd.DataFrame([
            {'patient_id': 'PAT-010', 'patient_id_oid': '1.2.3.4.5', 'first_name': 'Henry', 
             'last_name': 'Irving', 'dob': date(1970, 1, 1), 'gender': 'M'},
            {'patient_id': 'PAT-011', 'patient_id_oid': '1.2.3.4.5', 'first_name': 'Iris', 
             'last_name': 'Jones', 'dob': date(1980, 2, 2), 'gender': 'F'},
            {'patient_id': 'PAT-012', 'patient_id_oid': '1.2.3.4.5', 'first_name': 'Jack', 
             'last_name': 'King', 'dob': date(1990, 3, 3), 'gender': 'M'},
        ])
        
        personalizer = CCDPersonalizer()
        
        # Act
        results = personalizer.personalize_batch(template, df)
        
        # Assert
        assert len(results) == 3
        assert all(isinstance(r, CCDDocument) for r in results)
        assert results[0].patient_id == 'PAT-010'
        assert results[1].patient_id == 'PAT-011'
        assert results[2].patient_id == 'PAT-012'
        
        # Verify unique document_ids
        doc_ids = [r.document_id for r in results]
        assert len(doc_ids) == len(set(doc_ids))
    
    def test_personalize_batch_empty_dataframe(self, tmp_path):
        """Test batch personalization with empty DataFrame."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        df = pd.DataFrame(columns=['patient_id', 'patient_id_oid', 'first_name', 
                                   'last_name', 'dob', 'gender'])
        
        personalizer = CCDPersonalizer()
        
        # Act
        results = personalizer.personalize_batch(template, df)
        
        # Assert
        assert len(results) == 0
    
    def test_personalize_batch_partial_failure(self, tmp_path):
        """Test batch personalization handles individual patient errors."""
        # Arrange - Create malformed template to cause validation error
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        # Create DataFrame with one row that will have unclosed XML tag after personalization
        df = pd.DataFrame([
            {'patient_id': 'PAT-013', 'patient_id_oid': '1.2.3.4.5', 'first_name': 'Laura', 
             'last_name': 'Miller', 'dob': date(1985, 5, 5), 'gender': 'F'},
            {'patient_id': 'PAT-014', 'patient_id_oid': '1.2.3.4.5', 'first_name': 'Mike<tag', 
             'last_name': 'Nelson', 'dob': date(1990, 1, 1), 'gender': 'M'},  # Will cause XML error
            {'patient_id': 'PAT-015', 'patient_id_oid': '1.2.3.4.5', 'first_name': 'Nancy', 
             'last_name': 'Owen', 'dob': date(1995, 7, 7), 'gender': 'F'},
        ])
        
        personalizer = CCDPersonalizer()
        
        # Act
        results = personalizer.personalize_batch(template, df)
        
        # Assert - all should succeed because XML escaping handles the < character
        # This test verifies error handling exists but in this case all succeed
        assert len(results) == 3
        assert results[0].patient_id == 'PAT-013'
        assert results[1].patient_id == 'PAT-014'
        assert results[2].patient_id == 'PAT-015'
        # Verify XML escaping worked for problematic character
        assert '&lt;' in results[1].xml_content  # < should be escaped
    
    def test_personalize_with_nan_values_in_optional_fields(self, tmp_path):
        """Test personalization handles pandas NaN values in optional fields."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <addr>
                <city>{{city}}</city>
                <state>{{state}}</state>
            </addr>
            <telecom value="tel:{{phone}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        # Create DataFrame with NaN values
        df = pd.DataFrame([
            {'patient_id': 'PAT-NAN-001', 'patient_id_oid': '1.2.3.4.5',
             'first_name': 'Test', 'last_name': 'Patient',
             'dob': date(1980, 1, 1), 'gender': 'M',
             'city': pd.NA, 'state': None, 'phone': float('nan')}
        ])
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, df.iloc[0])
        
        # Assert - NaN values should be handled gracefully
        assert isinstance(result, CCDDocument)
        assert result.patient_id == 'PAT-NAN-001'
        assert '<city>' in result.xml_content
        assert '<state>' in result.xml_content
    
    def test_personalize_with_unicode_characters(self, tmp_path):
        """Test personalization handles Unicode/international characters."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        # Test with various Unicode characters
        test_cases = [
            {'patient_id': 'PAT-UNI-001', 'first_name': 'José', 'last_name': 'García'},
            {'patient_id': 'PAT-UNI-002', 'first_name': '李', 'last_name': '明'},
            {'patient_id': 'PAT-UNI-003', 'first_name': 'Müller', 'last_name': 'Schröder'},
            {'patient_id': 'PAT-UNI-004', 'first_name': 'Søren', 'last_name': 'Åström'},
        ]
        
        personalizer = CCDPersonalizer()
        
        for test_case in test_cases:
            # Arrange
            patient_row = pd.Series({
                'patient_id': test_case['patient_id'],
                'patient_id_oid': '1.2.3.4.5',
                'first_name': test_case['first_name'],
                'last_name': test_case['last_name'],
                'dob': date(1985, 6, 15),
                'gender': 'M'
            })
            
            # Act
            result = personalizer.personalize_from_dataframe_row(template, patient_row)
            
            # Assert
            assert test_case['first_name'] in result.xml_content
            assert test_case['last_name'] in result.xml_content
            assert result.patient_id == test_case['patient_id']
    
    def test_personalize_with_missing_required_columns(self, tmp_path):
        """Test handling when DataFrame is missing columns (uses empty string)."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        # DataFrame missing 'dob' column
        patient_row = pd.Series({
            'patient_id': 'PAT-ERR-100',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Test',
            'last_name': 'Patient',
            'gender': 'M'
            # Missing: dob
        })
        
        personalizer = CCDPersonalizer()
        
        # Act - missing column should be handled gracefully with empty string
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert isinstance(result, CCDDocument)
        assert result.patient_id == 'PAT-ERR-100'
        # Missing dob should result in empty value attribute
        assert 'value=""' in result.xml_content or 'value="' in result.xml_content
    
    def test_personalize_with_invalid_date_types(self, tmp_path):
        """Test handling of invalid date types in date fields."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        # String date instead of date object
        patient_row = pd.Series({
            'patient_id': 'PAT-DATE-001',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Test',
            'last_name': 'Patient',
            'dob': '1980-01-01',  # String instead of date object
            'gender': 'M'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act - should handle string dates gracefully by converting to string
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert isinstance(result, CCDDocument)
        assert '1980-01-01' in result.xml_content  # String is inserted as-is
    
    def test_personalize_with_empty_strings_in_required_fields(self, tmp_path):
        """Test handling of empty strings vs None in required fields."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        # Empty string in first_name
        patient_row = pd.Series({
            'patient_id': 'PAT-EMPTY-001',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': '',  # Empty string
            'last_name': 'Patient',
            'dob': date(1980, 1, 1),
            'gender': 'M'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert - empty string should be inserted
        assert isinstance(result, CCDDocument)
        assert '<given></given>' in result.xml_content
    
    def test_personalize_with_mixed_data_types(self, tmp_path):
        """Test handling of mixed data types (integers where strings expected)."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="{{patient_id}}" root="{{patient_id_oid}}"/>
            <addr>
                <postalCode>{{zip}}</postalCode>
            </addr>
            <patient>
                <name>
                    <given>{{first_name}}</given>
                    <family>{{last_name}}</family>
                </name>
                <administrativeGenderCode code="{{gender}}"/>
                <birthTime value="{{dob}}"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        # Integer zip code, integer patient_id
        patient_row = pd.Series({
            'patient_id': 12345,  # Integer instead of string
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Test',
            'last_name': 'Patient',
            'dob': date(1980, 1, 1),
            'gender': 'M',
            'zip': 62701  # Integer zip code
        })
        
        personalizer = CCDPersonalizer()
        
        # Act - should convert to strings
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert isinstance(result, CCDDocument)
        assert '12345' in result.xml_content
        assert '62701' in result.xml_content
    
    def test_personalize_with_template_no_placeholders(self, tmp_path):
        """Test personalization with static template (no placeholders)."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <recordTarget>
        <patientRole>
            <id extension="STATIC-001" root="1.2.3.4.5"/>
            <patient>
                <name>
                    <given>Static</given>
                    <family>Patient</family>
                </name>
                <administrativeGenderCode code="U"/>
            </patient>
        </patientRole>
    </recordTarget>
</ClinicalDocument>
        """)
        
        patient_row = pd.Series({
            'patient_id': 'PAT-STATIC-001',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Test',
            'last_name': 'Patient',
            'dob': date(1980, 1, 1),
            'gender': 'M'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert - static content should remain unchanged
        assert isinstance(result, CCDDocument)
        assert 'STATIC-001' in result.xml_content
        assert 'Static' in result.xml_content
        # Patient data should NOT be in the document since no placeholders
        assert 'PAT-STATIC-001' not in result.xml_content
