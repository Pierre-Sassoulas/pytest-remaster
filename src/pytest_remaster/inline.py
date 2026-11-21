"""Inline expectations: golden values stored in comments of the input file."""

from __future__ import annotations

import operator
import re
from collections.abc import Callable, Collection, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InlineLine:
    """One line of an input file carrying inline expectations.

    Given to the ``runner`` (or directly to the extractors) of
    :meth:`GoldenMaster.check_inline`.

    Attributes:
        path: The input file.
        lineno: Line number in the file, starting at 1.
        code: The text of the line before its expectation comments,
            without trailing whitespace.
        expected: The expectations written for the line, by key (or by
            ``key(argument)`` when the comment gives an argument). They
            come from the line itself, or from another line pointing at
            it (``# +1: key: value``). An expectation written for another
            interpreter version is left out.

    """

    path: Path
    lineno: int
    code: str
    expected: Mapping[str, str]


def read_lines(path: Path) -> list[str]:
    """Return the lines of *path* with their line endings untouched."""
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read().splitlines(keepends=True)


def write_lines(path: Path, lines: list[str]) -> None:
    """Write *lines* back to *path* without translating line endings."""
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("".join(lines))


_OPERATORS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}


def expectation_pattern(
    keys: Collection[str], comment: str, key_pattern: str | None = None
) -> re.Pattern[str]:
    """Return the pattern matching one ``<comment> <key>: <value>``.

    The value runs up to the next expectation comment or the end of the
    line, so one line can carry several expectations. A version
    condition may come before the key: ``<comment> >=3.14: <key>: <value>``.
    An argument may follow the key: ``<comment> <key>(<argument>): <value>``.
    The line the expectation is about may come first, relative
    (``<comment> +1: <key>: <value>``) or absolute (``<comment> 12: ...``).

    With *key_pattern*, a key is anything matching that regular expression
    instead of one of *keys*, and has no separate argument.
    """
    condition = (
        r"(?:(?P<line>[+-]?[0-9]+):)?[ \t]*"
        r"(?:(?P<op>[><=]+) *(?P<version>[0-9.]+):)?"
    )
    if key_pattern is not None:
        alternatives, argument = _unnamed(key_pattern), ""
    elif keys:
        # Longest first, so a key never shadows a longer one it is a prefix of.
        alternatives = "|".join(
            re.escape(k) for k in sorted(keys, key=len, reverse=True)
        )
        argument = r"(?:\((?P<argument>[^()]*)\))?"
    else:
        msg = "check_inline needs at least one extractor"
        raise ValueError(msg)
    marker = (
        rf"{re.escape(comment)}[ \t]*{condition}[ \t]*(?:{alternatives}){argument}:"
    )
    return re.compile(
        rf"{re.escape(comment)}[ \t]*{condition}[ \t]*"
        rf"(?P<label>(?P<key>{alternatives}){argument}):"
        rf"[ \t]*(?P<value>.*?)[ \t]*(?={_unnamed(marker)}|$)"
    )


def _unnamed(pattern: str) -> str:
    """Return *pattern* with its named groups made anonymous."""
    return re.sub(r"\(\?P<\w+>", "(?:", pattern)


def split_label(label: str) -> tuple[str, str | None]:
    """Return the key and the argument of ``key`` or ``key(argument)``."""
    key, opening, rest = label.partition("(")
    return (key, rest[:-1]) if opening else (key, None)


def _applies(match: re.Match[str], version: tuple[int, ...]) -> bool:
    """Whether the expectation of *match* is written for *version*."""
    if match["version"] is None:
        return True
    if match["op"] not in _OPERATORS:
        msg = (
            f"unknown version operator {match['op']!r} in {match[0]!r},"
            f" use one of {', '.join(_OPERATORS)}"
        )
        raise ValueError(msg)
    required = tuple(int(part) for part in match["version"].split("."))
    return bool(_OPERATORS[match["op"]](version, required))


def _target(match: re.Match[str], lineno: int) -> int:
    """Return the line the expectation of *match*, found on *lineno*, is about."""
    if (line := match["line"]) is None:
        return lineno
    return lineno + int(line) if line[0] in "+-" else int(line)


def _expectations(
    raw: str, pattern: re.Pattern[str], after_code: bool
) -> list[re.Match[str]]:
    """Return the expectation comments of one line.

    With *after_code*, a line holding only comments has none, unless they
    point at another line: an open key pattern would otherwise read
    ``# Note: ...`` as an expectation.
    """
    matches = list(pattern.finditer(raw.rstrip("\r\n")))
    if matches and after_code and not raw[: matches[0].start()].strip():
        return [match for match in matches if match["line"] is not None]
    return matches


def _code(raw: str, pattern: re.Pattern[str]) -> str:
    """Return the text of a line before its expectation comments."""
    text = raw.rstrip("\r\n")
    first = pattern.search(text)
    return (text[: first.start()] if first else text).rstrip()


def has_expectation(
    lines: list[str], pattern: re.Pattern[str], after_code: bool = False
) -> bool:
    """Whether *lines* carry an expectation, for any version."""
    return any(_expectations(raw, pattern, after_code) for raw in lines)


def find_inline_lines(
    path: Path,
    lines: list[str],
    pattern: re.Pattern[str],
    version: tuple[int, ...],
    after_code: bool = False,
) -> Iterator[InlineLine]:
    """Yield every line of *lines* with an expectation written for *version*.

    The expectations of a line are gathered from wherever they are
    written: on the line, or on a line pointing at it.
    """
    expected: dict[int, dict[str, str]] = {}
    for lineno, raw in enumerate(lines, start=1):
        for match in _expectations(raw, pattern, after_code):
            if not _applies(match, version):
                continue
            target = _target(match, lineno)
            if not 1 <= target <= len(lines):
                msg = (
                    f"{path}:{lineno}: {match[0]!r} points at line {target},"
                    f" the file has {len(lines)} lines"
                )
                raise ValueError(msg)
            expected.setdefault(target, {})[match["label"]] = match["value"]
    for target in sorted(expected):
        yield InlineLine(
            path=path,
            lineno=target,
            code=_code(lines[target - 1], pattern),
            expected=expected[target],
        )


def _rewrite_line(
    raw: str, matches: list[re.Match[str]], lineno: int, actual: Mapping[Any, str]
) -> str:
    """Return *raw* with the values of *matches* found in *actual* replaced."""
    text = raw.rstrip("\r\n")
    ending = raw[len(text) :]
    for match in reversed(matches):
        if (key := (_target(match, lineno), match["label"])) not in actual:
            continue
        after = text[match.end() :]
        text = (
            text[: match.end("label") + 1]
            + (f" {actual[key]}" if actual[key] else "")
            + (f"  {after}" if after else "")
        )
    return f"{text.rstrip()}{ending}"


def rewrite_lines(
    lines: list[str],
    pattern: re.Pattern[str],
    version: tuple[int, ...],
    actual: Mapping[tuple[int, str], str],
    after_code: bool = False,
) -> list[str]:
    """Return *lines* with the values written for *version* replaced.

    *actual* holds the new values by line they are about and key. Only
    these values change: the code, the other expectations, those written
    for another version and the line endings are kept as they are.
    """
    rewritten = []
    for lineno, raw in enumerate(lines, start=1):
        matches = [
            match
            for match in _expectations(raw, pattern, after_code)
            if _applies(match, version)
        ]
        rewritten.append(_rewrite_line(raw, matches, lineno, actual))
    return rewritten


Extractors = Mapping[str, Callable[..., Any]] | Callable[[Any, str], Any]


def inline_pattern(
    extractors: Extractors, key_pattern: str | None, comment: str
) -> re.Pattern[str]:
    """Return the expectation pattern of one ``check_inline`` call."""
    if isinstance(extractors, Mapping) == (key_pattern is not None):
        msg = (
            "check_inline takes either a mapping of extractors,"
            " or one function with a key_pattern"
        )
        raise ValueError(msg)
    keys = extractors.keys() if isinstance(extractors, Mapping) else ()
    return expectation_pattern(keys, comment, key_pattern)


def inline_keys(extractors: Extractors, key_pattern: str | None, comment: str) -> str:
    """Describe the comments ``check_inline`` looks for, for an error message."""
    if not isinstance(extractors, Mapping):
        return f"a comment matching '{comment} {key_pattern}:' after some code"
    return ", ".join(f"'{comment} {key}:'" for key in extractors)


def inline_actuals(
    extractors: Extractors, runner: Callable[[InlineLine], Any] | None, line: InlineLine
) -> Iterator[tuple[str, Any]]:
    """Yield the actual value of every expectation of *line*, by label."""
    result = runner(line) if runner is not None else line
    for label in line.expected:
        if not isinstance(extractors, Mapping):
            yield label, extractors(result, label)
            continue
        key, argument = split_label(label)
        if argument is None:
            yield label, extractors[key](result)
        else:
            yield label, extractors[key](result, argument)


def inline_value(value: str, line: InlineLine) -> str:
    """Return *value* ready to be written in a comment of *line*."""
    value = value.strip()
    if "\n" in value or "\r" in value:
        msg = (
            f"{line.path}:{line.lineno}: an inline expectation must fit"
            f" on one line, got {value!r}"
        )
        raise ValueError(msg)
    return value


def inline_changes(
    lines: Iterator[InlineLine],
    extractors: Extractors,
    runner: Callable[[InlineLine], Any] | None,
    serializer: Callable[[Any], str],
) -> dict[tuple[int, str], tuple[str, str]]:
    """Return the expected and actual values that differ, by line and label."""
    changed = {}
    for line in lines:
        for label, value in inline_actuals(extractors, runner, line):
            expected = line.expected[label]
            if (actual := inline_value(serializer(value), line)) != expected:
                changed[line.lineno, label] = (expected, actual)
    return changed
