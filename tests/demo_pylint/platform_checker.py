"""A tiny pylint checker that reports the target Python version and platform.

Loaded via ``--load-plugins`` to produce output that genuinely differs
when ``--py-version`` changes.
"""

from __future__ import annotations

import sys

from astroid import nodes
from pylint.checkers import BaseChecker


class PlatformChecker(BaseChecker):
    name = "platform-info"
    msgs = {
        "I9901": (
            "Target: Python %s, %s",
            "platform-info",
            "Reports the target Python version and current platform.",
        )
    }

    def visit_module(self, node: nodes.Module) -> None:
        ver = ".".join(str(v) for v in self.linter.config.py_version)
        self.add_message("platform-info", node=node, args=(ver, sys.platform))


def register(linter: object) -> None:
    """Required entry point for pylint plugins."""
    linter.register_checker(PlatformChecker(linter))  # type: ignore[arg-type]
