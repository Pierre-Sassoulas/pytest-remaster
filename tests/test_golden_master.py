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


def test_resolve_with_override_exists(pytester: pytest.Pytester) -> None:
    """resolve_with_override returns override when it exists."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import resolve_with_override

        def test_resolve(tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("base\\n")
            override.write_text("override\\n")
            assert resolve_with_override(base, override) == override
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_resolve_with_override_missing(pytester: pytest.Pytester) -> None:
    """resolve_with_override returns base when override doesn't exist."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import resolve_with_override

        def test_resolve(tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("base\\n")
            assert resolve_with_override(base, override) == base
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_resolve_with_override_none(pytester: pytest.Pytester) -> None:
    """resolve_with_override returns base when override is None."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import resolve_with_override

        def test_resolve(tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("base\\n")
            assert resolve_with_override(base) == base
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_override_exists_and_matches(pytester: pytest.Pytester) -> None:
    """check() with override_path uses override when it exists and matches."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_override(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            override.write_text("version-specific output\\n")
            golden_master.check(
                "version-specific output", base, override_path=override
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_override_missing_falls_back_to_base(pytester: pytest.Pytester) -> None:
    """check() with override_path falls back to base when override missing."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fallback(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            golden_master.check("generic output", base, override_path=override)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_override_mismatch_remaster_writes_override(pytester: pytest.Pytester) -> None:
    """check() remasters to override_path, not base."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            golden_master.check("new output", base, override_path=override)
            # Override created, base untouched
            assert override.read_text() == "new output\\n"
            assert base.read_text() == "generic output\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*a.314.txt*"])


def test_override_exists_mismatch_remaster(pytester: pytest.Pytester) -> None:
    """check() updates existing override, not base."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            override.write_text("old 3.14 output\\n")
            golden_master.check("new 3.14 output", base, override_path=override)
            assert override.read_text() == "new 3.14 output\\n"
            assert base.read_text() == "generic output\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*updated*a.314.txt*"])


def test_override_mismatch_no_remaster_hints_override(
    pytester: pytest.Pytester,
) -> None:
    """check() strict mode hints at creating override_path."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_hint(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            golden_master.check("new output", base, override_path=override)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*--remaster*a.314.txt*"])


def test_override_redundant_remaster_deletes(pytester: pytest.Pytester) -> None:
    """check() in remaster mode deletes override identical to base."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_dedup(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("same content\\n")
            override.write_text("same content\\n")
            golden_master.check("same content", base, override_path=override)
            assert not override.exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*deleted*redundant*a.314.txt*"])


def test_override_redundant_no_remaster_fails(pytester: pytest.Pytester) -> None:
    """check() in strict mode fails when override is identical to base."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_dedup(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("same content\\n")
            override.write_text("same content\\n")
            golden_master.check("same content", base, override_path=override)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*identical*redundant*"])


def test_override_remaster_dedup_after_write(pytester: pytest.Pytester) -> None:
    """After remastering override, if it matches base, it gets removed."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_dedup_after_write(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            # Base already has the "new" content; override will be written
            # with same content then deduped
            base.write_text("new output\\n")
            override.write_text("old output\\n")
            golden_master.check("new output", base, override_path=override)
            assert not override.exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*deleted*redundant*a.314.txt*"])


def test_override_no_base_creates_override(pytester: pytest.Pytester) -> None:
    """check() creates override when neither base nor override exist."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_no_base(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            golden_master.check("new output", base, override_path=override)
            assert override.read_text() == "new output\\n"
            assert not base.exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*a.314.txt*"])


def test_build_override_chain(pytester: pytest.Pytester) -> None:
    """_build_override_chain generates powerset in priority order."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster.golden_master import _build_override_chain

        def test_chain():
            chain = _build_override_chain(
                Path("/d/a.txt"), version="312", platform="linux",
            )
            names = [p.name for p in chain]
            assert names == [
                "a.312.linux.txt",
                "a.312.txt",
                "a.linux.txt",
            ]
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_build_override_chain_three_dimensions(pytester: pytest.Pytester) -> None:
    """_build_override_chain with three dimensions produces 7 entries."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster.golden_master import _build_override_chain

        def test_chain():
            chain = _build_override_chain(
                Path("/d/a.txt"),
                version="312", platform="linux", implementation="cpython",
            )
            names = [p.name for p in chain]
            assert names == [
                "a.312.linux.cpython.txt",
                "a.312.linux.txt",
                "a.312.cpython.txt",
                "a.linux.cpython.txt",
                "a.312.txt",
                "a.linux.txt",
                "a.cpython.txt",
            ]
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_dimensions_resolves_most_specific(pytester: pytest.Pytester) -> None:
    """check() with dimensions uses the most specific existing file."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_resolve(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            specific = tmp_path / "a.312.linux.txt"
            specific.write_text("specific\\n")
            golden_master.check(
                "specific", base,
                dimensions={"version": "312", "platform": "linux"},
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_dimensions_falls_back_to_less_specific(pytester: pytest.Pytester) -> None:
    """check() with dimensions falls back through the chain."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fallback(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            # Only version-specific exists, no version+platform
            version_only = tmp_path / "a.312.txt"
            version_only.write_text("version output\\n")
            golden_master.check(
                "version output", base,
                dimensions={"version": "312", "platform": "linux"},
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_dimensions_falls_back_to_base(pytester: pytest.Pytester) -> None:
    """check() with dimensions falls back to base when no overrides exist."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fallback(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            golden_master.check(
                "generic", base,
                dimensions={"version": "312", "platform": "linux"},
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_dimensions_remaster_writes_most_specific(pytester: pytest.Pytester) -> None:
    """check() with dimensions remasters to the most specific path."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            golden_master.check(
                "new output", base,
                dimensions={"version": "312", "platform": "linux"},
            )
            most_specific = tmp_path / "a.312.linux.txt"
            assert most_specific.read_text() == "new output\\n"
            assert base.read_text() == "generic\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*a.312.linux.txt*"])


def test_dimensions_dedup_against_less_specific(pytester: pytest.Pytester) -> None:
    """check() deduplicates against less-specific existing overrides."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_dedup(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            # Both overrides have the same content
            (tmp_path / "a.312.linux.txt").write_text("same\\n")
            (tmp_path / "a.312.txt").write_text("same\\n")
            golden_master.check(
                "same", base,
                dimensions={"version": "312", "platform": "linux"},
            )
            # Most specific removed because it matches less specific
            assert not (tmp_path / "a.312.linux.txt").exists()
            assert (tmp_path / "a.312.txt").exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*deleted*redundant*a.312.linux.txt*"])


def test_dimensions_new_test_creates_base_file(pytester: pytest.Pytester) -> None:
    """check() with dimensions creates the base file for new tests (no files exist)."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_new(golden_master, tmp_path):
            base = tmp_path / "test.txt"
            golden_master.check(
                "new output", base,
                dimensions={"version": "314", "platform": "linux"},
            )
            # Base file should be created, not the most specific override
            assert base.read_text() == "new output\\n"
            assert not (tmp_path / "test.314.linux.txt").exists()
            assert not (tmp_path / "test.314.txt").exists()
            assert not (tmp_path / "test.linux.txt").exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*test.txt*"])


def test_dimensions_mutually_exclusive_with_override_path(
    pytester: pytest.Pytester,
) -> None:
    """check() raises ValueError when both override_path and dimensions given."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_exclusive(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("content\\n")
            try:
                golden_master.check(
                    "content", base,
                    override_path=tmp_path / "a.312.txt",
                    dimensions={"version": "312"},
                )
                assert False, "should have raised"
            except ValueError as exc:
                assert "mutually exclusive" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


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
