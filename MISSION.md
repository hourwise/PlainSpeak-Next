# Mission

## Chosen problem

**Information inaccessibility caused by unnecessarily complex language.**

Every day, people encounter text they cannot understand: medical instructions, legal notices, government forms, terms of service, insurance policies, and public health guidance. The complexity is rarely necessary — it persists because writers default to jargon, institutions optimize for legal defensibility over clarity, and few tools exist to help writers see their text through their readers' eyes.

This creates real harm:
- Patients misunderstand medication instructions.
- Tenants sign leases they cannot parse.
- Citizens cannot engage with policy consultations.
- Non-native speakers are systematically excluded.
- People with cognitive disabilities, low literacy, or fatigue face barriers that are artefacts of presentation, not of content.

## Intended beneficiaries

1. **People with lower literacy levels** (approximately 1 in 5 adults in OECD countries read at or below primary-school level).
2. **Non-native speakers** of the language a document is written in.
3. **People with cognitive disabilities** (dyslexia, ADHD, acquired brain injury, cognitive fatigue from illness).
4. **Elderly people** experiencing age-related changes in working memory and processing speed.
5. **Anyone under time pressure or stress** who needs to understand something quickly.
6. **Writers and editors** in public service, healthcare, law, and education who want to check whether their text is accessible.

## Why the problem matters

Language is infrastructure. When public information is written at a reading level that excludes a substantial portion of the population, that is not a literacy problem — it is an access problem. The people most affected are often those already facing other disadvantages.

Existing readability tools are either:
- Proprietary and expensive (e.g., Grammarly, Readable.com);
- Embedded in word processors most people don't use for reading web content;
- Overly technical in their output;
- Not designed for the people who most need them.

## Intended form of benefit

A free, open-source, offline toolkit that:
1. **Measures** how readable a text is using multiple established metrics.
2. **Identifies** specific passages that create comprehension barriers.
3. **Explains** why each issue matters in plain language.
4. **Suggests** simpler alternatives where available.
5. **Produces** accessible, self-contained HTML reports that can be shared with writers.

The tool is designed to be used both by content creators checking their own work and by advocates or educators helping others understand difficult documents.

## Explicit non-goals

- We are **not** building an AI text generator or LLM-based rewriter.
- We are **not** attempting to replace human judgement in communication.
- We are **not** creating a grammar checker or style guide enforcer.
- We are **not** targeting creative or literary writing.
- We are **not** collecting user data or requiring network access.
- We are **not** claiming to make all text universally accessible.

## Ethical boundaries

1. **No data collection.** The tool operates entirely locally. No text is sent anywhere.
2. **No deception.** The tool identifies issues and suggests alternatives; it does not rewrite text in ways that could change meaning without the user's knowledge.
3. **No paternalism.** The tool explains what it finds and why; it does not dictate what the user must do.
4. **Accessibility of the tool itself.** The HTML output must meet WCAG 2.1 AA standards.
5. **Transparency of limitations.** The tool clearly communicates that automated readability metrics are proxies, not direct measures of human comprehension.
6. **Respect for domain expertise.** The tool flags complexity but does not claim that all jargon is unnecessary — some precision is essential in legal, medical, and technical contexts.

## Measures of success

1. The tool correctly computes at least four established readability metrics (Flesch-Kincaid, Flesch Reading Ease, Gunning Fog, SMOG).
2. The tool identifies at least five categories of readability barrier (passive voice, long sentences, complex words, nominalizations, jargon terms with plain alternatives).
3. The HTML report is itself accessible (passes automated WCAG checks).
4. A person unfamiliar with the project can install it, run it on a sample text, and understand the output within 10 minutes.
5. Tests cover core metrics with known-answer verification against manually scored texts.
6. All processing is offline with zero network calls.
