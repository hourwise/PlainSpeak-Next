# Release readiness: PlainSpeak 1.0.0

**Status: 1.0.0 CERTIFIED. Not published.**

Nothing here records a publication. No tag exists, no GitHub release has been
created, and nothing has been uploaded to PyPI. See [RELEASING.md](RELEASING.md)
for the steps that would, each of which requires an explicit decision — and note
that the PyPI step is blocked: the name `plainspeak` on PyPI belongs to an
unrelated project (see *Publication* below).

## What was certified

| | |
|---|---|
| commit | `ff067c4` on `codex/plainspeak-v1-final` (this page is added by the commit after it, and changes nothing else) |
| CI run | [36325087790](https://github.com/hourwise/PlainSpeak-Next/actions/runs/36325087790), dispatched, all nine jobs green |
| version | `1.0.0` |
| ruleset | 2026.5 / `6494a92617e6` / 220 rules, 139 automatic, 6 style fixes |
| integrity policy | 2026.2 / `ac617b549955` |
| morphology | 2026.1 / `93fba6907f87` |
| style policy | 2026.2 / `80ef39cef5f5` |
| profile pack | 2026.1 / `73deed35d673` — natural, plain, technical, government, academic |
| suggestion review | 2026.1 / `ee2612759484` |
| JSON contract | `plainspeak.present.v1` |
| desktop smoke output | `ca5d501239c0d4b6…` |
| certification sample output | `af79da49458bde04…`, unchanged since 1.0.0rc1 |

## Artifacts

Checksums as published in each artifact's `SHA256SUMS`, each verified with
`sha256sum --check` after download.

| artifact | SHA-256 |
|---|---|
| `plainspeak-1.0.0-py3-none-any.whl` | `75c60268ca78d4adc62548809e50bb76f9d5ef26e959759e7043da99d3d81a0b` |
| `plainspeak-1.0.0.tar.gz` | `b35b65a34d161d2a8e8b2598396bef9cfbcefd4eb53b12d6cc11cec65bbcdfca` |
| `plainspeak-desktop-1.0.0-windows.zip` | `829ff42aafde59880d642e698d5b1884b3cd408992124cacd660de59ce032faa` |
| `plainspeak-desktop-1.0.0-windows.manifest.json` | `90699c2fddad4c6cc613728e1507c5a6d3cdd04d535563aa01031a376cb61495` |
| `plainspeak-desktop-1.0.0-linux.tar.gz` | `9ed19f0829c511014712d4be99f0e49feeb1071c78d39142accc0d1d25dd7946` |
| `plainspeak-desktop-1.0.0-linux.manifest.json` | `045a33ee276edd8c47f3828921a0c804ecd1a565fea4025c426e2b3d18acd335` |

Desktop bundles: Windows 79 files, 80.9 MiB, `PlainSpeak.dist/desktop_main.exe`;
Linux 132 files, 162.3 MiB, `PlainSpeak.dist/desktop_main.bin`. Neither build is
bit-reproducible — wheels embed timestamps and Nuitka output varies between
runs — which is why every check below is on computed output, not on bytes.

## Certification results

| check | where | result |
|---|---|---|
| full test suite, with and without the desktop extra | CI: Windows, Linux, macOS × Python 3.10, 3.13 | green (4,315 tests locally on 3.14) |
| architecture policy, sealed identities, characterisation goldens | every test job | green |
| wheel and sdist carry the syllable dictionary and ruleset | CI | green |
| installed wheel certified from outside the checkout | CI, Linux, Python 3.13 | **51 / 51** |
| the same CI-built wheel, installed fresh with `[desktop]` | Windows 11, Python 3.14 | **51 / 51** |
| frozen desktop self-test outside the source tree | CI, Windows and Linux | OK, smoke `ca5d5012…` on both |
| the CI-built Windows bundle, unzipped to an unrelated directory | Windows 11 | self-test OK, smoke `ca5d5012…` |
| the CI-built Windows bundle started on the offscreen platform | Windows 11 | running after 8 s, 72 MB, no error |
| 27-document acceptance corpus through `analyze`, `present` and the desktop | locally | every protected fact kept, deterministic, desktop agrees with `present`; see [V1_ACCEPTANCE_REVIEW.md](V1_ACCEPTANCE_REVIEW.md) |

## What changed since 1.0.0rc1

The acceptance review read PlainSpeak's output on 27 realistic documents and
fixed what it found: 25 safe fixes that broke real sentences reclassified as
diagnostics (ruleset 2026.5), article agreement for replacements, 71 wrong
readability suggestions withdrawn and 5 corrected, verbs for nominalisations
from a reviewed table, stable rule IDs, and profiles that say what they change.
Preparing publication then found that `pip install plainspeak` installs an
unrelated project; nothing in PlainSpeak Next now tells anyone to run it.

## Publication

The name `plainspeak` on PyPI is taken by an unrelated project (English to
terminal commands), which also installs a top-level Python package named
`plainspeak`. Publishing to PyPI therefore needs a decision first:

- a free distribution name, such as `plainspeak-next` (available when checked);
- and whether the import name stays `plainspeak` (the two projects could not be
  installed side by side) or changes too (a breaking change to every import).

Until that is decided, a 1.0.0 release is the Git tag and the GitHub release
with the artifacts above attached, installed from the repository or the wheel.

## Known limitations carried into 1.0

Stated in full in [V1_SCOPE.md](V1_SCOPE.md) and [LIMITATIONS.md](LIMITATIONS.md).
In brief: English only; word- and phrase-level changes, no sentence
restructuring; short texts get little style feedback, and say so; style
suggestions are rare on real prose and the same under every profile; plain text
and Markdown only for transformation; readability suggestions are reviewed
advice that will not fit every context; no installer, no macOS build, no code
signing; not yet validated with readers.
