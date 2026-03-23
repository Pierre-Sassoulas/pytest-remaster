"""Pytest plugin for golden master testing with automatic expected file regeneration."""

from pytest_remaster.discovery import (
    CaseData,
    discover_test_cases,
    discover_test_files,
)
from pytest_remaster.golden_master import (
    GoldenMaster,
    MalformedTestCase,
    json_normalizer,
    whitespace_normalizer,
)
from pytest_remaster.patching import PatchRegistry

__all__ = [
    "CaseData",
    "GoldenMaster",
    "MalformedTestCase",
    "PatchRegistry",
    "discover_test_cases",
    "discover_test_files",
    "json_normalizer",
    "whitespace_normalizer",
]
