[![PyPI version](https://badge.fury.io/py/pytest-remaster.svg)](https://badge.fury.io/py/pytest-remaster)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pytest-remaster)](https://pypi.org/project/pytest-remaster/)
[![PyPI - License](https://img.shields.io/pypi/l/pytest-remaster)](https://pypi.org/project/pytest-remaster/)

# pytest-remaster

Framework for golden master testing for pytest with automatic regeneration of the golden master.

## Usage

By default, golden master files are automatically regenerated when a comparison fails.
Use `--no-remaster` to get strict failures instead.

The default can be changed in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
remaster-by-default = false
```
