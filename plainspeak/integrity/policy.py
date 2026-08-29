"""What PlainSpeak refuses to let a transformation change.

This is the declaration half of the integrity firewall: the categories of
information treated as invariant, the patterns that recognise them, and the
bounded vocabularies they draw on. The extractor reads it; nothing else decides
what is protected.

The policy is **versioned product behaviour**, not an implementation detail. A
document processed under `2026.1` was checked against these rules and no
others, so the version and its hash travel with every plan and every audit
record. A plan authorised under one policy cannot be applied under another —
that would mean applying edits nobody checked.

Two design commitments run through it.

**Bounded, not clever.** There is no attempt at arbitrary scientific-unit
parsing, no locale resolution for ambiguous slash dates, and no semantic
equivalence. Every vocabulary here is a list somebody reviewed. A pattern that
would need judgement to apply is a pattern that belongs in a diagnostic.

**Conservative on both sides.** Where a category might over-match ordinary
prose, the pattern is tightened rather than the check being softened; where a
legitimate rewrite trips a check, the honest outcome is that the rewrite is
refused. The firewall exists to be the thing that says no.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

#: Bumped when the protected categories or their recognition change in a way
#: that alters what would be accepted. The hash below moves with any change at
#: all; the version is the human-facing label for it.
POLICY_VERSION = "2026.1"

#: Bumped only if the canonical rendering itself changes shape, so that a hash
#: computed under an older layout can never be mistaken for a current one.
CANONICAL_FORM_VERSION = 1


# ── Vocabularies ───────────────────────────────────────────────────────────

#: Units recognised when they directly follow a number. Deliberately a reviewed
#: list rather than a general unit grammar: "5 mg" becoming "5 g" is a
#: thousandfold error in a dosage, and a system that guessed at unit syntax
#: would be guessing about exactly that.
#:
#: Case is significant. "mL" and "ml" are the same unit to a reader, but this
#: layer does not normalise them, because deciding which case differences are
#: meaningless is the kind of judgement that belongs to a reviewed rule rather
#: than to a safety check.
UNITS: tuple[str, ...] = (
    # Mass
    "mg", "g", "kg", "µg", "mcg", "ng", "lb", "oz", "t",
    # Volume
    "ml", "mL", "L", "l", "cl", "dl", "cc",
    # Length
    "mm", "cm", "m", "km", "in", "ft", "mi", "nm", "µm",
    # Speed
    "mph", "km/h", "kph", "m/s",
    # Temperature
    "°C", "°F", "K",
    # Time
    "ms", "s", "sec", "min", "h", "hr", "hrs", "d", "days", "wk", "yr",
    # Data
    "B", "KB", "MB", "GB", "TB", "KiB", "MiB", "GiB", "TiB", "bps", "Mbps", "Gbps",
    # Frequency, electrical
    "Hz", "kHz", "MHz", "GHz", "V", "mV", "kV", "A", "mA", "W", "kW", "MW", "Wh", "kWh",
    # Pressure, other
    "Pa", "kPa", "bar", "psi", "dB", "IU", "mmHg",
)

#: Currency symbols and ISO codes, mapped to one identity each. Changing "£" to
#: "$" leaves the digits alone and changes the amount entirely, which is why
#: currency identity is protected separately from the number beside it.
CURRENCY_SYMBOLS: dict[str, str] = {
    "£": "GBP",
    "$": "USD",
    "€": "EUR",
    "¥": "JPY",
    "₹": "INR",
    "₽": "RUB",
    "₩": "KRW",
    "R$": "BRL",
    "CHF": "CHF",
}

CURRENCY_CODES: tuple[str, ...] = (
    "GBP", "USD", "EUR", "JPY", "INR", "RUB", "KRW", "BRL", "CHF",
    "CAD", "AUD", "NZD", "CNY", "SEK", "NOK", "DKK", "PLN", "ZAR",
)

#: Negation markers. All normalise to one token, because the invariant being
#: protected is the *presence and count* of negation rather than its wording:
#: "must not" becoming "must" is the failure this exists to catch, and "not"
#: becoming "never" is not.
NEGATION_WORDS: tuple[str, ...] = (
    "cannot", "not", "no", "never", "without", "neither", "nor", "none",
)

#: Modal and authority terms. An obligation becoming a permission is a change
#: of legal effect that reads as a small edit.
MODAL_WORDS: tuple[str, ...] = (
    "must", "shall", "may", "can", "should", "will", "would", "could", "might",
)

#: Bounded comparators and qualifiers. Ordered longest-first so that "at least"
#: is recognised before "least" could be, and multi-word phrases claim their
#: text before any single word inside them.
#:
#: This list is knowingly strict. "Before" and "after" being protected means a
#: rule proposing "prior to" → "before" is refused, because the firewall cannot
#: tell that substitution from one that reverses an ordering. That is the
#: intended trade: a refused improvement costs a missed simplification, and a
#: permitted reversal costs the reader the meaning of the sentence.
COMPARATOR_PHRASES: tuple[str, ...] = (
    "greater than or equal to", "less than or equal to",
    "no earlier than", "no later than", "no more than", "no less than",
    "at least", "at most", "more than", "less than", "greater than",
    "fewer than", "up to", "as many as", "as few as",
    "before", "after", "within", "until", "unless", "only", "except",
)


# ── Categories ─────────────────────────────────────────────────────────────
#
# Order is significant and is part of the policy. Extraction claims text as it
# goes, and a later category never re-claims characters an earlier one took —
# so a URL's query string is a URL rather than a scatter of numbers, and
# "can't" is a negation rather than the modal "can" plus punctuation.
#
# Read the ordering as most-specific-first.

_NUMBER = r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+-]?\d+(?:\.\d+)?"
# Alternations are sorted longest-first so the regex engine prefers the longer
# unit or symbol: without it "m" would win over "mm" and "$" over "R$".
_UNIT_ALTERNATION = "|".join(sorted(map(re.escape, UNITS), key=len, reverse=True))
_CURRENCY_SYMBOL_ALTERNATION = "|".join(
    sorted(map(re.escape, CURRENCY_SYMBOLS), key=len, reverse=True)
)
_CURRENCY_CODE_ALTERNATION = "|".join(sorted(CURRENCY_CODES, key=len, reverse=True))
_NEGATION_ALTERNATION = "|".join(sorted(NEGATION_WORDS, key=len, reverse=True))
_MODAL_ALTERNATION = "|".join(sorted(MODAL_WORDS, key=len, reverse=True))
_COMPARATOR_ALTERNATION = "|".join(
    sorted((p.replace(" ", r"\s+") for p in COMPARATOR_PHRASES), key=len, reverse=True)
)

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
    "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

#: Categories whose recognition ignores capitalisation.
#:
#: A word at the start of a sentence is capitalised, so a case-sensitive
#: `not` silently fails to protect "Not applicable" — and "Must", "Before"
#: and "Neither" with it. Folding case for these is safe because their
#: normalisation lower-cases anyway: "Must" and "must" are the same obligation,
#: while "must" and "may" are not.
#:
#: Units are deliberately absent. "mg" and "Mg" are different units, and folding
#: their case would make a thousandfold error invisible to this layer.
CASE_INSENSITIVE_KINDS: frozenset = frozenset(
    {"negation", "modal", "comparator", "cve", "date", "time", "version", "percentage", "url"}
)

#: Punctuation trimmed from the end of a match, and the kinds it applies to.
#:
#: Patterns that run to a token boundary otherwise swallow the punctuation that
#: ends the sentence around them: "/etc/app/config.ini." is a path followed by a
#: full stop, not a path with a dot on the end. Declared here rather than in the
#: extractor because it changes which facts are produced, and everything that
#: does belongs in the hashed policy.
TRAILING_PUNCTUATION = ".,;:!?"
TRIMMED_KINDS: frozenset = frozenset({"url", "path", "email", "time"})

#: Which normalisation each kind uses to form its comparison identity. Names
#: rather than functions, so the policy document stays plain data — but a change
#: here changes what compares equal, so it has to move the hash.
NORMALIZERS: dict[str, str] = {
    "number": "digits",
    "percentage": "percentage",
    "currency": "currency",
    "measurement": "measurement",
    "negation": "single-token",
    "modal": "lowercase",
    "comparator": "lowercase",
    "time": "lowercase",
    "cve": "lowercase",
    "uuid": "lowercase",
    "hash": "lowercase",
    "url": "exact",
    "email": "exact",
    "path": "exact",
    "version": "exact",
    "date": "collapse-whitespace",
}

#: `(kind, pattern)` pairs, applied in order.
CATEGORIES: tuple[tuple[str, str], ...] = (
    # Addresses and identifiers, which contain digits that must not be read as
    # separate numbers.
    ("url", r"\b(?:https?|ftp)://[^\s<>\"')\]]+"),
    ("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ("uuid", r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    ("cve", r"\bCVE-\d{4}-\d{4,7}\b"),
    # Long hexadecimal runs only. Short ones are ordinary words far too often —
    # "decade", "faced", "added" are all valid hex.
    ("hash", r"\b[0-9a-fA-F]{32,128}\b"),
    # Windows drive paths, POSIX absolute paths, and explicit relative paths.
    # An explicit anchor is required throughout: bare "docs/readme" is prose
    # with a slash in it far more often than it is a path.
    ("path", r"[A-Za-z]:[\\/](?:[^\s<>:\"|?*]+[\\/])*[^\s<>:\"|?*]+"),
    ("path", r"(?:\.{1,2}[\\/])(?:[^\s<>:\"|?*]+[\\/])*[^\s<>:\"|?*]+"),
    ("path", r"(?<![\w.])/(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+"),
    # A version needs three components, or a "v" prefix, or a pre-release tag.
    # Two bare components are a decimal number far more often than a release.
    ("version", r"\bv\d+(?:\.\d+){1,3}(?:-[0-9A-Za-z.]+)?\b"),
    ("version", r"\b\d+\.\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.]+)?\b"),
    # Dates, before times and numbers claim their digits.
    ("date", r"\b\d{4}-\d{2}-\d{2}\b"),
    ("date", r"\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b"),
    ("date", r"\b\d{1,2}\s+(?:" + _MONTHS + r")\.?\s+\d{4}\b"),
    ("date", r"\b(?:" + _MONTHS + r")\.?\s+\d{1,2},\s*\d{4}\b"),
    ("time", r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?m\.?)?\b"),
    ("time", r"\b\d{1,2}\s*[ap]\.?m\.?(?![a-z])"),
    # Money, before the bare number underneath it.
    ("currency", r"(?:" + _CURRENCY_SYMBOL_ALTERNATION + r")\s?(?:" + _NUMBER + r")"),
    ("currency", r"\b(?:" + _CURRENCY_CODE_ALTERNATION + r")\s?(?:" + _NUMBER + r")"),
    ("currency", r"(?:" + _NUMBER + r")\s?(?:" + _CURRENCY_CODE_ALTERNATION + r")\b"),
    ("percentage", r"(?:" + _NUMBER + r")\s?%"),
    ("percentage", r"(?:" + _NUMBER + r")\s+per\s?cent(?:age)?\b"),
    ("percentage", r"(?:" + _NUMBER + r")\s+percent\b"),
    # A number with a recognised unit beside it.
    ("measurement", r"(?:" + _NUMBER + r")\s?(?:" + _UNIT_ALTERNATION + r")(?![A-Za-z0-9])"),
    # Everything numeric that no more specific category claimed.
    ("number", _NUMBER),
    # Logic. Comparators first so multi-word phrases win; negation before
    # modals so "can't" is one negation rather than a modal plus punctuation.
    ("comparator", r"\b(?:" + _COMPARATOR_ALTERNATION + r")\b"),
    ("negation", r"\b[A-Za-z]+n't\b"),
    ("negation", r"\b(?:" + _NEGATION_ALTERNATION + r")\b"),
    ("modal", r"\b(?:" + _MODAL_ALTERNATION + r")\b"),
)

#: Every kind the policy can produce, sorted for stable reporting.
KINDS: tuple[str, ...] = tuple(sorted({kind for kind, _ in CATEGORIES}))


# ── Identity ───────────────────────────────────────────────────────────────


def canonical_json(value: Any) -> str:
    """Canonical rendering, byte-identical on every platform.

    Deliberately duplicated from `plainspeak.rules.canonical` rather than
    imported. `integrity` is an architectural leaf — it may not import another
    layer, because anything it depended on could come to depend on it, and a
    cycle in the component whose job is to say "no" would be a cycle in the
    safety check itself. A test asserts the two renderings agree, so the
    duplication cannot drift.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def flags_for(kind: str) -> int:
    """Regex flags for a category. Part of the policy, so part of its identity."""
    return re.IGNORECASE if kind in CASE_INSENSITIVE_KINDS else 0


def policy_document() -> dict[str, Any]:
    """The whole policy as canonical data.

    Everything that changes what would be accepted is in here: the category
    order, every pattern, and every vocabulary. Vocabularies are sorted, since
    the order they are written in the source has no effect on behaviour and
    should not affect the identity.
    """
    return {
        "canonical_form": CANONICAL_FORM_VERSION,
        "policy_version": POLICY_VERSION,
        # Order is behaviour here, so this list is *not* sorted.
        "categories": [
            {
                "kind": kind,
                "pattern": pattern,
                "ignore_case": kind in CASE_INSENSITIVE_KINDS,
            }
            for kind, pattern in CATEGORIES
        ],
        "trimming": {
            "punctuation": TRAILING_PUNCTUATION,
            "kinds": sorted(TRIMMED_KINDS),
        },
        "normalizers": {key: NORMALIZERS[key] for key in sorted(NORMALIZERS)},
        "vocabularies": {
            "units": sorted(UNITS),
            "currency_symbols": {key: CURRENCY_SYMBOLS[key] for key in sorted(CURRENCY_SYMBOLS)},
            "currency_codes": sorted(CURRENCY_CODES),
            "negation": sorted(NEGATION_WORDS),
            "modal": sorted(MODAL_WORDS),
            "comparators": sorted(COMPARATOR_PHRASES),
        },
    }


def policy_hash() -> str:
    """SHA-256 of the canonical policy document."""
    return hashlib.sha256(canonical_json(policy_document()).encode("utf-8")).hexdigest()
