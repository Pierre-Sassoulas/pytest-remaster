"""Tests for the GoldenMaster comparison logic."""

from __future__ import annotations

import pytest


def test_check_match(pytester: pytest.Pytester) -> None:
    """check() passes when actual matches expected."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_match(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("hello world\\n")
            golden_master.check("hello world", expected)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_mismatch_remaster(pytester: pytest.Pytester) -> None:
    """check() with remaster writes new content and fails."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_mismatch(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("old content\\n")
            golden_master.check("new content", expected)
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*updated*please review*"])


def test_check_multiple_remaster(pytester: pytest.Pytester) -> None:
    """Multiple check() calls in remaster mode update all files in one pass."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_multi(golden_master, tmp_path):
            a = tmp_path / "a.txt"
            b = tmp_path / "b.txt"
            a.write_text("old a\\n")
            b.write_text("old b\\n")
            golden_master.check("new a", a)
            golden_master.check("new b", b)
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    # Both files updated in a single failure
    result.stdout.fnmatch_lines(["*updated*a.txt*", "*updated*b.txt*"])


def test_check_mismatch_no_remaster(pytester: pytest.Pytester) -> None:
    """check() without remaster fails with diff."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_mismatch(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("old content\\n")
            golden_master.check("new content", expected)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*mismatch*"])


def test_check_mismatch_truncated(pytester: pytest.Pytester) -> None:
    """check() truncates large diffs based on truncation_limit_lines."""
    pytester.makeini(
        """
        [pytest]
        truncation_limit_lines = 8
        truncation_limit_chars = 640
        """
    )
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_big_diff(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            # 50 lines of "old" content
            expected.write_text("\\n".join(f"old line {i}" for i in range(50)) + "\\n")
            # 50 lines of "new" content
            actual = "\\n".join(f"new line {i}" for i in range(50))
            golden_master.check(actual, expected)
        """
    )
    result = pytester.runpytest("--no-remaster", "--tb=short")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*diff truncated*lines hidden*use '-vv' to show*"])


def test_check_mismatch_not_truncated_with_vv(pytester: pytest.Pytester) -> None:
    """check() shows full diff with -vv."""
    pytester.makeini(
        """
        [pytest]
        truncation_limit_lines = 8
        truncation_limit_chars = 640
        """
    )
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_big_diff(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("\\n".join(f"old line {i}" for i in range(50)) + "\\n")
            actual = "\\n".join(f"new line {i}" for i in range(50))
            golden_master.check(actual, expected)
        """
    )
    result = pytester.runpytest("--no-remaster", "-vv", "--tb=short")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*new line 49*"])
    result.stdout.no_fnmatch_line("*diff truncated*")


def test_check_missing_file_remaster(pytester: pytest.Pytester) -> None:
    """check() with remaster creates missing file and fails."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_missing(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            golden_master.check("new content", expected)
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*please review*", "*created*"])


def test_check_empty_actual_deletes_file(pytester: pytest.Pytester) -> None:
    """check() with remaster deletes expected file when actual is empty."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_delete(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("old content\\n")
            golden_master.check("", expected)
            # File should be deleted after teardown triggers
            assert not expected.exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*deleted*"])


def test_check_empty_actual_no_file(pytester: pytest.Pytester) -> None:
    """check() passes when actual is empty and no expected file exists."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_both_empty(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            golden_master.check("", expected)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_missing_file_no_remaster(pytester: pytest.Pytester) -> None:
    """check() without remaster fails when file missing."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_missing(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            golden_master.check("new content", expected)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*does not exist*--remaster*"])


def test_check_callable(pytester: pytest.Pytester) -> None:
    """check() accepts a callable and calls it."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_callable(golden_master, tmp_path):
            expected = tmp_path / "expected.txt"
            expected.write_text("hello\\n")
            golden_master.check(lambda: "hello", expected)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_json_normalizer(pytester: pytest.Pytester) -> None:
    """json_normalizer ignores formatting differences in JSON files."""
    pytester.makepyfile(
        """
        import json
        from pathlib import Path
        from pytest_remaster import json_normalizer

        def test_json_norm(golden_master, tmp_path):
            # prettier-style: compact, no trailing newline
            expected = tmp_path / "data.json"
            expected.write_text('{ "b": 2, "a": [1, 2, 3] }\\n')
            # json.dumps style: different formatting, different key order
            actual = json.dumps({"a": [1, 2, 3], "b": 2}, indent=4)
            golden_master.check(actual, expected, normalizer=json_normalizer)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_whitespace_normalizer(pytester: pytest.Pytester) -> None:
    """whitespace_normalizer ignores trailing whitespace and line endings."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import whitespace_normalizer

        def test_ws(golden_master, tmp_path):
            expected = tmp_path / "output.txt"
            expected.write_text("hello  \\r\\nworld  \\n")
            golden_master.check(
                "hello\\nworld",
                expected,
                normalizer=whitespace_normalizer,
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_normalizer_explicit(pytester: pytest.Pytester) -> None:
    """check() accepts an explicit normalizer."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_normalizer(golden_master, tmp_path):
            expected = tmp_path / "output.txt"
            expected.write_text("  HELLO  WORLD  \\n")
            golden_master.check(
                "hello world",
                expected,
                normalizer=lambda s: " ".join(s.lower().split()),
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_serializer(pytester: pytest.Pytester) -> None:
    """check() uses custom serializer."""
    pytester.makepyfile(
        """
        import json
        from pathlib import Path

        def test_serializer(golden_master, tmp_path):
            expected = tmp_path / "expected.json"
            expected.write_text('{"key": "value"}\\n')
            golden_master.check(
                {"key": "value"}, expected,
                serializer=lambda o: json.dumps(o, sort_keys=True),
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_mock_calls_serializer(pytester: pytest.Pytester) -> None:
    """mock_calls_serializer formats call_args_list as diffable text."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from unittest.mock import MagicMock
        from pytest_remaster import mock_calls_serializer

        def test_serializer(golden_master, tmp_path):
            mock = MagicMock()
            mock("arg1", "arg2", key="value")
            mock("only_pos")
            mock(flag=True)

            expected = tmp_path / "expected_calls"
            expected.write_text(
                "fn('arg1', 'arg2', key='value')\\n"
                "fn('only_pos')\\n"
                "fn(flag=True)\\n"
            )
            golden_master.check(
                mock.call_args_list,
                expected,
                serializer=mock_calls_serializer("fn"),
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_mock_calls_serializer_empty(pytester: pytest.Pytester) -> None:
    """mock_calls_serializer returns empty string when no calls."""
    pytester.makepyfile(
        """
        from unittest.mock import MagicMock
        from pytest_remaster import mock_calls_serializer

        def test_empty(golden_master, tmp_path):
            mock = MagicMock()
            expected = tmp_path / "expected_calls"
            # No calls, no file — check() skips both-empty case
            golden_master.check(
                mock.call_args_list,
                expected,
                serializer=mock_calls_serializer("fn"),
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_directory_match(pytester: pytest.Pytester) -> None:
    """check_all() passes when all results match."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_match(golden_master, tmp_path):
            (tmp_path / "expected_0").write_text("first\\n")
            (tmp_path / "expected_1").write_text("second\\n")
            golden_master.check_all(["first", "second"], tmp_path)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_directory_with_suffix(pytester: pytest.Pytester) -> None:
    """check_all() with suffix uses expected_0.json, etc."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_suffix(golden_master, tmp_path):
            (tmp_path / "expected_0.json").write_text('{"a": 1}\\n')
            (tmp_path / "expected_1.json").write_text('{"b": 2}\\n')
            golden_master.check_all(
                ['{"a": 1}', '{"b": 2}'], tmp_path, suffix=".json"
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_directory_callable(pytester: pytest.Pytester) -> None:
    """check_all() accepts a callable returning a list."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_callable(golden_master, tmp_path):
            (tmp_path / "expected_0").write_text("a\\n")
            (tmp_path / "expected_1").write_text("b\\n")
            golden_master.check_all(lambda: ["a", "b"], tmp_path)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_directory_fewer_actuals_remaster(pytester: pytest.Pytester) -> None:
    """check_all() with remaster removes extra expected files."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fewer(golden_master, tmp_path):
            (tmp_path / "expected_0").write_text("only\\n")
            (tmp_path / "expected_1").write_text("extra\\n")
            golden_master.check_all(["only"], tmp_path)
        """
    )
    result = pytester.runpytest("--remaster")
    # expected_1 is removed after checks pass, reported at teardown
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*deleted*expected_1*"])


def test_check_directory_more_actuals_remaster(pytester: pytest.Pytester) -> None:
    """check_all() with remaster creates new expected files."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_more(golden_master, tmp_path):
            (tmp_path / "expected_0").write_text("first\\n")
            golden_master.check_all(["first", "second"], tmp_path)
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*"])


def test_check_directory_count_mismatch_no_remaster(pytester: pytest.Pytester) -> None:
    """check_all() without remaster fails on count mismatch."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_count(golden_master, tmp_path):
            (tmp_path / "expected_0").write_text("first\\n")
            (tmp_path / "expected_1").write_text("second\\n")
            (tmp_path / "expected_2").write_text("third\\n")
            golden_master.check_all(["first"], tmp_path)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Expected 3 results but got 1*"])


def test_malformed_test_case_check_callable(pytester: pytest.Pytester) -> None:
    """check() with callable wraps FileNotFoundError as MalformedTestCase."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import MalformedTestCase

        def test_malformed(golden_master, tmp_path):
            case_dir = tmp_path / "case"
            case_dir.mkdir()
            expected = case_dir / "expected.txt"
            expected.write_text("hello\\n")

            def bad_callable():
                return (case_dir / "missing_input").read_text()

            try:
                golden_master.check(bad_callable, expected)
                assert False, "should have raised"
            except MalformedTestCase as exc:
                assert "missing_input" in str(exc)
                assert "malformed" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_malformed_test_case_check_all(pytester: pytest.Pytester) -> None:
    """check_all() with callable wraps FileNotFoundError as MalformedTestCase."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import MalformedTestCase

        def test_malformed(golden_master, tmp_path):
            case_dir = tmp_path / "case"
            case_dir.mkdir()

            def bad_callable():
                return [(case_dir / "missing_input").read_text()]

            try:
                golden_master.check_all(bad_callable, case_dir)
                assert False, "should have raised"
            except MalformedTestCase as exc:
                assert "missing_input" in str(exc)
                assert "malformed" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_malformed_test_case_check_each(pytester: pytest.Pytester) -> None:
    """check_each() wraps runner FileNotFoundError as MalformedTestCase."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import CaseData, MalformedTestCase

        def test_malformed(golden_master, tmp_path):
            case_dir = tmp_path / "case"
            case_dir.mkdir()
            case = CaseData(input=case_dir)

            def bad_runner(case):
                return (case.input / "missing_input").read_text()

            try:
                golden_master.check_each(
                    case,
                    runner=bad_runner,
                    extractors={".stdout": lambda r: r},
                )
                assert False, "should have raised"
            except MalformedTestCase as exc:
                assert "missing_input" in str(exc)
                assert "case" in str(exc)
                assert "malformed" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)
