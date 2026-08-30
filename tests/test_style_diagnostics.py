"""Metrics and pattern diagnostics.

Two halves, and the second half is the one that matters. Detecting repetition is
easy; anyone can write something that fires. The work is in *not* firing on
ordinary prose, so every diagnostic here is tested with a control that must stay
quiet, and every one is tested below its minimum sample size where it must say
nothing at all.
"""
from __future__ import annotations

import pytest

from plainspeak.style import (
    DocumentStructure,
    MINIMUM_SAMPLES,
    ProseBlock,
    analyze,
)
from plainspeak.style import patterns, policy
from plainspeak.style.metrics import content_words, measure, sentences_of, words


def blocks(*texts: str, kind: str = "paragraph") -> DocumentStructure:
    return DocumentStructure(
        blocks=tuple(
            ProseBlock(kind=kind, text=text, index=index, path=(index,))
            for index, text in enumerate(texts)
        )
    )


def ids_of(text: str, structure: DocumentStructure | None = None) -> set[str]:
    return {finding.id for finding in analyze(text, structure).findings}


def finding(text: str, diagnostic: str, structure: DocumentStructure | None = None):
    for item in analyze(text, structure).findings:
        if item.id == diagnostic:
            return item
    return None


# ── Tokenising ─────────────────────────────────────────────────────────────


def test_words_keeps_contractions_and_hyphens_whole() -> None:
    assert words("It can't be a well-known fact.") == [
        "it", "can't", "be", "a", "well-known", "fact"
    ]


def test_words_folds_the_curly_apostrophe() -> None:
    """"don't" and "don’t" are the same contraction."""
    assert words("don’t") == words("don't") == ["don't"]


def test_content_words_drop_the_stop_list() -> None:
    assert content_words("The system is a robust platform") == ["system", "robust", "platform"]


def test_sentences_come_from_the_project_splitter() -> None:
    from plainspeak.core.tokenize import split_sentences

    text = "One sentence here. And a second one. A third?"
    assert sentences_of(text) == [s for s in split_sentences(text) if s.strip()]


# ── Sentence and paragraph metrics ─────────────────────────────────────────


def test_sentence_statistics() -> None:
    text = "One two three. One two three four five six. One two."
    metrics = measure(text, DocumentStructure())

    assert metrics.get("sentence_count") == 3
    assert metrics.get("sentence_words_min") == 2
    assert metrics.get("sentence_words_max") == 6
    assert metrics.get("sentence_words_mean") == pytest.approx(11 / 3)
    assert metrics.get("sentence_words_variation") > 0


def test_uniform_sentences_have_near_zero_variation() -> None:
    text = " ".join(["One two three four five."] * 6)
    assert measure(text, DocumentStructure()).get("sentence_words_variation") == 0.0


def test_paragraph_statistics() -> None:
    structure = blocks("One two three.", "One two three four five six seven eight.")
    metrics = measure("One two three. One two three four five six seven eight.", structure)

    assert metrics.get("paragraph_count") == 2
    assert metrics.get("paragraph_words_mean") == pytest.approx(5.5)
    assert metrics.get("paragraph_words_variation") > 0


# ── Punctuation, contractions, pronouns, questions ─────────────────────────


def test_punctuation_counts_and_rates() -> None:
    text = "A dash — here; a colon: and (a bracket). Really? Yes!"
    metrics = measure(text, DocumentStructure())

    assert metrics.get("punctuation_em_dash") == 1
    assert metrics.get("punctuation_semicolon") == 1
    assert metrics.get("punctuation_colon") == 1
    assert metrics.get("punctuation_open_parenthesis") == 1
    assert metrics.get("punctuation_question_mark") == 1
    assert metrics.get("punctuation_exclamation_mark") == 1
    assert metrics.get("punctuation_em_dash_per_1000") > 0


def test_an_em_dash_is_not_treated_as_a_defect() -> None:
    """It is a punctuation mark. The folklore about it is folklore."""
    text = "A dash — here and another — there. " * 5
    assert not ids_of(text)


def test_contraction_counts() -> None:
    metrics = measure("We can't go. It's fine. They don't mind.", DocumentStructure())
    assert metrics.get("contraction_count") == 3
    assert metrics.get("contraction_per_1000") > 0


def test_pronoun_families_are_counted_separately() -> None:
    metrics = measure("I asked you, and we told them.", DocumentStructure())
    assert metrics.get("pronoun_first_singular") == 1
    assert metrics.get("pronoun_first_plural") == 1
    assert metrics.get("pronoun_second") == 1
    assert metrics.get("pronoun_third") == 1


def test_question_frequency() -> None:
    metrics = measure("Is this a question? Yes it is. What about this?", DocumentStructure())
    assert metrics.get("question_count") == 2
    assert metrics.get("questions_per_100_sentences") == pytest.approx(200 / 3)


# ── Structural metrics ─────────────────────────────────────────────────────


def test_heading_and_list_metrics_come_from_structure() -> None:
    structure = DocumentStructure(
        blocks=(
            ProseBlock(kind="heading", text="A heading", index=0, path=(0,), level=1),
            ProseBlock(kind="paragraph", text="Some prose here.", index=1, path=(1,)),
            ProseBlock(kind="list_item", text="First item", index=2, path=(2,)),
            ProseBlock(kind="list_item", text="Second item", index=3, path=(3,)),
        ),
        list_blocks=1,
        code_blocks=2,
        tables=1,
    )
    metrics = measure("A heading Some prose here. First item Second item", structure)

    assert metrics.get("heading_count") == 1
    assert metrics.get("heading_level_1") == 1
    assert metrics.get("list_item_count") == 2
    assert metrics.get("list_block_count") == 1
    assert metrics.get("code_block_count") == 2
    assert metrics.get("table_count") == 1
    assert metrics.get("list_block_share") == pytest.approx(0.5)


# ── Repeated openers ───────────────────────────────────────────────────────


def test_a_repeated_sentence_opener_is_found() -> None:
    text = (
        "The system provides access. The system enables sharing. "
        "The system ensures accuracy. The system supports scaling. "
        "Reports run overnight. Data is retained for a year."
    )
    found = finding(text, policy.REPEATED_SENTENCE_OPENER)

    assert found is not None
    assert found.evidence[0].label == "the system"
    assert found.evidence[0].count == 4
    assert "4 of 6" in found.message
    assert found.evidence[0].occurrences


def test_a_one_token_opener_is_found() -> None:
    text = (
        "Applications close on Friday. Applications must be complete. "
        "Applications arrive by post. Applications are logged on receipt. "
        "Staff review them weekly. Decisions follow within a month."
    )
    found = finding(text, policy.REPEATED_SENTENCE_OPENER)
    assert found is not None
    assert found.evidence[0].label.startswith("applications")


def test_openers_ignore_punctuation_and_capitalisation() -> None:
    """"The system," and "The system —" are the same opening."""
    text = (
        "The system, which is new, works. The system works well. "
        "The system — updated — works. The system works reliably. "
        "Other things happen too. Nothing else is relevant. "
        "Reports run overnight."
    )
    found = finding(text, policy.REPEATED_SENTENCE_OPENER)
    assert found is not None
    assert found.evidence[0].label == "the system"
    assert found.evidence[0].count == 4


def test_varied_openers_produce_nothing() -> None:
    text = (
        "Applications close on Friday. We review them weekly. "
        "Staff record each decision. Letters go out the same day. "
        "Anyone may ask for a review. Nothing else changes."
    )
    assert policy.REPEATED_SENTENCE_OPENER not in ids_of(text)


def test_a_repeated_paragraph_opener_is_found() -> None:
    structure = blocks(
        "Furthermore, the fee is due.",
        "Furthermore, the form must be signed.",
        "Furthermore, evidence is required.",
        "The panel meets in June.",
    )
    text = " ".join(block.text for block in structure.blocks)
    found = finding(text, policy.REPEATED_PARAGRAPH_OPENER, structure)

    assert found is not None
    assert found.evidence[0].count == 3


# ── Transitions ────────────────────────────────────────────────────────────


def test_transition_density_is_measured() -> None:
    text = (
        "Furthermore, the fee applies. Moreover, it is due in March. "
        "However, exemptions exist. Therefore, check the rules. "
        "Additionally, evidence is needed. Consequently, allow time. "
        "Nevertheless, most people qualify. Ultimately, the panel decides."
    )
    found = finding(text, policy.TRANSITION_DENSITY)
    assert found is not None
    assert found.value >= policy.THRESHOLDS[policy.TRANSITION_DENSITY][0]


def test_one_transition_used_repeatedly_is_a_separate_finding() -> None:
    """Eight different transitions is not the same pattern as one used eight times."""
    varied = (
        "Furthermore, one. Moreover, two. However, three. Therefore, four. "
        "Additionally, five. Consequently, six. Likewise, seven. Similarly, eight."
    )
    repeated = (
        "Furthermore, one. Furthermore, two. Furthermore, three. Furthermore, four. "
        "Furthermore, five. Furthermore, six. Furthermore, seven. Furthermore, eight."
    )

    assert policy.REPEATED_TRANSITION not in ids_of(varied)
    assert policy.REPEATED_TRANSITION in ids_of(repeated)
    # Both are dense; only one is repetitive.
    assert policy.TRANSITION_DENSITY in ids_of(varied)


def test_sparse_transitions_produce_nothing() -> None:
    text = (
        "The fee applies from March. Exemptions exist for some households. "
        "However, you must apply in writing. Staff check each claim. "
        "Letters go out within ten days. You may ask for a review. "
        "Reviews take a further month. The panel meets quarterly."
    )
    assert policy.TRANSITION_DENSITY not in ids_of(text)


# ── Canned framing ─────────────────────────────────────────────────────────


def test_clustered_framing_is_found() -> None:
    structure = blocks(
        "It is important to note that the fee applies.",
        "It is worth noting that exemptions exist.",
        "It should be noted that evidence is required.",
        "The panel meets in June.",
    )
    text = " ".join(block.text for block in structure.blocks)
    found = finding(text, policy.CANNED_FRAMING, structure)

    assert found is not None
    assert found.value == pytest.approx(0.75)


def test_isolated_framing_produces_nothing() -> None:
    structure = blocks(
        "It is important to note that the fee applies.",
        "The form must be signed and dated before it is sent.",
        "Evidence must accompany the application in every case.",
        "The panel meets in June and again in December.",
        "Decisions are published on the register within a week.",
    )
    text = " ".join(block.text for block in structure.blocks)
    assert policy.CANNED_FRAMING not in ids_of(text, structure)


# ── Vocabulary ─────────────────────────────────────────────────────────────


def test_one_occurrence_never_triggers_vocabulary_overuse() -> None:
    """"Robust" is a good word. Using it once is using a word."""
    filler = "Everything else here is ordinary prose with no flagged vocabulary. " * 40
    text = "The platform is robust. " + filler
    assert measure(text, DocumentStructure()).get("word_count") > 200
    assert policy.VOCABULARY_OVERUSE not in ids_of(text)


def test_clustered_vocabulary_is_found() -> None:
    text = (
        "The robust platform is robust in every respect. Our robust approach "
        "delivers robust outcomes through robust engineering and robust design. "
    ) + ("Ordinary filler prose continues here for a while longer. " * 30)
    found = finding(text, policy.VOCABULARY_OVERUSE)

    assert found is not None
    assert found.evidence[0].label == "robust"
    assert found.evidence[0].count == 6


def test_vocabulary_matching_respects_word_boundaries() -> None:
    """"Robustness" is a different word from "robust"."""
    text = ("The robustness of the design is discussed. " * 10
            + "Ordinary prose continues here at some length. " * 30)
    assert measure(text, DocumentStructure()).get("word_count") > 200
    assert policy.VOCABULARY_OVERUSE not in ids_of(text)


# ── Rhetorical constructions ───────────────────────────────────────────────


def test_a_single_rhetorical_construction_produces_nothing() -> None:
    text = (
        "It is not only faster but also cheaper. The team reviewed the change. "
        "Testing continued for a week. Nothing else was affected. "
        "The release went out on Friday. No issues were reported."
    )
    assert policy.RHETORICAL_REPETITION not in ids_of(text)


def test_a_repeated_rhetorical_construction_is_found() -> None:
    text = (
        "It is not only faster but also cheaper. The change is not only simple "
        "but also safe. The result is not only clear but also short. "
        "It is not only useful but also correct. We reviewed it twice. "
        "Nothing else changed."
    )
    found = finding(text, policy.RHETORICAL_REPETITION)
    assert found is not None
    assert found.evidence[0].label == "not-only-but-also"


def test_a_single_triad_produces_nothing() -> None:
    text = (
        "We reviewed the design, the code and the tests. Work continued. "
        "The release went out on Friday. Nothing was reported. "
        "Staff were told on Monday. The log was archived."
    )
    assert policy.TRIADIC_REPETITION not in ids_of(text)


def test_repeated_triads_are_found() -> None:
    text = (
        "We reviewed the design, the code and the tests. It is fast, cheap and "
        "simple. The plan is clear, short and complete. Staff are trained, "
        "supported and paid. Work continued. Nothing else changed."
    )
    assert policy.TRIADIC_REPETITION in ids_of(text)


# ── Repeated phrases ───────────────────────────────────────────────────────


def test_a_repeated_phrase_is_found() -> None:
    text = (
        "The system provides access to records. The system provides access to "
        "reports. The system provides access to logs. Users sign in once. "
        "Sessions expire after an hour. Nothing is cached. Data is retained "
        "for a year. Reports run overnight."
    )
    found = finding(text, policy.REPEATED_PHRASE)
    assert found is not None
    assert "the system provides" in found.evidence[0].label


def test_stop_word_only_phrases_are_ignored() -> None:
    """"Of the" recurring is a fact about English, not about this document."""
    text = (
        "Some of the work was done. Most of the team agreed. Part of the plan "
        "changed. All of the tests passed. None of the risks materialised. "
        "Half of the budget remains. One of the servers failed. Two of the "
        "reports were late."
    )
    found = finding(text, policy.REPEATED_PHRASE)
    if found is not None:
        for evidence in found.evidence:
            assert not all(word in policy.STOP_WORDS for word in evidence.label.split())


def test_phrases_never_cross_a_sentence_boundary() -> None:
    """A phrase spanning a full stop is an artefact of counting."""
    text = " ".join(["Alpha beta. Gamma delta."] * 8)
    found = finding(text, policy.REPEATED_PHRASE)
    if found is not None:
        for evidence in found.evidence:
            assert "beta gamma" not in evidence.label


# ── Lexical overlap ────────────────────────────────────────────────────────


LONG_A = (
    "The service handled forty thousand enquiries during the year. Most arrived "
    "by telephone, although the proportion arriving online continued to grow "
    "steadily throughout every quarter of the reporting period."
)
LONG_B = (
    "Funding was confirmed for a further two years in the autumn, which allowed "
    "the team to recruit into two vacant posts that had been held open since "
    "the previous spring without any replacement being appointed."
)


def test_near_identical_paragraphs_are_reported_as_lexical_overlap() -> None:
    structure = blocks(LONG_A, LONG_B, LONG_A, LONG_B)
    text = " ".join(block.text for block in structure.blocks)
    found = finding(text, policy.LEXICAL_OVERLAP, structure)

    assert found is not None
    assert found.value > policy.THRESHOLDS[policy.LEXICAL_OVERLAP][0]


def test_the_finding_never_claims_the_paragraphs_mean_the_same_thing() -> None:
    """The method measures shared tokens. It cannot speak about meaning."""
    structure = blocks(LONG_A, LONG_B, LONG_A, LONG_B)
    text = " ".join(block.text for block in structure.blocks)
    found = finding(text, policy.LEXICAL_OVERLAP, structure)

    assert "content words" in found.message
    for word in ("meaning", "semantic", "equivalent", "duplicate", "same thing"):
        assert word not in found.message.lower()


def test_unrelated_paragraphs_produce_no_overlap_finding() -> None:
    structure = blocks(
        LONG_A,
        LONG_B,
        "Training was delivered to every member of the assessment team across "
        "four sessions covering the revised eligibility rules and the recording "
        "system introduced in January.",
        "A new telephone system was installed during the second quarter and "
        "early indications suggest it has reduced the number of abandoned calls "
        "considerably since then.",
    )
    text = " ".join(block.text for block in structure.blocks)
    assert policy.LEXICAL_OVERLAP not in ids_of(text, structure)


def test_short_paragraphs_are_never_compared() -> None:
    """Two six-word paragraphs sharing four words is arithmetic."""
    structure = blocks("The fee is due.", "The fee is due.", "The fee is due.", "The fee is due.")
    text = " ".join(block.text for block in structure.blocks)
    assert policy.LEXICAL_OVERLAP not in ids_of(text, structure)


# ── Structure ──────────────────────────────────────────────────────────────


def test_a_mostly_list_document_is_reported() -> None:
    structure = DocumentStructure(
        blocks=tuple(
            [ProseBlock(kind="paragraph", text="Before deploying:", index=0, path=(0,))]
            + [
                ProseBlock(kind="list_item", text=f"Check item number {n}", index=n, path=(n,))
                for n in range(1, 8)
            ]
        ),
        list_blocks=1,
    )
    text = " ".join(block.text for block in structure.blocks)
    found = finding(text, policy.LIST_DOMINANCE, structure)

    assert found is not None
    assert found.value == pytest.approx(7 / 8)


def test_a_document_with_a_few_lists_is_not_reported() -> None:
    structure = DocumentStructure(
        blocks=tuple(
            [
                ProseBlock(kind="paragraph", text=f"A paragraph of prose number {n}.",
                           index=n, path=(n,))
                for n in range(6)
            ]
            + [ProseBlock(kind="list_item", text="One item", index=6, path=(6,))]
        ),
        list_blocks=1,
    )
    text = " ".join(block.text for block in structure.blocks)
    assert policy.LIST_DOMINANCE not in ids_of(text, structure)


# ── Minimum sample sizes ───────────────────────────────────────────────────


def test_a_short_document_produces_nothing_at_all() -> None:
    """Silence is the right output when there is not enough text to judge."""
    structure = blocks("The office is closed on Monday.", "We reopen on Tuesday.")
    assert analyze("The office is closed on Monday. We reopen on Tuesday.", structure).findings == ()


def test_two_similar_sentences_are_not_a_repeated_opener() -> None:
    """Below the minimum sample, however uniform the text looks."""
    text = "The system works. The system runs."
    assert policy.REPEATED_SENTENCE_OPENER not in ids_of(text)


def test_uniformity_needs_enough_sentences() -> None:
    """Three identical-length sentences prove nothing."""
    text = "One two three four. Five six seven eight. Nine ten eleven twelve."
    assert policy.SENTENCE_UNIFORMITY not in ids_of(text)
    assert MINIMUM_SAMPLES[policy.SENTENCE_UNIFORMITY] > 3


def test_paragraph_uniformity_needs_enough_paragraphs() -> None:
    structure = blocks(*["A paragraph with exactly seven words here." for _ in range(4)])
    text = " ".join(block.text for block in structure.blocks)
    assert policy.PARAGRAPH_UNIFORMITY not in ids_of(text, structure)


def test_an_empty_document_is_handled() -> None:
    analysis = analyze("")
    assert analysis.findings == ()
    assert analysis.metrics.get("word_count") == 0
