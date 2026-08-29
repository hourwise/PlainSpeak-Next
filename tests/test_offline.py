"""PlainSpeak must work with the network switched off.

The offline guarantee is a product commitment, not a happy accident of the
current implementation. Someone processing a medical discharge letter or a legal
notice should be able to see, from the outside, that nothing left the machine.

A dependency that quietly fetched something — a unit table, a vocabulary, a
policy file — would break that, and would do it silently on a developer machine
with working DNS. So this test takes the network away and runs the whole
pipeline: load the rules, parse, project, analyse, plan, check integrity, apply.

Everything PlainSpeak needs ships with PlainSpeak.
"""
from __future__ import annotations

import socket
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class NetworkDenied(AssertionError):
    """Raised if anything attempts to open a connection."""


@pytest.fixture
def no_network(monkeypatch):
    """Make every outbound connection attempt fail loudly.

    Blocks the socket constructor and the convenience helpers above it, so a
    caller cannot slip past by using `create_connection` or a resolver directly.
    """

    def refuse(*args, **kwargs):
        raise NetworkDenied("PlainSpeak attempted to use the network")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "gethostbyname", refuse)
    return refuse


def test_the_network_fixture_actually_blocks(no_network) -> None:
    """A guard that does not guard would make every test below meaningless."""
    with pytest.raises(NetworkDenied):
        socket.socket()
    with pytest.raises(NetworkDenied):
        socket.create_connection(("example.com", 80))


def test_the_ruleset_loads_offline(no_network) -> None:
    from plainspeak.rules import load_ruleset

    ruleset = load_ruleset()
    assert len(ruleset) == 38
    assert ruleset.hash


def test_the_integrity_policy_loads_offline(no_network) -> None:
    from plainspeak.integrity import policy_hash, snapshot

    assert len(policy_hash()) == 64
    facts = snapshot("Take 0.5 mg before 14:30 on 2026-08-29, costing £250.")
    assert {fact.kind for fact in facts} >= {"measurement", "time", "date", "currency"}


def test_the_whole_pipeline_runs_offline(no_network) -> None:
    from plainspeak.document import parse_markdown
    from plainspeak.pipeline.apply import apply_plan
    from plainspeak.pipeline.audit import plan_to_json
    from plainspeak.pipeline.planner import build_plan

    source = (
        "It is important to note that staff utilise the register in order to "
        "apply. You must not exceed 0.5 mg.\n"
    )
    document = parse_markdown.parse(source)
    plan = build_plan(document)
    result = apply_plan(document, plan)

    assert result.changed
    assert "0.5 mg" in result.output, "the dose must survive"
    assert "must not" in result.output, "the prohibition must survive"
    assert plan_to_json(plan)


def test_the_inherited_analyser_runs_offline(no_network) -> None:
    from plainspeak.document import parse_markdown
    from plainspeak.pipeline import analyze_document

    result = analyze_document(parse_markdown.parse("The committee was convened.\n"))
    assert result.scores.total_words > 0


def test_the_syllable_dictionary_loads_offline(no_network) -> None:
    from plainspeak.core.syllables import get_syllable_count

    assert len(get_syllable_count()) >= 100_000


def test_no_networking_module_is_imported_by_the_engine() -> None:
    """A static check to go with the runtime one.

    Neither is sufficient alone: an import that only happens inside a function
    would not show here, and a module imported but never called would not show
    at runtime.
    """
    import ast

    forbidden = {
        "urllib", "http", "requests", "httpx", "socket", "ftplib", "smtplib",
        "telnetlib", "xmlrpc", "aiohttp", "ssl", "asyncio",
    }
    offences = []
    package = REPO_ROOT / "plainspeak"

    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in forbidden:
                    offences.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} imports {name}"
                    )

    # The web adapter is Flask-based and legitimately serves over a socket; it
    # is an interface, not the engine, and it binds locally.
    offences = [item for item in offences if "adapters/web.py" not in item.replace("\\", "/")]
    assert not offences, "networking imports in the engine: " + "; ".join(offences)


def test_no_dependency_is_a_model_or_inference_client() -> None:
    """The declared dependencies, checked against what this project must not be."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for forbidden in (
        "openai", "anthropic", "transformers", "torch", "tensorflow", "sentence-transformers",
        "spacy", "nltk", "gensim", "faiss", "chromadb", "langchain", "llama",
    ):
        assert forbidden not in text, f"{forbidden} must not be a dependency"
