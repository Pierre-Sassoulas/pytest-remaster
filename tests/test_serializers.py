"""Tests for the built-in serializer factories."""

from __future__ import annotations

import pytest


def test_json_serializer(pytester: pytest.Pytester) -> None:
    """json_serializer() writes sorted, indented JSON that json.loads round-trips."""
    pytester.makepyfile(
        """
        import json
        from pytest_remaster import json_serializer

        def test_serializer(golden_master, tmp_path):
            expected = tmp_path / "expected.json"
            expected.write_text('{\\n  "a": 1,\\n  "b": [2.5]\\n}\\n')
            golden_master.check(
                {"b": [2.5], "a": 1},
                expected,
                serializer=json_serializer(),
                deserializer=json.loads,
                matcher=lambda actual, golden: actual == golden,
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)
