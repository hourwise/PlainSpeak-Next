"""The PlainSpeak desktop application.

An adapter, and nothing more. Every decision it displays was made by the
pipeline: which changes are safe, which need a person, which the firewall
refused, what the style layer observed, and what the revised document says. The
desktop arranges those on a screen and sends review decisions back through the
Phase 9 contract. It has no engine of its own and no opinion it could disagree
with the engine about.

Two boundaries hold this in place, and both are enforced by tests rather than
convention.

**Qt lives only here.** No engine layer imports PySide6 — not `core`, not
`document`, not `rules`, `integrity`, `morphology`, `style` or `pipeline`. The
desktop is the only package that knows a GUI exists.

**The desktop imports only the pipeline.** Where it needed something the
pipeline did not expose, the answer was to widen the pipeline facade rather than
to reach around it into `rules` or `style`. `ReviewBundle` and `PreviewResult`
exist because of that rule: an interface joining four independent engine
authorities together in a widget would be re-implementing the engine somewhere
nobody would test it.

Importing this package does *not* import Qt. `session` — the state machine, the
review decisions and the save service — is deliberately Qt-free so that the
behaviour worth testing can be tested without an event loop or a display.
"""
from __future__ import annotations

__all__ = ["APPLICATION_NAME", "ORGANIZATION_NAME", "main", "run_self_test"]

#: Used for Qt's own settings and window identity. No auto-update URL, and
#: nothing here reaches a network.
APPLICATION_NAME = "PlainSpeak"
ORGANIZATION_NAME = "PlainSpeak"
ORGANIZATION_DOMAIN = "plainspeak.local"


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop application, or run the packaged self-test.

    Imported lazily so that this module — and therefore `plainspeak.desktop` —
    can be imported without PySide6 present.
    """
    from .app import main as _main

    return _main(argv)


def run_self_test(argv: list[str] | None = None) -> int:
    from .selftest import run_self_test as _run

    return _run(argv)
