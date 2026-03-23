"""Tests for the PatchRegistry."""

from __future__ import annotations

import pytest


def test_add_file_patch_loads_and_patches(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_file_patch() loads JSON files and patches targets."""
    pytester.makepyfile(
        mymodule="""
        def get_data():
            raise NotImplementedError
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch("data.json", target="mymodule.get_data")

        def test_fixtures(tmp_path):
            (tmp_path / "data.json").write_text('{"key": "value"}')
            with patcher.mock(tmp_path) as loaded:
                import mymodule
                assert mymodule.get_data() == {"key": "value"}
                assert loaded["data.json"] == {"key": "value"}
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_file_patch_uses_default(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_file_patch() uses default when file is missing."""
    pytester.makepyfile(
        mymodule="""
        def get_data():
            raise NotImplementedError
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch("missing.json", target="mymodule.get_data", default=[])

        def test_default(tmp_path):
            with patcher.mock(tmp_path) as loaded:
                import mymodule
                assert mymodule.get_data() == []
                assert loaded["missing.json"] == []
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_file_patch_custom_loader(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_file_patch() supports custom loaders."""
    pytester.makepyfile(
        mymodule="""
        def get_text():
            raise NotImplementedError
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch(
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
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_file_patch_multiple(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_file_patch() handles multiple registered patches."""
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
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch("a.json", target="mod_a.call_a")
        patcher.add_file_patch("b.json", target="mod_b.call_b", default="beta")

        def test_multi(tmp_path):
            (tmp_path / "a.json").write_text('"alpha"')
            with patcher.mock(tmp_path) as loaded:
                import mod_a, mod_b
                assert mod_a.call_a() == "alpha"
                assert mod_b.call_b() == "beta"
                assert loaded["a.json"] == "alpha"
                assert loaded["b.json"] == "beta"
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_file_patch_nested_attr(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_file_patch() supports nested attr paths."""
    pytester.makepyfile(
        mymodule="""
        def fetch():
            raise NotImplementedError
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch(
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
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_file_patch_shared_target(pytester: pytest.Pytester) -> None:
    """Two registrations on the same target patch the mock once."""
    pytester.makepyfile(
        mymodule="""
        class Api:
            pass
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch(
            "login.json",
            target="mymodule.Api",
            attr="return_value.login.side_effect",
        )
        patcher.add_file_patch(
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
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_file_patch_no_target(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_file_patch() with no target loads data without patching."""
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch("config.json")

        def test_load_only(tmp_path):
            (tmp_path / "config.json").write_text('{"port": 8080}')
            with patcher.mock(tmp_path) as loaded:
                assert loaded["config.json"] == {"port": 8080}
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_file_patch_skip_attr_if_falsy(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_file_patch() skips patching when value is falsy."""
    pytester.makepyfile(
        mymodule="""
        def get_data():
            return "original"
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch(
            "data.json",
            target="mymodule.get_data",
            default=[],
            skip_attr_if_falsy=True,
        )

        def test_skip(tmp_path):
            # No data.json file, default is [] which is falsy
            # Target is still patched (blocks real calls) but attr not configured
            with patcher.mock(tmp_path) as loaded:
                import mymodule
                assert loaded["data.json"] == []
                # get_data is mocked (not original) but has no configured return_value
                result = mymodule.get_data()
                assert result != "original"  # patched, not the real function
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_post_load(pytester: pytest.Pytester) -> None:
    """post_load hooks can derive values from multiple loaded files."""
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch("name.json")
        patcher.add_file_patch("greeting.json")

        @patcher.post_load
        def _build_message(loaded, case_dir):
            loaded["message"] = f"{loaded['greeting.json']} {loaded['name.json']}!"

        def test_post_load(tmp_path):
            (tmp_path / "name.json").write_text('"Alice"')
            (tmp_path / "greeting.json").write_text('"Hello"')
            with patcher.mock(tmp_path) as loaded:
                assert loaded["name.json"] == "Alice"
                assert loaded["greeting.json"] == "Hello"
                assert loaded["message"] == "Hello Alice!"
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_multiple_post_load(pytester: pytest.Pytester) -> None:
    """Multiple post_load hooks run in registration order."""
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch("data.json")

        @patcher.post_load
        def _step1(loaded, case_dir):
            loaded["step1"] = loaded["data.json"] * 2

        @patcher.post_load
        def _step2(loaded, case_dir):
            loaded["step2"] = loaded["step1"] + 1

        def test_chain(tmp_path):
            (tmp_path / "data.json").write_text("5")
            with patcher.mock(tmp_path) as loaded:
                assert loaded["step1"] == 10
                assert loaded["step2"] == 11
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_post_load_case_dir(pytester: pytest.Pytester) -> None:
    """post_load hooks receive the case directory path."""
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch("data.json")

        @patcher.post_load
        def _use_case_dir(loaded, case_dir):
            loaded["dir_name"] = case_dir.name

        def test_case_dir(tmp_path):
            (tmp_path / "data.json").write_text("1")
            with patcher.mock(tmp_path) as loaded:
                assert loaded["dir_name"] == tmp_path.name
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_file_patch_attr_new(pytester: pytest.Pytester) -> None:
    """attr='new' replaces the target directly (for constants)."""
    pytester.makepyfile(
        mymodule="""
        MAX_LENGTH = 9999
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch(
            "max_length.json",
            target="mymodule.MAX_LENGTH",
            attr="new",
        )

        def test_constant(tmp_path):
            (tmp_path / "max_length.json").write_text("420")
            with patcher.mock(tmp_path) as loaded:
                import mymodule
                assert mymodule.MAX_LENGTH == 420
                assert loaded["max_length.json"] == 420
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_patch(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_patch() creates plain mocks available in context."""
    pytester.makepyfile(
        mymodule="""
        def fetch():
            raise NotImplementedError
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_patch("mymodule.fetch")

        def test_plain_patch(tmp_path):
            with patcher.mock(tmp_path) as ctx:
                import mymodule
                mymodule.fetch("arg1")
                mock_obj = ctx["mymodule.fetch"]
                mock_obj.assert_called_once_with("arg1")
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_add_patch_with_kwargs(pytester: pytest.Pytester) -> None:
    """PatchRegistry.add_patch() passes kwargs to unittest.mock.patch."""
    pytester.makepyfile(
        mymodule="""
        def fetch():
            raise NotImplementedError
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_patch("mymodule.fetch", name="fetcher", side_effect=[1, 2])

        def test_side_effect(tmp_path):
            with patcher.mock(tmp_path) as ctx:
                import mymodule
                assert mymodule.fetch() == 1
                assert mymodule.fetch() == 2
                assert "fetcher" in ctx
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_mixed_file_and_plain_patches(pytester: pytest.Pytester) -> None:
    """PatchRegistry handles add_file_patch and add_patch together."""
    pytester.makepyfile(
        mymodule="""
        def get_data():
            raise NotImplementedError
        def send():
            raise NotImplementedError
        """
    )
    pytester.makepyfile(
        """
        from pytest_remaster import PatchRegistry

        patcher = PatchRegistry()
        patcher.add_file_patch("data.json", target="mymodule.get_data")
        patcher.add_patch("mymodule.send")

        def test_mixed(tmp_path):
            (tmp_path / "data.json").write_text('{"key": "value"}')
            with patcher.mock(tmp_path) as ctx:
                import mymodule
                assert mymodule.get_data() == {"key": "value"}
                mymodule.send("hello")
                ctx["mymodule.send"].assert_called_once_with("hello")
                assert ctx["data.json"] == {"key": "value"}
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
