"""Style profiles: how a valid measurement is interpreted for a target style.

Phase 7 answers *what patterns does this document contain*. This package answers
*how should those patterns be read for the kind of prose the writer is aiming
at*. A specification that calls the same thing by the same name in forty places
is doing its job; the same measurement in an essay is a writer with a tic. The
measurement is identical. Only the interpretation moves.

What a profile may change:

    thresholds, minimum samples (upwards only), whether a diagnostic is
    enabled, target metric ranges, and the prose explaining any of it.

What a profile may not change, and cannot reach from here:

    document parsing, source mapping, ruleset semantics, protected terminology,
    the integrity policy, morphology, or any authority to edit text.

There is no mechanism by which a profile could weaken the integrity firewall,
and the loader rejects a bundled profile that even names one. That is belt and
braces — a profile holds numbers and prose, and no number reaches the firewall —
but the check exists so that an attempt fails loudly instead of sitting in the
tree looking as though it worked.

The pack is a fifth versioned identity, separate from the base style policy.
Measurement semantics and interpretation semantics change for different reasons,
and folding them together would mean adding a profile moved the hash that says
how sentence uniformity is computed.
"""
from __future__ import annotations

from .canonical import (
    CANONICAL_FORM_VERSION,
    PROFILE_ORDER,
    PROFILE_PACK_VERSION,
    pack_document,
    pack_hash,
    profile_document,
    profile_hash,
)
from .loader import (
    BUNDLED,
    TARGETABLE_METRICS,
    ProfileError,
    explain_all,
    explain_profile,
    load_pack,
    load_profile,
    pack_identity,
    parse_profile,
    profile_ids,
    resolve_profile,
)
from .model import PROVENANCE, TARGET_STATES, DiagnosticRule, StyleProfile, TargetRange

__all__ = [
    "BUNDLED",
    "CANONICAL_FORM_VERSION",
    "DiagnosticRule",
    "PROFILE_ORDER",
    "PROFILE_PACK_VERSION",
    "PROVENANCE",
    "ProfileError",
    "StyleProfile",
    "TARGETABLE_METRICS",
    "TARGET_STATES",
    "TargetRange",
    "explain_all",
    "explain_profile",
    "load_pack",
    "load_profile",
    "pack_document",
    "pack_hash",
    "pack_identity",
    "parse_profile",
    "profile_document",
    "profile_hash",
    "profile_ids",
    "resolve_profile",
]
