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
3. ✅ **Post-fix style validation.** Style is re-measured after SAFE changes, and a
   set of changes that makes a governed diagnostic worse is not applied. The
   engine's own replacements must not be able to evade its own metrics.
   Delivered with honest connective counting, which also exposed two style
   fixes that only ever appeared to work; they were retired.
4. ✅ **First integrity equivalences.** A small, versioned, adversarially tested
   table of forms the firewall treats as the same fact (starting with
   "prior to" ≡ "before"). The firewall stays fail-closed.
5. ✅ **Short-text honesty.** Below a diagnostic's minimum sample, PlainSpeak says
   there was not enough text to judge rather than implying the text is clean.

## Stage 2 — V1 release *(1.0.0 published)*

`1.0.0` is published on PyPI as `plainspeak-next` and on GitHub as `v1.0.0`,
with portable Windows and Linux desktop bundles, a "how it works and what it
guarantees" document, and a walkthrough. The evidence is in
[RELEASE_READINESS.md](RELEASE_READINESS.md). V1's public contracts are the
compatibility baseline for everything below.

## V2 — Verify, the GitHub Action and MCP *(implemented and validated on `codex/plainspeak-v2-verify`; not yet accepted)*

What V2 promises is in [V2_SCOPE.md](V2_SCOPE.md). Every V1 contract is
unchanged; V2 is additive.

### Stage 3 — Verify *(V2-A)*

`plainspeak verify BEFORE AFTER` judges a transformation made by anyone —
PlainSpeak, a person, a language model, an agent, other software — against the
integrity model: `ACCEPTED`, `REFUSED` or `INCONCLUSIVE`, never collapsing
unknown into safe. `plainspeak.verify.v1`, a deterministic receipt, exit
statuses for CI. See [VERIFY.md](VERIFY.md).

### Stage 3b — GitHub Action *(V2-B)*

`uses: hourwise/PlainSpeak-Next@<ref>` runs the same verifier in a workflow,
fails on `REFUSED` or `INCONCLUSIVE` by default, annotates the lines concerned
and keeps the receipt. Dogfooded on Linux and Windows.

### Stage 4 — MCP *(V2-C)*

`plainspeak serve` exposes `present`, `verify` and `diagnose` to an agent as MCP
tools over stdio, returning the CLI's contracts byte for byte. MCP is an
adapter: the architecture tests keep it at the edge exactly as they keep the CLI
and desktop there. See [MCP.md](MCP.md).

### Stage 4b — Validation *(V2-D)*

97 transformations from ten classes, judged by hand before Verify ran. The first
run found a false acceptance of protected meaning; it was fixed and the final
run has none. See [VERIFY_STUDY.md](VERIFY_STUDY.md).

### Stage 4c — Field findings *(V2-E)*

Field testing of the published 1.0.0 found an unsafe SAFE rule (facilitate →
help), a readability verdict on three words, and hard-to-discover `--stdin`.
All fixed; a bounded audit reclassified 27 more rules, and an independent
review of the Verify study 14 more. 97 of 220 rules remain automatic. See
[V2_FIELD_FINDINGS.md](V2_FIELD_FINDINGS.md).

*Backlog:* `plainspeak explain before.txt after.txt` — a semantic/style diff that
classifies each difference as SAFE, PRESERVED, REVIEW or REFUSED.

## After V2 — recorded, not scheduled

These are directions, not commitments. None is implemented, and nothing below
was begun as part of V2.

### Findings from the V2 validation study

Verify's false refusals come from the integrity model's deliberate strictness.
Each of these would widen what the V1 firewall admits, so each is an integrity
policy change — versioned, adversarially tested in both directions, and weighed
against the V1 breaking-change boundary — never a Verify-only shortcut:

- reviewed comparator equivalences: "at most" ≡ "up to" ≡ "no more than";
  "not less than" ≡ "at least"; "no longer than" ≡ "up to";
- directional words as protected comparators: "above", "below", "under",
  "over", "exceeds" (today a change between them is INCONCLUSIVE, not REFUSED);
- date equivalences across written forms (`12/08/2026` and `12 August 2026`),
  which need a locale decision;
- modal ellipsis: "must be encrypted and tested" carrying the "must" of "must be
  encrypted and must be tested".

### Stage 5 — Speech

Two modes, kept distinct and never described as one another.

**Deterministic Speech.** Rules convert text into a spoken-friendly
representation — contractions, safe sentence splitting, number, date, unit and
currency rendering, spoken transitions, pause metadata, pronunciation handling
and SSML delivery. The same input, profile and ruleset produce the same spoken
script.

**Verified Speech.** A model proposes more substantial spoken restructuring, and
PlainSpeak Verify decides whether the proposed spoken version is admissible:
*the model proposes, PlainSpeak disposes*. The proposal is probabilistic; the
admission decision is deterministic. This mode is never described as
deterministic generation. Deterministic verification is not deterministic
generation.

Spoken-form integrity equivalences (currency, numbers, dates, units) come first,
because without them the firewall correctly refuses "£1,200" becoming "twelve
hundred pounds". PlainSpeak produces the script and delivery instructions; it
does not become a speech synthesiser.

### Stage 6 — Commercial boundary

Decided only after Verify, the Action and MCP have real users; V2's real-world
use should inform it. Not implemented, and not to be implemented early:
organisation policy packs, central rule management, signed receipts, a hosted
gateway, an enterprise audit dashboard, licence enforcement.

| Open | Possible commercial layer |
|---|---|
| Deterministic engine, core profiles | Organisation-specific policy packs (e.g. GOV.UK style, Simplified Technical English, Consumer Duty) |
| CLI, `present`, `verify`, the GitHub Action | Central policy administration and rule distribution |
| Desktop application | Audit histories and signed receipts |
| Local MCP server | Hosted or on-premises gateway, integration and support |
| Basic policy tooling | |

The core is not to be closed early. This table is a hypothesis until users
validate it.

## Will not be built

A general-purpose language model; a grammar checker in the Grammarly mould; an
AI-authorship detector; a plagiarism detector; an autonomous author; a planning
or reasoning engine; a speech synthesiser. Each would dilute the thing that is
unusual here: deterministic transformation under semantic constraints.
