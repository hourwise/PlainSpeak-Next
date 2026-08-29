# Migrating the inherited PlainSpeak glossary

The original PlainSpeak project shipped a glossary of plain-language
substitutions: 608 entries in `GLOSSARY`, 153 in `SIMPLE_WORD_MAP`, 706 unique
terms between them. This document accounts for all of them.

## The rule that governed the work

> **The inherited glossary is source material. It is not a transformation
> policy.**

Nothing in it became an automatic fix because upstream suggested it. Upstream's
own README described that project as "a diagnostic and review tool — not an
authoritative automatic rewriting system", and the glossary was built to that
standard: it is full of entries that are excellent prompts for a human and
unusable as mechanical substitutions.

A few, chosen at random from the inherited data:

| Entry | Why it cannot be automatic |
|---|---|
| `said → the` | A legal-drafting convention, not a synonym |
| `beneficiary → person who receives the benefit` | A definition. It explains; it does not substitute |
| `return → tax form` | One domain's sense of a very common word |
| `capacity → ability to make decisions` | A legal test, glossed |
| `benign → not cancerous` | Introduces a negation the integrity firewall protects |

449 of the 706 entries were single words and therefore even candidates. 140
became rules.

## How each entry was classified

Every term went through four questions:

1. **Does it have one sense in ordinary prose?** "Employ" is both *use* and
   *hire*; "elect" is both *choose* and *vote for*; "sustain" is both *support*
   and *suffer*. Those are diagnostics.
2. **Is the replacement an equivalent, or a definition?** A gloss cannot stand
   in the slot the word occupied.
3. **Does it fit grammatically in every form the rule would generate?**
4. **Does the replacement introduce a fact the integrity firewall protects?**
   "Solely → only" introduces a comparator and would be vetoed at planning time.
   A rule that can never fire is worse than no rule: it is dead weight that
   looks like coverage.

The reviewed answers live in [`migration/decisions.yaml`](migration/decisions.yaml).
Anything the decisions file does not name takes a stated default, and the
default is `deferred` rather than `diagnostic` on purpose — a diagnostic is a
claim that a term is worth flagging, whereas deferring says only that nobody has
looked yet, which is the honest description of an entry inherited in bulk.

## The numbers

| Classification | Count | Meaning |
|---|---:|---|
| `safe-fix` | 140 | Individually reviewed; became a rule |
| `deferred` | 477 | Not yet individually reviewed, or a multi-word phrase |
| `diagnostic` | 36 | Worth flagging, cannot be substituted mechanically |
| `protected` | 23 | In the inherited protected-term register |
| `rejected` | 14 | The inherited suggestion is wrong and was not carried forward |
| `already-covered` | 16 | Handled by a hand-authored Phase 4 rule |
| **Total** | **706** | |

That total is asserted by a test, not written by hand. The machine-readable
inventory is [`migration/glossary-inventory.json`](migration/glossary-inventory.json),
which carries every entry with its classification, reason, source module,
duplicate status and — where it became a rule — its new ID and generated forms.
Its SHA-256 is pinned in the test suite.

477 deferred entries is not a gap being hidden. It is the honest state: those
terms have not been read one by one, and until they have, the engine says
nothing about them. The inherited flat path still uses all 706 and remains
sealed by its characterisation goldens.

## Rejected entries

Fourteen inherited suggestions were judged wrong rather than merely unproven,
mostly legal terms glossed into approximations: `certiorari → review`,
`estoppel → barred from denying`, `laches → unreasonable delay`,
`subrogation → stepping into another's shoes`. The declarative engine does not
have to reproduce upstream's mistakes; the inherited path keeps them, sealed.

`hmrc → tax office` was rejected on a different ground: an organisation's name
is not a synonym for a description of it.

## Morphology

A lexical rule declares a lemma and a part of speech; the loader expands it into
explicit surface forms:

```yaml
match:
  type: lemma
  lemma: "utilise"
  pos: verb
action:
  type: replace
  lemma: "use"
```

becomes `utilise → use`, `utilises → uses`, `utilised → used`,
`utilising → using`. The forms are stored on the rule, shown by
`plainspeak rules explain`, and included in the ruleset hash — so a change to
morphology changes the ruleset identity rather than silently changing what it
matches.

**Morphology runs forwards only.** It never takes a surface form and works out
what it came from. The inherited simplifier did exactly that — strip a suffix,
hope the result is a word — and suggested the verb "clare" for the noun
"clarity". Going forwards from a declared lemma, the worst case is a form nobody
uses; it cannot be a word that does not exist.

Nominalisation reversal was **not** migrated. It stays a diagnostic in the
inherited path, which is where the `clare` defect lives and stays.

### What the grammar review found

Every generated form was read. Six were wrong, and the reviewed tables now
cover them:

| Was | Should be | Cause |
|---|---|---|
| `concured` | `concurred` | missing from the doubling list |
| `baned` | `banned` | missing from the doubling list |
| `steped in` | `stepped in` | missing from the doubling list |
| `spreaded` | `spread` | missing from the irregular table |
| `meaned` | `meant` | missing from the irregular table |
| `undertaked` | `undertook` | missing from the irregular table |

A seventh defect was structural rather than a missing entry. A regular English
verb writes its past and its past participle the same way, so
`accomplished → did` and `accomplished → done` are both reachable from one
surface, and "the work was accomplished" would have become "the work was did".
The engine now **drops** a form whose source surface maps to two possible
targets. `accomplish → do` therefore covers base, third person and gerund, and
simply does not match the past. That is the same answer as everywhere else in
this project: where it cannot tell, it says nothing.

All generated forms are pinned in
[`tests/morphology/generated-forms.txt`](tests/morphology/generated-forms.txt),
in plain English rather than as a hash, because that is the file where the next
"clare" would be visible to a reader.

### `inflect`

The build plan proposed adopting the `inflect` package. It was evaluated and not
adopted. It is MIT-licensed and supports the required Python versions, so the
decision is about fit:

- **It cannot do the main job.** `inflect` is very good at noun plurals,
  singulars and `a`/`an`. It has no verb tense or aspect API — `plural_verb`
  concerns number agreement, not conjugation — and verb inflection is what the
  glossary needs.
- **It would couple a safety identity to a third party.** The morphology hash is
  pinned and asserted on three platforms. Deriving forms from an external
  package means that identity moves whenever the package changes its heuristics,
  for reasons unrelated to any decision made here.

If a later phase needs broad noun morphology over open vocabulary, `inflect` is
the right place to look.

## Collisions

Adding 176 rules to 38 makes collisions likely, so they are audited rather than
hoped about. All four checks are tests:

| Check | Result |
|---|---:|
| Two rules claiming the same surface | 0 |
| A rule's output matched by another rule (cycle) | 0 |
| A generated surface that is a protected term | 0 |
| A surface generated by two different lemmas | 0 |

The first audit run found 13 collisions: the migration was about to add a second
rule for `utilise`, `commence`, `ascertain`, `demonstrate` and `aforementioned`,
all of which Phase 4 already covered by hand. Those are now detected
automatically and classified `already-covered`, keeping the original rule IDs —
**no existing rule ID was renumbered**, because an ID is a permanent identity
that an audit record may already name.

## Integrity

Every automatic rule was run through the Phase 5 firewall.

- **162 accepted.**
- **2 vetoed**, and they are the same two Phase 5 already documented:
  `PS.CLARITY.009` (introduces the protected comparator "before") and
  `PS.FRAMING.003` (deletes a phrase containing the modal "should").

Migration added no new systematic vetoes, and **the integrity policy was not
weakened** — its version and hash are unchanged at `2026.1` /
`21532115747c…`. No override mechanism was introduced, and none will be smuggled
in under a migration.

## Identities

| | Before | After |
|---|---|---|
| Ruleset | `2026.1` / 38 / `2110d4ed…` | `2026.2` / 214 / `e5aaf376…` |
| Integrity policy | `2026.1` / `21532115…` | unchanged |
| Morphology | — | `2026.1` / `93fba690…` |
| Glossary inventory | — | `b1657b20…` |

All four are pinned in the test suite and asserted on Windows, Linux and macOS,
so the platforms agree with each other rather than each with itself.

## Provenance

The inherited glossary comes from
[hourwise/Project-PlainSpeak](https://github.com/hourwise/Project-PlainSpeak)
under its MIT licence, recorded in [UPSTREAM.md](UPSTREAM.md). Every migrated
rule records `plainspeak/core/glossary.py` as its reference and is marked
`project-authored`: the classification, the rule wording, the examples and the
reasons are this project's work. No external glossary or style guide was
consulted or incorporated during this migration, so `THIRD_PARTY_NOTICES.md`
needs no addition — and a test enforces that any rule ever claiming otherwise
must appear there.

## What is still to do

- **477 deferred entries.** Each needs the same four questions asked of it.
- **228 multi-word entries.** Phrase rewriting needs syntactic review, not
  lexical substitution.
- **Integrity equivalences.** A reviewed way for a rule to declare that a
  substitution preserves a comparator would release `prior to → before`. That
  is a safety mechanism and belongs in its own phase, not in a migration.
- **Comparatives and superlatives.** No shipped rule needs them, and an
  untested form class is a liability.
