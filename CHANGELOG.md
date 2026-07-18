# Changelog

All notable changes to PlainSpeak will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
