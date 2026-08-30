# Style transformations

Phase 7 measures a document. Phase 8 decides what those measurements mean for a
chosen kind of prose. Phase 9 is the first phase in which any of that may
*suggest a change* — and the distinction it turns on is the one worth stating
first.

| | safe-fix | style-fix |
|---|---|---|
| What it is | a change believed to preserve meaning under stated conditions | a preference relative to a chosen style profile |
| Needs a profile | no | **yes, explicitly** |
| Needs a diagnostic | no | **yes** — and one that fired under that profile |
| May be applied automatically | yes | **never** |
| Where it lands in a plan | `accepted` | `review_required` |

A style preference must never silently become an automatic edit because a
profile says the prose is repetitive. Everything below exists to make that
guarantee structural rather than remembered.

## What a style fix is

Eight rules, all substitutions of one exact phrase for one exact phrase of the
same discourse class. Nothing is deleted, nothing is reordered, and no sentence
changes shape.

| rule | replaces | with | trigger |
|---|---|---|---|
| `PS.STYLEFIX.001` | `Nevertheless,` | `Even so,` | repeated transition |
| `PS.STYLEFIX.002` | `Nonetheless,` | `Even so,` | repeated transition |
| `PS.STYLEFIX.003` | `Conversely,` | `By contrast,` | repeated transition |
| `PS.STYLEFIX.004` | `Subsequently,` | `After that,` | repeated transition |
| `PS.STYLEFIX.005` | `For instance,` | `For example,` | repeated transition |
| `PS.STYLEFIX.006` | `Likewise,` | `Similarly,` | repeated transition |
| `PS.STYLEFIX.007` | `In addition,` | `Also,` | transition density |
| `PS.STYLEFIX.008` | `That said,` | `Even so,` | transition density |

Diagnostic and transformation identities are kept apart on purpose.
`PS.STYLE.REPEATED_TRANSITION` observes; `PS.STYLEFIX.001` proposes. A reader
should never have to work out which kind of thing they are looking at.

## Four rules that were written and deleted

The first draft of this family had rules for `Furthermore,`, `Moreover,`,
`Additionally,` and `Consequently,`. Every one was permanently superseded.

Phase 6's glossary migration already ships `PS.LEXICAL.161`, `.183`, `.103` and
`.122`, which replace exactly those words **automatically** as safe fixes. Mode
precedence means a style proposal covering the same characters loses every time,
so those four rules could not have produced a single review item on any document
ever.

Four rules that always lose is worse than four rules that do not exist, so they
were removed rather than shipped as evidence of effort.
`test_no_style_fix_duplicates_an_existing_safe_fix` is what stops them coming
back: it compares every style-fix surface against every automatic one and fails
on an overlap.

## What is deliberately not here

Phase 9 is the first slice, and the boundary is drawn where mechanical
justification runs out rather than where ambition does.

- **No register changes.** `However,` → `But`, `Therefore,` → `So`,
  `Hence,` → `So` are all common advice and all shift formality in a way a
  specification or a scholarly argument would not want. A test asserts no
  replacement begins with `but`, `so`, `and`, `yet` or `though`.
- **No synonym roulette.** No `robust → strong / solid / reliable`. Vocabulary
  overuse stays diagnostic-only: a synonym can change meaning even where every
  integrity fact is preserved, and picking between three of them is a decision
  nobody has made.
- **No repeated-opener rewriting.** "Seven sentences begin with *The system*"
  does not tell an engine how to rewrite seven sentences. `It…`, `This…`, `The
  application…` produced mechanically would be guessing.
- **No sentence-length variation.** Nothing splits or joins a sentence to
  improve variance. Sentence uniformity remains a diagnostic.
- **No paragraph restructuring.** Nothing moves a sentence between paragraphs.
  Paragraph uniformity, lexical overlap and list dominance stay diagnostics.
- **No ambiguous connectives.** `Meanwhile` is sometimes temporal and sometimes
  contrastive, and no single replacement covers both readings.
- **No deterministic variation.** A rule has one replacement. Where several
  alternatives might genuinely help, that is a later phase with its own contract,
  not a hash-selected choice made here.

## The gate

A style fix may propose something only when **all four** hold:

1. **A profile was named.** `plan_style_changes(document, profile="natural")`.
   There is no default. Passing `None` raises rather than falling back, because a
   configuration typo that analysed a specification against conversational
   expectations would produce a review queue that looked entirely normal and was
   answering the wrong question.
2. **The Phase 7 baseline is not a profile.** It measures. It represents nobody's
   intent and carries three known sealed false positives, so it cannot authorise
   an edit.
3. **The rule's trigger diagnostic fired under that profile.** Not under the
   baseline, not under a different profile.
4. **That finding named the rule's evidence label.** A rule for "nevertheless"
   has nothing to say about a finding about "in addition".

A style rule holds a phrase, a replacement, a trigger and a reason. It has no
threshold, no minimum sample and no measurement, so there is nothing in it that
*could* disagree with the style layer. That is the point: a rule that recomputed
the document-level condition would be a second style detector hiding inside the
transformation engine.

The planner does need the connective distribution to work out how many changes
are required, and it gets it by calling `style.patterns.transition_hits` — the
same function the diagnostic used. One tokeniser, so there is nothing to
disagree about.

## How many, and which

The document says the top connective accounts for six of seven. The profile says
0.70 and above is a finding. How many must change?

The answer is simulated, never estimated. For each *k* the resulting
distribution is built and measured against the profile's own line, and the first
*k* below it is the answer:

```
6 of 7  = 0.857   fires
k=1  →  5 of 6 = 0.833
k=2  →  4 of 5 = 0.800
k=3  →  3 of 4 = 0.750
k=4  →  2 of 3 = 0.667   below 0.70  →  four proposals
```

**Which four?** The **last** four in source order. The earliest uses established
the connective; the later ones are the repetition. Source order is a total order
over a fixed document, so this is deterministic without reference to hashing,
dictionary iteration or anything a platform could vary.

**One budget per finding, not per rule.** `signposted.md` contains both
`In addition,` and `That said,`, and either substitution alone brings the density
under the plain profile's line. Two rules each deciding independently that they
needed one change would ask a reviewer to approve an edit that was not needed, so
the budget is computed once for the finding and drawn down by rules in ID order.

**When it cannot be settled, there are no proposals.** If no *k* brings the
document under the line, the correct result is a diagnostic. Proposing a handful
of changes that would not resolve anything is worse than proposing none.

**A per-diagnostic cap of 25** stops a long document becoming a review queue.
It is versioned behaviour, bound into the plan, and disclosed in the audit
whenever it bites — nothing dropped is hidden.

## Cross-profile contrast

The proof that Phase 8 is actually governing Phase 9.

`tests/style/stylefix/signposted.md` measures **0.2027** transition density.

| profile | line | reading | proposals |
|---|---|---|---|
| plain | 0.20 | notice | **1** |
| technical | 0.20 | notice | **1** |
| government | 0.20 | notice | **1** |
| natural | 0.24 | quiet | 0 |
| academic | 0.30 | quiet | 0 |

Same prose. Byte-identical metrics — asserted. Different profile, different
answer.

## Review

Nothing is applied without a person.

```
style proposal
     │  integrity preflight, in the planner
     ▼
review_required          ← a first-class state, not a refusal
     │  ReviewSubmission(plan_hash, decisions)
     ▼
approved                 ← freshness: every authority still what it was?
     │
     ▼  whole-document integrity revalidation
applied
```

**Proposal IDs** are derived from content only: rule ID and version, source span,
the text now, the replacement, the trigger diagnostic, and the profile's ID and
hash. No clock, no counter, no iteration order. The same document under the same
profile produces the same identifiers on every platform, which is what makes a
stored decision meaningful. Two profiles produce *different* IDs for the same
edit, so a decision cannot cross between them.

**The plan hash** covers every authority: the document, the ruleset, the
integrity policy, morphology, the style policy, the profile pack and the selected
profile — plus every proposal in order. A submission names one, and approval
re-derives all of them from live state and refuses on any drift. Approving
"replace this *Nevertheless*" under the natural profile does not authorise the
same edit after somebody adjusts a threshold, because the thing that was approved
no longer exists.

**Decisions are `accept` or `reject`.** There is deliberately no `edit`:
free-form replacement text would be a new proposal nobody validated,
integrity-checked or bound to a plan.

**Batches are atomic.** One unknown proposal, one contradictory pair, one stale
authority, and the whole submission is refused. A reviewer who sent five
decisions and got three applied would have no way to know which two.

**`review_required` is not `applicable = false`.** A valid suggestion awaiting
judgement and one the engine rejected are different things, and a review
interface that could not tell them apart would be useless.

## Safety

**Integrity outranks approval.** A person saying yes changes whether a change is
wanted, not whether it is safe. The firewall runs twice: once per proposal in the
planner, so a reviewer is never shown a change it would refuse; and once over the
whole finished document before anything is written, because two individually
harmless edits can combine. There is no `ignore_integrity`, no `--unsafe`, and a
test walks every function signature in the package looking for one.

**Protected terms outrank profile preference.** A style fix runs through the
transformation planner's own `_protected_regions` and `_inherited_protection` —
the same code, not a second implementation that agrees today. For technical and
public-service prose especially, the repeated official term is very often the
correct one, and no profile can decide otherwise.

**Mode precedence is explicit**, and priority is never consulted across modes:

```
protected  >  safe-fix  >  style-fix  >  diagnostic
```

A style rule cannot displace a safe fix by declaring a bigger priority number.
Where the two cover the same characters the safe fix wins and the style proposal
is recorded as superseded, with the reason — not silently dropped, because a
reviewer wondering where a suggestion went deserves an answer.

**Losers do not resurrect.** One planner pass, one conflict resolution. If a
winner later fails integrity, the proposal it beat does not quietly return.

## Effectiveness

For every applied change, the triggering diagnostic is re-measured and must not
be worse. Measured against that diagnostic only — there is still no aggregate
style score, and inventing one to report an improvement against would be the
exact failure Phase 7 refused.

| fixture | profile | diagnostic | before | after |
|---|---|---|---|---|
| `concessive-heavy.md` | natural | repeated transition | 0.857 (notice) | quiet |
| `signposted.md` | plain | transition density | 0.203 (notice) | quiet |

**Idempotence** is at the exact-proposal level. An applied change does not come
back. Where a document is still above the line, new proposals for *other*
occurrences are legitimate and expected, and the two cases are tested
separately.

## Calibration

Run across both existing corpora — 30 documents, five profiles, 150 combinations.
**Zero style proposals.** Every profile-corpus document is quiet under the
profile it was written for, and `transition_heavy.md` is the only calibration
document any rule matches at all — where every proposal is superseded by the
existing safe fix for "furthermore".

That is the right result. The Phase 8 corpus was written to be well-suited to its
registers, and a style suggestion on a document the style layer considers quiet
would mean the gate had failed open.

Two Phase 9 fixtures carry the positive cases, in `tests/style/stylefix/`.

## A performance defect this phase exposed

`load_ruleset()` was uncached and cost about 520 ms — 222 rules of YAML parsed
and validated on every call. Nothing called it often enough to notice: the
transformation planner takes a ruleset once per document.

Style planning takes one per document *per profile*, so comparing five profiles
paid two and a half seconds of parsing to answer a question the first load had
already answered. The bundled tree is now loaded once per process. It is a pure
function of an immutable directory, an explicit `root` is still never cached
because that directory's contents genuinely can change, and the full test suite
went from 241 seconds to 48 — faster than before this phase added anything.

## Identity

| | before | after |
|---|---|---|
| Ruleset | 2026.2 / `e5aaf376077a` / 214 rules | **2026.3 / `7eddd0710ec1` / 222 rules** |
| Integrity | 2026.1 / `21532115747c` | unchanged |
| Morphology | 2026.1 / `93fba6907f87` | unchanged |
| Style policy | 2026.1 / `bedae926205a` | unchanged |
| Profile pack | 2026.1 / `cb305d331a31` | unchanged |

The ruleset bump is deliberate: activating a mode and adding transformations
changes what the engine will do to a document. No existing rule ID was
renumbered.

The profile thresholds were **not** touched. Phase 9 consumes Phase 8 profiles;
it does not recalibrate them to make style fixes easier to trigger.

## Still true from Phase 7

No authorship claim. No aggregate score. Unprofiled Phase 7 analysis is
byte-identical, pinned by digests that predate Phase 8, and the three known
baseline false positives were **not** "fixed" here — that would move a sealed
identity, and Phase 9 is not the place.
