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
#: updated.
_HISTORICAL = {"DECISIONS.md", "PROGRESS.md", "FINAL_REPORT.md", "Experiment Report.md"}


def _user_facing_files():
    yield from (p for p in ROOT.glob("*.md") if p.name not in _HISTORICAL)
    yield from (ROOT / "plainspeak").rglob("*.py")


def _paragraphs(text: str):
    """Paragraphs with their first line number, so a wrapped warning is read whole."""
    start, lines = 1, []
    for number, line in enumerate(text.splitlines() + [""], start=1):
        if line.strip():
            if not lines:
                start = number
            lines.append(line.strip())
        elif lines:
            yield start, " ".join(lines)
            lines = []


def _recommends(paragraph: str) -> bool:
    """Mentions the PyPI install without warning against it."""
    return bool(_FROM_PYPI.search(paragraph)) and "unrelated" not in paragraph and "Do not" not in paragraph


def test_no_user_facing_text_recommends_installing_plainspeak_from_pypi():
    """A paragraph that mentions the command must be warning against it.

    Judged by paragraph, not by line: a warning wrapped across two lines was
    once read as a recommendation.
    """
    offences = []
    for path in _user_facing_files():
        for number, paragraph in _paragraphs(path.read_text(encoding="utf-8")):
            if _recommends(paragraph):
                offences.append(f"{path.relative_to(ROOT)}:{number}: {paragraph[:120]}")
    assert not offences, "\n".join(offences)


def test_a_recommendation_is_still_caught():
    """The paragraph rule does not make the check toothless."""
    text = "Install the web extra with:\n\npip install plainspeak[web]\n"
    assert any(_recommends(paragraph) for _, paragraph in _paragraphs(text))


def test_a_wrapped_warning_is_not_a_recommendation():
    text = "Preparing publication found that `pip install plainspeak` installs an\nunrelated project.\n"
    assert not any(_recommends(paragraph) for _, paragraph in _paragraphs(text))


def test_the_pypi_name_is_not_mistaken_for_the_unrelated_one():
    """`plainspeak-next` is the right install, with or without extras."""
    for text in ("pip install plainspeak-next", 'pip install "plainspeak-next[desktop]"'):
        assert not _FROM_PYPI.search(text), text


def test_the_readme_installs_plainspeak_next_from_pypi():
    """The README is also the PyPI project page, so it must say which name to use."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install plainspeak-next" in readme
    assert "import plainspeak" in readme


#: A direct-reference install of this repository: `<name>[extras] @ git+...`.
_FROM_REPOSITORY = re.compile(r"([\w.-]+)(\[[^\]]*\])?\s*@\s*git\+https://github\.com/hourwise/PlainSpeak-Next")


def test_repository_installs_name_the_distribution_they_install():
    """pip refuses `plainspeak @ git+...` once the project is called `plainspeak-next`.

    The requirement's name must match the distribution the repository builds,
    so every documented repository install has to use the new name.
    """
    offences = [
        f"{path.relative_to(ROOT)}: {match.group(0)}"
        for path in _user_facing_files()
        for match in _FROM_REPOSITORY.finditer(path.read_text(encoding="utf-8"))
        if match.group(1) != "plainspeak-next"
    ]
    assert not offences, "\n".join(offences)
