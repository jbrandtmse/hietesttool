"""Unit tests for patient ID auto-generation."""

import re

import pytest

from ihe_test_util.csv_parser.id_generator import (
    ID_PREFIX,
    generate_patient_id,
    reset_generated_ids,
)


class TestGeneratePatientId:
    """Test suite for generate_patient_id function."""

    def setup_method(self):
        """Reset generated IDs before each test."""
        reset_generated_ids()

    def test_generate_patient_id_format(self):
        """Test that generated ID matches TEST-{UUID} format."""
        # Arrange & Act
        patient_id = generate_patient_id()

        # Assert
        assert patient_id.startswith(f"{ID_PREFIX}-")
        assert len(patient_id) == 41  # TEST- (5) + UUID (36)

        # Validate UUID format with regex
        uuid_pattern = r"TEST-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        assert re.match(uuid_pattern, patient_id), f"ID {patient_id} does not match UUID format"

    def test_generate_patient_id_uniqueness(self):
        """Test that generated IDs are unique across multiple generations."""
        # Arrange & Act
        ids = {generate_patient_id() for _ in range(1000)}

        # Assert - all IDs should be unique
        assert len(ids) == 1000, "Generated IDs contain duplicates"

    def test_generate_patient_id_deterministic_same_seed(self):
        """Test that same seed produces same sequence of IDs."""
        # Arrange
        seed = 42
        num_ids = 10

        # Act - generate IDs with same seed twice
        reset_generated_ids()
        ids1 = [generate_patient_id(seed=seed) for _ in range(num_ids)]

        reset_generated_ids()
        ids2 = [generate_patient_id(seed=seed) for _ in range(num_ids)]

        # Assert - sequences should be identical
        assert ids1 == ids2, "Same seed should produce identical ID sequences"

    def test_generate_patient_id_different_seeds_produce_different_sequences(self):
        """Test that different seeds produce different ID sequences."""
        # Arrange
        num_ids = 10

        # Act - generate IDs with different seeds
        reset_generated_ids()
        ids_seed1 = [generate_patient_id(seed=42) for _ in range(num_ids)]

        reset_generated_ids()
        ids_seed2 = [generate_patient_id(seed=99) for _ in range(num_ids)]

        # Assert - sequences should be different
        assert ids_seed1 != ids_seed2, "Different seeds should produce different ID sequences"

    def test_generate_patient_id_without_seed_produces_random_ids(self):
        """Test that generation without seed produces random (different) IDs each time."""
        # Arrange
        num_ids = 10

        # Act - generate IDs without seed twice
        reset_generated_ids()
        ids1 = [generate_patient_id() for _ in range(num_ids)]

        reset_generated_ids()
        ids2 = [generate_patient_id() for _ in range(num_ids)]

        # Assert - sequences should be different (with extremely high probability)
        assert ids1 != ids2, "Random generation should produce different sequences"

    def test_generate_patient_id_tracks_generated_ids(self):
        """Test that generated IDs are tracked to prevent duplicates."""
        # Arrange
        seed = 12345
        num_ids = 5

        # Act - generate IDs without resetting
        ids = [generate_patient_id(seed=seed) for _ in range(num_ids)]

        # Assert - all IDs should be unique (tracking prevents duplicates)
        assert len(set(ids)) == num_ids, "Tracking should prevent duplicate IDs"

    def test_generate_patient_id_with_seed_zero(self):
        """Test that seed=0 is valid and produces deterministic IDs."""
        # Arrange
        seed = 0
        num_ids = 5

        # Act
        reset_generated_ids()
        ids1 = [generate_patient_id(seed=seed) for _ in range(num_ids)]

        reset_generated_ids()
        ids2 = [generate_patient_id(seed=seed) for _ in range(num_ids)]

        # Assert - seed=0 should work and be deterministic
        assert ids1 == ids2, "Seed=0 should produce deterministic IDs"
        assert all(id.startswith(f"{ID_PREFIX}-") for id in ids1)

    def test_generate_patient_id_large_batch(self):
        """Test generating large batch of IDs for performance and uniqueness."""
        # Arrange
        num_ids = 5000

        # Act
        ids = [generate_patient_id() for _ in range(num_ids)]

        # Assert
        assert len(set(ids)) == num_ids, f"Expected {num_ids} unique IDs"
        assert all(re.match(r"TEST-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", id) for id in ids)


class TestResetGeneratedIds:
    """Test suite for reset_generated_ids function."""

    def test_reset_generated_ids_clears_tracking(self):
        """Test that reset clears the tracking set."""
        # Arrange - generate some IDs
        id1 = generate_patient_id(seed=100)

        # Act - reset and generate with same seed
        reset_generated_ids()
        id2 = generate_patient_id(seed=100)

        # Assert - should get same ID since tracking was reset
        assert id1 == id2, "Reset should clear tracking and allow same ID with same seed"

    def test_reset_generated_ids_allows_fresh_generation(self):
        """Test that reset allows starting fresh with ID generation."""
        # Arrange - generate IDs
        first_batch = [generate_patient_id(seed=200) for _ in range(5)]

        # Act - reset and generate again with same seed
        reset_generated_ids()
        second_batch = [generate_patient_id(seed=200) for _ in range(5)]

        # Assert - batches should be identical (same seed, fresh tracking)
        assert first_batch == second_batch, "Reset should allow identical generation with same seed"

    def test_reset_generated_ids_multiple_times(self):
        """Test that reset can be called multiple times safely."""
        # Arrange & Act & Assert - should not raise errors
        reset_generated_ids()
        reset_generated_ids()
        reset_generated_ids()

        # Should still be able to generate IDs
        id = generate_patient_id()
        assert id.startswith(f"{ID_PREFIX}-")


class TestIdGeneratorEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Reset generated IDs before each test."""
        reset_generated_ids()

    def test_generate_patient_id_with_negative_seed(self):
        """Test that negative seeds work correctly."""
        # Arrange
        seed = -42
        num_ids = 5

        # Act
        reset_generated_ids()
        ids1 = [generate_patient_id(seed=seed) for _ in range(num_ids)]

        reset_generated_ids()
        ids2 = [generate_patient_id(seed=seed) for _ in range(num_ids)]

        # Assert - negative seed should still be deterministic
        assert ids1 == ids2, "Negative seed should produce deterministic IDs"

    def test_generate_patient_id_with_large_seed(self):
        """Test that large seed values work correctly."""
        # Arrange
        seed = 999999999

        # Act & Assert - should not raise errors
        patient_id = generate_patient_id(seed=seed)
        assert patient_id.startswith(f"{ID_PREFIX}-")
        assert len(patient_id) == 41

    def test_generate_patient_id_format_consistency(self):
        """Test that all generated IDs consistently match format."""
        # Arrange
        num_tests = 100
        uuid_pattern = r"TEST-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

        # Act
        ids = [generate_patient_id() for _ in range(num_tests)]

        # Assert - all should match format
        for id in ids:
            assert re.match(uuid_pattern, id), f"ID {id} does not match expected format"
            assert id.startswith(f"{ID_PREFIX}-")
            assert len(id) == 41
