"""Deterministic capture of PlainSpeak's current observable behaviour.

This module exists to freeze what the inherited engine *does* — not what it
*should* do — so that the refactoring work in later phases cannot silently
change established behaviour. Nothing here asserts that the captured output is
correct. Several captured values are known to be crude or wrong; they are
sealed anyway, and changing them is meant to be a deliberate, reviewed act.

Everything captured must be deterministic across runs, machines and operating
systems: no wall-clock, no filesystem paths, no ordering that depends on
insertion history. Floats are rounded, mappings are emitted with sorted keys,
and anything time-dependent is redacted before hashing.

Regenerate the golden files with:

    python -m tests.characterisation.capture --write
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "corpus"
FORMATS_DIR = HERE / "formats"
GOLDEN_DIR = HERE / "golden"

# Rounding for every captured float. Six places is far finer than any metric
# claims to be meaningful at, while staying clear of platform floating-point
# noise in the last bits.
FLOAT_PLACES = 6

# ── Normalisation helpers ──────────────────────────────────────────────────

_ISO_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2}| UTC)?"
)


def redact_timestamps(text: str) -> str:
    """Replace any wall-clock timestamp with a fixed placeholder.

    Report generation stamps the current time into its output. That is fine for
    a report a human reads and fatal for a golden fixture, so it is removed
    before the output is hashed or stored.
    """
    return _ISO_TIMESTAMP.sub("<TIMESTAMP>", text)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalise(value: Any) -> Any:
    """Recursively convert a value into a JSON-stable form."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return normalise(dataclasses.asdict(value))
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        # -0.0 and 0.0 compare equal but serialise differently.
        rounded = round(value, FLOAT_PLACES)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, dict):
        return {
            str(k): normalise(v)
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, (list, tuple)):
        return [normalise(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(str(v) for v in value)
    return value


def digest_mapping(mapping: dict) -> dict:
    """Summarise a large mapping as a size plus a stable content hash.

    Storing all 600+ glossary entries inside a golden file would drown its
    diff. The hash still fails loudly if any entry changes, and the sample
    keeps the common case — an accidental edit — readable in review.
    """
    canonical = json.dumps(normalise(mapping), sort_keys=True, ensure_ascii=False)
    keys = sorted(str(k) for k in mapping)
    return {
        "size": len(mapping),
        "sha256": sha256(canonical),
        "first_key": keys[0] if keys else None,
        "last_key": keys[-1] if keys else None,
        "sample": {k: normalise(mapping[k]) for k in keys[:5]},
    }


# ── Per-document capture ───────────────────────────────────────────────────


def attempt(build: Any) -> dict:
    """Run a capture step, sealing either its result or the way it failed.

    Some inputs make the engine raise — empty text is the obvious one — and
    which inputs raise, with which exception, is behaviour in its own right. A
    refactor that turns a `ValueError` into an empty result, or vice versa,
    should show up as a failed seal rather than as a crashing test run.
    """
    try:
        return {"outcome": "ok", "value": normalise(build())}
    except Exception as exc:  # noqa: BLE001 - the failure mode *is* the behaviour
        return {
            "outcome": "error",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }


def capture_document(text: str) -> dict:
    """Capture every observable output the engine produces for one input text."""
    from plainspeak import analyzer, reporter, simplifier

    def analyzer_section() -> dict:
        scores = analyzer.analyze(text)
        sentences = analyzer.split_sentences(text)
        words = analyzer.split_words(text)
        return {
            "scores": normalise(scores),
            "sentence_count": len(sentences),
            "sentences": sentences,
            "word_count": len(words),
            "words_head": words[:40],
            "words_sha256": sha256(chr(0).join(words)),
        }

    def simplifier_section() -> dict:
        simplification = simplifier.analyze_simplification(text)
        simplified_text, replacement_count = simplifier.generate_simplified_text(text)
        grouped = simplifier.group_barriers_by_sentence(simplification.barriers)
        return {
            "result": normalise(simplification),
            "simplified_text": simplified_text,
            "replacement_count": replacement_count,
            "grouped_barriers": normalise(grouped),
            "top_improvements": normalise(simplifier.build_top_improvements(grouped)),
        }

    def reporter_section() -> dict:
        scores = analyzer.analyze(text)
        simplification = simplifier.analyze_simplification(text)
        html = redact_timestamps(reporter.generate_report(scores, simplification, text))
        return {
            # The JSON report is the machine-readable contract, so it is sealed
            # in full. The HTML report is large and presentational; a hash plus
            # its length catches any change without the diff noise.
            "json_report": normalise(json.loads(reporter.generate_json(scores, simplification, text))),
            "html_sha256": sha256(html),
            "html_chars": len(html),
            "console_report": redact_timestamps(
                reporter.format_console_report(scores, simplification)
            ),
        }

    return {
        "input": {
            "chars": len(text),
            "sha256": sha256(text),
        },
        "analyzer": attempt(analyzer_section),
        "simplifier": attempt(simplifier_section),
        "reporter": attempt(reporter_section),
    }


# ── Global capture (not tied to one document) ──────────────────────────────

# Words chosen to exercise the syllable counter's dictionary path, its
# heuristic fallback, silent-e handling, hyphenation and non-words.
SYLLABLE_WORDS = [
    "a", "the", "cat", "apple", "table", "simple", "rhythm", "queue", "science",
    "business", "beautiful", "readability", "consideration", "notwithstanding",
    "cholecystectomy", "laparoscopic", "aforementioned", "hyphen-ated", "co-operate",
    "don't", "o'clock", "1987", "COVID", "NASA", "zzzzz", "",
]

# Words chosen to exercise stemming: regular plurals, -ies, -ed, -ing, doubled
# consonants, irregulars, and words that must not be stemmed.
STEM_WORDS = [
    "applications", "applied", "applying", "companies", "running", "stopped",
    "utilised", "utilized", "children", "was", "is", "as", "gas", "bus",
    "considerations", "remands", "damages", "series", "analysis", "",
]

# Words probed against the glossary and the protected-term register. The
# overlaps matter: "consideration" is a protected legal term of art and also an
# ordinary nominalisation, and the interaction between those two facts is
# exactly the behaviour worth sealing.
GLOSSARY_PROBES = [
    "utilise", "utilize", "commence", "terminate", "purchase", "endeavour",
    "consideration", "remand", "negligence", "consent", "prognosis",
    "aforementioned", "notwithstanding", "heretofore", "pursuant",
    "cat", "the", "", "UTILISE", "Utilise",
]

GRAMMAR_PROBES = [
    "a apple a day",
    "a hour ago",
    "a unique opportunity",
    "an user account",
    "a MP was elected",
    "an one-off payment",
    "a honest mistake",
    "an FBI agent",
    "the european union",
    "first sentence. second sentence. third one",
    "i went to the shop. i came back",
    "",
]

BARRIER_TYPES = [
    "passive_voice", "long_sentence", "complex_word", "jargon",
    "nominalization", "redundant_pair", "hidden_verb", "unknown_type",
]


def capture_globals() -> dict:
    """Capture the engine's static data and its pure, document-free functions."""
    from plainspeak import __version__, analyzer, glossary, grammar, reader, simplifier

    return {
        "version": __version__,
        "data": {
            "glossary": digest_mapping(glossary.GLOSSARY),
            "simple_word_map": digest_mapping(glossary.SIMPLE_WORD_MAP),
            # Small enough to seal outright — and important enough that every
            # change to it should be visible in a review diff.
            "protected_terms": normalise(simplifier.PROTECTED_TERMS),
            "abbreviations": normalise(analyzer.ABBREVIATIONS),
            "max_credible_grade": normalise(analyzer.MAX_CREDIBLE_GRADE),
            "min_credible_grade": normalise(analyzer.MIN_CREDIBLE_GRADE),
        },
        "syllables": {word: analyzer.count_syllables(word) for word in SYLLABLE_WORDS},
        "stems": {word: simplifier.stem_word(word) for word in STEM_WORDS},
        "glossary_matches": {
            word: normalise(simplifier.find_glossary_match(word)) for word in GLOSSARY_PROBES
        },
        "protected_lookups": {
            word: {
                "is_protected": simplifier.is_protected_term(word),
                "domain": simplifier.get_protected_domain(word),
            }
            for word in GLOSSARY_PROBES
        },
        "grammar": {
            probe: {
                "fix_articles": grammar.fix_articles(probe),
                "fix_capitalization": grammar.fix_capitalization(probe),
                "post_process_simplified": grammar.post_process_simplified(probe),
            }
            for probe in GRAMMAR_PROBES
        },
        "barrier_metadata": {
            barrier_type: {
                "confidence": simplifier.get_barrier_confidence(barrier_type),
                "priority": simplifier.get_barrier_priority(barrier_type),
                "label": simplifier.get_barrier_label(barrier_type),
            }
            for barrier_type in BARRIER_TYPES
        },
        "difficulty_bands": {
            f"{grade:g}": normalise(analyzer._classify_difficulty_band(grade))
            for grade in [-5.0, 0.0, 3.0, 6.0, 9.0, 12.0, 16.0, 20.0, 25.0, 40.0]
        },
        "grade_descriptions": {
            f"{grade:g}": analyzer._describe_grade_level(grade)
            for grade in [0.0, 5.0, 8.0, 12.0, 17.0, 30.0]
        },
        "flesch_descriptions": {
            f"{score:g}": analyzer.describe_flesch_score(score)
            for score in [-50.0, 0.0, 30.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 120.0]
        },
        "reader_extensions": normalise(reader.get_supported_extensions()),
    }


def capture_readers() -> dict:
    """Capture what each document reader extracts from its fixture."""
    from plainspeak import reader

    captured: dict[str, Any] = {}
    for path in sorted(FORMATS_DIR.glob("sample.*")):
        try:
            text, kind = reader.read_auto(path)
            captured[path.name] = {
                "outcome": "read",
                "kind": kind,
                "chars": len(text),
                "sha256": sha256(text),
                "text": text,
            }
        except Exception as exc:  # noqa: BLE001 - the failure mode *is* the behaviour
            captured[path.name] = {
                "outcome": "error",
                "error_type": type(exc).__name__,
                # Paths differ per machine, so the message is only sealed with
                # any path-like fragment removed.
                "error_message": str(exc).replace(str(FORMATS_DIR), "<FORMATS>"),
            }

    try:
        reader.read_auto(FORMATS_DIR / "does-not-exist.txt")
        captured["<missing file>"] = {"outcome": "read"}
    except Exception as exc:  # noqa: BLE001
        captured["<missing file>"] = {
            "outcome": "error",
            "error_type": type(exc).__name__,
        }
    return captured


# ── Golden file plumbing ───────────────────────────────────────────────────


def corpus_files() -> list[Path]:
    return sorted(CORPUS_DIR.glob("*.txt"))


def read_corpus(path: Path) -> str:
    # Read bytes and decode explicitly: the fixtures are LF-normalised and must
    # not be translated by the platform's default newline handling.
    return path.read_bytes().decode("utf-8")


def build_all() -> dict[str, dict]:
    """Build every golden payload, keyed by the golden file's stem."""
    payloads: dict[str, dict] = {
        "_globals": capture_globals(),
        "_readers": capture_readers(),
    }
    for path in corpus_files():
        payloads[path.stem] = capture_document(read_corpus(path))
    return payloads


def serialise(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def load_golden(name: str) -> dict:
    return json.loads(golden_path(name).read_bytes().decode("utf-8"))


def write_all() -> list[str]:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, payload in build_all().items():
        path = golden_path(name)
        text = serialise(payload)
        existing = path.read_bytes().decode("utf-8") if path.exists() else None
        if existing != text:
            io.open(path, "w", encoding="utf-8", newline="\n").write(text)
            written.append(name)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate the characterisation goldens.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="regenerate the golden files in place (review the diff before committing)",
    )
    args = parser.parse_args(argv)
    if not args.write:
        parser.error("nothing to do: pass --write to regenerate the golden files")
    changed = write_all()
    if changed:
        print(f"updated {len(changed)} golden file(s): {', '.join(sorted(changed))}")
    else:
        print("golden files already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
