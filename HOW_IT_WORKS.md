# How PlainSpeak works, and what it guarantees

PlainSpeak takes a piece of writing — a report, a letter, a reply an AI agent
has drafted — and presents it more plainly. It does that with a fixed,
published set of rules, and it refuses any change that would alter the facts
the writing states.

This page explains what that means in practice. For the formal list of what
version 1 promises, see [V1_SCOPE.md](V1_SCOPE.md).

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

## What PlainSpeak changes

**SAFE changes** are word- and phrase-level substitutions from a versioned
rulebook of 220 rules — "in order to" becomes "to", "utilise" becomes "use",
"prior to" becomes "before". Each rule has been written down with examples of
where it applies and where it must not, and each is tested. A SAFE change is
applied automatically only if:

1. it passes the **integrity check** on its own, in its sentence, and together
   with every other change in the document; and
2. together with the other SAFE changes, it does not make the document's style
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
| ruleset | 2026.4 |
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

Profiles decide which style habits are reported and which style suggestions
are offered. They never affect SAFE changes, which are the same under every
profile, and they never affect what the integrity check protects.

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

[LIMITATIONS.md](LIMITATIONS.md) has the full list.
