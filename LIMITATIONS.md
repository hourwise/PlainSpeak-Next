# Limitations

All known limitations, uncertainties, and gaps. This document is maintained honestly and updated as evidence changes.

## The governed engine (PlainSpeak Next)

- **Bounded transformations.** Safe fixes are word- and phrase-level rules from
  a versioned ruleset; the eight style fixes are transition substitutions that
  always require review. Nothing restructures a sentence, so output can still
  read stiffly ("To help the successful completion of…").
- **The firewall is deliberately strict.** It compares protected facts, not
  meaning, so some correct changes are refused — "prior to" → "before" is
  refused because "before" is a protected comparator — and a change that alters
  meaning without touching a protected category is not detected.
- **Mid-sentence deletions are refused** where removing a phrase would leave
  broken spacing or punctuation, so some framing phrases survive.
- **Style diagnostics need enough text.** Each has a minimum sample (four to
  eight sentences or paragraphs, 200 words for vocabulary). Short texts
  currently produce no findings, which is not evidence that they are clean.
- **Safe fixes are not yet re-checked against style.** Several transitions map
  to the same replacement, which can create the repetition the style layer
  would flag. Addressed in Stage 1 (see [ROADMAP.md](ROADMAP.md)).
- **Transformation formats.** Only plain text and Markdown can be transformed
  and saved. DOCX, PDF and HTML are analysed through a plain-text fallback and
  refused for editing.
- **No sentence-structure, tense or agreement repair**, and no manual editing
  in the desktop application.

## The inherited engine

The original substitution engine (`core.transform`) is still in the package,
pinned by the characterisation seal for external callers of the old API. No
PlainSpeak interface uses it to transform text any more: `simplify` and the web
interface present through the governed pipeline, and a test forbids any
interface from importing it. The limitations below under *Stemming* and
*Mechanical simplification* describe only that inherited API.

The **readability suggestions** in `analyze` reports and on the web page still
come from the inherited glossary and are sealed with it. They are never applied,
and some are poor — "leverages" is offered "borrowed money". Replacing them
needs a deliberately versioned successor to the seal.

## Functional limitations

### Language support
- **English only.** Readability formulas, jargon glossary, and pattern matching are all English-specific. The architectural approach could be adapted to other languages, but each language would require its own metrics, patterns, and glossary.
- **No non-Latin script handling.** The tool has not been tested with Arabic, Chinese, Japanese, Korean, Cyrillic, or other writing systems.

### Text processing
- **Sentence segmentation is heuristic (improved in v0.2.0).** We use regex-based sentence splitting with a multi-phase protection-and-restore approach. Now handles 200+ abbreviations, URLs, email addresses, decimal numbers, initials, and numbered lists. Still known to fail on: dialogue with complex punctuation, some abbreviations not in the set, and highly irregular formatting.
- **Syllable counting is dictionary-backed, with a heuristic fallback.** Counts come from the CMU Pronouncing Dictionary (125K+ words, since v0.3.0). Words outside it — new coinages, many proper nouns — fall back to pattern-based heuristics, which are wrong for some loanwords and irregular pronunciations.
- **No semantic understanding.** The tool analyzes surface features of text. It cannot tell whether a "complex" sentence is actually clear in context, or whether a "simple" sentence is ambiguous.

### Suggestion quality
- **Plain language suggestions are from a static glossary.** They do not account for context. A suggested replacement may be inappropriate for the specific domain or may change nuance.
- **No guarantee that suggestions improve comprehension.** We have not conducted user studies. Suggestions are based on established plain-language guidelines (e.g., Plain Language Act, CDC Clear Communication Index) but have not been empirically validated in this tool.
- **Grammar issues from word substitution.** Mechanical word replacement inevitably breaks grammar (a/an agreement, gerund/infinitive, tense). v0.3.0 adds basic post-processing (a/an fixes, capitalization) but many grammar issues remain.

### Stemming limitations (legacy path)
- **Basic suffix-stripping only.** The stemmer handles common suffixes (-tion, -ment, -ing, -ed, -ly, etc.) but does not handle irregular forms, vowel changes, or morphology rules. Accuracy is approximately 70% for inflected forms.
- **No lemmatization.** The stemmer does not use a dictionary, so it cannot distinguish between different base forms that share the same stem (e.g., "organ" could be the base of "organic" or "organize").
- **Stemming is used only for glossary matching.** It does not affect readability metric computation or other analysis.

### Mechanical simplification (legacy path)
- **Word-level substitution only.** The `simplify` command replaces individual words with glossary alternatives. It does not restructure sentences, adjust grammar, or fix passive voice.
- **Can produce ungrammatical output.** For example, "The implementation of the policy" → "The carry out of the policy" (should be "Carrying out the policy"). This is a fundamental limitation of word-level substitution without syntactic transformation.
- **Replacements marked with **asterisks** for mandatory human review.** The tool does not produce "clean" simplified text because it cannot guarantee grammatical correctness.

### Input size
- **Not tested on documents > 100,000 words.** Performance characteristics for large documents are unknown.
- **Memory usage is proportional to input size.** The tool loads the full text into memory.

## Evidence limitations

### Metric validity
- **Readability formulas are proxies, not direct measures.** Flesch-Kincaid grade level correlates with comprehension difficulty but does not measure it directly. A text with a low grade level can still be confusing; a text with a high grade level can still be clear.
- **No human validation has been performed.** We have not tested whether the tool's output helps real users understand real documents better than they would without it.

### Suggestion effectiveness
- **We do not know whether writers act on the suggestions.** The tool identifies issues; we have no evidence about whether this leads to improved writing.

## Accessibility gaps

- **CLI is not accessible to all users.** A command-line interface assumes comfort with terminal environments, which excludes many of the intended beneficiaries. **Partially addressed in v0.2.0:** the `plainspeak web` command provides a browser-based interface that is more accessible to non-technical users.
- **Web interface requires local server.** The web app runs on localhost:5100. Its simplified text is the governed presentation, but it cannot review style suggestions; the desktop application is the supported graphical interface, and ships as a portable Windows or Linux directory with no installer yet.
- **HTML report has not been tested with screen readers.** We aim for WCAG 2.1 AA compliance but have not verified this with assistive technology.
- **No internationalization.** All interface text, explanations, and suggestions are in English.

## Scaling constraints

- **Single-threaded.** No parallel processing for large documents.
- **In-memory processing only.** Cannot handle documents larger than available RAM.
- **No streaming API.** The entire document must be available before processing begins.

## Privacy considerations

- **No data collection by design.** The tool runs entirely locally and makes no network requests.
- **However:** The HTML report, if shared, contains the full analyzed text. Users should be aware that sharing the report shares the content.

## Areas requiring specialist review

1. **Linguistics review.** The syllable counter, sentence segmenter, and simplification patterns should be reviewed by a computational linguist.
2. **Accessibility audit.** The HTML report template should be reviewed by an accessibility specialist using real assistive technology.
3. **Plain-language expert review.** The suggestion glossary should be reviewed by a plain-language professional.
4. **Legal review.** If the tool is used for legal or medical documents, the limitations of automated analysis in these domains should be clearly understood.
