"""Golden master comparison with optional auto-regeneration."""

from __future__ import annotations

import difflib
import itertools
import json
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
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


def json_serializer(
    *, indent: int = 2, sort_keys: bool = True, ensure_ascii: bool = False
) -> Callable[[Any], str]:
    """Return a serializer writing a value as human-reviewable JSON.

    The counterpart of ``deserializer=json.loads`` for numeric goldens::

        golden_master.check(
            metrics,
            golden_dir / "nominal.metrics.json",
            serializer=json_serializer(),
            deserializer=json.loads,
            matcher=tolerance_matcher(TOLERANCES),
            roundtrip=True,
        )

    Args:
        indent: Indentation level. Default: 2.
        sort_keys: Sort object keys for a stable diff. Default: True.
        ensure_ascii: Escape non-ASCII characters. Default: False.

    """

    def _serialize(value: Any) -> str:
        return json.dumps(
            value, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii
        )

    return _serialize


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


def _build_override_chain(base: str | Path, **dimensions: str) -> list[Path]:
    """Build a priority-ordered list of override paths from *base* and *dimensions*.

    Generates every non-empty subset of *dimensions* (most specific first)
    and inserts the values as dot-separated segments between the stem and
    the suffix of *base*.  Key insertion order determines priority.

    Example::

        _build_override_chain(
            "a.txt",
            version="312", platform="linux", implementation="cpython",
        )
        # [a.312.linux.cpython.txt,
        #  a.312.linux.txt,
        #  a.312.cpython.txt,
        #  a.312.txt,
        #  a.linux.cpython.txt,
        #  a.linux.txt,
        #  a.cpython.txt]

    """
    base = Path(base)
    keys = list(dimensions)
    result: list[Path] = []
    # From all dimensions down to single dimension
    for size in range(len(keys), 0, -1):
        for combo in itertools.combinations(keys, size):
            segment = ".".join(dimensions[k] for k in combo)
            result.append(base.parent / f"{base.stem}.{segment}{base.suffix}")
    return result


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


@dataclass(frozen=True)
class Output:
    """Per-output spec for :meth:`GoldenMaster.check_each`.

    Lets each suffix use its own serialization and comparison — e.g. a CSV
    DataFrame next to a JSON metrics file::

        golden_master.check_each(
            case,
            runner=run,
            extractors={
                ".csv": Output(
                    lambda r: r.df,
                    serializer=dataframe_serializer(),
                    deserializer=dataframe_deserializer(),
                    matcher=tolerance_matcher(TOL),
                    roundtrip=True,
                ),
                ".stdout": lambda r: r.out,  # bare callable still accepted
            },
        )

    ``serializer`` and ``name`` fall back individually to the shared
    ``check_each`` keyword arguments. The comparison fields (*normalizer*,
    *deserializer*, *matcher*, *roundtrip*) inherit as a unit: setting any
    of them replaces the shared comparison entirely, so an output never
    mixes its own normalizer with an inherited matcher.

    ``name`` overrides the expected file name (default
    ``expected{suffix}`` via ``case.expected()``); a callable receives the
    :class:`CaseData` — e.g. ``lambda case: f"{case.input.name}.csv"``.
    """

    extract: Callable[[Any], Any]
    serializer: Callable[[Any], str] | None = None
    normalizer: Callable[[str], str] | None = None
    deserializer: Callable[[str], Any] | None = None
    matcher: Callable[[Any, Any], bool] | None = None
    roundtrip: bool | None = None
    name: str | Callable[[CaseData], str] | None = None

    def overrides_comparison(self) -> bool:
        """Whether this output replaces the shared comparison strategy."""
        return (
            self.normalizer is not None
            or self.deserializer is not None
            or self.matcher is not None
            or self.roundtrip is not None
        )


class GoldenMaster:
    """Golden master comparison with optional auto-regeneration."""

    def __init__(self, remaster: bool, config: Config | None = None) -> None:
        self._remaster = remaster
        self._config = config
        self._updated: list[str] = []
        self._collecting_depth = 0
        self._mismatches: list[str] = []

    @contextmanager
    def collecting(self) -> Iterator[None]:
        """Defer mismatch failures and report them all at exit.

        Inside the context, a failing ``check()`` records its failure
        instead of failing the test immediately, so every comparison runs.
        On exit, a single failure lists all recorded mismatches. Useful
        when one expensive run produces many files to check::

            with golden_master.collecting():
                for name, result in results.items():
                    golden_master.check(result, GOLDEN_DIR / f"{name}.csv")

        Remaster mode is unaffected: updates are aggregated at fixture
        teardown by :meth:`assert_remastered` as usual.

        Blocks nest: helpers may wrap their checks in ``collecting()``
        while the caller holds its own block; everything is reported once,
        at the outermost exit.
        """
        self._collecting_depth += 1
        try:
            yield
        finally:
            self._collecting_depth -= 1
            if self._collecting_depth == 0:
                mismatches = self._mismatches[:]
                self._mismatches.clear()
            else:
                mismatches = []
        if mismatches:
            count = len(mismatches)
            pytest.fail(
                f"{count} golden master mismatch{'es' if count > 1 else ''}:\n\n"
                + "\n\n".join(mismatches),
                pytrace=False,
            )

    def _fail(self, message: str) -> None:
        """Fail immediately, or record the failure inside collecting()."""
        if self._collecting_depth:
            self._mismatches.append(message)
        else:
            pytest.fail(message, pytrace=False)

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
        dimensions: dict[str, str] | None = None,
        serializer: Callable[[Any], str] = str,
        normalizer: Callable[[str], str] | None = None,
        deserializer: Callable[[str], Any] | None = None,
        matcher: Callable[[Any, Any], bool] | None = None,
        roundtrip: bool = False,
    ) -> None:
        """Compare one actual value against one expected file.

        Args:
            actual: The actual value, or a callable that produces it.
            expected_path: Path to the expected output file (generic base).
            override_path: Optional single override path.  Mutually exclusive
                with *dimensions*.
            dimensions: Mapping of dimension names to values (e.g.
                ``{"version": "312", "platform": "linux"}``).  Generates a
                priority-ordered chain of override paths from most to least
                specific.  Mutually exclusive with *override_path*.
            serializer: Converts actual value to string. Default: str().
            normalizer: Optional function applied to both actual and expected
                strings before comparison. The normalized output is also
                written when remastering. Mutually exclusive with *matcher*.
            deserializer: Optional function parsing the expected file text
                back into a value for *matcher*. Requires *matcher*.
            matcher: Optional comparison hook replacing string equality.
                Called with the actual value (before serialization) and the
                expected value (the file text, deserialized when
                *deserializer* is given). Returns True on match. May raise
                AssertionError instead of returning False; its message is
                then shown in place of the string diff. Mutually exclusive
                with *normalizer*. If the serialized actual equals the file
                text, the values match without consulting the matcher.
            roundtrip: Pass ``deserializer(serializer(actual))`` to the
                matcher instead of the raw actual value, so both sides carry
                the storage precision and serialization rounding can never
                trip a tight tolerance. Requires *matcher* and *deserializer*.

        """
        expected_path = Path(expected_path)
        self._validate_check_args(
            override_path=override_path,
            dimensions=dimensions,
            normalizer=normalizer,
            deserializer=deserializer,
            matcher=matcher,
            roundtrip=roundtrip,
        )

        chain = self._resolve_chain(expected_path, override_path, dimensions)
        actual_value, actual_str = self._resolve_actual(
            actual, expected_path, serializer
        )
        if roundtrip:
            assert deserializer is not None  # guaranteed by roundtrip validation
            actual_value = deserializer(actual_str)
        self._check_resolved(
            actual_value,
            actual_str,
            expected_path,
            chain,
            dimensions=dimensions,
            normalizer=normalizer,
            deserializer=deserializer,
            matcher=matcher,
        )

    @staticmethod
    def _validate_check_args(
        *,
        override_path: str | Path | None,
        dimensions: dict[str, str] | None,
        normalizer: Callable[[str], str] | None,
        deserializer: Callable[[str], Any] | None,
        matcher: Callable[[Any, Any], bool] | None,
        roundtrip: bool,
    ) -> None:
        if override_path is not None and dimensions is not None:
            msg = "override_path and dimensions are mutually exclusive"
            raise ValueError(msg)
        if matcher is not None and normalizer is not None:
            msg = "matcher and normalizer are mutually exclusive"
            raise ValueError(msg)
        if deserializer is not None and matcher is None:
            msg = "deserializer requires matcher"
            raise ValueError(msg)
        if roundtrip and (matcher is None or deserializer is None):
            msg = "roundtrip requires matcher and deserializer"
            raise ValueError(msg)

    def _check_resolved(
        self,
        actual_value: Any,
        actual_str: str,
        expected_path: Path,
        chain: list[Path],
        *,
        dimensions: dict[str, str] | None,
        normalizer: Callable[[str], str] | None,
        deserializer: Callable[[str], Any] | None,
        matcher: Callable[[Any, Any], bool] | None,
    ) -> None:
        # Resolution: first existing file in chain, else base
        compare_path, fallback_paths = self._resolve_compare(expected_path, chain)

        try:
            expected_str = compare_path.read_text(encoding="utf-8").rstrip()
        except FileNotFoundError:
            expected_str = None

        # Both empty and no file: nothing to check
        if not actual_str and expected_str is None:
            return

        if matcher is not None:
            matched, detail = self._matcher_matches(
                actual_value, actual_str, expected_str, matcher, deserializer
            )
        else:
            matched = self._content_matches(actual_str, expected_str, normalizer)
            detail = None
        if matched:
            self._dedup_chain(compare_path, fallback_paths, expected_path, normalizer)
            return

        # New test with dimensions (no files exist): create the base file.
        # Existing test or explicit override_path: write to chain[0].
        write_path = expected_path
        if chain and not (dimensions is not None and expected_str is None):
            write_path = chain[0]
        if self._remaster:
            self._remaster_file(
                normalizer(actual_str) if normalizer else actual_str,
                expected_str,
                write_path,
            )
            self._dedup_chain(write_path, fallback_paths, expected_path, normalizer)
        else:
            self._fail_mismatch(
                actual_str, expected_str, expected_path, write_path, detail=detail
            )

    @staticmethod
    def _resolve_chain(
        expected_path: Path,
        override_path: str | Path | None,
        dimensions: dict[str, str] | None,
    ) -> list[Path]:
        if dimensions is not None:
            return _build_override_chain(expected_path, **dimensions)
        if override_path is not None:
            return [Path(override_path)]
        return []

    @staticmethod
    def _resolve_compare(
        expected_path: Path, chain: Sequence[Path]
    ) -> tuple[Path, list[Path]]:
        """Return (compare_path, less_specific_paths) from the chain."""
        for i, path in enumerate(chain):
            if path.exists():
                return path, list(chain[i + 1 :])
        return expected_path, []

    @staticmethod
    def _resolve_actual(
        actual: Any | Callable[[], Any],
        expected_path: Path,
        serializer: Callable[[Any], str],
    ) -> tuple[Any, str]:
        if callable(actual) and not isinstance(actual, str):
            try:
                actual = actual()
            except FileNotFoundError as exc:
                raise MalformedTestCase(
                    f"{expected_path.parent} — {exc.filename or exc}\n"
                    f"  (directory was discovered as a test case"
                    f" but appears malformed)"
                ) from exc
        return actual, serializer(actual).rstrip()

    @staticmethod
    def _matcher_matches(
        actual_value: Any,
        actual_str: str,
        expected_str: str | None,
        matcher: Callable[[Any, Any], bool],
        deserializer: Callable[[str], Any] | None,
    ) -> tuple[bool, str | None]:
        """Return (matched, failure_detail) from the matcher hook."""
        if expected_str is None:
            return False, None
        # Identical serialized content matches by definition (the serializer
        # is deterministic); the matcher only ever sees genuine drift.
        if actual_str == expected_str:
            return True, None
        expected_value = deserializer(expected_str) if deserializer else expected_str
        try:
            return bool(matcher(actual_value, expected_value)), None
        except AssertionError as exc:
            return False, str(exc)

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
        extractors: Mapping[str, Callable[[Any], Any] | Output],
        serializer: Callable[[Any], str] = str,
        normalizer: Callable[[str], str] | None = None,
        deserializer: Callable[[str], Any] | None = None,
        matcher: Callable[[Any, Any], bool] | None = None,
        roundtrip: bool = False,
    ) -> None:
        """Run a function on a case and check named outputs.

        Args:
            case: The test case.
            runner: Callable that takes the case and returns a result object.
            extractors: Mapping of file suffix to either an extractor
                function (receives the result from ``runner``, returns the
                value to compare) or an :class:`Output` spec carrying
                per-output serialization, comparison and file naming.
            serializer: Converts each value to string. Default: str().
            normalizer: Optional function applied before comparison.
            deserializer: Optional parser for expected file text. See check().
            matcher: Optional comparison hook. See check().
            roundtrip: Round-trip actual through storage. See check().

        The shared keyword arguments are defaults; an :class:`Output` that
        sets any comparison field (normalizer, deserializer, matcher,
        roundtrip) replaces the shared comparison entirely.

        """
        try:
            result = runner(case)
        except FileNotFoundError as exc:
            raise MalformedTestCase(
                f"{case.input} — {exc.filename or exc}\n"
                f"  (directory was discovered as a test case but appears malformed)"
            ) from exc
        for suffix, spec in extractors.items():
            output = spec if isinstance(spec, Output) else Output(extract=spec)
            overrides = output.overrides_comparison()
            self.check(
                output.extract(result),
                self._output_path(case, suffix, output.name),
                serializer=output.serializer or serializer,
                normalizer=output.normalizer if overrides else normalizer,
                deserializer=output.deserializer if overrides else deserializer,
                matcher=output.matcher if overrides else matcher,
                roundtrip=bool(output.roundtrip) if overrides else roundtrip,
            )

    @staticmethod
    def _output_path(
        case: CaseData, suffix: str, name: str | Callable[[CaseData], str] | None
    ) -> Path:
        """Resolve the expected file for one check_each() output."""
        if name is None:
            return case.expected(suffix=suffix)
        filename = name if isinstance(name, str) else name(case)
        # Mirror CaseData.expected(): file-mode inputs (with a suffix) get a
        # sibling file, directory-mode inputs contain the file.
        if case.input.suffix:
            return case.input.parent / filename
        return case.input / filename

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

    def _dedup_chain(
        self,
        current: Path,
        fallback_paths: list[Path],
        base: Path,
        normalizer: Callable[[str], str] | None,
    ) -> None:
        """Delete *current* if identical to any less-specific file."""
        if not current.exists():
            return
        # Check against each less-specific override, then the base
        candidates = [p for p in fallback_paths if p.exists()]
        candidates.append(base)
        current_content = current.read_text(encoding="utf-8").rstrip()
        if normalizer:
            current_content = normalizer(current_content)
        for candidate in candidates:
            if not candidate.exists() or candidate == current:
                continue
            candidate_content = candidate.read_text(encoding="utf-8").rstrip()
            if normalizer:
                candidate_content = normalizer(candidate_content)
            if current_content != candidate_content:
                continue
            if self._remaster:
                current.unlink()
                self._updated.append(f"deleted (redundant): {current}")
            else:
                self._fail(
                    f"{current} is identical to {candidate},"
                    f" remove the redundant override."
                )
            return

    def _fail_mismatch(
        self,
        actual_str: str,
        expected_str: str | None,
        compare_path: Path,
        write_path: Path,
        *,
        detail: str | None = None,
    ) -> None:
        if expected_str is None:
            self._fail(
                f"Expected file {compare_path} does not exist. "
                f"Run with --remaster to create {write_path}."
            )
            return
        if detail is not None:
            self._fail(
                f"Mismatch at {compare_path}:\n{detail}\n"
                f"Run with --remaster to update {write_path}."
            )
            return
        diff_lines = list(
            difflib.unified_diff(
                expected_str.splitlines(keepends=True),
                actual_str.splitlines(keepends=True),
                fromfile=str(compare_path),
                tofile="actual",
            )
        )
        diff_text = self._maybe_truncate(diff_lines)
        self._fail(
            f"Mismatch at {compare_path}:\n{diff_text}\n"
            f"Run with --remaster to update {write_path}."
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
        deserializer: Callable[[str], Any] | None = None,
        matcher: Callable[[Any, Any], bool] | None = None,
        roundtrip: bool = False,
        suffix: str = "",
    ) -> None:
        """Compare multiple actuals against expected_0, expected_1, ... files.

        Args:
            actuals: List of values, or a callable returning a list.
            directory: Directory containing expected_N files.
            serializer: Converts each value to string. Default: str().
            normalizer: Optional function applied before comparison.
            deserializer: Optional parser for expected file text. See check().
            matcher: Optional comparison hook. See check().
            roundtrip: Round-trip actual through storage. See check().
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

        def _index(path: Path) -> int:
            match = re.search(r"\d+", path.name)
            assert match is not None  # every name matched the \d+ pattern above
            return int(match.group())

        existing = sorted(
            (p for p in directory.iterdir() if re.match(pattern, p.name)), key=_index
        )

        for i, actual in enumerate(actuals):
            self.check(
                actual,
                directory / f"expected_{i}{suffix}",
                serializer=serializer,
                normalizer=normalizer,
                deserializer=deserializer,
                matcher=matcher,
                roundtrip=roundtrip,
            )

        self._trim_extra_expected(len(actuals), existing)

    def _trim_extra_expected(self, count: int, existing: list[Path]) -> None:
        """Delete (remaster) or report expected files beyond *count*."""
        if count >= len(existing):
            return
        if self._remaster:
            for extra in existing[count:]:
                extra.unlink()
                self._updated.append(f"deleted: {extra}")
        else:
            extra_files = [p.name for p in existing[count:]]
            self._fail(
                f"Expected {len(existing)} results but got {count}. "
                f"Extra files: {extra_files}. Run with --remaster to clean up."
            )
