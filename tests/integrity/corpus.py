"""The adversarial integrity corpus.

Regression and evaluation data, project-authored. Not training data — nothing
here is learned from, and nothing about it is statistical. It is a list of
transformations somebody thought of, paired with the answer the firewall must
give.

Every case is a *pair*: a before and an after, plus the verdict required. The
`MUST_REFUSE` half is the point of the whole phase — each entry is an edit that
reads as small and changes what the document says. The `MUST_ALLOW` half is what
stops the firewall being useless: a safety layer that refused everything would
be trivially correct and would be turned off within a week.

Cases are grouped by the category they exercise so that a failure names the
detector responsible.
"""
from __future__ import annotations

from typing import NamedTuple


class Case(NamedTuple):
    """One transformation and the verdict the firewall must return."""

    category: str
    before: str
    after: str
    note: str = ""

    @property
    def label(self) -> str:
        return f"{self.category}:{self.note}" if self.note else self.category


#: Transformations that must never survive. Each one is a plausible-looking
#: edit — a digit swapped, a word dropped — that changes the meaning of the
#: sentence it appears in.
MUST_REFUSE: tuple[Case, ...] = (
    # Numbers, doses and quantities.
    Case("number", "The value is 0.5 exactly.", "The value is 5 exactly.", "decimal-point-lost"),
    Case("number", "Provide 1,000 copies.", "Provide 100 copies.", "digit-dropped"),
    Case("number", "The change was -12 points.", "The change was 12 points.", "sign-dropped"),
    Case("number", "Between 5 and 10 people.", "Between 5 and 100 people.", "upper-bound-changed"),
    Case("measurement", "Take 5 mg daily.", "Take 5 g daily.", "mass-unit-scaled"),
    Case("measurement", "Add 500 mL of water.", "Add 500 L of water.", "volume-unit-scaled"),
    Case("measurement", "Drive at 30 mph.", "Drive at 30 km/h.", "speed-unit-swapped"),
    Case("measurement", "Store at 25 °C.", "Store at 25 °F.", "temperature-unit-swapped"),
    Case("measurement", "Take 0.5 mg.", "Take 0.5 mcg.", "unit-scaled-down"),
    # Percentages.
    Case("percentage", "Growth of 14.7%.", "Growth of 14.7.", "percent-sign-lost"),
    Case("percentage", "Growth of 14.7%.", "Growth of 1.47%.", "decimal-shifted"),
    Case("percentage", "A 5 percent rise.", "A 50 percent rise.", "word-form-magnitude"),
    # Money.
    Case("currency", "The fee is £2,500.", "The fee is £25,000.", "magnitude-changed"),
    Case("currency", "The fee is £2,500.", "The fee is $2,500.", "currency-swapped"),
    Case("currency", "Pay 100 GBP.", "Pay 100 EUR.", "code-swapped"),
    Case("currency", "The fee is £2,500.", "The fee is 2,500.", "currency-dropped"),
    # Dates and times.
    Case("date", "Apply by 2026-08-29.", "Apply by 2026-08-30.", "day-changed"),
    Case("date", "Apply by 29 August 2026.", "Apply by 29 August 2027.", "year-changed"),
    Case("date", "Apply by 29/08/2026.", "Apply by 08/29/2026.", "order-swapped"),
    Case("time", "Closes at 14:30.", "Closes at 14:03.", "digits-transposed"),
    Case("time", "Closes at 4pm.", "Closes at 4am.", "meridiem-swapped"),
    Case("time", "Closes at 14:30.", "Closes at 15:30.", "hour-changed"),
    # Addresses and identifiers.
    Case("url", "See https://example.com/f?id=17", "See https://example.com/f?id=71", "query-changed"),
    Case("url", "See https://example.com/a", "See https://example.org/a", "host-changed"),
    Case("url", "See https://example.com/a", "See http://example.com/a", "scheme-changed"),
    Case("email", "Write to case@example.gov.uk.", "Write to case@example.gov.us.", "domain-changed"),
    Case("path", "Edit /etc/app/config.ini now.", "Edit /etc/app/conf.ini now.", "filename-changed"),
    Case("path", "Edit ./docs/readme.md now.", "Edit ./docs/README.md now.", "case-changed"),
    Case("version", "Affects v1.5.0 only.", "Affects v1.5.1 only.", "patch-changed"),
    Case("version", "Affects 2.0.0-beta.1.", "Affects 2.0.0-beta.2.", "prerelease-changed"),
    Case("cve", "See CVE-2026-12345.", "See CVE-2026-12354.", "digits-transposed"),
    Case(
        "uuid",
        "Reference 550e8400-e29b-41d4-a716-446655440000 applies.",
        "Reference 550e8400-e29b-41d4-a716-446655440001 applies.",
        "last-digit-changed",
    ),
    Case(
        "hash",
        "Digest 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08 verified.",
        "Digest 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a09 verified.",
        "last-digit-changed",
    ),
    # Logic. The reason this phase exists.
    Case("negation", "You must not apply after 5pm.", "You must apply after 5pm.", "must-not-lost"),
    Case("negation", "You cannot appeal.", "You can appeal.", "cannot-lost"),
    Case("negation", "You can't appeal.", "You can appeal.", "contraction-lost"),
    Case("negation", "There is no fee.", "There is a fee.", "no-lost"),
    Case("negation", "It never applies.", "It always applies.", "never-lost"),
    Case("negation", "Apply without delay.", "Apply with delay.", "without-lost"),
    Case("negation", "You may apply.", "You may not apply.", "prohibition-introduced"),
    Case("modal", "You must apply.", "You may apply.", "obligation-to-permission"),
    Case("modal", "You may apply.", "You must apply.", "permission-to-obligation"),
    Case("modal", "Applicants shall provide evidence.", "Applicants should provide evidence.",
         "obligation-weakened"),
    Case("modal", "It could happen.", "It will happen.", "certainty-raised"),
    Case("comparator", "Apply before Friday.", "Apply after Friday.", "order-reversed"),
    Case("comparator", "Provide at least 5.", "Provide at most 5.", "bound-reversed"),
    Case("comparator", "More than 10 apply.", "Fewer than 10 apply.", "direction-reversed"),
    Case("comparator", "Valid until Friday.", "Valid from Friday.", "boundary-changed"),
    Case("comparator", "Only members may vote.", "Members may vote.", "restriction-lost"),
    Case("comparator", "Unless you object, we proceed.", "If you object, we proceed.",
         "condition-inverted"),
)

#: Transformations that must survive. These are the controls: ordinary
#: rewrites, reformattings that change no value, and prose that merely looks
#: like a protected fact.
MUST_ALLOW: tuple[Case, ...] = (
    # Ordinary rewrites, of the kind the bundled rules actually make.
    Case("prose", "Staff utilise the register.", "Staff use the register.", "word-substitution"),
    Case("prose", "In order to apply, register.", "To apply, register.", "phrase-reduction"),
    Case("prose", "It is important to note that fees apply.", "Fees apply.", "framing-deleted"),
    Case("prose", "The hearing will commence at ten.", "The hearing will start at ten.",
         "verb-substituted"),
    Case("prose", "Please send additional documents.", "Please send extra documents.",
         "adjective-substituted"),
    # Reformatting that changes no value.
    Case("number", "The fee is 1,000.25 exactly.", "The fee is 1000.25 exactly.", "separator-removed"),
    Case("number", "A rise of +3 points.", "A rise of 3 points.", "plus-dropped"),
    Case("currency", "The fee is £2,500.", "The fee is £2500.", "separator-removed"),
    Case("measurement", "Give 5mg now.", "Give 5 mg now.", "spacing-normalised"),
    Case("percentage", "A 5 percent rise.", "A 5% rise.", "spelling-normalised"),
    # Capitalisation, which is not a change of meaning for word categories.
    Case("modal", "must apply", "Must apply", "sentence-capital"),
    Case("negation", "not applicable", "Not applicable", "sentence-capital"),
    # Negation reworded but preserved.
    Case("negation", "You must not apply.", "You must never apply.", "negation-reworded"),
    # Prose that only looks like a protected fact.
    Case("control", "A notable result.", "A noteworthy result.", "notable-is-not-negation"),
    Case("control", "Notably, it worked.", "Strikingly, it worked.", "notably-is-not-negation"),
    Case("control", "Nothing was found.", "Nothing was located.", "nothing-is-not-negation"),
    Case("control", "Over a decade of work.", "Over a decade of effort.", "decade-is-not-a-hash"),
    Case("control", "The problem was faced.", "The problem was met.", "faced-is-not-a-hash"),
    Case("control", "Choose yes/no on the form.", "Select yes/no on the form.",
         "slash-is-not-a-path"),
    Case("control", "The and/or clause applies.", "The and/or clause is relevant.",
         "and-or-is-not-a-path"),
    Case("control", "Well-known terms are used.", "Well-known terms are common.",
         "hyphen-is-not-a-range"),
    Case("control", "The value is 1.5 exactly.", "The value is 1.5 precisely.",
         "two-part-decimal-is-not-a-version"),
    Case("control", "A cannonball flew past.", "A cannonball sailed past.",
         "cannonball-is-not-cannot"),
)

ALL_CASES: tuple[Case, ...] = MUST_REFUSE + MUST_ALLOW
