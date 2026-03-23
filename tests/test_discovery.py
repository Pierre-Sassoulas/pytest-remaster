"""Tests for test case discovery."""

from __future__ import annotations

import pytest


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
            # Returns pytest.param objects; extract the path from .values[0]
            names = [c.values[0].input.name for c in cases]
            assert sorted(names) == ["b", "case1", "case2"]

            # CaseData.expected() works for directory cases
            case = cases[0].values[0]
            assert case.expected(0).name == "expected_0"
            assert case.expected(1, ".txt").name == "expected_1.txt"
            # IDs are relative paths
            ids = [c.id for c in cases]
            assert sorted(ids) == ["a/case1", "a/case2", "b"]

            # Custom is_case: directory with a subdirectory is still a case
            (tmp_path / "c").mkdir()
            (tmp_path / "c" / "input.py").write_text("pass")
            (tmp_path / "c" / "subpkg").mkdir()
            (tmp_path / "c" / "subpkg" / "__init__.py").write_text("")
            custom = discover_test_cases(
                tmp_path, is_case=lambda p: any(p.glob("*.py"))
            )
            custom_names = [c.values[0].input.name for c in custom]
            assert "c" in custom_names
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
            # Returns pytest.param objects; extract the path from .values[0]
            names = [p.values[0].input.name for p in py_files]
            assert sorted(names) == ["a.py", "c.py"]

            # CaseData.expected() works for file cases
            case = py_files[0].values[0]
            assert case.expected(suffix=".txt").name == "a.txt"
            # IDs are relative paths
            ids = [p.id for p in py_files]
            assert sorted(ids) == ["a.py", "sub/c.py"]
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
