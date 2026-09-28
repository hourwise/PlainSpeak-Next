# The Verify validation study

Before V2 could be called a release candidate, Verify was run on a controlled
corpus of real and representative transformations, and every result was
compared with a judgement made by hand. The aim was not to maximise
`ACCEPTED`. It was to find where the integrity model must say `INCONCLUSIVE` —
and above all to find any case where it said `ACCEPTED` and should not have.

The corpus, the judgements, the runner and the recorded results are in
[validation/verify-study/](validation/verify-study/). `tests/test_verify_study.py`
re-runs the whole study on every build.

## Method

**97 before/after pairs in ten classes.**

| Class | Cases | Source of the "after" text |
|---|---|---|
| plainspeak | 27 | `plainspeak present --profile natural` on every acceptance-corpus document |
| human | 10 | edits a person makes: tidying drafting, correcting (or mis-correcting) a date, reordering, bulleting, trimming |
| claude | 10 | faithful plain-language rewrites written by Claude in this session |
| chatgpt-style | 6 | written for this study to be representative of ChatGPT's habits: cheerful bullets, summaries, confident promises |
| local-model-style | 10 | written for this study to be representative of small local models' errors: number drift, a dropped negation, a changed command, truncation, a hallucinated rule |
| aggressive | 5 | aggressive simplification of legal, HR, insurance, technical and already-plain text |
| technical | 6 | API reference, runbook and release notes: wrong status code, rate limit, version; reordered bullets |
| specification | 10 | requirement prose (RFC 2119 keywords, retention rules, a release gate): weakened, reordered, equivalent and broken requirements |
| already-good | 3 | good plain text left alone, rewrapped, or "polished" |
| probe | 10 | cases written to break Verify: moved deadlines, fronted phrases, swapped values, "only" moved, capitalisation, a reversed verb |

The befores are the V1 acceptance corpus (`tests/acceptance/corpus/`) and three
specification texts written for the study (`validation/verify-study/sources/`).
**No external model was called.** The ChatGPT-style and local-model-style cases
were written to be representative of those systems and are labelled as such in
`cases.yaml`; the Claude cases were written by Claude in the session that built
Verify. That is a limitation: none is a sample of real traffic.

**Judgements came first.** Each case records whether a careful reader would say
the meaning survived (tone alone does not count), whether any change touched
something the model protects, and what changed. They were written before Verify
ran on any case and were not revised to agree with it.

**Classification.**

| Verify said | Meaning | Outcome |
|---|---|---|
| ACCEPTED | preserved | correct |
| ACCEPTED | changed | **false acceptance** — release-blocking if the change was to protected meaning |
| REFUSED | changed | correct |
| REFUSED | preserved | false refusal |
| INCONCLUSIVE | changed | caution, correctly withheld |
| INCONCLUSIVE | preserved | caution, at a cost |

## What the first run found

Under verification policy `2026.1`, as V2-A shipped it on the development branch:

| Case | Before | After | Verify | Judgement |
|---|---|---|---|---|
| **X02** | You must submit the form before 5pm and pay the fee. | Before 5pm, you must submit the form and pay the fee. | ACCEPTED | changed — the deadline now governs both actions. **Protected meaning: release-blocking.** |
| **X04** | Polish workers must register within 30 days. | polish workers must register within 30 days. | ACCEPTED | changed — a nationality became a verb |

Both came from rules that accounted for too much. The permitted move let a time
phrase cross into a sentence with two clauses, where moving it changes which
clause it governs. The capitalisation rule accepted a case change on any
sentence-initial word, which cannot tell "you"/"You" from "Polish"/"polish".

**Fixed in policy `2026.2`:**

- a comparator and its value may move only between the start and the end of a
  *single-clause* sentence whose other words are unchanged — no clause-joining
  word or mark, no other comparator, nothing else reworded;
- capitalisation is accounted for only when a word became, or stopped being, the
  first word of its sentence.

Both cases, and variants of them, are regression tests
(`tests/test_verify.py`). The single-clause fronting that the rule was written
for — X03, "You must submit the form before 5pm" / "Before 5pm, you must submit
the form" — is still accepted.

The study also improved what Verify says, not only what it decides. Refusals now
point at the occurrence that changed rather than every line containing the same
word, and an unresolved protected item is described as moved to another
sentence, moved within its sentence, or left in place while the words around it
changed — three different things a reviewer needs to tell apart.

## Final results (policy 2026.2)

| class | cases | correct | false acceptance (protected) | false acceptance | false refusal | caution (correct) | caution (cost) |
|---|---|---|---|---|---|---|---|
| aggressive | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| already-good | 3 | 2 | 0 | 0 | 0 | 0 | 1 |
| chatgpt-style | 6 | 4 | 0 | 0 | 2 | 0 | 0 |
| claude | 10 | 0 | 0 | 0 | 8 | 0 | 2 |
| human | 10 | 3 | 0 | 0 | 4 | 0 | 3 |
| local-model-style | 10 | 7 | 0 | 0 | 1 | 2 | 0 |
| plainspeak | 27 | 27 | 0 | 0 | 0 | 0 | 0 |
| probe | 10 | 2 | 0 | 0 | 0 | 8 | 0 |
| specification | 10 | 5 | 0 | 0 | 2 | 1 | 2 |
| technical | 6 | 4 | 0 | 0 | 0 | 0 | 2 |
| **all** | **97** | **59** | **0** | **0** | **17** | **11** | **10** |

- **No false acceptance**, of protected meaning or otherwise.
- Of 35 transformations that changed protected meaning, **26 were REFUSED and 9
  INCONCLUSIVE; none was ACCEPTED.**
- **All 27 PlainSpeak transformations were ACCEPTED**, each explained by the SAFE
  rules it applied.
- Of 59 transformations that preserved meaning, 32 were ACCEPTED, 17 REFUSED and
  10 INCONCLUSIVE.

### False refusals — 17

Every one comes from the integrity model's deliberate strictness, which V1 chose
and V2 inherits unchanged: a different spelling of a protected item is a
different item unless a reviewed equivalence says otherwise.

| Pattern | Cases |
|---|---|
| Comparator synonyms: "at most" / "up to", "no longer than" / "up to", "not less than" / "at least", "limited to" / "up to", "prior to" / "early" | S02, S04, C01, C06, G01 |
| Modal changes that keep the obligation: "shall" → "must", "should" → imperative, "may request" → "can ask", "will be" → "is" | H01, C01, C02, C03, C06, C10, G01, G05 |
| Protected words inside a removed stock phrase or apology ("may have caused", "do not hesitate") | H07, C05 |
| A protected word added for emphasis or style ("only", "never") | H04, C04 |
| Negation restated ("no longer freezes" → "Fixed ... freezing") | H06 |
| One "must" covering two verbs | C08 |
| Dates in another written form (`12/08/2026`) | L04 |

This is the cost of a model that fails closed, and it falls hardest on faithful
rewrites: 8 of the 10 Claude rewrites were refused. A person reviewing a
refusal can see exactly which item moved and judge it. Each pattern above is a
candidate for a *reviewed* integrity equivalence in a future integrity policy —
recorded in [ROADMAP.md](ROADMAP.md) — and none was admitted here, because
each would widen what the V1 firewall accepts.

### Where the model must say INCONCLUSIVE — 21

**Meaning changed, correctly withheld (11).** Every one is a change the model
has no category for, so it can neither refuse nor accept it:

- what a protected item applies to — a deadline moved onto another action (X01,
  X02, X05), amounts swapped between actions or days (X06, X10), "only" moved
  from members to voting (X07), a negation now applying to promotions rather
  than rollbacks (S09);
- a changed word the model does not protect — "3% above" to "3% below" (L03),
  "pay to the agent" to "receive from the agent" (X09), a nationality
  lower-cased (X04);
- an invented rule with no protected item in it (L08).

**Meaning preserved, at a cost (10).** Reordered paragraphs and instructions
(H03, S03, T03), bulleted lists (H05), reworded steps and wording around
protected items (H09, C07, T04), joined sentences (C09), "below" / "under" (S07),
and a "polish" of good text (K02). The model cannot tell these from the cases
above, and does not pretend to.

## What this establishes

1. **ACCEPTED is safe to act on in the sense VERIFY.md defines**: across 97
   cases, including ten written to break it, nothing that changed meaning was
   accepted after the fixes this study forced.
2. **REFUSED is reliable in one direction only.** Every REFUSED case really did
   change a protected item; 17 of 44 did so without changing meaning. A refusal
   says *what* changed and needs a person to judge *whether it matters*.
3. **INCONCLUSIVE is where free rewriting lands.** Most real paraphrase — by
   people and by models — either touches a protected word (and is refused) or
   rewords around protected items (and is inconclusive). Verify's value on free
   rewriting is as a precise guard on facts, not as an approver of prose.
4. **The fail-closed policy was necessary, not theoretical.** The two false
   acceptances the study found were in the two places the policy tried to be
   helpful.

## Release-candidate decision

- No false acceptance involving protected meaning remains: **not blocked**.
- V1 is unchanged: `plainspeak.present.v1` is byte-identical to 1.0.0 across 135
  outputs; every V1 command, contract, identity and pinned output is unchanged.
- **Version:** V2 adds contracts and changes none, so the recommendation is
  **1.1.0** — see [V2_SCOPE.md](V2_SCOPE.md).

## Re-run after field testing of 1.0.0

Ruleset 2026.6 reclassified 28 SAFE rules after field testing
([V2_FIELD_FINDINGS.md](V2_FIELD_FINDINGS.md)), which changes the after text of
the PlainSpeak cases. The study was re-run with no case changed: every result
and outcome is the same, still with no false acceptance; only the receipts
moved, because they name the ruleset.

The cases most worth an independent reading before release — every case judged
to change protected meaning, every acceptance that rests on a move, an
equivalence or one of PlainSpeak's SAFE rules, and the two historical false
acceptances — are collected, with exactly what changed in each, in
[validation/verify-study/REVIEW_BUNDLE.md](validation/verify-study/REVIEW_BUNDLE.md).
The judgements in the study were all written by the same agent that built
Verify; an independent human reading of that bundle is the check this study
cannot supply for itself.

That reading agreed with every Verify outcome and questioned four of the SAFE
substitutions the PlainSpeak cases were accepted on. Re-examined against every
context their matchers can reach, ten substitution families were reclassified
(ruleset 2026.7), and four more of the same shape were found alongside them;
see [V2_FIELD_FINDINGS.md](V2_FIELD_FINDINGS.md). The study was re-run again
with no case changed: every result and outcome is the same, still with no
false acceptance.

The safe-rule qualification then probed every rule still automatic and
reclassified 74 more (ruleset 2026.8; see
[SAFE_RULE_QUALIFICATION.md](SAFE_RULE_QUALIFICATION.md)). None of them had
supplied a substitution any case rests on. The study was re-run with no case
changed: every result and outcome is the same, with no false acceptance; only
the receipts moved, because each receipt names the ruleset.

## Reproducing it

```bash
python validation/verify-study/run_study.py            # the summary above
python validation/verify-study/run_study.py --check    # fail if results.json is stale
```

The runner exits 2 if any case is a false acceptance of protected meaning.
