# Characterisation seal

This directory freezes what the inherited PlainSpeak engine **does**, so that
the architectural work in later phases cannot change established behaviour by
accident.

It is not a correctness suite. Nothing here claims the sealed output is good.
Several sealed values are demonstrably crude — the passive-voice detector is a
regex heuristic, Markdown is read as undifferentiated plain text, and empty
input raises rather than returning an empty result. All of that is sealed
exactly as it is. The point is that changing any of it must be a deliberate,
reviewed act rather than a side effect of a refactor.

## Layout

| Path | What it holds |
|---|---|
| `corpus/` | Input documents, one `.txt` per sealed case |
| `formats/` | One fixture per supported reader format, plus an unsupported one |
| `golden/` | The sealed output, one `.json` per corpus document |
| `capture.py` | Turns an input into a deterministic JSON payload |
| `test_characterisation.py` | Compares a fresh capture against the golden |

Two goldens are not derived from a corpus document:

- `_globals.json` — the engine's static data (glossary, protected terms,
  abbreviations) and its pure functions (syllables, stemming, article fixing,
  difficulty banding), probed with word lists chosen to hit known edge cases.
- `_readers.json` — what each document reader extracts from its fixture,
  including how it fails on an unsupported extension and a missing file.

## When a test here fails

A failure means one of two things, and telling them apart is the whole job:

1. **A refactor changed behaviour unintentionally.** Fix the code. Do not touch
   the golden file.
2. **Behaviour was changed deliberately.** Regenerate the goldens and commit
   the diff *in the same commit as the change*, so review sees exactly what
   moved and can agree that it should have.

```bash
python -m tests.characterisation.capture --write
```

Never regenerate to turn a red test green without reading the diff. That single
habit is the only thing standing between this suite and worthlessness.

The failure message names the first differing path into the payload — for
example `.simplifier.value.result.barriers[3].suggestion` — because comparing
two thousand-line JSON documents by eye is not a reasonable ask.

## What is captured, and why it is safe to compare

Everything sealed must be identical across runs, machines and operating
systems. That rules out a surprising amount:

- **Wall-clock.** The HTML report stamps generation time into its output.
  `redact_timestamps` removes it before hashing.
- **Floats.** Rounded to six decimal places — far finer than any readability
  metric claims to mean anything at, and coarse enough to clear
  platform floating-point noise in the last bits.
- **Ordering.** Mappings are emitted with sorted keys; sets are sorted.
- **Line endings.** Fixtures are LF and `.gitattributes` marks these trees
  byte-significant. Sentence segmentation keys off blank lines, so a CRLF
  fixture would seal behaviour that only holds on Windows. A test enforces
  this; it caught exactly that mistake the first time it ran.
- **Paths.** Reader errors have machine-specific fragments stripped.

Large mappings such as the 600-plus-entry glossary are sealed as a size plus a
SHA-256 of their canonical form rather than inline, so an accidental edit still
fails loudly without burying every other diff in the file.

## Known gaps

- **DOCX and PDF extraction depends on the installed library version.** The
  fixtures are read with `python-docx` and `pypdf`, and an upstream change to
  either could move `_readers.json` without any change to PlainSpeak. If that
  becomes noisy, pin the extras rather than loosening the seal.
- **The corpus is small.** It covers each barrier type, the protected-term
  overlaps, structural segmentation, abbreviations, non-ASCII punctuation, the
  integrity-sensitive categories, and five degenerate inputs. It is not a
  statistical sample of real prose, and it is not meant to be — the human and
  AI corpora described in the build plan are separate assets.
- **The web adapter is not sealed.** It is scheduled to stop being the primary
  interface, so freezing its current behaviour would seal in work that is meant
  to be replaced.

## Adding a case

Drop a `.txt` into `corpus/`, run the regeneration command, read the new golden
to check it says what you expect, and commit both. `test_every_corpus_document_is_sealed`
fails if you forget the second step.
