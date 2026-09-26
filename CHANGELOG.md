# Changelog

All notable changes to PlainSpeak will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

PlainSpeak Next has not yet made a release. Everything since the fork is under
**Unreleased**, and the package still reports the last upstream version,
`0.3.0`. Entries for `0.3.0` and earlier describe the upstream project
([Project-PlainSpeak](https://github.com/hourwise/Project-PlainSpeak)), whose
history this repository preserves; see [UPSTREAM.md](UPSTREAM.md).

## [Unreleased] — PlainSpeak Next

Development after the fork at `74ecd51` (2026-08-29 onward). Each phase is
described in full in its commit messages and in the document linked.

### Added
- **Phase 0–1.** Lineage record ([UPSTREAM.md](UPSTREAM.md)), cross-platform CI
  (Windows, Linux, macOS; Python 3.10 and 3.13), line-ending normalisation, and a
  characterisation seal pinning inherited behaviour byte-for-byte.
- **Phase 2.** Layered package — `core`, `document`, `integrity`, `reporting`,
  `adapters` — with the old module paths kept as compatibility shims, and an
  import policy enforced by tests ([ARCHITECTURE.md](ARCHITECTURE.md)).
- **Phase 3 / 3.5.** Document representation with exact source spans; the
  analysis projection; separate analysis and editing authority; fail-closed
  refusal of any text whose location cannot be established exactly.
- **Phase 4.** Declarative YAML rules with versioned, hash-identified rulesets,
  deterministic planning and atomic application; `plainspeak rules list` and
  `plainspeak rules explain`.
- **Phase 5.** The integrity firewall: numbers, dates, money, units, identifiers,
  negation, modals and comparators must survive every change. No override.
- **Phase 6.** Bounded deterministic morphology; all 706 inherited glossary
  entries inventoried, classified and migrated ([GLOSSARY_MIGRATION.md](GLOSSARY_MIGRATION.md)).
- **Phase 7.** Thirteen document-level style diagnostics, each reported with its
  arithmetic; no verdicts and no authorship claims ([STYLE_CALIBRATION.md](STYLE_CALIBRATION.md)).
- **Phase 8.** Five calibrated profiles — Natural, Plain, Technical, Government,
  Academic; `plainspeak profiles list` and `plainspeak profiles explain`
  ([STYLE_PROFILES.md](STYLE_PROFILES.md)).
- **Phase 9.** Eight profile-gated style fixes, every one requiring human review;
  `plainspeak style preview` ([STYLE_TRANSFORMATIONS.md](STYLE_TRANSFORMATIONS.md)).
- **Phase 10.** `plainspeak-desktop`, a PySide6 review application with
  side-by-side panes, per-suggestion Accept and Reject, non-overridable
  refusals and Save As only; portable Windows and Linux builds with out-of-tree
  self-tests ([DESKTOP_MVP.md](DESKTOP_MVP.md)).
- [ROADMAP.md](ROADMAP.md) rewritten for PlainSpeak Next, and
  [V1_SCOPE.md](V1_SCOPE.md) defining what 1.0 will and will not promise.

- **`plainspeak present`** — the governed, non-interactive transformation:
  every SAFE change applied, REVIEW proposals reported and never applied,
  refusals explained. Emits the versioned `plainspeak.present.v1` JSON contract
  (or `text`, `marked`, `summary`), reads a file or standard input, and never
  writes its input. `plainspeak.pipeline.present` / `present_text` in Python.

### Changed
- **One engine.** `plainspeak simplify` is now a deprecated alias for
  `present --format marked`, and requires `--profile`. The web interface's
  simplified text is the governed presentation. Both previously called the
  inherited substitution engine directly, with no integrity firewall — it
  turned "leverages" into "borrowed money" and "shall" into "must". A new
  architecture test forbids any interface from importing that engine.

### Fixed
- `plainspeak.pipeline.ReviewError` now catches every review refusal. Two
  unrelated classes shared the name, and the package exported the one the
  review facade does not raise.
- The desktop session no longer keeps a review decision the engine refused, so
  what it holds always matches the preview on screen.
- An integrity refusal no longer prints the same violation twice.
- The syllable dictionary, bundled rules and profiles are now included in built
  wheels and frozen desktop bundles; before this, installs silently fell back to
  heuristics or loaded no rules at all.

## [0.3.0] - 2026-08-11

Upstream release, recorded here from commit `ec748df`; it was not previously in
this file.

### Added
- Dictionary-backed syllable counting from the CMU Pronouncing Dictionary
  (125K+ words), with a heuristic fallback for unknown words.
- Grammar post-processing after substitutions: a/an agreement and sentence
  capitalisation.
- Multi-format reader for `.txt`, `.md`, `.docx`, `.pdf` and `.html`, with
  optional `python-docx` and `pypdf` extras.
- Glossary expansions (legal, academic, phrase-level matching) and stemming
  fixes.

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
