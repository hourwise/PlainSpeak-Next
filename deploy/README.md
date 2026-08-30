# Frozen desktop builds

```bash
pip install -e ".[desktop]"
cd deploy
pyside6-deploy -c pysidedeploy.spec -f
python ../tools/record_desktop_build.py dist
./dist/desktop_main.bin --self-test     # .exe on Windows
```

## Why the spec has no comments in it

`pysidedeploy.spec` is read by `configparser` through a strict path that raises
`MissingSectionHeaderError` on a comment before the first section. The first
version of this file opened with a paragraph explaining itself and failed the
build on both platforms for that reason alone. The explanation lives here
instead.

## Why the spec has no absolute paths

`pyside6-deploy --init` writes one full of them: the interpreter it happened to
run under, the directory it happened to be in, an icon from inside the PySide6
wheel. A build that only works on the machine that generated its configuration
is not a build anybody can reproduce, so every path here is relative or empty.

## The settings that matter

**`--include-package-data=plainspeak`** is the line this file exists for.
PlainSpeak carries a 1.8 MB syllable dictionary, 222 rule YAML files and five
profile YAML files, and none of them is a Python module — a successful compile
implies nothing about whether they came along. A build without them launches,
opens a document, loads zero rules and quietly produces different answers. That
is the same defect this project has already shipped twice through
`package-data`, invisible both times to everyone developing on it.

`--include-package-data` alone was **not** enough, and the check found it: the
first Linux build produced a perfectly good 160 MiB bundle containing the rule
YAML, the profile YAML and no syllable dictionary. Nuitka does not treat a
`.bin` as package data, so the file is now named explicitly with
`--include-data-files`. A build without it loads 222 rules, reports every
identity correctly and silently falls back to a vowel-counting heuristic for
every readability metric.

`--quiet` is deliberately absent. It suppressed the actual Nuitka error on the
first Windows build and left nothing but a non-zero exit code to work from.

`tools/record_desktop_build.py` checks the bundle actually contains the data,
and `--self-test` checks the engine still agrees with source. Neither is
optional.

**`mode = standalone`** rather than `onefile`: a one-file build unpacks itself
to a temporary directory on every launch, and a directory bundle is far easier
to inspect when somebody wants to know what is inside it.

**`modules = Core,Gui,Widgets`** — no QML runtime and no web engine. The
application has no use for either, and shipping a browser inside a review tool
would be a large attack surface in exchange for nothing.

**`--nofollow-import-to`** on flask, docx, pypdf and pytest. The desktop reviews
text and Markdown only, so a DOCX or PDF reader would be dead weight, and a web
framework has no business inside a native application.

## Verifying a build

`--self-test` must be run from a directory containing neither the checkout nor
the virtual environment. An executable that finds the engine's data only because
the source tree happens to be next to it is a failed deployment, and running the
check from inside the repository would not notice.
