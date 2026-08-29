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
   text · html          html · json      tokenize · metrics
   docx · pdf           console          barriers · transform
   detect               labels           lexicon · glossary
                                         morphology · syllables
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
| `document` | Reading files into text | `document` |
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

## What is deliberately not here yet

The build plan describes several layers that this codebase has not earned the
right to yet. They are absent rather than stubbed, because an empty package
implies a decision that has not been made:

- **`rules/`** — the declarative rule system. Today's detectors are Python
  functions with hard-coded patterns. The vocabulary in `core/glossary.py` is
  the data that will move first.
- **`style/`** — style profiles. There is currently one behaviour, not a
  choice between several.
- **A document intermediate representation.** Every reader currently flattens
  its input to a plain string, which is why the engine cannot tell a heading
  from a quotation, or a code block from prose. This is the next piece of work,
  and the one that most limits what the engine can safely do.

## Known weaknesses in the inherited engine

Sealed, not endorsed. Listed here so nobody mistakes "the tests pass" for "this
is good":

- Passive-voice detection is a regex over `be` + a participle-shaped suffix. It
  finds real passives and also finds things that are not passives.
- Nominalisation reversal derives verbs by stripping suffixes, which produces
  non-words: `clarity` currently yields the suggestion `clare`.
- Markdown is read as undifferentiated text, so link URLs, code fences and
  table pipes are all treated as prose.
- Empty and whitespace-only input raises rather than returning an empty result.
- Substitution marks its replacements with `**bold**` regardless of whether the
  surrounding document is Markdown.
