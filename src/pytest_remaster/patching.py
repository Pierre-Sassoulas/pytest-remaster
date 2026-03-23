"""FilePatchRegistry: load fixture files and patch mock targets."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pytest_remaster.discovery import CaseData


@dataclass
class _FixtureSpec:
    filename: str
    target: str | None
    attr: str
    loader: Callable[[str], Any]
    default: Any
    skip_attr_if_falsy: bool


def _set_nested_attr(obj: Any, attr_path: str, value: Any) -> None:
    """Set a nested attribute like ``return_value.json.side_effect``."""
    parts = attr_path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


class FilePatchRegistry:
    """Load fixture files from case directories and patch mock targets.

    Usage::

        patcher = FilePatchRegistry()
        patcher.register("data.json", target="myapp.api.call")
        patcher.register("config.json")  # load-only

        with patcher.mock(case_dir) as loaded:
            # patches active, loaded["data.json"] available
            ...
    """

    def __init__(self) -> None:
        self._specs: list[_FixtureSpec] = []
        self._post_load_hooks: list[Callable[[dict[str, Any], Path], None]] = []

    def register(  # pylint: disable=too-many-arguments
        self,
        filename: str,
        *,
        target: str | None = None,
        attr: str = "return_value",
        loader: Callable[[str], Any] = json.loads,
        default: Any = None,
        skip_attr_if_falsy: bool = False,
    ) -> None:
        """Register a fixture file to be loaded and optionally patched.

        Args:
            filename: Name of the file in the case directory.
            target: Dotted path for ``unittest.mock.patch`` (e.g. "myapp.api.call").
                    If ``None``, the file is loaded but not patched.
            attr: Attribute path on the mock to set the loaded value on.
                    Default: ``"return_value"``. Use dotted paths for nested
                    attributes (e.g. ``"return_value.json.side_effect"``).
                    Use ``"new"`` to replace the target directly with the
                    loaded value (for constants, not callables).
            loader: Callable that takes file content (str) and returns the value.
                    Default: ``json.loads``.
            default: Value to use when the file is not present in the case directory.
            skip_attr_if_falsy: If ``True``, the mock target is still patched (blocking
                    real calls) but the attr is not configured when the loaded
                    value is falsy (e.g. ``[]``, ``None``, ``""``). The value
                    is still available in the loaded dict.

        """
        self._specs.append(
            _FixtureSpec(
                filename=filename,
                target=target,
                attr=attr,
                loader=loader,
                default=default,
                skip_attr_if_falsy=skip_attr_if_falsy,
            )
        )

    def post_load(
        self, func: Callable[[dict[str, Any], Path], None]
    ) -> Callable[[dict[str, Any], Path], None]:
        """Register a hook that runs after all files are loaded, before patching.

        The hook receives the loaded dict and the case directory path,
        and can add derived values to the loaded dict.

        Usage::

            @patcher.post_load
            def _build_fixtures(loaded, case_dir):
                loaded["derived"] = transform(loaded["file.json"])

        """
        self._post_load_hooks.append(func)
        return func

    def _load_files(self, case_dir: Path) -> dict[str, Any]:
        loaded: dict[str, Any] = {}
        for spec in self._specs:
            filepath = case_dir / spec.filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                loaded[spec.filename] = spec.loader(content)
            else:
                loaded[spec.filename] = spec.default
        for hook in self._post_load_hooks:
            hook(loaded, case_dir)
        return loaded

    def _create_patches(self, loaded: dict[str, Any]) -> list[Any]:
        target_mocks: dict[str, Any] = {}
        active_patches: list[Any] = []
        for spec in self._specs:
            if spec.target is None:
                continue
            value = loaded[spec.filename]
            if spec.attr == "new":
                if not (spec.skip_attr_if_falsy and not value):
                    p = patch(spec.target, new=value)
                    p.start()
                    active_patches.append(p)
                continue
            if spec.target not in target_mocks:
                p = patch(spec.target)
                target_mocks[spec.target] = p.start()
                active_patches.append(p)
            if not (spec.skip_attr_if_falsy and not value):
                _set_nested_attr(target_mocks[spec.target], spec.attr, value)
        return active_patches

    @contextlib.contextmanager
    def mock(self, case_dir: str | Path | CaseData) -> Generator[dict[str, Any]]:
        """Load fixture files and activate patches.

        Yields a dict mapping filename to loaded value.
        """
        if isinstance(case_dir, CaseData):
            case_dir = case_dir.input
        case_dir = Path(case_dir)
        loaded = self._load_files(case_dir)
        active_patches = self._create_patches(loaded)
        try:
            yield loaded
        finally:
            for p in active_patches:
                p.stop()
