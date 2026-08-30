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

#: Spelled out rather than escaped inline, so the fixtures below stay legible.
NL = chr(10)


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

    from .test_glossary_migration import RULESET_COUNT

    ruleset = load_ruleset()
    assert len(ruleset) == RULESET_COUNT
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


def test_style_diagnostics_run_offline(no_network) -> None:
    """The layer most likely to be assumed to need a model.

    It does not need one, and this is where that is demonstrated rather than
    asserted: the whole style analysis runs with the network taken away.
    """
    from plainspeak.document import parse_markdown
    from plainspeak.pipeline.styling import analyze_style
    from plainspeak.style import STYLE_POLICY_VERSION, analysis_to_json, policy_hash

    source = (
        "Moreover, the framework enables the team to deliver. "
        "Moreover, the framework enables the team to report. "
        "Moreover, the framework enables the team to review. "
        "Moreover, the framework enables the team to improve. "
        "Moreover, the framework enables the team to publish. "
        "Moreover, the framework enables the team to archive.\n"
    )
    analysis = analyze_style(parse_markdown.parse(source))

    assert analysis.policy_version == STYLE_POLICY_VERSION
    assert analysis.policy_hash == policy_hash()
    assert analysis.findings, "a document this repetitive should produce something"
    assert analysis_to_json(analysis)


def test_style_profiles_load_and_apply_offline(no_network) -> None:
    """No remote profile service, no online calibration lookup, no telemetry.

    The profile pack is bundled YAML validated at load. Nothing about
    interpretation needs the network, and this is where that is demonstrated
    rather than assumed — including the comparison path, which is the one a
    desktop profile selector would use.
    """
    from plainspeak.document import parse_markdown
    from plainspeak.pipeline.styling import compare_style_profiles
    from plainspeak.style.profiles import load_pack, load_profile, pack_hash, profile_ids

    pack = load_pack()
    assert len(pack) == 5
    assert profile_ids() == ("natural", "plain", "technical", "government", "academic")
    assert len(pack_hash(pack)) == 64
    assert load_profile("technical").id == "technical"

    source = (
        "The consumer reads a message. The consumer applies the transform. "
        "The consumer writes the result. The consumer acknowledges the message.\n\n"
        "- validate the envelope\n- verify the digest\n- load the revision\n"
        "- apply the pipeline\n- write the result\n- acknowledge\n"
    )
    results = compare_style_profiles(parse_markdown.parse(source))
    assert set(results) == set(profile_ids())
    assert all(analysis.profile_hash for analysis in results.values())


def test_style_planning_and_review_work_offline(no_network) -> None:
    """No external synonym service, no telemetry, no model.

    The whole profile-governed path runs with sockets denied: plan, approve,
    apply. A style suggestion is an exact replacement written into a bundled YAML
    rule and reviewed by a person, and nothing about that needs a network.
    """
    from plainspeak.document import parse_markdown
    from plainspeak.pipeline.style_plan import plan_style_changes
    from plainspeak.pipeline.style_review import (
        accept_all,
        apply_style_changes,
        approve_style_changes,
    )

    source = (
        "The pilot ran for eleven months. Attendance was lower than forecast." + NL + NL
        + "Nevertheless, the scheme met its objective. The rate rose to 78%." + NL + NL
        + "Nevertheless, the cost stayed high. Staff time explains most of it." + NL + NL
        + "Site A did best. It also had the most experienced team." + NL + NL
        + "Nevertheless, the smaller sites improved too. It surprised the panel." + NL + NL
        + "Nevertheless, none reached the target. Three came close." + NL + NL
        + "Nevertheless, the panel recommends another year. The board decides." + NL + NL
        + "Nevertheless, the funding is not yet agreed. March is the deadline." + NL
    )
    document = parse_markdown.parse(source)
    plan = plan_style_changes(document, "natural")

    assert plan.review_required, "the offline fixture should produce suggestions"
    assert all(item.status == "review_required" for item in plan.review_required)

    approval = approve_style_changes(plan, accept_all(plan))
    result = apply_style_changes(document, approval)
    assert result.changed
    assert "Even so," in result.output


def test_the_desktop_review_path_works_offline(no_network) -> None:
    """The application needs no network on any path a person can reach.

    No update check, no analytics, no crash upload, no remote fonts, no web
    content and no telemetry. The whole review workflow — open, analyse, decide,
    materialise — runs with sockets denied.
    """
    from plainspeak.desktop.session import ReviewSession, save_revised
    from plainspeak.pipeline import build_review_bundle, parse_source

    source = (
        "The team utilise the register." + NL + NL
        + "Nevertheless, the panel agreed. Nevertheless, the cost rose." + NL + NL
        + "Nevertheless, attendance fell. Nevertheless, nobody minded." + NL + NL
        + "Nevertheless, the report went out. Nevertheless, March is the deadline." + NL
    )
    document = parse_source(source)
    session = ReviewSession("natural")
    session.load(REPO_ROOT / "offline.md", document.source)
    generation = session.begin_analysis()

    assert session.accept_analysis(build_review_bundle(document, "natural"), generation)
    snapshot = session.snapshot()
    assert snapshot.changes
    assert snapshot.identities["profile_id"] == "natural"

    if session.bundle.reviewable:
        session.accept(session.bundle.reviewable[0].proposal_id)
        assert session.snapshot().preview.revised_text


def test_the_desktop_self_test_runs_offline(no_network) -> None:
    """The packaged verification path is offline too."""
    from plainspeak.desktop.selftest import run_self_test

    assert run_self_test([]) == 0


def test_the_desktop_contains_no_network_code() -> None:
    """A static check to go with the runtime one.

    An update checker added later would most likely arrive as an import at the
    top of a widget module, which this catches even if nobody ever calls it.
    """
    import ast

    forbidden = {
        "urllib", "http", "requests", "httpx", "socket", "ftplib", "smtplib",
        "xmlrpc", "aiohttp", "webbrowser",
    }
    offences = []
    for path in sorted((REPO_ROOT / "plainspeak" / "desktop").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in forbidden:
                    offences.append(f"{path.name}:{node.lineno} imports {name}")

    assert not offences, "networking in the desktop: " + "; ".join(offences)

    # And no Qt module that can fetch or render remote content.
    for path in sorted((REPO_ROOT / "plainspeak" / "desktop").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for module in ("QtNetwork", "QtWebEngine", "QtWebView", "QtWebSockets"):
            assert module not in source, f"{path.name} uses {module}"


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
