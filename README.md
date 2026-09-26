# PlainSpeak Next

**A deterministic presentation engine for prose.** PlainSpeak reads a document,
measures where it is hard going, and makes the changes it can prove are safe —
while refusing any change that would alter protected information such as a
number, a date, an amount, an identifier, a negation or an obligation.

> This is a **descendant** of [hourwise/Project-PlainSpeak](https://github.com/hourwise/Project-PlainSpeak),
> created from commit `74ecd51` with its full history preserved. Development here is
> independent and nothing syncs in either direction — see [UPSTREAM.md](UPSTREAM.md).

The upstream system — a person, a model, an agent — decides what a text means.
PlainSpeak decides how that meaning may safely be presented, and says exactly
what it changed, what it left for a person to decide, and what it refused.

- **Deterministic.** The same input, profile and ruleset give byte-identical
  output on every platform. No model, no randomness, no synonym roulette.
- **Integrity-protected.** Every change passes a firewall that refuses anything
  touching numbers, dates, money, units, identifiers, negation, modal verbs or
  comparators. It cannot be switched off.
- **Reviewable.** Mechanical changes are marked `SAFE`. Style suggestions are
  marked `REVIEW` and never happen without a person accepting them. Refusals are
  marked `REFUSED` and cannot be overridden.
- **Inspectable.** Rules are versioned YAML with hashes. Every result names the
  rule, policy and profile versions that produced it.
- **Offline.** No network on any path. No telemetry, no accounts.

It is not an AI detector, not a grammar checker and not a paraphrasing model.
See [V1_SCOPE.md](V1_SCOPE.md) for exactly what it does and does not promise.

## Status

Pre-release. The package still reports the last upstream version, `0.3.0`;
PlainSpeak Next has not yet made a release. Phases 0–10 and Stage 0 are accepted
on `main`, and the work towards 1.0 is in [ROADMAP.md](ROADMAP.md).

## Install

```bash
pip install -e ".[desktop]"     # engine, CLI and desktop application
pip install -e .                # engine and CLI only — no Qt
```

Python 3.10 or later. Tested on Windows, Linux and macOS.

## Desktop application

```bash
plainspeak-desktop
```

A native window with the original document on the left and the revised version
on the right.

> **PlainSpeak does not overwrite the document you open.** There is no Save
> command — only **Save As** — and Save As refuses any destination that
> resolves to the file you opened.

**Supported files.** `.txt`, `.md` and `.markdown`. DOCX, PDF and HTML are
refused with an explanation rather than opened: they currently load as
undifferentiated text, which is an honest fallback for analysis and a poor
foundation for editing.

**Profiles.** Natural, Plain, Technical, Government and Academic. The same
document is read against different expectations: a specification that repeats a
defined term forty times is doing its job, and the identical measurement in an
essay is a writer with a tic. Changing profile clears your review decisions,
because a decision belongs to the profile it was made under.

| | |
|---|---|
| `SAFE` | A mechanically safe change. Already applied; you can inspect it. |
| `REVIEW` | A style suggestion for the profile you chose. **Nothing happens until you accept it.** |
| `REFUSED` | PlainSpeak will not make this change. There is no override. |

Rejecting a suggestion keeps your wording and leaves the observation standing —
you disagreed about what to do, not about what was measured.

Not yet: manual editing (both panes are read-only), Accept All, structured DOCX
or PDF, custom profiles, installers. See [DESKTOP_MVP.md](DESKTOP_MVP.md).

## Command line

### `present`: the governed transformation

```bash
plainspeak present document.md --profile natural                  # JSON contract
plainspeak present document.md --profile natural --format summary # readable account
plainspeak present document.md --profile plain --format text -o presented.md
cat reply.md | plainspeak present --stdin --profile technical
```

`present` applies every `SAFE` change and nothing else. `REVIEW` suggestions are
reported and left unapplied — only a person, in the desktop application, can
accept one — and `REFUSED` changes are reported with the reason. The input file
is never written; `-o` refuses an existing file unless given `--overwrite`, and
refuses the input file always.

The default output is the versioned **`plainspeak.present.v1`** JSON contract:
input and output SHA-256, every engine identity, the applied changes, the pending
reviews, the refusals, the protected facts with their source offsets, and the
style observations. It contains no timestamps, paths or host details, so the
same input gives the same bytes anywhere. Exit status is 0 when presented, 1
when the input cannot be presented (the JSON carries an error `code`), and 2 for
invalid usage. `--format` also accepts `text`, `marked` and `summary`, which
are for people and carry no layout guarantee.

### Inspecting the engine

```bash
plainspeak style preview document.md --profile natural   # suggestions, read-only
plainspeak rules list                                    # the bundled ruleset
plainspeak rules explain PS.CLARITY.001                  # one rule, in full
plainspeak profiles list                                 # the five profiles
plainspeak profiles explain technical                    # one profile's margins
```

Readability measurement:

```bash
plainspeak analyze document.txt --output report.html
plainspeak score document.txt
```

### `simplify` and `web`

`plainspeak simplify` is a deprecated alias for `present --format marked`. The
web interface (`plainspeak web`) shows the same governed presentation under the
Natural profile. Both once used the inherited substitution engine, which had no
integrity firewall; neither can reach it any more, and a test enforces that no
interface can.

The readability *suggestions* in `analyze` reports and the web page still come
from the inherited glossary, which the characterisation seal pins byte for byte.
They are never applied, and some are poor — "leverages" is still offered
"borrowed money". Treat them as hints, not as PlainSpeak's transformations.

## Tests

```bash
pip install -e ".[desktop,dev]"
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

The suite runs on Windows, Linux and macOS in CI, with and without the desktop
extra. Architecture rules — which layer may import which, and that Qt stays in
the desktop — are enforced by tests, not by convention.

## Limitations

- English only.
- Word- and phrase-level rules. PlainSpeak does not restructure sentences, so it
  will not make every text read as though a person wrote it.
- The firewall protects the categories it names. A change that alters meaning
  without touching one of them is not detected.
- Readability formulas are proxies for comprehension, and no study has yet shown
  that PlainSpeak's changes help readers.
- Not validated for legal, medical, financial or safety-critical documents
  without qualified human review.

The full accounting is in [LIMITATIONS.md](LIMITATIONS.md) and
[V1_SCOPE.md](V1_SCOPE.md).

## Documentation

- [V1_SCOPE.md](V1_SCOPE.md) — what 1.0 guarantees, what it does not, and what counts as breaking
- [ROADMAP.md](ROADMAP.md) — accepted phases, V1 blockers, and what comes after
- [ARCHITECTURE.md](ARCHITECTURE.md) — the layers, and what each may depend on
- [DESKTOP_MVP.md](DESKTOP_MVP.md) — the desktop application: architecture, file safety, review semantics, build evidence
- [STYLE_CALIBRATION.md](STYLE_CALIBRATION.md) — where the style thresholds came from, and which are not yet supported by evidence
- [STYLE_PROFILES.md](STYLE_PROFILES.md) — the five profiles and their margins
- [STYLE_TRANSFORMATIONS.md](STYLE_TRANSFORMATIONS.md) — what a style fix may propose, and what it may never do
- [GLOSSARY_MIGRATION.md](GLOSSARY_MIGRATION.md) — how 706 inherited terms were reconciled
- [LIMITATIONS.md](LIMITATIONS.md) — known gaps
- [SECURITY.md](SECURITY.md) — threat model and privacy
- [ACCESSIBILITY.md](ACCESSIBILITY.md) — checklist and known gaps
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — data provenance and licences
- [UPSTREAM.md](UPSTREAM.md) — lineage, and why nothing syncs
- [CHANGELOG.md](CHANGELOG.md) — version history

Records of the original experiment, kept as historical evidence and not
updated: [MISSION.md](MISSION.md), [DECISIONS.md](DECISIONS.md),
[PROGRESS.md](PROGRESS.md), [FINAL_REPORT.md](FINAL_REPORT.md),
[Experiment Report.md](Experiment%20Report.md),
[QUALITY_PHASE_REPORT.md](QUALITY_PHASE_REPORT.md),
[VALIDATION_FINDINGS.md](VALIDATION_FINDINGS.md).

## Licence

MIT — see [LICENSE](LICENSE).

Repository: [github.com/hourwise/PlainSpeak-Next](https://github.com/hourwise/PlainSpeak-Next)
