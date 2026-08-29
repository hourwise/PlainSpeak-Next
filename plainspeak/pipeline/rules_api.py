"""Read-only access to the ruleset, for adapters.

Adapters do not import `plainspeak.rules` directly. The reason is not
bureaucratic: the moment an adapter can reach the rule engine, it can start
matching and resolving on its own terms, and two adapters doing that
independently is how a CLI and an MCP server end up giving different answers
for the same document.

So the pipeline exposes exactly what an interface needs to *describe* rules —
list them, explain one — and nothing that would let it run them. Running them
is `build_plan`.
"""
from __future__ import annotations

from typing import Optional

from ..rules import Ruleset, load_ruleset
from ..rules.explain import RuleExplanation, describe, list_rules


def ruleset(root: Optional[str] = None) -> Ruleset:
    """The bundled ruleset, loaded and validated."""
    return load_ruleset(root) if root is not None else load_ruleset()


def all_rules(loaded: Optional[Ruleset] = None) -> tuple[RuleExplanation, ...]:
    """Every rule, described, in identity order."""
    return list_rules(loaded if loaded is not None else load_ruleset())


def rule(rule_id: str, loaded: Optional[Ruleset] = None) -> RuleExplanation:
    """Describe one rule. Raises `KeyError` if there is no such rule."""
    resolved = loaded if loaded is not None else load_ruleset()
    found = resolved.by_id(rule_id)
    if found is None:
        raise KeyError(f"no such rule: {rule_id}")
    return describe(found)
