"""Pytest plugin for golden master testing with automatic expected file regeneration."""

from typing import TYPE_CHECKING, Any

from pytest_remaster.discovery import CaseData, discover_test_cases, discover_test_files
from pytest_remaster.factory import golden_case_test
from pytest_remaster.golden_master import (
    GoldenMaster,
    MalformedTestCase,
    Output,
    json_normalizer,
    json_serializer,
    mock_calls_serializer,
    resolve_with_override,
    whitespace_normalizer,
)
from pytest_remaster.matchers import Tolerance, ToleranceSpec, tolerance_matcher
from pytest_remaster.patching import PatchRegistry

if TYPE_CHECKING:
    from pytest_remaster.pandas_io import dataframe_deserializer, dataframe_serializer

__all__ = [
    "CaseData",
    "GoldenMaster",
    "MalformedTestCase",
    "Output",
    "PatchRegistry",
    "Tolerance",
    "ToleranceSpec",
    "dataframe_deserializer",  # pylint: disable=undefined-all-variable
    "dataframe_serializer",  # pylint: disable=undefined-all-variable
    "discover_test_cases",
    "discover_test_files",
    "golden_case_test",
    "json_normalizer",
    "json_serializer",
    "mock_calls_serializer",
    "resolve_with_override",
    "tolerance_matcher",
    "whitespace_normalizer",
]

_PANDAS_EXPORTS = frozenset({"dataframe_serializer", "dataframe_deserializer"})


def __getattr__(name: str) -> Any:
    """Lazily import pandas helpers so the core package stays stdlib-pure."""
    if name in _PANDAS_EXPORTS:
        try:
            # pylint: disable-next=import-outside-toplevel
            from pytest_remaster import pandas_io
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                f"{name} requires pandas;"
                f" install it with: pip install pytest-remaster[pandas]"
            ) from exc
        return getattr(pandas_io, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
