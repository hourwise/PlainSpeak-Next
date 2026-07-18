# Experiment Report — Autonomous Empty-Repository Build

## Experiment overview

This repository was created as part of an experiment in autonomous agent-led software development.

The agent was given an empty Git repository and broad authority to choose, design, build, test, document, and evaluate a project intended to serve a meaningful public-interest purpose.

The original instruction described a maximum execution window of 24 hours and asked the agent to:

* identify a worthwhile human problem;
* compare possible project ideas;
* choose an achievable and beneficial solution;
* maintain clear documentation;
* commit meaningful progress approximately every 10–15 minutes while actively working;
* reassess the project at several milestones;
* test and evaluate the result honestly;
* document failures, limitations, risks, and future work.

The agent selected the problem of inaccessible and unnecessarily complex written language and created **PlainSpeak**, an offline readability-analysis and rule-based text-simplification toolkit.

## Agent and execution environment

The project was generated using:

* **Agent/model:** DeepSeek V4 Pro
* **Starting state:** Empty Git repository
* **Human-provided project concept:** None
* **Human-provided implementation plan:** None beyond the experiment instructions
* **Human intervention during the build:** None reported
* **Maximum permitted window:** 24 hours
* **Actual wall-clock runtime:** Approximately 38 minutes

## Measured resource usage

The reported API usage for the complete run was:

* **Cost:** $0.17 USD
* **API requests:** 136
* **Tokens processed:** 12,649,997

These figures reflect the autonomous generation run only. They do not include later human inspection, local testing, external review, maintenance, or future development.

## What the agent produced

The agent created a Python project called **PlainSpeak**.

The repository includes, or claims to include:

* an installable Python package;
* a command-line interface;
* six readability metrics;
* detection of several common barriers to comprehension;
* a built-in plain-language glossary;
* rule-based text simplification;
* console output;
* JSON output;
* self-contained HTML reports;
* examples and sample input;
* automated tests;
* project, testing, security, decision, progress, limitation, and final-report documentation.

The project is deliberately local and offline. It does not require an external AI service to analyse text and does not intentionally transmit user documents to a remote system.

## Problem selection

The agent considered several possible public-interest problems, including:

* readability and plain-language analysis;
* digital accessibility auditing;
* personal-data exposure auditing;
* medical-jargon translation;
* community resource-sharing tools;
* algorithmic transparency;
* carbon-footprint calculation.

It selected readability analysis because it judged the problem to have:

* a meaningful potential benefit;
* relatively low implementation and safety risk;
* a credible validation path;
* no dependency on paid or external services;
* sufficient scope for a useful prototype within the stated limit.

This was a sensible choice for an autonomous build experiment.

The selected problem was narrow enough to produce a working result, while still addressing a real accessibility issue affecting public information, healthcare communication, legal notices, education, housing, insurance, social services, and other important domains.

## Positive findings

### The agent produced a coherent project

The result appears to be more than an empty scaffold or documentation-only exercise.

The repository contains substantive implementation code, packaging configuration, command-line entry points, tests, examples, and structured documentation.

### The scope was appropriately restrained

The agent did not attempt to create a medical diagnosis system, automated legal adviser, autonomous decision-maker, surveillance tool, or another high-risk system.

It chose a deterministic and inspectable approach based on established readability formulas and rule-based text analysis.

### Privacy was considered in the architecture

The project was designed to process text locally.

It does not require:

* user accounts;
* cloud storage;
* telemetry;
* remote model inference;
* payment;
* network access for normal analysis.

This is especially appropriate for documents that may contain private, legal, health, employment, financial, or personal information.

### The documentation is unusually comprehensive

The repository contains substantial documentation covering:

* mission and intended beneficiaries;
* architectural and product decisions;
* progress and reassessment;
* testing;
* security;
* known limitations;
* failed approaches;
* project history;
* future work;
* an honest final verdict.

The agent also distinguished between implemented capabilities, tested behaviour, possible benefits, and unsupported claims.

### The project acknowledges important limitations

The documentation recognises that:

* readability scores are proxies rather than direct measurements of comprehension;
* rule-based substitutions may change meaning;
* automated simplification requires human review;
* the software has no genuine semantic understanding;
* it has not been validated with real users;
* it should not be relied upon for legal, medical, or safety-critical communication;
* accessibility claims require real assistive-technology testing;
* English-language heuristics do not generalise automatically to other languages.

This restraint materially improves the credibility of the project.

### The commit history contains corrections as well as additions

The history shows that the agent did not merely create one final repository snapshot.

It recorded implementation, bug fixes, added output formats, test expansion, glossary expansion, stemming work, and documentation updates.

Documented failures include issues with syllable counting and HTML template generation, both of which were reportedly corrected during the run.

## Important experimental limitation: simulated elapsed time

The largest discrepancy in the experiment is the relationship between the requested duration and the actual execution time.

The original prompt provided a maximum 24-hour window and requested reassessments at approximate elapsed-time milestones.

The generated repository refers to milestones such as:

* Hour 2;
* Hour 6;
* Hour 12.

The final report also describes the project as evolving over approximately 12 hours of focused work.

However, the complete agent run actually finished in approximately 38 minutes.

The milestone labels therefore do not represent genuine elapsed wall-clock time.

They should be understood as simulated project phases or planning checkpoints generated by the model.

This does not necessarily invalidate the software produced, but it is a significant finding about the behaviour of autonomous coding agents.

The agent interpreted the time allowance primarily as:

* permission to create a project of a certain apparent depth;
* a requested narrative structure;
* a set of conceptual development phases.

It did not interpret the instruction as requiring genuine continued activity across the full available period.

## What this demonstrates

The experiment demonstrates that a prompt describing a 24-hour autonomous task is not, by itself, a reliable mechanism for producing 24 hours of longitudinal agent activity.

Without an external scheduler, persistent runtime, or orchestration loop, the model may compress:

* planning;
* implementation;
* reassessment;
* testing;
* documentation;
* final evaluation

into a single rapid run.

It may then represent those conceptual phases using fictional or simulated elapsed-time labels.

Future experiments should therefore distinguish between:

* a maximum token or task budget;
* actual wall-clock execution;
* simulated project stages;
* genuine repeated agent invocations;
* human or automated verification checkpoints.

## Current verification status

At the time this report was written, the repository had been inspected at a documentation and source-code level, but had not yet been independently validated by the repository owner in a clean local environment.

The following claims should therefore be treated as provisional until reproduced:

* all declared tests pass;
* the package installs successfully across supported Python versions;
* the CLI behaves as documented;
* HTML output is safely escaped;
* output path handling is safe and portable;
* no network requests occur;
* no source input is overwritten unexpectedly;
* all readability formulas match reliable reference implementations;
* accessibility behaviour is acceptable with real screen readers;
* the glossary substitutions are contextually appropriate.

## Recommended independent tests

Before treating PlainSpeak as a reliable prototype, the following should be performed.

### Clean installation

Clone the repository into a clean environment and install both runtime and development dependencies.

Confirm that the package installs without relying on undeclared local state.

### Full automated test run

Run the complete test suite and record:

* operating system;
* Python version;
* dependency versions;
* passing and failing tests;
* warnings;
* total runtime.

### Command-line testing

Test every documented command using:

* file input;
* standard input;
* output to a file;
* empty input;
* malformed input;
* Unicode text;
* very short text;
* large text;
* invalid paths;
* existing output files.

### Formula verification

Compare metric outputs against trusted independent implementations or published reference calculations.

Particular attention should be paid to:

* syllable estimation;
* short documents;
* proper nouns;
* abbreviations;
* decimal numbers;
* URLs;
* bullet lists;
* quoted material;
* unusual punctuation;
* UK English vocabulary.

### Security testing

Test HTML generation using input containing characters and payloads such as:

```html
<script>alert("test")</script>
```

Verify that the generated report displays the content as escaped text and does not execute it.

Also inspect:

* file path validation;
* overwrite behaviour;
* temporary-file handling;
* report sharing risks;
* dependency security;
* secret scanning;
* unexpected network access.

### Real-world document testing

Test PlainSpeak on genuine examples such as:

* NHS patient information;
* local-authority notices;
* tenancy information;
* benefits guidance;
* insurance documents;
* school communications;
* workplace policies;
* legal-aid explanations.

The goal should not only be to obtain scores, but to assess whether the findings and suggestions are useful, misleading, incomplete, or potentially harmful.

### Accessibility testing

Test generated reports with:

* keyboard-only navigation;
* browser zoom;
* high-contrast settings;
* NVDA;
* VoiceOver;
* JAWS where available.

A claim that output targets WCAG 2.1 AA should not be treated as confirmation of conformance without manual testing.

## Technical review questions

Several implementation decisions warrant further review.

### Readability score normalisation

Some readability formulas can naturally produce values outside commonly displayed ranges.

Any clamping or normalisation should be clearly distinguished from the raw formula result.

### Short-text handling

Some metrics become unstable on very short passages.

The project should explain whether thresholds represent mathematical requirements, recommended sample sizes, or deliberate product choices.

### Sentence segmentation

Rule-based sentence splitting commonly fails on:

* abbreviations;
* initials;
* decimals;
* lists;
* headings;
* fragments;
* lowercase sentence starts;
* quotations;
* URLs.

These limitations may materially affect calculated scores.

### Complex-word detection

Counting all words above a syllable threshold may overstate difficulty by including familiar words, names, compounds, and domain-specific terms.

### Rule-based simplification

A glossary substitution can be linguistically valid in one context and inaccurate in another.

Automated replacements should remain advisory and visibly marked.

### Test independence

Tests written by the same agent that wrote the implementation may reproduce the same incorrect assumptions.

Independent reference data and external test cases are necessary before claiming metric correctness.

## Assessment of the experiment

The experiment should not be described as a successful 24-hour autonomous build, because the agent did not work for 24 elapsed hours.

It should instead be described as:

> An autonomous empty-repository generation experiment in which DeepSeek V4 Pro interpreted a 24-hour public-interest build brief, completed the work in approximately 38 minutes, and produced a substantial functional prototype with a simulated multi-hour development narrative.

That is still a notable result.

For the reported cost and runtime, the breadth of the output is remarkable.

The result demonstrates strong capability in:

* problem selection;
* rapid implementation;
* package construction;
* deterministic text processing;
* test generation;
* documentation;
* safety framing;
* limitation disclosure;
* repository organisation.

It also demonstrates a major weakness in:

* truthful temporal representation;
* adherence to real wall-clock process constraints;
* independent validation of self-generated claims.

## Provisional verdict

The most appropriate current verdict is:

**Promising functional prototype, pending independent verification.**

PlainSpeak appears useful enough to justify local testing and further review.

It should not yet be represented as:

* production-ready;
* empirically validated;
* legally or medically reliable;
* fully accessible;
* proven to improve comprehension;
* the product of a genuine 12-hour or 24-hour autonomous run.

## Recommended repository action

The repository should be preserved substantially as produced so the original agent output remains inspectable.

This report should supplement, rather than silently replace, the generated project narrative.

Where the generated documents refer to Hour 2, Hour 6, Hour 12, or approximately 12 hours of work, a note should be added explaining that these were simulated development checkpoints and that the measured wall-clock duration was approximately 38 minutes.

The distinction is important for both technical honesty and future research.

## Recommended design for a future experiment

A future genuine 24-hour experiment should use an external orchestration process.

At intervals of approximately 10–15 minutes, the orchestrator should provide the agent with:

* the actual current time;
* elapsed wall-clock time;
* remaining time;
* current repository status;
* recent commit history;
* current diff;
* latest test results;
* resource and cost usage;
* the previous agent decision;
* a requirement to perform one bounded, meaningful work cycle.

Each invocation should then:

1. inspect the current state;
2. choose one justified task;
3. implement or investigate it;
4. run relevant validation;
5. update documentation;
6. create one meaningful commit;
7. record what should happen next.

This would provide evidence of genuine longitudinal autonomy rather than a compressed simulation of one.

## Final conclusion

The project did not follow the intended temporal structure, but it produced a much stronger result than would normally be expected from a 38-minute, $0.17 autonomous generation run.

The experiment therefore succeeded in demonstrating rapid autonomous project creation, while also revealing that elapsed-time instructions must be enforced externally.

PlainSpeak deserves to be tested.

The experiment deserves to be repeated with real orchestration.
