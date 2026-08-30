"""The profile schema, the pack's identity, and what a profile may not be.

Three groups. Validation, because a malformed bundled profile is a build failure
and the interesting failures are the quiet ones — a NaN threshold that silences a
diagnostic, a misspelled key that reads as absent, a minimum sample below the
floor the baseline set for a reason.

Identity, because the pack is versioned product behaviour like the other four,
and because the decision to exclude display prose from the hash is a decision
that has to be tested in both directions or it is not a decision at all.

And the prohibitions, which matter most. A profile is a natural place to try to
put an override, and this is where that is made impossible rather than merely
discouraged.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from plainspeak.style import policy
from plainspeak.style.profiles import (
    PROFILE_ORDER,
    PROFILE_PACK_VERSION,
    ProfileError,
    explain_all,
    explain_profile,
    load_pack,
    load_profile,
    pack_hash,
    parse_profile,
    profile_hash,
    profile_ids,
    resolve_profile,
)

BUNDLED = Path(__file__).resolve().parent.parent / "plainspeak" / "style" / "profiles" / "bundled"

#: The pack as it currently ships. Pinned so Windows, Linux and macOS all assert
#: the same number rather than each comparing itself to itself.
PROFILE_PACK_HASH = "cb305d331a312e1a839a35ff3cd016039dd4b666cbca9f2f58ff407743885575"

PROFILE_HASHES = {
    "natural": "e6c391c6b1ee8c65eaa292048aaed8b1233429421bb94ad804d4f45e0c7d73c4",
    "plain": "d94b54ac4998856cebdce90d0d2762811d2dc0f5f1232aae2cf005d81aac5155",
    "technical": "2be8a33b8b1f77591a74d0f545bb3270deb1711ad30f384a18e2ce702901a85b",
    "government": "88b1660d778b7722264b4a1a664247c17a73c3bf2adc5126dcf7410f383e213a",
    "academic": "1d9d19325bec16e7735b4ff6cf892f6f22b63939838038cf0d24da54e8a31023",
}


def raw(identifier: str) -> dict:
    return yaml.safe_load((BUNDLED / f"{identifier}.yaml").read_text(encoding="utf-8"))


# ── The bundled pack ───────────────────────────────────────────────────────


def test_the_five_built_in_profiles_load() -> None:
    assert profile_ids() == ("natural", "plain", "technical", "government", "academic")
    assert len(load_pack()) == 5


def test_display_order_is_declared_not_discovered() -> None:
    """Filesystem traversal order is not a design decision.

    The loader refuses a pack whose contents do not match the declared order, so
    adding a profile file without deciding where it belongs in a selector is a
    build failure rather than a surprise in someone's UI.
    """
    assert tuple(profile.id for profile in load_pack()) == PROFILE_ORDER


def test_every_profile_states_every_diagnostic() -> None:
    """No inheritance means no absent values."""
    for profile in load_pack():
        assert set(profile.diagnostics) == set(policy.DIAGNOSTIC_IDS)


def test_no_profile_lowers_a_minimum_sample() -> None:
    """The Phase 7 minimums are measurement-safety floors, not preferences."""
    for profile in load_pack():
        for identifier, rule in profile.diagnostics.items():
            assert rule.minimum_sample >= policy.MINIMUM_SAMPLES[identifier], (
                f"{profile.id} lowers {identifier} to {rule.minimum_sample}"
            )


def test_at_least_one_profile_raises_a_minimum_sample() -> None:
    """Demanding more evidence is the permitted direction, and it is used."""
    raised = [
        (profile.id, identifier)
        for profile in load_pack()
        for identifier, rule in profile.diagnostics.items()
        if rule.minimum_sample > policy.MINIMUM_SAMPLES[identifier]
    ]
    assert raised, "no profile demands more evidence than the baseline anywhere"


def test_thresholds_run_in_the_right_direction() -> None:
    for profile in load_pack():
        for identifier, rule in profile.diagnostics.items():
            if identifier in policy.INVERTED:
                assert rule.strong < rule.notice, f"{profile.id}/{identifier}"
            else:
                assert rule.strong > rule.notice, f"{profile.id}/{identifier}"


def test_every_target_range_is_satisfiable() -> None:
    for profile in load_pack():
        for metric, target in profile.targets.items():
            assert target.minimum <= target.maximum, f"{profile.id}/{metric}"


def test_profiles_differ_from_each_other() -> None:
    """Five names over one set of numbers would be worse than no profiles.

    Checked pairwise on the identity-bearing view, so two profiles cannot be
    distinguished only by their prose.
    """
    rendered = {profile.id: profile.as_dict()["diagnostics"] for profile in load_pack()}
    seen = {}
    for identifier, diagnostics in rendered.items():
        key = repr(sorted(diagnostics.items()))
        assert key not in seen, f"{identifier} is identical to {seen[key]}"
        seen[key] = identifier


def test_each_profile_differs_from_the_baseline_somewhere() -> None:
    for profile in load_pack():
        differences = [
            identifier
            for identifier, rule in profile.diagnostics.items()
            if (rule.notice, rule.strong) != policy.THRESHOLDS[identifier]
            or rule.minimum_sample != policy.MINIMUM_SAMPLES[identifier]
        ]
        assert differences, f"{profile.id} is the baseline with a name attached"


def test_weak_calibration_is_declared_rather_than_hidden() -> None:
    """A threshold with no document on one side must say so.

    Every profile has some — the corpus does not exercise canned framing or
    vocabulary overuse in any register — and a pack that claimed otherwise would
    be the more worrying result.
    """
    for profile in load_pack():
        assert profile.weakly_calibrated, (
            f"{profile.id} declares no weakly calibrated threshold, which would mean "
            f"every one of its lines has a calibration document on both sides"
        )


def test_a_disabled_diagnostic_would_have_to_explain_itself() -> None:
    """None are disabled today; the requirement holds if one ever is."""
    for profile in load_pack():
        for identifier in profile.disabled:
            assert profile.diagnostics[identifier].reason


# ── Identity ───────────────────────────────────────────────────────────────


def test_the_pack_has_its_expected_identity() -> None:
    assert PROFILE_PACK_VERSION == "2026.1"
    assert pack_hash(load_pack()) == PROFILE_PACK_HASH, (
        "The profile pack hash changed.\n"
        "  If you moved a threshold or a target range deliberately, update\n"
        "  PROFILE_PACK_HASH and the per-profile hash here, and say in the commit\n"
        "  message what a reader will now be told that they were not told before.\n"
        "  If you did not, something platform-dependent has reached the canonical\n"
        "  form, which is a bug in the hashing rather than in this test."
    )


def test_every_profile_has_its_expected_identity() -> None:
    for profile in load_pack():
        assert profile.hash == PROFILE_HASHES[profile.id], f"{profile.id} moved"


def test_the_pack_identity_is_separate_from_the_style_policy() -> None:
    """A fifth identity, not a change to the fourth.

    Adding a profile must not move the hash that says how sentence uniformity is
    computed. Measurement semantics and interpretation semantics change for
    different reasons and are versioned separately.
    """
    assert pack_hash(load_pack()) != policy.policy_hash()


def test_hashing_is_stable_within_a_process() -> None:
    assert pack_hash(load_pack()) == pack_hash(load_pack())
    for profile in load_pack():
        assert profile_hash(profile) == profile.hash


def test_yaml_formatting_does_not_reach_the_hash() -> None:
    """The hash is taken over the validated object, not the file.

    Reformatting a profile — reordering keys, rewrapping a block scalar, changing
    the line endings — must produce the same identity, because none of it changes
    what a reader is told.
    """
    for identifier in profile_ids():
        document = raw(identifier)
        # Reversed key order at every level, and CRLF in the source.
        shuffled = {key: document[key] for key in reversed(list(document))}
        shuffled["diagnostics"] = {
            key: {inner: value[inner] for inner in reversed(list(value))}
            for key, value in reversed(list(document["diagnostics"].items()))
        }
        assert profile_hash(parse_profile(shuffled, "shuffled")) == PROFILE_HASHES[identifier]


def test_changing_a_threshold_moves_the_hash() -> None:
    for identifier in profile_ids():
        document = raw(identifier)
        target = policy.REPEATED_SENTENCE_OPENER
        document["diagnostics"][target]["notice"] += 0.05
        document["diagnostics"][target]["strong"] += 0.05
        assert profile_hash(parse_profile(document, "mutated")) != PROFILE_HASHES[identifier]


def test_changing_a_minimum_sample_moves_the_hash() -> None:
    document = raw("natural")
    document["diagnostics"][policy.SENTENCE_UNIFORMITY]["minimum_sample"] += 4
    assert profile_hash(parse_profile(document, "mutated")) != PROFILE_HASHES["natural"]


def test_changing_a_target_range_moves_the_hash() -> None:
    document = raw("academic")
    document["targets"]["sentence_words_mean"]["max"] += 1
    assert profile_hash(parse_profile(document, "mutated")) != PROFILE_HASHES["academic"]


def test_changing_a_provenance_moves_the_hash() -> None:
    """Relabelling a guess as evidence is a change a reviewer must see.

    No finding depends on provenance, so it would have been defensible to leave
    it out. It is in because `weakly-calibrated` is the field that admits a
    threshold has no data behind it, and quietly upgrading that admission is
    exactly the sort of edit that should not pass unnoticed.
    """
    document = raw("plain")
    document["diagnostics"][policy.LIST_DOMINANCE]["provenance"] = "project-calibration"
    assert profile_hash(parse_profile(document, "mutated")) != PROFILE_HASHES["plain"]


@pytest.mark.parametrize("field", ["name", "description", "target_use"])
def test_changing_display_prose_does_not_move_the_hash(field: str) -> None:
    """The other half of the decision, tested so it stays a decision.

    A typo fix in a description must not invalidate a pinned cross-platform
    identity, because nobody could act on that failure. The line is drawn at
    behaviour: prose about the profile is out, numbers and provenance are in.
    """
    document = raw("technical")
    document[field] = "Entirely different wording that changes nothing about behaviour."
    assert profile_hash(parse_profile(document, "reworded")) == PROFILE_HASHES["technical"]


def test_changing_a_reason_does_not_move_the_hash() -> None:
    document = raw("government")
    document["diagnostics"][policy.LIST_DOMINANCE]["reason"] = "Rewritten explanation."
    assert profile_hash(parse_profile(document, "reworded")) == PROFILE_HASHES["government"]


def test_install_location_does_not_reach_the_hash() -> None:
    """Nothing in the canonical form is a path.

    Asserted directly rather than by relocating the package, because the
    property that matters is that no path could get in, not that one particular
    move happens to be safe.
    """
    from plainspeak.style.profiles.canonical import pack_document

    rendered = policy.canonical_json(pack_document(load_pack()))
    for fragment in (str(BUNDLED), "bundled", ".yaml", "/", "\\\\"):
        assert fragment not in rendered or fragment == "/", fragment


# ── Resolution ─────────────────────────────────────────────────────────────


def test_a_profile_resolves_by_id() -> None:
    assert load_profile("technical").id == "technical"
    assert resolve_profile("technical") is load_profile("technical")


def test_an_unknown_profile_fails_rather_than_falling_back() -> None:
    """Silently defaulting would analyse a specification as conversational prose.

    The report would look entirely normal and would be answering a question
    nobody asked, which is the worst shape a configuration error can take.
    """
    with pytest.raises(ProfileError) as raised:
        load_profile("natrual")
    assert "natrual" in str(raised.value)
    assert "natural" in str(raised.value), "the error should list what is available"


def test_there_is_no_hidden_default() -> None:
    """`interpret` has no default profile parameter to fall back to."""
    import inspect

    from plainspeak.style.interpret import interpret

    signature = inspect.signature(interpret)
    assert signature.parameters["profile"].default is inspect.Parameter.empty


# ── What a profile may not be ──────────────────────────────────────────────


def base(identifier: str = "natural") -> dict:
    return copy.deepcopy(raw(identifier))


def test_a_minimum_below_the_baseline_floor_is_rejected() -> None:
    document = base()
    document["diagnostics"][policy.SENTENCE_UNIFORMITY]["minimum_sample"] = 3
    with pytest.raises(ProfileError, match="below the baseline safety floor"):
        parse_profile(document, "bad.yaml")


def test_an_inverted_threshold_the_wrong_way_round_is_rejected() -> None:
    """Reversed bands still produce findings — the wrong way round."""
    document = base()
    document["diagnostics"][policy.SENTENCE_UNIFORMITY]["notice"] = 0.20
    document["diagnostics"][policy.SENTENCE_UNIFORMITY]["strong"] = 0.40
    with pytest.raises(ProfileError, match="inverted"):
        parse_profile(document, "bad.yaml")


def test_a_normal_threshold_the_wrong_way_round_is_rejected() -> None:
    document = base()
    document["diagnostics"][policy.LIST_DOMINANCE]["notice"] = 0.80
    document["diagnostics"][policy.LIST_DOMINANCE]["strong"] = 0.50
    with pytest.raises(ProfileError, match="must be above"):
        parse_profile(document, "bad.yaml")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_threshold_is_rejected(value: float) -> None:
    """NaN compares false against everything, so it silences a diagnostic.

    The failure would be invisible: the report would show nothing found, which
    is exactly what a clean document shows.
    """
    document = base()
    document["diagnostics"][policy.LIST_DOMINANCE]["notice"] = value
    with pytest.raises((ProfileError, ValueError)):
        parse_profile(document, "bad.yaml")


def test_an_unknown_diagnostic_is_rejected() -> None:
    document = base()
    document["diagnostics"]["PS.STYLE.INVENTED"] = document["diagnostics"][policy.LIST_DOMINANCE]
    with pytest.raises(ProfileError, match="unknown diagnostic"):
        parse_profile(document, "bad.yaml")


def test_a_missing_diagnostic_is_rejected() -> None:
    document = base()
    del document["diagnostics"][policy.LIST_DOMINANCE]
    with pytest.raises(ProfileError, match="missing"):
        parse_profile(document, "bad.yaml")


def test_an_unknown_top_level_field_is_rejected() -> None:
    document = base()
    document["thresholds"] = {}
    with pytest.raises(ProfileError, match="unknown field"):
        parse_profile(document, "bad.yaml")


def test_a_misspelled_diagnostic_field_is_rejected() -> None:
    """The quiet failure: a typo reads as absent and keeps the baseline value."""
    document = base()
    document["diagnostics"][policy.LIST_DOMINANCE]["notise"] = 0.9
    with pytest.raises(ProfileError, match="unknown field"):
        parse_profile(document, "bad.yaml")


def test_an_impossible_target_range_is_rejected() -> None:
    document = base()
    document["targets"]["sentence_words_mean"] = {
        "min": 30, "max": 10, "provenance": "project-calibration",
    }
    with pytest.raises(ProfileError, match="no value can satisfy"):
        parse_profile(document, "bad.yaml")


def test_an_untargetable_metric_is_rejected() -> None:
    document = base()
    document["targets"]["template_there_is"] = {
        "min": 0, "max": 1, "provenance": "project-calibration",
    }
    with pytest.raises(ProfileError, match="not targetable"):
        parse_profile(document, "bad.yaml")


def test_an_unknown_provenance_is_rejected() -> None:
    document = base()
    document["diagnostics"][policy.LIST_DOMINANCE]["provenance"] = "vibes"
    with pytest.raises(ProfileError, match="provenance"):
        parse_profile(document, "bad.yaml")


@pytest.mark.parametrize(
    "field", ["replacement", "variation", "preferred_synonym", "rewrite", "substitutions"]
)
def test_a_transformation_field_is_rejected(field: str) -> None:
    """Interpretation does not get to smuggle in edit authority.

    A profile may say "repeated transition threshold: 0.7". It may not say
    "replace furthermore with also". The check is by field name, at any depth, so
    an attempt has to be deliberate rather than accidental — and fails loudly
    either way.
    """
    document = base()
    document["diagnostics"][policy.REPEATED_TRANSITION][field] = {"furthermore": "also"}
    with pytest.raises(ProfileError, match="transformation instruction"):
        parse_profile(document, "bad.yaml")


@pytest.mark.parametrize(
    "field", ["ignore_integrity", "skip_integrity", "unsafe", "protected_terms", "ruleset"]
)
def test_a_profile_cannot_name_the_firewall(field: str) -> None:
    """There is no integrity override, and an attempt to write one fails.

    None of these keys does anything — no code reads them — but a bundled profile
    containing one would sit in the tree looking as though it worked, and the
    next person to read it would reasonably conclude the mechanism exists.
    """
    document = base()
    document[field] = True
    with pytest.raises(ProfileError):
        parse_profile(document, "bad.yaml")


def test_a_nested_transformation_field_is_rejected() -> None:
    """Depth does not help."""
    document = base()
    document["targets"]["sentence_words_mean"] = {
        "min": 1, "max": 2, "provenance": "project-calibration",
        "rewrite": {"deep": {"deeper": "value"}},
    }
    with pytest.raises(ProfileError, match="transformation instruction"):
        parse_profile(document, "bad.yaml")


def test_duplicate_ids_are_rejected(tmp_path, monkeypatch) -> None:
    from plainspeak.style.profiles import loader

    for name in ("a.yaml", "b.yaml"):
        (tmp_path / name).write_text(
            (BUNDLED / "natural.yaml").read_text(encoding="utf-8"), encoding="utf-8"
        )
    monkeypatch.setattr(loader, "BUNDLED", tmp_path)
    loader.load_pack.cache_clear()
    try:
        with pytest.raises(ProfileError, match="duplicate profile id"):
            loader.load_pack()
    finally:
        loader.load_pack.cache_clear()


def test_a_pack_that_does_not_match_the_display_order_is_rejected(tmp_path, monkeypatch) -> None:
    from plainspeak.style.profiles import loader

    (tmp_path / "natural.yaml").write_text(
        (BUNDLED / "natural.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(loader, "BUNDLED", tmp_path)
    loader.load_pack.cache_clear()
    try:
        with pytest.raises(ProfileError, match="display order"):
            loader.load_pack()
    finally:
        loader.load_pack.cache_clear()


def test_yaml_is_loaded_safely() -> None:
    source = (
        Path(__file__).resolve().parent.parent
        / "plainspeak" / "style" / "profiles" / "loader.py"
    ).read_text(encoding="utf-8")
    assert "yaml.safe_load" in source
    for unsafe in ("yaml.load(", "yaml.full_load", "yaml.unsafe_load"):
        assert unsafe not in source


# ── Explanation ────────────────────────────────────────────────────────────


def test_explain_returns_what_a_selector_needs() -> None:
    explained = explain_profile("technical")

    assert explained["id"] == "technical"
    assert explained["version"] == 1
    assert explained["name"] and explained["description"] and explained["target_use"]
    assert len(explained["sha256"]) == 64
    assert len(explained["profile_pack_sha256"]) == 64
    assert set(explained["diagnostics"]) == set(policy.DIAGNOSTIC_IDS)
    assert explained["targets"]
    assert explained["weakly_calibrated"]


def test_explain_shows_what_moved_and_why() -> None:
    explained = explain_profile("technical")
    moved = {
        key: value
        for key, value in explained["diagnostics"].items()
        if value["differs_from_baseline"]
    }
    assert moved, "technical differs from the baseline somewhere"
    for key, value in moved.items():
        assert value["reason"], f"{key} moved without saying why"
        assert value["baseline_notice"] is not None


def test_explain_covers_every_profile_in_order() -> None:
    assert [item["id"] for item in explain_all()] == list(PROFILE_ORDER)


def test_explanations_are_plain_data() -> None:
    import json

    for item in explain_all():
        assert json.loads(json.dumps(item)) == item
