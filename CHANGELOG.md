# Changelog

All notable changes to PlainSpeak will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

PlainSpeak Next's first release is **1.0.0**, published on PyPI as
`plainspeak-next`. Everything since the fork is under it and the **1.0.0rc1**
release candidate. Entries for `0.3.0` and earlier
describe the upstream project
([Project-PlainSpeak](https://github.com/hourwise/Project-PlainSpeak)), whose
history this repository preserves; see [UPSTREAM.md](UPSTREAM.md).

## [Unreleased]

The 1.1.0 release candidate: Verify, the GitHub Action and the MCP server, and
fixes for defects found by field testing of the published 1.0.0. Every 1.0.0
contract keeps its shape. Recommended version: 1.1.0 ([V2_SCOPE.md](V2_SCOPE.md)).

### Fixed — found by field testing of 1.0.0
- **An unsafe automatic rewrite (FIELD-001).** 1.0.0 turned "In order to
  facilitate the completion of the task" into "To help the completion of the
  task": "facilitate X" is "make X easier", "help X" is "assist X".
  `PS.LEXICAL.153` is now a diagnostic. A bounded audit of every automatic
  lexical rule for the same defect reclassified 27 more — separable phrasal
  verbs before a pronoun ("reimburse you" → "pay back you"), reversed or changed
  meanings ("comprises five members" → "makes up five members"), adjectival
  participles ("augmented reality" → "added to reality") and terms of art
  ("comprehensive insurance", "a preliminary hearing", "quantitative easing").
  Ruleset 2026.6: 220 rules, 111 automatic; every rule keeps its ID. 25 of 145
  checked `present` outputs change, each only by no longer applying one of these
  rules.
- **A readability verdict on three words (FIELD-003).** `analyze` called "Please
  check this." grade 2, "Very easy". A sample under 100 words or 3 sentences is
  now reported as an insufficient sample: raw scores kept, no band or verdict.
  The JSON report gains a `sample` object; no existing field changes.
- **Piped text without `--stdin` (FIELD-002).** `analyze`, `present` and
  `diagnose` now say when text is being piped in without `--stdin`, and show
  the command that works; help shows `--stdin` examples and that `--profile`
  has no default. Input semantics and exit statuses are unchanged.

- **Fourteen more SAFE rules reclassified after an independent review of the
  Verify study** (ruleset 2026.7), which held each accepted SAFE substitution to
  every context its matcher can reach: "must notify the authority in writing"
  became "must tell"; "retained earnings" became "kept earnings";
  "modified-release tablets" became "changed-release"; "enhanced due
  diligence", "the additional rate" and "possess a controlled drug" are terms
  of art; "Keep your papers in order to avoid delays" became "Keep your papers
  to avoid delays"; a mid-sentence "furthermore", "moreover" or "additionally"
  became a comma-bound "also". Found alongside: "Please act accordingly" became
  "Please act so", "consequently" likewise, "hereafter" in a definition became
  "from now on", "A large number of them" became "Many them". 97 of 220 rules
  are now automatic; every ID is unchanged. The certification sample keeps "In
  order to".

See [V2_FIELD_FINDINGS.md](V2_FIELD_FINDINGS.md).

### Added
- **`plainspeak verify BEFORE AFTER`** judges a transformation made by anyone —
  a person, a language model, an agent, other software — against the integrity
  model: `ACCEPTED`, `REFUSED` or `INCONCLUSIVE`, never collapsing unknown into
  safe. Refuses any change to a protected fact, a term of art, or a region
  PlainSpeak never rewrites; accounts for formatting, reviewed equivalences,
  PlainSpeak's own SAFE rules in either direction, and a time or limit phrase
  moving within its sentence; reports everything else as unresolved. Swapped
  values and obligations — which a count of protected facts alone would pass —
  are not accepted. Versioned `plainspeak.verify.v1` JSON contract, a
  deterministic receipt (`plainspeak.verify.receipt.v1`), verification policy
  `2026.1`, and exit statuses for CI (0 accepted, 1 refused, 3 inconclusive,
  4 input error, 5 internal error). See [VERIFY.md](VERIFY.md).
- **GitHub Action** (`action.yml`): `uses: hourwise/PlainSpeak-Next@<ref>` with
  `before` and `after`. Fails on REFUSED or INCONCLUSIVE by default
  (`fail-on: refused` or `never` to relax), annotates the lines concerned,
  writes a job summary, exposes the result and receipt as outputs and uploads
  them as an artifact. Installs PlainSpeak from its own source at the pinned ref
  into an isolated environment; inputs reach it only through the environment,
  paths are confined to the workspace, and document text written back out is
  escaped. Dogfooded by the `Verify action` workflow on Linux and Windows.
- **`plainspeak serve`**: a local MCP server over stdio exposing `present`,
  `verify` and `diagnose` as tools, returning the CLI's contracts byte for
  byte. No network, no file access, no commands, no mutation, no telemetry and
  no dependencies — the protocol subset is implemented with the standard
  library. Protocol revisions 2024-11-05 to 2025-11-25; interoperability
  checked against the official MCP Python SDK client. A new `mcp` layer may
  import only `pipeline`, and only `plainspeak serve` may import it. See
  [MCP.md](MCP.md).
- **`plainspeak diagnose`** and the `plainspeak.diagnose.v1` contract:
  everything `present` observes, applied to nothing, built from the same review
  bundle so the two cannot disagree; plus readability, rounded to two places.
- `plainspeak.pipeline.verify`, `verify_text` and `verify_files`.
- **Validation study** ([VERIFY_STUDY.md](VERIFY_STUDY.md)): 97
  transformations in ten classes, judged by hand before Verify ran. Final run:
  no false acceptance; every PlainSpeak transformation accepted; 35 changes of
  protected meaning all refused (26) or inconclusive (9); 17 false refusals,
  all from the integrity model's deliberate strictness. Re-run by
  `tests/test_verify_study.py` on every build.

### Fixed (during V2 development)
- **Verification policy 2026.2.** The validation study found two false
  acceptances under 2026.1: a time phrase fronted in a two-clause sentence
  ("Before 5pm, you must submit the form and pay the fee") and a
  sentence-initial case change ("Polish" → "polish"). A comparator phrase may
  now move only between the ends of a single-clause sentence whose other words
  are unchanged, and capitalisation is accounted for only when a word became or
  stopped being first in its sentence. 2026.1 was never published.
- Verify's refusals point at the occurrence that changed, not every line
  holding the same word; unresolved protected items are described as moved to
  another sentence, moved within it, or unmoved with the words around them
  changed.
- The GitHub Action gave every run in a job the same output directory, so a
  later run overwrote an earlier run's receipt while its output still pointed
  at it (found by the dogfood workflow). Architecture
  tests forbid any interface from containing a verifier of its own, and require
  each versioned contract to be defined in exactly one module.


The release candidate after a pre-release acceptance review that ran PlainSpeak
over 27 realistic documents and read the output
([V1_ACCEPTANCE_REVIEW.md](V1_ACCEPTANCE_REVIEW.md)).

### Changed
- **Ruleset 2026.5.** 25 migrated safe fixes reclassified as diagnostics: each
  broke a real sentence — "requests are rate-limited" became "asks are
  rate-limited", "undertakes to pay" became "does to pay", "convene a meeting"
  became "meet a meeting". Reported, no longer applied. Every rule keeps its ID.
- **Articles agree with replacements.** "An advantageous position" becomes "a
  helpful position"; "a sufficient reason" and "an optimal choice" are refused.
- **Reviewed readability suggestions** (suggestion review 2026.1). 71 inherited
  suggestions withdrawn and 5 corrected — "leverages" is no longer offered
  "borrowed money". Nominalisation and hidden-verb suggestions come from a
  reviewed table of 340 verbs: "make a decision" is offered "decide", not
  "deci". The inherited glossary is unchanged; the characterisation seal was
  re-pinned with every difference attributed to a reviewed term.
- **Profiles say what they change**: the CLI, the desktop and HOW_IT_WORKS.md
  state that a profile changes which observations are reported, not the SAFE
  changes or what is protected.
- The desktop smoke output is now `ca5d501239c0…`: the self-test document says
  "the panel approved the request", which every build since Phase 10 had
  pinned as "the panel approved the ask".

### Packaging
- **Published as `plainspeak-next`.** `plainspeak` on PyPI is an unrelated
  project that also installs a `plainspeak` package, so the distribution is
  `plainspeak-next`: `pip install plainspeak-next`. The import package and the
  command are unchanged — `import plainspeak`, `plainspeak` — and the two
  distributions cannot share an environment. The first 1.0.0 artifacts, built
  as `plainspeak`, could not be published under that name; the release was
  rebuilt and certified again (see [RELEASE_READINESS.md](RELEASE_READINESS.md)).
- **Trusted Publishing.** `.github/workflows/release.yml` publishes the
  certified wheel and sdist to PyPI through GitHub OIDC, from the `pypi`
  environment, after checking the tag, the version, the CI run and every
  checksum. No PyPI token exists.
- **Valid classifiers only.** `Intended Audience :: Government`, inherited and
  never a real classifier, is removed: PyPI refused the first 1.0.0 upload
  over it, after the release had been certified, tagged and approved.
  `tools/check_classifiers.py` now checks every classifier, declared and in
  the built metadata, against PyPI's own list, in CI and before release
  approval. The first `v1.0.0` tag and GitHub release were withdrawn and
  reissued (see [RELEASE_READINESS.md](RELEASE_READINESS.md)).

### Fixed
- The migration builder assigned rule IDs by position, so reclassifying one
  rule would renumber the rest. `migration/rule-ids.json` binds each ID to its
  term.

## [1.0.0rc1] — release candidate, not published

The first release candidate of PlainSpeak Next: everything since the fork at
`74ecd51` (2026-08-29 onward). Each phase is described in full in its commit
messages and in the document linked. Certification evidence:
[RELEASE_READINESS.md](RELEASE_READINESS.md).

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
- **Style guard on safe fixes.** Safe fixes that together would make a baseline
  style diagnostic more severe are refused rule by rule, with the diagnostic
  named. Three rules turning "Furthermore", "Moreover" and "Additionally" into
  "Also" had been able to make most of a document's sentences begin with it.
- **Integrity equivalences** (policy 2026.2): a versioned, adversarially tested
  table of spellings that are the same fact. One entry: "prior to" is "before",
  so `PS.CLARITY.009` now applies — and deleting "prior to" or turning it into
  "after", which the firewall previously did not protect, is now refused.
- **Short-text honesty.** Every style diagnostic reports whether the document
  had enough text for it (`style_coverage` in the JSON contract, the CLI
  summary, NOT ENOUGH TEXT rows in the desktop), so a short text is reported as
  not judged rather than clean.

### Changed
- **Style policy 2026.2** counts the connectives PlainSpeak's own rules write
  ("also", "so", "even so", "by contrast", "after that") when they open a
  sentence, and declares each diagnostic's sample unit. No threshold moved, and
  no baseline finding in the Phase 7 corpus changed. One Phase 8 false positive
  (`allotment-year.md`, repeated transition) no longer fires under the baseline.
- **Ruleset 2026.4** retires `PS.STYLEFIX.007` and `PS.STYLEFIX.008`, which
  answered transition density by swapping one connective for another and only
  appeared to lower it because the replacements were not counted. Six style
  fixes remain; a density finding now comes with nothing to review.
- Repeated-transition proposals are budgeted honestly: `concessive-heavy.md`
  under natural needs two, not four.
- **Version 1.0.0rc1.** The characterisation seal now redacts the package
  version, as it already redacted timestamps: a version is not behaviour, and
  sealing it made every release a change to the seal. Verified before
  re-sealing: under redaction the only differences were the version stamps
  themselves, and switching the version afterwards changes no golden file.
- `HOW_IT_WORKS.md`, `WALKTHROUGH.md`, `RELEASING.md`, and release tooling:
  `tools/package_release.py` (versioned archives and `SHA256SUMS`) and
  `tools/certify_release.py` (certifies an installed wheel from outside the
  checkout). CI now packages and certifies on every run.
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
