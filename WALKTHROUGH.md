# Walkthrough: your first document

This takes about ten minutes and assumes nothing except a computer with
Python 3.10 or later. You will install PlainSpeak, give it a short piece of
machine-written text, read what it did, review its suggestions in the desktop
application, and save the result.

For what PlainSpeak is and what it promises, read
[HOW_IT_WORKS.md](HOW_IT_WORKS.md) first or afterwards.

## 1. Install

Install PlainSpeak Next from PyPI, where it is published as `plainspeak-next`:

```bash
python -m pip install "plainspeak-next[desktop]"
```

Leave out `[desktop]` if you only want the command-line tool; it then needs no
graphical toolkit at all. Once installed, the command is `plainspeak` and the
Python package is `import plainspeak` — only the PyPI name has the `-next`.

> **Do not run `pip install plainspeak`.** The name `plainspeak` on PyPI
> belongs to an unrelated project — a tool that turns English into terminal
> commands — which also installs a Python package called `plainspeak`. The two
> cannot share a Python environment.

Check it worked:

```bash
plainspeak version
```

Prefer not to install Python? A portable desktop build for Windows or Linux is
attached to each release: unzip it and run `PlainSpeak.dist/desktop_main.exe`
(Windows) or `PlainSpeak.dist/desktop_main.bin` (Linux). Skip to step 5.

## 2. Some text to work on

Save the following as `reply.md`. It is the kind of reply an AI assistant might
draft — accurate, but stiff, and leaning hard on one word.

```markdown
# Your account migration

In order to complete the migration, you must utilize the new portal prior to 30 June 2027. It should be noted that the old portal will not accept payments after that date.

Nevertheless, your existing direct debit of £42.50 per month will continue without any action from you. Your reference number, ACC-20931, does not change.

Nevertheless, some features will move. Statements will now be issued within 5 working days of the end of each month, rather than 10.

Nevertheless, you can still download older statements. They remain available for at least 7 years.

Nevertheless, you will need to set a new password. It must contain at least 12 characters.

Nevertheless, two-factor authentication is optional for now. From 1 January 2028 it will be required for every account.

Nevertheless, if you have questions, our support team can help. Contact them at support@example.com or on 0800 123 4567.
```

(The same text ships in the repository as `examples/agent_reply.md`.)

## 3. Present it

```bash
plainspeak present reply.md --profile natural --format summary
```

A profile is always required — PlainSpeak never chooses one for you. You will
see:

```text
PlainSpeak present — profile natural, ruleset 2026.7 (dc4146941049)
input 2d3888ed6c930f0b  output e6b9106a71f199f1

Applied automatically (SAFE): 2
  'utilize' -> 'use'  [PS.LEXICAL.001]
  'prior to' -> 'before'  [PS.CLARITY.009]
Awaiting a person (REVIEW, not applied): 2
  'Nevertheless,' -> 'Even so,'  [PS.STYLEFIX.001]
  'Nevertheless,' -> 'Even so,'  [PS.STYLEFIX.001]
Refused (REFUSED, never applied): 1
  'It should be noted that t': the change would alter protected information: integrity violation — modal: should -> nothing
Style observations under natural: 5
  [strong] 6 of 7 paragraphs begin with “nevertheless”.
  [strong] “nevertheless” accounts for 6 of 6 transitions.
  [strong] 6 transitions across 15 sentences (0.40 per sentence).
  [notice] 6 of 15 sentences begin with “nevertheless”.
  [notice] Sentence lengths vary little: mean 9.3 words, variation 0.43.
Not enough text to judge 2 of 13 style diagnostics (INSUFFICIENT_SAMPLE) — their silence is not a clean result:
  PARAGRAPH_UNIFORMITY: Needs 8 paragraphs; this document has 7. Too short to judge, not judged clean.
  VOCABULARY_OVERUSE: Needs 200 words; this document has 139. Too short to judge, not judged clean.
```

## 4. Read what happened

**Two SAFE changes were made.** Each is a rule from the published rulebook;
`plainspeak rules explain PS.CLARITY.009` shows any rule in full, with its
examples. Every one passed the integrity check. "In order to" was left alone:
it usually means "to", but "keep your papers in order to avoid delays" does
not, and a rule that cannot tell the two apart is not allowed to rewrite
either.

**Two REVIEW suggestions were not made.** The text starts six paragraphs with
"Nevertheless". PlainSpeak worked out that changing the last two is the fewest
changes that fixes the habit, and it keeps the first four. Nothing happens to
them until a person accepts them — step 5.

**One change was REFUSED.** Deleting "It should be noted that" would also
delete "should", and "should" is a protected word: PlainSpeak cannot tell an
idiom from an obligation, so it refuses rather than guesses.

**Nothing factual moved.** 30 June 2027, £42.50, ACC-20931, "within 5 working
days", "at least 7 years", "at least 12 characters", 1 January 2028, the email
address and the phone number are all exactly where they were. "Prior to"
became "before" because the two are recorded as the same fact; "prior to"
becoming "after" would have been refused.

**Two style checks said they could not judge.** Seven paragraphs is too few to
say anything about paragraph-length rhythm, and 139 words too few for
vocabulary habits. PlainSpeak says so instead of staying silent.

To see only the presented text:

```bash
plainspeak present reply.md --profile natural --format text
```

For programs and AI agents, leave out `--format`: the default is a JSON record,
`plainspeak.present.v1`. An excerpt:

```json
{
  "schema": "plainspeak.present.v1",
  "status": "ok",
  "profile": { "id": "natural", "version": 1, "sha256": "e6c391c6…" },
  "counts": { "applied": 2, "review": 2, "refused": 1, "protected": 31,
              "diagnostics": 5, "insufficient_sample": 2 },
  "input":  { "format": "markdown", "sha256": "2d3888ed…" },
  "output": { "sha256": "e6b9106a…", "changed": true, "text": "…" }
}
```

Each applied change, suggestion and refusal is listed in full with its rule,
its position in the original and in the revised text, and — for a refusal —
the reason. Each protected fact is listed with its position. The same input
always produces the same bytes, so the two SHA-256 values identify exactly
what went in and what came out.

`plainspeak present` never changes `reply.md`. To write the result to a file:

```bash
plainspeak present reply.md --profile natural --format text -o reply-plain.md
```

It will not replace an existing file unless you add `--overwrite`, and it will
never replace `reply.md` itself.

## 5. Review in the desktop application

```bash
plainspeak-desktop
```

1. Press **Open…** on the toolbar (`Ctrl+O`) and choose `reply.md`. The original appears on
   the left and the revised version on the right, with the three SAFE changes
   already made.
2. Choose a profile from the drop-down if you want something other than
   Natural. Changing it re-reads the document and clears any decisions.
3. The **Changes** tab lists every change. Rows marked `SAFE` are done; rows
   marked `REVIEW` are waiting for you; rows marked `REFUSED` have no button,
   by design. **Previous change** and **Next change** (`F6`/`F7`) step through
   them.
4. Select a `REVIEW` row and press **Accept** or **Reject**. Accept both
   "Nevertheless," suggestions and the right-hand pane updates.
5. The **Style** tab shows the observations, and a `NOT ENOUGH TEXT` row for
   each check the document was too short for. The **Integrity** tab shows the
   refusal. **Details** shows every rule-set version and fingerprint.

## 6. Save

Press **Save As…** on the toolbar (`Ctrl+Shift+S`) and choose a new name, such as
`reply-reviewed.md`. There is no plain Save: PlainSpeak refuses to overwrite
the document you opened, and it writes the engine's result rather than
whatever is on screen.

## 7. Check someone else's rewrite

PlainSpeak can also judge a rewrite it did not make — by a colleague, an AI
assistant, another tool. First, give it one it can vouch for: its own.

```bash
plainspeak present reply.md --profile natural --format text -o reply-presented.md
plainspeak verify reply.md reply-presented.md
```

```text
PlainSpeak verify — ACCEPTED
  every protected item survived, and every difference is one the integrity model accounts for.
...
Accounted for: 2
  PlainSpeak SAFE rule PS.CLARITY.009 'prior to' -> 'before'
  PlainSpeak SAFE rule PS.LEXICAL.001 'utilize' -> 'use'
```

Now make a copy of `reply.md` called `reply-edited.md`, and in it change
"Nevertheless, some features will move." to "Some features are moving." and
"at least 12 characters" to "at least 10 characters" — the kind of slip a
hurried rewrite makes. Then:

```bash
plainspeak verify reply.md reply-edited.md
```

```text
PlainSpeak verify — REFUSED
  a protected item or a region PlainSpeak never rewrites was lost, added or changed.
...
Refused: 2
  [modal] modal removed: will  (before line 7)
  [number] number changed: 12 became 10  (before line 11; after line 11)
```

The exit status is 0 for `ACCEPTED`, 1 for `REFUSED` and 3 for `INCONCLUSIVE`
— nothing protected was lost, but something changed that PlainSpeak cannot
vouch for, which is what most free rewrites get. None of the three means the
two texts say the same thing; `ACCEPTED` means only that every protected item
survived and every difference is accounted for. [VERIFY.md](VERIFY.md) says
exactly what is and is not checked, and how to run the same check in CI.

## What next

- Try the same document under `--profile technical` or `--profile academic`
  and compare the style observations.
- `plainspeak profiles explain natural` shows exactly what a profile expects.
- `plainspeak rules list` shows the whole rulebook.
- `plainspeak serve` lets an AI agent call `present`, `verify` and `diagnose`
  as tools; see [MCP.md](MCP.md).
- [LIMITATIONS.md](LIMITATIONS.md) says what PlainSpeak cannot do.
