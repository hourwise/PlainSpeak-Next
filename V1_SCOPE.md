# V1 scope

What PlainSpeak Next 1.0 will promise, what it will not, and which later changes
count as breaking. Written before V1 feature work began, so that the features
are built to a contract rather than the contract being written around whatever
the features turned out to do.

Items marked *(Stage 1)* are part of the V1 contract but were not yet
implemented when this document was first written; the V1 release candidate is
not ready until they are.

## Guaranteed in V1

### Determinism and reproducibility

- The same input bytes, under the same profile and the same engine identities,
  produce byte-identical output and identical hashes on Windows, Linux and
  macOS, on every supported Python version.
- Every result names the authorities that produced it: ruleset version and
  SHA-256, integrity policy version and SHA-256, morphology version and SHA-256,
  style policy version and SHA-256, profile pack version and SHA-256, and the
  selected profile's own hash.
- Output is never influenced by the clock, the locale, the environment, the
  network, randomness or a model.

### Offline operation

- No network access on any code path: no telemetry, update check, analytics,
  crash reporting, remote font, model or embedding. Asserted by tests that deny
  sockets.

### Supported inputs

- Transformation, review and saving: UTF-8 plain text (`.txt`) and Markdown
  (`.md`, `.markdown`), and text on standard input *(Stage 1: `present`)*.
- Markdown code, block quotes, tables, link and image destinations, autolinks
  and raw HTML are never rewritten.
- DOCX, PDF and HTML may be **analysed** through a plain-text fallback. They are
  **refused** for transformation, because the result would not preserve their
  structure.

### Profiles

- Five bundled profiles — Natural, Plain, Technical, Government, Academic — each
  versioned and hash-identified.
- Every operation names its profile explicitly. There is no hidden engine
  default.

### Classification of every change

Every change PlainSpeak considers is exactly one of:

| Class | Meaning |
|---|---|
| `SAFE` | A mechanical change from a `safe-fix` rule that passed the integrity firewall. Applied automatically. |
| `REVIEW` | A profile-triggered style suggestion. **Never** applied without an explicit human decision bound to the plan it came from. |
| `REFUSED` | A change PlainSpeak will not make: the firewall vetoed it, or applying it would damage the text. There is no override. |

- *(Stage 1)* SAFE changes are admitted only if applying them does not make a
  governed style diagnostic worse.

### Integrity protection

A change is refused if it would add, remove or alter any fact in these
categories, counted as a multiset (two identical dosages must stay two):
numbers, percentages, currency amounts with their currency, measurements with
their unit, dates, times, URLs, email addresses, file paths, version numbers,
CVE identifiers, UUIDs, long hashes, negation, modal verbs, and a bounded list
of comparators and qualifiers ("at least", "no later than", "before",
"unless", …).

- The firewall cannot be disabled by any rule, profile, flag or adapter.
- *(Stage 1)* A small, versioned table of equivalent forms (for example
  "prior to" and "before") is treated as the same fact. Each entry is
  deliberately chosen and adversarially tested.

### Review

- The desktop application never overwrites the file it opened, writes
  atomically, and saves the engine's output rather than a widget's contents.
- Accepting or rejecting a suggestion never re-plans the document.

### Short texts

- *(Stage 1)* Where a text is too short for a diagnostic's minimum sample, the
  result says so explicitly. Absence of a finding is never presented as
  evidence that the text is stylistically clean.

### Public contracts

- *(Stage 1)* `plainspeak present` and its versioned JSON result.
- The CLI commands `analyze`, `score`, `present`, `rules list`, `rules explain`,
  `profiles list`, `profiles explain`, `style preview` and `version`, and the
  `plainspeak-desktop` application.
- The Python facade exported from `plainspeak.pipeline`.

## Not guaranteed

- **Natural-sounding output.** PlainSpeak applies a bounded set of
  word- and phrase-level rules. It does not restructure sentences and will not
  make every input read as though a person wrote it.
- **Authorship detection.** No output is, or should be read as, a judgement
  about whether a person or a machine wrote the text.
- **Universal semantic equivalence.** The firewall protects the categories
  listed above. It does not understand meaning, and a change that alters
  meaning without touching a protected category is not detected.
- **Understanding of every rephrasing.** Two wordings of the same fact that are
  not in the equivalence table are treated as different facts, so some correct
  changes are refused.
- **Correctness of REVIEW suggestions.** A suggestion is a proposal that a
  person must judge. Its appearance is not a claim that it is right.
- **Format fidelity beyond plain text and Markdown.**
- **Improved comprehension.** Readability formulas are proxies. No study has yet
  shown that PlainSpeak's changes help readers understand text.
- **Fitness for legal, medical, financial or safety-critical use** without
  qualified human review.
- **Languages other than English.**

## Breaking-change boundary

After 1.0.0, each of the following requires a new major version, or an
explicitly versioned successor that leaves the old behaviour available:

| Area | Breaking |
|---|---|
| Output semantics | The same input, profile and engine identities producing different output text |
| Integrity semantics | Removing a protected category or equivalence-class member in a way that admits a change 1.0 would refuse |
| SAFE / REVIEW / REFUSED | Moving a change from REVIEW or REFUSED to SAFE, or changing what a class means |
| Refusal semantics | A refused change becoming overridable |
| Profiles | Removing a profile or changing a profile id |
| Rule identity | Changing how rule, ruleset, policy or profile hashes are computed |
| Source mapping | Changing the meaning of reported offsets |
| JSON contract | Removing or renaming a field, or changing a field's type or meaning, within one schema id |
| CLI | Removing a command or option, or changing exit-code meaning |

**Not breaking**, provided the affected identity is re-versioned and the change
is recorded in the CHANGELOG: adding a rule; making the firewall stricter;
adding a JSON field; adding a profile; recalibrating a profile's thresholds;
fixing a defect where the prior behaviour contradicted this document.

The distinction that matters: a stricter PlainSpeak is a new version; a looser
PlainSpeak is a new contract.
