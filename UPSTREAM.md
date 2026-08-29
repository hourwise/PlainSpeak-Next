# Upstream lineage

This repository is a **descendant** of the original PlainSpeak project. It was
created by preserving the full Git history of that project and then continuing
development independently.

## Origin

| Field | Value |
|---|---|
| This repository | https://github.com/hourwise/PlainSpeak-Next |
| Original repository | https://github.com/hourwise/Project-PlainSpeak |
| Source commit (SHA) | `74ecd51b3ff85af75cd6096524213e19e5d006b8` |
| Source commit subject | Fix P0: move protected-terms check to shared find_glossary_match + cross-type dedup |
| Source commit date | 2026-08-11 |
| Source branch | `main` |
| Root commit of preserved history | `6a233946d9f7540d2857fb81e96cbe26fc7ae630` (2026-07-18) |
| Commits inherited | 24 |
| Descendant created | 2026-08-29 |
| Original licence at fork point | MIT (Copyright (c) 2026 PlainSpeak) |

The licence file inherited from the upstream project is retained unmodified at
[`LICENSE`](LICENSE). Every commit up to and including `74ecd51` in this
repository is the work of the upstream project under that licence.

## Relationship to upstream

This is a deliberate **one-way split**.

- Development in this repository is **independent** of the upstream project.
  Design decisions here do not represent the upstream project's direction.
- There is **no automatic syncing** from upstream. No remote tracking the
  original repository is configured, and none should be added. Changes are not
  pulled, merged, rebased, or cherry-picked from upstream as a matter of course.
- Nothing is pushed **back** to upstream. The original repository receives no
  commit, branch, tag, release, issue, or documentation change as part of this
  project.
- The original PlainSpeak repository remains a valid standalone project. It is
  not deprecated, superseded, or replaced by this one.

## Why the split

Upstream PlainSpeak is a readability **analyser**: it measures text, identifies
barriers, and suggests glossary substitutions for a human to review. It is
deliberately cautious about automatic rewriting, because naive word
substitution breaks grammar and can change meaning.

This descendant takes the analysis work as a starting point and builds a
different class of tool on top of it: a deterministic prose **transformation
and review engine**, with a document intermediate representation, a declarative
rule system, an integrity layer that rejects meaning-changing edits, a desktop
application, and a headless MCP adapter — all local, and with no language
model, embeddings, or remote inference anywhere in the pipeline.

Those goals imply architectural changes that would not be appropriate to impose
on the upstream project, which is why this is a descendant rather than a branch.

## Verifying the lineage

The inherited history can be checked at any time:

```bash
git log --oneline | tail -1          # root commit 6a23394
git cat-file -t 74ecd51              # commit, present in this repository
```
