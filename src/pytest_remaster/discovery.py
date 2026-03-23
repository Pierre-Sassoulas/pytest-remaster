"""Test case discovery: find directories or files and return CaseData."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.mark.structures import ParameterSet


@dataclass(frozen=True, repr=False)
class CaseData:
    """A discovered test case with input path and expected output helpers."""

    input: Path

    def __repr__(self) -> str:
        return f"CaseData({self.input.name})"

    def expected(self, index: int | None = None, suffix: str = "") -> Path:
        """Return the expected output path.

        With index: returns ``input / expected_{index}{suffix}`` (directory mode).
        With suffix only: returns ``input / expected{suffix}`` (directory mode)
        or replaces input extension (file mode).
        """
        if index is not None:
            return self.input / f"expected_{index}{suffix}"
        if suffix:
            if self.input.suffix:
                return self.input.with_suffix(suffix)
            return self.input / f"expected{suffix}"
        msg = "expected() requires index or suffix"
        raise ValueError(msg)


def _is_leaf_directory(path: Path) -> bool:
    """Default predicate: a directory containing only files (no subdirs)."""
    return all(f.is_file() for f in path.iterdir())


def discover_test_cases(
    base_dir: str | Path,
    *,
    is_case: Callable[[Path], bool] = _is_leaf_directory,
) -> list[ParameterSet]:
    """Find test case directories under base_dir.

    Args:
        base_dir: Root directory to search.
        is_case: Predicate that returns True if a directory is a test case.
            Default: directories containing only files (leaf directories).

    Returns ``pytest.param(CaseData(...), id=relative_path)`` for each case,
    ready to use with ``@pytest.mark.parametrize``.

    """
    base_dir = Path(base_dir)
    return _discover_test_cases_recursive(base_dir, base_dir, is_case)


def _discover_test_cases_recursive(
    base_dir: Path, root: Path, is_case: Callable[[Path], bool]
) -> list[ParameterSet]:
    result: list[ParameterSet] = []
    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        if is_case(entry):
            result.append(
                pytest.param(CaseData(input=entry), id=str(entry.relative_to(root)))
            )
        else:
            result.extend(_discover_test_cases_recursive(entry, root, is_case))
    return result


def discover_test_files(
    base_dir: str | Path, pattern: str = "*.py"
) -> list[ParameterSet]:
    """Find files matching a glob pattern under base_dir.

    Returns ``pytest.param(CaseData(input=path), id=relative_path)`` for each
    matching file, ready to use with ``@pytest.mark.parametrize``.
    """
    base_dir = Path(base_dir)
    return [
        pytest.param(CaseData(input=p), id=str(p.relative_to(base_dir)))
        for p in sorted(base_dir.rglob(pattern))
    ]
