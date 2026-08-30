"""Confirm an *installed* PlainSpeak counts syllables from the dictionary.

Run against a fresh virtual environment that has the wheel installed, from a
directory that is not the source tree, so that the dictionary being found
proves it shipped rather than that the repository happens to be nearby.
"""
from __future__ import annotations

import sys

MINIMUM_ENTRIES = 100_000


def main() -> int:
    from plainspeak.core.syllables import get_syllable_count
    from plainspeak.morphology import forms_for
    from plainspeak.core.tokenize import _count_syllables_heuristic, count_syllables

    counts = get_syllable_count()
    if len(counts) < MINIMUM_ENTRIES:
        print(f"only {len(counts)} syllable entries loaded", file=sys.stderr)
        return 1

    # "business" is two syllables; the vowel-group heuristic says otherwise, so
    # the right answer proves the dictionary is the one being consulted.
    if count_syllables("business") != 2:
        print("syllable counting fell back to the heuristic", file=sys.stderr)
        return 1
    if _count_syllables_heuristic("business") == 2:
        print("this check no longer distinguishes dictionary from heuristic", file=sys.stderr)
        return 1

    from plainspeak.rules import load_ruleset

    ruleset = load_ruleset()
    if len(ruleset) < 20:
        print(f"only {len(ruleset)} rules loaded from the installed package", file=sys.stderr)
        return 1

    # The integrity policy is Python rather than packaged data, so it cannot go
    # missing the way the syllable dictionary did — but its *hash* is what binds
    # a plan to the safety rules that approved it, and an installed copy whose
    # policy differed from the source tree's would be a serious surprise.
    from plainspeak.integrity import POLICY_VERSION, check, policy_hash

    if len(policy_hash()) != 64:
        print("the installed integrity policy has no usable hash", file=sys.stderr)
        return 1
    if check("You must not apply.", "You must apply.").passed:
        print("the installed integrity firewall is not refusing", file=sys.stderr)
        return 1

    # Morphology generates the surfaces the migrated rules match, so an installed
    # copy whose morphology differed from the source tree's would match different
    # words while still calling itself the same ruleset.
    from plainspeak.morphology import MORPHOLOGY_VERSION
    from plainspeak.morphology import policy_hash as morphology_hash

    if ruleset.morphology_hash != morphology_hash():
        print("the installed ruleset and morphology disagree", file=sys.stderr)
        return 1
    if forms_for("utilise", "verb")["past"] != "utilised":
        print("the installed morphology is not inflecting correctly", file=sys.stderr)
        return 1

    # The style policy decides what a reader is told about their document. An
    # installed copy whose thresholds differed from the source tree's would give
    # different answers while reporting the same policy version.
    from plainspeak.style import STYLE_POLICY_VERSION, analyze
    from plainspeak.style import policy_hash as style_hash

    if len(style_hash()) != 64:
        print("the installed style policy has no usable hash", file=sys.stderr)
        return 1
    # Two sentences is far below every minimum sample, so a finding here would
    # mean the installed thresholds are not the reviewed ones.
    if analyze("A short sentence. Another one here.").findings:
        print("the installed style policy speaks below its minimum sample", file=sys.stderr)
        return 1

    # The bundled style profiles are packaged YAML, so they can go missing from a
    # wheel exactly as the syllable dictionary once did. A profile lookup that
    # failed would at least be loud; a pack that loaded with four of five
    # profiles would not be.
    from plainspeak.style.profiles import (
        PROFILE_PACK_VERSION,
        load_pack,
        pack_hash,
        profile_ids,
    )

    pack = load_pack()
    if len(pack) != 5:
        print(f"the installed profile pack holds {len(pack)} profiles", file=sys.stderr)
        return 1
    if profile_ids() != ("natural", "plain", "technical", "government", "academic"):
        print(f"unexpected installed profiles: {profile_ids()}", file=sys.stderr)
        return 1
    for profile in pack:
        if len(profile.hash) != 64:
            print(f"profile {profile.id} has no usable hash", file=sys.stderr)
            return 1

    # Phase 9 activated the `style-fix` mode. An installed package whose style
    # rules were missing would silently offer no style suggestions at all, and a
    # style rule that loaded as automatic would be a far worse failure — so both
    # the presence and the review classification are asserted here.
    style_fixes = ruleset.style_fixes
    if len(style_fixes) < 5:
        print(f"only {len(style_fixes)} style-fix rules installed", file=sys.stderr)
        return 1
    for rule in style_fixes:
        if rule.is_automatic or rule.review is None or not rule.review.required:
            print(f"style rule {rule.id} is not review-required", file=sys.stderr)
            return 1
        if rule.trigger is None:
            print(f"style rule {rule.id} declares no diagnostic trigger", file=sys.stderr)
            return 1

    print(
        f"installed package loads {len(counts)} syllable entries, "
        f"{len(ruleset)} rules (ruleset {ruleset.version} {ruleset.hash[:12]}), "
        f"integrity policy {POLICY_VERSION} ({policy_hash()[:12]}), "
        f"morphology {MORPHOLOGY_VERSION} ({morphology_hash()[:12]}) and "
        f"style policy {STYLE_POLICY_VERSION} ({style_hash()[:12]}), "
        f"profile pack {PROFILE_PACK_VERSION} ({pack_hash(pack)[:12]}): "
        + ", ".join(f"{profile.id} {profile.hash[:8]}" for profile in pack)
        + f"; {len(style_fixes)} style-fix rules, all review-required"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
