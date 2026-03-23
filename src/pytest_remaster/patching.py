"""PatchRegistry: load fixture files and patch mock targets."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pytest_remaster.discovery import CaseData


@dataclass
class _FileSpec:
    filename: str
    target: str | None
    attr: str
    loader: Callable[[str], Any]
    default: Any
    skip_attr_if_falsy: bool


@dataclass
class _PatchSpec:
    target: str
    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)


def _set_nested_attr(obj: Any, attr_path: str, value: Any) -> None:
    """Set a nested attribute like ``return_value.json.side_effect``."""
    parts = attr_path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


class PatchRegistry:
    """Load fixture files from case directories and patch mock targets.

    Usage::

        patcher = PatchRegistry()
        patcher.add_file_patch("data.json", target="myapp.api.call")
        patcher.add_file_patch("config.json")  # load-only
        patcher.add_patch("subprocess.run")

        with patcher.mock(case_dir) as ctx:
            # patches active, ctx["data.json"] has loaded data
            # ctx["subprocess.run"] is the mock object
            ...
    """

    def __init__(self) -> None:
        self._file_specs: list[_FileSpec] = []
        self._patch_specs: list[_PatchSpec] = []
        self._post_load_hooks: list[Callable[[dict[str, Any], Path], None]] = []

    def add_file_patch(  # pylint: disable=too-many-arguments
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
                    is still available in the context dict.

        """
        self._file_specs.append(
            _FileSpec(
                filename=filename,
                target=target,
                attr=attr,
                loader=loader,
                default=default,
                skip_attr_if_falsy=skip_attr_if_falsy,
            )
        )

    def add_patch(self, target: str, *, name: str | None = None, **kwargs: Any) -> None:
        """Register a plain mock patch (no file involved).

        The mock object is available in the context dict yielded by ``mock()``,
        keyed by ``name`` (defaults to ``target``).

        Args:
            target: Dotted path for ``unittest.mock.patch``.
            name: Key in the context dict. Default: ``target``.
            **kwargs: Extra arguments passed to ``unittest.mock.patch``
                (e.g. ``side_effect=...``, ``new_callable=...``).

        """
        self._patch_specs.append(
            _PatchSpec(target=target, name=name or target, kwargs=kwargs)
        )

    def post_load(
        self, func: Callable[[dict[str, Any], Path], None]
    ) -> Callable[[dict[str, Any], Path], None]:
        """Register a hook that runs after all files are loaded, before patching.

        The hook receives the context dict and the case directory path,
        and can add derived values to the dict.

        Usage::

            @patcher.post_load
            def _build_fixtures(ctx, case_dir):
                ctx["derived"] = transform(ctx["file.json"])

        """
        self._post_load_hooks.append(func)
        return func

    def _load_files(self, case_dir: Path) -> dict[str, Any]:
        ctx: dict[str, Any] = {}
        for spec in self._file_specs:
            filepath = case_dir / spec.filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                ctx[spec.filename] = spec.loader(content)
            else:
                ctx[spec.filename] = spec.default
        for hook in self._post_load_hooks:
            hook(ctx, case_dir)
        return ctx

    def _create_file_patches(self, ctx: dict[str, Any]) -> list[Any]:
        target_mocks: dict[str, Any] = {}
        active_patches: list[Any] = []
        for spec in self._file_specs:
            if spec.target is None:
                continue
            value = ctx[spec.filename]
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

    def _create_plain_patches(self, ctx: dict[str, Any]) -> list[Any]:
        active_patches: list[Any] = []
        for spec in self._patch_specs:
            p = patch(spec.target, **spec.kwargs)
            mock_obj = p.start()
            active_patches.append(p)
            ctx[spec.name] = mock_obj
        return active_patches

    @contextlib.contextmanager
    def mock(self, case_dir: str | Path | CaseData) -> Iterator[dict[str, Any]]:
        """Load fixture files and activate patches.

        Yields a dict mapping filenames to loaded values and patch names
        to mock objects.
        """
        if isinstance(case_dir, CaseData):
            case_dir = case_dir.input
        case_dir = Path(case_dir)
        ctx = self._load_files(case_dir)
        file_patches = self._create_file_patches(ctx)
        plain_patches = self._create_plain_patches(ctx)
        all_patches = file_patches + plain_patches
        try:
            yield ctx
        finally:
            for p in all_patches:
                p.stop()
