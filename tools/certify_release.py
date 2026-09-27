"""Certify an installed PlainSpeak, the way a user would meet it.

Run with the Python of an environment that has PlainSpeak *installed* — from a
wheel, not a checkout — and from a directory that is not the repository:

    python certify_release.py --report certification.json

Self-contained on purpose: it imports nothing from the repository and needs
nothing beside the installed package. Every check prints PASS or FAIL, a JSON
report is written if asked for, and the exit status is non-zero if anything
failed.

What it checks:

- the package is installed, not imported from a source tree;
- it was installed as the distribution `plainspeak-next`, is the only
  distribution providing `import plainspeak`, and installed the `plainspeak`
  command;
- the version and every engine identity are the ones this release pins;
- the syllable dictionary, all rules and all five profiles are present;
- `plainspeak present`, run as a user runs it, produces the pinned output
  hash for a fixed sample under every profile, byte-identically twice;
- SAFE changes are applied, a refusal is reported, protected facts survive and
  a short text reports insufficient sample;
- an unsupported file and an unknown profile are refused with their codes;
- the engine runs with networking disabled;
- the desktop self-test passes (reported as skipped if Qt is not installed).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_VERSION = "1.0.0"
#: The PyPI distribution. The import package and the command stay `plainspeak`;
#: `plainspeak` on PyPI is an unrelated project.
EXPECTED_DISTRIBUTION = "plainspeak-next"
EXPECTED_SCHEMA = "plainspeak.present.v1"

#: A fixed input and the SHA-256 of what every profile must present it as.
SAMPLE = (
    "# Account migration\n\n"
    "In order to finish, you must utilize the new portal prior to 30 June 2027. "
    "It should be noted that the old portal will not accept payments of £42.50 or more.\n\n"
    "Your reference, ACC-20931, does not change. Statements arrive within 5 working days.\n"
)
EXPECTED_OUTPUT_SHA256 = "af79da49458bde04b68d4ce94967a44c6dcedfa50e36d0ae94669cfeb0a202d9"

results: list[dict] = []


def check(name: str, passed: bool, detail: str = "") -> bool:
    results.append({"check": name, "passed": bool(passed), "detail": detail})
    print(f"{'PASS' if passed else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    return passed


def present(arguments: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    executable = shutil.which("plainspeak", path=str(Path(sys.executable).parent))
    command = [executable] if executable else [sys.executable, "-m", "plainspeak.adapters.cli"]
    return subprocess.run(
        command + ["present", *arguments], input=stdin, capture_output=True,
        text=True, encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=None)
    options = parser.parse_args()

    import plainspeak
    from plainspeak.desktop.selftest import EXPECTED
    from plainspeak.pipeline import engine_identities

    location = Path(plainspeak.__file__).resolve()
    source_tree = any((parent / "pyproject.toml").exists() for parent in location.parents)
    check("installed, not a source checkout", not source_tree, str(location.parent))
    check("version", plainspeak.__version__ == EXPECTED_VERSION, plainspeak.__version__)

    from importlib import metadata

    try:
        distribution = metadata.distribution(EXPECTED_DISTRIBUTION)
        name, installed = distribution.metadata["Name"], distribution.version
    except metadata.PackageNotFoundError:
        name, installed = None, None
    check("installed as the plainspeak-next distribution",
          name == EXPECTED_DISTRIBUTION and installed == EXPECTED_VERSION, f"{name} {installed}")
    providers = sorted(set(metadata.packages_distributions().get("plainspeak", [])))
    check("no other distribution provides import plainspeak",
          providers == [EXPECTED_DISTRIBUTION], ", ".join(providers))
    command = shutil.which("plainspeak", path=str(Path(sys.executable).parent))
    check("the plainspeak command is installed", command is not None, str(command))

    identity = engine_identities()
    for key in ("ruleset_version", "ruleset_sha256", "ruleset_count", "style_fix_count",
                "integrity_version", "integrity_sha256", "morphology_version",
                "morphology_sha256", "style_policy_version", "style_policy_sha256",
                "profile_pack_version", "profile_pack_sha256"):
        check(f"identity {key}", identity[key] == EXPECTED[key], str(identity[key])[:16])
    check("five profiles", tuple(identity["profiles"]) == EXPECTED["profiles"])
    check("syllable dictionary shipped",
          identity["syllable_uses_dictionary"] and identity["syllable_entries"] >= 100_000,
          f"{identity['syllable_entries']} entries")

    outputs = set()
    for profile in EXPECTED["profiles"]:
        first = present(["--stdin", "--profile", profile], SAMPLE)
        second = present(["--stdin", "--profile", profile], SAMPLE)
        if not check(f"present runs under {profile}", first.returncode == 0, first.stderr.strip()[:120]):
            continue
        check(f"present is byte-identical twice under {profile}", first.stdout == second.stdout)
        data = json.loads(first.stdout)
        outputs.add(data["output"]["sha256"])
        check(f"schema under {profile}", data["schema"] == EXPECTED_SCHEMA)
        check(f"protected facts preserved under {profile}", data["protected"]["preserved"] is True)
    check("the same presented text under every profile", len(outputs) == 1)
    check("presented text matches the pinned hash",
          outputs == {EXPECTED_OUTPUT_SHA256}, ", ".join(sorted(item[:16] for item in outputs)))

    data = json.loads(present(["--stdin", "--profile", "natural"], SAMPLE).stdout)
    applied = {item["rule_id"] for item in data["applied"]}
    check("SAFE changes applied", {"PS.CLARITY.001", "PS.LEXICAL.001", "PS.CLARITY.009"} <= applied,
          ", ".join(sorted(applied)))
    check("refusal reported", "PS.FRAMING.003" in {item["rule_id"] for item in data["refused"]})
    for surface in ("30 June 2027", "£42.50", "ACC-20931", "must", "not"):
        check(f"protected {surface!r} in output", surface in data["output"]["text"])
    check("short text reports insufficient sample", data["counts"]["insufficient_sample"] > 0)
    check("no review proposal applied", all(item["status"] == "review_required" for item in data["review"]))

    with tempfile.TemporaryDirectory() as scratch:
        unsupported = Path(scratch) / "document.docx"
        unsupported.write_bytes(b"not really a docx")
        refused = present([str(unsupported), "--profile", "natural"])
        check("unsupported input refused",
              refused.returncode == 1 and json.loads(refused.stdout)["error"]["code"] == "unsupported_input")
    unknown = present(["--stdin", "--profile", "casual"], SAMPLE)
    check("unknown profile refused",
          unknown.returncode == 1 and json.loads(unknown.stdout)["error"]["code"] == "unknown_profile")

    original = socket.socket

    def refuse(*_args, **_kwargs):
        raise OSError("network access attempted")

    socket.socket = refuse  # type: ignore[assignment]
    try:
        from plainspeak.pipeline import present_text

        offline = present_text(SAMPLE, "natural").preview.output_hash
        check("runs with networking disabled", offline == EXPECTED_OUTPUT_SHA256)
    except OSError as error:
        check("runs with networking disabled", False, str(error))
    finally:
        socket.socket = original

    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    selftest = subprocess.run([sys.executable, "-m", "plainspeak.desktop.selftest"],
                              capture_output=True, text=True, env=environment)
    check("desktop self-test", selftest.returncode == 0,
          (selftest.stdout.strip().splitlines() or [""])[-1] if selftest.returncode == 0
          else selftest.stderr.strip()[:200])

    failed = [item for item in results if not item["passed"]]
    summary = {
        "plainspeak_version": plainspeak.__version__,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "checks": results,
    }
    if options.report:
        Path(options.report).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"\n{summary['passed']} passed, {summary['failed']} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
