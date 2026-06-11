"""Tests for the collecting() failure-aggregation context manager."""

from __future__ import annotations

import pytest


def test_collecting_reports_all_mismatches(pytester: pytest.Pytester) -> None:
    """Every failing check() inside collecting() is reported in one failure."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_collect(golden_master, tmp_path):
            (tmp_path / "a.txt").write_text("old a\\n")
            (tmp_path / "b.txt").write_text("old b\\n")
            with golden_master.collecting():
                golden_master.check("new a", tmp_path / "a.txt")
                golden_master.check("new b", tmp_path / "b.txt")
                golden_master.check("c", tmp_path / "missing.txt")
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*3 golden master mismatches:*",
        "*Mismatch at *a.txt:*",
        "*Mismatch at *b.txt:*",
        "*Expected file *missing.txt does not exist*",
    ])


def test_collecting_all_pass(pytester: pytest.Pytester) -> None:
    """collecting() is a no-op when every check() matches."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_collect(golden_master, tmp_path):
            (tmp_path / "a.txt").write_text("a\\n")
            (tmp_path / "b.txt").write_text("b\\n")
            with golden_master.collecting():
                golden_master.check("a", tmp_path / "a.txt")
                golden_master.check("b", tmp_path / "b.txt")
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_collecting_single_mismatch_singular(pytester: pytest.Pytester) -> None:
    """A single collected mismatch is reported with a singular header."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_collect(golden_master, tmp_path):
            (tmp_path / "a.txt").write_text("old\\n")
            with golden_master.collecting():
                golden_master.check("new", tmp_path / "a.txt")
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*1 golden master mismatch:*"])


def test_collecting_matcher_detail(pytester: pytest.Pytester) -> None:
    """Matcher AssertionError details from several scenarios are aggregated."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def explain(actual, expected):
            raise AssertionError(f"golden={expected} actual={actual} tol=0.5")

        def test_collect(golden_master, tmp_path):
            (tmp_path / "nominal.txt").write_text("1.0\\n")
            (tmp_path / "degraded.txt").write_text("2.0\\n")
            with golden_master.collecting():
                golden_master.check(3.0, tmp_path / "nominal.txt", matcher=explain)
                golden_master.check(4.0, tmp_path / "degraded.txt", matcher=explain)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*golden=1.0 actual=3.0 tol=0.5*",
        "*golden=2.0 actual=4.0 tol=0.5*",
    ])


def test_collecting_remaster_unaffected(pytester: pytest.Pytester) -> None:
    """In remaster mode, collecting() changes nothing.

    Files are updated and assert_remastered() reports them at teardown.
    """
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_collect(golden_master, tmp_path):
            (tmp_path / "a.txt").write_text("old a\\n")
            (tmp_path / "b.txt").write_text("old b\\n")
            with golden_master.collecting():
                golden_master.check("new a", tmp_path / "a.txt")
                golden_master.check("new b", tmp_path / "b.txt")
            assert (tmp_path / "a.txt").read_text() == "new a\\n"
            assert (tmp_path / "b.txt").read_text() == "new b\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*updated*a.txt*", "*updated*b.txt*"])


def test_collecting_exception_propagates(pytester: pytest.Pytester) -> None:
    """A non-mismatch exception in the body propagates unchanged."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_collect(golden_master, tmp_path):
            (tmp_path / "a.txt").write_text("old\\n")
            with golden_master.collecting():
                golden_master.check("new", tmp_path / "a.txt")
                raise ValueError("simulation crashed")
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ValueError: simulation crashed*"])


def test_collecting_check_all_count_mismatch(pytester: pytest.Pytester) -> None:
    """check_all() count mismatches are collected too."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_collect(golden_master, tmp_path):
            (tmp_path / "expected_0.txt").write_text("a\\n")
            (tmp_path / "expected_1.txt").write_text("b\\n")
            (tmp_path / "other.txt").write_text("old\\n")
            with golden_master.collecting():
                golden_master.check_all(["a"], tmp_path, suffix=".txt")
                golden_master.check("new", tmp_path / "other.txt")
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*2 golden master mismatches:*",
        "*Expected 2 results but got 1*",
        "*Mismatch at *other.txt:*",
    ])


def test_collecting_nested_reports_at_outermost_exit(pytester: pytest.Pytester) -> None:
    """Nested collecting() blocks defer everything to the outermost exit."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_nested(golden_master, tmp_path):
            (tmp_path / "outer.txt").write_text("old\\n")
            (tmp_path / "inner.txt").write_text("old\\n")
            with golden_master.collecting():
                golden_master.check("new", tmp_path / "outer.txt")
                # A helper wrapping its own collecting() must not flush
                # early nor degrade the outer block to fail-fast
                with golden_master.collecting():
                    golden_master.check("new", tmp_path / "inner.txt")
                golden_master.check("new", tmp_path / "missing.txt")
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*3 golden master mismatches:*",
        "*Mismatch at *outer.txt:*",
        "*Mismatch at *inner.txt:*",
        "*missing.txt does not exist*",
    ])
