# V1 acceptance review

Before 1.0.0, PlainSpeak was run over a small corpus of realistic writing and
its output was read — every automatic change, every refusal, every piece of
advice. This was a product-quality gate, not another correctness suite: the
question was not "are the tests green" but "would a new user be embarrassed by
what this says".

It was worth doing. The engine that passed 4,191 tests was rewriting
"requests are rate-limited" as "asks are rate-limited", telling people to write
"deci" instead of "make a decision", and suggesting "borrowed money" for
"leverages". The fixes are below, each with its reason and its test.

## What was run

27 documents in `tests/acceptance/corpus/`, each a few paragraphs:

| kind | documents |
|---|---|
| AI-style prose | product answer, blog introduction, summary email, "comprehensive guide", support reply, cover letter |
| technical | README install section, API reference, incident post-mortem, runbook, release notes |
| government and bureaucratic | council tax notice, benefits decision, planning decision, NHS appointment letter, HR policy |
| legal and financial | tenancy clause, insurance policy excerpt |
| short | three agent replies, a payment notification, an error message |
| already good | plain-language guide, personal essay, news report, short story |

Each went through `plainspeak analyze`, `plainspeak present` under every profile,
and the desktop application — opened, analysed, every suggestion accepted and
rejected, the revised pane compared with `present`.

## What was wrong, and what changed

### Automatic changes that broke sentences

The most serious class, because nobody reviews a SAFE change before it happens.

**Words that are as often nouns as verbs.** "Request → ask" rewrote the noun:
"requests are rate-limited" became "asks are rate-limited", "checkout requests
took 14 seconds" became "checkout asks", "requests for leave" became "asks for
leave" — four of the 27 documents. It had been in the desktop self-test since
Phase 10, which pinned "the panel approved the ask" as correct.

A probe of every safe fix for the same classes of defect then found more:

| class | examples |
|---|---|
| also a noun or adjective | "a worthwhile endeavour" → "try"; "a social construct" → "build"; "the manufacture of" → "make"; "an objective assessment" → "an goal" |
| meaning changed | "undertakes to pay" (a promise) → "does to pay"; "furnish the flat" → "give"; "compensate for" → "pay for"; "inhibit" → "prevent"; "incorporated in England" → "included"; "gratuitous violence" → "free"; "deprecated" → "outdated"; "specification" → "detail"; "empirical" → "observed"; "considerable time" → "large time"; "resilient" → "strong"; "a fundamental paradigm shift" → "a basic model shift"; "the signature verifies" → "checks" |
| grammar broken | "convene a meeting" → "meet a meeting"; "ubiquitous devices" → "everywhere devices"; "identical to" → "same to"; "collaborate with" → "work with with" |

**25 migrated safe fixes were reclassified as diagnostics** (ruleset 2026.5).
They are no longer applied. (This review said they were "still reported". They
remain in the ruleset as diagnostic rules, but `present` does not list rule
diagnostics; corrected for 1.1.0, see [LIMITATIONS.md](LIMITATIONS.md).) Each
keeps its rule ID —
see *Rule IDs* below.

**Articles.** A replacement that changes the first sound left the article
wrong: "an advantageous position" became "an helpful position". The planner now
corrects "a"/"an" as part of the same change ("a helpful position"), keeping its
capitalisation, and refuses the change where the article cannot be reached in
one span. Two replacements — "enough" and "best" — cannot follow an article at
all, so "a sufficient reason" and "an optimal choice" are refused while
"sufficient funds → enough funds" and "optimal performance → best performance"
still apply.

### Advice that was wrong

The `analyze` report and the web page show suggestions from the inherited
glossary. 527 of its entries were never turned into rules, and the report
offered all of them. Every one was read.

**71 suggestions withdrawn and 5 corrected** (`plainspeak/core/suggestions.py`,
review 2026.1). Withdrawn: the 14 entries Phase 6 had already rejected; glosses
of a common word in one specialist sense ("transition → moving to adult
services", "term → length of cover", "oral → by mouth", "premium → insurance
payment", "said → the"); words with several senses ("employ", "establish",
"determine"); suggestions that change the meaning ("apparent → clear", "to the
extent that → if", "eligible → allowed"); and parts of speech that cannot stand
in ("interface → connect"). "Landlord" and "tenant" are no longer offered
replacements: they are plain already, and in an agreement they are defined
parties. Corrected: "leverage" → "use" (it was "borrowed money"), "in
accordance with" → "in line with", "lesion" → "damaged area", "materially" →
"significantly", "specified" → "listed". The inherited glossary itself is
untouched; the review overlays it, and its hash is pinned unchanged.

**Nominalisations and hidden verbs.** Both detectors guessed a verb by stripping
a suffix. Checked across the whole pronouncing dictionary, the nominalisation
rule produced 1,061 pairs, many nonsense ("action" → "ace", "lesion" → "lee",
"version" → "vere") or a different word ("commission" → "commit",
"confidence" → "confide", "organization" → "organize"), and presented every
"-ness" and "-ity" adjective as a verb. The hidden-verb rule checked nothing:
"make a decision" was offered "deci", "provided a solution" "solu". A verb is
now suggested only from a reviewed table of 340 nouns; a noun outside it is not
called a nominalisation.

Every change to the inherited characterisation seal was attributed before it was
re-sealed: each differing line in each golden file is one of the reviewed terms
above, and nothing else moved.

### Rule IDs

Reclassifying rules exposed a defect in the migration builder: it assigned IDs
by position, so moving one rule renumbered 134 others, and an ID an audit record
had cited would silently have meant a different rule. `migration/rule-ids.json`
now binds every ID to its term for life, and a test checks it. The 25
reclassified rules keep their IDs; only their mode changed.

## What reading it found that did not change

**Profiles differ in what they report, not in what they suggest.** The six
style fixes act on repeated transitions, where all five profiles draw the same
line. That is now said plainly by the CLI, the desktop and HOW_IT_WORKS.md, and a
test keeps the statement true.

**Real documents rarely get a style suggestion.** None of the 27 produced a
REVIEW item: the style fixes need a document that leans on one connective six
or more times. The desktop's value on real prose is showing the SAFE changes,
the refusals and the style observations; the review queue is usually empty.
Recorded as a product observation for after 1.0, not changed.

**Short texts get little style feedback.** The five short documents are
reported as too short to judge on all thirteen diagnostics — correct, and said
explicitly.

**The four good documents are left alone.** No SAFE change, no REFUSED change.

**The style guard earned its place.** In two AI-style documents it withheld
"Moreover → Also" because a third "Also" opener would have made the document
read worse.

**Advice still worth a human's judgement.** "provide → give", "required →
need" and "payment" flagged as a nominalisation are reasonable prompts that do
not always fit. They are advice, never applied, and were left.

## Result

Every protected fact survived in every document. Every document presents
byte-identically twice. The desktop's revised text matched `present` for all
27. The corrected behaviour is pinned by `tests/test_acceptance_corpus.py`,
`tests/test_suggestion_review.py` and `tests/test_glossary_migration.py`.
