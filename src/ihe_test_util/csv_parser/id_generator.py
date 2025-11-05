"""Patient ID auto-generation for test data.

This module provides functionality to generate unique patient IDs for test
scenarios where IDs are not provided in the input CSV.
"""

import logging
import random
import uuid
from typing import Optional, Set


logger = logging.getLogger(__name__)

# Generated IDs use this prefix for easy identification
ID_PREFIX = "TEST"

# Track generated IDs within a batch to ensure uniqueness
_generated_ids: Set[str] = set()

# Maximum attempts to generate a unique ID (collision should be extremely rare)
MAX_GENERATION_ATTEMPTS = 1000


def generate_patient_id(seed: Optional[int] = None) -> str:
    """Generate a unique patient ID in TEST-{UUID} format.

    Creates a unique patient identifier using UUID4 for scenarios where
    patient IDs are not provided in the input data. Supports deterministic
    generation via seed parameter for reproducible test data.

    Args:
        seed: Optional random seed for deterministic ID generation.
              When provided, the same seed will produce the same
              sequence of IDs across runs, enabling reproducible test data.

    Returns:
        Patient ID string in format TEST-{UUID} (e.g., TEST-a1b2c3d4-e5f6-7890-abcd-ef1234567890)

    Raises:
        ValueError: If unable to generate unique ID after maximum attempts
                   (extremely rare, indicates potential system issue)
    """
    attempts = 0

    while attempts < MAX_GENERATION_ATTEMPTS:
        # Generate UUID
        if seed is not None:
            # For deterministic generation, seed the random generator
            # and create UUID from random bits
            random.seed(seed + attempts)
            unique_id = uuid.UUID(int=random.getrandbits(128))
        else:
            # Generate random UUID4
            unique_id = uuid.uuid4()

        patient_id = f"{ID_PREFIX}-{unique_id}"

        # Check for collision (should be extremely rare with UUID4)
        if patient_id not in _generated_ids:
            _generated_ids.add(patient_id)
            logger.debug(f"Generated patient ID: {patient_id}")
            return patient_id

        # If collision detected, log warning and retry
        logger.warning(
            f"ID collision detected for {patient_id}. Regenerating (attempt {attempts + 1})"
        )
        attempts += 1

    # If we exhausted all attempts, raise error with actionable context
    raise ValueError(
        f"Unable to generate unique patient ID after {MAX_GENERATION_ATTEMPTS} attempts. "
        "This is extremely rare and may indicate a system issue. "
        "Try restarting the process or contact support."
    )


def reset_generated_ids() -> None:
    """Reset the set of generated IDs.

    This function is primarily for testing purposes, allowing test cases
    to start with a clean slate. Should be called at the start of each
    batch processing run in production code.
    """
    global _generated_ids
    _generated_ids.clear()
    logger.debug("Reset generated IDs tracking set")
