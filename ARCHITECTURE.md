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
                 projection · analysis · plan
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
       ▼                      ▼                      ▼
   document               reporting                core
   model · load           html · json          tokenize · metrics
   parse_text             console              barriers · transform
   parse_markdown         labels               lexicon · glossary
   text · html · detect                        morphology · syllables
   docx · pdf
                              │                      │
                              └──────────┬───────────┘
                                         ▼
                                     integrity
                                     protected
```

Arrows are the *only* permitted directions.

| Layer | Holds | May import |
|---|---|---|
| `core` | Tokenising, metrics, barrier detection, substitution, morphology | `core`, `integrity` |
| `integrity` | What must never be changed | nothing |
| `document` | Reading files, and the structured representation of one | `document` |
| `reporting` | Rendering results for a human or a machine | `reporting`, `core`, `integrity` |
| `pipeline` | Orchestration between documents and analysis | `pipeline`, `core`, `document`, `integrity` |
| `adapters` | Interfaces onto the engine | `adapters`, `pipeline`, `core`, `integrity`, `reporting` |

That table is not a description. `tests/test_architecture.py` parses it out of
this file and compares it against what the code actually imports, so a
documented rule and an enforced rule cannot drift apart. Changing the policy
means changing the table.

Three of those constraints are worth spelling out.

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

## What is deliberately not here yet

The build plan describes several layers that this codebase has not earned the
right to yet. They are absent rather than stubbed, because an empty package
implies a decision that has not been made:

- **`rules/`** — the declarative rule system. Today's detectors are Python
  functions with hard-coded patterns. The vocabulary in `core/glossary.py` is
  the data that will move first.
- **`style/`** — style profiles. There is currently one behaviour, not a
  choice between several.
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
