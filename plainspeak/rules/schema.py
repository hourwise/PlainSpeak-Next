"""What a rule is, and what makes one invalid.

A rule is data. It carries no code, no expressions to evaluate and no way to
reach the interpreter: everything it can express is a fixed vocabulary checked
here. That is not paranoia about the bundled rules, which are project assets —
it is what makes the ruleset something a reviewer can read and reason about
without also auditing Python.

The validator is deliberately unforgiving. A malformed bundled rule is a build
failure, not a warning that scrolls past: a rule that silently failed to load
would show up as prose quietly not being improved, which is indistinguishable
from the rule having decided not to fire.

Every rule also has to carry its own tests. `examples.positive` says what it
must match, `examples.negative` says what it must *not* match, and a safe-fix
must additionally show its expected transformation. Requiring the negative
cases is the important half — it forces the author to think about false
positives at the moment they are easiest to think about.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

# ── Vocabulary ─────────────────────────────────────────────────────────────

#: Detect and report; never proposes an edit.
MODE_DIAGNOSTIC = "diagnostic"
#: Detect and propose a deterministic replacement believed meaning-preserving
#: under the conditions the rule states.
MODE_SAFE_FIX = "safe-fix"
#: Declare text that other rules may not alter.
MODE_PROTECTED = "protected"

#: Detect and propose a deterministic replacement that is *not* mechanically
#: safe in the safe-fix sense — it is a stylistic preference, valid only
#: relative to a chosen style profile, and it always requires human review.
#:
#: The distinction from `safe-fix` is the whole point of this mode. A safe fix
#: is a change the engine believes preserves meaning under stated conditions and
#: may enter the accepted set on its own. A style fix is a change a *profile*
#: considers preferable for a kind of prose, and a preference must never become
#: an automatic edit merely because a threshold was crossed. Every style fix
#: goes to review, and the planner has no path that puts one anywhere else.
MODE_STYLE_FIX = "style-fix"

MODES = frozenset({MODE_DIAGNOSTIC, MODE_SAFE_FIX, MODE_PROTECTED, MODE_STYLE_FIX})

#: Modes whose proposals may be applied without a human deciding. Deliberately
#: not "everything that produces a replacement": `style-fix` produces one and is
#: absent from this set, which is where that guarantee lives.
AUTOMATIC_MODES = frozenset({MODE_SAFE_FIX})

#: Mode precedence when two proposals cover the same characters. Protection
#: outranks everything; a mechanically safe transformation outranks a stylistic
#: preference. Rule priority is only consulted *within* a mode, so a style rule
#: can never displace a safe fix by declaring a bigger number.
MODE_PRECEDENCE = {
    MODE_PROTECTED: 0,
    MODE_SAFE_FIX: 1,
    MODE_STYLE_FIX: 2,
    MODE_DIAGNOSTIC: 3,
}

MATCH_PHRASE = "phrase"
MATCH_WORD = "word"
MATCH_REGEX = "regex"
#: A lemma plus a part of speech. The loader expands it into explicit
#: surface forms through `plainspeak.morphology`, so the matcher still only
#: ever sees literals — there is no stemming anywhere in this path.
MATCH_LEMMA = "lemma"
MATCH_TYPES = frozenset({MATCH_PHRASE, MATCH_WORD, MATCH_REGEX, MATCH_LEMMA})

ACTION_NONE = "none"
ACTION_REPLACE = "replace"
ACTION_DELETE = "delete"
ACTION_PROTECT = "protect"
ACTION_TYPES = frozenset({ACTION_NONE, ACTION_REPLACE, ACTION_DELETE, ACTION_PROTECT})

#: Which action each mode may take. A diagnostic that could replace text would
#: not be a diagnostic.
ACTIONS_FOR_MODE = {
    MODE_DIAGNOSTIC: frozenset({ACTION_NONE}),
    MODE_SAFE_FIX: frozenset({ACTION_REPLACE, ACTION_DELETE}),
    MODE_PROTECTED: frozenset({ACTION_PROTECT}),
    # Replacement only. A deletion promotes a subordinate clause to a main one
    # and changes sentence structure, which Phase 4 accepted for three exact
    # reviewed phrases and which a stylistic preference has not earned.
    MODE_STYLE_FIX: frozenset({ACTION_REPLACE}),
}

CASE_SENSITIVE = "sensitive"
CASE_INSENSITIVE = "insensitive"
CASE_SENSITIVITIES = frozenset({CASE_SENSITIVE, CASE_INSENSITIVE})

#: How a replacement adapts to the casing of the text it replaces.
CASE_PRESERVE = "preserve"
CASE_EXACT = "exact"
CASE_POLICIES = frozenset({CASE_PRESERVE, CASE_EXACT})

#: Structural scopes a rule may name. These mirror the document representation
#: rather than inventing a parallel vocabulary.
SCOPES = frozenset({"prose", "heading", "list", "quote", "code", "table", "link"})

ID_PATTERN = re.compile(r"^PS\.[A-Z][A-Z0-9]{1,15}\.\d{3}$")

#: Bounds that keep a rule file from being a denial-of-service vector, and keep
#: reviewers able to read what they are approving.
MAX_PATTERN_LENGTH = 200
MAX_PHRASE_LENGTH = 120
MAX_REPLACEMENT_LENGTH = 120
MAX_PRIORITY = 1000
MIN_PRIORITY = 0

#: Regex constructs a bundled rule may not use. Backreferences and recursion
#: invite catastrophic backtracking; inline flags and conditionals change the
#: meaning of the pattern in ways a reviewer reading the YAML would not see.
FORBIDDEN_REGEX_CONSTRUCTS = (
    (r"\\[1-9]", "backreferences"),
    (r"\(\?R\)", "recursion"),
    (r"\(\?P>", "recursive subpattern calls"),
    (r"\(\?\(", "conditional patterns"),
    (r"\(\?[aiLmsux]*\)", "inline global flags"),
)

#: A quantifier applied to a group that itself contains a quantifier — `(a+)+`
#: and friends. The classic shape of catastrophic backtracking.
NESTED_QUANTIFIER = re.compile(r"\([^)]*[+*}][^)]*\)\s*[+*]")


#: Style diagnostics a style-fix rule may name as its trigger. Restricted to the
#: two the initial transformations can actually act on: a rule that named
#: `SENTENCE_UNIFORMITY` would be claiming an exact replacement could fix
#: cadence, which nothing in this phase can do.
TRIGGERABLE_DIAGNOSTICS = frozenset({
    "PS.STYLE.REPEATED_TRANSITION",
    "PS.STYLE.TRANSITION_DENSITY",
})

#: Length bound on the evidence label a style-fix rule keys off.
MAX_EVIDENCE_LABEL = 60


class RuleError(ValueError):
    """A rule could not be loaded. Always fatal; never downgraded to a warning."""

    def __init__(self, rule_id: str, source: str, problem: str) -> None:
        self.rule_id = rule_id
        self.source = source
        self.problem = problem
        location = f"{source}" + (f" ({rule_id})" if rule_id else "")
        super().__init__(f"{location}: {problem}")


# ── The rule ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Match:
    """How a rule recognises text."""

    type: str
    #: Literal text, for `phrase` and `word`.
    text: str = ""
    #: Additional literal forms a `word` rule also matches. Explicit rather than
    #: derived: the inherited stemmer produced non-words, and a rule that
    #: silently matched more than it said would be worse than one that matched
    #: too little.
    forms: tuple[str, ...] = ()
    #: The expression, for `regex`.
    pattern: str = ""
    case: str = CASE_INSENSITIVE
    #: For a `lemma` match: the declared lemma and its part of speech.
    lemma: str = ""
    part_of_speech: str = ""
    #: Which inflections to generate. Empty means every form the part of speech
    #: has.
    form_classes: tuple[str, ...] = ()
    #: `(surface, replacement)` pairs, filled in by the loader from the declared
    #: lemma. Present on the rule itself so that a reviewer, an explanation and
    #: the ruleset hash all see the exact surfaces the rule will match — the
    #: morphology is inspectable rather than implied.
    inflections: tuple[tuple[str, str], ...] = ()

    @property
    def literals(self) -> tuple[str, ...]:
        if self.inflections:
            return tuple(surface for surface, _ in self.inflections)
        return (self.text,) + self.forms if self.text else self.forms


@dataclass(frozen=True)
class Action:
    """What a rule proposes, if anything."""

    type: str
    replacement: str = ""
    #: For a `lemma` match: the lemma to replace it with. The loader inflects
    #: both sides together, so a past tense is never paired with a gerund.
    lemma: str = ""
    #: For `delete`: capitalise the following word when the deletion leaves a
    #: sentence starting in lower case. Refused when that cannot be done
    #: mechanically — see `plainspeak.rules.matcher`.
    recapitalize: bool = False


@dataclass(frozen=True)
class Trigger:
    """The style diagnostic a style-fix rule depends on.

    A style fix may only propose anything when the style layer, reading the
    document under the selected profile, has actually produced this finding and
    named this evidence label. The rule does not decide whether the document is
    repetitive; it is told, and it may then act on the occurrences.

    That is the separation the whole phase turns on. A rule that recomputed the
    document-level condition would be a second style detector hiding inside the
    transformation engine, free to disagree with the first.
    """

    diagnostic: str
    #: The evidence label the finding must name — "furthermore", "in addition".
    #: Without it, a rule for one transition would fire on a finding about a
    #: different one.
    evidence_label: str


@dataclass(frozen=True)
class Review:
    """Whether a proposal from this rule requires human judgement.

    Only ever `True`, and validated as such. The field exists so that a rule
    file states the classification explicitly rather than relying on the reader
    to know what `style-fix` implies, and so that an attempt to declare
    `required: false` fails loudly at load rather than quietly producing an
    automatic edit.
    """

    required: bool


@dataclass(frozen=True)
class Scope:
    include: tuple[str, ...] = ("prose",)
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class Provenance:
    """Where a rule came from.

    Recorded for every rule without exception. A rule whose origin nobody can
    state is a rule nobody can defend, and "it was in the codebase already" is
    not an answer when somebody asks why their document was changed.
    """

    source: str
    reference: str
    licence: str


@dataclass(frozen=True)
class Transformation:
    """An expected before/after pair, asserted by the test suite."""

    before: str
    after: str


@dataclass(frozen=True)
class Examples:
    positive: tuple[str, ...]
    negative: tuple[str, ...]
    transform: tuple[Transformation, ...] = ()


@dataclass(frozen=True)
class Rule:
    """One declarative rule."""

    id: str
    version: int
    name: str
    mode: str
    description: str
    match: Match
    action: Action
    scope: Scope
    case_policy: str
    priority: int
    reason: str
    provenance: Provenance
    examples: Examples
    #: Which bundled family the rule was loaded from. Not part of its identity —
    #: moving a file between directories must not change the ruleset hash.
    family: str = ""
    #: Style-fix rules only. The diagnostic that must be present, under the
    #: selected profile, before this rule may propose anything.
    trigger: Optional[Trigger] = None
    #: Style-fix rules only, and always `required=True`.
    review: Optional[Review] = None

    @property
    def identity(self) -> tuple[str, int]:
        return (self.id, self.version)

    @property
    def is_safe_fix(self) -> bool:
        return self.mode == MODE_SAFE_FIX

    @property
    def is_protected(self) -> bool:
        return self.mode == MODE_PROTECTED

    @property
    def is_style_fix(self) -> bool:
        return self.mode == MODE_STYLE_FIX

    @property
    def is_automatic(self) -> bool:
        """Whether a proposal from this rule may be applied without review."""
        return self.mode in AUTOMATIC_MODES


# ── Validation ─────────────────────────────────────────────────────────────

REQUIRED_TOP_LEVEL = ("id", "version", "name", "mode", "description", "match", "reason",
                      "provenance", "examples")
ALLOWED_TOP_LEVEL = frozenset(REQUIRED_TOP_LEVEL) | {
    "action", "scope", "case", "priority", "requires_diagnostic", "review",
}


def build_rule(data: Any, source: str, family: str = "") -> Rule:
    """Validate one parsed YAML document and turn it into a `Rule`.

    Raises `RuleError` on anything it does not fully understand. Unknown keys
    are rejected rather than ignored, because a typo in a rule file is
    otherwise a rule that silently does something other than what it says.
    """
    if not isinstance(data, dict):
        raise RuleError("", source, f"expected a mapping, found {type(data).__name__}")

    rule_id = data.get("id") if isinstance(data.get("id"), str) else ""

    unknown = sorted(set(data) - ALLOWED_TOP_LEVEL)
    if unknown:
        raise RuleError(rule_id, source, f"unknown field(s): {', '.join(unknown)}")

    missing = [key for key in REQUIRED_TOP_LEVEL if key not in data]
    if missing:
        raise RuleError(rule_id, source, f"missing required field(s): {', '.join(missing)}")

    _check_id(rule_id, data.get("id"), source)
    version = _check_version(rule_id, data["version"], source)
    mode = _check_mode(rule_id, data["mode"], source)
    name = _check_text(rule_id, data["name"], source, "name", maximum=80)
    description = _check_text(rule_id, data["description"], source, "description", maximum=600)
    reason = _check_reason(rule_id, data["reason"], source)
    match = _check_match(rule_id, data["match"], source)
    action = _check_action(rule_id, data.get("action"), mode, source)
    scope = _check_scope(rule_id, data.get("scope"), source)
    case_policy = _check_case_policy(rule_id, data.get("case"), source)
    priority = _check_priority(rule_id, data.get("priority", 100), source)
    provenance = _check_provenance(rule_id, data["provenance"], source)
    examples = _check_examples(rule_id, data["examples"], mode, source)

    trigger = _check_trigger(rule_id, data.get("requires_diagnostic"), mode, source)
    review = _check_review(rule_id, data.get("review"), mode, source)

    _check_combination(rule_id, mode, match, action, case_policy, source)

    return Rule(
        id=rule_id,
        version=version,
        name=name,
        mode=mode,
        description=description.strip(),
        match=match,
        action=action,
        scope=scope,
        case_policy=case_policy,
        priority=priority,
        reason=reason,
        provenance=provenance,
        examples=examples,
        family=family,
        trigger=trigger,
        review=review,
    )


def _check_trigger(rule_id: str, raw: Any, mode: str, source: str) -> Optional["Trigger"]:
    """Validate `requires_diagnostic`, which only a style fix may carry."""
    if mode != MODE_STYLE_FIX:
        if raw is not None:
            raise RuleError(
                rule_id, source,
                "requires_diagnostic applies only to a style-fix rule; a rule of any "
                "other mode does not depend on a style diagnostic",
            )
        return None

    if not isinstance(raw, dict):
        raise RuleError(
            rule_id, source,
            "a style-fix rule must declare requires_diagnostic: it may propose nothing "
            "until the style layer has produced the finding that justifies it",
        )
    unknown = sorted(set(raw) - {"id", "evidence_label"})
    if unknown:
        raise RuleError(rule_id, source, f"requires_diagnostic: unknown field(s): {unknown}")

    identifier = raw.get("id")
    if identifier not in TRIGGERABLE_DIAGNOSTICS:
        raise RuleError(
            rule_id, source,
            f"requires_diagnostic.id {identifier!r} is not a diagnostic a style fix may act "
            f"on; available: {sorted(TRIGGERABLE_DIAGNOSTICS)}",
        )

    label = raw.get("evidence_label")
    if not isinstance(label, str) or not label.strip():
        raise RuleError(
            rule_id, source,
            "requires_diagnostic.evidence_label is required: without it a rule for one "
            "transition would fire on a finding about a different one",
        )
    if len(label) > MAX_EVIDENCE_LABEL:
        raise RuleError(rule_id, source, "requires_diagnostic.evidence_label is too long")
    if label != label.strip().lower():
        raise RuleError(
            rule_id, source,
            "requires_diagnostic.evidence_label must be lower case and unpadded, because "
            "that is the form the style layer produces",
        )

    return Trigger(diagnostic=identifier, evidence_label=label)


def _check_review(rule_id: str, raw: Any, mode: str, source: str) -> Optional["Review"]:
    """Validate `review`, which only a style fix may carry and may only be true."""
    if mode != MODE_STYLE_FIX:
        if raw is not None:
            raise RuleError(
                rule_id, source,
                "review applies only to a style-fix rule; every other mode's review "
                "status follows from its mode",
            )
        return None

    if not isinstance(raw, dict):
        raise RuleError(
            rule_id, source, "a style-fix rule must declare review: {required: true}"
        )
    unknown = sorted(set(raw) - {"required"})
    if unknown:
        raise RuleError(rule_id, source, f"review: unknown field(s): {unknown}")

    required = raw.get("required")
    if required is not True:
        raise RuleError(
            rule_id, source,
            "review.required must be true. A style fix is a preference relative to a "
            "chosen profile, and a preference does not become an automatic edit because "
            "a threshold was crossed. There is no way to declare otherwise.",
        )
    return Review(required=True)


def _check_id(rule_id: str, raw: Any, source: str) -> None:
    if not isinstance(raw, str) or not ID_PATTERN.match(raw):
        raise RuleError(
            rule_id, source,
            f"id must match PS.<FAMILY>.<NNN>, for example PS.CLARITY.001; found {raw!r}",
        )


def _check_version(rule_id: str, raw: Any, source: str) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool) or raw < 1:
        raise RuleError(rule_id, source, f"version must be a positive integer, found {raw!r}")
    return raw


def _check_mode(rule_id: str, raw: Any, source: str) -> str:
    if raw not in MODES:
        raise RuleError(
            rule_id, source, f"mode must be one of {sorted(MODES)}, found {raw!r}"
        )
    return raw


def _check_text(rule_id: str, raw: Any, source: str, field_name: str, maximum: int) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise RuleError(rule_id, source, f"{field_name} must be a non-empty string")
    if len(raw) > maximum:
        raise RuleError(
            rule_id, source, f"{field_name} is {len(raw)} characters, limit is {maximum}"
        )
    return raw


def _check_reason(rule_id: str, raw: Any, source: str) -> str:
    if not isinstance(raw, dict) or "short" not in raw:
        raise RuleError(rule_id, source, "reason must be a mapping containing 'short'")
    unknown = sorted(set(raw) - {"short"})
    if unknown:
        raise RuleError(rule_id, source, f"unknown reason field(s): {', '.join(unknown)}")
    return _check_text(rule_id, raw["short"], source, "reason.short", maximum=120)


def _check_match(rule_id: str, raw: Any, source: str) -> Match:
    if not isinstance(raw, dict):
        raise RuleError(rule_id, source, "match must be a mapping")
    unknown = sorted(
        set(raw) - {"type", "text", "forms", "pattern", "case", "lemma", "pos", "classes"}
    )
    if unknown:
        raise RuleError(rule_id, source, f"unknown match field(s): {', '.join(unknown)}")

    match_type = raw.get("type")
    if match_type not in MATCH_TYPES:
        raise RuleError(
            rule_id, source, f"match.type must be one of {sorted(MATCH_TYPES)}, found {match_type!r}"
        )

    case = raw.get("case", CASE_INSENSITIVE)
    if case not in CASE_SENSITIVITIES:
        raise RuleError(
            rule_id, source,
            f"match.case must be one of {sorted(CASE_SENSITIVITIES)}, found {case!r}",
        )

    if match_type == MATCH_LEMMA:
        return _check_lemma_match(rule_id, raw, case, source)

    if "lemma" in raw or "pos" in raw or "classes" in raw:
        raise RuleError(
            rule_id, source, f"a {match_type} match takes 'text', not 'lemma'/'pos'/'classes'"
        )

    if match_type == MATCH_REGEX:
        if "text" in raw or "forms" in raw:
            raise RuleError(rule_id, source, "a regex match takes 'pattern', not 'text'/'forms'")
        pattern = raw.get("pattern")
        _check_regex(rule_id, pattern, source)
        return Match(type=match_type, pattern=pattern, case=case)

    if "pattern" in raw:
        raise RuleError(rule_id, source, f"a {match_type} match takes 'text', not 'pattern'")

    text = raw.get("text")
    if not isinstance(text, str) or not text:
        raise RuleError(rule_id, source, f"match.text must be a non-empty string for {match_type}")
    if len(text) > MAX_PHRASE_LENGTH:
        raise RuleError(
            rule_id, source, f"match.text is {len(text)} characters, limit is {MAX_PHRASE_LENGTH}"
        )

    forms_raw = raw.get("forms", [])
    if not isinstance(forms_raw, list) or any(not isinstance(f, str) or not f for f in forms_raw):
        raise RuleError(rule_id, source, "match.forms must be a list of non-empty strings")
    if match_type == MATCH_PHRASE and forms_raw:
        raise RuleError(rule_id, source, "match.forms is only meaningful for a word match")
    if len(forms_raw) != len(set(forms_raw)):
        raise RuleError(rule_id, source, "match.forms contains duplicates")
    if text in forms_raw:
        raise RuleError(rule_id, source, "match.forms repeats match.text")

    if match_type == MATCH_WORD:
        for candidate in (text, *forms_raw):
            if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", candidate):
                raise RuleError(
                    rule_id, source,
                    f"a word match may only contain letters, apostrophes and hyphens; "
                    f"found {candidate!r}. Use a phrase match for anything else",
                )

    return Match(type=match_type, text=text, forms=tuple(forms_raw), case=case)


def _check_lemma_match(rule_id: str, raw: dict, case: str, source: str) -> Match:
    """Validate a lemma match without inflecting it.

    Expansion happens in the loader, which is the only place that may import
    morphology. Keeping the two apart means a schema error reads as a schema
    error rather than as a morphology failure.
    """
    from ..morphology import FORM_CLASSES, PARTS_OF_SPEECH

    for forbidden in ("text", "forms", "pattern"):
        if forbidden in raw:
            raise RuleError(rule_id, source, f"a lemma match takes 'lemma', not {forbidden!r}")

    lemma = raw.get("lemma")
    if not isinstance(lemma, str) or not lemma.strip():
        raise RuleError(rule_id, source, "match.lemma must be a non-empty string")
    if len(lemma) > MAX_PHRASE_LENGTH:
        raise RuleError(
            rule_id, source, f"match.lemma is {len(lemma)} characters, limit is {MAX_PHRASE_LENGTH}"
        )

    part_of_speech = raw.get("pos")
    if part_of_speech not in PARTS_OF_SPEECH:
        raise RuleError(
            rule_id, source,
            f"match.pos must be one of {sorted(PARTS_OF_SPEECH)}, found {part_of_speech!r}",
        )

    classes = raw.get("classes", [])
    if not isinstance(classes, list) or any(not isinstance(name, str) for name in classes):
        raise RuleError(rule_id, source, "match.classes must be a list of strings")
    available = FORM_CLASSES[part_of_speech]
    unknown = sorted(set(classes) - set(available))
    if unknown:
        raise RuleError(
            rule_id, source,
            f"match.classes names form(s) a {part_of_speech} does not have: {unknown}; "
            f"available: {list(available)}",
        )
    if len(classes) != len(set(classes)):
        raise RuleError(rule_id, source, "match.classes contains duplicates")

    return Match(
        type=MATCH_LEMMA,
        case=case,
        lemma=lemma.strip(),
        part_of_speech=part_of_speech,
        form_classes=tuple(classes),
    )


def _check_regex(rule_id: str, pattern: Any, source: str) -> None:
    if not isinstance(pattern, str) or not pattern:
        raise RuleError(rule_id, source, "match.pattern must be a non-empty string")
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise RuleError(
            rule_id, source,
            f"match.pattern is {len(pattern)} characters, limit is {MAX_PATTERN_LENGTH}",
        )
    for construct, label in FORBIDDEN_REGEX_CONSTRUCTS:
        if re.search(construct, pattern):
            raise RuleError(rule_id, source, f"match.pattern uses {label}, which is not allowed")
    if NESTED_QUANTIFIER.search(pattern):
        raise RuleError(
            rule_id, source,
            "match.pattern nests a quantifier inside a quantified group, which risks "
            "catastrophic backtracking",
        )
    try:
        re.compile(pattern)
    except re.error as exc:
        raise RuleError(rule_id, source, f"match.pattern does not compile: {exc}") from exc


def _check_action(rule_id: str, raw: Any, mode: str, source: str) -> Action:
    if raw is None:
        raw = {"type": ACTION_NONE if mode == MODE_DIAGNOSTIC else ""}
    if not isinstance(raw, dict):
        raise RuleError(rule_id, source, "action must be a mapping")
    unknown = sorted(set(raw) - {"type", "replacement", "recapitalize", "lemma"})
    if unknown:
        raise RuleError(rule_id, source, f"unknown action field(s): {', '.join(unknown)}")

    action_type = raw.get("type")
    if action_type not in ACTION_TYPES:
        raise RuleError(
            rule_id, source,
            f"action.type must be one of {sorted(ACTION_TYPES)}, found {action_type!r}",
        )

    allowed = ACTIONS_FOR_MODE[mode]
    if action_type not in allowed:
        raise RuleError(
            rule_id, source,
            f"a {mode} rule may only use action {sorted(allowed)}, found {action_type!r}",
        )

    target_lemma = raw.get("lemma", "")
    if not isinstance(target_lemma, str):
        raise RuleError(rule_id, source, "action.lemma must be a string")

    replacement = raw.get("replacement", "")
    if action_type == ACTION_REPLACE:
        if replacement and target_lemma:
            raise RuleError(
                rule_id, source,
                "action takes either 'replacement' or 'lemma', not both: a lemma is "
                "inflected to match each form, a replacement is used verbatim",
            )
        if not replacement and not target_lemma:
            raise RuleError(rule_id, source, "action.replacement is required for a replace action")
        if len(replacement) > MAX_REPLACEMENT_LENGTH:
            raise RuleError(
                rule_id, source,
                f"action.replacement is {len(replacement)} characters, "
                f"limit is {MAX_REPLACEMENT_LENGTH}",
            )
    elif replacement:
        raise RuleError(
            rule_id, source, f"action.replacement is meaningless for a {action_type} action"
        )

    recapitalize = raw.get("recapitalize", False)
    if not isinstance(recapitalize, bool):
        raise RuleError(rule_id, source, "action.recapitalize must be true or false")
    if recapitalize and action_type != ACTION_DELETE:
        raise RuleError(rule_id, source, "action.recapitalize only applies to a delete action")

    return Action(
        type=action_type,
        replacement=replacement,
        lemma=target_lemma,
        recapitalize=recapitalize,
    )


def _check_scope(rule_id: str, raw: Any, source: str) -> Scope:
    if raw is None:
        return Scope()
    if not isinstance(raw, dict):
        raise RuleError(rule_id, source, "scope must be a mapping")
    unknown = sorted(set(raw) - {"include", "exclude"})
    if unknown:
        raise RuleError(rule_id, source, f"unknown scope field(s): {', '.join(unknown)}")

    def names(key: str, default: Sequence[str]) -> tuple[str, ...]:
        value = raw.get(key, list(default))
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise RuleError(rule_id, source, f"scope.{key} must be a list of strings")
        bad = sorted(set(value) - SCOPES)
        if bad:
            raise RuleError(
                rule_id, source,
                f"scope.{key} names unknown scope(s): {', '.join(bad)}; known: {sorted(SCOPES)}",
            )
        if len(value) != len(set(value)):
            raise RuleError(rule_id, source, f"scope.{key} contains duplicates")
        return tuple(value)

    include = names("include", ("prose",))
    exclude = names("exclude", ())
    overlap = sorted(set(include) & set(exclude))
    if overlap:
        raise RuleError(
            rule_id, source, f"scope names {', '.join(overlap)} as both included and excluded"
        )
    if not include:
        raise RuleError(rule_id, source, "scope.include must name at least one scope")
    return Scope(include=include, exclude=exclude)


def _check_case_policy(rule_id: str, raw: Any, source: str) -> str:
    if raw is None:
        return CASE_PRESERVE
    if not isinstance(raw, dict) or "policy" not in raw:
        raise RuleError(rule_id, source, "case must be a mapping containing 'policy'")
    unknown = sorted(set(raw) - {"policy"})
    if unknown:
        raise RuleError(rule_id, source, f"unknown case field(s): {', '.join(unknown)}")
    policy = raw["policy"]
    if policy not in CASE_POLICIES:
        raise RuleError(
            rule_id, source, f"case.policy must be one of {sorted(CASE_POLICIES)}, found {policy!r}"
        )
    return policy


def _check_priority(rule_id: str, raw: Any, source: str) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise RuleError(rule_id, source, f"priority must be an integer, found {raw!r}")
    if not (MIN_PRIORITY <= raw <= MAX_PRIORITY):
        raise RuleError(
            rule_id, source,
            f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}, found {raw}",
        )
    return raw


def _check_provenance(rule_id: str, raw: Any, source: str) -> Provenance:
    if not isinstance(raw, dict):
        raise RuleError(rule_id, source, "provenance must be a mapping")
    required = ("source", "reference", "licence")
    unknown = sorted(set(raw) - set(required))
    if unknown:
        raise RuleError(rule_id, source, f"unknown provenance field(s): {', '.join(unknown)}")
    missing = [key for key in required if key not in raw]
    if missing:
        raise RuleError(
            rule_id, source, f"provenance is missing: {', '.join(missing)}"
        )
    for key in required:
        if not isinstance(raw[key], str):
            raise RuleError(rule_id, source, f"provenance.{key} must be a string")
    # `reference` may legitimately be empty — an independently authored rule has
    # no external reference — but source and licence must say something.
    for key in ("source", "licence"):
        if not raw[key].strip():
            raise RuleError(rule_id, source, f"provenance.{key} must not be empty")
    return Provenance(source=raw["source"], reference=raw["reference"], licence=raw["licence"])


def _check_examples(rule_id: str, raw: Any, mode: str, source: str) -> Examples:
    if not isinstance(raw, dict):
        raise RuleError(rule_id, source, "examples must be a mapping")
    unknown = sorted(set(raw) - {"positive", "negative", "transform"})
    if unknown:
        raise RuleError(rule_id, source, f"unknown examples field(s): {', '.join(unknown)}")

    def strings(key: str) -> tuple[str, ...]:
        value = raw.get(key)
        if not isinstance(value, list) or not value:
            raise RuleError(rule_id, source, f"examples.{key} must be a non-empty list")
        if any(not isinstance(item, str) or not item for item in value):
            raise RuleError(rule_id, source, f"examples.{key} must contain non-empty strings")
        return tuple(value)

    positive = strings("positive")
    # The negative cases are the ones that matter. A rule with no stated
    # false-positive case is a rule whose author has not yet thought about when
    # it should stay quiet.
    negative = strings("negative")

    transform_raw = raw.get("transform", [])
    if not isinstance(transform_raw, list):
        raise RuleError(rule_id, source, "examples.transform must be a list")
    transforms = []
    for entry in transform_raw:
        if not isinstance(entry, dict) or set(entry) != {"before", "after"}:
            raise RuleError(
                rule_id, source, "each examples.transform entry needs exactly 'before' and 'after'"
            )
        if not isinstance(entry["before"], str) or not isinstance(entry["after"], str):
            raise RuleError(rule_id, source, "examples.transform values must be strings")
        transforms.append(Transformation(before=entry["before"], after=entry["after"]))

    if mode in (MODE_SAFE_FIX, MODE_STYLE_FIX) and not transforms:
        raise RuleError(
            rule_id, source,
            f"a {mode} rule must state at least one examples.transform pair; a change whose "
            f"expected output is not written down is not a change anybody can review",
        )
    if mode not in (MODE_SAFE_FIX, MODE_STYLE_FIX) and transforms:
        raise RuleError(
            rule_id, source, f"a {mode} rule proposes no edit, so examples.transform is meaningless"
        )

    return Examples(positive=positive, negative=negative, transform=tuple(transforms))


def _check_combination(
    rule_id: str, mode: str, match: Match, action: Action, case_policy: str, source: str
) -> None:
    """Reject matcher/action pairings that cannot mean anything sensible."""
    if match.type == MATCH_LEMMA and mode == MODE_SAFE_FIX and not action.lemma:
        raise RuleError(
            rule_id, source,
            "a lemma match driving a safe fix needs action.lemma: a fixed replacement "
            "would put the same word in every tense",
        )
    if action.lemma and match.type != MATCH_LEMMA:
        raise RuleError(rule_id, source, "action.lemma only applies to a lemma match")
    if match.type == MATCH_LEMMA and action.type == ACTION_DELETE:
        raise RuleError(
            rule_id, source, "deleting an inflected word leaves the surrounding grammar undefined"
        )
    if action.type == ACTION_DELETE and match.type == MATCH_WORD:
        raise RuleError(
            rule_id, source,
            "deleting a single word leaves the surrounding grammar undefined; use a "
            "phrase match that includes the whitespace it owns, or make the rule diagnostic",
        )
    if action.type == ACTION_REPLACE and match.type == MATCH_REGEX:
        raise RuleError(
            rule_id, source,
            "a regex match may not drive a replacement in this phase: the matched text "
            "varies with the input, so the replacement cannot be reviewed in advance",
        )
    if mode == MODE_STYLE_FIX and match.type != MATCH_PHRASE:
        raise RuleError(
            rule_id, source,
            "a style fix must match an exact phrase. A word or lemma match would let one "
            "stylistic preference apply to surfaces nobody reviewed, and a regex match "
            "cannot be reviewed in advance at all",
        )
    if mode == MODE_STYLE_FIX and not action.replacement:
        raise RuleError(
            rule_id, source, "a style fix must state the exact text it would propose"
        )
    if case_policy == CASE_EXACT and match.case == CASE_INSENSITIVE and mode == MODE_SAFE_FIX:
        raise RuleError(
            rule_id, source,
            "case.policy 'exact' with an insensitive match would rewrite text into casing "
            "the author did not use; make the match case-sensitive or preserve casing",
        )
