"""Golden master comparison with optional auto-regeneration."""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_remaster.discovery import CaseData

if TYPE_CHECKING:
    from _pytest.config import Config


def _normalize_whitespace(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    return "\n".join(line.rstrip() for line in lines).rstrip()


whitespace_normalizer = _normalize_whitespace
"""Built-in normalizer that strips trailing whitespace per line and
normalizes line endings to ``\\n``. Opt-in via ``normalizer=whitespace_normalizer``."""


def _json_normalizer(text: str) -> str:
    return json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False)


json_normalizer = _json_normalizer
"""Built-in normalizer for JSON files. Re-parses and re-serializes with
consistent formatting. Opt-in via ``normalizer=json_normalizer``."""


def mock_calls_serializer(name: str) -> Callable[[Any], str]:
    """Return a serializer that formats a mock's ``call_args_list``.

    Usage::

        golden_master.check(
            mock_obj.call_args_list,
            expected_path,
            serializer=mock_calls_serializer("subprocess"),
        )

    Produces one line per call, e.g.::

        subprocess(['sudo', 'reboot'], check=True)
        subprocess(['echo', 'done'])

    """

    def _serialize(call_args_list: Any) -> str:
        lines = []
        for call in call_args_list:
            parts = [repr(a) for a in call.args]
            parts.extend(f"{k}={v!r}" for k, v in call.kwargs.items())
            lines.append(f"{name}({', '.join(parts)})")
        return "\n".join(lines)

    return _serialize


def resolve_with_override(base: str | Path, override: str | Path | None = None) -> Path:
    """Return *override* if it exists on disk, otherwise *base*.

    Used for version-specific file resolution: *override* is an exact-match
    file (e.g. ``a.314.txt`` for Python 3.14) and *base* is the generic
    fallback (e.g. ``a.txt``).
    """
    if override is not None and Path(override).exists():
        return Path(override)
    return Path(base)


class MalformedTestCase(Exception):
    """Raised when a discovered test case directory is missing required files."""


class GoldenMaster:
    """Golden master comparison with optional auto-regeneration."""

    def __init__(self, remaster: bool, config: Config | None = None) -> None:
        self._remaster = remaster
        self._config = config
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
        override_path: str | Path | None = None,
        serializer: Callable[[Any], str] = str,
        normalizer: Callable[[str], str] | None = None,
    ) -> None:
        """Compare one actual value against one expected file.

        Args:
            actual: The actual value, or a callable that produces it.
            expected_path: Path to the expected output file.
            override_path: Optional version-specific override.  When given,
                the override is checked first and used for comparison if it
                exists; otherwise *expected_path* (the generic base) is used.
                Remastering always writes to *override_path* when provided,
                keeping the base file untouched.  Redundant overrides
                (identical to the base) are cleaned up automatically.
            serializer: Converts actual value to string. Default: str().
            normalizer: Optional function applied to both actual and expected
                strings before comparison. The normalized output is also
                written when remastering.

        """
        expected_path = Path(expected_path)
        override = Path(override_path) if override_path is not None else None
        actual_str = self._resolve_actual(actual, expected_path, serializer)

        # Resolution: override takes precedence if it exists on disk
        compare_path = (
            override if override is not None and override.exists() else expected_path
        )

        try:
            expected_str = compare_path.read_text(encoding="utf-8").rstrip()
        except FileNotFoundError:
            expected_str = None

        # Both empty and no file: nothing to check
        if not actual_str and expected_str is None:
            return

        if self._content_matches(actual_str, expected_str, normalizer):
            self._dedup_override(override, expected_path, normalizer)
            return

        # Where to write: override when provided, else expected_path
        write_path = override if override is not None else expected_path
        if self._remaster:
            write_str = normalizer(actual_str) if normalizer else actual_str
            self._remaster_file(write_str, expected_str, write_path)
            self._dedup_override(override, expected_path, normalizer)
        else:
            self._fail_mismatch(actual_str, expected_str, expected_path, write_path)

    @staticmethod
    def _resolve_actual(
        actual: Any | Callable[[], Any],
        expected_path: Path,
        serializer: Callable[[Any], str],
    ) -> str:
        if callable(actual) and not isinstance(actual, str):
            try:
                actual = actual()
            except FileNotFoundError as exc:
                raise MalformedTestCase(
                    f"{expected_path.parent} — {exc.filename or exc}\n"
                    f"  (directory was discovered as a test case"
                    f" but appears malformed)"
                ) from exc
        return serializer(actual).rstrip()

    @staticmethod
    def _content_matches(
        actual_str: str,
        expected_str: str | None,
        normalizer: Callable[[str], str] | None,
    ) -> bool:
        if expected_str is None:
            return False
        actual_cmp = normalizer(actual_str) if normalizer else actual_str
        expected_cmp = normalizer(expected_str) if normalizer else expected_str
        return actual_cmp == expected_cmp

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
        self, actual_str: str, expected_str: str | None, write_path: Path
    ) -> None:
        if not actual_str:
            write_path.unlink(missing_ok=True)
            if expected_str is not None:
                self._updated.append(f"deleted: {write_path}")
        else:
            write_path.parent.mkdir(parents=True, exist_ok=True)
            existed = write_path.exists()
            write_path.write_text(actual_str + "\n", encoding="utf-8")
            action = "updated" if existed else "created"
            self._updated.append(f"{action}: {write_path}")

    def _dedup_override(
        self, override: Path | None, base: Path, normalizer: Callable[[str], str] | None
    ) -> None:
        """Delete *override* if it is identical to *base* (redundant)."""
        if override is None or not override.exists() or not base.exists():
            return
        override_content = override.read_text(encoding="utf-8").rstrip()
        base_content = base.read_text(encoding="utf-8").rstrip()
        if normalizer:
            override_content = normalizer(override_content)
            base_content = normalizer(base_content)
        if override_content != base_content:
            return
        if self._remaster:
            override.unlink()
            self._updated.append(f"deleted (redundant): {override}")
        else:
            pytest.fail(
                f"{override} is identical to {base}, remove the redundant override.",
                pytrace=False,
            )

    def _fail_mismatch(
        self,
        actual_str: str,
        expected_str: str | None,
        compare_path: Path,
        write_path: Path,
    ) -> None:
        if expected_str is None:
            pytest.fail(
                f"Expected file {compare_path} does not exist. "
                f"Run with --remaster to create {write_path}.",
                pytrace=False,
            )
        diff_lines = list(
            difflib.unified_diff(
                expected_str.splitlines(keepends=True),
                actual_str.splitlines(keepends=True),
                fromfile=str(compare_path),
                tofile="actual",
            )
        )
        diff_text = self._maybe_truncate(diff_lines)
        pytest.fail(
            f"Mismatch at {compare_path}:\n{diff_text}\n"
            f"Run with --remaster to update {write_path}.",
            pytrace=False,
        )

    _VERBOSE_NO_TRUNCATE = 2

    def _maybe_truncate(self, lines: list[str]) -> str:
        if self._config is None:
            return "".join(lines)
        raw_lines = self._config.getini("truncation_limit_lines")
        raw_chars = self._config.getini("truncation_limit_chars")
        if raw_lines is None and raw_chars is None:
            return "".join(lines)
        max_lines = int(raw_lines or 0)
        max_chars = int(raw_chars or 0)
        verbose = self._config.get_verbosity(self._config.VERBOSITY_ASSERTIONS)
        if verbose >= self._VERBOSE_NO_TRUNCATE or max_lines == max_chars == 0:
            return "".join(lines)
        if 0 < max_lines < len(lines):
            hidden = len(lines) - max_lines
            truncated = lines[:max_lines]
            truncated.append(
                f"\n...diff truncated ({hidden} lines hidden), use '-vv' to show\n"
            )
            return "".join(truncated)
        return "".join(lines)

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

        for i, actual in enumerate(actuals):
            self.check(
                actual,
                directory / f"expected_{i}{suffix}",
                serializer=serializer,
                normalizer=normalizer,
            )

        if self._remaster and len(actuals) < len(existing):
            for extra in existing[len(actuals) :]:
                extra.unlink()
                self._updated.append(f"deleted: {extra}")

        if not self._remaster and len(actuals) < len(existing):
            extra_files = [p.name for p in existing[len(actuals) :]]
            pytest.fail(
                f"Expected {len(existing)} results but got {len(actuals)}. "
                f"Extra files: {extra_files}. Run with --remaster to clean up.",
                pytrace=False,
            )
