"""Terms of art whose meaning must survive any transformation.

These words may still be *flagged* as difficult, with a recommendation to
define or explain them on first use. What must never happen is a
substitution: "consideration" in a contract is not "thought", and "remand"
is not "send back".
"""


# ── Protected terms of art ─────────────────────────────────────────────────
# Domain terms whose meaning must not be altered by word substitution.
# These may still be FLAGGED as difficult/jargon, with a recommendation to
# define or explain on first use, but the engine must NEVER propose a
# replacement word that changes the term's legal/clinical/financial meaning.
PROTECTED_TERMS: dict[str, str] = {
    # Legal terms of art
    "shall": "legal",
    "may": "legal",
    "consideration": "legal",
    "party": "legal",
    "execute": "legal",
    "remedy": "legal",
    "damages": "legal",
    "liable": "legal",
    "indemnify": "legal",
    "warrant": "legal",
    "negligence": "legal",
    "covenant": "legal",
    "waive": "legal",
    "construe": "legal",
    "prejudice": "legal",
    "instrument": "legal",
    "serve": "legal",
    "notice": "legal",
    "provision": "legal",
    "estate": "legal",
    "deemed": "legal",
    "material": "legal",
    "notwithstanding": "legal",
    "heretofore": "legal",
    "thereto": "legal",
    "hereunder": "legal",
    "thereunder": "legal",
    "forthwith": "legal",
    "thereby": "legal",
    "hereby": "legal",
    "herein": "legal",
    "thereof": "legal",
    # Medical/clinical terms of art
    "acute": "medical",
    "chronic": "medical",
    "negative": "medical",
    "positive": "medical",
    "stable": "medical",
    "expired": "medical",
    "gross": "medical",
    "occult": "medical",
    "frank": "medical",
    "guarded": "medical",
    "labile": "medical",
    "refractory": "medical",
    "adverse": "medical",
    "titrate": "medical",
    "dose": "medical",
    "indicated": "medical",
    "contraindicated": "medical",
    "administer": "medical",
    "medication": "medical",
    "dosage": "medical",
    "significant": "medical",
    # Financial terms of art
    "principal": "financial",
    "securities": "financial",
    "maturity": "financial",
    "interest": "financial",
    "accrue": "financial",
    "default": "financial",
}


def is_protected_term(word: str) -> bool:
    """Check if a word is a protected domain term of art."""
    return word.lower() in PROTECTED_TERMS


def get_protected_domain(word: str) -> str:
    """Get the domain tag for a protected term."""
    return PROTECTED_TERMS.get(word.lower(), "")
