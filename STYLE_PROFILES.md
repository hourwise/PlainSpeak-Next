# Style profiles

Phase 7 asks *what patterns does this document contain*. Phase 8 asks *how
should those patterns be read for the kind of prose the writer is aiming at*.

A specification that calls the same thing by the same name in forty places is
doing its job. The identical measurement in an essay is a writer with a tic. The
measurement does not change between those two readings — only the line it is
compared against does, and that is the entire content of a profile.

Nothing here is objective. These are five calibrated opinions about five kinds of
writing, each with its evidence attached and its weak points named, and a reader
who disagrees with one should be able to see exactly which number to argue with.

## The five

| profile | for | not for |
|---|---|---|
| **Natural** | Essays, explanatory articles, newsletters, internal writing meant to read as though a person wrote it | Specifications, statutory guidance, scholarly argument |
| **Plain** | Instructions, service pages, forms guidance — prose that must be understood on a first reading | Prose whose purpose is to be enjoyable |
| **Technical** | Specifications, runbooks, API documentation, procedures | Prose meant to persuade or be read continuously |
| **Government** | Public-service pages, eligibility guidance, procedural information | Campaign material |
| **Academic** | Research writing, scholarly analysis, extended argument | Teaching material or writing for a general audience |

**Plain and Government are not the same profile with different names.** They
share a goal and differ in what they may assume. Plain writing is addressed to a
reader who chose to read it. Public-service writing is often addressed to a
reader who has to, about something consequential, possibly at the worst moment of
their year. The measurable consequences are heavier structure, more official
terms repeated exactly because a synonym for "mandatory reconsideration notice"
does not mean the same thing, and more lists because eligibility is a set of
conditions rather than an argument.

**Natural is not the default.** During Phase 8 every profiled call requires an
explicit profile ID, and the unprofiled baseline remains available and unchanged.
If a desktop application later defaults to Natural, that should be a visible
product decision rather than something the engine does quietly.

## What a profile may change

    thresholds · minimum samples (upwards only) · whether a diagnostic is
    enabled · target metric ranges · the prose explaining any of it

## What a profile may not change

    document parsing · source mapping · ruleset semantics · protected
    terminology · the integrity policy · morphology · any authority to edit text

There is no mechanism by which a profile can weaken the integrity firewall. A
profile holds numbers and prose, and no number reaches the firewall. The loader
additionally rejects a bundled profile that so much as names `ignore_integrity`,
`unsafe`, `protected_terms` or `ruleset` — not because those keys would do
anything, but so that an attempt fails loudly instead of sitting in the tree
looking as though the mechanism exists.

Transformation fields (`replacement`, `variation`, `preferred_synonym`,
`rewrite`, `substitutions`) are rejected at any depth. A profile may say
"repeated transition threshold: 0.7". It may not say "replace furthermore with
also".

## Thresholds

Bold is a value that differs from the Phase 7 baseline. `same` means the corpus
gave no reason to move it, and the profile stores the baseline value explicitly —
there is no inheritance, so every profile states every diagnostic.

| diagnostic | baseline | natural | plain | technical | government | academic |
|---|---|---|---|---|---|---|
| `CANNED_FRAMING` | 0.25 / 0.5 | same | same | same | same | same |
| `LEXICAL_OVERLAP` | 0.6 / 0.75 | same | same | same | same | same |
| `LIST_DOMINANCE` | 0.5 / 0.7 | **0.38 / 0.6** | **0.55 / 0.75** | **0.6 / 0.78** (n≥10) | **0.58 / 0.76** | same |
| `PARAGRAPH_UNIFORMITY` | 0.2 / 0.12 | same | same | same | same | same (n≥12) |
| `REPEATED_PARAGRAPH_OPENER` | 0.4 / 0.6 | **0.36 / 0.58** | **0.55 / 0.75** | **0.5 / 0.7** | **0.52 / 0.72** | same |
| `REPEATED_PHRASE` | 0.6 / 1.2 | same | **0.8 / 1.3** | **1.0 / 1.6** | **0.85 / 1.35** | same |
| `REPEATED_SENTENCE_OPENER` | 0.35 / 0.5 | same | same | same | same | same |
| `REPEATED_TRANSITION` | 0.5 / 0.7 | **0.7 / 0.88** | **0.7 / 0.88** | **0.7 / 0.88** | **0.7 / 0.88** | **0.7 / 0.88** |
| `RHETORICAL_REPETITION` | 0.3 / 0.6 | **0.5 / 0.9** | **0.5 / 0.9** | **0.5 / 0.9** | **0.5 / 0.9** | **0.5 / 0.9** |
| `SENTENCE_UNIFORMITY` | 0.34 / 0.26 | **0.44 / 0.3** | same | **0.3 / 0.22** | same | same |
| `TRANSITION_DENSITY` | 0.2 / 0.35 | **0.24 / 0.38** | same | same | same | **0.3 / 0.45** |
| `TRIADIC_REPETITION` | 0.3 / 0.6 | **0.65 / 1.1** | **0.65 / 1.1** | **0.65 / 1.1** | **0.65 / 1.1** | **0.65 / 1.1** |
| `VOCABULARY_OVERUSE` | 3.0 / 6.0 | same | same | same | same | same |

Six of thirteen diagnostics are at the baseline in every profile, and that is a
result rather than an oversight. Overriding a threshold the corpus gives no
evidence about would produce a difference nobody could defend, so it was not
done — see *Overrides that were not made*.

## The corrections this phase found

Three rows above move in the same direction in all five profiles. Those are not
register preferences. They are **baseline thresholds the new calibration
documents showed to be wrong**, and they are worth reading separately from
everything else on this page.

Phase 7 disclosed that three diagnostics had no natural document testing them
from the quiet side and two had no calibration document at all. Closing those
gaps was a Phase 8 requirement. Closing them found that three of the five
untested thresholds were too tight.

### Repeated transition: 0.50 → 0.70

Three ordinary natural documents fire under the baseline:

| document | value | sample |
|---|---|---|
| `natural/learning-to-cook-late.md` | 0.600 | 10 |
| `natural/packing-for-the-hills.md` | 0.571 | 7 |
| `natural/allotment-year.md` | 0.500 | 10 |

None of these is repetitive prose. They are conversational and essayistic writing
in which one connective happens to be the most common of the eight or ten used.
Phase 7 could not have found this: no document in that corpus reached the
six-transition minimum from the quiet side. `transition_heavy.md` measures 1.0
and is still `strong` at 0.88.

### Rhetorical repetition: 0.30 → 0.50

The baseline rate is *occurrences × 10 ÷ sentences*, so **two** uses of one
construction across 65 sentences reaches 0.308 and fires.
`controls/ordinary-rhetoric.md` — written specifically to use these
constructions the way careful prose does — measures exactly that. Two
"whether … or" constructions in a thousand words is ordinary English.

### Triadic repetition: 0.30 → 0.65

Same arithmetic, same problem. Three three-item lists in 65 sentences measures
0.462 and fires. `academic/reading-in-the-archive.md` measures 0.253 on two of
them, which is under the line by 0.047 and only by luck.

### Why the base policy was not changed

The Phase 7 style policy is an accepted, integrated identity, and its baseline
output is pinned byte-for-byte by digests that predate this phase. Changing it
would move `bedae926…`, invalidate the Phase 7 seal and break the compatibility
guarantee that unprofiled callers keep getting the Phase 7 answer.

So the corrections live in all five profiles, and the disagreement is pinned by a
test: `test_the_baseline_still_disagrees_where_the_corpus_says_it_should` asserts
that the baseline *does* fire on `controls/ordinary-rhetoric.md` and that no
profile does. If someone corrects the base policy later, that test fails and
tells them to update this page.

This is the honest position and not a comfortable one. The baseline is known to
be over-sensitive on three diagnostics, and a caller using the unprofiled path
gets those false positives.

## Target ranges

A target range is descriptive. A value outside one is reported as *above* or
*below* the range, with the range shown. Nothing in this package calls it a
defect, and a test asserts the words "bad", "wrong", "poor", "defect",
"violation", "error" and "fail" never appear in target output — because a
document outside a range is very often a document aimed at a different reader.

| metric | natural | plain | technical | government | academic |
|---|---|---|---|---|---|
| `sentence_words_mean` | 9–18 | 5–13 | 6–16 | 5–14 | 12–28 |
| `short_sentence_rate` | 0.30–0.62 | 0.55–0.90 | 0.45–0.80 | 0.50–0.85 | 0.08–0.45 |
| `content_word_diversity` | 0.58–0.85 | 0.35–0.65 | 0.38–0.68 | 0.38–0.68 | — |
| `contraction_per_1000` | 0–80 | 0–45 | 0–8 | 0–40 | 0–5 |
| `paragraph_sentences_mean` | 2.0–4.5 | — | — | — | — |
| `words_per_heading` | — | 40–120 | — | 45–140 | — |
| `list_block_share` | — | — | 0.05–0.55 | — | — |
| `long_sentence_rate` | — | — | — | — | 0.02–0.32 |
| `punctuation_semicolon_per_1000` | — | — | — | — | 0.5–14.0 |

`content_word_diversity` is the most interesting of these. Plain, technical and
government documents measure 0.45–0.55 against 0.62–0.71 for natural prose. Low
diversity is what deliberate terminology repetition looks like when it is
measured, and it is expected in three of the five registers rather than
tolerated.

## Calibration corpus

Sixteen documents, 12,000+ words, all project-authored. Nothing is trained on
any of it; it is regression data.

| register | documents | words |
|---|---|---|
| natural | 4 | 894, 959, 1047, 1081 |
| plain | 2 | 1098, 1100 |
| technical | 2 | 1146, 1249 |
| government | 2 | 1027, 1199 |
| academic | 2 | 1037, 1097 |
| controls | 2 | 607, 703 |

Every profile has at least two documents of 1,000+ words, against Phase 7's
longest calibration source of 352.

`expectations.yaml` states what each document must and must not produce, and
what changes when it is read against a profile it was not written for. Those
expectations were written before the engine was asked, which is what lets a test
disagree with the code rather than merely freeze it.

**Every document is silent under its own profile.** Thirteen of thirteen, zero
false positives in-register.

### Gaps Phase 7 recorded, and their state now

| gap | Phase 7 | now |
|---|---|---|
| Paragraph uniformity, quiet side | 1 document over the minimum | 16 |
| List dominance, quiet side | 0 documents with any list | 8 with real lists, up to 0.395 |
| Repeated transition, quiet side | 0 documents over the minimum | 8, up to 0.600 |
| Rhetorical repetition | no calibration document | 3, one deliberately near the line |
| Triadic repetition | no calibration document | 2 |
| Longest document | 352 words | 1,249 words |

## Margins

For each override, the nearest quiet calibration document and the nearest loud
one. A threshold with nothing on one side is labelled `weakly-calibrated` in the
profile itself, appears in `plainspeak profiles explain`, and is listed below.

| profile / diagnostic | nearest quiet | line | nearest loud |
|---|---|---|---|
| natural / `SENTENCE_UNIFORMITY` | 0.651 (`conversational`) | 0.44 | 0.342 (`list_heavy`) |
| natural / `LIST_DOMINANCE` | 0.233 (`packing-for-the-hills`) | 0.38 | 0.395 (`queue-consumer`) |
| natural / `REPEATED_PARAGRAPH_OPENER` | 0.294 (`measurement-and-construct`) | 0.36 | 0.367 (`appeal-a-decision`) |
| natural / `TRANSITION_DENSITY` | 0.167 (`long_natural`) | 0.24 | 0.471 (`transition_heavy`) |
| all / `REPEATED_TRANSITION` | 0.600 (`learning-to-cook-late`) | 0.70 | 1.0 (`transition_heavy`) |
| all / `RHETORICAL_REPETITION` | 0.308 (`ordinary-rhetoric`) | 0.50 | **none** |
| all / `TRIADIC_REPETITION` | 0.462 (`ordinary-rhetoric`) | 0.65 | **none** |
| plain / `REPEATED_PARAGRAPH_OPENER` | 0.367 (`appeal-a-decision`) | 0.55 | 1.0 (`repeated_openers`) |
| plain / `REPEATED_PHRASE` | 0.467 (`appeal-a-decision`) | 0.80 | 1.408 (`vocabulary_heavy`) |
| technical / `SENTENCE_UNIFORMITY` | 0.674 (`index-rebuild-runbook`) | 0.30 | 0.244 (`uniform_cadence`) |
| technical / `LIST_DOMINANCE` | 0.395 (`queue-consumer`) | 0.60 | 0.789 (`list_heavy`) |
| technical / `REPEATED_PHRASE` | 0.397 (`index-rebuild-runbook`) | 1.00 | 1.408 (`vocabulary_heavy`) |
| government / `LIST_DOMINANCE` | 0.361 (`help-with-housing-costs`) | 0.58 | 0.789 (`list_heavy`) |
| government / `REPEATED_PHRASE` | 0.434 (`registering-a-death`) | 0.85 | 1.408 (`vocabulary_heavy`) |
| academic / `TRANSITION_DENSITY` | 0.213 (`measurement-and-construct`) | 0.30 | 0.471 (`transition_heavy`) |

The two rows with **none** in the loud column are the weakest thresholds in the
pack. Rhetorical and triadic repetition now have documents establishing where
ordinary usage sits, and nothing establishing where excessive usage begins. The
lines at 0.50 and 0.65 are roughly twice the observed ordinary rate, which is a
reasonable guess and is exactly that.

The tightest margin is natural `LIST_DOMINANCE`, where the quiet document sits at
0.233 and the loud one at 0.395 with the line at 0.38 between them — 0.015 of
clearance on the loud side. That contrast is deliberate and it is thin.

### Weakly calibrated

Diagnostics where the profile's own register has no document producing a
measurement on one side of the line:

| profile | weakly calibrated |
|---|---|
| natural | canned framing, repeated phrase, vocabulary overuse |
| plain | canned framing, lexical overlap, list dominance, repeated transition, vocabulary overuse |
| technical | canned framing, vocabulary overuse |
| government | canned framing, lexical overlap, repeated transition, vocabulary overuse |
| academic | canned framing, list dominance, repeated phrase, vocabulary overuse |

Canned framing and vocabulary overuse are weakly calibrated in every profile: no
document in either corpus, in any register, produces a measurement for either
outside the two synthetic documents built to trip them. The thresholds separate
"some" from "none", and where the line between "a reasonable amount" and "too
much" should sit is untested everywhere.

The plain and government `contraction_per_1000` upper bounds are also
weakly calibrated. Both registers measure zero in the corpus, so only the lower
bound is evidenced; the upper bounds follow plain-language and public-service
convention and have never been tested against a document that uses contractions.

## Overrides that were not made

Places where the argument was available and the evidence was not.

**Technical lexical overlap.** Sections describing related machinery share
vocabulary legitimately, which is a real argument for loosening. The technical
documents measure 0.139 against a line at 0.60 and produce no second
measurement, so nothing in the corpus tests where the line should sit. A number
was not invented.

**Plain and government sentence uniformity.** Both registers use short sentences,
and the temptation to loosen is obvious. Short is not the same as uniform: the
plain documents measure 0.557 and 0.563 and the government ones 0.476 to 0.593,
none of them near the line. No evidence, no override.

**Academic paragraph uniformity.** Scholarly paragraphs are more regular by
convention. Rather than guess at a lower threshold, the academic profile raises
the *minimum sample* from 8 to 12 — demanding more evidence is the conservative
way to express the same belief, and it cannot produce a false negative on a
document that genuinely is uniform across twelve paragraphs.

**Plain, government and technical transition density.** These registers measure
0.0 to 0.051 against a line at 0.20, which argues for tightening. There is no
loud plain or government document to calibrate a tighter line against, so the
baseline stands.

## Sources

Profile semantics are authored for this project. No proprietary style-guide text
is reproduced anywhere in the pack or in this document.

Where external guidance informed a decision it is recorded in the `provenance`
field of the specific override, and the categories are:

- `project-calibration` — a number derived from measuring this project's corpus
- `baseline-derived` — the Phase 7 value, kept because nothing moved it
- `plain-language-convention` — general plain-language practice
- `public-service-convention` — general public-service writing practice,
  including the principle that defined terms are repeated exactly
- `technical-writing-convention` — general technical documentation practice
- `academic-convention` — general scholarly writing practice
- `weakly-calibrated` — no calibration document on one side of the line

Nothing is fetched at runtime. There is no remote profile service, no online
calibration lookup, no telemetry, no model and no embeddings, and the offline
test loads the pack, resolves a profile and compares all five with sockets
denied.

## Still no score

Profiles change what is reported. They do not change whether the output can be
collapsed into a number, and it cannot.

`ProfiledAnalysis` has no field whose name contains `score`, `rating`,
`probability`, `confidence` or `likelihood`, and a test asserts none appears in
the rendered report either. What comes out is dimensional:

```
Cadence variation       within profile range
Repeated openers        strong
List density            expected
Transition density      notice
```

Every band is one measurement compared against one threshold a reader can
reproduce by hand, and the report always names the profile that produced it —
because the same document is legitimately a finding under one profile and silent
under another, and a reader needs to know which question was asked.

## Changing a threshold

1. Change the number in `plainspeak/style/profiles/bundled/<profile>.yaml` and
   update its `reason` to say which documents justify it.
2. Run `python -m pytest tests/test_profile_corpus.py`. The snapshot at
   `tests/style/profiles/profile-findings.json` will fail and name every
   document and profile whose result moved.
3. Look at the diff. If a document started producing a finding under its own
   profile, the change is wrong.
4. Regenerate the snapshot, update `PROFILE_PACK_HASH` and the per-profile hash
   in `tests/test_style_profiles.py`, and update the tables above.

Adding a calibration document is cheaper than moving a threshold, and usually the
better answer.
