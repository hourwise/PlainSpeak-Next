# Architecture

PlainSpeak Next is organised as layers with a single rule holding them
together:

> **No interface has its own engine.**

The CLI, the desktop application and the MCP server are adapters. They translate
between the outside world and `plainspeak.core`, and they contain no analysis or
rewriting logic of their own. If they did, the same document could get different
answers depending on how it was asked for — which would make the determinism
this project is built on a claim rather than a property.

`tests/test_architecture.py` enforces this. It is not documentation of intent;
it fails the build.

## The layers

```
                          adapters
                   cli · web · (desktop) · (mcp)
                              │
                              ▼
                          pipeline
    projection · analysis · planner · apply · audit · styling
                              │
       ┌───────┬───────┬───────┼───────┬────────┐
       │       │       │       │       │        │
       ▼       ▼       ▼       ▼       ▼        ▼
   document   rules   reporting  style    core    integrity
              morphology           │        ▲
   model      schema  html·json  policy   └──────┘   protected
   load       loader  console    metrics  tokenize   policy
   parse_text matcher labels     patterns metrics    extract
   parse_markdown canonical      analyze  barriers   compare
   text · html explain           model    transform
   docx · pdf  bundled/          report   lexicon
   detect                                 glossary
                                          morphology
```

Arrows are the *only* permitted directions.

| Layer | Holds | May import |
|---|---|---|
| `core` | Tokenising, metrics, barrier detection, substitution, morphology | `core`, `integrity` |
| `integrity` | What must never be changed, and the firewall that enforces it | `integrity` |
| `document` | Reading files, and the structured representation of one | `document` |
| `reporting` | Rendering results for a human or a machine | `reporting`, `core`, `integrity` |
| `morphology` | Bounded English inflection, one way only | `morphology` |
| `rules` | Declarative prose rules and deterministic matching | `rules`, `morphology` |
| `style` | Document-level style diagnostics, measured not judged | `style`, `core` |
| `pipeline` | Orchestration between documents, rules and analysis | `pipeline`, `core`, `document`, `integrity`, `rules`, `style` |
| `adapters` | Interfaces onto the engine | `adapters`, `pipeline`, `core`, `integrity`, `reporting` |

That table is not a description. `tests/test_architecture.py` parses it out of
this file and compares it against what the code actually imports, so a
documented rule and an enforced rule cannot drift apart. Changing the policy
means changing the table.

Four of those constraints are worth spelling out.

**`integrity` is a leaf on purpose.** It is the part of the system whose job is
to say "no". Anything it imported could import it back, and a cycle there would
be a cycle in the safety check itself. Keeping it dependency-free means the
protected-term register can never be circumvented by import order.

**`reporting` may read results but never compute them.** A report that
calculated its own numbers would be a second engine wearing a different hat.

**Adapters reach documents only through `pipeline`.** An adapter that read a
file itself and then called `core` would be joining parsing to analysis on its
own terms, and two adapters doing that independently is exactly how the CLI and
the MCP server end up answering the same question differently.

**`rules` is a leaf, like `integrity`.** A rule sees a string and reports
analysis coordinates. It does not parse documents, does not know what a heading
is, and cannot compute a source offset — because it has never seen one. That is
what makes it impossible for a rule to put an edit in the wrong place, and it is
worth more than any amount of care taken further down the pipeline.

**`core` does not import `document`.** The analysis engine works on strings and
knows nothing about headings, quotes or code fences. The document
representation knows all of that and nothing about readability. Letting either
depend on the other would be the convenient move, and the thing that would rot
is `core` — it would gradually acquire opinions about markup, and the markup it
knew about would gradually diverge from the markup the parser knew about. So
neither imports the other, and `pipeline` joins them. Exactly one layer is
permitted to depend on both, and a test enforces that too.

## Where the layers came from

Every module here was extracted verbatim from the flat package inherited at the
fork point — copied by AST line range rather than retyped, so that no behaviour
could change during the move. The characterisation seal
(`tests/characterisation/`) is what proves it: the same 16-document corpus
produces byte-identical output before and after the split, on all three
operating systems.

| Was | Is now |
|---|---|
| `analyzer.py` | `core/tokenize.py` + `core/metrics.py` |
| `simplifier.py` | `core/barriers.py` + `core/transform.py` + `core/lexicon.py` + `integrity/protected.py` |
| `glossary.py` | `core/glossary.py` |
| `grammar.py` | `core/morphology.py` |
| `reader.py` | `document/{text,html,docx,pdf,detect}.py` |
| `reporter.py` | `reporting/{html,json,console,labels}.py` |
| `cli.py`, `web.py` | `adapters/cli.py`, `adapters/web.py` |
| `syllable_data.py` | `core/syllables.py` |

The old paths still exist as compatibility shims that re-export from the new
locations, so external callers keep working. **Nothing inside the package may
import through a shim** — that too is enforced by a test, because a shim that
becomes load-bearing stops being a courtesy and starts being architecture.

## The document representation

`plainspeak.document.model` is where a document stops being a string.

Every node records the exact character span of the source it came from, along
with its path in the tree, the parser that produced it, and a SHA-256 of its
original text. One property does most of the work:

> **Serialising an unedited document returns the original bytes, because the
> original bytes are what it holds.**

The document keeps its full source and nodes index into it. An edit is a span
replacement; a transformation plan is a list of span replacements that can be
checked for overlap and ordered before anything is applied. Nothing has to be
reconstructed, so nothing can be reconstructed wrongly.

`Document.prose_spans()` is the engine's only licence to edit. It walks the
tree and yields the spans of `Text` nodes that are transformable *and* have no
enclosing node forbidding it — so a paragraph inside a block quote contains
perfectly ordinary prose and is still not offered up, because rewording
somebody else's words and leaving them in quotation marks misattributes them.

What is excluded, and why it is recorded rather than implied:

| Excluded | Reason |
|---|---|
| Code blocks and code spans | code is not prose |
| Block quotes | quoted material must not be reworded |
| Tables | the pipe structure is significant and the cells are not yet parsed |
| Link and image destinations | an address is not prose |
| Autolinks | the visible text *is* the address |
| Raw HTML, thematic breaks | not prose |

### Failing safe

markdown-it reports inline tokens with no source offsets, so the offsets are
recovered by scanning the block's source and locating each token in turn. That
scan can fail, and what happens then is the heart of the design: **a node whose
location cannot be established exactly is refused, not guessed at.** The
scanner latches into a lost state on the first miss and never resumes, and the
enclosing block is marked untransformable. An edit applied at a wrong offset
corrupts a document silently, which is far worse than leaving it alone.

Three constructs used to trigger that refusal for whole paragraphs and no
longer do — escapes and entities (`text_join` is disabled so their source form
survives in the token), autolinks (there is no bracket to find), and reference
links (the destination lives elsewhere in the document, so that lookup is
allowed to miss). No Markdown construct currently tested defeats the scanner,
which means the refusal path only ever runs on a parser bug. It is tested by
forcing a failure, because a safety net nobody has pulled is not known to hold.

## The analysis projection

`core` analyses strings. `document` holds a tree. Neither imports the other, so
something has to join them, and `pipeline` is the only layer allowed to.

A **projection** is the string the analyser should see, plus the bookkeeping
needed to turn any offset in that string back into an exact offset in the
original source.

```
source:    The system provides a **robust** solution.
analysis:  The system provides a robust solution.
mapping:   analysis[22:28] -> source[24:30]
```

It is deliberately not a concatenation of `Text` nodes. Analysing each node
separately would cut every sentence at each emphasis marker, and sentence
segmentation, long-sentence detection and every readability statistic would be
measuring fragments of sentences. The projection reads across inline boundaries
so that the example above is one sentence, as it plainly is.

### Two authorities, not one

`analyzable` and `transformable` answer different questions, and the case that
forces them apart is the block quote:

| | analysable | transformable |
|---|---|---|
| Ordinary paragraph | yes | yes |
| Block quote | **yes** | **no** — quoted material must not be reworded |
| Code block or span | no | no |
| Table | no | no |
| Link or image destination | no | no |
| Autolink | no | no — the visible text *is* the address |
| Raw HTML, thematic break | no | no |
| Anything the parser could not locate | no | no |

A quotation is prose. A report should be able to say it is hard to read. It
still must not be reworded, because rewording somebody else's words while
leaving them inside quotation marks misattributes them.

Both flags come from one traversal, `Document.prose_segments()`. Two traversals
would agree today and drift apart on the first node type somebody added to only
one of them — and the drift would be silent, because the symptom is the engine
editing something it should not.

### Mapping refuses rather than approximating

Every character of a projection belongs to exactly one segment, and every
segment either names its source characters or declares itself synthetic. There
is no third category, because the only alternative to an exact offset is a
wrong one.

`map_to_source` refuses when the range:

- crosses the synthetic separator inserted between blocks;
- crosses markup, so that no single source replacement is defined;
- covers only part of a **non-linear** segment — a CRLF line break is one
  character of analysis text over two of source, and `&amp;` is one ampersand
  spelled with five;
- touches anything the engine may not rewrite.

A refused mapping still carries the real source positions it *could* establish,
so a finding stays reportable and pointable-at even when no safe edit exists
for it. `applicable` is the only thing a caller may consult before proposing an
automatic change.

The same discipline applies to placing findings. The inherited detectors are
inconsistent — some record offsets within the sentence, some record only the
matched text — so both are handled, and a disagreement between them is a reason
to refuse rather than a reason to pick one. A phrase that occurs twice in its
sentence is ambiguous, and ambiguity is refused rather than resolved by
guessing.

### What this looks like in practice

One word, four settings, three answers:

| Source | Reaches the analyser | Editable |
|---|---|---|
| `Use **approximately** 5 mg.` | yes | yes — maps to the bare word, not the markers |
| ``Use `approximately` as a variable name.`` | **no** | no |
| `See [approximately](https://approximately.example).` | yes (the link text) | yes — maps inside the brackets |
| `> Use approximately 5 mg.` | yes | **no** — quoted material |

### The analysis unit

Document-level statistics are computed over `project_document`, which joins
blocks with a synthetic separator. Readability, sentence segmentation and
long-sentence detection are all document-level questions, and answering them
per block would change what the inherited engine means by every one of them.

`project_block` exists for callers that want a bounded unit — reviewing one
paragraph without paying for the whole document. Both map back to the same
source coordinates.

### Legacy compatibility

`analyze(text)` is untouched and still means exactly what it meant; the
characterisation seal holds it to that. `analyze_document(document)` is a second
path alongside it, not a redefinition. A document of nothing but code returns an
empty analysis rather than being handed to the inherited analyser, which raises
on empty input — this layer declining to ask a question, not a change to the
answer.

## The rule engine

Language behaviour used to live in Python — `if pattern: make suggestion`. It
now lives in YAML that a reviewer can read without opening a source file, and
the code is a platform for running it deterministically.

```
versioned rule data
        ↓
validated loader          a malformed rule is a build failure
        ↓
deterministic matcher     analysis coordinates only
        ↓
projection mapping        the Phase 3.5 authority
        ↓
protection                declarative, then inherited
        ↓
conflict resolution       explicit, or refuse
        ↓
immutable plan
        ↓
atomic application
```

### Rules are data, not code

`yaml.safe_load` constructs plain data — no object instantiation, no imports,
nothing reachable from a rule file. Past that, the schema accepts a fixed
vocabulary and rejects everything else, **including unknown keys**: a typo would
otherwise become a rule that quietly does something other than what it says. A
malformed bundled rule raises, and is never skipped with a warning, because a
skipped rule looks exactly like a rule that decided not to fire — the only
symptom would be prose silently not being improved.

Regex support is deliberately narrow. Backreferences, recursion, conditionals
and inline flags are rejected, as is any quantifier applied to a group that
already contains one — the classic shape of catastrophic backtracking. Patterns
are length-capped, and a regex may not drive a replacement at all, because the
matched text varies with the input and the result could not be reviewed in
advance.

### Every rule carries its own tests

The schema requires `examples.positive` and `examples.negative`, and a safe-fix
must additionally state the transformation it produces. The negative cases are
the half that matters: a rule with no stated false-positive case is a rule whose
author has not yet thought about when it should stay quiet.

`tests/test_bundled_rules.py` enforces those claims, and it earned its keep
immediately — six rules shipped with negative examples describing cases a
lexical matcher cannot actually distinguish. Two of those turned out to be
genuine limitations, now recorded in the rule descriptions rather than papered
over.

### Ruleset identity

The hash is computed over a canonical JSON rendering of the *validated rules* —
the objects the loader produced, not the text it read. It therefore cannot move
because of directory traversal order, path separators, which folder a rule was
filed under, YAML key order, quoting, comments or line endings. It does move
when a rule's published wording changes, because descriptions and reasons appear
in reports and in `explain_rule`.

Files are loaded in whatever order the filesystem offers, deliberately unsorted:
sorting there would conceal an order dependency rather than remove one. The
ruleset is sorted by rule identity afterwards, and the tests shuffle the file
list to prove that is enough.

### Nothing is applied while matching

Every rule matches against one projection of the *original* document. If a rule
saw text an earlier rule had changed, the result would depend on which order the
rules ran, and every claim to determinism would be gone. Matches are collected,
mapped and judged before a single character moves.

### Two kinds of protection, neither able to weaken the other

Declarative `protected` rules cover phrases the ruleset knows about — "informed
consent", "additional insured", "force majeure". The inherited register in
`plainspeak.integrity.protected` covers the 59 terms the project has treated as
untouchable since before rules existed. A proposal has to survive both, and the
inherited check runs against *every word* inside a proposed edit rather than
just the head word: replacing "the material fact" as a unit changes "material"
as surely as replacing it alone would.

A test asserts that no bundled safe-fix targets an inherited protected term,
because such a rule could never fire and would be dead weight in the ruleset.

### Conflicts are settled by rule, or refused

Overlapping proposals are gathered into groups, and each group is settled by a
short cascade whose every branch is total — there is no "otherwise, whichever
came first":

1. One proposal → accept it.
2. All identical → accept the lowest rule ID; the rest are duplicates.
3. Exactly one strictly highest priority → accept it.
4. Exactly one strictly containing all the others → accept the longer match.
5. Anything else → **refuse the whole group.**

Step 5 is the important one. When two rules want the same characters in
different ways and neither has been given precedence, there is no principled
answer, and picking one would make the output depend on an accident. Refusing
both leaves the document unchanged and the reader informed.

### Application is atomic

`apply_plan` checks that the plan was built against this document, that every
accepted proposal still finds the text it was made against, and that no two
accepted edits overlap — all before anything is replaced. If any check fails,
nothing is applied. Not "as much as possible": a half-applied plan is a document
in a state no rule intended and no audit record describes, with no way to tell
from the result which half ran.

The original `Document` is never mutated; application returns a new string.

### Idempotence

`fix(fix(text)) == fix(text)` is enforced for every bundled safe-fix, for each
rule's own worked example, and across the whole characterisation corpus. There
is also a direct check at the source of the problem: no rule's replacement text
may be matched by any rule in the set.

### The audit record

Canonical JSON with sorted keys, a total entry order that does not depend on
iteration, and **no timestamp anywhere in the hashed content**. The record's own
hash identifies the decision rather than the moment it was taken — otherwise two
runs over the same input would produce different audits, and the hash would be
useless for the comparison it exists to support.

## The integrity firewall

The rule engine can show that a transformation is structurally valid: it matched
a declared pattern, mapped to exact source characters, survived conflict
resolution. None of that says the transformation preserved what the document
*meant*.

```
                    proposed transformation
                             │
                             ▼
                    integrity firewall
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                     ▼
        PASS                                  REFUSE
   accepted change                    diagnostic + audit record
```

The firewall answers one narrow question — *did this change information we have
declared invariant?* — and it does not care whether the prose reads better.
Numbers, percentages, currency, units, dates, times, URLs, emails, file paths,
version and vulnerability identifiers, digests, negation, modal verbs and a
bounded set of comparators.

### Rules propose; integrity vetoes

A rule classified `safe-fix` does not outrank this layer. A rule turning

    You must not apply after 5pm.

into

    You must apply after 5pm.

is structurally impeccable and is refused.

**There is no way to switch it off.** No rule field — the schema rejects unknown
keys, so there is nowhere to put one. No caller flag — `build_plan` takes a
document, a ruleset and a projection; `apply_plan` takes a document and a plan.
No style profile, no future adapter. Tests assert each of those. If an expert
workflow ever needs an override, that is a separate architecture and threat-model
decision, not a keyword argument.

### A versioned policy, not an implementation detail

The policy is product behaviour. A document processed under `2026.1` was checked
against those categories and no others, so the version and its SHA-256 travel
with every plan and every audit record — and a plan approved under one policy is
**refused** at application time under another. Applying edits nobody checked is
exactly the failure a version number exists to prevent.

The hash covers everything that changes what would be accepted: category order
(order is behaviour — an earlier category claims text a later one then cannot
see), every pattern, case sensitivity per category, the trimming rules, which
normaliser each kind uses, and every vocabulary. Tests mutate each of those in
turn and assert the hash moves. It is pinned as a constant so that the Windows,
Linux and macOS jobs all assert the same number, rather than each machine
comparing itself to itself.

### Facts, snapshots and comparison

A **fact** is one invariant found at one place: kind, surface, normalised
identity, exact offsets. A **snapshot** is every fact in a piece of text plus
the policy that found them; comparing snapshots from different policies is
refused rather than attempted.

Comparison is **position-independent and count-sensitive**. Any edit shifts the
offsets of everything after it, so comparing positions would flag every
successful transformation. What is compared is the multiset of identities — a
dosage that appeared twice must still appear twice.

Normalisation is applied narrowly, and only where a reformatting plainly is not
a change of meaning: `£2,500` and `£2500` are one amount, `5mg` and `5 mg` are
one dose. Where deciding would take judgement — `mL` against `ml`, `2026-08-29`
against `29 August 2026` — the surfaces are kept and treated as different.
Being too strict costs a refused edit; being too lax costs the reader the
meaning of the sentence.

Direction does not matter. Removing a negation turns a prohibition into a
permission; introducing one does the same in reverse.

### Three layers of check

| Layer | Compares | Catches |
|---|---|---|
| **proposal-local** | the replaced span against its replacement | doses, modals, currency symbols — the direct cases |
| **context-local** | the enclosing block, before and after the substitution | what a span-only view cannot: an edit adjacent to a negation |
| **document-global** | the original document against the finished output | what several edits did *together* |

The first two run during planning. The third runs inside `apply_plan`, before
it returns anything, so an output that failed it is never seen by a caller.
There is no repair attempt and no partial application.

Work is bounded deliberately: a proposal is checked against its block, never the
whole document, and the document-wide comparison happens exactly once per
application. Both are asserted structurally rather than by timing.

### The firewall runs last

Order matters more than it looks:

```
propose → protect → resolve conflicts → integrity → plan
```

If a proposal the firewall vetoes had its losing rival reinstated, the engine
would have two paths to resolving an overlap, and which edit landed would depend
on which safety check happened to fire. So **a conflict group whose winner fails
integrity produces no automatic edit at all.** The loser keeps the refusal
reason conflict resolution gave it. A later run reconsiders the document afresh.

### What it costs the shipped ruleset

Two of the 24 bundled safe fixes are now refused, and both refusals are correct
under a policy that deliberately cannot read meaning:

- `PS.CLARITY.009` replaces "prior to" with "before". "Before" is a protected
  comparator, and the firewall cannot tell that substitution from one that
  reverses an ordering.
- `PS.FRAMING.003` deletes "it should be noted that", which happens to contain
  the modal "should". The modal is part of the idiom rather than an obligation,
  but knowing that requires reading meaning.

Neither rule was changed and the ruleset hash is unaffected. Softening the
firewall to let them through would mean dropping "before" from the comparators —
which would allow a genuine ordering reversal — or exempting modals inside
deletions, which would allow "you should not apply" to lose its "should". Both
cost more than two missed simplifications do. The set is pinned by a test, so it
can only grow deliberately.

### Two authorities, not one

The protected-term register and the firewall are independent, and a proposal has
to survive both. The register refuses substituting "consideration" — a term of
art with no integrity facts in it at all. The firewall refuses turning "must"
into "may" — a word the register has never heard of. Neither can weaken the
other, and a test drives all three outcomes through one document.

### Not semantic equivalence

The firewall does not attempt to prove that "prior to" means "before" or that
"cannot" means "is unable to". Uncertainty resolves to refusal. A later reviewed
mechanism may let a rule *declare* an integrity-preserving equivalence; inferring
one is not something this layer will ever do.

## Morphology

A lexical rule declares a lemma; the loader expands it into explicit surface
forms:

```yaml
match:
  type: lemma
  lemma: "utilise"
  pos: verb
action:
  type: replace
  lemma: "use"
```

becomes `utilise → use`, `utilises → uses`, `utilised → used`,
`utilising → using`. Expansion happens once, at load time, and the forms are
stored on the rule. Three things stay true because of that: the matcher only
ever sees literals, `plainspeak rules explain` can show a reviewer the exact
surfaces, and **the ruleset hash covers the generated forms** rather than only
the lemma that produced them — so a change to morphology moves the ruleset
identity instead of silently changing what it matches.

### It runs forwards only

Morphology never takes a surface form and works out what it came from. The
inherited simplifier did exactly that — strip a suffix, hope the result is a
word — and suggested the verb "clare" for the noun "clarity". Going forwards
from a declared lemma the worst case is a form nobody uses; it cannot be a word
that does not exist, because a person wrote the lemma down. A test asserts no
function in the package looks like a stemmer.

Regular inflection follows a small set of rules declared as data. Everything
those rules would get wrong — irregular verbs, irregular plurals, consonant
doubling — is in a table somebody read. English doubles in "commit" and not in
"benefit", and the difference is stress, which is not recoverable from spelling;
so it is listed rather than derived.

### When it cannot tell, it says nothing

A regular English verb writes its past and its past participle the same way.
When the *target* distinguishes them, one source surface has two possible
replacements: "accomplished" is "did" after a subject and "done" after "was".
The engine produces neither and the rule does not match that form. `accomplish
→ do` therefore covers base, third person and gerund only.

That is the same defect as `clarity → clare`, arriving from the opposite
direction, and it gets the same answer.

### Identity

Morphology is versioned product behaviour, like the ruleset and the integrity
policy. Its hash covers the irregular tables, the inflection rules, the casing
policy, the supported form classes, phrasal-head handling and every exception.
It is pinned and asserted on all three platforms.

`inflect` was evaluated and not adopted: it has no verb conjugation API, which
is the main requirement, and deriving forms from a third party would move a
pinned safety identity whenever that package changed its heuristics. The reasons
are recorded in `plainspeak/morphology/policy.py` and
[GLOSSARY_MIGRATION.md](GLOSSARY_MIGRATION.md).

## The glossary migration

The inherited glossary — 706 unique terms — is **source material, not a
transformation policy**. 140 entries became rules. The rest are diagnostics,
deferred, protected, rejected or already covered, and
[GLOSSARY_MIGRATION.md](GLOSSARY_MIGRATION.md) reconciles all 706 exactly.

The rules are generated from `migration/decisions.yaml` by
`tools/build_glossary_inventory.py`, which also emits the machine-readable
inventory. Regenerating is the only supported way to change them, so the
inventory and the rules cannot disagree.

Adding 176 rules to 38 makes collisions likely, so four audits run as tests: no
two rules claiming one surface, no rule's output matched by another rule, no
generated surface that is a protected term, and no surface generated by two
lemmas. The first run found 13 — the migration was about to add a second rule
for words Phase 4 already handled by hand. Those are now detected and classified
`already-covered`, and **no existing rule ID was renumbered**.

### Scaling

214 rules over a 34,000-word document took a hundred seconds, because scope
filtering answered "which segments does this range touch?" by scanning every
segment: match count and segment count both grow with the text, and the product
is quadratic. A `_SegmentIndex` built once per plan replaces the scan with a
binary search over the contiguous run of segments a range touches. Planning is
now linear at roughly 105 ms per thousand words.

An optimisation that changed a decision would be a behaviour change wearing a
performance costume, so a test compares the index against the scan it replaced —
over every corpus document, every match the real ruleset makes, and every
single-character range. Bounded work is asserted by counting lookups rather than
seconds, so it cannot go flaky on a loaded machine.

## Style diagnostics

`plainspeak/style/` measures a whole document: cadence, repetition, transition
habits, vocabulary concentration, structural balance. Thirteen diagnostics, each
answering one question with arithmetic and reporting the arithmetic alongside
the answer.

It is **diagnostic only**. It proposes no edits, so it never reaches the
planner and has nothing for the integrity firewall to check. `style-fix` remains
a mode the schema recognises solely in order to reject it, because a style fix
has nothing to be relative to until profiles exist.

### What it will not do

This is the layer that could most easily turn into an AI detector. The demand is
real, the output superficially resembles what such a claim would need, and the
method cannot support it. So the prohibitions are enforced by tests rather than
stated in a comment:

- **No authorship claim.** `tests/test_style_policy.py` parses every
  non-docstring string literal in the package and fails on `authorship`,
  `probability`, `likely ai`, `human score`, `detector` and eleven other
  phrasings. Nothing that reaches a reader may say who wrote the text.
- **No aggregate score.** `StyleAnalysis` is asserted to have no field whose
  name contains `score`, `rating`, `probability`, `confidence` or `likelihood`.
  One number would hide the evidence that produced it, and one number is what
  gets pasted into a disciplinary email.
- **No edits.** No function in the layer may be named `apply`, `fix`,
  `replace`, `rewrite` or `replacement`.

What comes out instead is `analysis.profile`: a band per diagnostic, each
traceable to a single measurement and a single threshold. Uniform sentence
lengths are a property of text, not a confession.

### Repetition, not existence

An em dash is a punctuation mark. "Not only X but also Y" is ordinary English. A
document containing one of either is a document containing one of either.

Every diagnostic measures how often something happens relative to how much text
there is. `_punctuation_metrics` reports em-dash and semicolon *rates* precisely
so that a future profile can care about distribution rather than presence, and
no threshold anywhere in the layer fires on a single occurrence.

### Silence below the sample

A ratio over four sentences is arithmetic, not evidence. Each diagnostic
declares the smallest sample it will speak about and returns nothing beneath it,
and in this corpus the minimums do more work than the thresholds.

The eight-paragraph minimum on `PARAGRAPH_UNIFORMITY` exists because at five it
produced a false positive on `government.md` — a plain-English public-service
document whose paragraphs are a similar length because the register calls for
it. That is the failure mode the whole layer has to avoid, and it took two more
corpus documents to establish that the threshold still separated anything once
the minimum had been raised.

### Two authorities, again

Style measures prose; finding the prose is the pipeline's job.
`pipeline/styling.py` walks the document IR once and hands `style` a
`DocumentStructure` — blocks of text with a kind attached. The style layer never
sees markup, which is why the same thirteen diagnostics run unchanged over plain
text, Markdown and a .docx.

Quoted material is excluded from the prose it measures. A document that quotes a
repetitive source at length is not itself repetitive, and the block kinds
(`paragraph`, `heading`, `list_item`, `quote`) carry enough to say so.

It reaches `core` for exactly one thing: `split_sentences`. A second segmenter
here would eventually disagree with the analyser about how many sentences a
document has, and the first symptom would be a style report contradicting a
lexical finding. `tests/test_architecture.py` narrows the permitted crossing to
that one module, so the allowance cannot widen into the simplifier.

### Identity and calibration

The style policy is versioned product behaviour, like the ruleset, the integrity
policy and morphology. `policy_hash()` covers every threshold, every minimum
sample, every vocabulary and every bound, and is pinned and asserted on all
three platforms — 5% becoming 8% changes what a reader is told and fails the
build until somebody says so deliberately.

The thresholds were set against `tests/style/corpus/`: fourteen project-authored
documents, six of them ordinary prose whose only job is to stay quiet. Nothing is
trained on them; they are regression data, and
`tests/style/corpus-findings.json` records what each document currently
produces so a threshold change names the documents it moved.

Six natural documents, zero false positives; eight repetitive documents, zero
misses. [STYLE_CALIBRATION.md](STYLE_CALIBRATION.md) records the margin behind
each of those numbers and, more usefully, the three thresholds that no natural
document currently tests and the two diagnostics that no corpus document
exercises at all.

## What is deliberately not here yet

The build plan describes several layers that this codebase has not earned the
right to yet. They are absent rather than stubbed, because an empty package
implies a decision that has not been made:

- **Style profiles.** `style/` diagnoses; it does not adapt. There is currently
  one set of thresholds, not a choice between several, so a report cannot yet
  say "uniform *for a technical specification*" — which is the distinction that
  would make several of these findings useful rather than merely true.
- **Style fixes.** Nothing in `style/` proposes an edit. `style-fix` remains a
  mode the schema recognises only in order to reject it, since a style fix has
  nothing to be relative to until profiles exist.
- **Three style thresholds have no natural document testing them.** Repeated
  transition and list dominance have none at all; paragraph uniformity has one.
  They have not produced a false positive because nothing in the corpus has
  reached their minimum sample from the quiet side.
- **477 glossary entries are still deferred.** Each needs individual review;
  until it has one, the engine says nothing about it. The inherited flat path
  still uses all 706 and remains sealed.
- **228 multi-word entries are untouched.** Phrase rewriting needs syntactic
  review, not lexical substitution.
- **No comparatives or superlatives.** No shipped rule needs them, and an
  untested form class is a liability.
- **The CLI cannot apply rules.** `rules list` and `rules explain` are
  read-only. A destructive `fix` command should wait until the engine has been
  used in anger.
- **No declared equivalences.** A rule cannot yet say "this substitution
  preserves the comparator", which is what would let `prior to` → `before`
  through. Designing that safely is its own piece of work.
- **Dates are protected by surface, not by value.** `29/08/2026` and
  `08/29/2026` are different facts; no locale is resolved and none is guessed.
- **Units are matched, not understood.** A reviewed list, not a unit grammar.
  `5 mg` → `5 g` is caught because the unit changed, not because the engine
  knows what a milligram is.
- **No adapter offers the structured path yet.** `analyze_document` exists and
  is tested, and the CLI now takes its input through `pipeline.sources`, but
  the CLI's own commands still run the inherited flat-text path. Wiring that up
  is a separate, reviewable change.
- **Table cells are not parsed.** The whole table is opaque, so prose inside a
  cell is neither analysed nor editable. Parsing cell spans would make it both.
- **Findings that cross markup are diagnostics only.** `provides a robust` in
  `provides a **robust** solution` has no single source range, so it is
  reported and refused. Multi-span edits are a Phase 4 question.
- **DOCX, PDF and HTML have no structured parser.** They load through the
  plain-text parser, which is an honest degradation: the document records which
  parser actually ran, so a caller can tell "the structure says this is prose"
  from "we could not see any structure".

## Known weaknesses in the inherited engine

Sealed, not endorsed. Listed here so nobody mistakes "the tests pass" for "this
is good":

- Passive-voice detection is a regex over `be` + a participle-shaped suffix. It
  finds real passives and also finds things that are not passives.
- Nominalisation reversal derives verbs by stripping suffixes, which produces
  non-words: `clarity` currently yields the suggestion `clare`.
- The inherited reader path (`read_auto`, which the analyser still uses)
  flattens Markdown to undifferentiated text, so link URLs, code fences and
  table pipes are all treated as prose. The document representation fixes
  this, but nothing in `core` consults it yet.
- Empty and whitespace-only input raises rather than returning an empty result.
- Substitution marks its replacements with `**bold**` regardless of whether the
  surrounding document is Markdown.
