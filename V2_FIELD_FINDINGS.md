# Field findings from testing 1.0.0

Field testing of the published PlainSpeak 1.0.0 produced three findings. All
three are fixed in the 1.1.0 release candidate. This page records what was
found, what was changed, how far the change reaches, and the evidence that
nothing else moved.

## FIELD-001 — an unsafe SAFE rule

Published 1.0.0 presented

> In order to facilitate the completion of the task, the user should verify the configuration.

as

> To help the completion of the task, the user should verify the configuration.

`PS.LEXICAL.153`, *facilitate → help*, was an automatic SAFE rule. It is not
safe: "facilitate X" means *make X easier* and "help X" means *assist X*, so the
substitution is right only where X is something that can be assisted. Across
realistic sentences it failed almost everywhere:

| Sentence | 1.0.0 produced |
|---|---|
| facilitate the completion of the task | help the completion of the task |
| The portal facilitates access to your records. | The portal helps access to your records. |
| The new tool facilitates communication between teams. | …helps communication between teams. |
| This service facilitates the transfer of funds. | …helps the transfer of funds. |
| The chair will facilitate discussion. | The chair will help discussion. |
| The app is designed to facilitate payment. | …designed to help payment. |
| We facilitated a workshop for staff. | We helped a workshop for staff. |
| She was facilitating the meeting. | She was helping the meeting. |

No lexical pattern separates the few safe contexts ("facilitate you in") from
the rest, and a rule that tried would be a guess about grammar. The rule is now
a **diagnostic**: "facilitate" is still reported, and never rewritten. Its ID is
unchanged.

### The bounded audit

Every one of the 139 automatic rules in ruleset 2026.5 was reviewed for the same
defect shape — a context-free substitution that leaves a grammatically invalid
or materially worse sentence — and each rule that looked at risk was run on
realistic sentences. No rule was added and no new term was reviewed. 28 rules
failed and were reclassified as diagnostics (ruleset **2026.6**); each keeps its
ID.

| Defect | Rules | Example |
|---|---|---|
| Different argument structure | facilitate, comprise, constitute | "the committee comprises five members" → "makes up five members" (reversed); "constitutes a breach" → "makes up a breach" |
| A separable phrasal verb before a pronoun | reimburse, relinquish, substantiate, transcribe, expedite, effectuate, disburse, ascertain | "reimburse you" → "pay back you"; "relinquish it" → "give up it"; "ascertain it" → "find out it" |
| Different complement | cease | "cease to exist" → "stop to exist" |
| A participle that is also an adjective | augment, impair, preserve, acquire | "augmented reality" → "added to reality"; "impaired vision" → "harmed vision"; "the data was acquired" → "the data was got" |
| A sense the replacement lacks | consolidate, mitigate, validate, obligation, unilateral, contemporary, feasible | "consolidate our position" → "combine our position"; "contemporary accounts of the fire of 1666" → "modern accounts"; "It is feasible to finish" → "It is workable to finish" |
| A term of art | comprehensive, preliminary, viable, quantitative, qualitative | "comprehensive insurance" → "full insurance"; "a preliminary hearing" → "an early hearing"; "a viable pregnancy" → "a workable pregnancy"; "quantitative easing" → "numerical easing" |

The reason recorded for each is in `migration/decisions.yaml` (and, for the
hand-authored PS.LEXICAL.010, in the rule itself). A structural test now fails
if any automatic rule replaces a verb with a separable phrasal verb, the shape
behind eight of the 28.

Rules the audit checked and kept include *utilise → use*, *commence → start*,
*approximately → about*, *obtain → get*, *retain → keep*, *reside → live*,
*possess → have*, *relocate → move*, *notify → tell* and *henceforth → from now
on*; each is a regression test in `tests/test_field_findings.py`. 111 of the
220 rules are now automatic.

**Limitation carried over:** like the 25 rules the V1 acceptance review
reclassified, a reclassified migrated rule reports its base form only
("facilitate", not "facilitates").

## FIELD-003 — a three-word readability verdict

`plainspeak analyze` reported "Please check this." as consensus grade 2.0,
"Very easy", with "No significant readability barriers found." The style layer
already said such a text was too short to judge; the readability report did
not.

**The threshold.** A sample shorter than **100 words or 3 sentences** is an
*insufficient sample*; under **300 words** it is a *limited sample*. These are
the figures `core.metrics` has always used for its short-text warning, now named
constants (`MIN_SAMPLE_WORDS`, `MIN_SAMPLE_SENTENCES`, `LIMITED_SAMPLE_WORDS`) and
a pure function, `sample_status()`, so every report draws the same line. Nothing
about this sentence is special-cased.

**What a report does with it.** For an insufficient sample the console and HTML
reports keep every raw formula output, drop the interpretive labels ("Very
easy", "understood by an average 11-year-old"), say plainly that there is not
enough text to judge, and qualify "No significant readability barriers found"
— every sentence was checked, but that is too little text to call the document
easy to read. The web page shows "Not enough text" instead of a band. A limited
sample shows its short-text warning.

**Compatibility effect, decided before implementation.** The JSON report is
additive: it gains a `sample` object (`status`, `words`, `sentences`,
`minimum_words`, `minimum_sentences`, `short_text_warning`) and every existing
field keeps its name, type and value. The web API gains `sample_status`.
`plainspeak.diagnose.v1` (not yet released) gains `readability.sample_status`.
The console and HTML reports are for people and carry no layout guarantee.
`analyze()` itself is unchanged.

## FIELD-002 — piped text and the required profile

A user tried `"text" | plainspeak analyze` and `"text" | plainspeak present`
before finding `--stdin` and `--profile`. Reading standard input only when told
to is deliberate — a command that read a pipe whenever no file was named would
read the wrong thing the first time it ran in a script with an inherited stdin —
so input semantics and exit statuses are unchanged. What changed:

- when text is being piped in without `--stdin`, `analyze`, `present` and
  `diagnose` say so and show the command that works;
- `present` and `analyze` help show a `--stdin` example, and `present` says the
  profile is required and has no default.

## Behaviours field testing confirmed

Kept, with regression tests in `tests/test_field_findings.py`: file and stdin
input give the same transformation and the same input hash for the same bytes;
hashes see a terminal newline; Markdown headings, inline code, link destinations
and bare URLs survive; negation and modals survive, and Verify accepts
PlainSpeak's output for them.

## What changed in 1.0.0's outputs, and why

**`present`.** Every acceptance-corpus document, the walkthrough example and
the certification sample under all five profiles — 145 outputs — were rendered
before and after. 120 are byte-identical apart from the ruleset identity. 25
changed, all because a reclassified rule is no longer applied, and each textual
difference is exactly that substitution reverted:

| Document (all five profiles) | No longer applied |
|---|---|
| ai-blog-intro | PS.LEXICAL.010 ascertain → find out |
| ai-cover-letter | PS.LEXICAL.119 comprehensive → full |
| ai-guide | PS.LEXICAL.119 comprehensive → full (twice), PS.LEXICAL.153 facilitate → help |
| ai-product-answer | PS.LEXICAL.119 comprehensive → full, PS.LEXICAL.153 facilitate → help |
| ai-summary-email | PS.LEXICAL.119 comprehensive → full |

Unchanged: the certification sample output (`af79da49…`), the walkthrough
example (`fcfa1aa3…`) and the desktop smoke output (`ca5d5012…`).

**Pinned identities.** The ruleset hash is now `258b9e29edf4…` (2026.6). The
style-review pins moved only in their identity-bearing digests; their proposal
IDs and output hashes are unchanged. The generated-forms snapshot lost exactly
the 19 lemma rules among the 28.

**The characterisation seal.** 14 of 24 goldens changed, every change FIELD-003
and nothing else: all 14 gain the JSON `sample` object; the nine insufficient
samples replace the band and Flesch labels with the insufficient-sample block in
console and HTML; the two limited samples gain the short-text note; the three
sufficient samples change in JSON only. The analyser section of every golden is
unchanged.

**Verify.** The 97-case study was re-run without changing a case: every result
and outcome is identical, with no false acceptance. Only the receipts moved,
because they name the ruleset. A compact bundle of the highest-risk cases for
independent review is in
[validation/verify-study/REVIEW_BUNDLE.md](validation/verify-study/REVIEW_BUNDLE.md).
