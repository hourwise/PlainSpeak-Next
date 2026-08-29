"""Enforce the layering that the rest of the project depends on.

The build plan's central architectural commitment is that no interface gets its
own rewriting engine: the CLI, the desktop application and the MCP server are
all adapters over `plainspeak.core`, so that identical input cannot produce
different answers depending on how it was asked for.

That commitment is easy to state and easy to erode one convenient import at a
time. These tests make an erosion a failing build rather than a code review
someone has to catch.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "plainspeak"

# Which layers each layer is allowed to reach into. Absent from a layer's set
# means the import is a layering violation, not merely unusual.
ALLOWED_IMPORTS: dict[str, set[str]] = {
    # Detection and transformation. May consult the integrity register to find
    # out what it is forbidden to touch, and nothing else. In particular it
    # does not import `document`: the analysis engine works on strings and must
    # not acquire opinions about markup.
    "core": {"core", "integrity"},
    # The protected-term register is deliberately a leaf: anything it imported
    # could import it back, and a cycle here would be a cycle in the one part
    # of the system that exists to say "no".
    "integrity": set(),
    # Reading documents is independent of analysing them.
    "document": {"document"},
    # Declarative rules are a leaf, like `integrity`. A rule sees a string and
    # reports analysis coordinates; it does not parse documents and cannot
    # compute a source offset, because it has never seen one. That is what makes
    # it impossible for a rule to put an edit in the wrong place. It may import
    # within itself; what it may not do is reach any other layer.
    "rules": {"rules"},
    # Rendering consumes results; it must not compute them.
    "reporting": {"reporting", "core", "integrity"},
    # Orchestration, and the only layer permitted to depend on both `document`
    # and `core`. It notably may not import `reporting`: deciding how to render
    # a result is not part of producing one.
    "pipeline": {"pipeline", "core", "document", "integrity", "rules"},
    # Adapters are the only layer allowed to reach across the whole system.
    "adapters": {"adapters", "pipeline", "core", "integrity", "reporting"},
}

#: The layer that joins documents to analysis. Exactly one may do so.
ORCHESTRATION_LAYER = "pipeline"

# The flat modules kept as compatibility shims for external callers. Nothing
# inside the package may import through them, or the layering is bypassed and
# the shims become load-bearing instead of merely kind.
DEPRECATED_MODULES = {
    "analyzer", "simplifier", "glossary", "grammar",
    "reader", "reporter", "cli", "web", "syllable_data",
}


def _layer_modules() -> list[tuple[str, Path]]:
    """Every module inside a layer, as (layer name, path)."""
    found = []
    for layer in ALLOWED_IMPORTS:
        for path in sorted((PACKAGE_ROOT / layer).rglob("*.py")):
            found.append((layer, path))
    return found


def _imported_targets(path: Path) -> list[tuple[str, int]]:
    """Resolve every intra-package import to a top-level package name.

    Returns (target, line number) pairs, where target is the first component of
    the import path relative to `plainspeak` — so `from ..core.metrics import x`
    inside `plainspeak/reporting/html.py` yields `core`.
    """
    module_parts = path.relative_to(PACKAGE_ROOT).with_suffix("").parts
    tree = ast.parse(path.read_text(encoding="utf-8"))
    targets = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                # `.x` is a sibling, `..x` is a level up, and so on.
                base = list(module_parts[: len(module_parts) - node.level])
                parts = base + (node.module.split(".") if node.module else [])
            elif node.module and node.module.split(".")[0] == "plainspeak":
                parts = node.module.split(".")[1:]
            else:
                continue  # third-party or stdlib
            if parts:
                targets.append((parts[0], node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "plainspeak" and len(parts) > 1:
                    targets.append((parts[1], node.lineno))

    return targets


@pytest.mark.parametrize(
    "layer,path", _layer_modules(), ids=lambda value: getattr(value, "name", value)
)
def test_layer_only_imports_what_it_may(layer: str, path: Path) -> None:
    """No module reaches into a layer it is not allowed to depend on."""
    allowed = ALLOWED_IMPORTS[layer]
    relative = path.relative_to(PACKAGE_ROOT.parent)

    violations = [
        f"{relative}:{line} imports `{target}`"
        for target, line in _imported_targets(path)
        if target in ALLOWED_IMPORTS and target not in allowed
    ]
    assert not violations, (
        f"the `{layer}` layer may import {sorted(allowed) or 'nothing'}, but:\n  "
        + "\n  ".join(violations)
    )


@pytest.mark.parametrize(
    "layer,path", _layer_modules(), ids=lambda value: getattr(value, "name", value)
)
def test_no_layer_imports_a_deprecated_shim(layer: str, path: Path) -> None:
    """Internal code imports from the layer, never through the old flat path."""
    relative = path.relative_to(PACKAGE_ROOT.parent)
    violations = [
        f"{relative}:{line} imports the deprecated `plainspeak.{target}`"
        for target, line in _imported_targets(path)
        if target in DEPRECATED_MODULES
    ]
    assert not violations, "\n  ".join(["shims are for external callers only:"] + violations)


def test_no_analysis_lives_outside_core() -> None:
    """Adapters render and route; they do not decide what the text says.

    This is a blunt instrument — it looks for the detector and transformation
    entry points being *defined* rather than called — but it catches the exact
    failure mode the build plan warns about: an interface quietly growing its
    own copy of the engine.
    """
    engine_functions = {
        "analyze", "analyze_simplification", "generate_simplified_text",
        "find_glossary_match", "stem_word", "count_syllables", "split_sentences",
    }
    offences = []
    for layer in ("adapters", "reporting"):
        for path in sorted((PACKAGE_ROOT / layer).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in engine_functions:
                        offences.append(
                            f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno} "
                            f"defines `{node.name}`, which belongs to core"
                        )
    assert not offences, "\n  ".join(["engine logic found outside core:"] + offences)


def test_every_layer_has_a_docstring() -> None:
    """A layer whose purpose is not written down does not stay a layer long."""
    missing = []
    for layer in ALLOWED_IMPORTS:
        init = PACKAGE_ROOT / layer / "__init__.py"
        assert init.exists(), f"{layer} is not a package"
        if not ast.get_docstring(ast.parse(init.read_text(encoding="utf-8"))):
            missing.append(layer)
    assert not missing, f"layers with no docstring explaining what they are: {missing}"


# ── The seam between documents and analysis ────────────────────────────────


def test_core_does_not_import_document() -> None:
    """Stated separately from the table because it is the load-bearing one.

    Everything about the projection layer exists to keep this true. If it ever
    stops being true, the reason to have a pipeline at all has gone, and the
    right response is to think about the design again rather than to relax the
    test.
    """
    for path in sorted((PACKAGE_ROOT / "core").rglob("*.py")):
        targets = {target for target, _ in _imported_targets(path)}
        assert "document" not in targets, (
            f"{path.relative_to(PACKAGE_ROOT.parent)} imports `document`; "
            f"core must not know about markup"
        )


def test_document_does_not_import_core() -> None:
    """The other half of the same separation."""
    for path in sorted((PACKAGE_ROOT / "document").rglob("*.py")):
        targets = {target for target, _ in _imported_targets(path)}
        assert "core" not in targets, (
            f"{path.relative_to(PACKAGE_ROOT.parent)} imports `core`; "
            f"parsing must not depend on analysis"
        )


def test_only_the_orchestration_layer_joins_documents_to_analysis() -> None:
    """Orchestration lives in exactly one place.

    A module that imports both `document` and `core` is, by definition, doing
    the joining. If an adapter started doing it, the CLI and the MCP server
    could answer the same question differently, which is the failure the whole
    layering exists to prevent.
    """
    offenders = []
    for layer, path in _layer_modules():
        if layer == ORCHESTRATION_LAYER:
            continue
        targets = {target for target, _ in _imported_targets(path)}
        if "document" in targets and "core" in targets:
            offenders.append(str(path.relative_to(PACKAGE_ROOT.parent)))
    assert not offenders, (
        f"these modules join documents to analysis outside `{ORCHESTRATION_LAYER}`: {offenders}"
    )


def test_adapters_do_not_orchestrate_analysis_themselves() -> None:
    """An adapter routes and renders; it does not build a projection."""
    forbidden = {"project_document", "project_block", "analyze_document", "propose_change"}
    offences = []
    for path in sorted((PACKAGE_ROOT / "adapters").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in forbidden:
                offences.append(
                    f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno} defines `{node.name}`"
                )
    assert not offences, "orchestration found in an adapter: " + "; ".join(offences)


def test_nothing_below_the_orchestration_layer_imports_it() -> None:
    """The dependency runs outwards from `pipeline`, never back into it."""
    offenders = []
    for layer, path in _layer_modules():
        if layer in (ORCHESTRATION_LAYER, "adapters"):
            continue
        for target, line in _imported_targets(path):
            if target == ORCHESTRATION_LAYER:
                offenders.append(f"{path.relative_to(PACKAGE_ROOT.parent)}:{line}")
    assert not offenders, (
        f"lower layers must not import `{ORCHESTRATION_LAYER}`: {offenders}"
    )


# ── Documentation and enforcement must agree ───────────────────────────────


def _documented_policy() -> dict[str, set[str]]:
    """Parse the dependency table out of ARCHITECTURE.md.

    The table is the human-readable statement of the policy. Reading it here
    means a change to one and not the other fails the build, rather than
    leaving documentation that quietly describes a system that no longer
    exists.
    """
    doc = (PACKAGE_ROOT.parent / "ARCHITECTURE.md").read_text(encoding="utf-8")
    policy: dict[str, set[str]] = {}
    for line in doc.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 3:
            continue
        layer = cells[0].strip("`")
        if layer not in ALLOWED_IMPORTS:
            continue
        allowed = cells[2]
        policy[layer] = (
            set()
            if allowed == "nothing"
            else {item.strip().strip("`") for item in allowed.split(",")}
        )
    return policy


def test_documented_dependencies_match_the_enforced_ones() -> None:
    documented = _documented_policy()
    assert documented, "no dependency table found in ARCHITECTURE.md"
    assert documented == ALLOWED_IMPORTS, (
        "ARCHITECTURE.md and the enforced policy disagree. "
        f"documented: {documented} / enforced: {ALLOWED_IMPORTS}"
    )


# ── The rule engine ────────────────────────────────────────────────────────


def test_rules_do_not_parse_documents() -> None:
    """A rule matches text. Understanding markup is somebody else's job."""
    for path in sorted((PACKAGE_ROOT / "rules").rglob("*.py")):
        targets = {target for target, _ in _imported_targets(path)}
        assert "document" not in targets, (
            f"{path.relative_to(PACKAGE_ROOT.parent)} imports `document`; rules must "
            f"not parse documents or compute source offsets"
        )


def test_rules_import_nothing_from_the_rest_of_the_package() -> None:
    """The leaf property, stated directly rather than inferred from the table."""
    for path in sorted((PACKAGE_ROOT / "rules").rglob("*.py")):
        offenders = [
            f"{path.relative_to(PACKAGE_ROOT.parent)}:{line} imports `{target}`"
            for target, line in _imported_targets(path)
            if target != "rules"
        ]
        assert not offenders, "rules must stay a leaf: " + "; ".join(offenders)


def test_no_rule_module_can_evaluate_code() -> None:
    """Rules are data. Nothing in the loader may turn them into behaviour.

    A rule file that could reach `eval`, `exec` or `__import__` would stop being
    configuration and start being code, and the review that a YAML ruleset
    invites is not the review that code needs.
    """
    forbidden = {"eval", "exec", "compile", "__import__", "globals", "locals"}
    offences = []
    for path in sorted((PACKAGE_ROOT / "rules").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in forbidden:
                    offences.append(
                        f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno} "
                        f"calls `{node.func.id}`"
                    )
    assert not offences, "; ".join(offences)


def test_yaml_is_only_ever_loaded_safely() -> None:
    """`yaml.load` and `full_load` can construct arbitrary Python objects."""
    unsafe = {"load", "full_load", "unsafe_load", "load_all", "full_load_all", "unsafe_load_all"}
    offences = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "yaml"
                and node.func.attr in unsafe
            ):
                offences.append(
                    f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno} "
                    f"calls yaml.{node.func.attr}"
                )
    assert not offences, "use safe_load / safe_load_all only: " + "; ".join(offences)


def test_adapters_do_not_match_or_resolve_conflicts() -> None:
    """Matching and conflict resolution belong to one place each."""
    forbidden = {"find_matches", "build_plan", "apply_plan", "load_ruleset", "_settle", "_resolve"}
    offences = []
    for path in sorted((PACKAGE_ROOT / "adapters").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in forbidden:
                offences.append(
                    f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno} defines `{node.name}`"
                )
    assert not offences, "rule-engine logic found in an adapter: " + "; ".join(offences)


def test_the_bundled_rules_ship_with_the_package() -> None:
    """A rules directory outside the package would not survive installation."""
    from plainspeak.rules import BUNDLED_ROOT

    assert BUNDLED_ROOT.is_relative_to(PACKAGE_ROOT)
    assert (BUNDLED_ROOT / "RULESET.yaml").is_file()
    assert list(BUNDLED_ROOT.rglob("*.yaml"))
