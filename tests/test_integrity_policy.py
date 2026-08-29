"""The integrity policy's identity.

The policy is versioned product behaviour. A document processed under `2026.1`
was checked against those rules and no others, so its identity travels with
every plan and every audit record, and a plan approved under one policy cannot
be applied under another.

That only means anything if the identity is genuinely a property of the policy:
the same rules must hash the same on every machine, and *anything* that changes
what would be accepted must change the hash. Both halves are tested here.
"""
from __future__ import annotations

import json

import pytest

from plainspeak.integrity import (
    CATEGORIES,
    KINDS,
    POLICY_VERSION,
    canonical_json,
    policy_document,
    policy_hash,
)
from plainspeak.integrity import policy as policy_module

#: The identity of the policy as it currently ships. Pinned deliberately, and
#: for the same reason as the ruleset hash in `test_rules_loader.py`: every
#: other test here checks that the hash does not move for reasons it should not,
#: and none of them would catch it differing *between platforms*, because each
#: machine only ever compares its own value to itself. The Windows, Linux and
#: macOS jobs all assert this number.
#:
#: Updating it is correct when the policy changes, and a diff that touches
#: `policy.py` without touching this line has changed something it did not mean
#: to.
POLICY_HASH = "21532115747ceb12218b6f388d885f26d0fbcbbd09f7f895a11c6aa61c9b4720"


def test_the_policy_has_its_expected_identity() -> None:
    assert POLICY_VERSION == "2026.1"
    assert policy_hash() == POLICY_HASH, (
        "The integrity policy hash changed.\n"
        "  If you changed the policy deliberately, update POLICY_HASH here and say so\n"
        "  in the commit message — the hash is what binds a plan to the safety rules\n"
        "  it was approved under.\n"
        "  If you did not, something platform-dependent has reached the canonical\n"
        "  form, and that is a bug in the hashing rather than in this test."
    )


def test_hashing_is_stable_within_a_process() -> None:
    assert policy_hash() == policy_hash()


def test_the_canonical_form_carries_a_version() -> None:
    assert policy_document()["canonical_form"] == policy_module.CANONICAL_FORM_VERSION


def test_the_policy_document_is_plain_json_serialisable_data() -> None:
    document = policy_document()
    assert json.loads(json.dumps(document)) == document


def test_canonical_json_is_sorted_and_newline_terminated() -> None:
    assert canonical_json({"b": 1, "a": {"d": 2, "c": 3}}) == '{"a":{"c":3,"d":2},"b":1}\n'


def test_integrity_and_rules_canonicalisation_agree() -> None:
    """The two renderings are duplicated on purpose; they must not drift.

    `integrity` may not import `rules` — it is an architectural leaf, and a
    dependency either way could become a cycle in the component whose job is to
    say "no". So the canonical JSON helper exists twice. This test is what makes
    that duplication safe.
    """
    from plainspeak.rules import canonical_json as rules_canonical_json

    for value in (
        {"b": 1, "a": 2},
        {"nested": {"z": [3, 2, 1], "a": None}},
        {"unicode": "café — 21 °C", "empty": {}},
        [1, "two", {"three": True}],
    ):
        assert canonical_json(value) == rules_canonical_json(value)


# ── Everything behavioural is in the identity ──────────────────────────────


@pytest.mark.parametrize(
    "attribute,mutate",
    [
        ("UNITS", lambda value: value + ("furlong",)),
        ("MODAL_WORDS", lambda value: value + ("ought",)),
        ("NEGATION_WORDS", lambda value: value + ("nix",)),
        ("COMPARATOR_PHRASES", lambda value: value + ("roughly",)),
        ("CURRENCY_CODES", lambda value: value + ("XYZ",)),
        ("TRIMMED_KINDS", lambda value: frozenset(value | {"number"})),
        ("TRAILING_PUNCTUATION", lambda value: value + "-"),
        ("POLICY_VERSION", lambda value: "9999.1"),
    ],
)
def test_changing_the_policy_changes_its_hash(monkeypatch, attribute: str, mutate) -> None:
    """Anything that alters what would be accepted must alter the identity.

    A vocabulary the hash did not cover would let the firewall's behaviour
    change while every plan still claimed to have been approved under the same
    policy — which is precisely the situation the hash exists to make
    impossible.
    """
    before = policy_hash()
    monkeypatch.setattr(policy_module, attribute, mutate(getattr(policy_module, attribute)))
    assert policy_hash() != before, f"changing {attribute} did not move the policy hash"


def test_changing_a_pattern_changes_the_hash(monkeypatch) -> None:
    altered = tuple(
        (kind, pattern + "?") if kind == "modal" else (kind, pattern)
        for kind, pattern in CATEGORIES
    )
    before = policy_hash()
    monkeypatch.setattr(policy_module, "CATEGORIES", altered)
    assert policy_hash() != before


def test_reordering_categories_changes_the_hash(monkeypatch) -> None:
    """Order is behaviour: an earlier category claims text a later one cannot."""
    before = policy_hash()
    monkeypatch.setattr(policy_module, "CATEGORIES", tuple(reversed(CATEGORIES)))
    assert policy_hash() != before


def test_changing_case_sensitivity_changes_the_hash(monkeypatch) -> None:
    before = policy_hash()
    monkeypatch.setattr(
        policy_module,
        "CASE_INSENSITIVE_KINDS",
        frozenset(policy_module.CASE_INSENSITIVE_KINDS - {"modal"}),
    )
    assert policy_hash() != before


def test_changing_a_normalizer_assignment_changes_the_hash(monkeypatch) -> None:
    altered = dict(policy_module.NORMALIZERS)
    altered["modal"] = "exact"
    before = policy_hash()
    monkeypatch.setattr(policy_module, "NORMALIZERS", altered)
    assert policy_hash() != before


# ── Coherence ──────────────────────────────────────────────────────────────


def test_every_category_kind_has_a_declared_normalizer() -> None:
    missing = sorted(set(KINDS) - set(policy_module.NORMALIZERS))
    assert not missing, f"kinds with no declared normalisation: {missing}"


def test_no_normalizer_is_declared_for_a_kind_that_cannot_occur() -> None:
    orphans = sorted(set(policy_module.NORMALIZERS) - set(KINDS))
    assert not orphans, f"normalisers for kinds no category produces: {orphans}"


def test_trimmed_kinds_are_real_kinds() -> None:
    assert set(policy_module.TRIMMED_KINDS) <= set(KINDS)


def test_case_insensitive_kinds_are_real_kinds() -> None:
    assert set(policy_module.CASE_INSENSITIVE_KINDS) <= set(KINDS)


def test_units_are_not_case_folded() -> None:
    """`mg` and `Mg` differ by a factor of a million."""
    assert "measurement" not in policy_module.CASE_INSENSITIVE_KINDS


def test_every_currency_symbol_maps_to_a_known_code() -> None:
    unknown = sorted(
        code for code in policy_module.CURRENCY_SYMBOLS.values()
        if code not in policy_module.CURRENCY_CODES
    )
    assert not unknown, f"symbols mapping to codes the policy does not list: {unknown}"


def test_every_pattern_compiles() -> None:
    import re

    for kind, pattern in CATEGORIES:
        re.compile(pattern, policy_module.flags_for(kind))
