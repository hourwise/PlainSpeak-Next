"""Profile identity: what is in the hash, what is not, and why.

The pack is versioned product behaviour, like the ruleset, the integrity policy,
morphology and the base style policy. It is a *fifth* identity rather than part
of the fourth, on purpose: measurement semantics and interpretation semantics
change for different reasons and at different rates, and folding them together
would mean a new profile moved the hash that says how sentence uniformity is
computed.

### What the hash covers

Everything that can change what a reader is told about their document: the
thresholds, the minimum samples, whether a diagnostic is enabled, the target
ranges, the profile version, and each override's provenance.

Provenance is in the hash even though no finding depends on it. It is what marks
a threshold `weakly-calibrated`, and quietly relabelling a number as
well-evidenced is exactly the sort of change a reviewer should be forced to see.

### What the hash does not cover

`name`, `description`, `target_use` and every per-override `reason`. These are
prose about the profile, not behaviour of it, and putting them in the hash would
mean a typo fix in a description invalidated a pinned cross-platform identity
for no reason anybody could act on.

That exclusion is a decision, not an oversight, so it is tested both ways: a
threshold change must move the hash, and a description change must not.

### Determinism

The canonical form is built from sorted keys over data the loader has already
validated, so it cannot depend on YAML formatting, filesystem order, path
separators, dictionary iteration order or where the package is installed. The
pack hash is taken over the profiles in canonical ID order, not the order the
directory happened to yield.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

from ..policy import STYLE_POLICY_VERSION, canonical_json
from .model import StyleProfile

#: Bumped only if the canonical rendering changes shape — never for a content
#: change, which the hash already covers.
CANONICAL_FORM_VERSION = 1

#: Bumped when the bundled profiles change what a reader is told.
PROFILE_PACK_VERSION = "2026.1"

#: Deliberate display order, from most general to most specialised. Filesystem
#: traversal order is not a design decision and must never become one.
PROFILE_ORDER: tuple[str, ...] = ("natural", "plain", "technical", "government", "academic")


def profile_document(profile: StyleProfile) -> dict[str, Any]:
    return profile.as_dict()


def profile_hash(profile: StyleProfile) -> str:
    return hashlib.sha256(
        canonical_json(profile_document(profile)).encode("utf-8")
    ).hexdigest()


def pack_document(profiles: Iterable[StyleProfile]) -> dict[str, Any]:
    """The whole pack as canonical data.

    The base style policy version is included because a pack is an
    interpretation *of* a particular measurement semantics. The same thresholds
    read against a different base policy would mean something different, and the
    identity should say so.
    """
    ordered = sorted(profiles, key=lambda item: item.id)
    return {
        "canonical_form": CANONICAL_FORM_VERSION,
        "profile_pack_version": PROFILE_PACK_VERSION,
        "profiles": {profile.id: profile_document(profile) for profile in ordered},
        "style_policy_version": STYLE_POLICY_VERSION,
    }


def pack_hash(profiles: Iterable[StyleProfile]) -> str:
    return hashlib.sha256(
        canonical_json(pack_document(profiles)).encode("utf-8")
    ).hexdigest()
