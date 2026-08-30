"""Starting the application, and the one command-line surface it has.

`plainspeak-desktop` opens the window. `plainspeak-desktop --self-test` does not:
it verifies that a packaged build actually carries the engine's data and produces
the expected answer, and exits with a status a build job can act on.

There is no update check, no analytics, no crash upload and no network call of
any kind on any path through this module.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .. import __version__
from . import APPLICATION_NAME, ORGANIZATION_DOMAIN, ORGANIZATION_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plainspeak-desktop",
        description=(
            "PlainSpeak desktop review. Opens a document, shows what would change "
            "and why, and writes the result to a new file. The document you open "
            "is never modified."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="A .txt, .md or .markdown document to open on startup.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Verify that this build carries the engine's rules, profiles and data "
            "and produces the expected output, then exit. Opens no window."
        ),
    )
    parser.add_argument("--version", action="version", version=f"PlainSpeak {__version__}")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    arguments = build_parser().parse_args(argv if argv is not None else sys.argv[1:])

    if arguments.self_test:
        # Imported here so the self-test can run in a build environment where
        # opening a display is impossible.
        from .selftest import run_self_test

        return run_self_test([])

    return run_gui(arguments.path)


def run_gui(path: Optional[str] = None) -> int:
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    application = QApplication.instance() or QApplication(sys.argv[:1])
    application.setApplicationName(APPLICATION_NAME)
    application.setApplicationDisplayName(APPLICATION_NAME)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setOrganizationDomain(ORGANIZATION_DOMAIN)
    application.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()
    if path:
        window.load_path(Path(path))

    return application.exec()


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
