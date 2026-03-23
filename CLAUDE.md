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
- `src/pytest_remaster/patching.py` — `PatchRegistry`
- `tests/test_plugin.py` — Tests for the plugin options and fixtures (via pytester)
- `tests/test_core.py` — Tests for core logic (via pytester)
- `tests/demo/` — Demo chatbot app exercising the framework end-to-end
- `tests/demo_subprocess/` — Demo CLI app with capsys/caplog capture

## Public API

- `GoldenMaster` — fixture, `check()` for single file, `check_all()` for directory,
  `check_each()` for named outputs (runner + extractors)
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
