# Limitations

All known limitations, uncertainties, and gaps. This document is maintained honestly and updated as evidence changes.

## Functional limitations

### Language support
- **English only.** Readability formulas, jargon glossary, and pattern matching are all English-specific. The architectural approach could be adapted to other languages, but each language would require its own metrics, patterns, and glossary.
- **No non-Latin script handling.** The tool has not been tested with Arabic, Chinese, Japanese, Korean, Cyrillic, or other writing systems.

### Text processing
- **Sentence segmentation is heuristic.** We use regex-based sentence splitting, which will fail on abbreviations (e.g., "Dr.", "U.S."), decimal numbers, and other edge cases. This is a known limitation of all regex-based approaches.
- **Syllable counting is approximate.** The syllable counter uses pattern-based heuristics. It will be wrong for some words, especially loanwords and irregular pronunciations. The error rate is typically ~5-10%, which propagates to Flesch-Kincaid and other syllable-dependent metrics.
- **No semantic understanding.** The tool analyzes surface features of text. It cannot tell whether a "complex" sentence is actually clear in context, or whether a "simple" sentence is ambiguous.

### Suggestion quality
- **Plain language suggestions are from a static glossary.** They do not account for context. A suggested replacement may be inappropriate for the specific domain or may change nuance.
- **No guarantee that suggestions improve comprehension.** We have not conducted user studies. Suggestions are based on established plain-language guidelines (e.g., Plain Language Act, CDC Clear Communication Index) but have not been empirically validated in this tool.

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

- **CLI is not accessible to all users.** A command-line interface assumes comfort with terminal environments, which excludes many of the intended beneficiaries.
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
