# Limitations

All known limitations, uncertainties, and gaps. This document is maintained honestly and updated as evidence changes.

## Functional limitations

### Language support
- **English only.** Readability formulas, jargon glossary, and pattern matching are all English-specific. The architectural approach could be adapted to other languages, but each language would require its own metrics, patterns, and glossary.
- **No non-Latin script handling.** The tool has not been tested with Arabic, Chinese, Japanese, Korean, Cyrillic, or other writing systems.

### Text processing
- **Sentence segmentation is heuristic (improved in v0.2.0).** We use regex-based sentence splitting with a multi-phase protection-and-restore approach. Now handles 200+ abbreviations, URLs, email addresses, decimal numbers, initials, and numbered lists. Still known to fail on: dialogue with complex punctuation, some abbreviations not in the set, and highly irregular formatting.
- **Syllable counting is approximate.** The syllable counter uses pattern-based heuristics. It will be wrong for some words, especially loanwords and irregular pronunciations. The error rate is typically ~5-10%, which propagates to Flesch-Kincaid and other syllable-dependent metrics. A dictionary-based improvement is planned (see ROADMAP.md Phase 3.2).
- **No semantic understanding.** The tool analyzes surface features of text. It cannot tell whether a "complex" sentence is actually clear in context, or whether a "simple" sentence is ambiguous.

### Suggestion quality
- **Plain language suggestions are from a static glossary.** They do not account for context. A suggested replacement may be inappropriate for the specific domain or may change nuance.
- **No guarantee that suggestions improve comprehension.** We have not conducted user studies. Suggestions are based on established plain-language guidelines (e.g., Plain Language Act, CDC Clear Communication Index) but have not been empirically validated in this tool.
- **Grammar issues from word substitution.** Mechanical word replacement inevitably breaks grammar (a/an agreement, gerund/infinitive, tense). v0.3.0 adds basic post-processing (a/an fixes, capitalization) but many grammar issues remain.

### Stemming limitations
- **Basic suffix-stripping only.** The stemmer handles common suffixes (-tion, -ment, -ing, -ed, -ly, etc.) but does not handle irregular forms, vowel changes, or morphology rules. Accuracy is approximately 70% for inflected forms.
- **No lemmatization.** The stemmer does not use a dictionary, so it cannot distinguish between different base forms that share the same stem (e.g., "organ" could be the base of "organic" or "organize").
- **Stemming is used only for glossary matching.** It does not affect readability metric computation or other analysis.

### Mechanical simplification
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
- **Web interface requires local server.** The web app runs on localhost:5100, which still requires running a command first. A standalone double-clickable executable is planned (see ROADMAP.md Phase 6.1).
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
