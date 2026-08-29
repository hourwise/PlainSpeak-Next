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
       ┌───────────────────┼───────────────────┐
       │                   │                   │
       ▼                   ▼                   ▼
   document             reporting            core
   model · load         html · json      tokenize · metrics
   parse_text           console          barriers · transform
   parse_markdown       labels           lexicon · glossary
   text · html                           morphology · syllables
   docx · pdf · detect
                           │                   │
                           └─────────┬─────────┘
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
| `adapters` | Interfaces onto the engine | everything |

Two of those constraints are worth spelling out.

**`integrity` is a leaf on purpose.** It is the part of the system whose job is
to say "no". Anything it imported could import it back, and a cycle there would
be a cycle in the safety check itself. Keeping it dependency-free means the
protected-term register can never be circumvented by import order.

**`reporting` may read results but never compute them.** A report that
calculated its own numbers would be a second engine wearing a different hat.

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

## What is deliberately not here yet

The build plan describes several layers that this codebase has not earned the
right to yet. They are absent rather than stubbed, because an empty package
implies a decision that has not been made:

- **`rules/`** — the declarative rule system. Today's detectors are Python
  functions with hard-coded patterns. The vocabulary in `core/glossary.py` is
  the data that will move first.
- **`style/`** — style profiles. There is currently one behaviour, not a
  choice between several.
- **The analyser does not use the representation yet.** `core` still consumes a
  flat string; the IR sits alongside it. Connecting the two — so that detection
  runs per prose span rather than over the whole document — is the next step,
  and it is what turns the structural knowledge into behaviour.
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
