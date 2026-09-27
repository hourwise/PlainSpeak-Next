# Release readiness: PlainSpeak 1.0.0rc1

**Status: RELEASE CANDIDATE READY. Not published.**

Nothing here authorises or records a publication. `1.0.0` has not been tagged,
no GitHub release exists and nothing has been uploaded to PyPI; see
[RELEASING.md](RELEASING.md) for the four steps that would, each of which
requires an explicit decision.

## What was certified

| | |
|---|---|
| commit | `041b23d` on `codex/plainspeak-v1-rc` (this page is added by the commit after it, and changes nothing else) |
| CI run | [36310547008](https://github.com/hourwise/PlainSpeak-Next/actions/runs/36310547008), dispatched, all nine jobs green |
| version | `1.0.0rc1` |
| ruleset | 2026.4 / `b2068de58272` / 220 rules, 6 style fixes |
| integrity policy | 2026.2 / `ac617b549955` |
| morphology | 2026.1 / `93fba6907f87` |
| style policy | 2026.2 / `80ef39cef5f5` |
| profile pack | 2026.1 / `73deed35d673` — natural, plain, technical, government, academic |
| JSON contract | `plainspeak.present.v1` |
| desktop smoke output | `a70aa737f4a5b63a…`, unchanged since Phase 10 |
| certification sample output | `af79da49458bde04…` |

## Artifacts

Checksums as published in each artifact's `SHA256SUMS`, and each verified with
`sha256sum --check` after download.

| artifact | SHA-256 |
|---|---|
| `plainspeak-1.0.0rc1-py3-none-any.whl` | `7796bbdbea758842fdeab57b44163ac595b696ee0e41ac12956198ec46e16363` |
| `plainspeak-1.0.0rc1.tar.gz` | `0ebd772942bd5098d452bcfe0f174083e855b9ddf5a664c9429a709271abda20` |
| `plainspeak-desktop-1.0.0rc1-windows.zip` | `301d77e3d4be80b53b1ec1530c2c4c2a8a53e8d93d1f1a2458f309afdd1f0579` |
| `plainspeak-desktop-1.0.0rc1-windows.manifest.json` | `f2544ee85e917d01030630d700872059ce785ea9c25106879daa6d180a29d505` |
| `plainspeak-desktop-1.0.0rc1-linux.tar.gz` | `70bef4bef4d8bb41b70de1ee1d206aeda5c5e9c0c4d8c537d51b12b9203fbdbb` |
| `plainspeak-desktop-1.0.0rc1-linux.manifest.json` | `161c9faf13944df88e307ff94216a385ff8b3ebcd3be14b73336c402c50986fd` |

Desktop bundles: Windows 78 files, 80.8 MiB, `PlainSpeak.dist/desktop_main.exe`;
Linux 131 files, 162.2 MiB, `PlainSpeak.dist/desktop_main.bin`. Neither build is
bit-reproducible — wheels embed timestamps and Nuitka output varies between
runs — which is why every check below is on computed output, not on bytes.

## Certification results

| check | where | result |
|---|---|---|
| full test suite, with and without the desktop extra | CI: Windows, Linux, macOS × Python 3.10, 3.13 | green (4,191 tests locally on 3.14) |
| architecture policy, sealed identities, characterisation goldens | every test job | green |
| wheel and sdist carry the syllable dictionary and ruleset | CI | green |
| installed wheel certified from outside the checkout | CI, Linux, Python 3.13 | **51 / 51** |
| the same CI-built wheel, installed fresh with `[desktop]` | Windows 11, Python 3.14 | **51 / 51** |
| frozen desktop self-test outside the source tree | CI, Windows and Linux | OK, smoke `a70aa737…` on both |
| the CI-built Windows bundle, unzipped to an unrelated directory | Windows 11 | self-test OK, smoke `a70aa737…` |
| the CI-built Windows bundle started on the offscreen platform | Windows 11 | running after 8 s, 72 MB, no error |
| install from Git exactly as WALKTHROUGH.md instructs | Windows 11, fresh environment | installs; `present` runs |

The installed-wheel certification (`tools/certify_release.py`) checks: the
package is imported from the environment, not a source tree; the version and
all twelve pinned identity values; five profiles; the 125,068-entry syllable
dictionary; `plainspeak present`, run as the installed console script, under
every profile — byte-identical twice, schema `plainspeak.present.v1`, protected
facts preserved, the same text under every profile, and the pinned output hash;
the SAFE changes, the refusal, five protected surfaces in the output,
insufficient-sample reporting and no REVIEW proposal applied; refusal of an
unsupported file and an unknown profile with their error codes; operation with
networking disabled; and the desktop self-test.

## Defects found while certifying, all fixed before this candidate

- `[project.urls]` placed above `dependencies` made TOML read the dependency
  list as a URL; the build refused it. Now pinned by a test.
- Two packaging tests used `tomllib`, which Python 3.10 lacks, and failed only
  on the 3.10 jobs. Fixed in the commit itself before it reached `main`, so no
  red checkpoint entered accepted history.
- The Windows `SHA256SUMS` had CRLF line endings, so `sha256sum --check` could
  not read it; and the Python artifact nested its files under the runner's
  absolute path. Both fixed, the first pinned by a test.
- `plainspeak version` and the CLI help still described the upstream
  "readability analysis and text simplification toolkit".

## Known limitations carried into 1.0

Stated in full in [V1_SCOPE.md](V1_SCOPE.md) and [LIMITATIONS.md](LIMITATIONS.md).
In brief: English only; word- and phrase-level changes, no sentence
restructuring; short texts get little style feedback, and say so; plain text
and Markdown only for transformation; the `analyze` report's readability
suggestions come from the sealed inherited glossary and some are poor; no
installer, no macOS build, no code signing; not yet validated with readers.
