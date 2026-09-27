"""Nothing tells a user to install `plainspeak` from PyPI.

The name `plainspeak` on PyPI belongs to an unrelated project that also
installs a package called `plainspeak`. A help message or document that said
"pip install plainspeak" would install somebody else's software. Found while
preparing publication: the web command's error message did exactly that.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: "pip install plainspeak", with or without extras or quotes, not followed by
#: " @ git+" — the repository install is fine.
_FROM_PYPI = re.compile(r"pip install ['\"]?plainspeak(\[[^\]]*\])?['\"]?(?![\[\w-]|\s*@)")

#: Historical records of the original experiment, kept as evidence and not
#: updated, and this test itself.
_HISTORICAL = {"DECISIONS.md", "PROGRESS.md", "FINAL_REPORT.md", "Experiment Report.md"}


def _user_facing_files():
    yield from (p for p in ROOT.glob("*.md") if p.name not in _HISTORICAL)
    yield from (ROOT / "plainspeak").rglob("*.py")


def test_no_user_facing_text_recommends_installing_plainspeak_from_pypi():
    offences = []
    for path in _user_facing_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _FROM_PYPI.search(line) and "Do not" not in line and "installs an unrelated" not in line:
                offences.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not offences, "\n".join(offences)
