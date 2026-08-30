"""Entry point for the frozen desktop build.

`pyside6-deploy` wants one script it can point Nuitka at, and Nuitka follows
imports from there. Keeping it here rather than reaching into the package means
the build has a single obvious starting point, and the package keeps its normal
console entry point (`plainspeak-desktop`) for source installs.

It does nothing itself. The logic is in `plainspeak.desktop.app`, so the frozen
build and the source install run the same code and cannot drift.
"""
from __future__ import annotations

import sys


def main() -> int:
    from plainspeak.desktop.app import main as run

    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
