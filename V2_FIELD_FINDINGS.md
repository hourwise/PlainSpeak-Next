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
a **diagnostic**: "facilitate" is never rewritten. Its ID is unchanged. It is
not flagged to users either: the engine matches a diagnostic rule and records
the match in its plan, but `present`, `diagnose`, the MCP tools and the desktop
application do not currently list rule diagnostics.

### The bounded audit

> **Correction (V2-F).** The claim below that every automatic rule was reviewed
> and the rest passed was too strong: the review of the Verify study found four
> rules this audit had kept that fail in exactly this way (`accordingly`,
> `consequently`, `hereafter`, `a large number of`). See *V2-F* below.

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
reclassified, a reclassified migrated rule matches its base form only
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

## V2-F — independent review of the accepted SAFE substitutions

An independent reading of
[validation/verify-study/REVIEW_BUNDLE.md](validation/verify-study/REVIEW_BUNDLE.md)
agreed with every Verify outcome, and questioned four SAFE substitutions the
PlainSpeak cases were accepted on. The principle, the same as FIELD-001's: **a
SAFE rule must be defensible across every context its matcher can actually
reach, not only the sentence that happened to exercise it.** Every substitution
the bundle lists as accepted on a SAFE rule was held to that.

**The questioned examples, run through the matcher:**

| Sentence | Reachable? | 2026.6 produced |
|---|---|---|
| The tenant must notify the authority in writing within 14 days. | yes, PS.LEXICAL.186 | must tell the authority in writing |
| The company reported £5 million in retained earnings. | yes, PS.LEXICAL.221 | kept earnings |
| The solicitor was retained by the claimant. | yes, PS.LEXICAL.221 | was kept by the claimant |
| The patient must not crush modified-release tablets. | yes, PS.LEXICAL.182 | changed-release tablets |
| The product contains genetically modified ingredients. | yes, PS.LEXICAL.182 | genetically changed |
| The policy names the landlord as an additional insured. | **no** — PS.PROTECT.002 protects the phrase and refused PS.LEXICAL.009 | unchanged |

**Every substitution the bundle listed, decided:**

| Substitution | Decision | Why |
|---|---|---|
| notify → tell (PS.LEXICAL.186) | **diagnostic** | notice is a procedure: "must notify … in writing" became "must tell" |
| retain → keep (PS.LEXICAL.221) | **diagnostic** | "retained earnings", "the solicitor was retained" |
| modify → change (PS.LEXICAL.182) | **diagnostic** | "modified-release tablets", "genetically modified" |
| additional → extra (PS.LEXICAL.009) | **diagnostic** | "additional insured" was protected, but "the additional rate" of tax, "Additional Voluntary Contributions" and "additional needs" were not |
| enhance → improve (PS.LEXICAL.147) | **diagnostic** | "an enhanced DBS check", "enhanced due diligence" |
| possess → have (PS.LEXICAL.200) | **diagnostic** | "it is an offence to possess a controlled drug" |
| in order to → to (PS.CLARITY.001) | **diagnostic** | "in order" also means arranged: "Keep your papers in order to avoid delays" became "Keep your papers to avoid delays"; "Put the files in order to find them" lost its sense |
| furthermore / moreover / additionally → also (PS.LEXICAL.161, 183, 103) | **diagnostic** | mid-sentence they became a comma-bound "also" that moves the focus: "The tenant, furthermore, must pay" became "The tenant, also, must pay", which implies someone else must too |
| utilize → use (PS.LEXICAL.001) | kept | one sense; no counterexample found |
| prior to → before (PS.CLARITY.009) | kept | matches only the preposition ("the prior agreement" is untouched); an integrity equivalence |
| commence → start (PS.LEXICAL.005) | kept | "start proceedings" is the Civil Procedure Rules' own phrase |
| It is worth noting that → ∅ (PS.FRAMING.002) | kept | removes framing only; no counterexample found |

**Found alongside, and reclassified:** repairing the style-guard tests needed
two SAFE rules that write the same sentence opener, and the obvious candidates
failed the same test — "Please act accordingly" became "Please act so" and "The
fee is accordingly waived" "The fee is so waived" (PS.LEXICAL.101); "The rent
was, consequently, increased" became "The rent was, so, increased"
(PS.LEXICAL.122); "The Company (hereafter the Seller)" became "(from now on the
Seller)" (PS.LEXICAL.164); "A large number of them were late" became "Many them
were late" (PS.CLARITY.007). They were not on the bundle's list; they are
reclassified because they are the same defect and were found, and each is
recorded so it can be revisited. They also show that the V2-E audit was not
exhaustive (see the correction above).

**Result:** ruleset **2026.7**, 220 rules, **97 automatic**; every rule keeps its
ID; `migration/rule-ids.json` is unchanged. The style-guard tests, which
needed the three connective rules to demonstrate the guard, now run on a
fixture ruleset holding exactly those rules as they were in 2026.6
(`tests/fixtures/style-guard-rules/`): the guard is a mechanism and is still
shown to hold back changes that would repeat a sentence opener.

**What changed in the outputs.** Against ruleset 2026.6, 75 of the 145 checked
`present` outputs changed (15 documents under five profiles), each only by no
longer applying one of these rules, and each textual difference is exactly that
substitution reverted; 70 are identical apart from the ruleset identity.
Against 1.0.0, the cumulative picture is the same 75 and 70, all attributed to
the 42 reclassifications. The certification sample now keeps "In order to
finish" (`6107653a…`, was `af79da49…`), and the certification script expects
the two SAFE changes that remain; the walkthrough example now makes two SAFE
changes (`e6b9106a…`, was `fcfa1aa3…`). The desktop smoke output is unchanged
(`ca5d5012…`). The style-review pins moved only in identity-bearing digests;
the generated-forms snapshot lost exactly the five reclassified lemma rules.

**Verify.** The 97-case study was re-run with no case changed: every result and
outcome is identical, with no false acceptance. The regenerated review bundle
now lists seven PlainSpeak cases accepted on SAFE rules (from thirteen), each
resting only on `utilize`, `prior to`, `commence` and the framing deletion.

**Residual risk.** This was a bounded review of the substitutions the bundle
listed. The four rules found alongside it show that the earlier audit missed
cases, so the remaining 97 automatic rules have not been shown safe in every
context their matchers can reach; they have only not been shown unsafe.

## The safe-rule qualification (ruleset 2026.8)

That residual risk is what the next step addressed. Every one of the 97 rules
still automatic in 2026.7 was probed — ordinary uses, adversarial positions
and forms, and specialist legal, financial, clinical, technical and
government sentences — and given one disposition. 23 were qualified; 74 are
diagnostics, each resting on a sentence it broke. "Henceforth", "approximately",
"obtain" and "reside", which this page's audits kept, are among them:
"The Company (henceforth the Seller)" is the defect already found in
"hereafter"; "returns approximately the square root" became "returns about the
square root"; "The same rule obtains in Scotland" became "The same rule gets
in Scotland"; "Authority resides with the board" became "Authority lives with
the board". [SAFE_RULE_QUALIFICATION.md](SAFE_RULE_QUALIFICATION.md) is the
ledger: every rule, every probe, every judgement, generated from
`validation/safe-rule-qualification/` and held to the ruleset by a test.
