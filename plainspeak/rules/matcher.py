"""Finding rule matches in analysis text.

This module sees a string and nothing else. It does not know what a document
is, where the string came from, or which characters of any source it
corresponds to — and that is the point. Every offset it produces is an *analysis*
offset, and turning one into a source offset is the pipeline's job, done through
the Phase 3.5 projection with all of that machinery's refusals intact.

A rule that computed source offsets itself would be a rule that could put an
edit in the wrong place, and no amount of care elsewhere would catch it.

Matching is deterministic in the strong sense: the same text and the same rules
produce the same matches in the same order, whatever order the rules were
loaded in. Matches are sorted by position, then by descending length, then by
rule identity — never by anything that depends on iteration order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from .schema import (
    ACTION_DELETE,
    ACTION_REPLACE,
    CASE_EXACT,
    CASE_INSENSITIVE,
    CASE_PRESERVE,
    MATCH_PHRASE,
    MATCH_REGEX,
    MATCH_WORD,
    Rule,
)

#: Why a match cannot become a proposed edit. These are the matcher's own
#: refusals — the ones that depend only on the text, before the pipeline has
#: had a chance to add its own.
REFUSAL_CASE_UNMAPPABLE = "the matched text's capitalisation has no mechanical equivalent"
REFUSAL_CASE_EXACT = "the rule requires the exact casing it declares"
REFUSAL_RECAPITALIZE = "deleting this would leave a sentence starting in lower case"
REFUSAL_SPACING = "deleting this would leave invalid spacing or punctuation"

#: Characters that end a sentence. Used only to decide whether a deletion sits
#: at the start of one.
SENTENCE_ENDINGS = ".!?"


@dataclass(frozen=True)
class RuleMatch:
    """One rule firing at one place in the analysis text.

    `replacement` is what the rule proposes for `[start, end)`, already adjusted
    for the casing of the text it found. It is empty for a diagnostic, and for
    a protected match, neither of which propose anything.

    `refusal` is non-empty when the rule matched but cannot safely propose the
    edit it would like to. Such a match is still reported — it is a real
    finding — but it can never become an accepted change.
    """

    rule_id: str
    rule_version: int
    mode: str
    priority: int
    reason: str
    #: Half-open range within the analysis text.
    start: int
    end: int
    matched_text: str
    replacement: str = ""
    refusal: str = ""

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def sort_key(self) -> tuple:
        """Total order over matches, independent of how rules were loaded."""
        return (self.start, -self.length, self.rule_id, self.rule_version)


def find_matches(text: str, rules: Iterable[Rule]) -> tuple[RuleMatch, ...]:
    """Every match of every rule, in a deterministic order.

    Nothing is applied and nothing is filtered by structure here. Rules all see
    the same unmodified text, which is what stops one rule's output becoming
    another rule's input.
    """
    matches: list[RuleMatch] = []
    for rule in rules:
        matches.extend(_matches_for(text, rule))
    return tuple(sorted(matches, key=lambda match: match.sort_key))


def _matches_for(text: str, rule: Rule) -> list[RuleMatch]:
    if rule.match.type == MATCH_REGEX:
        spans = [(start, end, "") for start, end in _regex_spans(text, rule)]
    else:
        spans = _literal_spans(text, rule)

    found = []
    for start, end, form_replacement in spans:
        matched = text[start:end]
        replacement, refusal = _resolve_edit(
            text, rule, start, end, matched, form_replacement
        )
        found.append(
            RuleMatch(
                rule_id=rule.id,
                rule_version=rule.version,
                mode=rule.mode,
                priority=rule.priority,
                reason=rule.reason,
                start=start,
                end=end,
                matched_text=matched,
                replacement=replacement,
                refusal=refusal,
            )
        )
    return found


# ── Locating text ──────────────────────────────────────────────────────────


def _literal_spans(text: str, rule: Rule) -> list[tuple[int, int, str]]:
    """Find every occurrence of a rule's literal forms, with its replacement.

    Word boundaries are always enforced at an edge that is a letter or digit,
    for both phrase and word matches. Without that a rule for `utilise` would
    rewrite the middle of `utiliser`, and a rule for `in order to` would fire
    inside `join order token`.

    An inflected rule carries a different replacement for each surface —
    `utilised` becomes `used`, not `use` — so the pair travels with the span.
    """
    flags = re.IGNORECASE if rule.match.case == CASE_INSENSITIVE else 0
    found: dict[tuple[int, int], str] = {}

    if rule.match.inflections:
        candidates = rule.match.inflections
    else:
        candidates = tuple((literal, "") for literal in rule.match.literals)

    for literal, form_replacement in candidates:
        pattern = _bounded_pattern(literal)
        for hit in re.finditer(pattern, text, flags):
            key = (hit.start(), hit.end())
            # Two forms of one rule can find the same characters. Keeping the
            # first keeps a rule from conflicting with itself.
            if key not in found:
                found[key] = form_replacement

    return [(start, end, value) for (start, end), value in sorted(found.items())]


def _bounded_pattern(literal: str) -> str:
    """A literal with word boundaries asserted only where they mean something.

    `\\b` before a leading space would never match, so the boundary is applied
    only when the adjacent character is one a word boundary is defined against.
    """
    escaped = re.escape(literal)
    prefix = r"\b" if literal[:1].isalnum() else ""
    suffix = r"\b" if literal[-1:].isalnum() else ""
    return prefix + escaped + suffix


def _regex_spans(text: str, rule: Rule) -> list[tuple[int, int]]:
    flags = re.IGNORECASE if rule.match.case == CASE_INSENSITIVE else 0
    compiled = re.compile(rule.match.pattern, flags)
    return [
        (found.start(), found.end())
        for found in compiled.finditer(text)
        if found.end() > found.start()
    ]


# ── Deciding what to propose ───────────────────────────────────────────────


def _resolve_edit(
    text: str, rule: Rule, start: int, end: int, matched: str, form_replacement: str = ""
) -> tuple[str, str]:
    """Work out the replacement for one match, or why there cannot be one."""
    if rule.action.type == ACTION_REPLACE:
        return _cased_replacement(rule, matched, form_replacement)
    if rule.action.type == ACTION_DELETE:
        return _deletion(text, rule, start, end, matched)
    return "", ""


def _cased_replacement(
    rule: Rule, matched: str, form_replacement: str = ""
) -> tuple[str, str]:
    """Adapt the authored replacement to the casing of what was matched.

    Refusing is a real outcome here. A rule that lower-cased whatever it found
    would turn `In order to` at the start of a sentence into `to`, and a rule
    that guessed at `iN OrDeR tO` would be guessing.
    """
    # An inflected rule supplies the replacement for the form that matched;
    # a plain rule has one replacement for all of its literals.
    replacement = form_replacement or rule.action.replacement

    if rule.case_policy == CASE_EXACT:
        if matched != rule.match.text and matched not in rule.match.forms:
            return "", REFUSAL_CASE_EXACT
        return replacement, ""

    shape = _case_shape(matched)
    if shape == "lower":
        return replacement, ""
    if shape == "upper":
        return replacement.upper(), ""
    if shape == "title":
        return _title_case(replacement), ""
    if shape == "sentence":
        return replacement[:1].upper() + replacement[1:], ""
    return "", REFUSAL_CASE_UNMAPPABLE


def _case_shape(matched: str) -> str:
    """Classify capitalisation into one of the shapes we can reproduce."""
    letters = [character for character in matched if character.isalpha()]
    if not letters:
        return "lower"
    if matched == matched.lower():
        return "lower"
    if matched == matched.upper():
        return "upper"

    words = [word for word in matched.split() if any(c.isalpha() for c in word)]
    if words and all(word[:1].isupper() and word[1:] == word[1:].lower() for word in words):
        return "title" if len(words) > 1 else "sentence"
    if matched[:1].isupper() and matched[1:] == matched[1:].lower():
        return "sentence"
    # Mixed in a way we cannot reproduce: iPhone, mIxEd, McDonald.
    return "unmappable"


def _title_case(replacement: str) -> str:
    return " ".join(word[:1].upper() + word[1:] for word in replacement.split(" "))


def _deletion(text: str, rule: Rule, start: int, end: int, matched: str) -> tuple[str, str]:
    """Decide whether a phrase can be deleted without breaking the sentence.

    Deletion is the least safe thing this engine does, so the conditions are
    stated rather than assumed. The rule's phrase is expected to own its own
    trailing space; what remains to check is what the deletion leaves behind.
    """
    before = text[:start]
    after = text[end:]

    if not after:
        # Deleting to the end of the text would leave a dangling fragment.
        return "", REFUSAL_SPACING

    following = after[0]
    if following.isspace():
        # The phrase did not own its trailing space, so removing it would leave
        # a double space or a space before punctuation.
        return "", REFUSAL_SPACING
    if following in ",;:.!?":
        return "", REFUSAL_SPACING

    at_sentence_start = _at_sentence_start(before)

    if at_sentence_start and following.islower():
        if not rule.action.recapitalize:
            return "", REFUSAL_RECAPITALIZE
        if not following.isalpha():
            return "", REFUSAL_RECAPITALIZE
        # Extend the edit by one character and put it back capitalised. This is
        # signalled to the caller by returning a replacement for the *extended*
        # span; `deletion_span` below reports the extension.
        return following.upper(), ""

    if not at_sentence_start:
        # Mid-sentence deletion would strand the preceding text against the
        # following word without the phrase that joined them. Only a deletion
        # that begins a sentence is mechanically safe here.
        return "", REFUSAL_SPACING

    return "", ""


def deletion_span(text: str, rule: Rule, match: RuleMatch) -> tuple[int, int]:
    """The span a deletion actually replaces, including any recapitalisation.

    A deletion that has to capitalise the following word edits one character
    more than it matched. Reporting that here keeps the adjustment in one place
    rather than scattered through the planner.
    """
    if rule.action.type != ACTION_DELETE or match.refusal:
        return match.start, match.end
    if match.replacement:
        # `_deletion` returned the capitalised following character.
        return match.start, match.end + 1
    return match.start, match.end


def _at_sentence_start(before: str) -> bool:
    """Whether the text so far has ended a sentence (or has not begun one)."""
    trimmed = before.rstrip()
    if not trimmed:
        return True
    return trimmed[-1] in SENTENCE_ENDINGS
