"""Tests for the matcher and deserializer hooks of GoldenMaster."""

from __future__ import annotations

import pytest


def test_matcher_within_tolerance_passes(pytester: pytest.Pytester) -> None:
    """check() with matcher passes within tolerance and never touches the file."""
    pytester.makepyfile(
        """
        import math
        from pathlib import Path

        def close(actual, expected):
            golden = [float(x) for x in expected.split()]
            return all(
                math.isclose(a, g, abs_tol=0.5) for a, g in zip(actual, golden)
            ) and len(actual) == len(golden)

        def test_tolerance(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("1.0 2.0\\n")
            golden_master.check(
                [1.1, 2.0],
                expected,
                serializer=lambda vals: " ".join(f"{v:.6g}" for v in vals),
                matcher=close,
            )
            # Within tolerance: golden untouched, no churn even in remaster mode
            assert expected.read_text() == "1.0 2.0\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1)


def test_matcher_beyond_tolerance_fails(pytester: pytest.Pytester) -> None:
    """check() with matcher fails with string diff when matcher returns False."""
    pytester.makepyfile(
        """
        import math
        from pathlib import Path

        def close(actual, expected):
            golden = [float(x) for x in expected.split()]
            return all(
                math.isclose(a, g, abs_tol=0.5) for a, g in zip(actual, golden)
            )

        def test_tolerance(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("1.0 2.0\\n")
            golden_master.check(
                [3.0, 2.0],
                expected,
                serializer=lambda vals: " ".join(f"{v:.6g}" for v in vals),
                matcher=close,
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Mismatch at*", "*--remaster*"])


def test_matcher_assertion_error_detail(pytester: pytest.Pytester) -> None:
    """A matcher raising AssertionError gets its message into the failure.

    The message appears verbatim between the ``Mismatch at`` header and the
    ``--remaster`` hint, *replacing* the unified diff.
    """
    pytester.makepyfile(
        """
        from pathlib import Path

        def explain(actual, expected):
            raise AssertionError("row 3: golden=1.0 actual=3.0 tol=0.5")

        def test_detail(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("1.0\\n")
            golden_master.check([3.0], expected, matcher=explain)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*Mismatch at *expected.txt:*",
        "*row 3: golden=1.0 actual=3.0 tol=0.5*",
        "*Run with --remaster to update *expected.txt*",
    ])
    # The AssertionError message replaces the unified diff
    result.stdout.no_fnmatch_line("*+++ actual*")


def test_matcher_mismatch_remaster_rewrites(pytester: pytest.Pytester) -> None:
    """check() with matcher rewrites the golden in remaster mode (bless flow)."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_bless(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("1.0\\n")
            golden_master.check(
                [3.0],
                expected,
                serializer=lambda vals: " ".join(f"{v:.6g}" for v in vals),
                matcher=lambda actual, exp: False,
            )
            # Rewritten with the serializer output
            assert expected.read_text() == "3\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*updated*please review*", "*updated: *expected.txt*"])


def test_matcher_with_deserializer(pytester: pytest.Pytester) -> None:
    """Deserializer parses the expected file before the matcher sees it."""
    pytester.makepyfile(
        """
        import json
        import math
        from pathlib import Path

        def close(actual, expected):
            # actual arrives unserialized, expected deserialized from file text
            assert isinstance(actual, dict)
            assert isinstance(expected, dict)
            return all(
                math.isclose(actual[k], expected[k], abs_tol=0.5) for k in expected
            ) and actual.keys() == expected.keys()

        def test_deserializer(golden_master, tmp_path):
            expected = tmp_path / "expected.json"
            expected.write_text('{"w_bess_kw": 1.0}\\n')
            golden_master.check(
                {"w_bess_kw": 1.2},
                expected,
                serializer=json.dumps,
                deserializer=json.loads,
                matcher=close,
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_matcher_missing_file_no_remaster(pytester: pytest.Pytester) -> None:
    """check() with matcher and missing golden fails without calling the matcher."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def boom(actual, expected):
            raise RuntimeError("matcher must not be called when golden is missing")

        def test_missing(golden_master, tmp_path):
            golden_master.check([1.0], tmp_path / "expected.txt", matcher=boom)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*does not exist*--remaster*"])
    result.stdout.no_fnmatch_line("*matcher must not be called*")


def test_matcher_normalizer_mutually_exclusive(pytester: pytest.Pytester) -> None:
    """check() rejects matcher combined with normalizer."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_exclusive(golden_master, tmp_path):
            try:
                golden_master.check(
                    "x",
                    tmp_path / "expected.txt",
                    normalizer=str.strip,
                    matcher=lambda a, e: True,
                )
                assert False, "should have raised"
            except ValueError as exc:
                assert "mutually exclusive" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_deserializer_requires_matcher(pytester: pytest.Pytester) -> None:
    """check() rejects deserializer without matcher."""
    pytester.makepyfile(
        """
        import json
        from pathlib import Path

        def test_requires(golden_master, tmp_path):
            try:
                golden_master.check(
                    "x", tmp_path / "expected.txt", deserializer=json.loads
                )
                assert False, "should have raised"
            except ValueError as exc:
                assert "deserializer requires matcher" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_deserializer_receives_rstripped_text(pytester: pytest.Pytester) -> None:
    """The deserializer gets the golden file text already rstrip()-ed."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def parse(text):
            assert text == "1.0", repr(text)
            return float(text)

        def test_rstrip(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("1.0  \\n\\n")
            golden_master.check(
                1.0, expected, deserializer=parse, matcher=lambda a, e: a == e
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_matcher_bless_round_trip(pytester: pytest.Pytester) -> None:
    """Blessing writes serializer(actual).rstrip() + newline.

    A strict re-check then passes through deserializer + matcher
    (the storage round-trip).
    """
    pytester.makepyfile(
        """
        import math
        from pathlib import Path
        from pytest_remaster import GoldenMaster

        def serialize(vals):
            return " ".join(f"{v:.6g}" for v in vals) + "\\n"

        def parse(text):
            return [float(x) for x in text.split()]

        def close(actual, expected):
            return len(actual) == len(expected) and all(
                math.isclose(a, e, rel_tol=1e-4) for a, e in zip(actual, expected)
            )

        def test_round_trip(tmp_path):
            expected = tmp_path / "expected.txt"
            actual = [1.25, 2.0]

            blesser = GoldenMaster(remaster=True)
            blesser.check(
                actual, expected, serializer=serialize, deserializer=parse,
                matcher=close,
            )
            assert expected.read_text() == "1.25 2\\n"

            checker = GoldenMaster(remaster=False)
            checker.check(
                actual, expected, serializer=serialize, deserializer=parse,
                matcher=close,
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_all_with_matcher(pytester: pytest.Pytester) -> None:
    """check_all() forwards matcher and deserializer to each check."""
    pytester.makepyfile(
        """
        import math
        from pathlib import Path

        def test_all(golden_master, tmp_path):
            (tmp_path / "expected_0.txt").write_text("1.0\\n")
            (tmp_path / "expected_1.txt").write_text("2.0\\n")
            golden_master.check_all(
                [1.2, 2.1],
                tmp_path,
                serializer=lambda v: f"{v:.6g}",
                deserializer=float,
                matcher=lambda a, e: math.isclose(a, e, abs_tol=0.5),
                suffix=".txt",
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)
