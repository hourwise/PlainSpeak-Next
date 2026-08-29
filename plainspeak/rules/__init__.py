"""Declarative prose rules.

This package holds what PlainSpeak knows about language, as data rather than as
Python. A rule states what it looks for, what it would do about it, why, and
where it came from — and a reviewer can read all of that without opening a
source file.

It is deliberately a leaf. `rules` imports nothing else from the package: it
does not parse documents, does not know what a heading is, does not compute
source offsets and does not decide whether an edit may be applied. It sees a
string, finds occurrences in it, and reports analysis coordinates.

Everything downstream of that — mapping to the source, consulting the integrity
register, resolving conflicts, building a plan — belongs to `pipeline`, which
is the only layer permitted to join rules to documents. That separation is what
stops a rule ever putting an edit in the wrong place: a rule cannot name a
source offset, because it has never seen one.

    load_ruleset()          the bundled rules, validated and identified
    find_matches(text, ...) matches in analysis coordinates
    explain_rule(id)        inspectable metadata, for reports and adapters
"""

from .canonical import canonical_json, canonical_rule, ruleset_hash, sha256_text
from .explain import RuleExplanation, explain_rule
from .loader import BUNDLED_ROOT, Ruleset, RulesetError, load_ruleset
from .matcher import RuleMatch, deletion_span, find_matches
from .schema import (
    ACTION_DELETE,
    ACTION_NONE,
    ACTION_PROTECT,
    ACTION_REPLACE,
    MODE_DIAGNOSTIC,
    MODE_PROTECTED,
    MODE_SAFE_FIX,
    Rule,
    RuleError,
)

__all__ = [
    "ACTION_DELETE",
    "ACTION_NONE",
    "ACTION_PROTECT",
    "ACTION_REPLACE",
    "BUNDLED_ROOT",
    "MODE_DIAGNOSTIC",
    "MODE_PROTECTED",
    "MODE_SAFE_FIX",
    "Rule",
    "RuleError",
    "RuleExplanation",
    "RuleMatch",
    "Ruleset",
    "RulesetError",
    "canonical_json",
    "canonical_rule",
    "deletion_span",
    "explain_rule",
    "find_matches",
    "load_ruleset",
    "ruleset_hash",
    "sha256_text",
]
