"""Measuring a document. No opinions, only arithmetic.

Everything here is neutral: a count, a mean, a rate. Nothing in this module
decides whether a number is good or bad — that is `policy`'s job, and keeping
the two apart means a threshold can be argued about without touching the
measurement it applies to.

Sentence segmentation comes from `plainspeak.core.tokenize`, the same splitter
the analyser and the rule engine use. A second implementation here would drift
from that one, and the first symptom would be a style report that disagreed with
a lexical finding about how many sentences a document has.
"""
from __future__ import annotations

import re
import statistics
from functools import lru_cache
from typing import Iterable, Sequence

from ..core.tokenize import split_sentences
from .model import DocumentStructure, StyleMetrics
from .policy import CONTRACTIONS, PRONOUNS, PUNCTUATION, STOP_WORDS

#: A word, for counting purposes: letters, with internal apostrophes and hyphens
#: kept so "can't" and "well-known" are one token each.
WORD = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")

_CONTRACTION_RE = re.compile(
    r"\b(?:" + "|".join(sorted((re.escape(item) for item in CONTRACTIONS), key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)


#: Both tokenisers are memoised because a dozen diagnostics ask for the same
#: split of the same text, and re-segmenting a long report once per question
#: dominated everything else.
#:
#: Sized for paragraphs, not documents. The first attempt used a cache of eight,
#: which held the document but thrashed on the per-paragraph calls and came out
#: slower than no cache at all. Both functions are pure, so this changes nothing
#: but the time.
_CACHE_SIZE = 2048


@lru_cache(maxsize=_CACHE_SIZE)
def _tokenise(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower().replace("’", "'") for match in WORD.finditer(text))


def words(text: str) -> list[str]:
    """Every word in the text, lower-cased, apostrophes normalised.

    The curly apostrophe is folded to the straight one so "don't" and "don’t"
    are the same contraction. Nothing else about the token is changed — there is
    no stemming here, deliberately.
    """
    return list(_tokenise(text))


def content_words(text: str) -> list[str]:
    """Words with the stop list removed, for concentration statistics."""
    return [word for word in words(text) if word not in STOP_WORDS]


@lru_cache(maxsize=_CACHE_SIZE)
def _segment(text: str) -> tuple[str, ...]:
    return tuple(sentence for sentence in split_sentences(text) if sentence.strip())


def sentences_of(text: str) -> list[str]:
    """The project's sentence segmentation, with empties dropped."""
    return list(_segment(text))


def _dispersion(values: Sequence[float]) -> tuple[float, float]:
    """`(standard deviation, coefficient of variation)`.

    The coefficient of variation — deviation over mean — is what the uniformity
    diagnostics use, because it is scale-free: a document of long sentences and
    one of short sentences can be compared for *variety* without the comparison
    being dominated by their average length.
    """
    if len(values) < 2:
        return 0.0, 0.0
    mean = statistics.fmean(values)
    if mean == 0:
        return 0.0, 0.0
    deviation = statistics.pstdev(values)
    return deviation, deviation / mean


def measure(text: str, structure: DocumentStructure) -> StyleMetrics:
    """Every metric the style layer computes, as one flat mapping."""
    values: dict[str, float] = {}

    sentences = sentences_of(text)
    all_words = words(text)
    total_words = len(all_words)

    values["word_count"] = total_words
    values["sentence_count"] = len(sentences)

    _sentence_metrics(sentences, values)
    _paragraph_metrics(structure, values)
    _punctuation_metrics(text, total_words, values)
    _lexical_metrics(text, all_words, total_words, values)
    _structural_metrics(structure, values)
    _question_metrics(sentences, values)

    return StyleMetrics(values=values)


def _sentence_metrics(sentences: Sequence[str], values: dict[str, float]) -> None:
    lengths = [len(words(sentence)) for sentence in sentences]
    if not lengths:
        return

    deviation, variation = _dispersion(lengths)
    values["sentence_words_mean"] = statistics.fmean(lengths)
    values["sentence_words_median"] = statistics.median(lengths)
    values["sentence_words_min"] = min(lengths)
    values["sentence_words_max"] = max(lengths)
    values["sentence_words_stddev"] = deviation
    values["sentence_words_variation"] = variation
    # "Short" and "long" are stated in absolute words rather than relative to
    # this document, so the rate means the same thing across two documents.
    values["short_sentence_rate"] = sum(1 for n in lengths if n <= 8) / len(lengths)
    values["long_sentence_rate"] = sum(1 for n in lengths if n >= 30) / len(lengths)


def _paragraph_metrics(structure: DocumentStructure, values: dict[str, float]) -> None:
    paragraphs = structure.paragraphs
    values["paragraph_count"] = len(paragraphs)
    if not paragraphs:
        return

    word_counts = [len(words(block.text)) for block in paragraphs]
    sentence_counts = [len(sentences_of(block.text)) for block in paragraphs]

    word_deviation, word_variation = _dispersion(word_counts)
    values["paragraph_words_mean"] = statistics.fmean(word_counts)
    values["paragraph_words_median"] = statistics.median(word_counts)
    values["paragraph_words_stddev"] = word_deviation
    values["paragraph_words_variation"] = word_variation

    sentence_deviation, sentence_variation = _dispersion(sentence_counts)
    values["paragraph_sentences_mean"] = statistics.fmean(sentence_counts)
    values["paragraph_sentences_stddev"] = sentence_deviation
    values["paragraph_sentences_variation"] = sentence_variation


def _punctuation_metrics(text: str, total_words: int, values: dict[str, float]) -> None:
    """Counts and rates per 1,000 words.

    No punctuation mark is treated as bad here. An em dash is a punctuation
    mark; the persistent claim that its presence indicates a machine wrote the
    text is folklore, and this layer reports the rate so that a future profile
    can care about distribution rather than presence.
    """
    for name, character in PUNCTUATION.items():
        count = text.count(character)
        values[f"punctuation_{name}"] = count
        values[f"punctuation_{name}_per_1000"] = _per_thousand(count, total_words)


def _lexical_metrics(
    text: str, all_words: Sequence[str], total_words: int, values: dict[str, float]
) -> None:
    contractions = len(_CONTRACTION_RE.findall(text))
    values["contraction_count"] = contractions
    values["contraction_per_1000"] = _per_thousand(contractions, total_words)

    counts = {word: 0 for word in all_words}
    for word in all_words:
        counts[word] += 1

    for family, members in PRONOUNS.items():
        count = sum(counts.get(member, 0) for member in members)
        values[f"pronoun_{family}"] = count
        values[f"pronoun_{family}_per_1000"] = _per_thousand(count, total_words)

    content = [word for word in all_words if word not in STOP_WORDS]
    values["content_word_count"] = len(content)
    values["distinct_content_words"] = len(set(content))
    # Type-token ratio over content words. A low value means the same handful of
    # words doing all the work, which is worth seeing next to the repetition
    # diagnostics.
    values["content_word_diversity"] = (
        len(set(content)) / len(content) if content else 0.0
    )


def _structural_metrics(structure: DocumentStructure, values: dict[str, float]) -> None:
    blocks = structure.blocks
    headings = structure.headings
    items = structure.list_items

    values["block_count"] = len(blocks)
    values["heading_count"] = len(headings)
    values["list_block_count"] = structure.list_blocks
    values["list_item_count"] = len(items)
    values["code_block_count"] = structure.code_blocks
    values["table_count"] = structure.tables

    total_words = sum(len(words(block.text)) for block in blocks)
    if total_words:
        values["words_per_heading"] = total_words / len(headings) if headings else float(total_words)
        values["list_word_share"] = sum(len(words(block.text)) for block in items) / total_words

    if blocks:
        values["list_block_share"] = len(items) / len(blocks)

    if items:
        values["list_item_words_mean"] = statistics.fmean(
            [len(words(block.text)) for block in items]
        )

    for level in range(1, 7):
        count = sum(1 for block in headings if block.level == level)
        if count:
            values[f"heading_level_{level}"] = count


def _question_metrics(sentences: Sequence[str], values: dict[str, float]) -> None:
    questions = sum(1 for sentence in sentences if sentence.rstrip().endswith("?"))
    values["question_count"] = questions
    values["questions_per_100_sentences"] = (
        questions * 100 / len(sentences) if sentences else 0.0
    )


def _per_thousand(count: int, total_words: int) -> float:
    return count * 1000 / total_words if total_words else 0.0
