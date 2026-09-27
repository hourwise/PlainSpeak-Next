"""Turn build outputs into release artifacts with published checksums.

Run after a build. Given the directory a build produced, writes one archive per
artifact under a versioned name, and a `SHA256SUMS` file in the format
`sha256sum --check` reads, so anyone downloading a release can verify it
without trusting the page they downloaded it from.

    python tools/package_release.py desktop deploy/dist windows  -> release/
    python tools/package_release.py python  dist                 -> release/

This prepares artifacts. It does not publish anything, tag anything or upload
anything; that is a separate, deliberately manual step (see RELEASING.md).
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "release"


def version() -> str:
    sys.path.insert(0, str(ROOT))
    from plainspeak import __version__

    return __version__


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_sums(paths: list[Path]) -> Path:
    """Append to SHA256SUMS, one line per file, sorted and de-duplicated."""
    sums = RELEASE / "SHA256SUMS"
    lines = set(sums.read_text(encoding="utf-8").splitlines()) if sums.exists() else set()
    lines |= {f"{sha256_of(path)}  {path.name}" for path in paths}
    sums.write_text("\n".join(sorted(lines, key=lambda line: line[66:])) + "\n", encoding="utf-8")
    return sums


def package_desktop(bundle: Path, platform: str) -> list[Path]:
    if not (bundle / "PlainSpeak.dist").is_dir():
        raise SystemExit(f"{bundle} does not contain PlainSpeak.dist; was the build run?")
    stem = RELEASE / f"plainspeak-desktop-{version()}-{platform}"
    fmt = "zip" if platform == "windows" else "gztar"
    archive = Path(shutil.make_archive(str(stem), fmt, root_dir=bundle, base_dir="PlainSpeak.dist"))
    produced = [archive]
    manifest = bundle.parent / "build-manifest.json"
    if manifest.exists():
        target = RELEASE / f"plainspeak-desktop-{version()}-{platform}.manifest.json"
        shutil.copyfile(manifest, target)
        produced.append(target)
    return produced


def package_python(dist: Path) -> list[Path]:
    produced = []
    for item in sorted(dist.iterdir()):
        if item.suffix in (".whl", ".gz") and version() in item.name:
            target = RELEASE / item.name
            shutil.copyfile(item, target)
            produced.append(target)
    if not any(path.suffix == ".whl" for path in produced):
        raise SystemExit(f"no wheel for {version()} in {dist}")
    return produced


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("desktop", "python"):
        print(__doc__)
        return 2
    RELEASE.mkdir(exist_ok=True)
    source = Path(argv[1])
    produced = package_desktop(source, argv[2]) if argv[0] == "desktop" else package_python(source)
    sums = write_sums(produced)
    for path in produced:
        print(f"{sha256_of(path)}  {path.name}  ({path.stat().st_size / 1024 / 1024:.1f} MiB)")
    print(f"checksums: {sums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
