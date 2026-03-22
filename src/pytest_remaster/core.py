"""Core golden master comparison and discovery logic."""

from __future__ import annotations

import difflib
import functools
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


def _normalize_whitespace(text: str) -> str:
    """Normalize line endings and strip trailing whitespace per line."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    return "\n".join(line.rstrip() for line in lines).rstrip()


whitespace_normalizer = _normalize_whitespace
"""Built-in normalizer that strips trailing whitespace per line and
normalizes line endings to ``\\n``. Opt-in via ``normalizer=whitespace_normalizer``."""


def _json_normalizer(text: str) -> str:
    """Normalize JSON text for comparison, ignoring formatting differences."""
    return json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False)


json_normalizer = _json_normalizer
"""Built-in normalizer for JSON files. Re-parses and re-serializes with
consistent formatting. Automatically applied for ``.json`` files."""


@dataclass(frozen=True)
class CaseData:
    """A discovered test case with input path and expected output helpers."""

    input: Path

    def expected(self, index: int | None = None, suffix: str = "") -> Path:
        """Return the expected output path.

        Without index: derives from input path (replaces extension with suffix).
        With index: returns ``input / expected_{index}{suffix}`` (directory mode).
        """
        if index is not None:
            return self.input / f"expected_{index}{suffix}"
        if suffix:
            return self.input.with_suffix(suffix)
        return self.input


class GoldenMaster:
    """Golden master comparison with optional auto-regeneration."""

    def __init__(self, remaster: bool) -> None:
        self._remaster = remaster
        self._updated: list[str] = []

    def assert_remastered(self) -> None:
        """Fail if any golden masters were updated during this test.

        Called automatically by the ``golden_master`` fixture at teardown.
        """
        if self._updated:
            summary = "\n".join(self._updated)
            self._updated.clear()
            pytest.fail(
                f"Expected files updated, please review the changes:\n{summary}",
                pytrace=False,
            )

    def check(
        self,
        actual: Any | Callable[[], Any],
        expected_path: str | Path,
        *,
        serializer: Callable[[Any], str] = str,
        normalizer: Callable[[str], str] | None = None,
    ) -> None:
        """Compare one actual value against one expected file.

        Args:
            actual: The actual value, or a callable that produces it.
            expected_path: Path to the expected output file.
            serializer: Converts actual value to string. Default: str().
            normalizer: Optional function applied to both actual and expected
                strings before comparison. The raw serializer output is still
                written when remastering.

        """
        expected_path = Path(expected_path)
        if callable(actual) and not isinstance(actual, str):
            actual = actual()
        actual_str = serializer(actual).rstrip()

        try:
            expected_str = expected_path.read_text(encoding="utf-8").rstrip()
        except FileNotFoundError:
            expected_str = None

        if expected_str is not None:
            actual_cmp = normalizer(actual_str) if normalizer else actual_str
            expected_cmp = normalizer(expected_str) if normalizer else expected_str
            if actual_cmp == expected_cmp:
                return

        if self._remaster:
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(actual_str + "\n", encoding="utf-8")
            action = "created" if expected_str is None else "updated"
            self._updated.append(f"{action}: {expected_path}")
        else:
            if expected_str is None:
                pytest.fail(
                    f"Expected file {expected_path} does not exist. "
                    f"Run with --remaster to create it.",
                    pytrace=False,
                )
            diff = difflib.unified_diff(
                expected_str.splitlines(keepends=True),
                actual_str.splitlines(keepends=True),
                fromfile=str(expected_path),
                tofile="actual",
            )
            pytest.fail(
                f"Mismatch at {expected_path}:\n{''.join(diff)}",
                pytrace=False,
            )

    def check_all(
        self,
        actuals: list[Any] | Callable[[], list[Any]],
        directory: str | Path,
        *,
        serializer: Callable[[Any], str] = str,
        normalizer: Callable[[str], str] | None = None,
        suffix: str = "",
    ) -> None:
        """Compare multiple actuals against expected_0, expected_1, ... files.

        Args:
            actuals: List of values, or a callable returning a list.
            directory: Directory containing expected_N files.
            serializer: Converts each value to string. Default: str().
            normalizer: Optional function applied before comparison.
            suffix: File extension (e.g. ``".json"``, ``".txt"``).

        """
        directory = Path(directory)
        if callable(actuals) and not isinstance(actuals, list):
            actuals = list(actuals())

        pattern = rf"expected_\d+{re.escape(suffix)}$"
        existing = sorted(
            (p for p in directory.iterdir() if re.match(pattern, p.name)),
            key=lambda p: int(re.search(r"\d+", p.name).group()),  # type: ignore[union-attr]
        )

        if self._remaster and len(actuals) != len(existing):
            for extra in existing[len(actuals) :]:
                extra.unlink()

        for i, actual in enumerate(actuals):
            self.check(
                actual,
                directory / f"expected_{i}{suffix}",
                serializer=serializer,
                normalizer=normalizer,
            )

        if not self._remaster and len(actuals) < len(existing):
            extra_files = [p.name for p in existing[len(actuals) :]]
            pytest.fail(
                f"Expected {len(existing)} results but got {len(actuals)}. "
                f"Extra files: {extra_files}. Run with --remaster to clean up.",
                pytrace=False,
            )


def discover_test_cases(
    base_dir: str | Path,
) -> list[Any]:
    """Find leaf directories (containing only files) under base_dir.

    Returns ``pytest.param(CaseData(input=path), id=relative_path)`` for each
    leaf directory, ready to use with ``@pytest.mark.parametrize``.
    """
    base_dir = Path(base_dir)
    return _discover_test_cases_recursive(base_dir, base_dir)


def _discover_test_cases_recursive(base_dir: Path, root: Path) -> list[Any]:
    result: list[Any] = []
    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        if all(f.is_file() for f in entry.iterdir()):
            result.append(
                pytest.param(CaseData(input=entry), id=str(entry.relative_to(root)))
            )
        else:
            result.extend(_discover_test_cases_recursive(entry, root))
    return result


def discover_test_files(base_dir: str | Path, pattern: str = "*.py") -> list[Any]:
    """Find files matching a glob pattern under base_dir.

    Returns ``pytest.param(CaseData(input=path), id=relative_path)`` for each
    matching file, ready to use with ``@pytest.mark.parametrize``.
    """
    base_dir = Path(base_dir)
    return [
        pytest.param(CaseData(input=p), id=str(p.relative_to(base_dir)))
        for p in sorted(base_dir.rglob(pattern))
    ]


@dataclass
class _FixtureSpec:
    filename: str
    target: str | None
    loader: Callable[[str], Any]
    default: Any
    side_effect: bool


class FilePatchRegistry:
    """Registry for loading fixture files from case directories and patching them in."""

    def __init__(self) -> None:
        self._specs: list[_FixtureSpec] = []

    def register(  # pylint: disable=too-many-arguments
        self,
        filename: str,
        *,
        target: str | None = None,
        loader: Callable[[str], Any] = json.loads,
        default: Any = None,
        side_effect: bool = False,
    ) -> None:
        """Register a fixture file to be loaded and optionally patched.

        Args:
            filename: Name of the file in the case directory.
            target: Dotted path for ``unittest.mock.patch`` (e.g. "myapp.api.call").
                    If ``None``, the file is loaded but not patched — read it
                    from the case directory in the test body.
            loader: Callable that takes file content (str) and returns the value.
                    Default: ``json.loads``.
            default: Value to use when the file is not present in the case directory.
            side_effect: If ``True``, set ``side_effect`` on the mock instead of
                    ``return_value``. Useful when the mock is called multiple times
                    and should return different values from a list.

        """
        self._specs.append(
            _FixtureSpec(
                filename=filename,
                target=target,
                loader=loader,
                default=default,
                side_effect=side_effect,
            )
        )

    def use(
        self, func: Callable[..., Any] | None = None, *, case_param: str = "case"
    ) -> Any:
        """Decorate a test to load fixtures and patch targets.

        Finds the case directory from the test parameter named ``case_param``
        (default: ``"case"``).

        Usage::

            @patcher.use
            def test_command(case, golden_master):
                ...

            @patcher.use(case_param="path_to_directory")
            def test_command(path_to_directory, golden_master):
                ...

        """
        if func is None:
            return functools.partial(self.use, case_param=case_param)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if (case_arg := kwargs.get(case_param)) is None:
                msg = (
                    f"FilePatchRegistry.use: parameter '{case_param}' not found "
                    f"in keyword arguments. Make sure the test receives it "
                    f"via @pytest.mark.parametrize."
                )
                raise TypeError(msg)
            case_dir = Path(
                case_arg.input if isinstance(case_arg, CaseData) else case_arg
            )
            active_patches: list[Any] = []
            for spec in self._specs:
                filepath = case_dir / spec.filename
                if filepath.exists():
                    content = filepath.read_text(encoding="utf-8")
                    value = spec.loader(content)
                else:
                    value = spec.default
                if spec.target is not None:
                    kwargs_patch = (
                        {"side_effect": value}
                        if spec.side_effect
                        else {"return_value": value}
                    )
                    p = patch(spec.target, **kwargs_patch)
                    active_patches.append(p)

            for p in active_patches:
                p.start()
            try:
                return func(*args, **kwargs)
            finally:
                for p in active_patches:
                    p.stop()

        return wrapper
