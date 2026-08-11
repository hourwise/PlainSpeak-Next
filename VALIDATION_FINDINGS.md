# Validation Findings

Significant discoveries from reviewing PlainSpeak's output against
real-world texts. Each entry describes a finding, its impact, and
the corrective action taken.

---

## Finding 1: "material" mapped to "relevant" (legal false friend)

**Date:** 2026-08-11
**Source:** Legal indemnification passage
**Severity:** High — could mislead

### Observation
PlainSpeak suggested replacing "material breach" with "relevant breach".
In legal English, "material" means "significant" or "important", not "relevant".

### Impact
A writer following this suggestion would produce a legally inaccurate text.
"Relevant breach" has a different meaning from "material breach" in contract law.

### Correction
Changed glossary entry from `"material": "relevant"` to `"material": "important"`.
Added domain-awareness note: this word has different meanings in legal vs
everyday contexts.

### Regression test
Added to `tests/test_glossary.py`: verify "material" maps to "important" not "relevant".

---

## Finding 2: "provided, however, that" stemmed to verb "provide"

**Date:** 2026-08-11
**Source:** Legal indemnification passage
**Severity:** High — produces nonsensical output

### Observation
The legal conjunction "provided, however, that" (meaning "on the condition that")
was being stemmed to the verb "provide" and then replaced with "give", producing:
"give, but, that" instead of "but only if".

### Impact
The simplified text was grammatically broken and semantically wrong.
This is a fundamental word-sense disambiguation failure.

### Correction
Added "provided that", "provided, however, that", and "provided however that"
as multi-word phrase entries in the glossary, which are matched before
word-by-word stemming.

### Regression test
Added to `tests/test_glossary.py`: verify phrase entries exist and are
matched before word stemming.

---

## Finding 3: Syllable counter overcounted "every" as 3 syllables

**Date:** 2026-08-11
**Source:** CMU Pronouncing Dictionary comparison
**Severity:** Medium — affected all syllable-dependent metrics

### Observation
The heuristic syllable counter reported "every" as having 3 syllables.
CMUdict confirms it has 2 syllables (EH1 V R IY0). This is a known
failure mode of pattern-based syllable counting for words with
consecutive vowel graphemes.

### Impact
Flesch-Kincaid, Gunning Fog, and SMOG indices were all slightly inflated
for texts containing "every" (one of the most common English words).

### Correction
Integrated CMU Pronouncing Dictionary (125K+ words) as primary syllable
source. Heuristic is now a fallback only.

### Regression test
Updated `tests/test_analyzer.py`: "every" now expected at 2 syllables.

---

## Finding 4: "pro-rata" (hyphenated) not matched by word or phrase pass

**Date:** 2026-08-11
**Source:** Legal indemnification passage
**Severity:** Low — missed simplification opportunity

### Observation
"pro-rata" (with hyphen) was not being matched because:
- Phrase matcher only handles entries with spaces
- Word matcher only matches `[a-zA-Z]+` (no hyphens)

### Impact
Hyphenated terms like "pro-rata", "pro-bono", "by-laws" were invisible
to the simplification engine.

### Correction
Added hyphenated-term matching pass between phrase and word passes.

### Regression test
Verified "pro-rata" → "in proportion" in legal text simplification.

---

## Finding 5: Double-replacement inside marked text

**Date:** 2026-08-11
**Source:** Legal text simplification
**Severity:** Medium — produced nested and confusing markup

### Observation
After phrase "pro-rata" was replaced with "**in proportion**", the word
matcher subsequently replaced "portion" → "share", producing:
"**in **share****" (nested, broken markup).

### Impact
The simplified text output contained broken markup that would confuse users.

### Correction
Implemented segment-aware replacement: split text on `**...**` boundaries
and only apply word replacements to non-marked segments.

### Regression test
Verified no double-replacement in legal text output.

---

## Finding 6: Suffix ordering caused "modified" → "modifi"

**Date:** 2026-08-11
**Source:** CRISPR gene-editing passage
**Severity:** Medium — stemmer produced wrong base forms for many verbs

### Observation
The suffix list had "ed" before "ied", so "modified" matched "ed" first
and produced stem "modifi" instead of correctly matching "ied" and
producing "modify".

### Impact
Many regular -ied verbs (carried, modified, satisfied) were incorrectly
stemmed, preventing glossary matches.

### Correction
Reordered SUFFIXES_TO_STRIP strictly longest-to-shortest.

### Regression test
Added stemming test cases for -ied verbs.
