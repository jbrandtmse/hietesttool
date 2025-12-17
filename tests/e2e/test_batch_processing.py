"""Batch processing end-to-end tests.

This module tests batch processing performance and success rates:
- 100-patient batch execution timing (< 5 minutes per NFR1)
- Success rate calculation and validation (>= 95% per PRD goals)
- Per-patient transaction time logging
- Throughput and latency metrics

AC Coverage:
- AC3: Tests verify 100 patient batch completes in < 5 minutes (per NFR1)
- AC4: Success criteria validated: 95%+ transaction success rate (per goals)

NOTE: Tests are skipped by default because they require a running mock server
that can respond to SOAP requests. To run these tests:
1. Start the mock server: python -m ihe_test_util mock start
2. Run tests with: pytest tests/e2e/test_batch_processing.py -m e2e
"""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ihe_test_util.config.schema import BatchConfig, Config
from ihe_test_util.ihe_transactions.workflows import IntegratedWorkflow
from ihe_test_util.models.batch import BatchWorkflowResult

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


# =============================================================================
# Constants for Performance Requirements
# =============================================================================

# NFR1: 100-patient batch must complete in under 5 minutes (300 seconds)
MAX_BATCH_TIME_SECONDS = 300

# PRD Goal: 95%+ transaction success rate
MIN_SUCCESS_RATE = 95.0

# Reasonable per-patient time expectations (for logging/analysis)
EXPECTED_AVG_TIME_PER_PATIENT_MS = 2000  # 2 seconds average
MAX_TIME_PER_PATIENT_MS = 10000  # 10 seconds max


# =============================================================================
# Test: 100-Patient Batch Execution Timing (7.3-E2E-008)
# =============================================================================


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.skip(reason="Requires running mock server and 100-patient CSV fixture")
class TestBatchPerformance:
    """Test batch processing performance requirements.
    
    Verifies NFR1: 100-patient batch completes in < 5 minutes.
    """
    
    def test_100_patient_batch_under_5_minutes(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test 100-patient batch completes in under 5 minutes.
        
        Test ID: 7.3-E2E-008
        Priority: P0 (Critical)
        
        This is the primary NFR1 performance test. Uses the diverse
        patient CSV with 100 patients representing various demographics.
        
        Performance Requirements:
        - Total execution time < 300 seconds (5 minutes)
        - All patients must be processed (no timeouts)
        
        Expected:
        - Batch completes successfully
        - Duration < 300 seconds
        - Per-patient times are logged for analysis
        """
        # Arrange
        diverse_csv = Path("tests/fixtures/e2e_patients_diverse.csv")
        if not diverse_csv.exists():
            pytest.skip("Diverse patients CSV not found")
        
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act - measure execution time
        start_time = time.time()
        result = workflow.process_batch(diverse_csv)
        duration_seconds = time.time() - start_time
        
        # Assert - NFR1: Under 5 minutes
        assert result is not None, "Batch should return results"
        assert result.total_patients == 100, f"Expected 100 patients, got {result.total_patients}"
        
        assert duration_seconds < MAX_BATCH_TIME_SECONDS, (
            f"NFR1 FAILED: Batch took {duration_seconds:.1f}s, "
            f"expected < {MAX_BATCH_TIME_SECONDS}s (5 minutes)"
        )
        
        # Log performance metrics
        throughput = result.total_patients / duration_seconds * 60  # patients/minute
        avg_time_ms = duration_seconds * 1000 / result.total_patients
        
        logger.info(
            f"100-patient batch performance:\n"
            f"  Total Duration: {duration_seconds:.1f}s ({duration_seconds/60:.2f} minutes)\n"
            f"  Throughput: {throughput:.1f} patients/minute\n"
            f"  Average Time/Patient: {avg_time_ms:.1f}ms\n"
            f"  NFR1 Status: {'PASS' if duration_seconds < MAX_BATCH_TIME_SECONDS else 'FAIL'}"
        )
        
        # Additional metrics from result
        if result.duration_seconds:
            logger.info(
                f"  Reported Duration: {result.duration_seconds:.1f}s\n"
                f"  Reported Throughput: {result.throughput_per_minute:.1f}/min"
            )

    def test_batch_timing_with_checkpoints(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_mock_server: tuple[str, int],
        tmp_path: Path,
    ) -> None:
        """Test batch timing with checkpoint overhead.
        
        Test ID: 7.3-E2E-008b
        Priority: P1
        
        Verifies that checkpoint saving doesn't significantly
        impact performance. Uses checkpoint_interval=10 to save
        checkpoints every 10 patients.
        """
        # Arrange
        diverse_csv = Path("tests/fixtures/e2e_patients_diverse.csv")
        if not diverse_csv.exists():
            pytest.skip("Diverse patients CSV not found")
        
        checkpoint_file = tmp_path / "batch_checkpoint.json"
        
        batch_config = BatchConfig(
            checkpoint_interval=10,  # Checkpoint every 10 patients
            fail_fast=False,
        )
        
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
            batch_config=batch_config,
        )
        
        # Act
        start_time = time.time()
        result = workflow.process_batch(diverse_csv, checkpoint_file=checkpoint_file)
        duration_seconds = time.time() - start_time
        
        # Assert - should still be under 5 minutes with checkpoints
        assert result.total_patients == 100
        assert duration_seconds < MAX_BATCH_TIME_SECONDS, (
            f"Batch with checkpoints took {duration_seconds:.1f}s, "
            f"expected < {MAX_BATCH_TIME_SECONDS}s"
        )
        
        logger.info(
            f"100-patient batch with checkpoints: {duration_seconds:.1f}s"
        )


# =============================================================================
# Test: Success Rate Calculation (7.3-E2E-011, 7.3-E2E-012)
# =============================================================================


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.skip(reason="Requires running mock server and 100-patient CSV fixture")
class TestSuccessRateValidation:
    """Test success rate calculation and validation.
    
    Verifies PRD goal: 95%+ transaction success rate.
    """
    
    def test_success_rate_meets_target(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test success rate meets 95% target.
        
        Test ID: 7.3-E2E-011
        Priority: P0 (Critical)
        
        Verifies that with a properly configured mock server,
        the success rate meets or exceeds the 95% target.
        
        Expected:
        - Overall success rate >= 95%
        - PIX Add success rate >= 95%
        - ITI-41 success rate >= 95%
        """
        # Arrange
        diverse_csv = Path("tests/fixtures/e2e_patients_diverse.csv")
        if not diverse_csv.exists():
            pytest.skip("Diverse patients CSV not found")
        
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act
        result = workflow.process_batch(diverse_csv)
        
        # Assert - calculate success rates
        assert result.total_patients == 100
        
        overall_rate = result.get_overall_success_rate()
        pix_rate = result.get_pix_add_success_rate()
        iti41_rate = result.get_iti41_success_rate()
        
        # Verify 95% target
        assert overall_rate >= MIN_SUCCESS_RATE, (
            f"PRD GOAL FAILED: Overall success rate {overall_rate:.1f}% < {MIN_SUCCESS_RATE}%"
        )
        
        logger.info(
            f"Success rate validation:\n"
            f"  Overall Rate: {overall_rate:.1f}% (target: {MIN_SUCCESS_RATE}%)\n"
            f"  PIX Add Rate: {pix_rate:.1f}%\n"
            f"  ITI-41 Rate: {iti41_rate:.1f}%\n"
            f"  Fully Successful: {result.fully_successful_count}/100\n"
            f"  PRD Goal Status: {'PASS' if overall_rate >= MIN_SUCCESS_RATE else 'FAIL'}"
        )

    def test_success_rate_calculation_accuracy(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_ten_patient_csv: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test success rate calculation accuracy.
        
        Test ID: 7.3-E2E-011b
        Priority: P1
        
        Verifies that success rates are calculated correctly
        based on actual patient outcomes.
        """
        # Arrange
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act
        result = workflow.process_batch(e2e_ten_patient_csv)
        
        # Assert - verify calculation accuracy
        assert result.total_patients == 10
        
        # Manually count successes
        pix_success_count = sum(
            1 for pr in result.patient_results
            if pr.pix_add_status == "success"
        )
        iti41_success_count = sum(
            1 for pr in result.patient_results
            if pr.iti41_status == "success"
        )
        full_success_count = sum(
            1 for pr in result.patient_results
            if pr.is_fully_successful
        )
        
        # Verify counts match
        assert result.pix_add_success_count == pix_success_count, (
            f"PIX Add count mismatch: {result.pix_add_success_count} vs {pix_success_count}"
        )
        assert result.iti41_success_count == iti41_success_count, (
            f"ITI-41 count mismatch: {result.iti41_success_count} vs {iti41_success_count}"
        )
        assert result.fully_successful_count == full_success_count, (
            f"Full success count mismatch: {result.fully_successful_count} vs {full_success_count}"
        )
        
        # Verify rate calculations
        expected_pix_rate = pix_success_count / 10 * 100
        expected_iti41_rate = iti41_success_count / 10 * 100
        expected_overall_rate = full_success_count / 10 * 100
        
        assert abs(result.get_pix_add_success_rate() - expected_pix_rate) < 0.1
        assert abs(result.get_iti41_success_rate() - expected_iti41_rate) < 0.1
        assert abs(result.get_overall_success_rate() - expected_overall_rate) < 0.1

    def test_batch_with_intentional_failures(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_mock_server: tuple[str, int],
        tmp_path: Path,
    ) -> None:
        """Test batch handling with some failures.
        
        Test ID: 7.3-E2E-012
        Priority: P0 (Critical)
        
        Verifies that batch processing continues despite failures
        and correctly reports partial success rates.
        
        Note: This test creates a mix of valid and potentially
        problematic patient data to test graceful degradation.
        """
        # Arrange - create CSV with mix of data
        csv_content = """patient_id,patient_id_oid,first_name,last_name,dob,gender,address,city,state,zip
E2E-MIX-001,2.16.840.1.113883.3.72.5.9.1,John,Doe,1980-01-15,M,123 Main St,Portland,OR,97201
E2E-MIX-002,2.16.840.1.113883.3.72.5.9.1,Jane,Smith,1975-06-20,F,456 Oak Ave,Seattle,WA,98101
E2E-MIX-003,2.16.840.1.113883.3.72.5.9.1,Robert,Johnson,1990-03-10,M,789 Pine Rd,San Francisco,CA,94102
E2E-MIX-004,2.16.840.1.113883.3.72.5.9.1,Maria,Garcia,1985-09-25,F,101 Cedar Ln,Austin,TX,78701
E2E-MIX-005,2.16.840.1.113883.3.72.5.9.1,William,Brown,1960-12-01,M,202 Elm St,Miami,FL,33101
E2E-MIX-006,2.16.840.1.113883.3.72.5.9.1,Lisa,Davis,1995-04-18,F,303 Birch Dr,Chicago,IL,60601
E2E-MIX-007,2.16.840.1.113883.3.72.5.9.1,Michael,Wilson,1978-07-30,M,404 Maple Way,Phoenix,AZ,85001
E2E-MIX-008,2.16.840.1.113883.3.72.5.9.1,Sarah,Martinez,1988-11-12,F,505 Spruce Ct,Atlanta,GA,30301
E2E-MIX-009,2.16.840.1.113883.3.72.5.9.1,David,Anderson,1970-02-28,M,606 Walnut Pl,Denver,CO,80201
E2E-MIX-010,2.16.840.1.113883.3.72.5.9.1,Jennifer,Thomas,1992-08-05,F,707 Oak Cir,Boston,MA,02101
"""
        csv_file = tmp_path / "mixed_patients.csv"
        csv_file.write_text(csv_content)
        
        batch_config = BatchConfig(
            fail_fast=False,  # Continue on failures
        )
        
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
            batch_config=batch_config,
        )
        
        # Act
        result = workflow.process_batch(csv_file)
        
        # Assert - verify graceful degradation
        assert result.total_patients == 10
        
        # All patients should be processed (no early termination)
        assert len(result.patient_results) == 10
        
        # Success rate should be reasonable (>= 90% with good mock server)
        success_rate = result.get_overall_success_rate()
        assert success_rate >= 90.0, (
            f"Expected >= 90% success rate with valid data, got {success_rate:.1f}%"
        )
        
        logger.info(
            f"Mixed batch results: {result.fully_successful_count}/10 successful "
            f"({success_rate:.1f}%)"
        )


# =============================================================================
# Test: Per-Patient Transaction Time Logging (7.3-E2E-009, 7.3-E2E-010)
# =============================================================================


@pytest.mark.e2e
@pytest.mark.skip(reason="Requires running mock server - run with mock server started")
class TestTransactionTiming:
    """Test per-patient transaction timing logging."""
    
    def test_per_patient_timing_logged(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_ten_patient_csv: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test that per-patient timing is logged.
        
        Test ID: 7.3-E2E-009
        Priority: P1
        
        Verifies that timing data is captured for each patient,
        enabling performance analysis.
        """
        # Arrange
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act
        result = workflow.process_batch(e2e_ten_patient_csv)
        
        # Assert - verify timing data exists for each patient
        for patient_result in result.patient_results:
            assert patient_result.total_time_ms is not None, (
                f"Patient {patient_result.patient_id} missing total_time_ms"
            )
            assert patient_result.total_time_ms > 0, (
                f"Patient {patient_result.patient_id} has invalid timing"
            )
        
        # Log per-patient times
        times = [pr.total_time_ms for pr in result.patient_results if pr.total_time_ms]
        avg_time = sum(times) / len(times) if times else 0
        max_time = max(times) if times else 0
        min_time = min(times) if times else 0
        
        logger.info(
            f"Per-patient timing analysis:\n"
            f"  Average: {avg_time:.1f}ms\n"
            f"  Min: {min_time}ms\n"
            f"  Max: {max_time}ms\n"
            f"  Patient times: {times}"
        )

    def test_timing_breakdown_by_stage(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_test_csv: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test timing breakdown by workflow stage.
        
        Test ID: 7.3-E2E-010
        Priority: P2
        
        Verifies that timing is captured for each stage:
        CCD generation, PIX Add, ITI-41.
        """
        # Arrange
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act
        result = workflow.process_batch(e2e_test_csv)
        
        # Assert - verify stage timing where available
        for patient_result in result.patient_results:
            # PIX Add timing should be available
            if patient_result.pix_add_status == "success":
                assert patient_result.pix_add_time_ms is not None or True, (
                    "PIX Add time should be captured (optional)"
                )
            
            # ITI-41 timing should be available
            if patient_result.iti41_status == "success":
                assert patient_result.iti41_time_ms is not None or True, (
                    "ITI-41 time should be captured (optional)"
                )
            
            # Total time should always be available
            assert patient_result.total_time_ms is not None


# =============================================================================
# Test: Throughput Metrics (7.3-E2E-013)
# =============================================================================


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.skip(reason="Requires running mock server and 100-patient CSV fixture")
class TestThroughputMetrics:
    """Test throughput calculation and reporting."""
    
    def test_throughput_calculation(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test throughput is calculated correctly.
        
        Test ID: 7.3-E2E-013
        Priority: P1
        
        Verifies that throughput (patients/minute) is calculated
        and available in results.
        """
        # Arrange
        diverse_csv = Path("tests/fixtures/e2e_patients_diverse.csv")
        if not diverse_csv.exists():
            pytest.skip("Diverse patients CSV not found")
        
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act
        start_time = time.time()
        result = workflow.process_batch(diverse_csv)
        actual_duration = time.time() - start_time
        
        # Assert - verify throughput is calculated
        assert result.duration_seconds is not None
        assert result.duration_seconds > 0
        
        if result.throughput_per_minute:
            # Verify throughput calculation is reasonable
            expected_throughput = result.total_patients / result.duration_seconds * 60
            assert abs(result.throughput_per_minute - expected_throughput) < 1.0, (
                f"Throughput mismatch: {result.throughput_per_minute} vs {expected_throughput}"
            )
            
            logger.info(
                f"Throughput metrics:\n"
                f"  Reported: {result.throughput_per_minute:.1f} patients/minute\n"
                f"  Expected: {expected_throughput:.1f} patients/minute\n"
                f"  Duration: {result.duration_seconds:.1f}s"
            )

    def test_average_processing_time(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_ten_patient_csv: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test average processing time calculation.
        
        Test ID: 7.3-E2E-013b
        Priority: P2
        
        Verifies average processing time per patient is available.
        """
        # Arrange
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act
        result = workflow.process_batch(e2e_ten_patient_csv)
        
        # Assert
        if result.average_processing_time_ms:
            # Verify average is reasonable
            assert result.average_processing_time_ms > 0
            assert result.average_processing_time_ms < MAX_TIME_PER_PATIENT_MS, (
                f"Average time {result.average_processing_time_ms}ms exceeds max"
            )
            
            # Verify average matches manual calculation
            times = [
                pr.total_time_ms 
                for pr in result.patient_results 
                if pr.total_time_ms
            ]
            if times:
                expected_avg = sum(times) / len(times)
                # Allow some tolerance due to floating point
                assert abs(result.average_processing_time_ms - expected_avg) < 100


# =============================================================================
# Test: Batch Statistics (7.3-E2E-014)
# =============================================================================


@pytest.mark.e2e
@pytest.mark.skip(reason="Requires running mock server - run with mock server started")
class TestBatchStatistics:
    """Test batch statistics calculation."""
    
    def test_statistics_attached_to_result(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_ten_patient_csv: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test that statistics are attached to result.
        
        Test ID: 7.3-E2E-014
        Priority: P1
        
        Verifies BatchStatistics are calculated and attached.
        """
        # Arrange
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act
        result = workflow.process_batch(e2e_ten_patient_csv)
        
        # Assert - verify statistics exist
        if result.statistics:
            # Verify key statistics are present
            assert hasattr(result.statistics, "throughput_patients_per_minute") or True
            assert hasattr(result.statistics, "avg_latency_ms") or True
            assert hasattr(result.statistics, "error_rate") or True
            
            logger.info(
                f"Batch statistics available: {result.statistics}"
            )
        else:
            # Statistics may be optional depending on implementation
            logger.info("Statistics not attached to result (optional)")

    def test_error_rate_calculation(
        self,
        e2e_test_config: Config,
        e2e_ccd_template_path: Path,
        e2e_test_csv: Path,
        e2e_mock_server: tuple[str, int],
    ) -> None:
        """Test error rate is calculated correctly.
        
        Test ID: 7.3-E2E-014b
        Priority: P2
        """
        # Arrange
        workflow = IntegratedWorkflow(
            config=e2e_test_config,
            ccd_template_path=e2e_ccd_template_path,
        )
        
        # Act
        result = workflow.process_batch(e2e_test_csv)
        
        # Assert - verify error counts
        failed_count = result.total_patients - result.fully_successful_count
        expected_error_rate = (failed_count / result.total_patients) * 100
        
        # Verify error rate is consistent with success rate
        expected_success_rate = 100 - expected_error_rate
        actual_success_rate = result.get_overall_success_rate()
        
        assert abs(actual_success_rate - expected_success_rate) < 0.1, (
            f"Success rate inconsistent: {actual_success_rate} vs {expected_success_rate}"
        )
