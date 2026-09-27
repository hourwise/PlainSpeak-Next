"""The reviewed suggestion glossary: what `analyze` may recommend to a reader.

`glossary.py` is the vocabulary inherited from the original project, kept byte
for byte as the record of what was inherited. The declarative ruleset reviewed
140 of its entries into automatic changes (see GLOSSARY_MIGRATION.md); the rest
were never used for automatic changes, but the readability report still showed
every one of them as advice — including suggestions that are wrong in ordinary
prose. "Leverages" was offered "borrowed money". "Transition" was offered
"moving to adult services". "Oral" was offered "by mouth".

This module is the review of what the report may say. It does not edit the
inherited data. It withdraws suggestions that are wrong in ordinary use and
corrects a few where a right one exists, and `EFFECTIVE_GLOSSARY` and
`EFFECTIVE_SIMPLE_WORD_MAP` are what every consumer reads. A withdrawn term
is no longer offered a replacement; a long word is still flagged as long.

The review read all 527 entries the migration did not turn into rules or
protect: 477 never individually reviewed, 36 judged diagnostic, 14 rejected.
Most are sound advice for a person — jargon glossed into plain words, which is
what a readability report is for. Those below are not, and each says why.

Versioned and hashed like every other policy: a change here changes what users
are told, so it changes the identity.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from .glossary import GLOSSARY, SIMPLE_WORD_MAP

SUGGESTION_REVIEW_VERSION = "2026.1"

# Why a suggestion was withdrawn. Kept as short, stable labels so the record
# can be read as a table.
DOMAIN = "glosses a common word in one specialist domain's sense"
SENSES = "the word has several common senses and the suggestion fits only one"
MEANING = "the suggestion changes what the sentence says"
GRAMMAR = "the suggestion is a different part of speech, so it cannot stand in the word's place"
REJECTED = "rejected in the Phase 6 glossary migration as a wrong gloss"
PLAIN = "already plain, and in an agreement usually a defined party that must not be renamed"

#: Terms whose inherited suggestion is withdrawn, and why.
WITHDRAWN: dict[str, str] = {
    # Rejected by the Phase 6 migration, but still shown by the report until now.
    "benign": REJECTED,
    "certiorari": REJECTED,
    "demurrer": REJECTED,
    "dispositive": REJECTED,
    "estoppel": REJECTED,
    "executory": REJECTED,
    "gravamen": REJECTED,
    "hmrc": REJECTED,
    "laches": REJECTED,
    "meritorious": REJECTED,
    "probative": REJECTED,
    "scienter": REJECTED,
    "subrogation": REJECTED,
    "supersedeas": REJECTED,
    # One domain's sense, offered as the meaning of an everyday word.
    "capacity": DOMAIN,          # -> "ability to make decisions"
    "commodity": DOMAIN,         # -> "raw material"
    "deductible": DOMAIN,        # -> "excess"
    "derivative": DOMAIN,        # -> "contract based on another asset"
    "endorsement": DOMAIN,       # -> "change to policy"
    "equity": DOMAIN,            # -> "ownership share"
    "exclusion": DOMAIN,         # -> "what is not covered"
    "exemption": DOMAIN,         # -> "free from tax"
    "hedge": DOMAIN,             # -> "risk reduction"
    "indication": DOMAIN,        # -> "reason to use"
    "ontology": DOMAIN,          # -> "classification system"
    "oral": DOMAIN,              # -> "by mouth"
    "placement": DOMAIN,         # -> "where someone lives or stays"
    "premises": DOMAIN,          # -> "property"
    "premium": DOMAIN,           # -> "insurance payment"
    "prescribe": DOMAIN,         # -> "set"
    "protocol": DOMAIN,          # -> "set of rules"
    "redundancy": DOMAIN,        # -> "backup"
    "relief": DOMAIN,            # -> "reduction"
    "renewal": DOMAIN,           # -> "continuing your cover"
    "repository": DOMAIN,        # -> "storage location"
    "return": DOMAIN,            # -> "tax form"
    "rider": DOMAIN,             # -> "extra cover"
    "said": DOMAIN,              # -> "the"
    "submission": DOMAIN,        # -> "entry"
    "term": DOMAIN,              # -> "length of cover"
    "topical": DOMAIN,           # -> "on the skin"
    "transition": DOMAIN,        # -> "moving to adult services"
    "trauma": DOMAIN,            # -> "injury"
    "venue": DOMAIN,             # -> "location of court"
    # Several senses; the suggestion is right for only one of them.
    "determine": SENSES,         # -> "decide"; also "find out"
    "employ": SENSES,            # -> "use"; also "hire"
    "establish": SENSES,         # -> "set up"; also "prove"
    "intimate": SENSES,          # -> "hint"
    "negotiate": SENSES,         # -> "discuss"; negotiating is not discussing
    "remit": SENSES,             # -> "send"; also a noun, "scope"
    "render": SENSES,            # -> "make"; "render assistance" is not "make assistance"
    "sustain": SENSES,           # -> "support"; also "suffer"
    "underlying": SENSES,        # -> "basic"
    "yield": SENSES,             # -> "return"
    # The suggestion changes what the sentence says.
    "apparent": MEANING,         # -> "clear"; "apparent" can mean only seeming
    "the reason for": MEANING,   # -> "why"
    "to the extent that": MEANING,  # -> "if"; extent is not condition
    "in the process of": MEANING,   # -> "being"
    # A different part of speech.
    "individual": GRAMMAR,       # -> "person"; "individual cases"
    "implementation": GRAMMAR,   # -> "setup"
    "interface": GRAMMAR,        # -> "connect"; usually a noun
    "palliative": GRAMMAR,       # -> "comfort care"
    "permit": GRAMMAR,           # -> "let"; also a noun, "a permit"
    "providing": GRAMMAR,        # -> "giving"; "providing that" means "if"
    "therapeutic": GRAMMAR,      # -> "treatment"
    # Found by the V1 acceptance corpus.
    "cache": DOMAIN,             # -> "temporary storage"; the technical term has no plainer equal
    "eligible": MEANING,         # -> "allowed"; eligible means you qualify, not that you may
    "landlord": PLAIN,           # -> "property owner"
    "operational": SENSES,       # -> "working"; "operational costs" are not "working costs"
    "tenant": PLAIN,             # -> "renter"
    # An inflected form the stemmer sends to an entry whose suggestion does
    # not fit it: "substantially" was offered the adjective "large".
    "substantially": GRAMMAR,
}

#: Terms whose inherited suggestion is replaced: `{term: (suggestion, explanation)}`.
CORRECTED: dict[str, tuple[str, str]] = {
    "leverage": ("use", "As a verb, 'leverage' usually just means use or make use of."),
    "in accordance with": ("in line with", "A plainer phrase with the same meaning."),
    "lesion": ("damaged area", "A plain description a reader can picture."),
    "materially": ("significantly", "The everyday word for the same degree."),
    "specified": ("listed", "Says the same thing in an everyday word."),
}


def _effective_glossary() -> dict[str, tuple[str, str]]:
    effective = {term: entry for term, entry in GLOSSARY.items() if term not in WITHDRAWN}
    for term, entry in CORRECTED.items():
        if term in GLOSSARY:
            effective[term] = entry
    return effective


def _effective_simple_word_map() -> dict[str, str]:
    effective = {term: word for term, word in SIMPLE_WORD_MAP.items() if term not in WITHDRAWN}
    for term, (word, _) in CORRECTED.items():
        if term in SIMPLE_WORD_MAP:
            effective[term] = word
    return effective


#: What the report, the lexicon and the inherited substitution engine read.
EFFECTIVE_GLOSSARY: dict[str, tuple[str, str]] = _effective_glossary()
EFFECTIVE_SIMPLE_WORD_MAP: dict[str, str] = _effective_simple_word_map()


def review_document() -> dict:
    """The review as canonical data: every decision, and the data it applies to."""
    return {
        "suggestion_review_version": SUGGESTION_REVIEW_VERSION,
        "withdrawn": {term: WITHDRAWN[term] for term in sorted(WITHDRAWN)},
        "corrected": {term: list(CORRECTED[term]) for term in sorted(CORRECTED)},
        "noun_verbs": {noun: NOUN_VERBS[noun] for noun in sorted(NOUN_VERBS)},
        "same_form_verbs": sorted(SAME_FORM_VERBS),
    }


def _digest(value) -> str:
    rendered = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def review_hash() -> str:
    """SHA-256 of the review decisions."""
    return _digest(review_document())


def inherited_glossary_hash() -> str:
    """SHA-256 of the inherited vocabulary, which this module never edits."""
    return _digest({"glossary": GLOSSARY, "simple_word_map": SIMPLE_WORD_MAP})


def effective_glossary_hash() -> str:
    """SHA-256 of what the report may actually suggest."""
    return _digest({"glossary": EFFECTIVE_GLOSSARY, "simple_word_map": EFFECTIVE_SIMPLE_WORD_MAP})


def reviewed_suggestion(term: str) -> Optional[tuple[str, str]]:
    """The suggestion for an exact term after review, or None."""
    if term in EFFECTIVE_GLOSSARY:
        return EFFECTIVE_GLOSSARY[term]
    if term in EFFECTIVE_SIMPLE_WORD_MAP:
        return (EFFECTIVE_SIMPLE_WORD_MAP[term], "A simpler word is available.")
    return None


# ── Nouns and their verbs ──────────────────────────────────────────────────
#
# The nominalisation and hidden-verb detectors used to derive a verb by
# stripping a suffix. Checked across every word in the pronouncing dictionary,
# the nominalisation rule produced 1,061 pairs and many were nonsense ("action"
# became "ace", "lesion" became "lee"), a different word ("commission" became
# "commit", "confidence" became "confide", "organization" became "organize"),
# or an adjective presented as a verb (every "-ness" and "-ity" word). The
# hidden-verb rule checked nothing at all: "make a decision" was offered
# "deci", "provided a solution" was offered "solu".
#
# A verb is now suggested only from this reviewed table, where the verb is in
# common use and means what the noun names. A noun outside it is not claimed
# to be a nominalisation.

_PAIRS = """
abandonment abandon; abatement abate; abridgement abridge; accomplishment accomplish;
accreditation accredit; achievement achieve; acknowledgement acknowledge;
acknowledgment acknowledge; acquiescence acquiesce; adaptation adapt; adherence adhere;
adjournment adjourn; adjustment adjust; admission admit; admonishment admonish;
adornment adorn; advancement advance; affirmation affirm; aggrandizement aggrandize;
alignment align; allotment allot; alteration alter; amazement amaze; amendment amend;
amortization amortize; amusement amuse; analysis analyze; annexation annex;
announcement announce; annulment annul; appearance appear; appeasement appease;
application apply; appointment appoint; apportionment apportion; approval approve;
arraignment arraign; arrangement arrange; assessment assess; assignment assign;
assumption assume; astonishment astonish; atonement atone; attachment attach;
attainment attain; augmentation augment; authorization authorize; banishment banish;
bereavement bereave; bewilderment bewilder; bombardment bombard;
categorization categorize; centralization centralize; characterization characterize;
choice choose; clarification clarify; coalescence coalesce; cohabitation cohabit;
colonization colonize; commencement commence; commendation commend;
commercialization commercialize; commitment commit; comparison compare;
complaint complain; completion complete; compliance comply; concealment conceal;
condemnation condemn; confinement confine; confirmation confirm;
confrontation confront; connivance connive; consideration consider; consignment consign;
consultation consult; containment contain; continuance continue; contravention contravene;
contribution contribute; contrivance contrive; convalescence convalesce; convergence converge;
criminalization criminalize; curtailment curtail; debasement debase;
decentralization decentralize; decision decide; decriminalization decriminalize;
deferment defer; deforestation deforest; deformation deform; deliberation deliberate;
delivery deliver; demonstration demonstrate; deployment deploy; deportation deport;
derailment derail; description describe; detachment detach; determination determine;
diminishment diminish; disagreement disagree; disappearance disappear;
disappointment disappoint; disbarment disbar; disbursement disburse; discernment discern;
discontinuance discontinue; discouragement discourage; discussion discuss;
disembarkation disembark; disengagement disengage; disfigurement disfigure;
disillusionment disillusion; dismantlement dismantle; displacement displace;
distribution distribute; divergence diverge; divestment divest; dramatization dramatize;
embarkation embark; embarrassment embarrass; embellishment embellish;
embezzlement embezzle; emergence emerge; emission emit; employment employ;
empowerment empower; enactment enact; encirclement encircle; encouragement encourage;
encroachment encroach; endangerment endanger; endorsement endorse; endowment endow;
enforcement enforce; engagement engage; enhancement enhance; enjoyment enjoy;
enlargement enlarge; enlistment enlist; enrichment enrich; enrollment enroll;
enrolment enrol; enslavement enslave; entanglement entangle; enticement entice;
entrapment entrap; entrenchment entrench; equalization equalize; estrangement estrange;
evaluation evaluate; examination examine; excitement excite; exhortation exhort;
expectation expect; experimentation experiment; explanation explain; exploitation exploit;
extinguishment extinguish; failure fail; fermentation ferment; flirtation flirt;
formalization formalize; formation form; fragmentation fragment; fulfilment fulfil;
fulfillment fulfill; furtherance further; generalization generalize; globalization globalize;
guidance guide; harassment harass; harmonization harmonize; hospitalization hospitalize;
identification identify; immunization immunize; impairment impair; impeachment impeach;
implantation implant; implementation implement; importation import; impoundment impound;
impoverishment impoverish; imprisonment imprison; improvement improve;
improvisation improvise; incitement incite; indentation indent; indictment indict;
inducement induce; indulgence indulge; industrialization industrialize; infestation infest;
infringement infringe; inquiry inquire; inspection inspect; installation install;
interference interfere; internment intern; interpretation interpret; intervention intervene;
introduction introduce; investigation investigate; investment invest; involvement involve;
issuance issue; judgement judge; judgment judge; legalization legalize;
liberalization liberalize; limitation limit; localization localize; manifestation manifest;
marginalization marginalize; maximization maximize; measurement measure;
mechanization mechanize; minimization minimize; misinterpretation misinterpret;
mismanagement mismanage; misrepresentation misrepresent; misstatement misstate;
mistreatment mistreat; mobilization mobilize; modernization modernize;
modification modify; monopolization monopolize; nationalization nationalize;
naturalization naturalize; neutralization neutralize; normalization normalize;
notification notify; nourishment nourish; observation observe; observance observe;
omission omit; optimization optimize; orientation orient; overpayment overpay;
overstatement overstate; participation participate; payment pay; permission permit;
personalization personalize; placement place; polarization polarize;
popularization popularize; postponement postpone; prediction predict; preparation prepare;
prepayment prepay; presentation present; privatization privatize; procurement procure;
production produce; pronouncement pronounce; proposal propose; protection protect;
provision provide; punishment punish; radicalization radicalize; readjustment readjust;
reaffirmation reaffirm; realignment realign; realisation realise; realization realize;
reappearance reappear; reappointment reappoint; rearrangement rearrange;
reassessment reassess; reassignment reassign; recommendation recommend;
reconsideration reconsider; recruitment recruit; redeployment redeploy;
redevelopment redevelop; reduction reduce; reenactment reenact; reference refer;
refinement refine; reforestation reforest; refurbishment refurbish;
reimbursement reimburse; reinforcement reinforce; reinstatement reinstate;
reinterpretation reinterpret; reintroduction reintroduce; reinvestment reinvest;
relaxation relax; reminiscence reminisce; reorganization reorganize; repayment repay;
replacement replace; replenishment replenish; representation represent;
reproduction reproduce; requirement require; reservation reserve; resemblance resemble;
resentment resent; resettlement resettle; resignation resign; response respond;
restatement restate; retirement retire; retrenchment retrench; revision revise;
revitalization revitalize; securitization securitize; segmentation segment;
selection select; socialization socialize; solicitation solicit; solution solve;
specialization specialize; stabilization stabilize; standardization standardize;
statement state; sterilization sterilize; submission submit; subsidization subsidize;
suggestion suggest; synchronization synchronize; taxation tax; temptation tempt;
transformation transform; transplantation transplant; transportation transport;
treatment treat; underpayment underpay; understatement understate; urbanization urbanize;
usurpation usurp; utilization utilize; utterance utter; verification verify;
victimization victimize; visualization visualize
"""

#: Reviewed noun -> verb pairs, for both the nominalisation and hidden-verb detectors.
NOUN_VERBS: dict[str, str] = dict(
    pair.split() for pair in (item.strip() for item in _PAIRS.replace("\n", " ").split(";"))
    if pair
)

#: Hidden-verb nouns that are already verbs: "conduct a review" -> "review".
SAME_FORM_VERBS: frozenset = frozenset({
    "attempt", "change", "check", "estimate", "increase", "look", "plan", "purchase",
    "repair", "report", "request", "review", "study", "survey", "visit",
})


def verb_for(noun: str) -> Optional[str]:
    """The reviewed verb for a noun, or None if nobody has reviewed one."""
    noun = noun.lower()
    if noun in NOUN_VERBS:
        return NOUN_VERBS[noun]
    if noun in SAME_FORM_VERBS:
        return noun
    return None
