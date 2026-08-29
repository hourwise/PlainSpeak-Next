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
    # out what it is forbidden to touch, and nothing else.
    "core": {"core", "integrity"},
    # The protected-term register is deliberately a leaf: anything it imported
    # could import it back, and a cycle here would be a cycle in the one part
    # of the system that exists to say "no".
    "integrity": set(),
    # Reading documents is independent of analysing them.
    "document": {"document"},
    # Rendering consumes results; it must not compute them.
    "reporting": {"reporting", "core", "integrity"},
    # Adapters are the only layer allowed to reach across the whole system.
    "adapters": {"adapters", "core", "document", "integrity", "reporting"},
}

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
