# Decisions

A chronological record of major decisions, alternatives considered, rationale, trade-offs, and reversal conditions.

---

## Decision 1: Problem domain — Language accessibility vs. other candidates

**Date:** 2026-07-18, Hour 0  
**Status:** Accepted

### Alternatives considered

| Problem | Potential benefit | Feasibility (24h) | Neglected? | Risk of harm |
|---|---|---|---|---|
| Readability / plain-language toolkit | High — affects millions daily | High — established metrics, rule-based | Yes — few free, offline tools | Low |
| Digital accessibility audit (WCAG checker) | High — web accessibility gap | Medium — HTML parsing needed | Partially — some open tools exist | Low |
| Personal data exposure auditor | Medium — privacy awareness | Low — requires network, external APIs | Partially | Medium — could surface sensitive data |
| Medical jargon translator | High — health literacy | Low — needs domain knowledge base | Yes | High — risk of mistranslation |
| Community resource sharing protocol | Medium — social cohesion | Low — needs network, coordination | Yes | Low |
| Algorithmic transparency explainer | Medium — digital rights | Low — needs platform-specific knowledge | Yes | Low |
| Carbon footprint calculator | Low-Medium — many exist | High | No — well-served | Low |

### Decision

Build **PlainSpeak**: a readability analysis and text simplification toolkit as a Python library with CLI.

### Rationale

1. **Highest feasibility-to-impact ratio.** Readability formulas are well-documented and mechanically computable. Rule-based pattern matching for complex constructions is achievable. The core value — measuring and reporting on text complexity — can be delivered without any external services or ML models.

2. **Genuinely neglected.** Free readability tools exist (e.g., `textstat` Python library) but they rarely combine measurement with explanation, actionable guidance, and accessible output. Most are developer-oriented libraries, not tools a non-technical person could use.

3. **Builds on established science.** Flesch-Kincaid, Gunning Fog, SMOG, and other metrics have decades of validation. We are not inventing new measures — we are making existing ones more accessible.

4. **Clear validation path.** Known-answer tests can verify metric computation. Human review can validate suggestion quality on sample texts.

5. **Zero dependency on external services.** Everything runs locally. No API keys, no network, no privacy risk.

### Trade-offs accepted

- **No ML-based simplification.** Rule-based suggestions are less sophisticated than what an LLM could produce. However, they are deterministic, auditable, and cannot introduce hallucinated meanings.
- **English-only initially.** Readability formulas exist for other languages but require separate validation.
- **No browser-based UI.** CLI + HTML report output is less immediately approachable than a web app, but avoids the complexity of a frontend build.

### Reversal conditions

If evidence emerges that:
- Rule-based simplification produces unhelpful or misleading suggestions at an unacceptable rate, we will restrict scope to measurement and identification only (removing the suggestion feature).
- The target audience cannot practically use a CLI tool, we will consider a simple local web interface.

---

## Decision 2: Technology stack — Python with standard library emphasis

**Date:** 2026-07-18, Hour 0  
**Status:** Accepted

### Alternatives considered

| Stack | Pros | Cons |
|---|---|---|
| Python (stdlib-heavy) | Readable, widely available, fast to prototype | Slower execution, packaging complexity |
| JavaScript/Node.js | Could run in browser, npm ecosystem | Async complexity, less readable for text processing |
| Rust | Fast, safe, single binary | Slower to develop, fewer potential contributors |
| Go | Fast, simple deployment | Less natural for text processing |

### Decision

Python 3.10+ with minimal dependencies. Use only `click` for CLI (potentially) and standard library otherwise.

### Rationale

- Python is the most accessible language for potential contributors in education, public service, and linguistics.
- Text processing is natural in Python.
- Standard library includes `re`, `string`, `html`, `json`, `argparse`, `statistics` — sufficient for the core features.
- If the project succeeds, porting to a faster language is straightforward.

### Trade-offs

- Python packaging can be confusing for non-developers. We will provide clear installation instructions.
- Performance is adequate but not optimal for very large documents.

---

## Decision 3: Project name — "PlainSpeak"

**Date:** 2026-07-18, Hour 0  
**Status:** Accepted

Simple, descriptive, not trademarked in the software tools space to our knowledge. The package will be `plainspeak`.

---

## Decision 4: Output format — Self-contained HTML report

**Date:** 2026-07-18, Hour 0  
**Status:** Accepted

### Alternatives

- **Plain text:** Simple but cannot convey structure, color-coding, or interactive elements.
- **JSON:** Machine-readable but not human-friendly for the primary audience.
- **PDF:** Requires additional dependencies, harder to make accessible.
- **HTML:** Self-contained, can be opened in any browser, supports accessible markup, can include inline CSS, requires no server.

### Decision

Generate a single, self-contained HTML file with embedded CSS. The report must itself pass WCAG 2.1 AA automated checks.

---

## Decision 5: Dependency — Use `click` for CLI

**Date:** 2026-07-18, Hour 0  
**Status:** Accepted

### Alternatives

- `argparse` (stdlib): Adequate but verbose. Would work but adds boilerplate.
- `typer`: Newer, uses type hints. Similar dependency weight to `click`.

### Decision

Use `click` — mature, well-maintained, widely used, reduces CLI boilerplate significantly. This is the only non-stdlib dependency.

### Reversal

If `click` proves problematic or if zero-dependency is deemed valuable, we will replace with `argparse`. The CLI surface is small enough that this is a low-cost change.
