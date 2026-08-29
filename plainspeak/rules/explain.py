"""Explaining a rule to whoever is being asked to accept its change.

The product commitment is that PlainSpeak applies inspectable rules rather than
thinking about your writing. That is only true if the inspection is actually
available at the point of decision — in a desktop review pane, in `plainspeak
rules explain`, in an MCP response. All three will render the same structure,
built here once, so they cannot describe the same rule differently.

This is metadata only. Nothing here matches, decides or edits.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .loader import Ruleset, load_ruleset
from .schema import ACTION_DELETE, ACTION_REPLACE, MODE_SAFE_FIX, Rule


@dataclass(frozen=True)
class RuleExplanation:
    """Everything a person needs to judge whether a rule should have fired."""

    id: str
    version: int
    name: str
    mode: str
    family: str
    description: str
    reason: str
    matches: str
    proposes: str
    scope_include: tuple[str, ...]
    scope_exclude: tuple[str, ...]
    case_policy: str
    priority: int
    provenance_source: str
    provenance_reference: str
    provenance_licence: str
    examples_positive: tuple[str, ...]
    examples_negative: tuple[str, ...]
    examples_transform: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        """A plain-data form, for JSON output and adapter rendering."""
        return {
            "id": self.id,
            "version": self.version,
            "name": self.name,
            "mode": self.mode,
            "family": self.family,
            "description": self.description,
            "reason": self.reason,
            "matches": self.matches,
            "proposes": self.proposes,
            "scope": {"include": list(self.scope_include), "exclude": list(self.scope_exclude)},
            "case_policy": self.case_policy,
            "priority": self.priority,
            "provenance": {
                "source": self.provenance_source,
                "reference": self.provenance_reference,
                "licence": self.provenance_licence,
            },
            "examples": {
                "positive": list(self.examples_positive),
                "negative": list(self.examples_negative),
                "transform": [
                    {"before": before, "after": after}
                    for before, after in self.examples_transform
                ],
            },
        }


def explain_rule(rule_id: str, ruleset: Optional[Ruleset] = None) -> RuleExplanation:
    """Look up a rule and describe it. Raises `KeyError` if there is no such rule."""
    resolved = ruleset if ruleset is not None else load_ruleset()
    rule = resolved.by_id(rule_id)
    if rule is None:
        raise KeyError(f"no such rule: {rule_id}")
    return describe(rule)


def describe(rule: Rule) -> RuleExplanation:
    return RuleExplanation(
        id=rule.id,
        version=rule.version,
        name=rule.name,
        mode=rule.mode,
        family=rule.family,
        description=rule.description,
        reason=rule.reason,
        matches=_describe_match(rule),
        proposes=_describe_action(rule),
        scope_include=rule.scope.include,
        scope_exclude=rule.scope.exclude,
        case_policy=rule.case_policy,
        priority=rule.priority,
        provenance_source=rule.provenance.source,
        provenance_reference=rule.provenance.reference,
        provenance_licence=rule.provenance.licence,
        examples_positive=rule.examples.positive,
        examples_negative=rule.examples.negative,
        examples_transform=tuple(
            (item.before, item.after) for item in rule.examples.transform
        ),
    )


def _describe_match(rule: Rule) -> str:
    sensitivity = "case-sensitive" if rule.match.case == "sensitive" else "any capitalisation"
    if rule.match.type == "regex":
        return f"the pattern /{rule.match.pattern}/ ({sensitivity})"
    forms = list(rule.match.literals)
    if len(forms) == 1:
        return f"the {rule.match.type} “{forms[0]}” ({sensitivity})"
    listed = ", ".join(f"“{form}”" for form in forms)
    return f"any of {listed} ({sensitivity})"


def _describe_action(rule: Rule) -> str:
    if rule.action.type == ACTION_REPLACE:
        return f"replacing it with “{rule.action.replacement}”"
    if rule.action.type == ACTION_DELETE:
        tail = ", capitalising the following word" if rule.action.recapitalize else ""
        return f"deleting it{tail}"
    if rule.mode == MODE_SAFE_FIX:  # pragma: no cover - schema forbids this
        return "an edit"
    return "nothing; this rule reports only"


def list_rules(ruleset: Optional[Ruleset] = None) -> tuple[RuleExplanation, ...]:
    """Describe every rule, ordered by identity."""
    resolved = ruleset if ruleset is not None else load_ruleset()
    return tuple(describe(rule) for rule in resolved.rules)
