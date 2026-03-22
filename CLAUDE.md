# pytest-remaster

Golden master testing framework for pytest with automatic regeneration.

## Project structure

- `src/pytest_remaster/plugin.py` — Pytest plugin: `--remaster`/`--no-remaster` options,
  `remaster` and `golden_master` fixtures
- `src/pytest_remaster/core.py` — Core logic: `GoldenMaster`, `CaseData`,
  `FilePatchRegistry`, `discover_test_cases`, `discover_test_files`, normalizers
- `tests/test_plugin.py` — Tests for the plugin options and fixtures (via pytester)
- `tests/test_core.py` — Tests for core logic (via pytester)
- `tests/demo/` — Demo chatbot app exercising the framework end-to-end

## Public API

- `GoldenMaster` — fixture, `check()` for single file, `check_all()` for directory
- `CaseData` — returned by discovery, `.input` path + `.expected(index, suffix)` helper
- `FilePatchRegistry` — register file→mock mappings, `@patcher.use` decorator
- `discover_test_cases(base_dir)` — leaf directories → `CaseData`
- `discover_test_files(base_dir, pattern)` — files by glob → `CaseData`
- `json_normalizer`, `whitespace_normalizer` — opt-in normalizers for `check()`

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Pre-commit hooks require the venv on PATH for pylint:

```bash
export PATH="$(pwd)/.venv/bin:$PATH"
```

## Testing notes

- All tests use `pytester` (subprocess-based) for proper pytest plugin testing
- Coverage shows ~65% because imports and def/class lines execute at plugin load time
  before coverage starts — function bodies are fully covered
- `plugin.py` keeps `pragma: no cover` since it's loaded before coverage and fully
  tested via pytester
- Do not add `Co-Authored-By` in commit messages
