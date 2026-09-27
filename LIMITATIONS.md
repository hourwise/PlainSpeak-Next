# Limitations

All known limitations, uncertainties, and gaps. This document is maintained honestly and updated as evidence changes.

## The governed engine (PlainSpeak Next)

- **Bounded transformations.** Safe fixes are word- and phrase-level rules from
  a versioned ruleset; the six style fixes are transition substitutions that
  always require review. Nothing restructures a sentence, so output can still
  read stiffly ("To help the successful completion of…").
- **The firewall is deliberately strict.** It compares protected facts, not
  meaning, so some correct changes are refused — deleting "it should be noted
  that" is refused because it contains the modal "should" — and a change that
  alters meaning without touching a protected category is not detected. The
  equivalence table that lets "prior to" become "before" has one entry.
- **Mid-sentence deletions are refused** where removing a phrase would leave
  broken spacing or punctuation, so some framing phrases survive.
- **Style diagnostics need enough text.** Each has a minimum sample (four to
  eight sentences or paragraphs, 200 words for vocabulary). A short text is
  reported as too short to judge — most agent replies will be — so the style
  layer has little to say about them.
- **The style guard declines; it does not repair.** When safe fixes would make
  a document read worse, some are refused rather than replaced with something
  better, so a document can keep several of the heavy connectives it started
  with.
- **Transition density has no fix.** No bundled rule can lower it honestly, so
  a density finding comes with nothing to review.
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

The **readability suggestions** in `analyze` reports and on the web page come
from the inherited glossary through a reviewed overlay (`core/suggestions.py`):
71 wrong suggestions were withdrawn and 5 corrected before 1.0, and verbs for
nominalisations come only from a reviewed table. What remains is advice that
will not fit every context — "provide → give" is often right and sometimes not
— and is never applied.

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

## Verify

- **Not a meaning checker.** Verify checks the properties the integrity model
  represents. A reworded sentence with every protected fact intact is
  INCONCLUSIVE, not ACCEPTED; a changed word the model does not protect ("pay"
  to "receive", "approved" to "rejected") cannot be called wrong.
- **Strict about equivalent wording.** "at most" and "up to", "no longer than"
  and "up to", "not less than" and "at least", "shall" and "must", a date
  written `12/08/2026` instead of `12 August 2026`: each is refused, because the
  integrity policy treats different spellings as different facts unless a
  reviewed equivalence says otherwise, and its table of equivalences is
  deliberately tiny. The validation study counts 17 such false refusals in 97
  cases ([VERIFY_STUDY.md](VERIFY_STUDY.md)).
- **Directional words that are not comparators.** "above", "below", "under",
  "over" and "exceeds" are not protected comparators in integrity policy
  2026.2, so "3% above" becoming "3% below" is INCONCLUSIVE rather than REFUSED.
- **Counts modals, not their scope.** "must be encrypted and must be tested"
  becoming "must be encrypted and tested" loses a "must" and is refused, though
  the obligation is the same.
- **English, plain text and Markdown only.** Alignment is quadratic in the worst
  case; very long documents are slow.

