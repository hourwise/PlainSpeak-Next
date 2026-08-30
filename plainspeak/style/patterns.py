"""Observing repetition, cadence and habit across a whole document.

Each function here answers one question and returns findings with the arithmetic
attached. None of them decides anything about who wrote the text.

Three commitments run through the module.

**Repetition, not existence.** "Not only X but also Y" is ordinary English and a
document containing one is a document containing one. Every diagnostic here
measures how often something happens relative to how much text there is, and
says nothing about a single occurrence.

**Silence below the sample size.** A three-sentence paragraph where two
sentences start alike is arithmetic, not evidence. Every diagnostic declares the
smallest sample it will speak about and returns nothing beneath it.

**Evidence a reader can check.** Every finding names the thing — the repeated
opener, the overused word — and lists where to look. A reader who disagrees
should be able to go and see for themselves.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Callable, Iterable, Optional, Sequence

from .metrics import content_words, sentences_of, words
from .model import DocumentStructure, Evidence, Occurrence, ProseBlock, StyleFinding
from .policy import (
    CANNED_FRAMING,
    FLAGGED_VOCABULARY,
    FRAMING_PHRASES,
    LEXICAL_OVERLAP,
    LIST_DOMINANCE,
    MINIMUM_SAMPLES,
    NGRAM_MAX_RETAINED,
    NGRAM_MINIMUM_OCCURRENCES,
    NGRAM_SIZES,
    OPENER_SIZES,
    OVERLAP_CANDIDATE_TOKENS,
    OVERLAP_MAX_COMPARISONS,
    OVERLAP_MAX_PAIR_UPDATES,
    OVERLAP_MINIMUM_TOKENS,
    PARAGRAPH_UNIFORMITY,
    REPEATED_PARAGRAPH_OPENER,
    REPEATED_PHRASE,
    REPEATED_SENTENCE_OPENER,
    REPEATED_TRANSITION,
    RHETORICAL_PATTERNS,
    RHETORICAL_REPETITION,
    SENTENCE_UNIFORMITY,
    STOP_WORDS,
    SURFACE_TEMPLATES,
    THRESHOLDS,
    TRANSITION_DENSITY,
    TRANSITION_PHRASES,
    TRANSITIONS,
    TRIADIC_REPETITION,
    VOCABULARY_OVERUSE,
    severity_for,
)

#: How much of a sentence to quote in evidence.
EXCERPT = 72

_TRANSITION_RE = re.compile(
    r"\b(?:"
    + "|".join(sorted((re.escape(item) for item in TRANSITIONS), key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
_TRANSITION_PHRASE_RE = re.compile(
    r"\b(?:"
    + "|".join(sorted((re.escape(item) for item in TRANSITION_PHRASES), key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
_FRAMING_RE = re.compile(
    r"\b(?:"
    + "|".join(sorted((re.escape(item) for item in FRAMING_PHRASES), key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
_TRIAD_RE = re.compile(
    r"\b[\w'’-]+,\s+[\w'’-]+,?\s+and\s+[\w'’-]+\b", re.IGNORECASE
)
_RHETORICAL_RES = tuple(
    (name, re.compile(pattern, re.IGNORECASE)) for name, pattern in RHETORICAL_PATTERNS
)
_TEMPLATE_RES = tuple(
    (name, re.compile(pattern, re.IGNORECASE)) for name, pattern in SURFACE_TEMPLATES
)


def _excerpt(text: str) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= EXCERPT else collapsed[: EXCERPT - 1] + "…"


def _finding(
    diagnostic: str,
    category: str,
    value: float,
    sample_size: int,
    message: str,
    evidence: Sequence[Evidence],
) -> Optional[StyleFinding]:
    """Build a finding, or nothing when the measurement is unremarkable."""
    if sample_size < MINIMUM_SAMPLES[diagnostic]:
        return None
    severity = severity_for(diagnostic, value)
    if not severity:
        return None
    notice, strong = THRESHOLDS[diagnostic]
    return StyleFinding(
        id=diagnostic,
        category=category,
        severity=severity,
        message=message,
        value=value,
        threshold=strong if severity == "strong" else notice,
        sample_size=sample_size,
        evidence=tuple(evidence),
    )


# ── Uniformity ─────────────────────────────────────────────────────────────


def sentence_uniformity(text: str, metrics) -> Optional[StyleFinding]:
    """Sentence lengths that barely vary.

    17, 18, 17, 18, 17 reads as machinery in a way 7, 24, 13, 9, 31 does not,
    and the difference is measurable without knowing anything about the content.
    """
    sentences = sentences_of(text)
    variation = metrics.get("sentence_words_variation")
    lengths = [len(words(sentence)) for sentence in sentences]
    if not lengths:
        return None

    sample = ", ".join(str(length) for length in lengths[:12])
    evidence = [
        Evidence(
            label=f"lengths: {sample}" + ("…" if len(lengths) > 12 else ""),
            count=len(lengths),
            total=len(lengths),
        )
    ]
    return _finding(
        SENTENCE_UNIFORMITY,
        "cadence",
        variation,
        len(sentences),
        f"Sentence lengths vary little: mean {metrics.get('sentence_words_mean'):.1f} words, "
        f"variation {variation:.2f}.",
        evidence,
    )


def paragraph_uniformity(structure: DocumentStructure, metrics) -> Optional[StyleFinding]:
    paragraphs = structure.paragraphs
    variation = metrics.get("paragraph_words_variation")
    lengths = [len(words(block.text)) for block in paragraphs]
    if not lengths:
        return None

    evidence = [
        Evidence(
            label="lengths: " + ", ".join(str(length) for length in lengths[:12]),
            count=len(lengths),
            total=len(lengths),
        )
    ]
    return _finding(
        PARAGRAPH_UNIFORMITY,
        "cadence",
        variation,
        len(paragraphs),
        f"Paragraphs are of similar length: mean "
        f"{metrics.get('paragraph_words_mean'):.1f} words, variation {variation:.2f}.",
        evidence,
    )


# ── Repeated openers ───────────────────────────────────────────────────────


def _opener(text: str, size: int) -> str:
    """The first `size` words of a piece of text, normalised.

    Lower-cased and stripped of punctuation so that "The system," and "The
    system" are the same opener. Not stemmed: "provides" and "provide" are
    different openers, and pretending otherwise would be the guessing this
    project keeps refusing to do.
    """
    tokens = words(text)[:size]
    return " ".join(tokens) if len(tokens) == size else ""


def _repeated_opener(
    diagnostic: str,
    units: Sequence[tuple[str, str]],
    what: str,
) -> Optional[StyleFinding]:
    """The most repeated opener across a set of `(location, text)` units."""
    if not units:
        return None

    best: Optional[tuple[float, int, str, list[Occurrence]]] = None
    for size in OPENER_SIZES:
        openers = [(location, _opener(text, size), text) for location, text in units]
        counts = Counter(opener for _, opener, _ in openers if opener)
        if not counts:
            continue
        # Ties resolve on the opener text so two runs cannot disagree.
        label, count = min(
            ((word, number) for word, number in counts.items()),
            key=lambda pair: (-pair[1], pair[0]),
        )
        if count < 2:
            continue
        share = count / len(units)
        occurrences = [
            Occurrence(location=location, excerpt=_excerpt(text))
            for location, opener, text in openers
            if opener == label
        ]
        # A longer repeated opener is stronger evidence than a shorter one at
        # the same share: "The system provides" says more than "The".
        candidate = (share, size, label, occurrences)
        if best is None or (share, size) > (best[0], best[1]):
            best = candidate

    if best is None:
        return None

    share, size, label, occurrences = best
    return _finding(
        diagnostic,
        "repetition",
        share,
        len(units),
        f"{len(occurrences)} of {len(units)} {what} begin with “{label}”.",
        [Evidence(label=label, count=len(occurrences), total=len(units),
                  occurrences=tuple(occurrences[:10]))],
    )


def repeated_sentence_opener(text: str) -> Optional[StyleFinding]:
    sentences = sentences_of(text)
    units = [(f"sentence {index + 1}", sentence) for index, sentence in enumerate(sentences)]
    return _repeated_opener(REPEATED_SENTENCE_OPENER, units, "sentences")


def repeated_paragraph_opener(structure: DocumentStructure) -> Optional[StyleFinding]:
    units = [(block.location, block.text) for block in structure.paragraphs]
    return _repeated_opener(REPEATED_PARAGRAPH_OPENER, units, "paragraphs")


# ── Transitions ────────────────────────────────────────────────────────────


def _transition_hits(text: str) -> list[str]:
    found = [match.group(0).lower() for match in _TRANSITION_RE.finditer(text)]
    found += [
        " ".join(match.group(0).lower().split())
        for match in _TRANSITION_PHRASE_RE.finditer(text)
    ]
    return found


def transition_density(text: str) -> Optional[StyleFinding]:
    """How much of the prose is discourse scaffolding."""
    sentences = sentences_of(text)
    hits = _transition_hits(text)
    if not sentences:
        return None

    density = len(hits) / len(sentences)
    counts = Counter(hits)
    evidence = [
        Evidence(label=word, count=number, total=len(hits))
        for word, number in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
    ]
    return _finding(
        TRANSITION_DENSITY,
        "scaffolding",
        density,
        len(sentences),
        f"{len(hits)} transitions across {len(sentences)} sentences "
        f"({density:.2f} per sentence).",
        evidence,
    )


def repeated_transition(text: str, structure: DocumentStructure) -> Optional[StyleFinding]:
    """One transition doing all the work.

    Deliberately separate from density. Eight different transitions is a writer
    with a habit of signposting; the same transition eight times is a different
    observation, and collapsing them would lose the more interesting one.
    """
    hits = _transition_hits(text)
    if not hits:
        return None

    counts = Counter(hits)
    label, count = min(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    if count < 2:
        return None

    share = count / len(hits)
    pattern = re.compile(r"\b" + re.escape(label) + r"\b", re.IGNORECASE)
    occurrences = [
        Occurrence(location=block.location, excerpt=_excerpt(block.text))
        for block in structure.blocks
        if pattern.search(block.text)
    ]
    return _finding(
        REPEATED_TRANSITION,
        "repetition",
        share,
        len(hits),
        f"“{label}” accounts for {count} of {len(hits)} transitions.",
        [Evidence(label=label, count=count, total=len(hits),
                  occurrences=tuple(occurrences[:10]))],
    )


# ── Canned framing ─────────────────────────────────────────────────────────


def canned_framing(text: str, structure: DocumentStructure) -> Optional[StyleFinding]:
    """How often the document announces a statement rather than making it.

    Some of these phrases are also Phase 4 transformation rules, which detect
    each occurrence. This measures how often they occur across the document —
    a different level of evidence, and both are worth having.
    """
    hits = [" ".join(match.group(0).lower().split()) for match in _FRAMING_RE.finditer(text)]
    paragraphs = structure.paragraphs or structure.blocks
    if not hits or not paragraphs:
        return None

    density = len(hits) / len(paragraphs)
    counts = Counter(hits)
    occurrences = [
        Occurrence(location=block.location, excerpt=_excerpt(block.text))
        for block in structure.blocks
        if _FRAMING_RE.search(block.text)
    ]
    evidence = [
        Evidence(label=phrase, count=number, total=len(hits),
                 occurrences=tuple(occurrences[:6]))
        for phrase, number in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    ]
    return _finding(
        CANNED_FRAMING,
        "scaffolding",
        density,
        len(paragraphs),
        f"{len(hits)} framing phrases across {len(paragraphs)} paragraphs.",
        evidence,
    )


# ── Vocabulary ─────────────────────────────────────────────────────────────


def vocabulary_overuse(text: str) -> Optional[StyleFinding]:
    """A flagged word used unusually often.

    Not a claim that any of these words means anything about who wrote the text.
    "Robust" is a good word; eleven of them in two thousand is an observation.
    One occurrence never produces a finding.
    """
    all_words = words(text)
    if not all_words:
        return None

    counts = Counter(word for word in all_words if word in FLAGGED_VOCABULARY)
    if not counts:
        return None

    label, count = min(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    if count < 2:
        return None

    rate = count * 1000 / len(all_words)
    evidence = [
        Evidence(label=word, count=number, total=len(all_words))
        for word, number in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
    ]
    return _finding(
        VOCABULARY_OVERUSE,
        "repetition",
        rate,
        len(all_words),
        f"“{label}” appears {count} times in {len(all_words)} words "
        f"({rate:.1f} per 1,000).",
        evidence,
    )


# ── Rhetorical constructions ───────────────────────────────────────────────


def rhetorical_repetition(text: str) -> Optional[StyleFinding]:
    """A construction reused across the document.

    Every pattern here is ordinary English. The diagnostic is about a writer
    reaching for the same shape repeatedly, which is why a single occurrence
    produces nothing at all.
    """
    sentences = sentences_of(text)
    if not sentences:
        return None

    counts: Counter = Counter()
    examples: dict[str, list[Occurrence]] = defaultdict(list)
    for index, sentence in enumerate(sentences):
        for name, pattern in _RHETORICAL_RES:
            if pattern.search(sentence):
                counts[name] += 1
                examples[name].append(
                    Occurrence(location=f"sentence {index + 1}", excerpt=_excerpt(sentence))
                )

    if not counts:
        return None
    label, count = min(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    if count < 2:
        return None

    rate = count * 10 / len(sentences)
    evidence = [
        Evidence(label=name, count=number, total=len(sentences),
                 occurrences=tuple(examples[name][:6]))
        for name, number in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    ]
    return _finding(
        RHETORICAL_REPETITION,
        "rhetoric",
        rate,
        len(sentences),
        f"The “{label}” construction appears {count} times in {len(sentences)} sentences.",
        evidence,
    )


def triadic_repetition(text: str) -> Optional[StyleFinding]:
    """Three-item lists, used repeatedly.

    A three-item list is not a defect. A document that reaches for one in every
    third sentence has a habit, and that is the only claim made here. No attempt
    is made to parse nested lists.
    """
    sentences = sentences_of(text)
    if not sentences:
        return None

    occurrences = [
        Occurrence(location=f"sentence {index + 1}", excerpt=_excerpt(match.group(0)))
        for index, sentence in enumerate(sentences)
        for match in [_TRIAD_RE.search(sentence)]
        if match
    ]
    if len(occurrences) < 2:
        return None

    rate = len(occurrences) * 10 / len(sentences)
    return _finding(
        TRIADIC_REPETITION,
        "rhetoric",
        rate,
        len(sentences),
        f"{len(occurrences)} three-item lists across {len(sentences)} sentences.",
        [Evidence(label="X, Y and Z", count=len(occurrences), total=len(sentences),
                  occurrences=tuple(occurrences[:8]))],
    )


# ── Repeated phrases ───────────────────────────────────────────────────────


def repeated_phrase(text: str) -> Optional[StyleFinding]:
    """The same phrase, several times over.

    Phrases never cross a sentence boundary — a "phrase" spanning a full stop is
    an artefact of counting, not something an author wrote. Phrases made only of
    stop words are dropped, because "of the" recurring is a fact about English.

    Memory is bounded by the policy: three phrase lengths, a minimum occurrence
    count, and a cap on how many candidates are retained.
    """
    sentences = sentences_of(text)
    total_words = len(words(text))
    if not sentences or not total_words:
        return None

    counts: Counter = Counter()
    locations: dict[str, list[Occurrence]] = defaultdict(list)

    for index, sentence in enumerate(sentences):
        tokens = words(sentence)
        for size in NGRAM_SIZES:
            for start in range(len(tokens) - size + 1):
                gram = tokens[start : start + size]
                if all(token in STOP_WORDS for token in gram):
                    continue
                phrase = " ".join(gram)
                counts[phrase] += 1
                if len(locations[phrase]) < 8:
                    locations[phrase].append(
                        Occurrence(location=f"sentence {index + 1}", excerpt=_excerpt(sentence))
                    )

    repeated = [
        (phrase, count)
        for phrase, count in counts.items()
        if count >= NGRAM_MINIMUM_OCCURRENCES
    ]
    if not repeated:
        return None

    # Longest-then-most-frequent, so "it is important to note" is reported
    # rather than the "it is important" inside it.
    repeated.sort(key=lambda pair: (-len(pair[0].split()), -pair[1], pair[0]))
    repeated = repeated[:NGRAM_MAX_RETAINED]

    label, count = max(repeated, key=lambda pair: (pair[1], len(pair[0].split()), pair[0]))
    rate = count * 100 / total_words
    evidence = [
        Evidence(label=phrase, count=number, total=total_words,
                 occurrences=tuple(locations[phrase][:6]))
        for phrase, number in repeated[:6]
    ]
    return _finding(
        REPEATED_PHRASE,
        "repetition",
        rate,
        len(sentences),
        f"“{label}” appears {count} times.",
        evidence,
    )


# ── Lexical overlap ────────────────────────────────────────────────────────


def shared_token_counts(
    paragraphs: Sequence[frozenset], budget: int = OVERLAP_MAX_PAIR_UPDATES
) -> tuple[Counter, int]:
    """How many content tokens each pair of paragraphs shares, within a budget.

    Returns the pair counts and the number of pair updates actually performed,
    so the bound can be asserted by counting work rather than by timing it. A
    test that measures seconds goes flaky on a loaded machine; a test that
    measures updates does not.

    The naive version of this was quadratic and looked bounded. It skipped
    tokens appearing in more than half the paragraphs, capped the number of
    scored comparisons at `OVERLAP_MAX_COMPARISONS`, and still built the whole
    candidate set first — so the cap bounded the cheap half and measured pair
    counts grew as 3n² in paragraphs. 160 paragraphs produced 76,240 pairs;
    5,000 would have produced 75 million.

    Two things make stopping safe. Tokens are visited rarest first, so the work
    that is dropped is the least informative available: a token in two
    paragraphs says those two are related, and one in a third of them says
    almost nothing. And the order is total — frequency, then the token itself —
    so the result never depends on dictionary iteration order.

    Exhausting the budget makes the diagnostic go quiet rather than wrong. On a
    document of several thousand near-identical paragraphs it will stop
    reporting overlap; that is the intended failure direction, and it is
    recorded in STYLE_CALIBRATION.md rather than hidden.
    """
    index: dict[str, list[int]] = defaultdict(list)
    for position, tokens in enumerate(paragraphs):
        for token in tokens:
            index[token].append(position)

    # A token appearing in more than half the paragraphs tells us nothing and
    # would dominate the candidate set.
    spread = max(2, len(paragraphs) // 2)
    ordered = sorted(index.items(), key=lambda item: (len(item[1]), item[0]))

    shared: Counter = Counter()
    updates = 0
    for _, positions in ordered:
        if len(positions) > spread:
            continue
        # Rarest first, so once one token costs more than the budget has left,
        # every token after it costs at least as much: stopping is correct as
        # well as cheaper than skipping.
        pairs = len(positions) * (len(positions) - 1) // 2
        if updates + pairs > budget:
            break
        updates += pairs
        for i, left in enumerate(positions):
            for right in positions[i + 1 :]:
                shared[(left, right)] += 1

    return shared, updates


def lexical_overlap(structure: DocumentStructure) -> Optional[StyleFinding]:
    """Two paragraphs sharing most of their content words.

    Deliberately called *lexical overlap* and nothing else. This measures shared
    tokens; it does not know what either paragraph means, and saying "paragraph
    11 repeats the meaning of paragraph 4" would be a claim the method cannot
    support. What it can say is that they share 82% of their content words,
    which a reader can verify by looking.

    Comparison is filtered through an inverted index rather than run over all
    pairs: a long report has hundreds of paragraphs, and all-pairs is quadratic
    for a diagnostic that only cares about the strongest few. The bounded part
    is `shared_token_counts`, which is where the work actually is.
    """
    paragraphs = [
        (block, frozenset(content_words(block.text)))
        for block in structure.paragraphs
        if len(content_words(block.text)) >= OVERLAP_MINIMUM_TOKENS
    ]
    if len(paragraphs) < 2:
        return None

    shared, _ = shared_token_counts([tokens for _, tokens in paragraphs])

    candidates = [
        pair for pair, count in shared.items() if count >= OVERLAP_CANDIDATE_TOKENS
    ]
    candidates.sort()
    candidates = candidates[:OVERLAP_MAX_COMPARISONS]

    best: Optional[tuple[float, ProseBlock, ProseBlock]] = None
    for left, right in candidates:
        left_block, left_tokens = paragraphs[left]
        right_block, right_tokens = paragraphs[right]
        union = left_tokens | right_tokens
        if not union:
            continue
        score = len(left_tokens & right_tokens) / len(union)
        if best is None or score > best[0]:
            best = (score, left_block, right_block)

    if best is None:
        return None

    score, left_block, right_block = best
    return _finding(
        LEXICAL_OVERLAP,
        "repetition",
        score,
        len(structure.paragraphs),
        f"{left_block.location} and {right_block.location} share "
        f"{score * 100:.0f}% of their content words.",
        [
            Evidence(
                label=f"{left_block.location} / {right_block.location}",
                count=1,
                total=len(paragraphs),
                occurrences=(
                    Occurrence(location=left_block.location, excerpt=_excerpt(left_block.text)),
                    Occurrence(location=right_block.location, excerpt=_excerpt(right_block.text)),
                ),
            )
        ],
    )


# ── Structure ──────────────────────────────────────────────────────────────


def list_dominance(structure: DocumentStructure) -> Optional[StyleFinding]:
    """A document that is mostly bullet points.

    Worth surfacing and not worth moralising about. Some documents should be
    lists. The observation is that this one is, which a writer may or may not
    have intended.
    """
    blocks = structure.blocks
    items = structure.list_items
    if not blocks:
        return None

    share = len(items) / len(blocks)
    return _finding(
        LIST_DOMINANCE,
        "structure",
        share,
        len(blocks),
        f"{len(items)} of {len(blocks)} prose blocks are list items.",
        [Evidence(label="list items", count=len(items), total=len(blocks),
                  occurrences=tuple(
                      Occurrence(location=block.location, excerpt=_excerpt(block.text))
                      for block in items[:6]
                  ))],
    )


# ── Surface templates ──────────────────────────────────────────────────────


def surface_template_counts(text: str) -> dict[str, int]:
    """How often each sentence-opening template appears.

    Called *surface* templates because that is what they are: lexical patterns,
    not grammar. Recognising "The system provides" does not mean the engine has
    parsed a subject and a verb, and naming them honestly keeps anyone from
    assuming it has.
    """
    counts: dict[str, int] = {name: 0 for name, _ in _TEMPLATE_RES}
    for sentence in sentences_of(text):
        normalised = " ".join(sentence.split()).lower()
        for name, pattern in _TEMPLATE_RES:
            if pattern.search(normalised):
                counts[name] += 1
    return counts
