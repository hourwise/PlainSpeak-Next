"""Record what a frozen desktop build actually contains.

Run after `pyside6-deploy`. Writes a manifest next to the bundle and prints a
summary, so a build job produces evidence rather than an assertion that
something happened.

Two things it checks rather than merely reports, because both have failed here
before and both fail silently:

**The engine's data is inside the bundle.** The syllable dictionary, the rule
YAML and the profile YAML are not Python modules, so nothing about a successful
compile implies they came along. A build missing them starts, opens a document,
loads no rules and gives different answers.

**The executable exists and has a plausible size.** A zero-byte or absent
binary after a "successful" build is a real outcome on Windows when a step
fails quietly.

Exits non-zero if either fails.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

#: Data files without which the application is wrong rather than broken.
REQUIRED_PATTERNS = (
    ("syllable dictionary", "syllable_data.bin"),
    ("bundled rules", "RULESET.yaml"),
    ("style profiles", "natural.yaml"),
)

#: Anything smaller than this is not a real executable.
MINIMUM_EXECUTABLE_BYTES = 100_000


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: record_desktop_build.py <bundle-directory>", file=sys.stderr)
        return 2

    bundle = Path(argv[1])
    if not bundle.is_dir():
        print(f"no bundle at {bundle}", file=sys.stderr)
        return 1

    files = sorted(path for path in bundle.rglob("*") if path.is_file())
    if not files:
        print(f"{bundle} is empty", file=sys.stderr)
        return 1

    executables = [
        path for path in files
        if path.suffix.lower() in (".exe", ".bin") or (
            path.suffix == "" and path.stat().st_mode & 0o111
        )
    ]

    failures: list[str] = []
    for label, needle in REQUIRED_PATTERNS:
        found = [path for path in files if path.name.endswith(needle)]
        if not found:
            failures.append(
                f"{label}: no file ending in {needle!r} inside the bundle. The build "
                f"has no engine data and would give different answers than source."
            )

    main_executable = None
    for path in executables:
        if "desktop_main" in path.name.lower() or "plainspeak" in path.name.lower():
            main_executable = path
            break
    if main_executable is None and executables:
        main_executable = max(executables, key=lambda path: path.stat().st_size)

    if main_executable is None:
        failures.append("no executable found in the bundle")
    elif main_executable.stat().st_size < MINIMUM_EXECUTABLE_BYTES:
        failures.append(
            f"{main_executable.name} is {main_executable.stat().st_size} bytes, "
            f"which is not a real executable"
        )

    total = sum(path.stat().st_size for path in files)
    manifest = {
        "bundle": str(bundle),
        "file_count": len(files),
        "total_bytes": total,
        "executable": main_executable.name if main_executable else None,
        # Relative to the bundle, because a standalone build nests the binary
        # and a job that guessed the layout would fail for the wrong reason.
        "executable_path": (
            str(main_executable.relative_to(bundle)).replace("\\", "/")
            if main_executable else ""
        ),
        "executable_bytes": main_executable.stat().st_size if main_executable else 0,
        "executable_sha256": sha256_of(main_executable) if main_executable else "",
        "engine_data": {
            label: sorted(
                str(path.relative_to(bundle)) for path in files if path.name.endswith(needle)
            )
            for label, needle in REQUIRED_PATTERNS
        },
    }

    destination = bundle.parent / "build-manifest.json"
    destination.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"bundle        {bundle}")
    print(f"files         {len(files)}")
    print(f"total size    {total / 1_048_576:.1f} MiB")
    if main_executable is not None:
        print(f"executable    {manifest['executable_path']}")
        print(f"  size        {main_executable.stat().st_size / 1_048_576:.1f} MiB")
        print(f"  sha256      {manifest['executable_sha256']}")
    for label, found in manifest["engine_data"].items():
        print(f"{label:<14}{'present' if found else 'MISSING'} ({len(found)})")
    print(f"manifest      {destination}")

    if failures:
        print("\nbuild verification FAILED", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
