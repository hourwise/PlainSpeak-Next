"""Safe changes may not make the document's style worse.

A safe fix is judged one span at a time: this word, that replacement, does the
firewall object. Style is a property of the whole document, and the two can
disagree. Three different rules each turn a heavy transition into "Also,", and
each is individually a fine simplification; applied together to a document
that used "Furthermore", "Moreover" and "Additionally" four times each, they
produce twelve sentences that begin with "Also" — the very repetition the style
layer exists to point out.

So after the firewall has had its say, the guard measures the document as the
accepted changes would leave it and compares it with the document as it is. If
no style diagnostic has become more severe, every change stands. If one has,
the changes are admitted rule by rule, in rule-identifier order, and a rule
whose changes would make any diagnostic worse is withheld and refused with the
diagnostic named. Nothing is rewritten differently; the guard only declines.

### Which judgement

The **baseline** style policy, not a profile. A safe fix is safe for every
reader, so whether it is applied cannot depend on which profile somebody chose;
profiles govern the suggestions that need review. The comparison is by severity
band — none, notice, strong — rather than by raw value, because a replacement
that shortens a sentence nudges every length statistic slightly, and refusing
fixes for movements no reader is told about would be noise.

### Cost

One extra measurement of the document in the common case, where nothing gets
worse. Only when something does is the document measured once more per rule.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import groupby
from typing import Optional, Sequence

from ..document import parse_markdown, parse_text
from ..document.model import Document
from ..style.analyze import interpret_baseline
from ..style.model import StyleObservations
from ..style.model import text_hash as measured_hash
from ..style.policy import STYLE_POLICY_VERSION, policy_hash
from .plan import ProposedChange
from .projection import Projection, project_document
from .styling import observe_style

REFUSAL_STYLE_REGRESSION = "applying this would make the document's style worse"

#: Severity bands in order. Absence of a finding ranks lowest.
_RANK = {"": 0, "info": 1, "notice": 2, "strong": 3}


@dataclass(frozen=True)
class StyleRegression:
    """One diagnostic that a set of changes would make more severe."""

    diagnostic: str
    before: str
    after: str

    def describe(self) -> str:
        return f"{self.diagnostic} {self.before or 'none'} -> {self.after}"


def style_policy_identity() -> tuple[str, str]:
    """The style policy a guarded plan was judged under."""
    return STYLE_POLICY_VERSION, policy_hash()


def guard_style(
    document: Document,
    accepted: Sequence[ProposedChange],
    projection: Optional[Projection] = None,
    observed: Optional[StyleObservations] = None,
) -> tuple[tuple[ProposedChange, ...], tuple[ProposedChange, ...]]:
    """Split accepted safe changes into those that stand and those withheld.

    Returns `(kept, withheld)`. Withheld changes are marked inapplicable, with a
    reason naming the diagnostic they would have made worse. Deterministic: the
    admission order is by rule identifier, and within a rule every occurrence
    is admitted or withheld together, so a document never ends up with some of
    one rule's replacements and not others for reasons nobody could explain.
    """
    locatable = [change for change in accepted if change.source_span is not None]
    if not locatable:
        return tuple(accepted), ()

    view = projection if projection is not None else project_document(document)
    if observed is not None and observed.document_hash != measured_hash(view.text):
        # A measurement of some other text would make the guard judge the wrong
        # document. Refused rather than silently re-measured, because a caller
        # passing one has a bug worth hearing about.
        raise ValueError("the style observations supplied are not of this document")
    source = observed if observed is not None else observe_style(document, view)
    baseline = _judged(source)

    if not _regressions(baseline, document, locatable):
        return tuple(accepted), ()

    kept: list[ProposedChange] = []
    withheld: list[ProposedChange] = []
    by_rule = sorted(locatable, key=lambda change: change.rule_id)
    for _rule_id, group in groupby(by_rule, key=lambda change: change.rule_id):
        members = list(group)
        worse = _regressions(baseline, document, kept + members)
        if worse:
            reason = f"{REFUSAL_STYLE_REGRESSION}: " + "; ".join(item.describe() for item in worse)
            withheld += [replace(change, applicable=False, reason=reason) for change in members]
        else:
            kept += members

    # Identity, not equality: two proposals can be equal field for field.
    withheld_ids = {id(change) for change in by_rule} - {id(change) for change in kept}
    stands = tuple(change for change in accepted if id(change) not in withheld_ids)
    return stands, tuple(withheld)


def _regressions(
    baseline: dict[str, str], document: Document, changes: Sequence[ProposedChange]
) -> list[StyleRegression]:
    candidate = _candidate(document, changes)
    after = _judged(observe_style(candidate, project_document(candidate)))
    return [
        StyleRegression(diagnostic=key, before=baseline.get(key, ""), after=severity)
        for key, severity in sorted(after.items())
        if _RANK[severity] > _RANK[baseline.get(key, "")]
    ]


def _judged(observed: StyleObservations) -> dict[str, str]:
    """Diagnostic id -> severity, under the baseline policy."""
    return {finding.id: finding.severity for finding in interpret_baseline(observed).findings}


def _candidate(document: Document, changes: Sequence[ProposedChange]) -> Document:
    """The document as these changes would leave it, parsed the same way."""
    text = document.serialise([(change.source_span, change.replacement) for change in changes])
    parser = parse_markdown if document.source_format == "markdown" else parse_text
    return parser.parse(text)
