# How PlainSpeak works, and what it guarantees

PlainSpeak takes a piece of writing — a report, a letter, a reply an AI agent
has drafted — and presents it more plainly. It does that with a fixed,
published set of rules, and it refuses any change that would alter the facts
the writing states.

This page explains what that means in practice. For the formal list of what
version 1 promises, see [V1_SCOPE.md](V1_SCOPE.md); for what the Verify, GitHub
Action and MCP additions promise, [V2_SCOPE.md](V2_SCOPE.md).

## The short version

- **The same input always gives the same output.** No AI model, no randomness,
  no internet connection. Run it twice, on any computer, and you get identical
  bytes.
- **Facts are protected.** Numbers, dates, amounts of money, units, reference
  numbers, web and email addresses, "not", "must", "may", "at least", "before"
  and similar words cannot be changed, added or removed by any rule. There is
  no setting that turns this off.
- **Every change is labelled.** `SAFE` changes are made automatically. `REVIEW`
  suggestions are only ever made by a person. `REFUSED` changes are shown to you
  with the reason, and cannot be forced through.
- **It tells you what it could not judge.** If a text is too short for a style
  check to mean anything, it says so, rather than implying the text is fine.
- **It can check other people's rewrites.** `plainspeak verify` compares a text
  with a rewrite of it, whoever made it, and says whether every protected fact
  survived — without claiming to know whether the two mean the same thing.

## What PlainSpeak changes

**SAFE changes** are word- and phrase-level substitutions from a versioned
rulebook of 220 rules, 23 of which may change text automatically — "utilise" becomes "use", "due to the fact that" becomes "because",
"prior to" becomes "before". Each rule has been written down with examples of
where it applies and where it must not, and each is tested. Each of the 23
has been qualified against ordinary, adversarial and specialist sentences;
[SAFE_RULE_QUALIFICATION.md](SAFE_RULE_QUALIFICATION.md) records every one.
Most of the other rules are diagnostics — terms that cannot be substituted
safely everywhere. They are never applied, and `present` and `diagnose` do
not currently list them. A SAFE change is applied automatically only if:

1. it passes the **integrity check** on its own, in its sentence, and together
   with every other change in the document; and
2. the words around it still read correctly — "an advantageous position"
   becomes "a helpful position", with the article corrected, and a replacement
   that cannot follow "a" or "an" is refused where one precedes it; and
3. together with the other SAFE changes, it does not make the document's style
   **worse** — for example, by turning "Furthermore", "Moreover" and
   "Additionally" all into "Also" until half the sentences begin with the same
   word. If a group of changes would, that group is refused and the reason is
   shown.

**REVIEW suggestions** come from six style rules that only act when the
document shows a particular habit — for instance, starting paragraph after
paragraph with "Nevertheless". PlainSpeak suggests the smallest number of
changes that would fix the habit, leaves the earliest uses alone, and does
nothing until a person accepts each one.

## What PlainSpeak refuses to change

PlainSpeak extracts every protected fact from the text before and after a
change and compares them. If anything was added, removed or altered, the change
is refused. The protected categories are:

| | examples |
|---|---|
| numbers, percentages | `12`, `3.5`, `40%`, `40 per cent` |
| money | `£42.50`, `USD 100` — the currency is part of the amount |
| measurements | `5 mg`, `250 ml`, `2 kg` — the unit is part of the amount |
| dates and times | `30 June 2027`, `2027-06-30`, `3pm` |
| identifiers | web addresses, email addresses, file paths, version numbers, CVE numbers, long hashes |
| negation | not, no, never, without, cannot, don't … |
| obligation and permission | must, shall, may, can, should, will … |
| comparisons and limits | at least, no later than, before, after, unless, only, within … |

Counts matter: if a document states the same dose twice, both must survive.

The check does not understand meaning. It protects these categories, and only
these. A change that alters meaning without touching one of them would not be
caught — which is one reason the rulebook is deliberately conservative and
refuses rather than guesses.

A very small, reviewed table lets two spellings count as the same fact. In
version 1 it has one entry: "prior to" and "before". Admitting a spelling also
protects it, so "prior to" can no longer be deleted or turned into "after".

## Determinism

Everything PlainSpeak produces comes from its input and five published,
versioned rule sets:

| | version |
|---|---|
| ruleset | 2026.8 |
| integrity policy | 2026.2 |
| morphology | 2026.1 |
| style policy | 2026.2 |
| profile pack | 2026.1 |

Each has a SHA-256 fingerprint, and every result names all five. If you and a
colleague get different results, the fingerprints will tell you why; if they
match, the results will.

## Profiles

A specification that repeats a defined term forty times is doing its job; an
essay that does the same has a tic. So style is judged against a **profile**:
Natural, Plain, Technical, Government or Academic. You always choose one —
PlainSpeak never picks for you.

| choosing a profile changes | choosing a profile does not change |
|---|---|
| which style observations are reported, and at what strength | the SAFE changes — identical under every profile |
| how much text a style check needs before it will judge | what the integrity check protects |
| the target ranges shown for sentence length and vocabulary | the REFUSED changes |

In version 1 the six style suggestions act on repeated transitions, where all
five profiles draw the same line, so the suggestions you are offered are the
same under every profile. Profiles are five standards for judging the same
text, not five ways of rewriting it. `plainspeak profiles explain technical`
shows exactly where one profile draws its lines and why.

## `plainspeak present`

The command-line tool for scripts, pipelines and AI agents:

```bash
plainspeak present reply.md --profile natural
```

It applies every SAFE change and nothing else, and prints a JSON record
(`plainspeak.present.v1`) containing the presented text, fingerprints of the
input and output, every change made, every suggestion waiting for review,
every refusal with its reason, every protected fact with its position, the
style observations, and which style checks had enough text. The same input
always produces the same bytes. `--format summary` prints a readable account
instead; `--format text` prints only the presented document.

It never writes to the file it reads.

## `plainspeak verify`

For a rewrite PlainSpeak did not make — by a colleague, an AI assistant,
another tool:

```bash
plainspeak verify original.md rewritten.md
```

It answers one of three things:

- **ACCEPTED** — every protected fact survived, in order, and every other
  difference is one PlainSpeak can account for: layout, a spelling the rules
  treat as the same fact, one of its own SAFE changes, or a time phrase moved to
  the other end of a simple sentence.
- **REFUSED** — a number, date, amount, unit, "not", "must", "before" or other
  protected word was lost, added or changed; or a term of art was replaced; or
  code, a quotation, a table or a link address changed.
- **INCONCLUSIVE** — nothing protected was lost, but something changed that
  PlainSpeak cannot vouch for: a reworded sentence, facts in a different order.

What it does **not** do is decide whether the two texts mean the same thing. "The
payment was approved" and "the payment was rejected" contain no fact for
PlainSpeak to protect, so it cannot call that change wrong; it will not call it
safe either. The result carries a receipt — a fingerprint of the two texts, the
result and every rule it was decided under — that anyone can recompute. The same
check runs in CI as a GitHub Action. See [VERIFY.md](VERIFY.md).

## For AI agents: `plainspeak serve`

`plainspeak serve` makes `present`, `verify` and `diagnose` available to an AI
agent as tools, over the Model Context Protocol. The agent gets exactly the
answer the command line gives. The server runs on your computer, talks only
through its standard input and output, reads no files and runs nothing; the
agent hands it text and gets a result back. See [MCP.md](MCP.md).

## The desktop application

`plainspeak-desktop` shows the original on the left and the revised version on
the right, with every change listed underneath. You accept or reject each
REVIEW suggestion individually; there is no "accept all". REFUSED changes have
no button at all. Saving is **Save As** only, to a different file: PlainSpeak
never overwrites the document you opened.

## Offline

PlainSpeak makes no network connections. There is no telemetry, no update
check, no account and no model download. Your text never leaves your computer.
This is enforced by tests that run the engine with networking disabled.

## Limitations

- **English only.**
- **It will not make every text read naturally.** It substitutes words and
  phrases; it does not rewrite sentences.
- **Short texts get little style feedback.** Style checks need several
  sentences or paragraphs to mean anything, and most short replies are below
  that — PlainSpeak says so rather than guessing.
- **Plain text and Markdown only** for changes and saving. Word, PDF and HTML
  files are not edited.
- **Not a substitute for expert review** of legal, medical, financial or
  safety-critical text.
- **It is not an AI detector.** Nothing PlainSpeak reports is a judgement about
  whether a person or a machine wrote the text.
- **Verify is not a meaning checker.** It checks the facts its rules protect,
  and says INCONCLUSIVE about everything else it cannot account for. It is
  strict: an equivalent rewording such as "at most 5" for "up to 5" is refused.

[LIMITATIONS.md](LIMITATIONS.md) has the full list.
