"""Does this build actually carry the engine, and does it still agree with it?

A frozen application can fail in a way source never does: everything imports,
the window opens, and a data file is missing — so the ruleset is empty, or the
syllable dictionary silently falls back to a heuristic, and every answer is
quietly wrong. This project has shipped that defect twice already, both times in
`package-data`, both times invisible to anyone developing on it.

So the self-test is not a smoke test. It asserts the exact identities the engine
publishes and the exact output of a checked-in fixture, and it does it through
the same pipeline everything else uses — there is no second implementation here
that could pass while the real one is broken.

It opens no window, so a build job can run it, and it exits non-zero on any
failure with a line saying which check failed.
"""
from __future__ import annotations

import sys
from typing import Optional

#: Spelled out so the fixture below stays readable as one expression.
NL = chr(10)

#: The identities this build must report. Pinned rather than merely
#: self-consistent: a frozen application comparing itself to itself would pass
#: while carrying a completely different ruleset.
EXPECTED = {
    "ruleset_version": "2026.3",
    "ruleset_count": 222,
    "ruleset_sha256": "7eddd0710ec15b7bdc940321d08dd2c4882e1561e11f8473fb1f2148709c0461",
    "integrity_version": "2026.1",
    "integrity_sha256": "21532115747ceb12218b6f388d885f26d0fbcbbd09f7f895a11c6aa61c9b4720",
    "morphology_version": "2026.1",
    "morphology_sha256": "93fba6907f874be5ec2832b5784874754c366f4c37ea5820a55a48513cf13263",
    "style_policy_version": "2026.1",
    "style_policy_sha256": "bedae926205a22cd6f2e9421d652c9d7fd7fa2f502e124210b29afbf773f421c",
    "profile_pack_version": "2026.1",
    "profile_pack_sha256": "cb305d331a312e1a839a35ff3cd016039dd4b666cbca9f2f58ff407743885575",
    "profiles": ("natural", "plain", "technical", "government", "academic"),
    "style_fix_count": 8,
    "syllable_minimum": 100_000,
}

#: A document written for this check, carried inside the package so a frozen
#: build has it without the repository. The expected output is the whole point:
#: an application that loads its data and still produces different text has a
#: defect the identity checks would not have caught.
SMOKE_SOURCE = (
    "# Quarterly note" + NL + NL
    + "It is important to note that the deadline is 30 September. Staff must not "
    + "exceed 0.5 mg per dose." + NL + NL
    + "Nevertheless, the panel approved the request. The cost was 250 GBP." + NL + NL
    + "Nevertheless, attendance fell. Three sites reported the same pattern." + NL + NL
    + "However, the trend reversed in June. Nobody could explain why." + NL + NL
    + "Nevertheless, the report was published on time." + NL + NL
    + "Nevertheless, the board deferred a decision until March." + NL + NL
    + "Nevertheless, the team utilise the register every week." + NL + NL
    + "Finally, the appendix lists every site." + NL
)

#: SHA-256 of the revised document with every safe fix applied and no style
#: suggestion accepted. Recomputed by the test suite from source, so a frozen
#: build disagreeing with source is a build failure rather than a mystery.
SMOKE_OUTPUT_SHA256 = "a70aa737f4a5b63a059eaaaee953be533e451eccf810a3d42e123707c3143ae3"


def run_self_test(argv: Optional[list[str]] = None) -> int:
    """Verify the packaged runtime. Returns 0 on success, 1 on any failure."""
    failures: list[str] = []

    def check(label: str, actual, expected) -> None:
        if actual != expected:
            failures.append(f"{label}: expected {expected!r}, found {actual!r}")

    try:
        from ..pipeline import build_review_bundle, engine_identities, parse_source
    except Exception as error:  # noqa: BLE001 - a packaging failure, reported plainly
        print(f"self-test: the engine could not be imported: {error}", file=sys.stderr)
        return 1

    try:
        identity = engine_identities()
        check("ruleset version", identity["ruleset_version"], EXPECTED["ruleset_version"])
        check("ruleset count", identity["ruleset_count"], EXPECTED["ruleset_count"])
        check("ruleset sha256", identity["ruleset_sha256"], EXPECTED["ruleset_sha256"])
        check("style-fix count", identity["style_fix_count"], EXPECTED["style_fix_count"])
        if not identity["style_fixes_all_review_required"]:
            failures.append("a style-fix rule loaded as automatic")

        check("integrity version", identity["integrity_version"], EXPECTED["integrity_version"])
        check("integrity sha256", identity["integrity_sha256"], EXPECTED["integrity_sha256"])
        check("morphology version", identity["morphology_version"], EXPECTED["morphology_version"])
        check("morphology sha256", identity["morphology_sha256"], EXPECTED["morphology_sha256"])
        check("style policy version", identity["style_policy_version"],
              EXPECTED["style_policy_version"])
        check("style policy sha256", identity["style_policy_sha256"],
              EXPECTED["style_policy_sha256"])
        check("profile pack version", identity["profile_pack_version"],
              EXPECTED["profile_pack_version"])
        check("profile pack sha256", identity["profile_pack_sha256"],
              EXPECTED["profile_pack_sha256"])
        check("profiles", identity["profiles"], EXPECTED["profiles"])

        if identity["syllable_entries"] < EXPECTED["syllable_minimum"]:
            failures.append(
                f"syllable dictionary: {identity['syllable_entries']} entries, "
                f"expected at least {EXPECTED['syllable_minimum']}"
            )
        if not identity["syllable_uses_dictionary"]:
            failures.append("syllable counting fell back to the heuristic")
    except Exception as error:  # noqa: BLE001
        failures.append(f"identity checks raised: {error}")

    output_hash = ""
    try:
        bundle = build_review_bundle(parse_source(SMOKE_SOURCE), "natural")
        preview = bundle.preview()
        output_hash = preview.output_hash

        if not preview.changed:
            failures.append("the smoke fixture produced no change at all")
        if "0.5 mg" not in preview.revised_text:
            failures.append("the smoke fixture lost a protected measurement")
        if "must not" not in preview.revised_text:
            failures.append("the smoke fixture lost a protected prohibition")
        if "250 GBP" not in preview.revised_text:
            failures.append("the smoke fixture lost a protected currency amount")
        if not bundle.reviewable:
            failures.append("the smoke fixture produced no style suggestion to review")
        if SMOKE_OUTPUT_SHA256 and output_hash != SMOKE_OUTPUT_SHA256:
            failures.append(
                f"smoke output sha256: expected {SMOKE_OUTPUT_SHA256}, found {output_hash}"
            )
    except Exception as error:  # noqa: BLE001
        failures.append(f"analysing the smoke fixture raised: {error}")

    qt_status = _qt_status()

    if failures:
        print("PlainSpeak desktop self-test FAILED", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(
        "PlainSpeak desktop self-test OK\n"
        f"  ruleset       {EXPECTED['ruleset_version']} "
        f"({EXPECTED['ruleset_sha256'][:12]}) {EXPECTED['ruleset_count']} rules, "
        f"{EXPECTED['style_fix_count']} style fixes\n"
        f"  integrity     {EXPECTED['integrity_version']} "
        f"({EXPECTED['integrity_sha256'][:12]})\n"
        f"  morphology    {EXPECTED['morphology_version']} "
        f"({EXPECTED['morphology_sha256'][:12]})\n"
        f"  style policy  {EXPECTED['style_policy_version']} "
        f"({EXPECTED['style_policy_sha256'][:12]})\n"
        f"  profile pack  {EXPECTED['profile_pack_version']} "
        f"({EXPECTED['profile_pack_sha256'][:12]}) "
        f"{', '.join(EXPECTED['profiles'])}\n"
        f"  smoke output  {output_hash}\n"
        f"  qt            {qt_status}"
    )
    return 0


def _qt_status() -> str:
    """Whether Qt can start here — reported, never fatal.

    A build machine may have no display and no offscreen platform plugin, and
    that says nothing about whether the application works on a desktop. The
    engine checks above are what the self-test is actually for.
    """
    try:
        from PySide6 import QtCore
    except Exception as error:  # noqa: BLE001
        return f"PySide6 not importable ({type(error).__name__})"
    return f"PySide6 {QtCore.qVersion()} available"


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(run_self_test())

