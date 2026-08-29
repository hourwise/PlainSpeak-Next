"""Protecting meaning from the transformation engine.

Two authorities live here, and neither can weaken the other.

**The protected-term register** (`protected`) names domain terms of art that
must never be substituted — "consideration" in a contract is not "thought". It
predates the rule engine and remains authoritative.

**The integrity firewall** (`policy`, `extract`, `compare`) answers a narrower
question about any proposed transformation: *did this change information we have
declared invariant?* Numbers, percentages, currency, units, dates, times, URLs,
emails, paths, version and vulnerability identifiers, negation, modal verbs and
a bounded set of comparators. Not whether the prose reads better — only whether
the facts survived.

The relationship with the rest of the system is one-directional and deliberate:

    rules propose  →  integrity vetoes

A rule classified `safe-fix` does not outrank this layer. If a rule would turn
"You must not apply after 5pm" into "You must apply after 5pm", the rule engine
may well consider that structurally valid, and the firewall rejects it anyway.

There is no way to switch it off. No rule field, no caller flag, no style
profile, no future adapter. If an expert workflow ever needs an override, that
is a separate architecture and threat-model decision, not a keyword argument.

This package is an architectural leaf. It imports nothing else from PlainSpeak,
because anything it depended on could come to depend on it, and a cycle in the
component whose whole job is to say "no" would be a cycle in the safety check
itself. It works on ordinary strings and immutable contracts, uses only the
standard library, and requires no network access of any kind.
"""

from .compare import check, compare, passes
from .extract import extract, snapshot
from .model import (
    IntegrityFact,
    IntegritySnapshot,
    IntegrityVerdict,
    Violation,
    text_hash,
)
from .policy import (
    CATEGORIES,
    KINDS,
    POLICY_VERSION,
    canonical_json,
    policy_document,
    policy_hash,
)
from .protected import PROTECTED_TERMS, get_protected_domain, is_protected_term

__all__ = [
    "CATEGORIES",
    "KINDS",
    "POLICY_VERSION",
    "PROTECTED_TERMS",
    "IntegrityFact",
    "IntegritySnapshot",
    "IntegrityVerdict",
    "Violation",
    "canonical_json",
    "check",
    "compare",
    "extract",
    "get_protected_domain",
    "is_protected_term",
    "passes",
    "policy_document",
    "policy_hash",
    "snapshot",
    "text_hash",
]
