# Style calibration corpus

Project-authored regression and calibration data. **Nothing is trained on it.**

Its two jobs:

1. **Calibration.** Every threshold in `plainspeak/style/policy.py` was set by
   measuring these documents and choosing a line the natural samples sit below
   and the repetitive ones sit above. The margins are recorded in
   `STYLE_CALIBRATION.md`.
2. **Regression.** A change to a metric or a threshold shows up as a change in
   which documents produce which findings.

Every file is written for this repository. No external corpus is bundled, no
copyrighted prose is reproduced, and nothing here was gathered from the web.

## What is here, and why

| File | Kind | What it is for |
|---|---|---|
| `conversational.md` | natural | Varied cadence, contractions, questions — must stay quiet |
| `technical.md` | natural | Formal but varied technical prose — must stay quiet |
| `government.md` | natural | Public-service register, plain but formal — must stay quiet |
| `academic.md` | natural | Long sentences, careful hedging — must stay quiet |
| `short.md` | natural | Below every minimum sample size — must produce nothing |
| `long_natural.md` | natural | Long enough to clear the paragraph minimums — must stay quiet |
| `uniform_cadence.md` | repetitive | Sentences all one length |
| `repeated_openers.md` | repetitive | Same sentence and paragraph openings |
| `transition_heavy.md` | repetitive | One transition doing all the work |
| `framing_heavy.md` | repetitive | Canned framing in most paragraphs |
| `vocabulary_heavy.md` | repetitive | Flagged vocabulary clustered |
| `list_heavy.md` | repetitive | Mostly bullet points |
| `overlapping.md` | repetitive | Two paragraphs restating each other |
| `uniform_paragraphs.md` | repetitive | Ten paragraphs of near-identical length |

The natural samples matter more than the repetitive ones. Anyone can write a
detector that fires; the work is in not firing on ordinary prose, and six of the
fourteen documents here exist to hold the thresholds honest about that.
