# Releasing PlainSpeak

How a release is built, what it contains, how it is certified, and which steps
are deliberately manual.

## What a release contains

| artifact | built by | contents |
|---|---|---|
| `plainspeak_next-<version>-py3-none-any.whl` | CI `package` job | the engine, CLI, web adapter and desktop code; the syllable dictionary, the ruleset (220 rules) and five profiles |
| `plainspeak_next-<version>.tar.gz` | CI `package` job | the source distribution |
| `plainspeak-desktop-<version>-windows.zip` | CI `desktop-build` job (Windows) | portable desktop bundle, `PlainSpeak.dist/desktop_main.exe` |
| `plainspeak-desktop-<version>-linux.tar.gz` | CI `desktop-build` job (Linux) | portable desktop bundle, `PlainSpeak.dist/desktop_main.bin` |
| `plainspeak-desktop-<version>-<os>.manifest.json` | `tools/record_desktop_build.py` | every file in the bundle, the executable's SHA-256, the data-file checks |
| `SHA256SUMS` | `tools/package_release.py` | a checksum for every artifact, readable by `sha256sum --check` |
| `certification-python.json` | `tools/certify_release.py` | the installed-wheel certification report, including a pinned output hash for a fixed sample |

The wheel and sdist are the distribution `plainspeak-next`: that is the name on
PyPI and in the file names. The Python package they install is still
`plainspeak` and the command is still `plainspeak`. The PyPI distribution named
`plainspeak` is an unrelated project that also installs a `plainspeak` package;
the two cannot be installed side by side in one environment.

There is no installer, no macOS build and no code signing. See
[V1_SCOPE.md](V1_SCOPE.md) and [LIMITATIONS.md](LIMITATIONS.md).

## Versions

The version is stated in `pyproject.toml`, in `plainspeak/__init__.py`, in
`tools/certify_release.py` (independently, so certification can catch a wheel
reporting the wrong one) and — without any pre-release suffix, because Windows
file versions are four numbers — in `deploy/pysidedeploy.spec`.
`test_the_version_is_stated_consistently_everywhere` keeps them in agreement.

The engine version is part of every plan's identity, so changing it moves
every plan hash and review-decision binding. That is intended: a decision made
under one release cannot be replayed under another. It does **not** move the
characterisation seal, which redacts the version, and it does not change any
presented text. Changing the version therefore needs the pinned plan hashes in
`tests/test_style_review.py` updated in the same commit.

## Building and certifying

1. Everything below runs from a green commit on `main`.
2. Dispatch CI on it: `gh workflow run CI --ref main`. A dispatched run adds the
   frozen desktop builds to the ordinary test matrix.
3. When it is green, download the artifacts:
   `gh run download <run-id> --dir release-candidate`.
4. CI has already:
   - run the full test suite on Windows, Linux and macOS, Python 3.10 and 3.13,
     with and without the desktop extra;
   - built the wheel and sdist, checked they carry their data, installed the
     wheel into a fresh environment and run `tools/certify_release.py` against
     it from outside the checkout;
   - built both desktop bundles and run `--self-test` on each from a directory
     containing neither the checkout nor the build environment.
5. Verify the checksums: `sha256sum --check SHA256SUMS` in each downloaded
   directory.
6. Record the result in [RELEASE_READINESS.md](RELEASE_READINESS.md): the
   commit, the CI run, the artifact checksums, and every certification result.

## Publishing — manual, and only when authorised

None of these happens as part of preparing a release candidate. Each requires
an explicit decision to release:

1. Set the final version (for example `1.0.0`) in the four places above,
   update the pinned plan hashes, and move the CHANGELOG entry from its
   pre-release heading to the release. Merge that commit to `main` through the
   usual green-checkpoint process and repeat *Building and certifying* on it.
   Record the evidence in RELEASE_READINESS.md in the commit after it: that
   file is the only one allowed to differ between the certified commit and the
   tag, and the release workflow checks it.
2. Tag `main`: `git tag -a v1.0.0 -m "PlainSpeak 1.0.0"` and push the tag.
3. Create the GitHub release from the tag and attach every artifact above,
   from the certified CI run, including each `SHA256SUMS`.
4. Publish the wheel and sdist to PyPI as `plainspeak-next` by dispatching the
   release workflow on the tag, naming the certified CI run:
   `gh workflow run release.yml --ref v1.0.0 -f ci-run-id=<run-id>`.
   It verifies the tag, the version, the CI run and every checksum, then waits
   for approval in the `pypi` environment before uploading the certified files
   themselves — not a rebuild.

### Trusted Publishing

PyPI accepts uploads for `plainspeak-next` only from GitHub Actions, through
OpenID Connect; there is no PyPI token in the repository, in its secrets or on
any machine. PyPI's trusted publisher for the project is:

| | |
|---|---|
| PyPI project | `plainspeak-next` |
| owner | `hourwise` |
| repository | `PlainSpeak-Next` |
| workflow | `release.yml` |
| environment | `pypi` |

Before the first release this is a *pending* publisher, added by the PyPI
account owner at <https://pypi.org/manage/account/publishing/>; the first
upload creates the project. The `pypi` environment in the repository settings
admits only `v*` tags and requires a reviewer's approval, so a workflow run
alone cannot publish.

A release candidate is **ready** when *Building and certifying* is green. It is
**published** only after the four steps above. The two are not the same.
