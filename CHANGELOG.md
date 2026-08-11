# Changelog

All notable changes to PlainSpeak will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-08-11

### Added
- Local web application (`plainspeak web`) providing a browser-based interface. Runs entirely on localhost — no accounts, no data collection, no network access required.
- Real-time analysis API endpoint (`POST /api/analyze`) returning JSON with full readability scores and simplification results.
- Interactive web UI with: paste/type text area, live-updating readability scores (debounced), tabbed results (Scores / Barriers / Simplified Text), dark mode support (respects OS preference), sample text loading (legal, medical, plain), keyboard shortcut (Ctrl+Enter to analyze), and WCAG 2.1 AA-targeted accessible design with skip link and ARIA labels.
- `/api/sample/<name>` endpoint for loading bundled example texts.
- `plainspeak web` CLI command with configurable host, port, and `--no-open` flag.
- Flask added as optional dependency (`plainspeak[web]`).

### Changed
- **Sentence segmentation significantly improved.** Now handles: 200+ abbreviations, URLs, email addresses, decimal numbers, single-letter initials (J.K. Rowling), ellipsis, and numbered list markers. Uses multi-phase protection-and-restore approach for robustness.
- Expanded abbreviation set from ~55 to ~200 entries, covering titles, military ranks, academic degrees, business entities, Latin phrases, months, time, countries, references, units of measurement, and US state codes.
- Version bumped to 0.2.0.

### Fixed
- Sentence segmentation no longer breaks on URLs or email addresses.
- Sentence segmentation no longer breaks on numbered list markers ("1.", "a.").
- Decimal numbers (3.14, $5.00) no longer trigger false sentence boundaries.

## [0.1.0] - 2026-07-18

### Added
- Initial project conception and problem selection.
- Repository documentation: MISSION.md, DECISIONS.md, PROGRESS.md, LIMITATIONS.md, SECURITY.md, TESTING.md, CHANGELOG.md.
- Core readability analysis engine with 6 metrics: Flesch Reading Ease, Flesch-Kincaid Grade Level, Gunning Fog Index, SMOG Index, Automated Readability Index, Coleman-Liau Index.
- Text simplification engine detecting 7 barrier types: passive voice, long sentences, complex words, nominalizations, jargon, redundant pairs, hidden verbs.
- Plain-language glossary with 300+ jargon-to-simpler mappings across bureaucratic, medical, legal, financial, tech, and academic domains.
- Accessible HTML report generator with embedded CSS.
- Console report formatter.
- CLI interface with `analyze`, `score`, and `version` commands.
- Comprehensive test suite (113 tests).
- Sample texts: legal pleading, medical discharge instructions, plain language guide.

### Fixed
- Syllable counter bug: silent-e removal interfering with -le pattern detection.
- HTML template escaping: CSS braces conflicting with Python str.format().
- Test expectation alignment with heuristic accuracy limits.
