# Release readiness: PlainSpeak 1.0.0

**Status: 1.0.0 CERTIFIED as `plainspeak-next`, with valid classifiers. Not
published.**

This is the third certification of 1.0.0, and the one a release publishes.
The first (`ff067c4`) built the distribution as `plainspeak`; the second
(`2423c03`) was tagged and released on GitHub, and PyPI refused its wheel over
an invalid classifier (see *Withdrawn publication attempt*). Nothing has been
uploaded to PyPI. See [RELEASING.md](RELEASING.md) for the steps a
publication takes.

Status as recorded before this certification, kept as it was:

> **Status: 1.0.0 NOT PUBLISHED. The first publication attempt failed at PyPI
> and is being withdrawn and reissued.**
>
> The `v1.0.0` tag and GitHub release made from `6ded4e5` are being withdrawn:
> PyPI refused their wheel because its metadata carried a classifier PyPI does
> not know. Nothing reached PyPI. See *Withdrawn publication attempt*, which
> records it in full, and [RELEASING.md](RELEASING.md) for the steps a
> publication takes.
>
> Status as recorded before that attempt, kept as it was:
>
> > **Status: 1.0.0 CERTIFIED as `plainspeak-next`. Not published.**
> >
> > Nothing here records a publication. No tag exists, no GitHub release has
> > been created, and nothing has been uploaded to PyPI.

## What was certified

| | |
|---|---|
| commit | `719376b` on `codex/plainspeak-v1-release-repair`; the commit after it changes only this page |
| CI run | [36339056288](https://github.com/hourwise/PlainSpeak-Next/actions/runs/36339056288), dispatched, all nine jobs green |
| distribution | `plainspeak-next` — import package `plainspeak`, command `plainspeak` |
| version | `1.0.0` |
| classifiers | 14, every one accepted by PyPI's list (`trove-classifiers`), in `pyproject.toml`, the wheel and the sdist |
| ruleset | 2026.5 / `6494a92617e6` / 220 rules, 139 automatic, 6 style fixes |
| integrity policy | 2026.2 / `ac617b549955` |
| morphology | 2026.1 / `93fba6907f87` |
| style policy | 2026.2 / `80ef39cef5f5` |
| profile pack | 2026.1 / `73deed35d673` — natural, plain, technical, government, academic |
| suggestion review | 2026.1 / `ee2612759484` |
| JSON contract | `plainspeak.present.v1` |
| desktop smoke output | `ca5d501239c0d4b6…` |
| certification sample output | `af79da49458bde04…`, unchanged since 1.0.0rc1 |

The only change from the second certification's package metadata is one
classifier fewer. Every engine identity and pinned output is the same; no code
under `plainspeak/` changed.

## Artifacts

Checksums as published in each artifact's `SHA256SUMS`, each verified with
`sha256sum --check` after download.

| artifact | SHA-256 |
|---|---|
| `plainspeak_next-1.0.0-py3-none-any.whl` | `858346dc4b7ad9696f7c38de6a56aea9f1d592415c29c03a0298019ab7814f00` |
| `plainspeak_next-1.0.0.tar.gz` | `18dd3258400cfa6f60247d265d38f46cf3ce0e5ccbf31f3aef56162e5b832b44` |
| `plainspeak-desktop-1.0.0-windows.zip` | `ac866ba1caaca15d2f2b7113cc2bacffa5cb795bf84f1516b838454b9e54ea88` |
| `plainspeak-desktop-1.0.0-windows.manifest.json` | `92d653f8d2d952c6703a35456f0208e8678733dbebef4ed2431572b39382fd7e` |
| `plainspeak-desktop-1.0.0-linux.tar.gz` | `6544a9173eca65da4428b9de9bbf8d55cfa124b5f4486dacd421747c3e97f493` |
| `plainspeak-desktop-1.0.0-linux.manifest.json` | `045a33ee276edd8c47f3828921a0c804ecd1a565fea4025c426e2b3d18acd335` |

Distribution metadata, read from the CI-built files: the wheel's `METADATA`
and the sdist's `PKG-INFO` both say `Name: plainspeak-next` and
`Version: 1.0.0`, with the 14 declared classifiers. The wheel holds 116 files
under `plainspeak/` and `plainspeak_next-1.0.0.dist-info/`; its console
scripts are `plainspeak`, `plainspeak-desktop` and `plainspeak-web`.
`twine check --strict` passes on both.

Desktop bundles: Windows 79 files, 80.9 MiB, `PlainSpeak.dist/desktop_main.exe`
(SHA-256 `cf992a33b3a8a277…`); Linux 132 files, 162.3 MiB,
`PlainSpeak.dist/desktop_main.bin` (SHA-256 `c743fffc04e552e8…`, the same
executable and manifest as both earlier certifications). The Windows build is
not bit-reproducible, which is why every check below is on computed output.

## Certification results

| check | where | result |
|---|---|---|
| full test suite, with and without the desktop extra | CI: Windows, Linux, macOS × Python 3.10, 3.13 | green (4,332 tests locally on 3.14, exit status 0) |
| architecture policy, sealed identities, characterisation goldens | every test job | green |
| every classifier accepted by PyPI, in `pyproject.toml`, wheel and sdist | CI package job, and again locally | 14 / 14 |
| wheel and sdist carry the syllable dictionary, ruleset and profiles | CI | green |
| installed wheel certified from outside the checkout | CI, Linux, Python 3.13 | **54 / 54** |
| the same CI-built wheel, installed fresh with `[desktop]` | Windows 11, Python 3.14, PySide6 6.11.2 | **54 / 54** |
| `import plainspeak`, `plainspeak --help`, `plainspeak present` on a file | that Windows install, outside the checkout | 1.0.0; `plainspeak-next` 1.0.0 is the only provider of `plainspeak`; `present` exits 0, schema `plainspeak.present.v1`, protected facts preserved |
| engine with networking disabled | both certifications above | same output hash as online |
| `twine check --strict` | wheel and sdist | passed |
| frozen desktop self-test outside the source tree | CI, Windows and Linux | OK, smoke `ca5d5012…` on both |
| the CI-built Windows bundle, unzipped to an unrelated directory | Windows 11 | self-test OK, smoke `ca5d5012…` |

## Publication

The PyPI distribution is `plainspeak-next` (`pip install plainspeak-next`);
the import name and the command stay `plainspeak`. The unrelated `plainspeak`
distribution installs a package of the same name, so the two cannot be
installed side by side in one environment.

PyPI publication runs only through `release.yml`, from the protected `pypi`
environment, with PyPI's trusted publisher for `plainspeak-next` set to
`hourwise/PlainSpeak-Next`, workflow `release.yml`, environment `pypi`. It
publishes the wheel and sdist of run 36339056288 listed above, after checking
their checksums, their metadata, every classifier against the current PyPI
list, and that the tagged commit differs from `719376b` only in this page.

## Withdrawn publication attempt

The first attempt to publish 1.0.0, on 2026-09-27. Recorded before the tag
and release were deleted, so what existed stays on record.

| | |
|---|---|
| accepted release commit | `6ded4e5a33ac2784147463708c9336f4d9e5f7e1` (`main`); certified package source `2423c03`, CI run 36329522785 |
| tag | `v1.0.0`, annotated, tag object `4be733bb2aa9683b3cae58e314f892d51b6aec69`, tagger pcgsoft, 2026-09-27 16:21:08 UTC |
| GitHub release | "PlainSpeak 1.0.0", release ID `397720344` (`RE_kwDOUIHgY84XtLsY`), published 2026-09-27 16:22:20 UTC, <https://github.com/hourwise/PlainSpeak-Next/releases/tag/v1.0.0> |
| release workflow | [36333000273](https://github.com/hourwise/PlainSpeak-Next/actions/runs/36333000273), dispatched on `v1.0.0` with `ci-run-id=36329522785` |
| verification job | green, 16:22:33–16:22:41 UTC: annotated tag on `main`; version and distribution name; CI run green and differing from the tag only in this page; `sha256sum --check` on all six artifacts; wheel and sdist `Name: plainspeak-next`, `Version: 1.0.0`; certification 54 / 0; 1.0.0 not on PyPI |
| approval | the `pypi` environment, approved by hourwise |
| publish job | 17:47:17–17:47:35 UTC. Both files re-verified against the certified hashes. Trusted Publishing worked: the OIDC token was exchanged and PyPI attestations generated for both files. The wheel upload was then refused |
| PyPI's answer | `400 'Intended Audience :: Government' is not a valid classifier` |
| on PyPI | nothing: the sdist was never sent, and neither the project `plainspeak-next` nor any 1.0.0 file was created (`/pypi/plainspeak-next/json` answers 404) |

The GitHub release carried these assets, with GitHub's own digests:

| asset | SHA-256 |
|---|---|
| `plainspeak_next-1.0.0-py3-none-any.whl` | `1c3c5464930d07487362fd58c49c669447c3d7841c30e4e2ff1c2d00e2a3aab2` |
| `plainspeak_next-1.0.0.tar.gz` | `2ad392742c548528b290668daf9ce59559f72408e2b36843e7f7d0af82c8bba4` |
| `plainspeak-desktop-1.0.0-windows.zip` | `681aa76aeda59e7e0c477b4ba6a3524737e01ac96699e000c52bb876b9d8bd53` |
| `plainspeak-desktop-1.0.0-windows.manifest.json` | `5597926fa8401ce5e4c1161ce8ec50a425c561eb0f5742f3e5b364ce099472ac` |
| `plainspeak-desktop-1.0.0-linux.tar.gz` | `e147bfcfffbcf0176a584c675fb342d9606ee45285e6dc0dbd21799f14d4c65b` |
| `plainspeak-desktop-1.0.0-linux.manifest.json` | `045a33ee276edd8c47f3828921a0c804ecd1a565fea4025c426e2b3d18acd335` |
| `certification-python.json` | `0dfcb8b01691c828de38480f1b7571b828a580c00443dda8305aeb943962c261` |
| `SHA256SUMS` | `1565c6cd770faf6d7996db44eb5cf852c7385be049e73a3bc0dbc5cead569920` |

**Cause.** `pyproject.toml` declared `Intended Audience :: Government`, which
is not a Trove classifier; it had been there since before the fork. Nothing
checked classifiers: not the tests, not the certification, not the release
workflow. PyPI checks them on upload, so the problem surfaced only after
certification, tagging, the GitHub release and approval. The package itself
was not at fault.

**Resolution.** The classifier is removed, and `tools/check_classifiers.py`
now checks every classifier — in `pyproject.toml` and in the built wheel and
sdist — against `trove-classifiers`, PyPI's own list, in CI's package job and
in the release workflow's verification, before the `pypi` approval. Because
the metadata changed, 1.0.0 is rebuilt and certified again. Then the `v1.0.0`
tag and GitHub release above are deleted and made again on the certified
`main`. The version stays 1.0.0: no 1.0.0 was ever published anywhere a user
could install it from PyPI.

1.0.0 was certified twice. The first certification, of `ff067c4`, produced
artifacts whose distribution metadata said `Name: plainspeak`; they could not
be published to PyPI under the chosen name (see *Why 1.0.0 was certified
again*). The release was rebuilt as `plainspeak-next` and certified again from
the start. The second certification, below, is the one a release publishes.
The first is kept, unchanged, as a historical record.

## Second certification (superseded)

Kept as it was recorded. These artifacts were tagged `v1.0.0` and attached to
a GitHub release, which were then withdrawn: PyPI refused the wheel's
`Intended Audience :: Government` classifier (see *Withdrawn publication
attempt*).

### What was certified

| | |
|---|---|
| commit | `2423c03` on `codex/plainspeak-v1-release-fix`; the commit after it changes only this page |
| CI run | [36329522785](https://github.com/hourwise/PlainSpeak-Next/actions/runs/36329522785), dispatched, all nine jobs green |
| distribution | `plainspeak-next` — import package `plainspeak`, command `plainspeak` |
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

Every engine identity, the smoke output and the sample output are the same as
in the first certification: no code under `plainspeak/` changed.

### Artifacts

Checksums as published in each artifact's `SHA256SUMS`, each verified with
`sha256sum --check` after download.

| artifact | SHA-256 |
|---|---|
| `plainspeak_next-1.0.0-py3-none-any.whl` | `1c3c5464930d07487362fd58c49c669447c3d7841c30e4e2ff1c2d00e2a3aab2` |
| `plainspeak_next-1.0.0.tar.gz` | `2ad392742c548528b290668daf9ce59559f72408e2b36843e7f7d0af82c8bba4` |
| `plainspeak-desktop-1.0.0-windows.zip` | `681aa76aeda59e7e0c477b4ba6a3524737e01ac96699e000c52bb876b9d8bd53` |
| `plainspeak-desktop-1.0.0-windows.manifest.json` | `5597926fa8401ce5e4c1161ce8ec50a425c561eb0f5742f3e5b364ce099472ac` |
| `plainspeak-desktop-1.0.0-linux.tar.gz` | `e147bfcfffbcf0176a584c675fb342d9606ee45285e6dc0dbd21799f14d4c65b` |
| `plainspeak-desktop-1.0.0-linux.manifest.json` | `045a33ee276edd8c47f3828921a0c804ecd1a565fea4025c426e2b3d18acd335` |

Distribution metadata, read from the CI-built files: the wheel's `METADATA`
and the sdist's `PKG-INFO` both say `Name: plainspeak-next` and
`Version: 1.0.0`. The wheel holds 116 files under two top-level entries,
`plainspeak/` and `plainspeak_next-1.0.0.dist-info/`, and its console scripts
are `plainspeak`, `plainspeak-desktop` and `plainspeak-web`.

Desktop bundles: Windows 79 files, 80.9 MiB, `PlainSpeak.dist/desktop_main.exe`
(SHA-256 `97a4cb289b1dacba…`); Linux 132 files, 162.3 MiB,
`PlainSpeak.dist/desktop_main.bin` (SHA-256 `c743fffc04e552e8…`). The Linux
executable and its manifest came out byte-identical to the first
certification's; the archive differs only because it records file times. The
Windows build is not bit-reproducible, which is why every check below is on
computed output, not on bytes.

### Certification results

| check | where | result |
|---|---|---|
| full test suite, with and without the desktop extra | CI: Windows, Linux, macOS × Python 3.10, 3.13 | green (4,326 tests locally on 3.14, exit status 0) |
| architecture policy, sealed identities, characterisation goldens | every test job | green |
| wheel and sdist carry the syllable dictionary, ruleset and profiles | CI | green |
| installed wheel certified from outside the checkout | CI, Linux, Python 3.13 | **54 / 54** |
| the same CI-built wheel, installed fresh with `[desktop]` | Windows 11, Python 3.14, PySide6 6.11.2 | **54 / 54** |
| `import plainspeak`, `plainspeak --help`, `plainspeak version`, `plainspeak present` on a file | that Windows install, outside the checkout | 1.0.0; `plainspeak-next` 1.0.0 is the only provider of `plainspeak`; `present` exits 0, schema `plainspeak.present.v1`, protected facts preserved |
| engine with networking disabled | both certifications above | same output hash as online |
| frozen desktop self-test outside the source tree | CI, Windows and Linux | OK, smoke `ca5d5012…` on both |
| the CI-built Windows bundle, unzipped to an unrelated directory | Windows 11 | self-test OK, smoke `ca5d5012…` |

The certification script now has 54 checks: the 51 of the first certification,
unchanged, and three for the distribution identity — installed as
`plainspeak-next` at the pinned version, no other distribution providing
`import plainspeak`, and the `plainspeak` command installed.

### Why 1.0.0 was certified again

The first certification's wheel and sdist were built with the distribution
name `plainspeak`: their metadata said `Name: plainspeak`, and their files
were `plainspeak-1.0.0-…`. PyPI accepts a file only for the project its
metadata names, so those artifacts could only ever have gone to the PyPI
project `plainspeak`, which belongs to an unrelated tool (and is itself at
1.0.0). The blocker was the distribution metadata, not the package: the code,
the engine identities and every certified output were right.

`2423c03` changes the distribution name to `plainspeak-next` and nothing under
`plainspeak/`: the import package and the command stay `plainspeak`. It also
updates the install documentation, adds the three identity checks to the
certification script, and adds `.github/workflows/release.yml`, which
publishes to PyPI through Trusted Publishing. Because the metadata changed,
the wheel and sdist were rebuilt, and so were the desktop bundles, so that a
release carries one coherent set built by one dispatched CI run; everything
above was certified again. No artifact of the first certification is part of
the release.

### Publication, as it stood

Decided: the PyPI distribution is `plainspeak-next`
(`pip install plainspeak-next`); the import name stays `plainspeak`, as does
the command. The unrelated `plainspeak` distribution installs a package of the
same name, so the two cannot be installed side by side in one environment.
`plainspeak-next` was unclaimed on PyPI when this was recorded.

PyPI publication runs only through `release.yml`, from the protected `pypi`
environment, with PyPI's trusted publisher for `plainspeak-next` set to
`hourwise/PlainSpeak-Next`, workflow `release.yml`, environment `pypi`. It
publishes the wheel and sdist of run 36329522785 listed above, after checking
their checksums, their metadata and that the tagged commit differs from
`2423c03` only in this page.

## First certification (superseded)

Kept as it was recorded. These artifacts were never published and are not
part of the release: their metadata names the distribution `plainspeak`.

### What was certified

| | |
|---|---|
| commit | `ff067c4` on `codex/plainspeak-v1-final`; the two commits after it change only this page and one test (see *Checkpoint note*) |
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

### Artifacts

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

### Certification results

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

### Checkpoint note

Two commits reached `main` red. `adc523b`, which added this page, failed the
install-guidance test: a sentence here that *warns* against installing the
unrelated PyPI package was wrapped across two lines, and the test, reading line
by line, took it for a recommendation. The suite's output was piped through
`tail`, whose success hid pytest's failure, and the commit was pushed.
`006043d`, which made the test read whole paragraphs, was red for the same
reason: its own note quoted the command, and the focused run that caught it did
not stop the push. Both were fixed forward in the commit after `006043d`, with
the suite's own exit status gating the commit, rather than by rewriting
`main`. No package code differs from the certified `ff067c4`; the tag, when one
is authorised, belongs on the current `main`.

### Publication, as it stood

The name `plainspeak` on PyPI is taken by an unrelated project (English to
terminal commands), which also installs a top-level Python package named
`plainspeak`. Publishing to PyPI therefore needs a decision first:

- a free distribution name, such as `plainspeak-next` (available when checked);
- and whether the import name stays `plainspeak` (the two projects could not be
  installed side by side) or changes too (a breaking change to every import).

Until that is decided, a 1.0.0 release is the Git tag and the GitHub release
with the artifacts above attached, installed from the repository or the wheel.

## What changed since 1.0.0rc1

The acceptance review read PlainSpeak's output on 27 realistic documents and
fixed what it found: 25 safe fixes that broke real sentences reclassified as
diagnostics (ruleset 2026.5), article agreement for replacements, 71 wrong
readability suggestions withdrawn and 5 corrected, verbs for nominalisations
from a reviewed table, stable rule IDs, and profiles that say what they change.
Preparing publication then found that `pip install plainspeak` installs an
unrelated project; nothing in PlainSpeak Next now tells anyone to run it.

## Known limitations carried into 1.0

Stated in full in [V1_SCOPE.md](V1_SCOPE.md) and [LIMITATIONS.md](LIMITATIONS.md).
In brief: English only; word- and phrase-level changes, no sentence
restructuring; short texts get little style feedback, and say so; style
suggestions are rare on real prose and the same under every profile; plain text
and Markdown only for transformation; readability suggestions are reviewed
advice that will not fit every context; no installer, no macOS build, no code
signing; not yet validated with readers.
