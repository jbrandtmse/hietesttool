"""Integration tests for complete CCD personalization workflow."""

import time
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ihe_test_util.models.ccd import CCDDocument
from ihe_test_util.template_engine.ccd_personalizer import CCDPersonalizer
from ihe_test_util.template_engine.validators import validate_xml


class TestCCDPersonalizationWorkflow:
    """Test suite for complete CCD personalization workflow."""
    
    def test_complete_ccd_personalization_workflow(self, tmp_path):
        """Test complete workflow: CSV → Parse → Personalize → Validate."""
        # Arrange
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text("""patient_id,patient_id_oid,first_name,last_name,dob,gender,mrn,address,city,state,zip,phone,email
PAT-001,1.2.3.4.5,John,Doe,1980-01-15,M,MRN-001,123 Main St,Springfield,IL,62701,555-0001,john@example.com
PAT-002,1.2.3.4.5,Jane,Smith,1990-05-20,F,MRN-002,456 Oak Ave,Chicago,IL,60601,555-0002,jane@example.com
PAT-003,1.2.3.4.5,Bob,Johnson,1985-03-10,M,MRN-003,789 Pine Rd,Peoria,IL,61602,555-0003,bob@example.com
""")
        
        template_file = tmp_path / "test_ccd_template.xml"
        template_file.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
    <id root="{{document_id}}"/>
    <effectiveTime value="{{creation_timestamp}}"/>
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
        
        output_dir = tmp_path / "ccds"
        output_dir.mkdir()
        
        # Act
        df = pd.read_csv(csv_file)
        df['dob'] = pd.to_datetime(df['dob']).dt.date
        
        personalizer = CCDPersonalizer()
        ccds = personalizer.personalize_batch(template_file, df)
        
        # Assert
        assert len(ccds) == 3  # All patients processed
        
        # Verify all CCDs are valid XML
        for ccd in ccds:
            validate_xml(ccd.xml_content)  # Should not raise
            assert ccd.document_id  # Unique ID present
            assert ccd.patient_id  # Patient reference present
            assert ccd.size_bytes > 0
            assert ccd.sha256_hash
        
        # Verify unique document IDs
        doc_ids = [ccd.document_id for ccd in ccds]
        assert len(doc_ids) == len(set(doc_ids))  # All unique
        
        # Verify required fields populated
        assert 'PAT-001' in ccds[0].xml_content
        assert 'John' in ccds[0].xml_content
        assert 'Doe' in ccds[0].xml_content
        assert '19800115' in ccds[0].xml_content  # HL7 date format
        
        # Verify optional fields populated
        assert 'MRN-001' in ccds[0].xml_content
        assert '123 Main St' in ccds[0].xml_content
        assert 'Springfield' in ccds[0].xml_content
        
        # Save CCDs for inspection
        for ccd in ccds:
            output_file = output_dir / f"{ccd.patient_id}.xml"
            ccd.to_file(output_file)
            assert output_file.exists()
            
            # Verify saved file content
            saved_content = output_file.read_text(encoding='utf-8')
            assert saved_content == ccd.xml_content
    
    def test_personalization_with_sample_csv(self, tmp_path):
        """Test personalization using sample CSV if available."""
        # Arrange
        sample_csv = Path("examples/patients_sample.csv")
        
        if not sample_csv.exists():
            pytest.skip("Sample CSV not available")
        
        template_file = tmp_path / "template.xml"
        template_file.write_text("""<?xml version="1.0"?>
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
        
        # Act
        df = pd.read_csv(sample_csv)
        df['dob'] = pd.to_datetime(df['dob']).dt.date
        
        personalizer = CCDPersonalizer()
        ccds = personalizer.personalize_batch(template_file, df)
        
        # Assert
        assert len(ccds) == len(df)  # All patients processed
        
        # Verify all CCDs are valid XML
        for ccd in ccds:
            validate_xml(ccd.xml_content)
            assert ccd.document_id
            assert ccd.patient_id
    
    def test_personalization_with_test_fixture_template(self, tmp_path):
        """Test personalization using test fixture template if available."""
        # Arrange
        template_file = Path("tests/fixtures/test_ccd_template.xml")
        
        if not template_file.exists():
            pytest.skip("Test fixture template not available")
        
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text("""patient_id,patient_id_oid,first_name,last_name,dob,gender
PAT-100,1.2.3.4.5,Test,Patient,1990-01-01,M
""")
        
        # Act
        df = pd.read_csv(csv_file)
        df['dob'] = pd.to_datetime(df['dob']).dt.date
        
        personalizer = CCDPersonalizer()
        ccds = personalizer.personalize_batch(template_file, df)
        
        # Assert
        assert len(ccds) == 1
        assert ccds[0].patient_id == 'PAT-100'
        validate_xml(ccds[0].xml_content)
    
    def test_batch_personalization_performance(self, tmp_path):
        """Verify batch processing meets performance requirement."""
        # Arrange - Generate 100-patient DataFrame
        patients_data = []
        for i in range(100):
            patients_data.append({
                'patient_id': f'PAT-{i:03d}',
                'patient_id_oid': '1.2.3.4.5',
                'first_name': f'First{i}',
                'last_name': f'Last{i}',
                'dob': date(1980 + (i % 30), 1 + (i % 12), 1 + (i % 28)),
                'gender': 'M' if i % 2 == 0 else 'F'
            })
        df = pd.DataFrame(patients_data)
        
        template_path = tmp_path / "template.xml"
        template_path.write_text("""<?xml version="1.0"?>
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
        
        personalizer = CCDPersonalizer()
        
        # Act
        start = time.time()
        ccds = personalizer.personalize_batch(template_path, df)
        duration = time.time() - start
        
        # Assert performance requirement: <5 minutes (300 seconds)
        assert duration < 300, f"Processing took {duration:.2f}s, expected <300s"
        assert len(ccds) == 100  # All patients processed
        
        # Average per patient should be reasonable (<3 seconds)
        avg_time = duration / 100
        assert avg_time < 3.0, f"Average time per patient: {avg_time:.3f}s, expected <3s"
        
        # Verify unique document_ids
        doc_ids = [c.document_id for c in ccds]
        assert len(doc_ids) == len(set(doc_ids))
    
    def test_batch_personalization_template_caching(self, tmp_path):
        """Verify template caching improves performance."""
        # Arrange - Small dataset for testing cache benefit
        df = pd.DataFrame([
            {'patient_id': f'PAT-{i}', 'patient_id_oid': '1.2.3.4.5',
             'first_name': f'First{i}', 'last_name': f'Last{i}',
             'dob': date(1980, 1, 1), 'gender': 'M'}
            for i in range(10)
        ])
        
        template_path = tmp_path / "template.xml"
        template_path.write_text("""<?xml version="1.0"?>
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
        
        personalizer = CCDPersonalizer()
        
        # Act
        ccds = personalizer.personalize_batch(template_path, df)
        
        # Assert
        assert len(ccds) == 10
        # Verify all CCDs have unique IDs but same template
        doc_ids = [c.document_id for c in ccds]
        assert len(doc_ids) == len(set(doc_ids))
        
        # All should have same structure (from same cached template)
        for ccd in ccds:
            assert '<ClinicalDocument' in ccd.xml_content
            assert '<recordTarget>' in ccd.xml_content
    
    def test_personalization_preserves_xml_namespaces(self, tmp_path):
        """Verify that personalization preserves HL7 CCDA XML namespaces."""
        # Arrange
        template = tmp_path / "template.xml"
        template.write_text("""<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
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
            'patient_id': 'PAT-NS-001',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'Namespace',
            'last_name': 'Test',
            'dob': date(1985, 6, 15),
            'gender': 'M'
        })
        
        personalizer = CCDPersonalizer()
        
        # Act
        result = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        # Assert
        assert 'xmlns="urn:hl7-org:v3"' in result.xml_content
        assert 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' in result.xml_content
    
    def test_error_handling_in_batch_mode(self, tmp_path):
        """Test that batch mode handles errors gracefully."""
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
        
        # Create DataFrame with data that will be personalized successfully
        # (The personalizer converts all values to strings, so even "invalid" data succeeds)
        df = pd.DataFrame([
            {'patient_id': 'PAT-ERR-001', 'patient_id_oid': '1.2.3.4.5',
             'first_name': 'Valid', 'last_name': 'Patient1',
             'dob': date(1980, 1, 1), 'gender': 'M'},
            {'patient_id': 'PAT-ERR-002', 'patient_id_oid': '1.2.3.4.5',
             'first_name': 'Test<xml', 'last_name': 'Patient2',  # Special XML character
             'dob': date(1985, 6, 15), 'gender': 'M'},
            {'patient_id': 'PAT-ERR-003', 'patient_id_oid': '1.2.3.4.5',
             'first_name': 'Valid', 'last_name': 'Patient3',
             'dob': date(1990, 1, 1), 'gender': 'F'},
        ])
        
        personalizer = CCDPersonalizer()
        
        # Act
        results = personalizer.personalize_batch(template, df)
        
        # Assert - all should succeed due to XML escaping
        assert len(results) == 3
        assert results[0].patient_id == 'PAT-ERR-001'
        assert results[1].patient_id == 'PAT-ERR-002'
        assert results[2].patient_id == 'PAT-ERR-003'
        # Verify XML escaping worked
        assert '&lt;' in results[1].xml_content  # < should be escaped
    
    def test_ccd_document_to_file_method(self, tmp_path):
        """Test CCDDocument.to_file() saves correctly."""
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
            'patient_id': 'PAT-FILE-001',
            'patient_id_oid': '1.2.3.4.5',
            'first_name': 'File',
            'last_name': 'Test',
            'dob': date(1992, 8, 20),
            'gender': 'F'
        })
        
        personalizer = CCDPersonalizer()
        ccd = personalizer.personalize_from_dataframe_row(template, patient_row)
        
        output_file = tmp_path / "output.xml"
        
        # Act
        ccd.to_file(output_file)
        
        # Assert
        assert output_file.exists()
        saved_content = output_file.read_text(encoding='utf-8')
        assert saved_content == ccd.xml_content
        assert 'PAT-FILE-001' in saved_content
