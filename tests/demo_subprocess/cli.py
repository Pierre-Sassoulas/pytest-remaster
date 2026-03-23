"""Fake CLI tool that writes to stdout, stderr, and logging."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def main(args: list[str] | None = None) -> int:
    """Run the CLI with the given arguments."""
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    if args is None:
        args = sys.argv[1:]

    if not args:
        print("error: no command given", file=sys.stderr)
        return 1

    command, *rest = args

    if command == "greet":
        name = rest[0] if rest else "World"
        logger.info("greeting user %s", name)
        print(f"Hello, {name}!")
        return 0

    if command == "divide":
        expected_args = 2
        if len(rest) != expected_args:
            print("error: divide requires two arguments", file=sys.stderr)
            return 1
        a, b = rest
        logger.debug("dividing %s / %s", a, b)
        try:
            result = int(a) / int(b)
        except ZeroDivisionError:
            logger.error("division by zero: %s / %s", a, b)
            print("error: division by zero", file=sys.stderr)
            return 1
        print(f"{a} / {b} = {result:.2f}")
        return 0

    print(f"error: unknown command: {command}", file=sys.stderr)
    logger.warning("unknown command attempted: %s", command)
    return 1


if __name__ == "__main__":
    sys.exit(main())
