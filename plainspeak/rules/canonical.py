"""Canonical form of a rule, and the identity of a ruleset.

Two machines holding the same rules must compute the same ruleset hash. That
sounds obvious and is easy to get wrong, because the obvious implementation —
hash the files — makes the identity depend on things that are not the rules:

- the order the filesystem happened to return directory entries in;
- `\\` versus `/` in the paths;
- which directory a rule file was filed under;
- YAML key order, indentation, quoting style and comments;
- trailing whitespace and line endings.

None of those change what a rule does, so none of them may change what a
ruleset is called. The hash is therefore computed over a canonical JSON
rendering of the *validated* rules — the objects the loader produced, not the
text it read — with rules sorted by identity and every mapping sorted by key.

The hash covers everything a rule declares, including its description, reason
and provenance. Those are published: they appear in reports and in
`explain_rule`, so changing one changes what a user is told, and the ruleset
identity should move when that happens.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .schema import Rule

#: Bumped when the canonical form itself changes shape, so that a hash computed
#: under an older layout can never be mistaken for a current one.
CANONICAL_FORM_VERSION = 1


def canonical_rule(rule: Rule) -> dict[str, Any]:
    """The identity-bearing content of one rule, as plain data.

    `family` is deliberately absent: it records which directory the rule was
    filed under, and moving a file must not change the ruleset.
    """
    return {
        "id": rule.id,
        "version": rule.version,
        "name": rule.name,
        "mode": rule.mode,
        "description": rule.description,
        "match": {
            "type": rule.match.type,
            "text": rule.match.text,
            "forms": list(rule.match.forms),
            "pattern": rule.match.pattern,
            "case": rule.match.case,
        },
        "action": {
            "type": rule.action.type,
            "replacement": rule.action.replacement,
            "recapitalize": rule.action.recapitalize,
        },
        "scope": {
            "include": list(rule.scope.include),
            "exclude": list(rule.scope.exclude),
        },
        "case_policy": rule.case_policy,
        "priority": rule.priority,
        "reason": rule.reason,
        "provenance": {
            "source": rule.provenance.source,
            "reference": rule.provenance.reference,
            "licence": rule.provenance.licence,
        },
        "examples": {
            "positive": list(rule.examples.positive),
            "negative": list(rule.examples.negative),
            "transform": [
                {"before": item.before, "after": item.after} for item in rule.examples.transform
            ],
        },
    }


def canonical_json(value: Any) -> str:
    """Render data in the one form this project treats as canonical.

    Sorted keys, no insignificant whitespace, UTF-8 rather than escapes, and a
    trailing newline. Used for both the ruleset hash and the audit output, so
    that the same bytes are produced on every platform.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def ruleset_document(rules: Iterable[Rule], ruleset_version: str) -> dict[str, Any]:
    """The whole ruleset as canonical data, ordered by rule identity."""
    ordered = sorted(rules, key=lambda rule: (rule.id, rule.version))
    return {
        "canonical_form": CANONICAL_FORM_VERSION,
        "ruleset_version": ruleset_version,
        "rules": [canonical_rule(rule) for rule in ordered],
    }


def ruleset_hash(rules: Iterable[Rule], ruleset_version: str) -> str:
    """SHA-256 of the canonical ruleset document."""
    document = ruleset_document(rules, ruleset_version)
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
