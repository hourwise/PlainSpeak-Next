# PlainSpeak field-test harness

A small harness that runs a real agent (via [opencode](https://opencode.ai))
against a fixed set of rewriting cases, twice: once on its own and once under
a PlainSpeak protocol. It measures whether the agent *follows the protocol*,
not whether the rewrite is stylistically good.

## What it checks

`cases.json` holds six short institutional sentences, one per defect class
(positive control, modal comparator, removable framing, negation, numbers and
money, scope). For every case, `runner.py` runs two arms:

- **baseline** — the model rewrites the sentence with no tools. Protocol
  check: it must not call any tool, and must end with a
  `FINAL_REWRITE: <text>` line.
- **governed** — the model must rewrite, then verify its rewrite against the
  original using only the PlainSpeak MCP `verify` tool: stop on `ACCEPTED` or
  `INCONCLUSIVE`, revise exactly once on `REFUSED`, and stop after a second
  verification regardless. The final line must carry the last text it
  actually verified.

After each run the harness re-verifies the reported rewrite itself (an
"observer" `plainspeak verify --format json` call), then
`evaluate_protocol` emits `PASS`/`FAIL` with machine-readable reasons, e.g.
`governed_did_not_call_verify`, `model_continued_after_terminal_result`,
`final_rewrite_not_last_verified_text`,
`observer_result_disagrees_with_last_tool_result`. Note the result is about
protocol compliance: an `INCONCLUSIVE` observer decision is not a failure.

## How results are recorded

Each invocation writes `results/<run-id>/` (git-ignored): one
`<case>-<arm>.json` per experiment and a `manifest.json` summary. Every record
stores the prompt, the original, the assistant text and the final rewrite with
their SHA-256 hashes, the full opencode event stream, tool calls, token usage,
the observer verification and the protocol verdict — enough to re-audit a run
offline.

## Running it later against a local model

1. Install opencode and PlainSpeak so both are on `PATH`
   (`opencode --version`, `plainspeak --version`; PlainSpeak ships the MCP
   server as `plainspeak serve`).
2. Start an OpenAI-compatible server for the local model (Gemma 4) listening
   on `http://127.0.0.1:8080/v1`.
3. Copy the example config and adjust it if the server differs:

   ```
   cp field/opencode.local.example.json field/opencode.local.json
   ```

   It defines provider `localsrv` (base URL `http://127.0.0.1:8080/v1`, a
   dummy key, model id `gemma-4`) plus the same `plainspeak` MCP server block
   as the default `field/opencode.json`.
4. From the repo root, run:

   ```
   python3 field/runner.py --config field/opencode.local.json \
       --model localsrv/gemma-4
   ```

   Optional: `--case PSF-003` to run one case, `--arm governed` for one arm.
   Without `--config` the harness uses `field/opencode.json` and whatever
   model opencode picks by default — the original behaviour.

## What the 1.0.0 run found

The previous field test (opencode with a hosted model, against published
PlainSpeak 1.0.0) produced three findings; see
[V2_FIELD_FINDINGS.md](../V2_FIELD_FINDINGS.md). All three were fixed in
1.1.0; this harness is prepared so the same protocol can be re-run against
1.1.0 with a local model.
