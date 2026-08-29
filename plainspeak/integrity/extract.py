"""Finding the protected facts in a piece of text.

Ordinary deterministic text processing: the policy's categories are applied in
order, and each claims the characters it matches so a later category cannot
re-read them. That claiming is what makes the result stable and sensible — a
URL's query string stays a URL rather than becoming a scatter of loose numbers,
and `can't` is one negation rather than the modal `can` followed by punctuation.

Normalisation exists so that a genuine reformatting is not mistaken for a
change of meaning: `£2,500` and `£2500` are one amount. It is applied narrowly.
Where deciding whether two surfaces mean the same thing would take judgement —
`mL` against `ml`, `2026-08-29` against `29 August 2026` — the surface is kept
and the two are treated as different. Being too strict costs a refused edit;
being too lax costs the reader the meaning of the sentence.
"""
from __future__ import annotations

import re
from typing import Optional

from .model import IntegrityFact, IntegritySnapshot, text_hash
from .policy import (
    CATEGORIES,
    CURRENCY_CODES,
    CURRENCY_SYMBOLS,
    POLICY_VERSION,
    TRAILING_PUNCTUATION,
    TRIMMED_KINDS,
    flags_for,
    policy_hash,
)

#: Compiled once. The policy is a module-level constant, so this cannot go
#: stale, and rebuilding these on every call would dominate the cost of
#: snapshotting a large document.
_COMPILED: tuple[tuple[str, "re.Pattern[str]"], ...] = tuple(
    (kind, re.compile(pattern, flags_for(kind))) for kind, pattern in CATEGORIES
)

_POLICY_HASH = policy_hash()

_NUMBER_RE = re.compile(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+-]?\d+(?:\.\d+)?")
_WHITESPACE = re.compile(r"\s+")

#: Trimming is declared by the policy, not decided here — see `policy` for why.
#: `time` is among the trimmed kinds because "4pm." and "4pm" would otherwise be
#: different facts, which would make moving a time to the end of a sentence look
#: like changing it. Trimming is idempotent: "4 p.m." becomes "4 p.m", and so
#: does "4 p.m".
_TRAILING_PUNCTUATION = TRAILING_PUNCTUATION
_TRIMMED_KINDS = TRIMMED_KINDS


def snapshot(text: str) -> IntegritySnapshot:
    """Every protected fact in `text`, in document order."""
    return IntegritySnapshot(
        text_hash=text_hash(text),
        policy_version=POLICY_VERSION,
        policy_hash=_POLICY_HASH,
        facts=extract(text),
    )


def extract(text: str) -> tuple[IntegrityFact, ...]:
    """Apply every category in policy order, claiming text as it goes."""
    claimed = bytearray(len(text))
    found: list[IntegrityFact] = []

    for kind, pattern in _COMPILED:
        for match in pattern.finditer(text):
            start, end = _trim(kind, text, match.start(), match.end())
            if start >= end:
                continue
            # A later category never re-reads characters an earlier one took.
            if any(claimed[start:end]):
                continue
            surface = text[start:end]
            normalized = _normalize(kind, surface)
            if normalized is None:
                continue
            claimed[start:end] = b"\x01" * (end - start)
            found.append(
                IntegrityFact(
                    start=start, end=end, kind=kind, surface=surface, normalized=normalized
                )
            )

    # Sorted rather than left in category order: the snapshot should read in
    # document order, and the sort key is total, so two runs cannot differ.
    return tuple(sorted(found))


def _trim(kind: str, text: str, start: int, end: int) -> tuple[int, int]:
    """Give back sentence punctuation a greedy pattern took.

    Only trailing, only for the kinds that run to a token boundary, and never
    into the match: `report.md` keeps its extension because the dot is not last.
    """
    if kind not in _TRIMMED_KINDS:
        return start, end
    while end > start and text[end - 1] in _TRAILING_PUNCTUATION:
        end -= 1
    return start, end


# ── Normalisation ──────────────────────────────────────────────────────────


def _normalize(kind: str, surface: str) -> Optional[str]:
    """The comparison identity for one matched surface.

    Returning `None` rejects the match outright, which is how a pattern that is
    right about the shape but wrong about the content declines to claim text.
    """
    handler = _NORMALIZERS.get(kind)
    return handler(surface) if handler else _collapse(surface)


def _collapse(surface: str) -> str:
    return _WHITESPACE.sub(" ", surface.strip())


def _digits(surface: str) -> str:
    """A number's value, independent of thousands separators and a leading `+`.

    `1,000.25` and `1000.25` are the same quantity. `+3` and `3` are the same
    quantity; `-3` is not, so the minus survives.
    """
    cleaned = surface.replace(",", "").strip()
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if "." in cleaned:
        # Trailing zeros after a decimal point do not change the value, but
        # they do change how precise the writer claimed to be, so they are kept.
        return cleaned
    return cleaned


def _normalize_number(surface: str) -> str:
    return _digits(surface)


def _normalize_percentage(surface: str) -> str:
    """Every spelling of a percentage becomes `<value>%`."""
    match = _NUMBER_RE.search(surface)
    value = _digits(match.group(0)) if match else surface
    return f"{value}%"


def _normalize_currency(surface: str) -> Optional[str]:
    """`<CODE> <value>`, so symbol and amount are both part of the identity.

    Changing `£` to `$` leaves the digits untouched and changes the amount
    entirely, which is precisely why the currency is not merely decoration on a
    number.
    """
    match = _NUMBER_RE.search(surface)
    if match is None:
        return None
    value = _digits(match.group(0))

    remainder = (surface[: match.start()] + surface[match.end():]).strip()
    code = CURRENCY_SYMBOLS.get(remainder)
    if code is None:
        upper = remainder.upper()
        code = upper if upper in CURRENCY_CODES else None
    if code is None:
        return None
    return f"{code} {value}"


def _normalize_measurement(surface: str) -> Optional[str]:
    """`<value> <unit>`, with the unit's case preserved.

    Whitespace between the number and the unit is not meaningful — `5mg` and
    `5 mg` are one dose — but the unit itself is left exactly as written. See
    the note in `policy.UNITS` on why case is not folded here.
    """
    match = _NUMBER_RE.match(surface.strip())
    if match is None:
        return None
    value = _digits(match.group(0))
    unit = surface.strip()[match.end():].strip()
    if not unit:
        return None
    return f"{value} {unit}"


def _normalize_negation(surface: str) -> str:
    """Every negation marker becomes one token.

    The invariant is the presence and count of negation, not its wording:
    `must not` becoming `must` is the failure this exists to catch, and `not`
    becoming `never` is not.
    """
    return "NEG"


def _normalize_lower(surface: str) -> str:
    return _collapse(surface).lower()


def _normalize_exact(surface: str) -> str:
    """Kept character for character. Used where any difference is a difference."""
    return surface


_NORMALIZERS = {
    "number": _normalize_number,
    "percentage": _normalize_percentage,
    "currency": _normalize_currency,
    "measurement": _normalize_measurement,
    "negation": _normalize_negation,
    "modal": _normalize_lower,
    "comparator": _normalize_lower,
    "time": _normalize_lower,
    "cve": _normalize_lower,
    "uuid": _normalize_lower,
    "hash": _normalize_lower,
    # Addresses, paths, versions and dates are identities in their own right.
    # A single changed character is a different thing, so nothing is folded.
    "url": _normalize_exact,
    "email": _normalize_exact,
    "path": _normalize_exact,
    "version": _normalize_exact,
    "date": _collapse,
}
