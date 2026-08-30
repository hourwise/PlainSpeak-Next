# PlainSpeak Next

> This is a **descendant** of [hourwise/Project-PlainSpeak](https://github.com/hourwise/Project-PlainSpeak),
> created from commit `74ecd51` with its full history preserved. Development here is
> independent and nothing syncs in either direction — see [UPSTREAM.md](UPSTREAM.md).
>
> It is being rebuilt from a readability *analyser* into a deterministic prose
> transformation and review engine. See [ARCHITECTURE.md](ARCHITECTURE.md) for the
> current shape of the code, including what is deliberately not built yet.

The description below is inherited, and still accurate for what the engine does today.

**A diagnostic and review assistant for plain-language communication.**

PlainSpeak helps you understand how readable your writing is, identifies
where readers may struggle, and suggests what you can reasonably improve.
It is primarily a **diagnostic and review tool** — not an authoritative
automatic rewriting system.

All suggestions require human review. This is especially important for
legal, medical, financial, or safety-critical content.

## What it does

- **Measures readability** using six established metrics and a difficulty band system.
- **Identifies barriers** to comprehension: long sentences, passive voice, jargon, complex words, nominalizations, and more.
- **Prioritizes findings** — grouped by sentence, ranked by impact, with confidence levels.
- **Suggests plain-language alternatives** from a glossary of over 600 terms across legal, medical, financial, academic, and bureaucratic domains.
- **Generates accessible reports** — HTML and console output, plus a local web application.
- **Supports multiple formats** — paste text, upload .txt/.md/.docx/.pdf/.html files.
- **Runs entirely offline** — no accounts, no data collection, no network access required.

## What problem it addresses

Every day, people encounter text they cannot understand: medical instructions, legal notices, government forms, terms of service. Complex language creates barriers that disproportionately affect people with lower literacy, non-native speakers, people with cognitive disabilities, and elderly people.

PlainSpeak gives writers and advocates a free, offline tool to check whether text is accessible — and to understand why it might not be.

## Who it is for

- **Public service writers** checking whether forms and notices are understandable.
- **Healthcare communicators** creating patient-facing materials.
- **Educators** preparing accessible learning resources.
- **Legal aid organizations** explaining rights and processes.
- **Anyone** who wants their writing to be understood by more people.

## What currently works

✅ **Working prototype with web interface.** The core toolkit is functional and tested.

- [x] **Difficulty band system** — colour-coded bands (Very Easy → Very Difficult) with explanations, replacing raw grade numbers
- [x] Readability metric computation (6 metrics) with **grade clamping** to prevent absurd values
- [x] **Grouped & prioritized barrier reporting** — findings grouped by sentence, deduplicated, ranked High/Consider/Info with confidence levels
- [x] **Protected terms of art** — 50+ legal/medical/financial terms flagged but never given meaning-changing replacements
- [x] **Top improvements summary** — 3–7 highest-value actions always visible
- [x] Plain-language suggestion engine (600+ terms across legal, medical, financial, academic, bureaucratic domains)
- [x] **Local web application** with real-time analysis, dark mode, sample texts, **before/after comparison mode**
- [x] **Dictionary-backed syllable counting** (CMU Pronouncing Dictionary, 125K+ words)
- [x] **Structural sentence segmentation** (double newlines, list markers, headings, lines without terminal punctuation)
- [x] **Multi-format document support** (.txt, .md, .docx, .pdf, .html)
- [x] HTML report generation (accessibility-guidance-designed)
- [x] CLI interface (analyze, score, simplify, web, version commands)
- [x] **Document-level style diagnostics** — cadence, repetition, transition and vocabulary patterns, each reported with the arithmetic behind it. Diagnostic only: no authorship claim, no aggregate score, no automatic fixes (see [STYLE_CALIBRATION.md](STYLE_CALIBRATION.md))
- [x] **Style profiles** — five calibrated interpretations (Natural, Plain, Technical, Government, Academic) of the same measurements, so a specification and an essay are not judged against identical expectations. `plainspeak profiles list` (see [STYLE_PROFILES.md](STYLE_PROFILES.md))
- [x] **Profile-governed style suggestions** — eight exact phrase substitutions that a chosen profile can trigger, every one requiring human review before it changes anything. `plainspeak style preview --profile natural` (see [STYLE_TRANSFORMATIONS.md](STYLE_TRANSFORMATIONS.md))
- [x] Test suite (**3,862 tests**, all passing)

## How to run it

### Web interface (recommended for most users)

```bash
pip install -e ".[web]"
plainspeak web
```

Opens a browser-based analyzer at http://127.0.0.1:5100. Paste text, click analyze, see results instantly. Nothing leaves your computer.

### Command-line interface

```bash
pip install -e .
plainspeak analyze my_document.txt --output report.html
```

## How to test it

```bash
python -m pytest tests/ -v
```

## What remains incomplete

See [LIMITATIONS.md](LIMITATIONS.md) for a full accounting of known gaps. Key items:

- English-only; no internationalization.
- No empirical validation with human readers.
- HTML report/web app not tested with real screen readers.
- Word-level substitution inevitably breaks grammar in edge cases.

## Principal limitations

1. **Readability formulas are proxies**, not direct measures of comprehension.
2. **Suggestions are rule-based**, not context-aware — they must be reviewed by a human.
3. **English only.** The metrics and patterns are language-specific.
4. **Web app requires terminal to start** — a standalone executable is planned.
5. **Not validated** for legal, medical, or safety-critical documents.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — the layers, and what each may depend on
- [STYLE_CALIBRATION.md](STYLE_CALIBRATION.md) — where the baseline style thresholds came from, and which are not yet supported by evidence
- [STYLE_PROFILES.md](STYLE_PROFILES.md) — the five profiles, their margins, and the three baseline thresholds this calibration showed to be wrong
- [STYLE_TRANSFORMATIONS.md](STYLE_TRANSFORMATIONS.md) — what a style fix may propose, what it may never do, and why four of them were deleted
- [GLOSSARY_MIGRATION.md](GLOSSARY_MIGRATION.md) — how 706 inherited terms were reconciled
- [UPSTREAM.md](UPSTREAM.md) — lineage, and why nothing syncs
- [MISSION.md](MISSION.md) — problem, beneficiaries, ethical boundaries
- [ROADMAP.md](ROADMAP.md) — development phases and priorities
- [DECISIONS.md](DECISIONS.md) — chronological decision record
- [LIMITATIONS.md](LIMITATIONS.md) — honest accounting of all known gaps
- [SECURITY.md](SECURITY.md) — threat model and privacy verification
- [ACCESSIBILITY.md](ACCESSIBILITY.md) — manual checklist, known gaps
- [QUALITY_PHASE_REPORT.md](QUALITY_PHASE_REPORT.md) — evidence and product quality findings
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — data provenance and licences
- [VALIDATION_FINDINGS.md](VALIDATION_FINDINGS.md) — regression discoveries
- [CHANGELOG.md](CHANGELOG.md) — version history

## License

MIT — see [LICENSE](LICENSE) file.

## Contributing

This is an experimental project built within a constrained 24-hour window. Contributions, forks, and continuations are welcome. Start with [MISSION.md](MISSION.md) to understand the project's purpose and [DECISIONS.md](DECISIONS.md) for the rationale behind major choices.

Repository: [github.com/hourwise/Project-PlainSpeak](https://github.com/hourwise/Project-PlainSpeak)
