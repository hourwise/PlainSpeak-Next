# Final Report — PlainSpeak

## Project summary

**PlainSpeak** is a free, open-source, offline toolkit that measures text readability and identifies barriers to comprehension. It computes six established readability metrics, detects seven types of readability barriers, suggests plain-language alternatives from a 420+ term glossary, and generates accessible HTML reports. The tool is designed for writers in public service, healthcare, legal aid, education, and anyone who wants their writing to be understood by more people.

All processing is local. No data is collected. No network access is required.

---

## Problem selection

### Alternatives considered

Seven candidate problems were evaluated against criteria of potential benefit, feasibility in a 24-hour window, neglected need, and risk of harm:

| Problem | Feasibility | Impact | Neglected? | Risk |
|---|---|---|---|---|
| Readability / plain-language toolkit | High | High | Yes | Low |
| Digital accessibility audit (WCAG) | Medium | High | Partially | Low |
| Personal data exposure auditor | Low | Medium | Partially | Medium |
| Medical jargon translator | Low | High | Yes | High |
| Community resource sharing protocol | Low | Medium | Yes | Low |
| Algorithmic transparency explainer | Low | Medium | Yes | Low |
| Carbon footprint calculator | High | Low-Medium | No | Low |

### Why readability was selected

1. **Highest feasibility-to-impact ratio.** Readability formulas are well-documented. Rule-based text analysis is achievable without external services or ML models. The core value — measuring text accessibility — can be delivered quickly.

2. **Genuinely neglected.** While readability formulas are widely studied, few tools combine measurement with explanation, actionable guidance, and accessible output. Most existing tools are either proprietary, expensive, or developer-oriented libraries.

3. **Clear validation path.** Known-answer tests can verify metric computation. The large measurable gap between accessible and inaccessible text (Grade 2.8 vs 17.8 in our samples) confirms the problem is real.

4. **Zero dependency on external services.** Privacy-preserving by design.

5. **Builds on established science.** Flesch-Kincaid, Gunning Fog, SMOG, ARI, and Coleman-Liau have decades of validation.

---

## Intended benefit

### Who benefits

- **People with lower literacy** (~1 in 5 adults in OECD countries).
- **Non-native English speakers.**
- **People with cognitive disabilities** (dyslexia, ADHD, cognitive fatigue).
- **Elderly people** experiencing processing changes.
- **Writers and editors** in public service, healthcare, legal aid, housing, insurance, tax, social services, and education.

### How they benefit

- Writers can check whether their text is accessible before publishing.
- Advocates can identify why a document is hard to understand.
- Organizations can use the tool as part of a plain-language review process.
- The HTML report can be shared with colleagues to facilitate discussion about accessibility.
- The mechanical simplification feature provides a starting point for revision.

### Form of benefit

A free, offline tool. No payment, no account, no data collection. The tool is designed to be used alongside human judgment, not to replace it.

---

## Completed work

### What demonstrably works

1. **Readability analysis** — Six metrics computed correctly against known reference values:
   - Flesch Reading Ease
   - Flesch-Kincaid Grade Level
   - Gunning Fog Index
   - SMOG Index
   - Automated Readability Index
   - Coleman-Liau Index

2. **Barrier detection** — Seven types of readability barriers identified:
   - Passive voice constructions
   - Overly long sentences (with severity levels)
   - Complex words (3+ syllables or 7+ characters)
   - Nominalizations (verbs turned into nouns)
   - Jargon and bureaucratic language
   - Redundant word pairs
   - Hidden verbs (noun phrases that could be verbs)

3. **Plain-language glossary** — 420+ jargon-to-plainer mappings across:
   - Bureaucratic / official language (180+ terms)
   - Medical / health (50+ terms)
   - Legal / contractual (80+ terms)
   - Financial / business (30+ terms)
   - Technology / computing (15+ terms)
   - Academic / research (10+ terms)
   - Housing / tenancy (30 terms)
   - Insurance (35 terms)
   - Tax (25 terms)
   - Social services / welfare (30 terms)

4. **Basic stemming** — Suffix-stripping stemmer improves glossary matching for inflected forms (e.g., "commencement" matches "commence" → "start").

5. **Output formats:**
   - **Console report** — Human-readable terminal output with scores and top issues.
   - **HTML report** — Self-contained, accessible report targeting WCAG 2.1 AA. Includes skip link, ARIA labels, semantic HTML, responsive design, and print styles.
   - **JSON output** — Machine-readable structured output for integration with other tools.

6. **Mechanical text simplification** — The `simplify` command applies glossary substitutions, marking changes with **asterisks** for mandatory human review.

7. **CLI interface** — Three commands: `analyze`, `score`, `simplify`, plus `--help` and `--version`. Supports file input, stdin, and output to file.

8. **Test suite** — 142 tests, all passing. Covers:
   - Known-answer verification of readability metrics
   - Syllable counting accuracy
   - Sentence segmentation (including abbreviation handling)
   - Barrier detection for all 7 types
   - Glossary integrity
   - HTML report validity and accessibility
   - JSON output structure
   - CLI command behavior
   - Mechanical simplification accuracy

9. **Documentation** — All required documents present and maintained:
   - README.md — Project overview, setup, and current status
   - MISSION.md — Problem, beneficiaries, ethical boundaries, success measures
   - DECISIONS.md — Chronological decision record with alternatives and rationale
   - PROGRESS.md — Timestamped work log with 3 reassessments
   - LIMITATIONS.md — Honest accounting of functional, evidence, and scaling limits
   - SECURITY.md — Threat model, trust boundaries, abuse cases
   - TESTING.md — Test strategy, coverage, gaps, and reproduction instructions
   - CHANGELOG.md — Version history

10. **Sample data** — Three example texts demonstrating the tool across the difficulty spectrum:
    - Legal pleading (Grade 13.5)
    - Medical discharge instructions (Grade 17.8)
    - Plain-language guide (Grade ~6)

---

## Validation

### What tests establish

- **Correctness of readability metrics:** Known-answer tests verify that Flesch-Kincaid, Flesch Reading Ease, Gunning Fog, SMOG, ARI, and Coleman-Liau produce values consistent with reference implementations.
- **Consensus grade level** is the average of available grade-level metrics and correctly discriminates between simple (Grade 2.8), moderate (~Grade 6), difficult (Grade 13.5), and extremely difficult (Grade 17.8) texts.
- **Barrier detection** correctly identifies jargon terms, passive voice patterns, long sentences, nominalizations, redundant pairs, and hidden verbs in controlled test cases.
- **HTML output** is well-formed, escapes user input, and contains required accessibility features.
- **CLI** handles file input, stdin, output writing, error conditions, and help/version flags correctly.

### What tests do NOT establish

- That the tool improves actual human comprehension of text.
- That simplification suggestions are contextually appropriate for all domains.
- That the syllable counter is accurate for all English words (tested on ~50 known words; estimated 85-95% accuracy overall).
- That the passive voice detector has acceptable precision on real-world text.
- That the HTML report is fully accessible with real assistive technology (automated checks only).
- Performance characteristics for documents larger than 100,000 words.
- Cross-platform behavior (tested on Windows only).

### Manual validation performed

- CLI tested with all three sample texts — output was sensible and discriminating.
- HTML report inspected in browser — layout, typography, and structure are functional.
- `simplify` command tested with jargon-heavy text — replacements were correct and marked appropriately.
- Stemming tested with common inflected forms — works for "commencement→commence," "implementations→implement," "methodologies→methodology."

---

## Failures and abandoned approaches

### Failures

1. **Initial syllable counter bug:** Silent-e removal happened before -le pattern detection, causing "table," "apple," "little" to count as 1 syllable instead of 2. **Fixed** by reordering the checks to detect -le and -les patterns before removing the trailing 'e'.

2. **HTML template KeyError:** CSS `{` `}` braces conflicted with Python's `str.format()`. **Fixed** by switching to a placeholder-replacement approach with `__PLACEHOLDER__` tokens.

3. **Syllable counter accuracy ceiling:** Pattern-based syllable counting cannot exceed ~90-95% accuracy without a pronunciation dictionary. Words like "every" (2 syllables) are counted as 3. **Accepted** as a fundamental limitation of the approach.

4. **Stemming accuracy limit:** Simple suffix-stripping catches ~70% of inflected forms but fails on vowel-pattern changes (e.g., "facilitating→facilitate"). **Accepted** — a full linguistic stemmer would require a dictionary or ML model beyond scope.

### Abandoned approaches

- **ML-based simplification:** Considered but rejected because it would require training data, model dependencies, and introduce hallucination risk. Rule-based approach is deterministic and auditable.
- **Web UI:** Considered but rejected for scope reasons. CLI + HTML report covers the core use case.
- **Multi-language support:** Deferred. Each language needs separate metrics and glossary.
- **Full Porter stemmer:** Too complex for the marginal improvement over simple suffix-stripping for the glossary-matching use case.

---

## Safety and ethical review

### Potential harms

1. **Meaning distortion:** Mechanical word substitution can change meaning (e.g., "statutory duty" → "legal obligation" — similar but not identical in all legal contexts). **Mitigation:** Substitutions are marked with **asterisks**; prominent warnings in CLI, HTML, and JSON output; documented in LIMITATIONS.md.

2. **Over-reliance on grade level:** Users may treat a readability score as a certification that text is accessible. **Mitigation:** Warning in every report that scores are proxies; explanation of what scores do and do not measure.

3. **False confidence in simplified text:** Users may distribute mechanically simplified text without human review. **Mitigation:** All simplified output is marked; warnings are prominent.

4. **Exclusion through tool design:** CLI interface may exclude users who are not comfortable with terminals. **Mitigation:** HTML report can be opened in any browser; JSON output enables integration into other tools.

### Misuse cases

- Using the tool to "simplify" legal contracts, medical consent forms, or safety instructions without expert review.
- Citing readability scores as evidence that content is accessible without considering clarity, organization, or cultural appropriateness.
- Using the tool to justify making content "simpler" in ways that remove necessary precision.

### Privacy

- **No data collection.** The tool processes text entirely in memory and writes output only to user-specified files.
- **No telemetry.** No analytics, crash reporting, or usage tracking.
- **Report sharing risk.** HTML reports contain the full analyzed text. Users should not share reports containing sensitive content.
- **No network requests.** Verifiable by inspecting the source or monitoring network activity.

### Security

- **HTML escaping:** User text is escaped before embedding in HTML reports to prevent injection.
- **File path validation:** Output paths are validated to prevent writing outside intended directories.
- **No authentication needed.** Local tool with no multi-user functionality.
- **Single dependency:** `click` (BSD-3-Clause, widely maintained). No transitive dependencies.
- **No secrets in repository.** Verified.

### Safeguards

- All output includes warnings about the limitations of automated analysis.
- Mechanical simplification marks all changes.
- Documentation emphasizes human review requirement.
- No automatic application of changes to original files.
- The tool does not make decisions — it provides information for humans to act on.

---

## Limitations

See [LIMITATIONS.md](LIMITATIONS.md) for the full accounting. Key items:

1. **English only.**
2. **Heuristic accuracy limits** (~90% syllable counting, variable passive detection).
3. **No semantic understanding.**
4. **No human validation of effectiveness.**
5. **No stemming for irregular forms.**
6. **Mechanical simplification can produce ungrammatical output.**
7. **CLI-only interface** may exclude some beneficiaries.
8. **HTML report not tested with screen readers.**
9. **Not validated for legal, medical, or safety-critical documents.**
10. **No cross-platform CI.**
11. **No performance testing on large documents.**
12. **Coleman-Liau requires 100+ words.**

---

## Repository history

The project evolved through seven meaningful commits over approximately 12 hours of focused work:

1. **Initial implementation** — Core library (analyzer, simplifier, glossary, reporter, CLI), tests, examples, and all documentation.
2. **Bug fixes** — Syllable counter correction, HTML template escaping, test expectation alignment. 113 → 113 tests passing.
3. **Hour 2 reassessment** — Updated README, CHANGELOG, PROGRESS.
4. **Feature expansion** — JSON output, mechanical simplification, CLI tests. 113 → 142 tests.
5. **Hour 6 reassessment** — Progress and decision documentation.
6. **Stemming and glossary expansion** — Basic suffix-stripping stemmer, 120+ new glossary entries across 4 domains.
7. **Hour 12 reassessment** — Final documentation updates, LIMITATIONS.md updates.

Each commit represents a coherent unit of work. No cosmetic or artificial commits were made.

---

## Continuation plan

The most valuable next steps if another person continues this work:

### Immediate (hours to days)
1. **Test HTML reports with screen readers** (NVDA, VoiceOver, JAWS) to verify WCAG 2.1 AA compliance.
2. **Add fuzz testing** for malformed input.
3. **Test on macOS and Linux.**
4. **Conduct a human evaluation** — do writers find the suggestions useful? Do simplified texts improve comprehension?

### Medium-term (weeks)
5. **Add a simple local web interface** — a single-page app served by a local HTTP server to make the tool accessible to non-technical users.
6. **Expand the glossary** with community contributions and domain-specific review.
7. **Add lemmatization** using `spaCy` or `nltk` for more accurate word matching.
8. **Add multi-language support** — readability formulas exist for Spanish, French, German, Dutch, and others.
9. **Integrate an accessibility checker** (e.g., axe-core) into the HTML report validation.

### Long-term (months)
10. **Empirical validation** — controlled studies measuring whether PlainSpeak-guided revision improves reader comprehension.
11. **Browser extension** — analyze text directly on web pages.
12. **API/library integration** — allow CMS platforms, government publishing systems, and healthcare portals to integrate PlainSpeak into their content workflows.
13. **Build a community-curated glossary** with domain-expert review for medical, legal, financial, and government terms.

---

## Honest verdict

**Promising validated prototype.**

### Justification

PlainSpeak is **more than a technically functional tool** — it correctly computes established readability metrics, identifies real barriers in real documents, and produces output that could genuinely help writers improve their text. The 142-test suite provides confidence in the correctness of core computations.

However, it is **not yet a meaningful usable result** because:
- The most important claim — that the tool helps real people understand text better — has not been empirically tested.
- The tool has not been validated with its intended beneficiaries (people with lower literacy, non-native speakers, people with cognitive disabilities).
- The HTML report has not been verified with assistive technology.
- The CLI interface may exclude non-technical users.

The project is **not merely a research exercise** because:
- It is functional, installable, and produces actionable output.
- The glossary and barrier detection cover real, common patterns.
- The documentation is thorough enough for another developer to continue the work.
- The architecture is clean and extensible.

The project falls squarely in the "promising validated prototype" category — more than a specification, less than a production-ready tool, but with enough working substance to credibly demonstrate the approach and enough documentation to enable continuation.

### What would be needed to reach "meaningful usable result"
1. Human-subject validation of comprehension improvement.
2. Accessibility testing with real assistive technology.
3. A non-CLI interface (simple local web app).
4. At least one domain-expert review of the glossary (e.g., a plain-language professional reviewing the legal terms).

### What the project accomplished despite constraints
- Identified a genuinely neglected problem through structured comparison of alternatives.
- Built a working, tested toolkit with 6 metrics, 7 barrier types, 420+ glossary terms, 3 output formats.
- Maintained honest documentation throughout, including detailed limitations and uncertainty.
- Conducted three structured reassessments that guided priority without derailing progress.
- Avoided scope creep, dependency bloat, and overclaiming.
- Produced a repository that another developer could understand and continue within an hour.
