"""Pytest plugin for golden master testing with automatic expected file regeneration."""

from pytest_remaster.core import (
    CaseData,
    FilePatchRegistry,
    GoldenMaster,
    discover_test_cases,
    discover_test_files,
    json_normalizer,
    whitespace_normalizer,
)

__all__ = [
    "CaseData",
    "FilePatchRegistry",
    "GoldenMaster",
    "discover_test_cases",
    "discover_test_files",
    "json_normalizer",
    "whitespace_normalizer",
]
