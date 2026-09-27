# Release readiness: PlainSpeak 1.0.0rc1

**Status: release candidate prepared — pending CI certification. Not published.**

Nothing here authorises or records a publication. `1.0.0` has not been tagged,
no GitHub release exists and nothing has been uploaded to PyPI; see
[RELEASING.md](RELEASING.md) for the steps that would, each of which requires
an explicit decision.

## What is being certified

| | |
|---|---|
| version | `1.0.0rc1` |
| ruleset | 2026.4 / `b2068de58272` / 220 rules, 6 style fixes |
| integrity policy | 2026.2 / `ac617b549955` |
| morphology | 2026.1 / `93fba6907f87` |
| style policy | 2026.2 / `80ef39cef5f5` |
| profile pack | 2026.1 / `73deed35d673` — natural, plain, technical, government, academic |
| JSON contract | `plainspeak.present.v1` |
| desktop smoke output | `a70aa737f4a5b63a…` |
| certification sample output | `af79da49458bde04…` |

## Local certification

Windows 11, Python 3.14.0.

| check | result |
|---|---|
| full test suite, headless, with the desktop extra | 4,183 passed |
| wheel and sdist build | `plainspeak-1.0.0rc1-py3-none-any.whl`, `plainspeak-1.0.0rc1.tar.gz` |
| data in both | syllable dictionary and bundled ruleset present |
| wheel installed into a fresh environment, `[desktop]` extra, certified from a directory outside the checkout | **51 of 51 checks passed** |

The installed-wheel certification (`tools/certify_release.py`) confirmed: the
package was imported from the environment and not a source tree; the version
and all twelve identity values; five profiles; the 125,068-entry syllable
dictionary; `plainspeak present`, run as the installed console script, under
every profile — byte-identical twice, schema `plainspeak.present.v1`, protected
facts preserved, the same text under every profile, and the pinned output hash
`af79da49…`; the SAFE changes, the refusal, five protected surfaces in the
output, insufficient-sample reporting and no REVIEW proposal applied; refusal
of an unsupported file and an unknown profile with their error codes; operation
with networking disabled; and the desktop self-test.

## CI certification

*Pending: recorded in the commit that follows this one, from the dispatched CI
run on it.*

## Known limitations carried into 1.0

Stated in full in [V1_SCOPE.md](V1_SCOPE.md) and [LIMITATIONS.md](LIMITATIONS.md).
In brief: English only; word- and phrase-level changes, no sentence
restructuring; short texts get little style feedback, and say so; plain text
and Markdown only for transformation; the `analyze` report's readability
suggestions come from the sealed inherited glossary and some are poor; no
installer, no macOS build, no code signing.
