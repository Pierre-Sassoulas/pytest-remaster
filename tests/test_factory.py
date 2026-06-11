"""Tests for the golden_case_test factory."""

from __future__ import annotations

import pytest


def _make_cases(pytester: pytest.Pytester) -> None:
    cases = pytester.path / "cases"
    (cases / "nominal").mkdir(parents=True)
    (cases / "nominal" / "expected.txt").write_text("alpha\n")
    (cases / "degraded").mkdir()
    (cases / "degraded" / "expected.txt").write_text("beta\n")


def test_factory_runs_each_case_runner_once(pytester: pytest.Pytester) -> None:
    """One pytest node per case directory; the runner executes once."""
    _make_cases(pytester)
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import golden_case_test

        CALLS = Path(__file__).parent / "calls.log"

        def run_all():
            CALLS.open("a").write("call\\n")
            return {"nominal": "alpha", "degraded": "beta"}

        test_cases = golden_case_test(
            Path(__file__).parent / "cases",
            run_all,
            extractors={".txt": lambda r: r},
        )
        """
    )
    result = pytester.runpytest("--no-remaster", "-v")
    result.assert_outcomes(passed=2)
    result.stdout.fnmatch_lines(["*degraded*PASSED*", "*nominal*PASSED*"])
    assert (pytester.path / "calls.log").read_text() == "call\n"


def test_factory_missing_result_fails_clearly(pytester: pytest.Pytester) -> None:
    """A case directory with no runner result names what the runner produced."""
    _make_cases(pytester)
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import golden_case_test

        test_cases = golden_case_test(
            Path(__file__).parent / "cases",
            lambda: {"nominal": "alpha"},
            extractors={".txt": lambda r: r},
        )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1, failed=1)
    # fnmatch treats [ ] as a character class — avoid the bracketed list
    result.stdout.fnmatch_lines([
        "*runner produced no result for case 'degraded'*nominal*"
    ])


def test_factory_drifting_case_does_not_hide_others(pytester: pytest.Pytester) -> None:
    """One case fails on its own node; the other still passes.

    The failing case aggregates all its files via collecting().
    """
    _make_cases(pytester)
    (pytester.path / "cases" / "degraded" / "expected.log").write_text("old\n")
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import Output, golden_case_test

        test_cases = golden_case_test(
            Path(__file__).parent / "cases",
            lambda: {
                "nominal": {"txt": "alpha", "log": ""},
                "degraded": {"txt": "drifted", "log": "new"},
            },
            extractors={
                ".txt": lambda r: r["txt"],
                ".log": lambda r: r["log"],
            },
        )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines([
        "*2 golden master mismatches:*",
        "*Mismatch at *expected.txt:*",
        "*Mismatch at *expected.log:*",
    ])
