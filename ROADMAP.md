# Roadmap — PlainSpeak Next Stages

## Context

This document was created on 2026-08-11, several weeks after the initial 24-hour autonomous build experiment that produced PlainSpeak v0.1.0. It defines the next stages of development, building on what was learned and addressing the most critical gaps identified in the original experiment.

The original prompt asked for a project that:

> "solve a meaningful human problem; reduce harm, waste, inequality, confusion, or unnecessary effort; expand access to knowledge, safety, opportunity, or essential services."

PlainSpeak v0.1.0 established a credible foundation. The next stages are about making that foundation reach the people it was built for.

---

## Where we are now (v0.1.0 recap)

| Capability | Status |
|---|---|
| 6 readability metrics | ✅ Working, tested |
| 7 barrier detection types | ✅ Working, tested |
| 420+ term plain-language glossary | ✅ Working, tested |
| HTML/console/JSON output | ✅ Working, tested |
| CLI interface (Click) | ✅ Working, tested |
| 142 tests, all passing | ✅ |
| Comprehensive documentation | ✅ |

**The single biggest gap:** The intended beneficiaries — people with lower literacy, non-native speakers, people with cognitive disabilities, elderly people — are the *least* likely to use a command-line tool. The tool works, but it doesn't reach its audience.

---

## Phase 2: Local Web Application ⭐ HIGHEST PRIORITY

> **Goal:** Make PlainSpeak accessible to non-technical users while preserving the offline, privacy-first architecture.

### 2.1 Local web server

Build a lightweight local web application using Flask (or a single-file approach with Python's `http.server`). The app runs entirely on localhost — no deployment, no cloud, no accounts.

**Features:**
- Paste or type text into a text area, or drag-and-drop a `.txt` file
- Run analysis with a single click
- View results in an interactive, accessible web report
- Toggle between summary view and detailed barrier-by-barrier view
- Highlighted text showing which passages triggered each barrier
- Download the full HTML report (the existing reporter format)
- Copy simplified text to clipboard
- Dark mode / high-contrast mode toggle

**Architecture:**
- Backend: Flask (or FastAPI) serving the existing `plainspeak` analyzers
- Frontend: Minimal vanilla HTML/CSS/JS — no framework, no build step, no npm
- All processing stays local; the browser talks to localhost only
- Single `plainspeak web` command to start the server and open the browser

**Why this matters:**
- Removes the terminal barrier entirely
- The same people the mission describes can now actually use the tool
- Preserves all privacy guarantees (nothing leaves the machine)
- A web interface also enables future use on shared machines (libraries, community centers, clinics)

### 2.2 Real-time analysis

As the user types or pastes text, show live readability scores and barrier counts that update on each keystroke (debounced). This turns the tool from a "check after writing" workflow into a "see as you write" companion.

### 2.3 Browser extension (stretch goal for Phase 2)

A minimal browser extension (Chrome/Firefox) that:
- Adds a toolbar button to analyze the current page's selected text
- Shows a popup with readability scores and top barriers
- Links to the full local web app for detailed analysis

---

## Phase 3: Accuracy & Robustness Improvements

> **Goal:** Improve the reliability of the core analysis so users can trust the output.

### 3.1 Better sentence segmentation

The current regex-based sentence splitter fails on abbreviations ("Dr.", "U.S.", "Ph.D."), decimal numbers, ellipses, and dialogue. 

**Approach:**
- Implement a rule-based segmenter using the known abbreviation list more aggressively
- Add handling for common edge cases: numbered lists, honorifics, initials, domain names
- Add a test corpus of 200+ tricky sentences with known-correct segmentations
- Target: reduce segmentation errors by 50%+

### 3.2 Improved syllable counting

Current accuracy is ~85-95%. The error propagates to Flesch-Kincaid and other syllable-dependent metrics.

**Approach:**
- Embed a lookup dictionary of the 5,000 most common English words with verified syllable counts (sourced from CMU Pronouncing Dictionary or similar open data)
- Fall back to the pattern-based heuristic only for words not in the dictionary
- This gives near-100% accuracy on common words while keeping the zero-dependency architecture (the dictionary is a data file, not a service)
- Target: 98%+ accuracy on typical English text

### 3.3 Smarter simplification

The current `simplify` command does word-level substitution only, which can produce ungrammatical output.

**Approach:**
- Add part-of-speech awareness using a lightweight tagger (e.g., a rule-based tagger or a small pre-trained model embedded as a data file)
- Detect when a substitution would require grammatical adjustment (e.g., "the implementation of" → "carrying out" needs the gerund form)
- Mark uncertain substitutions more prominently, and suppress substitutions that would clearly break grammar
- Add before/after diff view in reports

### 3.4 Document format support

Currently only plain text (`.txt`) is supported.

**Approach:**
- Add `.docx` reading (using `python-docx`, optional dependency)
- Add `.pdf` reading (using `pypdf`, optional dependency — text extraction only, no OCR)
- Add `.html` reading (strip tags, extract text content)
- Add `.md` reading (treat as plain text with optional heading awareness)

---

## Phase 4: Empirical Validation

> **Goal:** Answer the most important open question — does PlainSpeak actually help people understand text better?

### 4.1 Structured readability study

Design and conduct a small controlled study:
- Recruit 20-30 participants across literacy levels
- Give each participant two documents: one original, one with PlainSpeak-guided revisions
- Measure comprehension using multiple-choice questions and free-recall summaries
- Measure reading time and self-reported difficulty
- Compare comprehension scores between original and revised versions

### 4.2 Suggestion quality audit

- Have 3-5 plain-language experts review a sample of 100 suggestions
- Rate each as: helpful, neutral, unhelpful, or harmful
- Use results to prune and refine the glossary
- Publish the audit results transparently

### 4.3 Screen reader testing

- Test the HTML report with NVDA (Windows) and VoiceOver (macOS)
- Test the web app interface with screen readers
- Fix any accessibility barriers found
- Document the testing process and results

---

## Phase 5: Multi-Language Foundation

> **Goal:** Lay the groundwork for extending PlainSpeak beyond English.

### 5.1 Architecture for multi-language support

- Refactor the analyzer to accept language-specific configurations (metrics, patterns, glossaries)
- Define a language plugin interface
- Implement Spanish as a proof-of-concept second language:
  - Fernández-Huerta readability formula (Spanish adaptation of Flesch)
  - Spanish-specific barrier patterns (gerund overuse, long noun phrases, subjunctive complexity)
  - Spanish plain-language glossary (100+ terms initially)

### 5.2 Community contribution framework

- Document how to contribute a new language
- Provide templates for glossary, barrier patterns, and metric implementations
- Set up a structure for community-maintained language packs

---

## Phase 6: Ecosystem & Distribution

> **Goal:** Get PlainSpeak into the hands of people and organizations that need it.

### 6.1 Package distribution
- Publish on PyPI as `plainspeak`
- Create a standalone executable (via PyInstaller or Nuitka) for Windows, macOS, Linux — zero install, double-click to run the web app
- Create a Docker image for server deployments

### 6.2 Integrations
- WordPress plugin (analyze posts/pages before publishing)
- Google Docs add-on (analyze selected text within a document)
- CI/CD action (GitHub Action to check readability of documentation in PRs)

### 6.3 Partnerships & outreach
- Reach out to plain-language advocacy organizations
- Offer the tool to public libraries, legal aid clinics, community health centers
- Create a "Plain Language in Practice" guide with case studies

---

## Prioritization summary

| Priority | Phase | Why |
|---|---|---|
| 🔴 **Now** | Phase 2: Web App | The biggest gap between the tool and its intended beneficiaries. Without this, the project fails its mission. |
| 🟡 **Next** | Phase 3: Accuracy | Builds trust in the tool. Better sentence splitting and syllable counting directly improve every feature. |
| 🟢 **Then** | Phase 4: Validation | Answers the fundamental question: does this actually help people? Required before promoting the tool for real-world use. |
| 🔵 **Later** | Phase 5: Multi-Language | Expands the beneficiary base by an order of magnitude. Requires Phase 3-4 learnings first. |
| ⚪ **Future** | Phase 6: Ecosystem | Distribution and integration — only valuable once the tool is validated and reliable. |

---

## Immediate next actions (this session)

1. **Build the local web application** (Phase 2.1):
   - Add Flask as an optional dependency
   - Create `plainspeak/web.py` with routes for analysis and report viewing
   - Create `plainspeak/templates/` with the web interface HTML
   - Add `plainspeak web` CLI command to start the server
   - The web app reuses 100% of the existing analyzer, simplifier, glossary, and reporter modules

2. **Add real-time analysis endpoint** (Phase 2.2):
   - POST `/api/analyze` endpoint returning JSON
   - Frontend debounced textarea that calls the endpoint on input
   - Live-updating score display

3. **Improve sentence segmentation** (Phase 3.1, partial):
   - Enhance the abbreviation list
   - Add handling for numbered lists, initials, and domain-like patterns

4. **Update documentation** to reflect the new capabilities

---

## Principles carried forward from the original experiment

- **Offline-first.** No network requests. No accounts. No data collection.
- **Deterministic and auditable.** Rule-based where possible. ML only if it can run locally and explain itself.
- **Honest about limitations.** Every feature documents what it cannot do.
- **Built for the people who need it most,** not for the people who find it easiest to use.
- **Free and open source.** MIT license. Community contributions welcomed.

---

*This roadmap is a living document. It will be updated as we learn from building and from users.*
