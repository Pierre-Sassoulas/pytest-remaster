"""Golden master testing for pytest with automatic regeneration."""

from pytest_remaster.core import (
    CaseFixtures,
    GoldenMaster,
    discover_test_cases,
    discover_test_files,
)

__all__ = [
    "CaseFixtures",
    "GoldenMaster",
    "discover_test_cases",
    "discover_test_files",
]
