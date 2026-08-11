# Validation Scoring Format

Templates for human review of PlainSpeak's output.
Use these to evaluate every detected issue and suggestion.

---

## Barrier Review

For each detected readability barrier, classify:

| Label | Meaning |
|---|---|
| `correct_useful` | The finding is correct and the recommendation is helpful |
| `correct_low_value` | The finding is technically correct but unlikely to help |
| `debatable` | Reasonable people could disagree about this finding |
| `false_positive` | The finding is incorrect — this is not a real issue |

### Example barrier review

```yaml
barrier_id: "s3_passive_1"
type: passive_voice
sentence: "The form must be completed by the applicant."
classification: correct_useful
notes: "Clear passive construction. Active rewrite would help."
```

---

## Simplification Suggestion Review

For each suggested word/phrase replacement, classify:

| Label | Meaning |
|---|---|
| `clearly_helpful` | The suggestion improves clarity without changing meaning |
| `acceptable` | The suggestion is reasonable but the original is also fine |
| `awkward_harmless` | The suggestion reads awkwardly but does not mislead |
| `misleading` | The suggestion changes meaning or nuance inappropriately |
| `potentially_harmful` | The suggestion could cause misunderstanding in context |

### Example suggestion review

```yaml
suggestion_id: "s1_material"
original: "material breach"
suggested: "important breach"
domain: legal
classification: awkward_harmless
notes: "'Important' is not wrong but 'significant' or 'serious' would be more precise in legal context."
```

---

## Meaning Preservation

For mechanically simplified text, classify each change:

| Label | Meaning |
|---|---|
| `preserved` | Meaning is unchanged |
| `uncertain` | Cannot confidently determine if meaning changed |
| `changed` | Meaning has been altered |

### Example meaning review

```yaml
change_id: "c_3_provided_that"
original_segment: "provided, however, that the Indemnitor shall..."
simplified_segment: "but only if the Indemnitor must..."
classification: uncertain
notes: "The simplification loses the legal nuance of 'provided however that' vs 'but only if'."
```

---

## Aggregate Scoring

For each analyzed document:

### Barrier quality
- Total barriers detected: ___
- Correct and useful: ___ (___%)
- Correct but low value: ___ (___%)
- Debatable: ___ (___%)
- False positives: ___ (___%)

### Suggestion quality
- Total suggestions: ___
- Clearly helpful: ___ (___%)
- Acceptable: ___ (___%)
- Awkward but harmless: ___ (___%)
- Misleading: ___ (___%)
- Potentially harmful: ___ (___%)

### Overall utility
- [ ] The analysis helped identify real readability problems
- [ ] The suggestions provided useful starting points for revision
- [ ] The tool did not cause the reviewer to make a harmful change
- [ ] The difficulty band matched the reviewer's independent assessment

---

## Storage Format

Store review results as YAML or JSON files in:
```
validation/results/{sample_id}_{reviewer}_{date}.yaml
```

Aggregate results in:
```
validation/results/aggregate_{date}.yaml
```
