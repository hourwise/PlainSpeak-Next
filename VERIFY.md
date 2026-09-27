# `plainspeak verify`

`present` governs PlainSpeak's own edits. `verify` judges a transformation that
has **already happened** — made by a person, a language model, an agent, other
software or PlainSpeak itself — given only the text before and the text after.

```bash
plainspeak verify original.md revised.md                    # readable account
plainspeak verify original.md revised.md --format json      # plainspeak.verify.v1
plainspeak verify original.md revised.md --receipt r.json   # also write the receipt
```

## What it guarantees — and what it does not

Verify determines **whether the transformation preserves the properties
represented by PlainSpeak's integrity model**, and whether every difference
between the two texts is one that model can account for.

It does **not** establish that the two texts mean the same thing. Nothing
deterministic can. "The payment was approved" and "the payment was rejected"
contain no number, date, negation or modal for the model to protect; Verify
will not call that change safe, but it cannot call it wrong either, so it says
it cannot vouch for it.

## The three results

| Result | Meaning | Exit |
|---|---|---|
| `ACCEPTED` | Every protected item survived, in order, and every difference is accounted for | 0 |
| `REFUSED` | A protected item was lost, added or changed, or a region PlainSpeak never rewrites changed | 1 |
| `INCONCLUSIVE` | Nothing protected was lost, but something changed that the model cannot vouch for | 3 |

Unknown is never collapsed into safe. A rewrite whose facts all survived but
whose wording changed is `INCONCLUSIVE`, because "the numbers survived" is a
weaker claim than `ACCEPTED` makes.

Other exit statuses: **2** invalid usage; **4** the inputs could not be verified
(unreadable, unsupported format, empty before text — with `--format json`,
standard output carries the error code); **5** internal error. Only `ACCEPTED`
exits 0, so a CI step fails on anything else unless told otherwise.

### Protected — a change is `REFUSED`

- **Facts under the integrity policy** (V1's firewall, over the whole of both
  texts): numbers, percentages, currency amounts, measurements and units,
  dates, times, URLs, email addresses, paths, versions, CVE and other
  identifiers, hashes, negation, modals (`must`, `should`, `may`, …) and
  comparators (`before`, `within`, `at least`, `only`, …). Counts matter: a
  value that appeared twice must still appear twice.
- **Terms of art**: the protected-term register (`indemnify`, `consideration`,
  `contraindicated`, …) and the ruleset's declared protected phrases
  (`informed consent`, `additional insured`, `force majeure`, …).
- **Regions PlainSpeak never rewrites**: code blocks and code spans, block
  quotations, tables, link destinations and raw markup. Code must be identical
  apart from line endings; a quotation or table may be re-laid out but not
  reworded.

### Accounted for — allowed in `ACCEPTED`

- Whitespace, line endings, line wrapping and inline markup (emphasis).
- A spelling the integrity policy treats as the same fact: `£2,500` and `£2500`,
  `prior to` and `before`.
- Any of PlainSpeak's reviewed **SAFE** rules, applied to either text, in either
  direction: `utilize` ↔ `use`, `in order to` ↔ `to`. Both texts are normalised
  with the same rules before they are compared.
- Capitalisation of a sentence's first word.
- A paragraph break added or removed between two sentences.
- A comparator and the value it governs — `before 5pm`, `within 5 days` —
  moving within its own sentence: *"You must submit the form before 5pm"* and
  *"Before 5pm, you must submit the form"*. A comparator directly after a
  negation (`not before 5pm`) never moves.

### Not accounted for — `INCONCLUSIVE`

- Any other change of wording, anywhere: a changed verb, an added or removed
  sentence, a rephrased clause — even when every protected item survived.
- Protected items that appear in a different order: *"Pay £5 before Monday and
  £10 after Friday"* against *"Pay £10 before Monday and £5 after Friday"* keeps
  every amount and comparator, and is not accepted.
- A protected item that moved to a different sentence.
- Capitalisation changed mid-sentence (`polish` → `Polish`).
- Structure the parser could not locate exactly, or a text PlainSpeak's own
  rules could not be applied to.

### Known limits of the model

- It does not represent what a protected item **applies to**. "You must pay £5"
  and "You must receive £5" differ in a word the model does not protect, so the
  change is `INCONCLUSIVE` — never `ACCEPTED` — but the model cannot say it is
  wrong.
- It does not represent the **scope** of a negation beyond its position among
  the other protected items.
- Units are compared exactly (`mL` and `ml` differ), dates by their written form
  (`2026-08-29` and `29 August 2026` differ). Being too strict costs a
  `REFUSED` that a person can overrule; being too lax would cost the meaning.
- English only, plain text and Markdown only.
- Alignment is quadratic in the worst case; documents of tens of thousands of
  words are slow.

## In GitHub Actions

```yaml
permissions:
  contents: read

steps:
  - uses: actions/checkout@v5
  - uses: hourwise/PlainSpeak-Next@<tag or commit SHA>
    with:
      before: docs/original.md
      after: docs/revised.md
      # fail-on: inconclusive   # default: fail on REFUSED or INCONCLUSIVE
      # fail-on: refused        # fail on REFUSED only
      # fail-on: never          # report, never fail
```

| Input | Default | |
|---|---|---|
| `before`, `after` | — | paths inside the workspace; anything resolving outside it is refused |
| `fail-on` | `inconclusive` | `inconclusive`, `refused` or `never` |
| `input-format` | from `before`'s extension | `markdown` or `text` |
| `upload-receipt` | `true` | upload `result.json` and `receipt.json` as an artifact |
| `artifact-name` | `plainspeak-verify` | make it unique if the action runs twice in one job |
| `python-version` | `3.12` | the Python PlainSpeak runs on, in its own environment |

Outputs: `result`, `receipt-sha256`, `before-sha256`, `after-sha256`,
`refusals`, `unresolved`, `result-path`, `receipt-path`. Refusals are annotated
as errors on the lines they concern; unresolved differences are errors when
they fail the step and warnings when they do not. The job summary shows the
result, the policy, every finding and the receipt.

**Why `inconclusive` fails by default.** A change the model cannot vouch for is
not known to be safe, and a gate that passed it would be claiming more than
verification established. A repository that only wants its facts guarded —
numbers, dates, obligations, negation — can choose `fail-on: refused`.

**How it is packaged.** The action installs PlainSpeak from its own source, at
exactly the ref the workflow names, into a virtual environment of its own. The
verifier that runs is the one that ref contains — pin a tag or a commit SHA —
and nothing is added to the job's Python. Installing needs the network to fetch
PlainSpeak's three dependencies from PyPI; verification itself is offline and
deterministic. The action needs no secrets and no permission beyond reading the
repository.

**Pull-request input is treated as hostile.** Inputs reach the verifier through
environment variables and are never interpolated into a shell script; paths are
confined to the workspace, symbolic links out of it included; every snippet of
document text written back to the log or the job summary is escaped, so it
cannot become a workflow command, a link, an image or a table cell.

## The `plainspeak.verify.v1` contract

Canonical JSON — sorted keys, no insignificant whitespace, a final newline, no
timestamps, paths or host details — so the same inputs under the same engine
give the same bytes anywhere. Within one schema id a field is never removed,
renamed or given a different type or meaning.

| Field | |
|---|---|
| `schema` | `"plainspeak.verify.v1"` |
| `status` | `"ok"` (or `"error"` with `error.code` and `error.message`) |
| `result` | `ACCEPTED`, `REFUSED` or `INCONCLUSIVE` |
| `plainspeak_version`, `verify_policy`, `engine` | every identity the decision depended on: verification policy, integrity policy, ruleset and morphology, each with version and SHA-256 |
| `input_format` | `markdown` or `text` |
| `before`, `after` | `sha256` and `characters`. For files, the SHA-256 of the file's bytes |
| `identical` | whether the texts are byte-identical |
| `protected` | the integrity policy identity, whether the facts were preserved, and every protected item in the before text with its line |
| `equivalences` | every difference accounted for: `code` (`fact_equivalence`, `safe_rule`, `permitted_move`, `formatting`), `kind`, `before`, `after`, `detail`, lines |
| `refusals` | every protected change: `code` (`protected_fact_changed`, `protected_term_changed`, `protected_region_changed`), `kind`, `before`, `after`, `detail`, `before_lines`, `after_lines` |
| `unresolved` | every difference not accounted for: `code` (`unexplained_change`, `protected_item_moved`, `protected_item_unmatched`, `unlocatable_structure`, `normalisation_unavailable`), `detail`, `before`, `after`, lines |
| `counts`, `notes` | totals, and plain notes such as "the two texts are identical" |
| `receipt` | see below |

Error codes: `empty_input`, `unsupported_input`, `unreadable_input`,
`format_mismatch`.

## The receipt

`receipt` is `{"payload": …, "sha256": …}`. The payload names the receipt schema
(`plainspeak.verify.receipt.v1`), the PlainSpeak version, the verification
policy, the engine identities, the input format, both inputs' SHA-256, the
result, and the SHA-256 of the findings. `sha256` is the SHA-256 of the
payload's canonical JSON. The same inputs under the same engine and policy
produce the same receipt, byte for byte; any change to the inputs, the policy
or the result produces a different one.

A receipt is **evidence, not a signature**. Anyone can recompute it by running
the same version of PlainSpeak on the same two files; nobody can prove from the
receipt alone who ran it.

## The verification policy

Version `2026.1`. What counts as accounted for is data
(`plainspeak.pipeline.verify.verify_policy_document()`), versioned and hashed
like the integrity policy, and the hash is in every result and receipt. Adding
anything to what is accounted for is a change of policy version.

## How it works

1. Both texts are parsed into documents (Markdown or plain text) and projected
   into analysis text, the representation `present` reads.
2. The V1 firewall compares the protected facts of the whole of both texts, and
   the regions PlainSpeak never rewrites are compared one by one. Any
   difference is a refusal.
3. PlainSpeak's SAFE rules are applied to both projections, so a difference
   that is one of those rules disappears.
4. Each text becomes a sequence of tokens — words, punctuation, paragraph
   breaks, and every protected fact and term as one atomic token — and the two
   sequences are aligned deterministically.
5. Every difference the alignment leaves is either accounted for by the
   verification policy or reported as unresolved.

Verify is part of the pipeline, not of any interface: the CLI, the GitHub
Action and the MCP server all call `plainspeak.pipeline.verify`, and an
architecture test forbids any of them from containing a verifier of its own.
