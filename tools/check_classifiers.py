"""Every declared Trove classifier is one PyPI accepts.

PyPI refuses an upload whose metadata carries a classifier it does not know,
and nothing before the upload noticed. The first 1.0.0 publication attempt
was certified, tagged, released on GitHub and approved for PyPI with
`Intended Audience :: Government` in its metadata — not a real classifier —
and PyPI rejected the wheel at the last step.

This checks the classifiers against `trove-classifiers`, the PyPA-maintained
package PyPI itself validates against, in two places:

- the declaration in pyproject.toml;
- the metadata of each built wheel (`METADATA`) and sdist (`PKG-INFO`), which
  must also carry exactly the declared set.

    python tools/check_classifiers.py pyproject.toml dist/

Needs `trove-classifiers` installed (a development and release tool, never a
runtime dependency of PlainSpeak). Without it the check fails rather than
passing unchecked. Exit status 0 only if every classifier is accepted.
"""
from __future__ import annotations

import sys
import tarfile
import zipfile
from email.parser import HeaderParser
from pathlib import Path


def accepted() -> tuple[set[str], set[str]]:
    """PyPI's current classifiers, and the deprecated ones it also refuses."""
    try:
        from trove_classifiers import classifiers, deprecated_classifiers
    except ImportError:
        raise SystemExit("trove-classifiers is not installed; cannot validate classifiers") from None
    return set(classifiers), set(deprecated_classifiers)


def declared(pyproject: Path) -> list[str]:
    import tomllib

    return list(tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"].get("classifiers", []))


def _headers(text: str) -> list[str]:
    return HeaderParser().parsestr(text).get_all("Classifier") or []


def from_wheel(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as wheel:
        name = next(item for item in wheel.namelist() if item.endswith(".dist-info/METADATA"))
        return _headers(wheel.read(name).decode("utf-8"))


def from_sdist(path: Path) -> list[str]:
    with tarfile.open(path) as sdist:
        # PKG-INFO sits directly under the "<name>-<version>/" directory.
        member = next(item for item in sdist.getmembers() if item.name.count("/") == 1 and item.name.endswith("/PKG-INFO"))
        return _headers(sdist.extractfile(member).read().decode("utf-8"))


def problems(label: str, found: list[str], known: set[str], deprecated: set[str]) -> list[str]:
    out = []
    for classifier in found:
        if classifier in deprecated:
            out.append(f"{label}: {classifier!r} is deprecated; PyPI refuses it")
        elif classifier not in known:
            out.append(f"{label}: {classifier!r} is not a valid classifier")
    return out


def artifacts(paths: list[Path]) -> list[Path]:
    found = []
    for path in paths:
        found += sorted(path.glob("*.whl")) + sorted(path.glob("*.tar.gz")) if path.is_dir() else [path]
    return found


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    known, deprecated = accepted()
    pyproject, rest = Path(argv[0]), [Path(item) for item in argv[1:]]
    source = declared(pyproject)
    failures = problems(str(pyproject), source, known, deprecated)
    if not source:
        failures.append(f"{pyproject}: declares no classifiers")

    built = artifacts(rest)
    if rest and not built:
        failures.append(f"no wheel or sdist found in {', '.join(map(str, rest))}")
    for path in built:
        if path.suffix == ".whl":
            found = from_wheel(path)
        elif path.name.endswith(".tar.gz"):
            found = from_sdist(path)
        else:
            failures.append(f"{path}: not a wheel or sdist")
            continue
        failures += problems(path.name, found, known, deprecated)
        if sorted(found) != sorted(source):
            failures.append(f"{path.name}: classifiers differ from {pyproject}")

    for failure in failures:
        print(f"FAIL  {failure}")
    checked = ", ".join([pyproject.name] + [path.name for path in built])
    print(f"{len(source)} classifiers checked in {checked}: {'FAILED' if failures else 'all accepted by PyPI'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
