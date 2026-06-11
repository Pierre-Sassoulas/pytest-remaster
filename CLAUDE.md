# pytest-remaster

Pytest plugin for golden master (characterisation) testing with automatic expected file
regeneration.

## Project structure

- `src/pytest_remaster/plugin.py` — Pytest plugin: `--remaster`/`--no-remaster` options,
  `remaster` and `golden_master` fixtures
- `src/pytest_remaster/discovery.py` — `CaseData`, `discover_test_cases`,
  `discover_test_files`
- `src/pytest_remaster/golden_master.py` — `GoldenMaster`, `MalformedTestCase`,
  normalizers
- `src/pytest_remaster/matchers.py` — `tolerance_matcher`
- `src/pytest_remaster/pandas_io.py` — `dataframe_serializer`, `dataframe_deserializer`
  (requires the `pandas` extra; lazily exported via `__getattr__` in `__init__.py` so
  the core package stays stdlib-pure)
- `src/pytest_remaster/patching.py` — `PatchRegistry`
- `tests/test_plugin.py` — Tests for plugin options and fixtures (via pytester)
- `tests/test_golden_master.py` — Tests for GoldenMaster (via pytester)
- `tests/test_discovery.py` — Tests for discovery (via pytester)
- `tests/test_patching.py` — Tests for PatchRegistry (via pytester)
- `tests/test_matcher.py` — Tests for matcher/deserializer hooks (via pytester)
- `tests/test_collecting.py` — Tests for collecting() failure aggregation (via pytester)
- `tests/test_output_spec.py` — Tests for the Output spec in check_each (via pytester)
- `tests/test_pandas_io.py` — Tests for pandas helpers (importorskip pandas)
- `tests/test_tolerance_matcher.py` — Tests for tolerance_matcher (direct calls; it is a
  pure function, pytester only for the fixture integration test)
- `tests/demo/` — Demo chatbot app exercising the framework end-to-end
- `tests/demo_subprocess/` — Demo CLI app with capsys/caplog capture

## Public API

- `GoldenMaster` — fixture, `check()` for single file, `check_all()` for directory,
  `check_each()` for named outputs (runner + extractors)
  - `matcher=` + `deserializer=` — pluggable comparison on deserialized values (e.g.
    numeric tolerance); matcher may raise AssertionError for rich failure detail
  - `roundtrip=` — matcher receives `deserializer(serializer(actual))` so both sides
    carry storage precision; identical serialized content matches without the matcher
- `tolerance_matcher(tolerances, rel=, default=, report_limit=, nan_equal=, total_limit=)`
  — built-in matcher: per-key tolerances (exact key, then fnmatch patterns, then
  default), table values are atol floats or `(atol, rtol)` pairs, recurses
  mappings/sequences, raises AssertionError listing values beyond tolerance; NaN == NaN
  by default
  - `collecting()` — context manager deferring strict-mode failures; reports all
    mismatches in one failure at the outermost exit (re-entrant)
- `Output` — per-suffix spec for `check_each()`: extract + own
  serializer/normalizer/deserializer/matcher/roundtrip + `name` override (str or
  callable receiving CaseData); comparison fields override the shared kwargs as a unit
- `dataframe_serializer(float_format=)` / `dataframe_deserializer(index_col=)` — CSV at
  fixed precision out, column → series mapping back in (`pandas` extra)
- `CaseData` — returned by discovery, `.input` path + `.expected(index, suffix)` helper
  - `expected(index=, suffix=)` — directory mode: `expected_{index}{suffix}`
  - `expected(suffix=)` — directory mode: `expected{suffix}`, file mode: replaces
    extension
- `PatchRegistry` — `add_file_patch()` for file→mock mappings, `add_patch()` for plain
  mocks, `patcher.mock()` context manager yields dict with loaded data + mock objects
- `discover_test_cases(base_dir)` — leaf directories → `CaseData`
- `discover_test_files(base_dir, pattern)` — files by glob → `CaseData`
- `json_normalizer`, `whitespace_normalizer` — opt-in normalizers for `check()`
- `mock_calls_serializer(name)` — serializer for `mock.call_args_list`

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Always lint and format through pre-commit, not by invoking tools directly:

```bash
export PATH="$(pwd)/.venv/bin:$PATH"
pre-commit run --all-files
```

## Testing notes

- All tests use `pytester` (subprocess-based) for proper pytest plugin testing
- Coverage shows ~65% because imports and def/class lines execute at plugin load time
  before coverage starts — function bodies are fully covered
- `plugin.py` keeps `pragma: no cover` since it's loaded before coverage and fully
  tested via pytester
- Do not add `Co-Authored-By` in commit messages
