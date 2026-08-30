# Style calibration

Where the numbers in `plainspeak/style/policy.py` came from, what evidence
supports each one, and — the part that matters most — which of them are not yet
supported by enough evidence to be trusted.

Nothing here is trained. The corpus in `tests/style/corpus/` is regression data:
fourteen documents written for this repository, six of them ordinary prose whose
only job is to stay quiet. No external corpus is bundled, no copyrighted prose is
reproduced, and no model of any kind is involved at any point.

## What a threshold is for

Every diagnostic answers one question with arithmetic — a rate, a ratio, a
coefficient of variation — and then compares that number to two lines. Above the
first it is a `notice`; above the second a `strong`. Below both it says nothing.
Uniformity runs the other way: *less* variation is the finding, so
`SENTENCE_UNIFORMITY` and `PARAGRAPH_UNIFORMITY` are inverted and their `strong`
line sits below their `notice` line.

The thresholds are product behaviour, not implementation detail. Moving one
changes what a reader is told, so `policy_hash()` covers all of them and
`tests/test_style_policy.py` pins the result on every platform. Changing 5% to 8%
fails the build until somebody updates the pin deliberately.

## The two guards

A threshold alone is not enough, because a ratio computed over four sentences is
arithmetic rather than evidence. Every diagnostic also declares the smallest
sample it will speak about, and returns nothing beneath it. The minimum sample
does more work than the threshold in this corpus, and in one case it is doing
*all* of the work — see the weaknesses below.

## How the corpus separates

Measured values for all fourteen documents. `—` means the diagnostic found
nothing to measure at all (no flagged word, no repeated opener); a number below
the minimum sample is shown with the sample in brackets, and is silent regardless
of what the number says.

### Sentence uniformity — coefficient of variation, inverted

Lines: `notice` 0.34, `strong` 0.26. Minimum sample 8 sentences.

| natural | CV | repetitive | CV |
|---|---|---|---|
| `long_natural` | 0.725 | `framing_heavy` | 0.736 |
| `conversational` | 0.651 | `vocabulary_heavy` | 0.707 |
| `technical` | 0.575 | `transition_heavy` | 0.601 |
| `short` | 0.544 (3) | `overlapping` | 0.557 |
| `academic` | 0.501 | `repeated_openers` | 0.531 |
| `government` | **0.476** | `uniform_paragraphs` | 0.469 |
| | | `list_heavy` | **0.342** |
| | | `uniform_cadence` | **0.244 → strong** |

The nearest natural document sits 0.136 above the notice line — about 40%
headroom, which is the widest margin in the corpus. The uncomfortable number is
`list_heavy` at 0.342, two thousandths above the line. Bullet points are short
and similar to each other by nature, so list-shaped prose lands very close to
where uniform prose lands. It does not currently fire, and I would not describe
that as a margin.

### Paragraph uniformity — coefficient of variation, inverted

Lines: `notice` 0.20, `strong` 0.12. Minimum sample 8 paragraphs.

| document | kind | CV | paragraphs |
|---|---|---|---|
| `long_natural` | natural | 0.611 | 9 |
| `technical` | natural | 0.388 (6) | 6 |
| `conversational` | natural | 0.292 (5) | 5 |
| `vocabulary_heavy` | repetitive | 0.224 (6) | 6 |
| `repeated_openers` | repetitive | 0.164 (4) | 4 |
| `government` | natural | 0.157 (5) | 5 |
| `overlapping` | repetitive | 0.145 (5) | 5 |
| `framing_heavy` | repetitive | 0.132 (6) | 6 |
| `academic` | natural | 0.109 (4) | 4 |
| `transition_heavy` | repetitive | 0.094 (4) | 4 |
| `uniform_paragraphs` | repetitive | **0.059 → strong** | 10 |

**This is the weakest calibration in the layer, and the table shows why.** Only
two of the fourteen documents clear the eight-paragraph minimum. Every other row
is silent because of its sample size, not because of its measurement — and four
of them, including two natural documents, would fire `strong` if the minimum
were lower.

That minimum was not chosen for elegance. At five paragraphs, `government.md`
produced a false positive: a plain-English public-service document, five
paragraphs of deliberately similar length because that is what the register
calls for, reported as uniform. Raising the minimum to eight silenced it, and
`long_natural.md` and `uniform_paragraphs.md` were written afterwards so that
the threshold had at least one document on each side that actually reached it.

So the threshold is supported by exactly one natural data point. It separates
0.611 from 0.059 cleanly, which is a real separation, but a single natural
sample is not evidence that 0.20 is the right line — only that it is not
obviously the wrong one. More long natural documents would help; short ones
would not, because they cannot reach the minimum.

### Repeated sentence opener — share of sentences sharing an opening

Lines: `notice` 0.35, `strong` 0.50. Minimum sample 6 sentences.

Natural: 0.100–0.182. Repetitive that should *not* fire: up to 0.323
(`uniform_paragraphs`) and 0.316 (`framing_heavy`). Firing: `transition_heavy`
0.471 (notice), `repeated_openers` 0.706 (strong).

Wide headroom above natural prose (0.17), narrower below the nearest
non-target (0.03). The line sits closer to documents that are genuinely
repetitive in some other way than to ordinary writing, which is the correct
side to be tight on.

### Transition density — share of sentences opening with a transition

Lines: `notice` 0.20, `strong` 0.35. Minimum sample 8 sentences.

Natural: 0.071–0.167. Firing: `uniform_cadence` 0.273 (notice),
`transition_heavy` 0.471 (strong).

The highest natural value is `long_natural` at 0.167, leaving 0.033 of margin —
the second-tightest in the corpus. Prose that signposts heavily is not
automatically bad prose, and a document a little more signposted than
`long_natural.md` would cross this line. The `notice` band is doing the right
thing by being a notice.

### Repeated transition — share of transitions that are the same one

Lines: `notice` 0.50, `strong` 0.70. Minimum sample 6 transitions.

Only `transition_heavy` reaches the minimum, at 1.0. The closest natural
document, `long_natural`, has five transitions with a 0.4 concentration —
below the minimum, so silent, and below the line in any case.

**No natural document in the corpus clears this minimum.** The threshold is
therefore untested from the quiet side. It has not produced a false positive
because nothing natural has had six transitions to concentrate.

### List dominance — share of blocks that are list items

Lines: `notice` 0.50, `strong` 0.70. Minimum sample 6 blocks.

Every natural document measures 0.0; `list_heavy` measures 0.789.

Perfect separation, and worth almost nothing. **No natural document in the
corpus contains a single list.** A well-structured technical page with a
legitimate seven-item list is exactly the case this threshold needs to be
tested against, and there is no such document here. This diagnostic is
plausible rather than calibrated.

### Canned framing, lexical overlap, repeated phrase, vocabulary overuse

| diagnostic | lines | natural | firing |
|---|---|---|---|
| `CANNED_FRAMING` | 0.25 / 0.50 | nothing found | `framing_heavy` 1.0 |
| `LEXICAL_OVERLAP` | 0.60 / 0.75 | nothing found | `overlapping` 1.0 |
| `REPEATED_PHRASE` | 0.60 / 1.20 | nothing found | `uniform_paragraphs` 1.167, `vocabulary_heavy` 1.408 |
| `VOCABULARY_OVERUSE` | 3.0 / 6.0 per 1,000 | nothing found | `vocabulary_heavy` 37.6 |

These four produce no measurement at all on natural prose — not a low number, no
finding. That is a cleaner result than a wide margin, but it also means the
thresholds are unexercised from below: they separate "some" from "none", and the
line between "a reasonable amount" and "too much" is not tested anywhere. The
`VOCABULARY_OVERUSE` minimum of 200 words exists because a rate per thousand
computed over 80 words is noise; only one corpus document reaches it.

### Rhetorical repetition and triadic repetition

Lines: 0.30 / 0.60 for both. **No corpus document exercises either.** Both are
covered only by targeted cases in `tests/test_style_diagnostics.py`, because a
whole document built to trip them would not resemble prose anyone writes and
would therefore be useless as calibration evidence. `tests/test_style_corpus.py`
names these two as the permitted exceptions, so a third one cannot be added
quietly.

## What the calibration is worth, stated plainly

Six natural documents, zero false positives. Eight repetitive documents, zero
misses. That is the headline and it is true, but it is a weaker claim than it
sounds, and these are the reasons:

1. **Fourteen documents is a small corpus.** It is enough to catch a threshold
   that is grossly wrong and not enough to establish that one is right.
2. **Three thresholds have no natural document on the quiet side of them** —
   repeated transition, list dominance, and paragraph uniformity has only one.
   They have not produced a false positive because nothing has tested them.
3. **Two diagnostics have no calibration document at all.**
4. **All fourteen documents are one author's English prose**, written for this
   purpose. Register varies deliberately; dialect, first-language background and
   genre do not. Prose written by someone whose English is a second language may
   legitimately have lower variation, and this corpus contains no evidence about
   what that does to these thresholds.
5. **The documents are short.** The longest is 352 words. Real reports run to
   thousands, and several of these measurements behave differently at length —
   a repeated opener that is 18% of a page may be 4% of a chapter.

Every one of these is a reason the output is phrased as an observation with its
arithmetic attached rather than as a verdict. A reader who disagrees with a
finding can look at the number, the threshold and the quoted evidence, and be
right.

## What this layer will never do

Diagnostics describe a document. They do not describe its author.

The method here cannot support an authorship claim at any confidence, and the
temptation to make one anyway is the most likely way this layer goes wrong — the
demand is real and the output looks superficially like the input such a claim
would need. So the prohibition is tested rather than merely written down.
`tests/test_style_policy.py` parses every non-docstring string literal in
`plainspeak/style/` and fails on `authorship`, `probability`, `likely ai`,
`human score`, `detector` and eleven other phrasings.

There is also no aggregate score, and `StyleAnalysis` is asserted to have no
field whose name contains `score`, `rating`, `probability`, `confidence` or
`likelihood`. A single number would hide the evidence that produced it, and a
single number is what gets pasted into a disciplinary email. What comes out
instead is `analysis.profile`: a band per diagnostic, each traceable to one
measurement and one threshold a reader can check by hand.

Uniform sentence lengths are a property of text. They are not a confession.

## Changing a threshold

1. Change the number in `plainspeak/style/policy.py`.
2. Run `python -m pytest tests/test_style_corpus.py`. The corpus snapshot at
   `tests/style/corpus-findings.json` will fail and name every document whose
   findings moved.
3. Look at the diff. If a natural document started producing a finding, the
   change is wrong.
4. Regenerate the snapshot, update `STYLE_POLICY_HASH` in
   `tests/test_style_policy.py`, and say in the commit message what a reader
   will now be told that they were not told before.

Adding a calibration document is cheaper than moving a threshold, and usually
the better answer.
