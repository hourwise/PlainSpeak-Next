"""Verifying a transformation somebody else made.

`present` governs PlainSpeak's own edits: every change it makes is one of its
reviewed rules, located exactly and checked by the integrity firewall before it
happens. `verify` asks the same questions about a transformation that has
*already* happened — made by a person, a language model, an agent or any other
software — given only the text before and the text after.

### What it establishes, and what it does not

Verify does **not** decide whether two texts mean the same thing. Nothing
deterministic can. It decides whether the transformation preserved the
properties PlainSpeak's integrity model represents, and whether every
difference is one that model can account for:

    ACCEPTED       every protected item survived, in order, and every other
                   difference is accounted for: formatting, a reviewed
                   equivalence, one of PlainSpeak's own SAFE rules, or a
                   permitted move of a time or limit phrase within a sentence
    REFUSED        a protected item was lost, gained or changed — a number,
                   date, amount, unit, negation, modal, comparator, identifier,
                   term of art — or a region PlainSpeak never rewrites (code,
                   quotation, table, link destination, raw markup) changed
    INCONCLUSIVE   nothing protected was lost, but something changed that the
                   model cannot vouch for: reworded prose, protected items
                   moved relative to each other, structure it could not locate

Unknown is never collapsed into safe. A reworded sentence whose numbers all
survived is INCONCLUSIVE, not ACCEPTED, because "the numbers survived" is not
the same claim as "nothing that matters changed", and ACCEPTED must only ever
mean the second in the narrow sense above.

### How

Both texts are parsed into documents and projected into analysis text, the
same representation `present` reads. PlainSpeak's reviewed SAFE rules are then
applied to *both* sides (normalisation), so a change that is one of those rules
— in either direction — disappears from the comparison. What remains is
tokenised with every protected fact and protected term as a single, atomic
token and compared with a deterministic sequence alignment. Every difference
left over is either explained by the verification policy below or reported.

Nothing here is a second integrity engine. Facts come from
`plainspeak.integrity`, protected phrases from the ruleset, SAFE rules from the
planner; this module only compares what they report about two texts.

### The contract

`VerifyResult.as_dict()` is the public, versioned `plainspeak.verify.v1`
contract, under the same rules as `plainspeak.present.v1`: within one schema id
a field is never removed, renamed, or given a different type or meaning.
Everything in it is deterministic — no timestamps, no paths, no host details —
and its `receipt` is a canonical record whose SHA-256 identifies the decision.
The receipt is evidence, not a signature.
"""
from __future__ import annotations

import bisect
import difflib
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from .. import __version__
from ..document.model import (
    REASON_INHERITED,
    REASON_UNLOCATABLE,
    CodeBlock,
    CodeSpan,
    Document,
    HtmlBlock,
    Link,
    Node,
    Quote,
    RawInline,
    Table,
    ThematicBreak,
)
from ..integrity import (
    PROTECTED_TERMS,
    IntegrityFact,
    check as integrity_check,
    extract,
    snapshot,
)
from ..integrity.policy import POLICY_VERSION as INTEGRITY_POLICY_VERSION
from ..integrity.policy import policy_hash as integrity_policy_hash
from ..rules import MODE_PROTECTED, Ruleset, canonical_json, find_matches, load_ruleset
from .apply import ApplicationError, apply_plan
from .planner import build_plan
from .projection import BLOCK_SEPARATOR, Projection, project_document

#: The contract identifiers. Bump the trailing version for any change that is
#: not purely additive.
VERIFY_SCHEMA = "plainspeak.verify.v1"
RECEIPT_SCHEMA = "plainspeak.verify.receipt.v1"

#: The verification policy: what counts as accounted for. Versioned and hashed
#: like the integrity policy, because changing it changes which transformations
#: are accepted, and a receipt must say which rules it was decided under.
VERIFY_POLICY_VERSION = "2026.1"

ACCEPTED = "ACCEPTED"
REFUSED = "REFUSED"
INCONCLUSIVE = "INCONCLUSIVE"
RESULTS = (ACCEPTED, REFUSED, INCONCLUSIVE)

STATUS_OK = "ok"
STATUS_ERROR = "error"

#: Machine-readable error codes. Part of the contract. An error means nothing
#: was verified; it is never a result.
ERROR_EMPTY_INPUT = "empty_input"
ERROR_UNSUPPORTED_INPUT = "unsupported_input"
ERROR_UNREADABLE_INPUT = "unreadable_input"
ERROR_FORMAT_MISMATCH = "format_mismatch"

FORMAT_MARKDOWN = "markdown"
FORMAT_TEXT = "text"
VERIFIABLE_SUFFIXES = {".md": FORMAT_MARKDOWN, ".markdown": FORMAT_MARKDOWN, ".txt": FORMAT_TEXT}

# Refusal codes.
REFUSAL_FACT = "protected_fact_changed"
REFUSAL_TERM = "protected_term_changed"
REFUSAL_REGION = "protected_region_changed"

# Unresolved codes.
UNRESOLVED_WORDING = "unexplained_change"
UNRESOLVED_MOVED = "protected_item_moved"
UNRESOLVED_UNMATCHED = "protected_item_unmatched"
UNRESOLVED_UNLOCATABLE = "unlocatable_structure"
UNRESOLVED_NORMALISATION = "normalisation_unavailable"

# Accounted-for codes.
EQUIVALENCE_FACT = "fact_equivalence"
EQUIVALENCE_RULE = "safe_rule"
EQUIVALENCE_MOVE = "permitted_move"
EQUIVALENCE_FORMATTING = "formatting"

# ── The verification policy ────────────────────────────────────────────────

#: Fact kinds that are values a comparator can govern: "before 5pm",
#: "within 5 days", "at least £40".
VALUE_KINDS: tuple[str, ...] = (
    "currency", "date", "measurement", "number", "percentage", "time",
)

#: Tokens that end a sentence. Deliberately naive: an abbreviation's full stop
#: counts too, which only ever makes a move *less* likely to be permitted.
SENTENCE_BOUNDARIES: tuple[str, ...] = (".", "!", "?")

#: Punctuation that may appear or disappear around a moved phrase —
#: "Before 5pm, you must" against "you must … before 5pm".
MOVE_JOINERS: tuple[str, ...] = (",",)

#: At most this many ordinary words may sit between a comparator and the value
#: it governs for the two to move as one phrase ("before the 5 pm cut-off").
MAX_UNIT_GAP = 2

#: Tokenisation of analysis text. Whitespace is not a token, so reflowing lines
#: or changing line endings is never a difference; a blank line between blocks
#: is, because paragraphing can separate a condition from what it governs.
TOKEN_PATTERN = r"\n\n|\w+(?:['’]\w+)*|[^\w\s]"


def verify_policy_document() -> dict[str, Any]:
    """The verification policy as canonical data."""
    return {
        "canonical_form": 1,
        "verify_policy_version": VERIFY_POLICY_VERSION,
        "value_kinds": sorted(VALUE_KINDS),
        "sentence_boundaries": sorted(SENTENCE_BOUNDARIES),
        "move_joiners": sorted(MOVE_JOINERS),
        "max_unit_gap": MAX_UNIT_GAP,
        "token_pattern": TOKEN_PATTERN,
        "accounted_for": [
            "identical token streams (whitespace, line endings, inline markup)",
            "fact equivalence under the integrity policy",
            "PlainSpeak SAFE rules, applied to either side",
            "capitalisation of a sentence's first word",
            "paragraph breaks between sentences",
            "a comparator and the value it governs moved within one sentence",
        ],
    }


def verify_policy_hash() -> str:
    return hashlib.sha256(canonical_json(verify_policy_document()).encode("utf-8")).hexdigest()


_TOKEN_RE = re.compile(TOKEN_PATTERN)


# ── Errors ─────────────────────────────────────────────────────────────────


class VerifyError(ValueError):
    """Two inputs could not be verified. Carries a contract error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": VERIFY_SCHEMA,
            "status": STATUS_ERROR,
            "error": {"code": self.code, "message": self.message},
        }

    def to_json(self) -> str:
        return canonical_json(self.as_dict())


# ── One side of a comparison ───────────────────────────────────────────────


@dataclass(frozen=True)
class _Token:
    #: What alignment compares: ("F", kind, normalized) for a protected fact,
    #: ("T", term) for a protected term, ("W", lower-cased word), ("P", mark),
    #: ("B",) for a paragraph break.
    key: tuple
    surface: str
    #: Offsets in the document source, for reporting. The end is exclusive.
    source_start: int
    source_end: int
    fact_kind: str = ""
    #: Set for a token that came from a SAFE rule's replacement.
    rule_id: str = ""

    @property
    def is_protected(self) -> bool:
        return self.key[0] in ("F", "T")

    @property
    def is_boundary(self) -> bool:
        return self.key == ("B",) or (self.key[0] == "P" and self.key[1] in SENTENCE_BOUNDARIES)


@dataclass(frozen=True)
class _Region:
    """Something PlainSpeak never rewrites, as it appears in one document."""

    kind: str
    key: tuple
    excerpt: str
    source_start: int


@dataclass
class _Side:
    """Everything verification needs to know about one document."""

    document: Document
    view: Projection
    tokens: list[_Token]
    sentence_of: list[int]
    regions: list[_Region]
    applied_rules: list[tuple[str, str, str]]
    unlocatable: int
    normalised: bool
    normalisation_note: str = ""

    @property
    def source(self) -> str:
        return self.document.source

    def line(self, offset: int) -> int:
        return self.source.count("\n", 0, max(0, min(offset, len(self.source)))) + 1


def _prepare(document: Document, ruleset: Ruleset) -> _Side:
    view = project_document(document)
    plan = build_plan(document, ruleset, projection=view)
    accepted = [change for change in plan.accepted if change.source_span is not None]
    normalised, note = True, ""
    try:
        apply_plan(document, plan)
    except ApplicationError as error:
        # Normalisation is only ever a way of *explaining* differences. If the
        # plan cannot be applied, nothing is explained by it: fewer changes are
        # accounted for, never more.
        accepted, normalised, note = [], False, str(error)

    text, origin = _normalise(view.text, accepted)
    tokens = _tokenise(text, origin, view, ruleset)
    applied = sorted(
        (change.rule_id, change.original_text.lower(), change.replacement.lower())
        for change in accepted
    )
    return _Side(
        document=document,
        view=view,
        tokens=tokens,
        sentence_of=_sentences(tokens),
        regions=_regions(document),
        applied_rules=applied,
        unlocatable=sum(
            1 for node in document.walk() if node.untransformable_reason == REASON_UNLOCATABLE
        ),
        normalised=normalised,
        normalisation_note=note,
    )


def _normalise(text: str, accepted: Sequence) -> tuple[str, list[tuple[int, int, int, int, str]]]:
    """Apply SAFE replacements to the analysis text, remembering where from.

    Returns the normalised text and the replaced pieces as
    `(normalised start, normalised end, analysis start, analysis end, rule)`,
    so every normalised offset can be traced back to the original.
    """
    pieces: list[str] = []
    origin: list[tuple[int, int, int, int, str]] = []
    cursor = 0
    length = 0
    for change in sorted(accepted, key=lambda item: item.analysis_span.start):
        start, end = change.analysis_span.start, change.analysis_span.end
        if start < cursor:
            continue  # accepted changes never overlap; this is belt and braces
        pieces.append(text[cursor:start])
        length += start - cursor
        pieces.append(change.replacement)
        origin.append((length, length + len(change.replacement), start, end, change.rule_id))
        length += len(change.replacement)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), origin


def _to_analysis(offset: int, origin: Sequence[tuple[int, int, int, int, str]]) -> tuple[int, str]:
    """A normalised offset as an offset in the original analysis text."""
    shift = 0
    for n_start, n_end, a_start, a_end, rule in origin:
        if offset < n_start:
            break
        if offset < n_end:
            return a_start, rule
        shift = a_end - n_end
    return offset + shift, ""


class _SourceMap:
    """Analysis offsets to source offsets, as nearly as the projection allows.

    Used only to point a reader at a line. A synthetic separator maps to the
    start of the next real segment, a non-linear segment to its own start.
    """

    def __init__(self, view: Projection) -> None:
        self.segments = [segment for segment in view.segments if segment.source_span is not None]
        self.starts = [segment.analysis_span.start for segment in self.segments]

    def __call__(self, offset: int) -> int:
        if not self.segments:
            return 0
        index = bisect.bisect_right(self.starts, offset) - 1
        if index < 0:
            return self.segments[0].source_span.start
        segment = self.segments[index]
        span = segment.analysis_span
        if offset >= span.end:
            if index + 1 < len(self.segments):
                return self.segments[index + 1].source_span.start
            return segment.source_span.end
        if segment.linear:
            return segment.source_span.start + (offset - span.start)
        return segment.source_span.start


def _tokenise(text: str, origin, view: Projection, ruleset: Ruleset) -> list[_Token]:
    """Protected facts and phrases as single tokens, then everything else."""
    claimed: list[tuple[int, int, tuple, str, str]] = []
    for fact in extract(text):
        claimed.append((fact.start, fact.end, ("F", fact.kind, fact.normalized), fact.surface, fact.kind))
    taken = bytearray(len(text))
    for start, end, *_ in claimed:
        taken[start:end] = b"\x01" * (end - start)
    protected_rules = [rule for rule in ruleset.rules if rule.mode == MODE_PROTECTED]
    for match in find_matches(text, protected_rules):
        if any(taken[match.start:match.end]):
            continue
        phrase = " ".join(text[match.start:match.end].lower().split())
        claimed.append((match.start, match.end, ("T", phrase), text[match.start:match.end], "term"))
        taken[match.start:match.end] = b"\x01" * (match.end - match.start)

    for match in _TOKEN_RE.finditer(text):
        start, end = match.span()
        if any(taken[start:end]):
            continue
        surface = match.group(0)
        if surface == BLOCK_SEPARATOR:
            key = ("B",)
        elif surface[0].isalnum() or surface[0] == "_":
            lowered = surface.lower()
            if lowered in PROTECTED_TERMS:
                claimed.append((start, end, ("T", lowered), surface, "term"))
                continue
            key = ("W", lowered)
        else:
            key = ("P", surface)
        claimed.append((start, end, key, surface, ""))

    to_source = _SourceMap(view)
    tokens = []
    for start, end, key, surface, kind in sorted(claimed, key=lambda item: (item[0], item[1])):
        a_start, rule = _to_analysis(start, origin)
        a_end, _ = _to_analysis(max(start, end - 1), origin)
        s_start = to_source(a_start)
        s_end = max(s_start, to_source(a_end) + 1)
        tokens.append(_Token(key=key, surface=surface, source_start=s_start, source_end=s_end,
                             fact_kind=kind, rule_id=rule))
    return tokens


def _sentences(tokens: Sequence[_Token]) -> list[int]:
    """The sentence index of every token. A boundary belongs to the sentence it ends."""
    index, found = 0, []
    for token in tokens:
        found.append(index)
        if token.is_boundary:
            index += 1
    return found


def _sentence_initial(tokens: Sequence[_Token], position: int) -> bool:
    return position == 0 or tokens[position - 1].is_boundary


# ── Regions PlainSpeak never rewrites ─────────────────────────────────────

_REGION_KINDS = (
    (CodeBlock, "code"), (CodeSpan, "code"), (Quote, "quote"), (Table, "table"),
    (HtmlBlock, "markup"), (RawInline, "markup"),
)


def _regions(document: Document) -> list[_Region]:
    found: list[_Region] = []

    def visit(node: Node) -> None:
        if isinstance(node, ThematicBreak):
            return
        for kind_type, kind in _REGION_KINDS:
            if isinstance(node, kind_type):
                raw = node.span.text(document.source)
                found.append(_Region(kind, (kind,) + _region_key(kind, raw), _excerpt(raw),
                                     node.span.start))
                return
        if isinstance(node, Link):
            href = node.href or ""
            start = node.href_span.start if node.href_span is not None else node.span.start
            found.append(_Region("link destination", ("link", href), _excerpt(href), start))
        for child in node.children():
            visit(child)

    for block in document.blocks:
        visit(block)
    return found


def _region_key(kind: str, raw: str) -> tuple:
    """What must be identical for a region to count as unchanged.

    Code and markup keep every character but line endings: whitespace in code
    is meaning. Quotations and tables keep every word and mark, case included,
    but not their layout — rewrapping a quotation is not rewording it.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    if kind in ("code", "markup"):
        return (text.strip("\n"),)
    if kind == "quote":
        text = re.sub(r"(?m)^[ \t]*(?:>[ \t]?)+", "", text)
    if kind == "table":
        text = re.sub(r"-{3,}", "---", text)
    return tuple(_TOKEN_RE.findall(text))


def _excerpt(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


# ── The result ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VerifyResult:
    """The verdict on one before/after pair. `result` is the only field to act on."""

    result: str
    input_format: str
    before_text: str
    after_text: str
    identities: dict[str, Any]
    protected: dict[str, Any]
    equivalences: tuple[dict[str, Any], ...]
    refusals: tuple[dict[str, Any], ...]
    unresolved: tuple[dict[str, Any], ...]
    notes: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.result == ACCEPTED

    @property
    def before_sha256(self) -> str:
        return _sha256(self.before_text)

    @property
    def after_sha256(self) -> str:
        return _sha256(self.after_text)

    @property
    def identical(self) -> bool:
        return self.before_text == self.after_text

    @property
    def receipt(self) -> dict[str, Any]:
        """The canonical receipt: a payload and the SHA-256 that identifies it."""
        payload = {
            "schema": RECEIPT_SCHEMA,
            "plainspeak_version": __version__,
            "verify_policy": {
                "version": VERIFY_POLICY_VERSION,
                "sha256": verify_policy_hash(),
            },
            "engine": dict(self.identities),
            "input_format": self.input_format,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "result": self.result,
            "findings_sha256": _sha256(canonical_json(self._findings())),
        }
        return {"payload": payload, "sha256": _sha256(canonical_json(payload))}

    @property
    def receipt_id(self) -> str:
        return self.receipt["sha256"]

    def receipt_json(self) -> str:
        return canonical_json(self.receipt)

    def _findings(self) -> dict[str, Any]:
        return {
            "equivalences": list(self.equivalences),
            "refusals": list(self.refusals),
            "unresolved": list(self.unresolved),
            "protected": self.protected,
        }

    def as_dict(self) -> dict[str, Any]:
        """The `plainspeak.verify.v1` contract."""
        return {
            "schema": VERIFY_SCHEMA,
            "status": STATUS_OK,
            "result": self.result,
            "plainspeak_version": __version__,
            "verify_policy": {"version": VERIFY_POLICY_VERSION, "sha256": verify_policy_hash()},
            "engine": dict(self.identities),
            "input_format": self.input_format,
            "before": {"sha256": self.before_sha256, "characters": len(self.before_text)},
            "after": {"sha256": self.after_sha256, "characters": len(self.after_text)},
            "identical": self.identical,
            "counts": {
                "protected": self.protected["count"],
                "equivalences": len(self.equivalences),
                "refusals": len(self.refusals),
                "unresolved": len(self.unresolved),
            },
            "protected": self.protected,
            "equivalences": list(self.equivalences),
            "refusals": list(self.refusals),
            "unresolved": list(self.unresolved),
            "notes": list(self.notes),
            "receipt": self.receipt,
        }

    def to_json(self) -> str:
        return canonical_json(self.as_dict())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Entry points ───────────────────────────────────────────────────────────


def verify(before: Document, after: Document, ruleset: Optional[Ruleset] = None) -> VerifyResult:
    """Verify that `after` is an admissible transformation of `before`."""
    if before.source_format != after.source_format:
        raise VerifyError(
            ERROR_FORMAT_MISMATCH,
            f"before is {before.source_format} and after is {after.source_format}; "
            "verify compares two documents of one format",
        )
    if not before.source.strip():
        raise VerifyError(ERROR_EMPTY_INPUT, "the before text is empty; there is nothing to verify against")
    rules = ruleset if ruleset is not None else load_ruleset()
    return _Verification(before, after, rules).run()


def verify_text(
    before: str, after: str, markdown: bool = True, ruleset: Optional[Ruleset] = None
) -> VerifyResult:
    """Verify two texts an adapter already holds."""
    from .review import parse_source

    return verify(parse_source(before, markdown=markdown), parse_source(after, markdown=markdown), ruleset)


def verify_files(
    before_path: str | Path, after_path: str | Path, input_format: Optional[str] = None,
    ruleset: Optional[Ruleset] = None,
) -> VerifyResult:
    """Read two files and verify them, parsed as one format.

    The format is `input_format` when given, otherwise the before file's
    extension. Files are read as UTF-8 with their line endings intact, so the
    SHA-256 values in the result are the SHA-256 of the files themselves.
    """
    fmt = input_format or _format_of(before_path)
    return verify_text(_read(before_path), _read(after_path), markdown=fmt == FORMAT_MARKDOWN,
                       ruleset=ruleset)


def _format_of(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix not in VERIFIABLE_SUFFIXES:
        raise VerifyError(
            ERROR_UNSUPPORTED_INPUT,
            f"{Path(path).name}: verify reads plain text and Markdown (.txt, .md, .markdown)",
        )
    return VERIFIABLE_SUFFIXES[suffix]


def _read(path: str | Path) -> str:
    target = Path(path)
    _format_of(target)
    try:
        return target.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise VerifyError(ERROR_UNREADABLE_INPUT, f"cannot read {target.name}: {error}") from None


# ── The comparison ─────────────────────────────────────────────────────────


class _Verification:
    def __init__(self, before: Document, after: Document, ruleset: Ruleset) -> None:
        self.before_document = before
        self.after_document = after
        self.ruleset = ruleset
        self.equivalences: list[dict[str, Any]] = []
        self.refusals: list[dict[str, Any]] = []
        self.unresolved: list[dict[str, Any]] = []
        self.notes: list[str] = []

    def run(self) -> VerifyResult:
        before = _prepare(self.before_document, self.ruleset)
        after = _prepare(self.after_document, self.ruleset)
        source_before, source_after = before.source, after.source

        if source_before != source_after:
            self._check_facts(before, after)
            self._check_regions(before, after)
            self._check_terms(before, after)
            self._check_structure(before, after)
            if not self.refusals:
                self._align(before, after)
            if source_before != source_after and not (self.refusals or self.unresolved):
                self._note_formatting(before, after)
        else:
            self.notes.append("the two texts are identical")

        if self.refusals:
            result = REFUSED
        elif self.unresolved:
            result = INCONCLUSIVE
        else:
            result = ACCEPTED

        return VerifyResult(
            result=result,
            input_format=self.before_document.source_format,
            before_text=source_before,
            after_text=source_after,
            identities=_identities(self.ruleset),
            protected=_protected_summary(before, after),
            equivalences=tuple(self.equivalences),
            refusals=tuple(self.refusals),
            unresolved=tuple(self.unresolved),
            notes=tuple(self.notes),
        )

    # ── Refusals ──────────────────────────────────────────────────────────

    def _check_facts(self, before: _Side, after: _Side) -> None:
        """The V1 firewall, over the whole of both sources."""
        verdict = integrity_check(before.source, after.source)
        if verdict.passed:
            return
        facts_before, facts_after = snapshot(before.source), snapshot(after.source)
        lost = facts_before.signature - facts_after.signature
        gained = facts_after.signature - facts_before.signature
        for violation in verdict.violations:
            self.refusals.append({
                "code": REFUSAL_FACT,
                "kind": violation.kind,
                "before": list(violation.before),
                "after": list(violation.after),
                "detail": violation.detail,
                "before_lines": _lines(before, facts_before.facts, violation.kind, lost),
                "after_lines": _lines(after, facts_after.facts, violation.kind, gained),
            })

    def _check_regions(self, before: _Side, after: _Side) -> None:
        keys_b = [region.key for region in before.regions]
        keys_a = [region.key for region in after.regions]
        if keys_b == keys_a:
            return
        matcher = difflib.SequenceMatcher(None, keys_b, keys_a, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            removed, added = before.regions[i1:i2], after.regions[j1:j2]
            kinds = sorted({region.kind for region in removed + added})
            verb = {"replace": "changed", "delete": "removed", "insert": "added"}[tag]
            self.refusals.append({
                "code": REFUSAL_REGION,
                "kind": ", ".join(kinds),
                "before": [region.excerpt for region in removed],
                "after": [region.excerpt for region in added],
                "detail": f"{' and '.join(kinds)} {verb}: PlainSpeak never rewrites this, "
                          "so a transformation may not either",
                "before_lines": [before.line(region.source_start) for region in removed],
                "after_lines": [after.line(region.source_start) for region in added],
            })

    def _check_terms(self, before: _Side, after: _Side) -> None:
        terms_b = Counter(token.key[1] for token in before.tokens if token.key[0] == "T")
        terms_a = Counter(token.key[1] for token in after.tokens if token.key[0] == "T")
        lost, gained = terms_b - terms_a, terms_a - terms_b
        if not lost and not gained:
            return
        removed = sorted(lost.elements())
        added = sorted(gained.elements())
        if removed and added:
            detail = f"protected term changed: {', '.join(removed)} became {', '.join(added)}"
        elif removed:
            detail = f"protected term removed: {', '.join(removed)}"
        else:
            detail = f"protected term introduced: {', '.join(added)}"
        self.refusals.append({
            "code": REFUSAL_TERM,
            "kind": "term",
            "before": removed,
            "after": added,
            "detail": detail + " — a term of art is never substituted",
            "before_lines": sorted({before.line(t.source_start) for t in before.tokens
                                    if t.key[0] == "T" and t.key[1] in lost}),
            "after_lines": sorted({after.line(t.source_start) for t in after.tokens
                                   if t.key[0] == "T" and t.key[1] in gained}),
        })

    def _check_structure(self, before: _Side, after: _Side) -> None:
        for side, name in ((before, "before"), (after, "after")):
            if side.unlocatable:
                self.unresolved.append({
                    "code": UNRESOLVED_UNLOCATABLE,
                    "detail": f"the {name} text has {side.unlocatable} part(s) whose position the "
                              "parser could not establish exactly, so they cannot be compared",
                    "before": "", "after": "", "before_line": None, "after_line": None,
                })
            if not side.normalised:
                self.unresolved.append({
                    "code": UNRESOLVED_NORMALISATION,
                    "detail": f"PlainSpeak's SAFE rules could not be applied to the {name} text "
                              f"({side.normalisation_note}); no difference is explained by them",
                    "before": "", "after": "", "before_line": None, "after_line": None,
                })

    # ── Alignment ────────────────────────────────────────────────────────

    def _align(self, before: _Side, after: _Side) -> None:
        tb, ta = before.tokens, after.tokens
        facts_b = Counter(t.key for t in tb if t.key[0] == "F")
        facts_a = Counter(t.key for t in ta if t.key[0] == "F")
        if facts_b != facts_a:
            # The firewall passed over the whole source, yet the prose holds
            # different facts: something moved between prose and a region the
            # projection does not read. Not a proven loss; not accounted for.
            self.unresolved.append({
                "code": UNRESOLVED_UNMATCHED,
                "detail": "protected items could not be matched one-for-one between the two "
                          "texts' prose",
                "before": ", ".join(sorted(k[2] for k in (facts_b - facts_a).elements())),
                "after": ", ".join(sorted(k[2] for k in (facts_a - facts_b).elements())),
                "before_line": None, "after_line": None,
            })
            return

        matcher = difflib.SequenceMatcher(None, [t.key for t in tb], [t.key for t in ta],
                                          autojunk=False)
        opcodes = matcher.get_opcodes()
        moved_b, moved_a = self._moves(before, after, opcodes)

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                self._equal_region(before, after, i1, i2, j1)
                continue
            self._changed_region(before, after, i1, i2, j1, j2, moved_b, moved_a)

        self._record_rules(before, after)

    def _equal_region(self, before: _Side, after: _Side, i1: int, i2: int, j1: int) -> None:
        for offset in range(i2 - i1):
            tb, ta = before.tokens[i1 + offset], after.tokens[j1 + offset]
            if tb.surface == ta.surface:
                continue
            if tb.key[0] == "F":
                if tb.surface.lower() != ta.surface.lower():
                    self.equivalences.append({
                        "code": EQUIVALENCE_FACT,
                        "kind": tb.fact_kind,
                        "before": tb.surface,
                        "after": ta.surface,
                        "detail": f"the same {tb.fact_kind} under integrity policy "
                                  f"{INTEGRITY_POLICY_VERSION}",
                        "before_line": before.line(tb.source_start),
                        "after_line": after.line(ta.source_start),
                    })
                continue
            if tb.rule_id or ta.rule_id:
                continue  # a SAFE replacement's own casing
            if _sentence_initial(before.tokens, i1 + offset) or _sentence_initial(after.tokens, j1 + offset):
                continue  # capitalisation of a sentence's first word
            self.unresolved.append(self._unexplained(
                before, after, [tb], [ta], "capitalisation changed mid-sentence"))

    def _changed_region(self, before, after, i1, i2, j1, j2, moved_b, moved_a) -> None:
        removed = before.tokens[i1:i2]
        added = after.tokens[j1:j2]
        involved = any(i in moved_b for i in range(i1, i2)) or any(j in moved_a for j in range(j1, j2))
        residual_b = [t for i, t in zip(range(i1, i2), removed)
                      if i not in moved_b and not (involved and t.key == ("P", ",") )]
        residual_a = [t for j, t in zip(range(j1, j2), added)
                      if j not in moved_a and not (involved and t.key == ("P", ","))]
        if not residual_b and not residual_a:
            return  # wholly a permitted move, recorded by `_moves`
        if _only_paragraph_breaks(residual_b, residual_a) and _between_sentences(before, after, i1, i2, j1, j2):
            self.equivalences.append({
                "code": EQUIVALENCE_FORMATTING,
                "kind": "paragraph",
                "before": "", "after": "",
                "detail": "paragraph break added or removed between sentences",
                "before_line": before.line(before.tokens[min(i1, len(before.tokens) - 1)].source_start)
                if before.tokens else None,
                "after_line": after.line(after.tokens[min(j1, len(after.tokens) - 1)].source_start)
                if after.tokens else None,
            })
            return
        # Every protected item is on both sides by now, so one that sits in a
        # changed stretch has moved: the text around it is not where it was.
        protected = [t for t in residual_b + residual_a if t.is_protected]
        entry = self._unexplained(
            before, after, removed, added,
            "a protected item moved to a different place in the text, and the integrity "
            "model cannot establish that it still applies to the same thing" if protected else
            "wording changed in a way the integrity model cannot vouch for",
            anchor_b=i1, anchor_a=j1)
        if protected:
            entry["code"] = UNRESOLVED_MOVED
        self.unresolved.append(entry)

    def _unexplained(self, before, after, removed, added, detail, anchor_b=None, anchor_a=None) -> dict:
        return {
            "code": UNRESOLVED_WORDING,
            "detail": detail,
            "before": _snippet(before, removed),
            "after": _snippet(after, added),
            "before_line": _line_of(before, removed, anchor_b),
            "after_line": _line_of(after, added, anchor_a),
        }

    # ── Moves ────────────────────────────────────────────────────────────

    def _moves(self, before: _Side, after: _Side, opcodes) -> tuple[set[int], set[int]]:
        """Protected items that changed position, and whether that was permitted.

        Returns the token positions, in each text, of comparator phrases whose
        move is permitted. Everything else that moved is reported unresolved.
        """
        seq_b = [i for i, t in enumerate(before.tokens) if t.is_protected]
        seq_a = [j for j, t in enumerate(after.tokens) if t.is_protected]
        if [before.tokens[i].key for i in seq_b] == [after.tokens[j].key for j in seq_a]:
            return set(), set()

        units_b = _units(before)
        units_a = _units(after)
        # The skeleton: protected items that are not part of a movable unit.
        in_unit_b = {i for unit in units_b for i in unit}
        in_unit_a = {j for unit in units_a for j in unit}
        skeleton_b = [before.tokens[i].key for i in seq_b if i not in in_unit_b]
        skeleton_a = [after.tokens[j].key for j in seq_a if j not in in_unit_a]
        unit_keys_b = [tuple(before.tokens[i].key for i in unit) for unit in units_b]
        unit_keys_a = [tuple(after.tokens[j].key for j in unit) for unit in units_a]

        permitted = skeleton_b == skeleton_a and Counter(unit_keys_b) == Counter(unit_keys_a)
        anchors = _anchors(opcodes)
        pairs: list[tuple[list[int], list[int]]] = []
        if permitted:
            remaining = list(range(len(units_a)))
            for unit_b, key in zip(units_b, unit_keys_b):
                match = next((k for k in remaining if unit_keys_a[k] == key), None)
                if match is None:
                    permitted = False
                    break
                remaining.remove(match)
                unit_a = units_a[match]
                if not _same_sentence(before, after, unit_b[0], unit_a[0], anchors):
                    permitted = False
                    break
                pairs.append((unit_b, unit_a))

        if not permitted:
            moved_b = [before.tokens[i] for i in seq_b]
            moved_a = [after.tokens[j] for j in seq_a]
            self.unresolved.append({
                "code": UNRESOLVED_MOVED,
                "detail": "protected items appear in a different order; the integrity model "
                          "cannot establish that each still applies to the same thing",
                "before": " · ".join(t.surface for t in _out_of_order(moved_b, moved_a)),
                "after": " · ".join(t.surface for t in _out_of_order(moved_a, moved_b)),
                "before_line": _first_line(before, _out_of_order(moved_b, moved_a)),
                "after_line": _first_line(after, _out_of_order(moved_a, moved_b)),
            })
            return set(), set()

        moved_b, moved_a = set(), set()
        aligned = {i: j for tag, i1, i2, j1, j2 in opcodes if tag == "equal"
                   for i, j in zip(range(i1, i2), range(j1, j2))}
        for unit_b, unit_a in pairs:
            span_b = range(unit_b[0], unit_b[-1] + 1)
            span_a = range(unit_a[0], unit_a[-1] + 1)
            if all(aligned.get(i) == j for i, j in zip(span_b, span_a)):
                continue  # did not move
            moved_b.update(span_b)
            moved_a.update(span_a)
            self.equivalences.append({
                "code": EQUIVALENCE_MOVE,
                "kind": "comparator",
                "before": _snippet(before, [before.tokens[i] for i in span_b]),
                "after": _snippet(after, [after.tokens[j] for j in span_a]),
                "detail": "a comparator and the value it governs moved within one sentence",
                "before_line": before.line(before.tokens[unit_b[0]].source_start),
                "after_line": after.line(after.tokens[unit_a[0]].source_start),
            })
        return moved_b, moved_a

    def _record_rules(self, before: _Side, after: _Side) -> None:
        """SAFE rules that account for a difference, in either direction."""
        in_b = Counter(before.applied_rules)
        in_a = Counter(after.applied_rules)
        for (rule_id, original, replacement), count in sorted((in_b - in_a).items()):
            for _ in range(count):
                self.equivalences.append({
                    "code": EQUIVALENCE_RULE, "kind": rule_id,
                    "before": original, "after": replacement,
                    "detail": f"PlainSpeak SAFE rule {rule_id}",
                    "before_line": None, "after_line": None,
                })
        for (rule_id, original, replacement), count in sorted((in_a - in_b).items()):
            for _ in range(count):
                self.equivalences.append({
                    "code": EQUIVALENCE_RULE, "kind": rule_id,
                    "before": replacement, "after": original,
                    "detail": f"PlainSpeak SAFE rule {rule_id}, in reverse",
                    "before_line": None, "after_line": None,
                })

    def _note_formatting(self, before: _Side, after: _Side) -> None:
        if [t.key for t in before.tokens] == [t.key for t in after.tokens] and not self.equivalences:
            self.equivalences.append({
                "code": EQUIVALENCE_FORMATTING, "kind": "layout",
                "before": "", "after": "",
                "detail": "only whitespace, line endings, line breaks or inline markup differ",
                "before_line": None, "after_line": None,
            })


# ── Helpers ────────────────────────────────────────────────────────────────


def _units(side: _Side) -> list[list[int]]:
    """Comparator phrases that may move: a comparator and the value it governs.

    A comparator directly after a negation ("not before 5pm") never moves: the
    negation belongs to the phrase, and leaving it behind would reverse it.
    """
    tokens = side.tokens
    units = []
    for i, token in enumerate(tokens):
        if token.key[0] != "F" or token.fact_kind != "comparator":
            continue
        if i > 0 and tokens[i - 1].key[0] == "F" and tokens[i - 1].fact_kind == "negation":
            continue
        for gap in range(0, MAX_UNIT_GAP + 1):
            j = i + 1 + gap
            if j >= len(tokens) or tokens[j].is_boundary:
                break
            if tokens[j].is_protected:
                if tokens[j].key[0] == "F" and tokens[j].fact_kind in VALUE_KINDS \
                        and all(tokens[k].key[0] == "W" for k in range(i + 1, j)):
                    units.append(list(range(i, j + 1)))
                break
    return units


def _anchors(opcodes) -> list[tuple[int, int]]:
    return [(i, j) for tag, i1, i2, j1, j2 in opcodes if tag == "equal"
            for i, j in zip(range(i1, i2), range(j1, j2))]


def _same_sentence(before: _Side, after: _Side, i: int, j: int, anchors) -> bool:
    """Whether token `i` of before and `j` of after lie in corresponding sentences.

    Two sentences correspond when some aligned, unchanged token lies in both.
    """
    sentence_b = before.sentence_of[i]
    sentence_a = after.sentence_of[j]
    return any(
        before.sentence_of[x] == sentence_b and after.sentence_of[y] == sentence_a
        and not before.tokens[x].is_boundary
        for x, y in anchors
    )


def _out_of_order(sequence: Sequence[_Token], other: Sequence[_Token]) -> list[_Token]:
    """The protected items of `sequence` not in the common ordered core."""
    matcher = difflib.SequenceMatcher(None, [t.key for t in sequence], [t.key for t in other],
                                      autojunk=False)
    kept = {i for block in matcher.get_matching_blocks() for i in range(block.a, block.a + block.size)}
    return [token for i, token in enumerate(sequence) if i not in kept]


def _only_paragraph_breaks(removed: Sequence[_Token], added: Sequence[_Token]) -> bool:
    return bool(removed or added) and all(t.key == ("B",) for t in list(removed) + list(added))


def _between_sentences(before: _Side, after: _Side, i1, i2, j1, j2) -> bool:
    def ends_sentence(side: _Side, index: int) -> bool:
        return index <= 0 or side.tokens[index - 1].is_boundary

    return ends_sentence(before, i1) and ends_sentence(after, j1)


def _snippet(side: _Side, tokens: Sequence[_Token], limit: int = 200) -> str:
    # A paragraph break is synthetic and has no text of its own to show.
    tokens = [t for t in tokens if t.key != ("B",)]
    if not tokens:
        return ""
    start = min(t.source_start for t in tokens)
    end = max(t.source_end for t in tokens)
    return _excerpt(side.source[start:end], limit)


def _line_of(side: _Side, tokens: Sequence[_Token], anchor: Optional[int]) -> Optional[int]:
    tokens = [t for t in tokens if t.key != ("B",)]
    if tokens:
        return side.line(min(t.source_start for t in tokens))
    if anchor is not None and side.tokens:
        near = side.tokens[min(anchor, len(side.tokens) - 1)]
        return side.line(near.source_start)
    return None


def _first_line(side: _Side, tokens: Sequence[_Token]) -> Optional[int]:
    return side.line(tokens[0].source_start) if tokens else None


def _lines(side: _Side, facts: Sequence[IntegrityFact], kind: str, changed: Counter) -> list[int]:
    return sorted({side.line(fact.start) for fact in facts
                   if fact.kind == kind and changed.get(fact.identity)})


def _protected_summary(before: _Side, after: _Side) -> dict[str, Any]:
    facts = snapshot(before.source)
    terms = [t for t in before.tokens if t.key[0] == "T"]
    items = [
        {"kind": fact.kind, "surface": fact.surface, "normalized": fact.normalized,
         "before_line": before.line(fact.start)}
        for fact in facts.facts
    ] + [
        {"kind": "term", "surface": token.surface, "normalized": token.key[1],
         "before_line": before.line(token.source_start)}
        for token in terms
    ]
    return {
        "policy_version": facts.policy_version,
        "policy_sha256": facts.policy_hash,
        "count": len(items),
        "preserved": integrity_check(before.source, after.source).passed,
        "items": items,
    }


def _identities(ruleset: Ruleset) -> dict[str, Any]:
    return {
        "ruleset_version": ruleset.version,
        "ruleset_sha256": ruleset.hash,
        "integrity_version": INTEGRITY_POLICY_VERSION,
        "integrity_sha256": integrity_policy_hash(),
        "morphology_version": ruleset.morphology_version,
        "morphology_sha256": ruleset.morphology_hash,
    }


__all__ = [
    "ACCEPTED",
    "ERROR_EMPTY_INPUT",
    "ERROR_FORMAT_MISMATCH",
    "ERROR_UNREADABLE_INPUT",
    "ERROR_UNSUPPORTED_INPUT",
    "INCONCLUSIVE",
    "RECEIPT_SCHEMA",
    "REFUSED",
    "RESULTS",
    "VERIFY_POLICY_VERSION",
    "VERIFY_SCHEMA",
    "VerifyError",
    "VerifyResult",
    "verify",
    "verify_files",
    "verify_policy_document",
    "verify_policy_hash",
    "verify_text",
]
