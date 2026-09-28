# Verify fixtures

One original and three transformations of it, used by `tests/test_github_action.py`
and by the `Verify action` workflow, which runs the GitHub Action from this
repository against them.

| File | Expected | Why |
|---|---|---|
| `accepted.md` | ACCEPTED | a PlainSpeak SAFE rule (`prior to` → `before`), a fact equivalence (`£1,500` → `£1500`) and nothing else |
| `refused.md` | REFUSED | `must` became `should`, `30 June` became `30 July`, and `cannot` became `can` |
| `inconclusive.md` | INCONCLUSIVE | every protected item survived, but "the date your payment is taken" was reworded |
