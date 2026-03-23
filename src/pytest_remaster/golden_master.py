"""Golden master comparison with optional auto-regeneration."""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pytest_remaster.discovery import CaseData


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
consistent formatting. Opt-in via ``normalizer=json_normalizer``."""


class MalformedTestCase(Exception):
    """Raised when a discovered test case directory is missing required files."""


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
            try:
                actual = actual()
            except FileNotFoundError as exc:
                raise MalformedTestCase(
                    f"{expected_path.parent} — {exc.filename or exc}\n"
                    f"  (directory was discovered as a test case but appears malformed)"
                ) from exc
        actual_str = serializer(actual).rstrip()

        try:
            expected_str = expected_path.read_text(encoding="utf-8").rstrip()
        except FileNotFoundError:
            expected_str = None

        # Both empty and no file: nothing to check
        if not actual_str and expected_str is None:
            return

        if expected_str is not None:
            actual_cmp = normalizer(actual_str) if normalizer else actual_str
            expected_cmp = normalizer(expected_str) if normalizer else expected_str
            if actual_cmp == expected_cmp:
                return

        if self._remaster:
            write_str = normalizer(actual_str) if normalizer else actual_str
            self._remaster_file(write_str, expected_str, expected_path)
        else:
            self._fail_mismatch(actual_str, expected_str, expected_path)

    def check_each(
        self,
        case: CaseData,
        *,
        runner: Callable[[CaseData], Any],
        extractors: dict[str, Callable[[Any], Any]],
        serializer: Callable[[Any], str] = str,
        normalizer: Callable[[str], str] | None = None,
    ) -> None:
        """Run a function on a case and check named outputs.

        Args:
            case: The test case.
            runner: Callable that takes the case and returns a result object.
            extractors: Mapping of file suffix to extractor function. Each
                extractor receives the result from ``runner`` and returns
                the value to compare.
            serializer: Converts each value to string. Default: str().
            normalizer: Optional function applied before comparison.

        """
        try:
            result = runner(case)
        except FileNotFoundError as exc:
            raise MalformedTestCase(
                f"{case.input} — {exc.filename or exc}\n"
                f"  (directory was discovered as a test case but appears malformed)"
            ) from exc
        for suffix, getter in extractors.items():
            self.check(
                getter(result),
                case.expected(suffix=suffix),
                serializer=serializer,
                normalizer=normalizer,
            )

    def _remaster_file(
        self, actual_str: str, expected_str: str | None, expected_path: Path
    ) -> None:
        if not actual_str:
            expected_path.unlink(missing_ok=True)
            if expected_str is not None:
                self._updated.append(f"deleted: {expected_path}")
        else:
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(actual_str + "\n", encoding="utf-8")
            action = "created" if expected_str is None else "updated"
            self._updated.append(f"{action}: {expected_path}")

    @staticmethod
    def _fail_mismatch(
        actual_str: str, expected_str: str | None, expected_path: Path
    ) -> None:
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
            try:
                actuals = list(actuals())
            except FileNotFoundError as exc:
                raise MalformedTestCase(
                    f"{directory} — {exc.filename or exc}\n"
                    f"  (directory was discovered as a test case"
                    f" but appears malformed)"
                ) from exc

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
