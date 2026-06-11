"""Built-in matchers for tolerance-based golden master comparison."""

from __future__ import annotations

import math
import numbers
from collections.abc import Callable, Mapping, Sequence
from fnmatch import fnmatchcase
from typing import Any, NamedTuple


def _is_number(value: Any) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _join(path: str, key: Any) -> str:
    return f"{path}.{key}" if path else str(key)


class Tolerance(NamedTuple):
    """A per-key tolerance with named terms.

    Being a tuple, it is interchangeable with a bare ``(atol, rtol)``
    pair; the named form keeps tolerance tables readable::

        tolerance_matcher({
            "soc_pct": 0.1,
            "*_kw": Tolerance(atol=0.5, rtol=1e-3),
        })

    Like a bare pair — and unlike a bare float — a ``Tolerance`` does not
    inherit the global ``rel=``: its ``rtol`` is exactly what it says
    (default ``0.0``).
    """

    atol: float = 0.0
    rtol: float = 0.0


ToleranceSpec = float | tuple[float, float] | Tolerance
"""A tolerance table value: absolute tolerance, an ``(atol, rtol)`` pair,
or a :class:`Tolerance`."""


class _ToleranceComparison:  # pylint: disable=too-few-public-methods
    """Recursive numeric comparison with per-key tolerances."""

    def __init__(
        self,
        tolerances: Mapping[str, ToleranceSpec] | None,
        *,
        rel: float,
        default: float,
        report_limit: int,
        nan_equal: bool,
        total_limit: int | None,
    ) -> None:
        # Normalize every entry to an (atol, rtol) pair; bare floats get
        # the global rel.
        self._tolerances = {
            key: spec if isinstance(spec, tuple) else (spec, rel)
            for key, spec in (tolerances or {}).items()
        }
        self._default = (default, rel)
        self._report_limit = report_limit
        self._nan_equal = nan_equal
        self._total_limit = total_limit

    def __call__(self, actual: Any, golden: Any) -> bool:
        failures: list[str] = []
        self._compare("", None, actual, golden, failures=failures)
        if self._total_limit is not None and len(failures) > self._total_limit:
            hidden = len(failures) - self._total_limit
            failures = failures[: self._total_limit]
            failures.append(f"... and {hidden} more values beyond tolerance")
        if failures:
            raise AssertionError("\n".join(failures))
        return True

    def _tolerance_for(self, key: str | None) -> tuple[float, float]:
        """Return the (atol, rtol) pair for *key*."""
        if key is None:
            return self._default
        if key in self._tolerances:
            return self._tolerances[key]
        for pattern, tolerance in self._tolerances.items():
            if fnmatchcase(key, pattern):
                return tolerance
        return self._default

    def _close(self, actual: Any, golden: Any, tolerance: tuple[float, float]) -> bool:
        if _is_number(actual) and _is_number(golden):
            if math.isnan(actual) or math.isnan(golden):
                return self._nan_equal and math.isnan(actual) and math.isnan(golden)
            atol, rtol = tolerance
            return math.isclose(actual, golden, rel_tol=rtol, abs_tol=atol)
        return bool(actual == golden)

    def _compare(
        self,
        path: str,
        key: str | None,
        actual: Any,
        golden: Any,
        *,
        failures: list[str],
    ) -> None:
        if isinstance(actual, Mapping) and isinstance(golden, Mapping):
            self._compare_mapping(path, actual, golden, failures)
            return
        if _is_sequence(actual) and _is_sequence(golden):
            self._compare_sequence(
                path or "value", key, actual, golden, failures=failures
            )
            return
        self._compare_scalar(path or "value", key, actual, golden, failures=failures)

    def _compare_mapping(
        self,
        path: str,
        actual: Mapping[Any, Any],
        golden: Mapping[Any, Any],
        failures: list[str],
    ) -> None:
        for k in golden:
            if k not in actual:
                failures.append(f"{_join(path, k)}: missing from actual")
        for k in actual:
            if k not in golden:
                failures.append(f"{_join(path, k)}: not in golden")
            else:
                self._compare(
                    _join(path, k), str(k), actual[k], golden[k], failures=failures
                )

    def _compare_sequence(
        self,
        path: str,
        key: str | None,
        actual: Any,
        golden: Any,
        *,
        failures: list[str],
    ) -> None:
        actual, golden = list(actual), list(golden)
        if len(actual) != len(golden):
            failures.append(f"{path}: length {len(actual)} != golden {len(golden)}")
            return
        tolerance = self._tolerance_for(key)
        mismatches = [
            i
            for i, (a, g) in enumerate(zip(actual, golden, strict=True))
            if not self._close(a, g, tolerance)
        ]
        for i in mismatches[: self._report_limit]:
            self._compare_scalar(
                f"{path}[{i}]", key, actual[i], golden[i], failures=failures
            )
        if len(mismatches) > self._report_limit:
            failures.append(
                f"{path}: ... and {len(mismatches) - self._report_limit} more"
                f" rows beyond tolerance"
            )

    def _compare_scalar(
        self,
        path: str,
        key: str | None,
        actual: Any,
        golden: Any,
        *,
        failures: list[str],
    ) -> None:
        tolerance = self._tolerance_for(key)
        if self._close(actual, golden, tolerance):
            return
        if _is_number(actual) and _is_number(golden):
            atol, rtol = tolerance
            failures.append(
                f"{path}: golden={golden:.6g} actual={actual:.6g}"
                f" |Δ|={abs(actual - golden):.6g} tol={atol:g}"
                + (f" rel={rtol:g}" if rtol else "")
            )
        else:
            failures.append(f"{path}: golden={golden!r} actual={actual!r}")


def tolerance_matcher(
    tolerances: Mapping[str, ToleranceSpec] | None = None,
    *,
    rel: float = 0.0,
    default: float = 0.0,
    report_limit: int = 5,
    nan_equal: bool = True,
    total_limit: int | None = None,
) -> Callable[[Any, Any], bool]:
    """Return a matcher comparing numeric values with per-key tolerances.

    Compares scalars, sequences, mappings, and mappings of sequences
    (e.g. column → series) recursively. Numbers are compared with
    ``math.isclose``; everything else with equality.

    A tolerance table value is either an absolute tolerance (``0.5``) or
    an ``(atol, rtol)`` pair (``(0.5, 1e-4)``) when a wide-range quantity
    needs a relative tolerance alongside keys that must stay purely
    absolute. Bare floats use the global *rel*.

    NaN handling: with *nan_equal* (the default), two NaN compare equal —
    a reproduced gap in a time series is a match — while NaN vs number is
    a mismatch regardless of tolerance. ``nan_equal=False`` makes any NaN
    a mismatch (the raw ``math.isclose`` behavior).

    The tolerance for a value is resolved from its innermost mapping key:
    exact match first, then ``fnmatch`` patterns in declaration order,
    then *default*. Sequence elements inherit the tolerance of their key.

    Usage::

        golden_master.check(
            metrics,
            expected_path,
            serializer=json.dumps,
            deserializer=json.loads,
            matcher=tolerance_matcher({"hz": 1e-3, "*_kw": 0.5}),
        )

    On mismatch the matcher raises :class:`AssertionError` listing every
    value beyond tolerance (``key[row]: golden=… actual=… |Δ|=… tol=…``),
    capped at *report_limit* rows per sequence.

    Args:
        tolerances: Mapping of key name or ``fnmatch`` pattern to absolute
            tolerance or ``(atol, rtol)`` pair.
        rel: Relative tolerance for entries without their own rtol (and
            for *default*). Default: 0.0.
        default: Absolute tolerance for keys not in *tolerances*.
            Default: 0.0 (exact comparison).
        report_limit: Maximum mismatching rows reported per sequence.
        nan_equal: Whether two NaN compare equal. Default: True.
        total_limit: Maximum failure lines reported overall; the rest is
            summarized as ``... and N more values beyond tolerance``.
            Default: None (unlimited).

    """
    return _ToleranceComparison(
        tolerances,
        rel=rel,
        default=default,
        report_limit=report_limit,
        nan_equal=nan_equal,
        total_limit=total_limit,
    )
