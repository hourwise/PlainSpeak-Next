"""Reading, validating and freezing the bundled profiles.

A malformed bundled profile is a build failure, not a runtime surprise. The
whole pack is validated on first load and the failure names the file, the
diagnostic and what was wrong with it, because the person who will read that
message is editing YAML and needs to know which line to go to.

Validation is deliberately paranoid about the things that fail quietly:

- **A minimum sample below the baseline floor.** The Phase 7 minimums are
  measurement-safety floors — a paragraph-uniformity ratio over four paragraphs
  is arithmetic rather than evidence, and `government.md` proved it by producing
  a false positive at five. A profile may demand *more* evidence. It may never
  demand less, and this is where that is enforced rather than trusted.
- **Thresholds in the wrong direction.** For an inverted diagnostic `strong`
  must sit below `notice`. Get it backwards and the diagnostic still runs, still
  produces bands, and gets them the wrong way round.
- **NaN and infinity.** A NaN threshold compares false against everything, so
  the diagnostic goes permanently silent and looks like a clean document.
- **Unknown fields.** A typo in a key name is otherwise a threshold that reads
  as absent and silently keeps the baseline value.
- **Transformation fields.** A profile may not carry `replacement`,
  `variation`, `preferred_synonym` or `rewrite`. Interpretation does not get to
  smuggle in edit authority, and the check is by field name so the smuggling has
  to be deliberate rather than accidental.

Nothing here can weaken the integrity firewall, because nothing here can reach
it. There is no `ignore_integrity`, no override key, and no mechanism a profile
could use to construct one: a profile holds numbers and prose, and the firewall
is not consulted by anything a number can influence.
"""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from ..policy import DIAGNOSTIC_IDS, INVERTED, MINIMUM_SAMPLES, THRESHOLDS
from .canonical import PROFILE_ORDER, pack_hash, profile_hash
from .model import PROVENANCE, DiagnosticRule, StyleProfile, TargetRange, finite_number

BUNDLED = Path(__file__).resolve().parent / "bundled"

#: Metrics a target range may name. Restricted to the stable, interpretable ones
#: rather than everything `measure()` happens to emit — a profile that targeted
#: an internal counter would be depending on an implementation detail.
TARGETABLE_METRICS: frozenset[str] = frozenset(
    {
        "sentence_words_mean",
        "sentence_words_median",
        "sentence_words_variation",
        "paragraph_words_mean",
        "paragraph_sentences_mean",
        "paragraph_words_variation",
        "short_sentence_rate",
        "long_sentence_rate",
        "contraction_per_1000",
        "pronoun_first_singular_per_1000",
        "pronoun_first_plural_per_1000",
        "pronoun_second_per_1000",
        "punctuation_semicolon_per_1000",
        "punctuation_em_dash_per_1000",
        "punctuation_colon_per_1000",
        "punctuation_open_parenthesis_per_1000",
        "questions_per_100_sentences",
        "content_word_diversity",
        "list_block_share",
        "words_per_heading",
    }
)

TOP_LEVEL_FIELDS = frozenset(
    {"id", "version", "name", "description", "target_use", "provenance", "diagnostics", "targets"}
)
DIAGNOSTIC_FIELDS = frozenset({"enabled", "notice", "strong", "minimum_sample", "provenance", "reason"})
TARGET_FIELDS = frozenset({"min", "max", "provenance", "reason"})

#: Field names that would make a profile a transformation policy. Checked
#: everywhere in the document, at any depth.
TRANSFORMATION_FIELDS = frozenset(
    {"replacement", "replacements", "variation", "variations", "preferred_synonym",
     "preferred_synonyms", "rewrite", "rewrites", "substitute", "substitutions", "fix", "fixes"}
)

#: Keys that would be an attempt to reach the firewall. None of these can do
#: anything — there is no code that reads them — but a bundled profile
#: containing one means somebody tried, and that should fail loudly rather than
#: sit in the tree looking like it works.
FORBIDDEN_KEYS = frozenset(
    {"ignore_integrity", "skip_integrity", "unsafe", "allow_unsafe", "force",
     "integrity", "protected", "protected_terms", "ruleset", "morphology"}
)


class ProfileError(ValueError):
    """A bundled profile is malformed. Always a build failure."""


def _reject_forbidden(value: Any, where: str) -> None:
    """Walk the raw document looking for keys that must never appear."""
    if isinstance(value, dict):
        for key, item in value.items():
            name = str(key).lower()
            if name in TRANSFORMATION_FIELDS:
                raise ProfileError(
                    f"{where}: `{key}` is a transformation instruction. A profile decides how a "
                    f"measurement is interpreted; it does not decide what to write instead."
                )
            if name in FORBIDDEN_KEYS:
                raise ProfileError(
                    f"{where}: `{key}` is not something a profile may express. Interpretation "
                    f"cannot reach the integrity firewall, the ruleset or morphology."
                )
            _reject_forbidden(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden(item, f"{where}[{index}]")


def _unknown(present: Iterable[str], allowed: frozenset[str], where: str) -> None:
    extra = sorted(set(present) - allowed)
    if extra:
        raise ProfileError(
            f"{where}: unknown field(s) {extra}. A misspelled key would otherwise read as "
            f"absent and silently keep the baseline value."
        )


def _provenance(value: Any, where: str) -> str:
    if value not in PROVENANCE:
        raise ProfileError(f"{where}: provenance {value!r} is not one of {list(PROVENANCE)}")
    return value


def _diagnostic_rule(diagnostic: str, raw: Any, where: str) -> DiagnosticRule:
    if not isinstance(raw, dict):
        raise ProfileError(f"{where}: expected a mapping, got {type(raw).__name__}")
    _unknown(raw, DIAGNOSTIC_FIELDS, where)

    for required in ("enabled", "notice", "strong", "minimum_sample", "provenance"):
        if required not in raw:
            raise ProfileError(f"{where}: missing `{required}`")

    enabled = raw["enabled"]
    if not isinstance(enabled, bool):
        raise ProfileError(f"{where}: `enabled` must be true or false, got {enabled!r}")

    reason = str(raw.get("reason", "")).strip()
    if not enabled and not reason:
        raise ProfileError(
            f"{where}: a disabled diagnostic must say why. Silence loses evidence, so it is "
            f"the one profile decision that always needs an argument."
        )

    notice = finite_number(raw["notice"], f"{where}.notice")
    strong = finite_number(raw["strong"], f"{where}.strong")

    inverted = diagnostic in INVERTED
    if inverted and not strong < notice:
        raise ProfileError(
            f"{where}: {diagnostic} is inverted, so `strong` ({strong}) must be below `notice` "
            f"({notice}). Reversed bands still produce findings — the wrong way round."
        )
    if not inverted and not strong > notice:
        raise ProfileError(
            f"{where}: `strong` ({strong}) must be above `notice` ({notice})"
        )

    minimum = raw["minimum_sample"]
    if not isinstance(minimum, int) or isinstance(minimum, bool):
        raise ProfileError(f"{where}: `minimum_sample` must be a whole number, got {minimum!r}")
    floor = MINIMUM_SAMPLES[diagnostic]
    if minimum < floor:
        raise ProfileError(
            f"{where}: `minimum_sample` {minimum} is below the baseline safety floor of {floor}. "
            f"A profile may demand more evidence than the measurement needs; it may never "
            f"demand less."
        )

    return DiagnosticRule(
        diagnostic=diagnostic,
        enabled=enabled,
        notice=notice,
        strong=strong,
        minimum_sample=minimum,
        inverted=inverted,
        provenance=_provenance(raw["provenance"], f"{where}.provenance"),
        reason=reason,
    )


def _target_range(metric: str, raw: Any, where: str) -> TargetRange:
    if not isinstance(raw, dict):
        raise ProfileError(f"{where}: expected a mapping, got {type(raw).__name__}")
    _unknown(raw, TARGET_FIELDS, where)

    for required in ("min", "max", "provenance"):
        if required not in raw:
            raise ProfileError(f"{where}: missing `{required}`")

    minimum = finite_number(raw["min"], f"{where}.min")
    maximum = finite_number(raw["max"], f"{where}.max")
    if minimum > maximum:
        raise ProfileError(f"{where}: min {minimum} is above max {maximum}; no value can satisfy it")

    return TargetRange(
        metric=metric,
        minimum=minimum,
        maximum=maximum,
        provenance=_provenance(raw["provenance"], f"{where}.provenance"),
        reason=str(raw.get("reason", "")).strip(),
    )


def parse_profile(raw: Any, where: str) -> StyleProfile:
    """Validate one profile document and freeze it."""
    if not isinstance(raw, dict):
        raise ProfileError(f"{where}: expected a mapping at the top level")

    _reject_forbidden(raw, where)
    _unknown(raw, TOP_LEVEL_FIELDS, where)

    for required in ("id", "version", "name", "description", "target_use", "provenance",
                     "diagnostics"):
        if required not in raw:
            raise ProfileError(f"{where}: missing `{required}`")

    identifier = raw["id"]
    if not isinstance(identifier, str) or not identifier.isidentifier() or identifier.lower() != identifier:
        raise ProfileError(
            f"{where}: id {identifier!r} must be a lower-case machine identifier"
        )

    version = raw["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ProfileError(f"{where}: version must be a positive whole number, got {version!r}")

    diagnostics_raw = raw["diagnostics"]
    if not isinstance(diagnostics_raw, dict):
        raise ProfileError(f"{where}.diagnostics: expected a mapping")

    unknown = sorted(set(diagnostics_raw) - set(DIAGNOSTIC_IDS))
    if unknown:
        raise ProfileError(
            f"{where}.diagnostics: unknown diagnostic(s) {unknown}. A profile interprets the "
            f"diagnostics the base policy defines; it cannot invent one."
        )
    missing = sorted(set(DIAGNOSTIC_IDS) - set(diagnostics_raw))
    if missing:
        raise ProfileError(
            f"{where}.diagnostics: missing {missing}. Every profile states every diagnostic "
            f"explicitly — there is no inheritance, so an absent one would have no value at all."
        )

    diagnostics = {
        key: _diagnostic_rule(key, diagnostics_raw[key], f"{where}.diagnostics.{key}")
        for key in sorted(diagnostics_raw)
    }

    targets_raw = raw.get("targets") or {}
    if not isinstance(targets_raw, dict):
        raise ProfileError(f"{where}.targets: expected a mapping")
    unknown_metrics = sorted(set(targets_raw) - TARGETABLE_METRICS)
    if unknown_metrics:
        raise ProfileError(
            f"{where}.targets: {unknown_metrics} are not targetable metrics. "
            f"Targetable: {sorted(TARGETABLE_METRICS)}"
        )
    targets = {
        key: _target_range(key, targets_raw[key], f"{where}.targets.{key}")
        for key in sorted(targets_raw)
    }

    profile = StyleProfile(
        id=identifier,
        version=version,
        name=str(raw["name"]),
        description=" ".join(str(raw["description"]).split()),
        target_use=" ".join(str(raw["target_use"]).split()),
        provenance=_provenance(raw["provenance"], f"{where}.provenance"),
        diagnostics=diagnostics,
        targets=targets,
    )
    # The hash is taken over the validated object rather than the file, so YAML
    # formatting, key order and line endings cannot reach it.
    return replace(profile, hash=profile_hash(profile))


@lru_cache(maxsize=1)
def load_pack() -> tuple[StyleProfile, ...]:
    """Every bundled profile, validated, in canonical display order."""
    found: dict[str, StyleProfile] = {}
    seen_versions: dict[tuple[str, int], str] = {}

    # Sorted so the *validation* order is stable too: two malformed profiles
    # should always produce the same error message.
    for path in sorted(BUNDLED.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = parse_profile(document, path.name)

        if profile.id in found:
            raise ProfileError(
                f"{path.name}: duplicate profile id {profile.id!r}, already defined by another file"
            )
        key = (profile.id, profile.version)
        if key in seen_versions:
            raise ProfileError(
                f"{path.name}: duplicate {profile.id!r} version {profile.version}, "
                f"already defined by {seen_versions[key]}"
            )
        seen_versions[key] = path.name
        found[profile.id] = profile

    if not found:
        raise ProfileError(f"no bundled profiles found in {BUNDLED}")

    listed = set(PROFILE_ORDER)
    if set(found) != listed:
        raise ProfileError(
            f"the bundled profiles {sorted(found)} do not match the declared display order "
            f"{list(PROFILE_ORDER)}; filesystem order is not a design decision"
        )

    return tuple(found[identifier] for identifier in PROFILE_ORDER)


def profile_ids() -> tuple[str, ...]:
    """Bundled profile IDs in canonical display order."""
    return tuple(profile.id for profile in load_pack())


def load_profile(identifier: str) -> StyleProfile:
    """One profile by ID.

    An unknown ID is an error. Falling back to a default would mean a typo in a
    configuration file silently analysed a technical specification against
    conversational expectations, and the report would look entirely normal.
    """
    for profile in load_pack():
        if profile.id == identifier:
            return profile
    raise ProfileError(
        f"unknown style profile {identifier!r}; available: {list(profile_ids())}"
    )


#: `resolve_profile` is the name the brief suggested; `load_profile` is the name
#: the rest of this codebase uses for the same shape of call. Same function.
resolve_profile = load_profile


def pack_identity() -> dict[str, Any]:
    """The pack's version and hash, plus every profile's own identity."""
    profiles = load_pack()
    return {
        "profile_pack_sha256": pack_hash(profiles),
        "profiles": {profile.id: profile.reference() for profile in profiles},
    }


def explain_profile(identifier: str) -> dict[str, Any]:
    """Everything a person needs to decide whether this is the right profile.

    Built for a profile selector — a desktop pane, a CLI listing, an MCP
    resource — which is why it returns plain data rather than formatted text.
    None of those adapters exist yet; this is the shape they will read.
    """
    from ..policy import STYLE_POLICY_VERSION, THRESHOLDS as BASE

    profile = load_profile(identifier)
    return {
        "id": profile.id,
        "version": profile.version,
        "name": profile.name,
        "description": profile.description,
        "target_use": profile.target_use,
        "provenance": profile.provenance,
        "sha256": profile.hash,
        "profile_pack_sha256": pack_hash(load_pack()),
        "style_policy_version": STYLE_POLICY_VERSION,
        "diagnostics": {
            key: {
                "enabled": rule.enabled,
                "notice": rule.notice,
                "strong": rule.strong,
                "minimum_sample": rule.minimum_sample,
                "baseline_notice": BASE[key][0],
                "baseline_strong": BASE[key][1],
                "baseline_minimum_sample": MINIMUM_SAMPLES[key],
                "differs_from_baseline": (
                    rule.notice != BASE[key][0]
                    or rule.strong != BASE[key][1]
                    or rule.minimum_sample != MINIMUM_SAMPLES[key]
                    or not rule.enabled
                ),
                "provenance": rule.provenance,
                "reason": rule.reason,
            }
            for key, rule in sorted(profile.diagnostics.items())
        },
        "targets": {
            key: {
                "min": target.minimum,
                "max": target.maximum,
                "provenance": target.provenance,
                "reason": target.reason,
            }
            for key, target in sorted(profile.targets.items())
        },
        "disabled": list(profile.disabled),
        "weakly_calibrated": list(profile.weakly_calibrated),
    }


def explain_all() -> list[dict[str, Any]]:
    """Every bundled profile, in canonical display order."""
    return [explain_profile(identifier) for identifier in profile_ids()]
