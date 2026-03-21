"""Core golden master comparison and discovery logic."""

from __future__ import annotations  # pragma: no cover

import difflib  # pragma: no cover
import re  # pragma: no cover
from collections.abc import Callable  # pragma: no cover
from pathlib import Path  # pragma: no cover
from typing import Any  # pragma: no cover

import pytest  # pragma: no cover


class GoldenMaster:  # pragma: no cover
    """Golden master comparison with optional auto-regeneration."""

    def __init__(self, remaster: bool) -> None:  # pragma: no cover
        self._remaster = remaster

    def check(  # pragma: no cover
        self,
        actual: Any | Callable[[], Any],
        expected_path: str | Path,
        serializer: Callable[[Any], str] = str,
    ) -> None:
        """Compare actual output against an expected file.

        Args:
            actual: The actual value, or a callable that produces it.
            expected_path: Path to the expected output file.
            serializer: Converts actual value to string. Default: str().
        """
        expected_path = Path(expected_path)
        if callable(actual) and not isinstance(actual, str):
            actual = actual()
        actual_str = serializer(actual).rstrip()

        try:
            expected_str = expected_path.read_text(encoding="utf-8").rstrip()
        except FileNotFoundError:
            expected_str = None

        if expected_str is not None and actual_str == expected_str:
            return

        if self._remaster:
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(actual_str + "\n", encoding="utf-8")
            action = "created" if expected_str is None else "updated"
            pytest.fail(
                f"Golden master {action} at {expected_path}, "
                f"please review and relaunch.",
                pytrace=False,
            )
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
                f"Golden master mismatch at {expected_path}:\n{''.join(diff)}",
                pytrace=False,
            )

    def check_all(  # pragma: no cover
        self,
        *actuals: Any | Callable[[], list[Any]],
        directory: str | Path,
        serializer: Callable[[Any], str] = str,
    ) -> None:
        """Compare multiple actuals against result_0, result_1, ... files.

        Args:
            *actuals: Values to compare, or a single callable returning a list.
            directory: Directory containing result_N files.
            serializer: Converts each value to string. Default: str().
        """
        directory = Path(directory)

        if (
            len(actuals) == 1
            and callable(actuals[0])
            and not isinstance(actuals[0], str)
        ):
            actuals = tuple(actuals[0]())

        existing = sorted(
            (p for p in directory.iterdir() if re.match(r"result_\d+$", p.name)),
            key=lambda p: int(p.name.split("_")[1]),
        )

        if self._remaster and len(actuals) != len(existing):
            for extra in existing[len(actuals) :]:
                extra.unlink()

        for i, actual in enumerate(actuals):
            self.check(actual, directory / f"result_{i}", serializer=serializer)

        if not self._remaster and len(actuals) < len(existing):
            extra_files = [p.name for p in existing[len(actuals) :]]
            pytest.fail(
                f"Expected {len(existing)} results but got {len(actuals)}. "
                f"Extra files: {extra_files}. Run with --remaster to clean up.",
                pytrace=False,
            )


def discover_test_cases(base_dir: str | Path) -> list[Path]:  # pragma: no cover
    """Find leaf directories (containing only files) under base_dir.

    Suitable for use with ``@pytest.mark.parametrize``.
    Returns absolute paths sorted alphabetically.
    """
    base_dir = Path(base_dir)
    result: list[Path] = []
    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():  # pragma: no cover
            continue
        if all(f.is_file() for f in entry.iterdir()):
            result.append(entry)
        else:
            result.extend(discover_test_cases(entry))
    return result


def discover_test_files(
    base_dir: str | Path, pattern: str = "*.py"
) -> list[Path]:  # pragma: no cover
    """Find files matching a glob pattern under base_dir.

    Suitable for use with ``@pytest.mark.parametrize``.
    Returns absolute paths sorted alphabetically.
    """
    base_dir = Path(base_dir)
    return sorted(base_dir.rglob(pattern))
