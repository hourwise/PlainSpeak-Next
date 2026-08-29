"""Turning rule matches into an immutable transformation plan.

This is where the rule engine and the document meet, and the order of
operations is the whole design:

    project the document once
        ↓
    run every rule against that one projection
        ↓
    collect every match — changing nothing
        ↓
    map each match to source, through the Phase 3.5 projection
        ↓
    apply protection: declarative rules, then the inherited register
        ↓
    resolve conflicts
        ↓
    freeze the plan

No edit is applied while matching. That is a hard invariant, not a performance
choice: if a rule saw text that an earlier rule had already changed, the result
would depend on which order the rules happened to run in, and the whole claim
to determinism would be gone. Every rule sees the same original projection.

Protection is checked twice, deliberately. Declarative `protected` rules cover
phrases this ruleset knows about; the inherited register in
`plainspeak.integrity.protected` covers terms the project has treated as
untouchable since before rules existed. Neither can weaken the other, and a
proposal has to survive both.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, replace
from typing import Iterable, Optional, Sequence

from .. import __version__ as ENGINE_VERSION
from ..document.model import Document, Span
from ..integrity import Violation, check as integrity_check
from ..integrity.policy import POLICY_VERSION as INTEGRITY_POLICY_VERSION
from ..integrity.policy import policy_hash as integrity_policy_hash
from ..integrity.protected import get_protected_domain, is_protected_term
from ..rules import (
    MODE_DIAGNOSTIC,
    MODE_PROTECTED,
    MODE_SAFE_FIX,
    Rule,
    RuleMatch,
    Ruleset,
    deletion_span,
    find_matches,
    load_ruleset,
    sha256_text,
)
from .plan import ProposedChange, propose_change
from .projection import Projection, project_document

#: Why a proposal was refused at the planning stage, after the projection has
#: already had its say.
REFUSAL_DECLARED_PROTECTED = "a protected rule covers this text"
REFUSAL_INHERITED_PROTECTED = "the text contains a protected term of art"
REFUSAL_CONFLICT = "two rules propose different changes here and neither takes precedence"
REFUSAL_SUPERSEDED_PRIORITY = "a higher-priority rule covers this text"
REFUSAL_SUPERSEDED_LONGER = "a longer match covers this text"
REFUSAL_DUPLICATE = "an identical change was already proposed"
REFUSAL_OUT_OF_SCOPE = "the match is outside the scopes this rule declares"
REFUSAL_DIAGNOSTIC = "this rule reports only and never proposes an edit"
REFUSAL_INTEGRITY = "the change would alter protected information"


@dataclass(frozen=True)
class IntegrityRefusal:
    """A proposal the integrity firewall vetoed, and what it found.

    Recorded separately from the refusal reason on the proposal itself so
    that an audit can say *which* protected category moved and in which
    direction. "Refused for integrity" is not something a reader can act on;
    "modal: must became may" is.
    """

    rule_id: str
    rule_version: int
    #: Where the vetoed proposal sat, so an audit entry can be matched to its
    #: refusal without relying on the rule ID being unique within a document.
    analysis_start: int
    analysis_end: int
    #: Which comparison caught it — see `_integrity_preflight`.
    scope: str
    summary: str
    violations: tuple[Violation, ...]


@dataclass(frozen=True)
class Conflict:
    """A recorded overlap between proposals, and how it was settled."""

    kind: str
    reason: str
    source_start: int
    source_end: int
    rule_ids: tuple[str, ...]
    winner: str = ""


@dataclass(frozen=True)
class TransformationPlan:
    """Everything one run of the rule engine decided, frozen.

    A plan answers, without re-running anything: which rules ran, against which
    document, what they proposed, which proposals may be applied, and why the
    rest may not. It is bound to the document by `input_hash` and to the rules
    by `ruleset_hash`, so applying it to anything else is detectable rather
    than merely unwise.
    """

    engine_version: str
    ruleset_version: str
    ruleset_hash: str
    #: The integrity policy that authorised this plan. Application checks it:
    #: applying a plan approved under one safety policy while running another
    #: would mean applying edits nobody actually checked.
    integrity_policy_version: str
    integrity_policy_hash: str
    input_hash: str
    projection_hash: str
    #: Every safe-fix candidate, whether or not it survived.
    proposals: tuple[ProposedChange, ...]
    #: Those that may be applied. Always a subset of `proposals`.
    accepted: tuple[ProposedChange, ...]
    #: Those that may not, each carrying its reason.
    refused: tuple[ProposedChange, ...]
    #: Findings from rules that report and never edit.
    diagnostics: tuple[ProposedChange, ...]
    #: Overlaps and how each was settled.
    conflicts: tuple[Conflict, ...]
    #: Proposals the firewall vetoed after conflict resolution had chosen them.
    integrity_refusals: tuple[IntegrityRefusal, ...] = ()

    @property
    def rule_ids(self) -> tuple[str, ...]:
        seen = []
        for change in self.proposals + self.diagnostics:
            if change.rule_id not in seen:
                seen.append(change.rule_id)
        return tuple(sorted(seen))

    def is_for(self, document: Document) -> bool:
        """Whether this plan was built against the given document."""
        return self.input_hash == document.source_hash


def build_plan(
    document: Document,
    ruleset: Optional[Ruleset] = None,
    projection: Optional[Projection] = None,
) -> TransformationPlan:
    """Run a ruleset against a document and return an immutable plan."""
    rules = ruleset if ruleset is not None else load_ruleset()
    view = projection if projection is not None else project_document(document)

    matches = find_matches(view.text, rules.rules)
    by_id = {rule.id: rule for rule in rules.rules}

    index = _SegmentIndex(view)
    in_scope = [match for match in matches if _in_scope(index, match, by_id[match.rule_id])]

    protected_regions = _protected_regions(view, document, in_scope, by_id)
    diagnostics = tuple(
        _record(view, document, match, by_id[match.rule_id], REFUSAL_DIAGNOSTIC)
        for match in in_scope
        if match.mode == MODE_DIAGNOSTIC
    )

    proposals = []
    for match in in_scope:
        if match.mode != MODE_SAFE_FIX:
            continue
        proposals.append(_propose(view, document, match, by_id[match.rule_id], protected_regions))

    accepted, refused, conflicts = _resolve(tuple(proposals), _priority_lookup(rules))

    # The firewall runs last, on what conflict resolution actually chose.
    # Running it earlier would let a vetoed proposal's loser take its place,
    # which would be a second, implicit conflict-resolution path — see
    # `_integrity_preflight`.
    accepted, vetoed, integrity_refusals = _integrity_preflight(view, index, accepted)
    refused = tuple(sorted(refused + vetoed, key=_order))

    return TransformationPlan(
        engine_version=ENGINE_VERSION,
        ruleset_version=rules.version,
        ruleset_hash=rules.hash,
        integrity_policy_version=INTEGRITY_POLICY_VERSION,
        integrity_policy_hash=integrity_policy_hash(),
        input_hash=document.source_hash,
        projection_hash=sha256_text(view.text),
        proposals=tuple(proposals),
        accepted=accepted,
        refused=refused,
        diagnostics=diagnostics,
        conflicts=conflicts,
        integrity_refusals=integrity_refusals,
    )


# ── The integrity firewall ─────────────────────────────────────────────────


def _integrity_preflight(
    view: Projection, index: "_SegmentIndex", accepted: tuple[ProposedChange, ...]
) -> tuple[tuple[ProposedChange, ...], tuple[ProposedChange, ...], tuple[IntegrityRefusal, ...]]:
    """Veto any accepted proposal that would alter protected information.

    Two comparisons, both bounded:

    **proposal-local** — the text being replaced against its replacement. Catches
    the direct cases: a dose, a percentage, a modal verb, a currency symbol.

    **context-local** — the enclosing block, before and after the substitution.
    Catches what a span-only view cannot: a deletion adjacent to a negation
    changes the sentence without the negation itself lying inside the span.

    A third, **document-global** check runs at application time over the complete
    candidate output; see `plainspeak.pipeline.apply`.

    Crucially this runs *after* conflict resolution, on the proposal that
    resolution chose. If a vetoed proposal's losing rival were reinstated here,
    the engine would have two paths to deciding an overlap and the result would
    depend on which safety check happened to fire. A conflict group whose winner
    fails integrity produces no automatic edit at all.
    """
    survivors: list[ProposedChange] = []
    vetoed: list[ProposedChange] = []
    records: list[IntegrityRefusal] = []

    for change in accepted:
        verdict = integrity_check(change.original_text, change.replacement)
        scope = "proposal"

        if verdict.passed:
            before, after = _context_pair(view, index, change)
            if before is not None:
                verdict = integrity_check(before, after)
                scope = "context"

        if verdict.passed:
            survivors.append(change)
            continue

        vetoed.append(
            replace(change, applicable=False, reason=f"{REFUSAL_INTEGRITY}: {verdict.summary}")
        )
        records.append(
            IntegrityRefusal(
                rule_id=change.rule_id,
                rule_version=change.rule_version,
                analysis_start=change.analysis_span.start,
                analysis_end=change.analysis_span.end,
                scope=scope,
                summary=verdict.summary,
                violations=verdict.violations,
            )
        )

    records.sort(key=lambda item: (item.analysis_start, item.analysis_end, item.rule_id))
    return tuple(survivors), tuple(vetoed), tuple(records)


def _context_pair(
    view: Projection, index: "_SegmentIndex", change: ProposedChange
) -> tuple[Optional[str], str]:
    """The enclosing block's text, before and after this one substitution.

    Bounded to the block rather than the document: a block is the largest unit a
    single edit can affect the reading of, and scanning the whole document once
    per proposal would make planning quadratic in a long report for no extra
    safety — the whole-document check at application time covers the rest.
    """
    block_path = _block_of(index, change)
    bounds = index.block_range(block_path)
    if bounds is None:
        return None, ""

    start, end = bounds
    span = change.analysis_span
    if not (start <= span.start and span.end <= end):
        return None, ""

    before = view.text[start:end]
    after = view.text[start : span.start] + change.replacement + view.text[span.end : end]
    return before, after


def _block_of(index: "_SegmentIndex", change: ProposedChange) -> tuple[int, ...]:
    touched = index.touching(change.analysis_span.start, change.analysis_span.start + 1)
    return touched[0].block_path if touched else change.document_path


# ── Locating segments ──────────────────────────────────────────────────────


class _SegmentIndex:
    """A read-only index over a projection's segments.

    Both scope filtering and the context check need "which segments does this
    range touch?", and answering it by scanning every segment made planning
    quadratic: with 214 rules over a 34,000-word document the match count and
    the segment count both grow with the text, and the product took a hundred
    seconds.

    Segments tile the projection in order, so the ones a range touches form a
    contiguous run and a binary search finds it. The index is built once per
    plan and changes no semantics — a test asserts it agrees with the scan it
    replaces.
    """

    __slots__ = ("segments", "_starts", "_blocks")

    def __init__(self, view: Projection) -> None:
        self.segments = view.segments
        self._starts = [segment.analysis_span.start for segment in view.segments]

        blocks: dict[tuple[int, ...], list[int]] = {}
        for segment in view.segments:
            if segment.synthetic:
                continue
            span = blocks.get(segment.block_path)
            if span is None:
                blocks[segment.block_path] = [
                    segment.analysis_span.start,
                    segment.analysis_span.end,
                ]
            else:
                span[0] = min(span[0], segment.analysis_span.start)
                span[1] = max(span[1], segment.analysis_span.end)
        self._blocks = {path: (low, high) for path, (low, high) in blocks.items()}

    def touching(self, start: int, end: int) -> list:
        """Every segment overlapping `[start, end)`, in document order."""
        if end <= start or not self.segments:
            return []
        first = max(bisect.bisect_right(self._starts, start) - 1, 0)
        touched = []
        for segment in self.segments[first:]:
            if segment.analysis_span.start >= end:
                break
            if segment.analysis_span.end > start:
                touched.append(segment)
        return touched

    def block_range(self, path: tuple[int, ...]):
        """The analysis range covered by one block, or `None`."""
        return self._blocks.get(path)


def _in_scope(index: "_SegmentIndex", match: RuleMatch, rule: Rule) -> bool:
    """Whether a match sits somewhere the rule says it applies.

    A match that crosses a block boundary is dropped outright. The separator
    between blocks is not in the document, so a "phrase" spanning it is an
    artefact of how the projection was assembled rather than something an
    author wrote.
    """
    touched = index.touching(match.start, match.end)
    if not touched or any(segment.synthetic for segment in touched):
        return False

    scopes = {name for segment in touched for name in segment.scopes}
    if not scopes & set(rule.scope.include):
        return False
    if scopes & set(rule.scope.exclude):
        return False
    return True


# ── Protection ─────────────────────────────────────────────────────────────


def _protected_regions(
    view: Projection,
    document: Document,
    matches: Sequence[RuleMatch],
    by_id: dict[str, Rule],
) -> tuple[Span, ...]:
    """Source ranges that declarative `protected` rules have claimed.

    Computed before any proposal is judged, so that protection never depends on
    which rule was considered first.
    """
    regions = []
    for match in matches:
        if match.mode != MODE_PROTECTED:
            continue
        mapping = view.map_to_source(Span(match.start, match.end))
        for span in mapping.source_spans:
            regions.append(span)
    return tuple(sorted(set(regions), key=lambda span: (span.start, span.end)))


def _inherited_protection(text: str) -> str:
    """The inherited register's verdict on the words inside a proposed edit.

    Any protected term anywhere in the span is disqualifying, not just the head
    word. Replacing "the material fact" as a unit would change "material" just
    as surely as replacing the word on its own.
    """
    for word in _words(text):
        if is_protected_term(word):
            domain = get_protected_domain(word)
            return f"{REFUSAL_INHERITED_PROTECTED}: '{word}'" + (f" ({domain})" if domain else "")
    return ""


def _words(text: str) -> list[str]:
    word = []
    words = []
    for character in text:
        if character.isalpha() or character in "'-":
            word.append(character)
        elif word:
            words.append("".join(word))
            word = []
    if word:
        words.append("".join(word))
    return words


# ── Building one proposal ──────────────────────────────────────────────────


def _propose(
    view: Projection,
    document: Document,
    match: RuleMatch,
    rule: Rule,
    protected_regions: Sequence[Span],
) -> ProposedChange:
    start, end = deletion_span(view.text, rule, match)
    change = propose_change(
        view,
        document,
        Span(start, end),
        replacement=match.replacement,
        rule_id=match.rule_id,
        rule_version=match.rule_version,
        mode=match.mode,
    )

    # The matcher's own refusal — a casing it cannot reproduce, a deletion that
    # would break spacing — outranks anything found later, because it means the
    # rule never had a well-defined edit to offer.
    if match.refusal:
        return replace(change, applicable=False, reason=match.refusal)

    if not change.applicable:
        return change

    span = change.source_span
    if span is not None and any(span.overlaps(region) for region in protected_regions):
        return replace(change, applicable=False, reason=REFUSAL_DECLARED_PROTECTED)

    inherited = _inherited_protection(change.original_text)
    if inherited:
        return replace(change, applicable=False, reason=inherited)

    return change


def _record(
    view: Projection, document: Document, match: RuleMatch, rule: Rule, reason: str
) -> ProposedChange:
    """A finding that proposes nothing, recorded in the same contract."""
    change = propose_change(
        view,
        document,
        Span(match.start, match.end),
        replacement="",
        rule_id=match.rule_id,
        rule_version=match.rule_version,
        mode=match.mode,
    )
    return replace(change, applicable=False, reason=change.reason or reason)


# ── Conflict resolution ────────────────────────────────────────────────────


def _resolve(
    proposals: tuple[ProposedChange, ...],
    priorities: dict[tuple[str, int], int],
) -> tuple[tuple[ProposedChange, ...], tuple[ProposedChange, ...], tuple[Conflict, ...]]:
    """Decide which overlapping proposals may be applied.

    The algorithm is a short cascade, and every branch is total — there is no
    "otherwise, whichever came first". Proposals that overlap are gathered into
    groups, and each group is settled independently:

    1.  One proposal in the group      → accept it.
    2.  All identical (same span, same replacement)
                                       → accept the lowest rule ID, the rest
                                         are duplicates.
    3.  Exactly one has the strictly highest priority
                                       → accept it; the rest are superseded.
    4.  Exactly one strictly contains all the others
                                       → accept it; the rest are superseded by
                                         the longer match.
    5.  Anything else                  → refuse the whole group.

    Step 5 is the important one. When two rules want to change the same text in
    different ways and neither has been given precedence, there is no principled
    answer, and picking one would make the output depend on an accident. Refusing
    both leaves the document unchanged and the reader informed, which is the
    right trade every time.
    """
    applicable = [change for change in proposals if change.applicable]
    already_refused = [change for change in proposals if not change.applicable]

    accepted: list[ProposedChange] = []
    refused: list[ProposedChange] = list(already_refused)
    conflicts: list[Conflict] = []

    for group in _overlap_groups(applicable):
        winner, losers, conflict = _settle(group, priorities)
        if winner is not None:
            accepted.append(winner)
        refused.extend(losers)
        if conflict is not None:
            conflicts.append(conflict)

    accepted.sort(key=_order)
    refused.sort(key=_order)
    conflicts.sort(key=lambda item: (item.source_start, item.source_end, item.rule_ids))
    return tuple(accepted), tuple(refused), tuple(conflicts)


def _order(change: ProposedChange) -> tuple:
    """A total order that does not depend on how anything was iterated."""
    span = change.source_span
    start = span.start if span else -1
    end = span.end if span else -1
    return (start, end, change.rule_id, change.rule_version, change.analysis_span.start)


def _overlap_groups(proposals: Sequence[ProposedChange]) -> list[list[ProposedChange]]:
    """Partition proposals into maximal transitively-overlapping groups."""
    ordered = sorted(proposals, key=_order)
    groups: list[list[ProposedChange]] = []
    current: list[ProposedChange] = []
    reach = -1

    for change in ordered:
        span = change.source_span
        assert span is not None  # applicable proposals always have one
        if current and span.start < reach:
            current.append(change)
            reach = max(reach, span.end)
            continue
        if current:
            groups.append(current)
        current = [change]
        reach = span.end

    if current:
        groups.append(current)
    return groups


def _settle(
    group: list[ProposedChange],
    priorities: dict[tuple[str, int], int],
) -> tuple[Optional[ProposedChange], list[ProposedChange], Optional[Conflict]]:
    """Settle one group of overlapping proposals. See `_resolve` for the cascade."""

    def priority_of(change: ProposedChange) -> int:
        return priorities.get((change.rule_id, change.rule_version), 0)

    if len(group) == 1:
        return group[0], [], None

    spans = [change.source_span for change in group]
    start = min(span.start for span in spans)
    end = max(span.end for span in spans)
    ids = tuple(sorted({change.rule_id for change in group}))

    ordered = sorted(group, key=lambda change: (change.rule_id, change.rule_version))

    # 2. Identical proposals from different rules.
    first = ordered[0]
    if all(
        change.source_span == first.source_span and change.replacement == first.replacement
        for change in ordered
    ):
        losers = [replace(c, applicable=False, reason=REFUSAL_DUPLICATE) for c in ordered[1:]]
        return first, losers, Conflict(
            kind="duplicate",
            reason=REFUSAL_DUPLICATE,
            source_start=start,
            source_end=end,
            rule_ids=ids,
            winner=first.rule_id,
        )

    # 3. A single strictly highest priority.
    ranked = sorted((priority_of(change) for change in group), reverse=True)
    if ranked[0] > ranked[1]:
        winner = max(ordered, key=lambda change: (priority_of(change), change.rule_id))
        losers = [
            replace(c, applicable=False, reason=REFUSAL_SUPERSEDED_PRIORITY)
            for c in ordered
            if c is not winner
        ]
        return winner, losers, Conflict(
            kind="superseded-by-priority",
            reason=REFUSAL_SUPERSEDED_PRIORITY,
            source_start=start,
            source_end=end,
            rule_ids=ids,
            winner=winner.rule_id,
        )

    # 4. One proposal strictly containing every other.
    for candidate in ordered:
        span = candidate.source_span
        others = [c for c in ordered if c is not candidate]
        if all(span.contains(other.source_span) for other in others) and all(
            len(span) > len(other.source_span) for other in others
        ):
            losers = [
                replace(c, applicable=False, reason=REFUSAL_SUPERSEDED_LONGER) for c in others
            ]
            return candidate, losers, Conflict(
                kind="superseded-by-longer-match",
                reason=REFUSAL_SUPERSEDED_LONGER,
                source_start=start,
                source_end=end,
                rule_ids=ids,
                winner=candidate.rule_id,
            )

    # 5. No principled winner: refuse the group.
    losers = [replace(c, applicable=False, reason=REFUSAL_CONFLICT) for c in ordered]
    return None, losers, Conflict(
        kind="unresolved",
        reason=REFUSAL_CONFLICT,
        source_start=start,
        source_end=end,
        rule_ids=ids,
    )


def _priority_lookup(ruleset: Ruleset) -> dict[tuple[str, int], int]:
    """Rule priorities, keyed by audit identity.

    Built per plan rather than cached on the module. A shared cache would make
    the result of resolving a conflict depend on which rulesets had been loaded
    earlier in the process, which is precisely the kind of hidden order
    dependency this phase exists to eliminate.
    """
    return {(rule.id, rule.version): rule.priority for rule in ruleset.rules}
