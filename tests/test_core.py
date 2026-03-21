"""Tests for the core golden master logic."""

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
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*updated*review and relaunch*"])


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
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*created*review and relaunch*"])


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


def test_check_all_match(pytester: pytest.Pytester) -> None:
    """check_all() passes when all results match."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_match(golden_master, tmp_path):
            (tmp_path / "result_0").write_text("first\\n")
            (tmp_path / "result_1").write_text("second\\n")
            golden_master.check_all("first", "second", directory=tmp_path)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_all_callable(pytester: pytest.Pytester) -> None:
    """check_all() accepts a callable returning a list."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_callable(golden_master, tmp_path):
            (tmp_path / "result_0").write_text("a\\n")
            (tmp_path / "result_1").write_text("b\\n")
            golden_master.check_all(lambda: ["a", "b"], directory=tmp_path)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_check_all_fewer_actuals_remaster(pytester: pytest.Pytester) -> None:
    """check_all() with remaster removes extra result files."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fewer(golden_master, tmp_path):
            (tmp_path / "result_0").write_text("only\\n")
            (tmp_path / "result_1").write_text("extra\\n")
            golden_master.check_all("only", directory=tmp_path)
        """
    )
    result = pytester.runpytest("--remaster")
    # result_1 is removed, result_0 matches so no update needed
    result.assert_outcomes(passed=1)


def test_check_all_more_actuals_remaster(pytester: pytest.Pytester) -> None:
    """check_all() with remaster creates new result files."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_more(golden_master, tmp_path):
            (tmp_path / "result_0").write_text("first\\n")
            golden_master.check_all("first", "second", directory=tmp_path)
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*created*"])


def test_check_all_count_mismatch_no_remaster(pytester: pytest.Pytester) -> None:
    """check_all() without remaster fails on count mismatch."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_count(golden_master, tmp_path):
            (tmp_path / "result_0").write_text("first\\n")
            (tmp_path / "result_1").write_text("second\\n")
            (tmp_path / "result_2").write_text("third\\n")
            golden_master.check_all("first", directory=tmp_path)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Expected 3 results but got 1*"])


def test_discover_test_cases(pytester: pytest.Pytester) -> None:
    """discover_test_cases() finds leaf directories."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import discover_test_cases

        def test_discover(tmp_path):
            # Create hierarchy: base/a/case1/ and base/a/case2/ and base/b/
            (tmp_path / "a" / "case1").mkdir(parents=True)
            (tmp_path / "a" / "case1" / "command").write_text("hello")
            (tmp_path / "a" / "case2").mkdir(parents=True)
            (tmp_path / "a" / "case2" / "command").write_text("bye")
            (tmp_path / "b").mkdir()
            (tmp_path / "b" / "command").write_text("help")

            cases = discover_test_cases(tmp_path)
            names = [c.name for c in cases]
            assert sorted(names) == ["b", "case1", "case2"]
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_discover_test_files(pytester: pytest.Pytester) -> None:
    """discover_test_files() finds files matching a pattern."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import discover_test_files

        def test_discover(tmp_path):
            (tmp_path / "a.py").write_text("pass")
            (tmp_path / "b.txt").write_text("hello")
            (tmp_path / "sub").mkdir()
            (tmp_path / "sub" / "c.py").write_text("pass")

            py_files = discover_test_files(tmp_path, "*.py")
            names = [f.name for f in py_files]
            assert sorted(names) == ["a.py", "c.py"]
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
