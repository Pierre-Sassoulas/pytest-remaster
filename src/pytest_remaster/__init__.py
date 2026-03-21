"""Golden master testing for pytest with automatic regeneration."""

from pytest_remaster.core import (  # pragma: no cover
    GoldenMaster,
    discover_test_cases,
    discover_test_files,
)

__all__ = [
    "GoldenMaster",
    "discover_test_cases",
    "discover_test_files",
]  # pragma: no cover
