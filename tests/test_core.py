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
    # expected_1 is removed, expected_0 matches so no update needed
    result.assert_outcomes(passed=1)


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


def test_file_patch_registry_loads_and_patches(pytester: pytest.Pytester) -> None:
    """FilePatchRegistry loads JSON files and patches targets."""
    pytester.makepyfile(
        mymodule="""
        def get_data():
            raise NotImplementedError
        """,
    )
    pytester.makepyfile(
        """
        from pytest_remaster import FilePatchRegistry

        patcher = FilePatchRegistry()
        patcher.register("data.json", target="mymodule.get_data")

        def test_fixtures(tmp_path):
            (tmp_path / "data.json").write_text('{"key": "value"}')
            with patcher.mock(tmp_path) as loaded:
                import mymodule
                assert mymodule.get_data() == {"key": "value"}
                assert loaded["data.json"] == {"key": "value"}
        """,
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_file_patch_registry_uses_default(pytester: pytest.Pytester) -> None:
    """FilePatchRegistry uses default when file is missing."""
    pytester.makepyfile(
        mymodule="""
        def get_data():
            raise NotImplementedError
        """,
    )
    pytester.makepyfile(
        """
        from pytest_remaster import FilePatchRegistry

        patcher = FilePatchRegistry()
        patcher.register("missing.json", target="mymodule.get_data", default=[])

        def test_default(tmp_path):
            with patcher.mock(tmp_path) as loaded:
                import mymodule
                assert mymodule.get_data() == []
                assert loaded["missing.json"] == []
        """,
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_file_patch_registry_custom_loader(pytester: pytest.Pytester) -> None:
    """FilePatchRegistry supports custom loaders."""
    pytester.makepyfile(
        mymodule="""
        def get_text():
            raise NotImplementedError
        """,
    )
    pytester.makepyfile(
        """
        from pytest_remaster import FilePatchRegistry

        patcher = FilePatchRegistry()
        patcher.register(
            "input.txt",
            target="mymodule.get_text",
            loader=lambda s: s.strip().upper(),
        )

        def test_loader(tmp_path):
            (tmp_path / "input.txt").write_text("hello world")
            with patcher.mock(tmp_path) as loaded:
                import mymodule
                assert mymodule.get_text() == "HELLO WORLD"
                assert loaded["input.txt"] == "HELLO WORLD"
        """,
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_file_patch_registry_multiple(pytester: pytest.Pytester) -> None:
    """FilePatchRegistry handles multiple registered patches."""
    pytester.makepyfile(
        mod_a="""
        def call_a():
            raise NotImplementedError
        """,
        mod_b="""
        def call_b():
            raise NotImplementedError
        """,
    )
    pytester.makepyfile(
        """
        from pytest_remaster import FilePatchRegistry

        patcher = FilePatchRegistry()
        patcher.register("a.json", target="mod_a.call_a")
        patcher.register("b.json", target="mod_b.call_b", default="beta")

        def test_multi(tmp_path):
            (tmp_path / "a.json").write_text('"alpha"')
            with patcher.mock(tmp_path) as loaded:
                import mod_a, mod_b
                assert mod_a.call_a() == "alpha"
                assert mod_b.call_b() == "beta"
                assert loaded["a.json"] == "alpha"
                assert loaded["b.json"] == "beta"
        """,
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_file_patch_registry_nested_attr(pytester: pytest.Pytester) -> None:
    """FilePatchRegistry supports nested attr paths."""
    pytester.makepyfile(
        mymodule="""
        def fetch():
            raise NotImplementedError
        """,
    )
    pytester.makepyfile(
        """
        from pytest_remaster import FilePatchRegistry

        patcher = FilePatchRegistry()
        patcher.register(
            "responses.json",
            target="mymodule.fetch",
            attr="side_effect",
        )

        def test_side_effect(tmp_path):
            (tmp_path / "responses.json").write_text('[1, 2, 3]')
            with patcher.mock(tmp_path):
                import mymodule
                assert mymodule.fetch() == 1
                assert mymodule.fetch() == 2
                assert mymodule.fetch() == 3
        """,
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_file_patch_registry_shared_target(pytester: pytest.Pytester) -> None:
    """Two registrations on the same target patch the mock once."""
    pytester.makepyfile(
        mymodule="""
        class Api:
            pass
        """,
    )
    pytester.makepyfile(
        """
        from pytest_remaster import FilePatchRegistry

        patcher = FilePatchRegistry()
        patcher.register(
            "login.json",
            target="mymodule.Api",
            attr="return_value.login.side_effect",
        )
        patcher.register(
            "data.json",
            target="mymodule.Api",
            attr="return_value.query.side_effect",
        )

        def test_shared(tmp_path):
            (tmp_path / "login.json").write_text('["ok"]')
            (tmp_path / "data.json").write_text('[{"id": 1}]')
            with patcher.mock(tmp_path):
                import mymodule
                api = mymodule.Api()
                assert api.login() == "ok"
                assert api.query() == {"id": 1}
        """,
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_file_patch_registry_no_target(pytester: pytest.Pytester) -> None:
    """FilePatchRegistry with no target loads data without patching."""
    pytester.makepyfile(
        """
        from pytest_remaster import FilePatchRegistry

        patcher = FilePatchRegistry()
        patcher.register("config.json")

        def test_load_only(tmp_path):
            (tmp_path / "config.json").write_text('{"port": 8080}')
            with patcher.mock(tmp_path) as loaded:
                assert loaded["config.json"] == {"port": 8080}
        """,
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_file_patch_registry_skip_if_falsy(pytester: pytest.Pytester) -> None:
    """FilePatchRegistry skips patching when value is falsy."""
    pytester.makepyfile(
        mymodule="""
        def get_data():
            return "original"
        """,
    )
    pytester.makepyfile(
        """
        from pytest_remaster import FilePatchRegistry

        patcher = FilePatchRegistry()
        patcher.register(
            "data.json",
            target="mymodule.get_data",
            default=[],
            skip_if_falsy=True,
        )

        def test_skip(tmp_path):
            # No data.json file, default is [] which is falsy -> no patch
            with patcher.mock(tmp_path) as loaded:
                import mymodule
                assert loaded["data.json"] == []
                assert mymodule.get_data() == "original"  # not mocked
        """,
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
