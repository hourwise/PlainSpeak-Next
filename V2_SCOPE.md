# V2 scope

V2 adds three things to PlainSpeak 1.0 — **Verify**, a **GitHub Action** and an
**MCP server** — plus the `diagnose` operation the server exposes. It changes
nothing V1 promised. [V1_SCOPE.md](V1_SCOPE.md) still describes everything it
described, and every guarantee in it still holds.

This is the scope of the V2 release candidate. It has not been published.

## Guaranteed

### Verify

- **Three results, never collapsed.** `ACCEPTED`, `REFUSED` or `INCONCLUSIVE`.
  Unknown is never reported as safe: a difference the verification policy does
  not account for makes the result `INCONCLUSIVE` at best.
- **`REFUSED` whenever a protected item changed**: any fact under the integrity
  policy (whole text, counts included), any term of art in the protected-term
  register or the ruleset's declared protected phrases, and any change to a
  region PlainSpeak never rewrites (code, quotations, tables, link destinations,
  raw markup).
- **`ACCEPTED` only when everything is accounted for** by verification policy
  `2026.2`: identical token streams, fact equivalences under the integrity
  policy, PlainSpeak's SAFE rules applied to either text, capitalisation of a word
  that became or stopped being first in its sentence, a paragraph break between
  sentences, and a comparator with its value moving between the start and the
  end of a single-clause sentence whose other words are unchanged.
- **PlainSpeak accepts its own work.** Every `present` output verifies as
  `ACCEPTED` against its input; a test runs this over the whole acceptance
  corpus.
- **Determinism.** The same inputs under the same engine and verification policy
  produce byte-identical JSON and an identical receipt on every platform. No
  timestamps, paths or host details.
- **Offline.** Verification makes no network connection.
- **Exit statuses** for `plainspeak verify`: 0 `ACCEPTED`, 1 `REFUSED`, 2 invalid
  usage, 3 `INCONCLUSIVE`, 4 the inputs could not be verified, 5 internal error.

### The GitHub Action

- Runs the same verifier, installed from the action's own source at the ref the
  workflow names, in an environment of its own; the job's Python is untouched.
- Fails on `REFUSED` or `INCONCLUSIVE` by default; `fail-on: refused` or `never`
  relax it.
- Inputs reach it only through environment variables; paths are confined to the
  workspace; document text written to the log or the job summary is escaped.
- Needs no secrets and no permission beyond reading the repository.

### The MCP server

- Exposes `present`, `verify` and `diagnose` and nothing else, over stdio.
- Returns exactly the bytes the CLI's `--format json` returns for the same input.
- Reads no files, runs no commands, changes no rule, policy or profile, and makes
  no network connection. Imports nothing outside the standard library.
- Refuses malformed messages, unknown methods and tools, and arguments outside a
  tool's schema, without ending the session.

### `diagnose`

- Reports what `present` would report, from the same review bundle, and applies
  nothing. Its `safe`, `review`, `refused`, `diagnostics` and `style_coverage`
  equal `present`'s `applied`, `review`, `refused`, `diagnostics` and
  `style_coverage` for the same input and profile.

## Not guaranteed

- **That two texts mean the same thing.** Verify checks the properties the
  integrity model represents. `ACCEPTED` means every protected item survived and
  every difference is accounted for; it does not mean nothing that matters
  changed outside what the model represents. See [VERIFY.md](VERIFY.md).
- **That an equivalent rewording is accepted.** The model is strict: "at most"
  for "up to", "shall" for "must", a reformatted date — each is refused.
- **That what a protected item applies to is unchanged**, beyond the order of
  protected items and the permitted move above. "You must pay £5" and "You must
  receive £5" differ in a word the model does not protect; the result is
  `INCONCLUSIVE`, not `REFUSED`.
- **Signed receipts.** A receipt is evidence anyone can recompute, not a
  signature.
- **Anything hosted.** There is no remote MCP transport and no hosted service.

## Public contracts added

- `plainspeak verify` and **`plainspeak.verify.v1`**: `schema`, `status`,
  `result`, `plainspeak_version`, `verify_policy` (version, sha256), `engine`
  (ruleset, integrity and morphology versions and hashes), `input_format`,
  `before` and `after` (sha256, characters), `identical`, `counts`,
  `protected`, `equivalences`, `refusals`, `unresolved`, `notes`, `receipt`.
  Error codes `empty_input`, `unsupported_input`, `unreadable_input`,
  `format_mismatch`. Documented field by field in [VERIFY.md](VERIFY.md).
- **`plainspeak.verify.receipt.v1`**: `{"payload", "sha256"}`, the SHA-256 of the
  payload's canonical JSON.
- `plainspeak diagnose` and **`plainspeak.diagnose.v1`**: `schema`, `status`,
  `plainspeak_version`, `profile`, `input`, `engine`, `counts`, `safe`, `review`,
  `refused`, `protected`, `diagnostics`, `style_coverage`, `readability`. Exit
  status 0 diagnosed, 1 not diagnosable, 2 invalid usage.
- `plainspeak serve` and the MCP tools `present`, `verify` and `diagnose`, their
  input schemas and their results. See [MCP.md](MCP.md).
- The GitHub Action (`action.yml`): inputs `before`, `after`, `fail-on`,
  `input-format`, `upload-receipt`, `artifact-name`, `python-version`; outputs
  `result`, `receipt-sha256`, `before-sha256`, `after-sha256`, `refusals`,
  `unresolved`, `result-path`, `receipt-path`.
- The Python facade gains `verify`, `verify_text`, `verify_files`, `VerifyResult`,
  `VerifyError`, `diagnose`, `diagnose_text`, `DiagnoseResult` and the schema
  constants.

## Compatibility with V1

No V1 contract changed shape, and two field defects in 1.0.0's behaviour were
corrected deliberately ([V2_FIELD_FINDINGS.md](V2_FIELD_FINDINGS.md)):

- **Ruleset 2026.7** reclassifies 42 SAFE rules as diagnostics: 28 after field
  testing (FIELD-001, an automatic rewrite that broke sentences, and the audit
  that followed), 14 after the independent review of the Verify study, which
  held each remaining SAFE rule to every context its matcher can reach. 97 of
  220 rules remain automatic. Of 145 `present` outputs checked — 29 documents
  under five profiles — 70 are byte-identical to 1.0.0 apart from the ruleset
  identity, and 75 differ only in that a reclassified rule is no longer
  applied; nothing is applied that was not before, and each textual difference
  is a reverted substitution. The certification sample now keeps "In order to"
  (`6107653a…`, from `af79da49…`).
- **`analyze` reports** qualify a sample shorter than 100 words or 3 sentences
  instead of presenting a verdict (FIELD-003). The JSON report gains a `sample`
  object; every existing field keeps its value.
- The `plainspeak.present.v1` schema, every V1 CLI command, option and exit
  status, and the integrity policy (2026.2), morphology, style policy and
  profile pack are unchanged. V2 adds commands; it removes and alters none.
- No runtime dependency was added. `import plainspeak` loads neither the MCP
  server nor anything new outside the standard library.

## Breaking-change boundary for V2's contracts

The V1 boundary applies to the new contracts as well. In addition:

| Area | Breaking |
|---|---|
| Verify results | Accepting anything verification policy `2026.2` does not account for without a new policy version; reporting `ACCEPTED` for a transformation that loses, adds or changes a protected item |
| Verify exit statuses | Changing the meaning of any exit status |
| Receipts | Changing how a receipt's payload or hash is computed within `plainspeak.verify.receipt.v1` |
| The Action | Removing an input or output, or making the default policy less strict |
| MCP | Removing a tool, or returning anything other than the CLI's contract for it |

## Version

V2 is additive, every V1 contract keeps its shape, and the two behaviour
changes are corrections of defects found in 1.0.0 — output that was wrong, not
output anyone could have relied on — so the recommended next version is
**1.1.0**, not 2.0.0. See [VERIFY_STUDY.md](VERIFY_STUDY.md) for the
release-candidate evidence.
