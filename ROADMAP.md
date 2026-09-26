# Roadmap

PlainSpeak Next is a deterministic presentation engine for machine-generated
and institutional prose. The upstream system decides what a text means;
PlainSpeak decides how that meaning may safely be presented to a person, and
refuses any change that would alter protected information.

This file records what has been built and accepted, what V1 still needs, and
what comes after it. A phase is **accepted** only when every checkpoint commit
in it is green and it has been fast-forwarded onto `main`. *Implemented* and
*accepted* are different states, and this file does not blur them.

The roadmap of the original 24-hour experiment (v0.1–v0.3) is preserved in Git
history at `74ecd51` and in [`Experiment Report.md`](Experiment%20Report.md). It
no longer describes this project's direction.

## Accepted

| Phase | What it established |
|---|---|
| 0 | Lineage fork with history preserved, provenance ([UPSTREAM.md](UPSTREAM.md)), cross-platform CI |
| 1 | Characterisation seal: inherited behaviour pinned byte-for-byte by golden fixtures |
| 2 | Layered package (`core`, `document`, `integrity`, `reporting`, `adapters`) behind compatibility shims |
| 3 / 3.5 | Document representation with exact source spans; analysis projection; separate analysis and editing authority; fail-closed on unmappable text |
| 4 | Declarative, versioned, hash-identified rule system with deterministic planning and atomic application |
| 5 | Integrity firewall: numbers, dates, money, units, identifiers, negation, modals and comparators must survive every change |
| 6 | Bounded deterministic morphology; all 706 inherited glossary entries inventoried, classified and migrated |
| 7 | Document-level style diagnostics — measurements with evidence, no verdicts and no authorship claims |
| 8 | Five calibrated profiles: Natural, Plain, Technical, Government, Academic |
| 9 | Profile-gated style fixes that always require human review |
| 10 | PySide6 desktop review application; frozen Windows and Linux builds with out-of-tree self-tests ([DESKTOP_MVP.md](DESKTOP_MVP.md)) |

Phase 10 was first built on `codex/plainspeak-phase-10-desktop-review` and
rejected, because one intermediate checkpoint (`ad7c3b0`) introduced the desktop
package before its architecture-policy entry and was red. It was reissued on
`codex/plainspeak-phase-10-reissue` with the policy entry in the checkpoint that
introduces the package. The rejected branch is kept as evidence.

## Stage 0 — Repair the record *(complete)*

Documentation brought into agreement with the code; the legacy unguarded paths
labelled as such; [V1_SCOPE.md](V1_SCOPE.md) written before any V1 feature code.

## Stage 1 — V1 blockers

1. ✅ **One engine.** Every user-facing rewriting path goes through the governed
   pipeline. `simplify` is a deprecated alias for `present`, the web UI presents
   through it, and a test forbids any interface from importing the inherited
   substitution engine.
2. ✅ **`plainspeak present`.** Non-interactive. Applies SAFE changes only, never a
   review-required one, and emits a versioned machine-readable contract: input
   and output hashes, engine identities, applied changes, pending reviews,
   refusals, protected facts and diagnostics. MCP and other adapters will reuse
   this contract rather than invent their own.
3. **Post-fix style validation.** Style is re-measured after SAFE changes, and a
   set of changes that makes a governed diagnostic worse is not applied. The
   engine's own replacements must not be able to evade its own metrics.
4. **First integrity equivalences.** A small, versioned, adversarially tested
   table of forms the firewall treats as the same fact (starting with
   "prior to" ≡ "before"). The firewall stays fail-closed.
5. **Short-text honesty.** Below a diagnostic's minimum sample, PlainSpeak says
   there was not enough text to judge rather than implying the text is clean.

## Stage 2 — V1 release

A certified release candidate: Python package, portable Windows and Linux
desktop bundles, a "how it works and what it guarantees" document, and a
walkthrough a new user can follow without reading the source. `1.0.0` is tagged
and published only after the release-readiness report is green **and**
publication has been explicitly authorised.

## After V1 — recorded, not scheduled

These are directions, not commitments. None is implemented.

### Stage 3 — Verify

`plainspeak verify before.txt after.txt` exposes the integrity firewall for any
pair of texts, whoever produced the rewrite: PlainSpeak, another model, a
person, an agent, or third-party software. A GitHub Action would follow. This
may become PlainSpeak's strongest standalone capability, because it is useful
even to people who never use PlainSpeak's own transformations.

*Backlog, not before V1:* `plainspeak explain before.txt after.txt` — a
semantic/style diff that classifies each difference as SAFE, PRESERVED, REVIEW
or REFUSED.

### Stage 4 — MCP

`plainspeak serve` exposes thin adapters over canonical pipeline operations
(`present`, `verify`, `diagnose`). MCP must not become another engine; the
architecture tests keep it at the edge exactly as they keep the CLI and desktop
there.

### Stage 5 — Speech

Two guarantees, kept distinct and never described as one another.

**Deterministic.** Rules convert text into a spoken-friendly representation:
contractions, safe sentence splitting, number/date/unit/currency rendering,
spoken transitions, pause metadata, pronunciation handling and SSML. Same input,
profile and ruleset produce the same spoken script.

**Verified.** A model may propose more substantial spoken restructuring, and
PlainSpeak decides whether to admit it: *the model proposes, PlainSpeak
disposes*. The proposal is probabilistic; the admission decision is
deterministic. This mode is never described as deterministic generation.

Spoken-form integrity equivalences (currency, numbers, dates, units) come first,
because without them the firewall correctly refuses "£1,200" becoming "twelve
hundred pounds". PlainSpeak produces the script and delivery instructions; it
does not become a speech synthesiser.

### Stage 6 — Commercial boundary

Decided only after Verify and MCP have real users. The working hypothesis:

| Open | Possible commercial layer |
|---|---|
| Deterministic engine, core profiles | Organisation-specific policy packs (e.g. GOV.UK style, Simplified Technical English, Consumer Duty) |
| CLI, `present`, `verify` | Central policy administration and rule distribution |
| Desktop application | Audit histories and signed presentation receipts |
| Local MCP server | Hosted or on-premises gateway, integration and support |
| Basic policy tooling | |

The core is not to be closed early. This table is a hypothesis until users
validate it.

## Will not be built

A general-purpose language model; a grammar checker in the Grammarly mould; an
AI-authorship detector; a plagiarism detector; an autonomous author; a planning
or reasoning engine; a speech synthesiser. Each would dilute the thing that is
unusual here: deterministic transformation under semantic constraints.
