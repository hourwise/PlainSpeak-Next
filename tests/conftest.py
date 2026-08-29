"""Shared fixtures for the rule-engine tests.

Most rule tests need a small, purpose-built ruleset rather than the bundled one:
testing conflict resolution against 38 real rules would mean constructing prose
that happens to trigger exactly the overlap under test, which is fragile and
unreadable. `ruleset_from` writes YAML to a temporary directory and loads it
through the real loader, so the fixtures exercise the same validation path as
the shipped rules.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Callable

import pytest

from plainspeak.rules import Ruleset, load_ruleset

#: A complete, valid rule. Tests that need "a rule with one thing wrong" start
#: from this and break exactly that thing, so a failure names the field it
#: meant to test rather than the first field the validator happened to reach.
VALID_RULE = """\
id: PS.TEST.001
version: 1
name: example-rule
mode: safe-fix
description: >
  A rule used by the test suite.
match:
  type: phrase
  text: "in order to"
action:
  type: replace
  replacement: "to"
scope:
  include: [prose]
case:
  policy: preserve
priority: 100
reason:
  short: "A shorter phrase means the same thing"
provenance:
  source: "PlainSpeak test suite"
  reference: ""
  licence: "project-authored"
examples:
  positive:
    - "Register in order to vote."
  negative:
    - "The items arrived in order."
  transform:
    - before: "Register in order to vote."
      after: "Register to vote."
"""

MANIFEST = 'ruleset_version: "test.1"\n'


@pytest.fixture
def ruleset_from(tmp_path: Path) -> Callable[..., Ruleset]:
    """Build a ruleset from YAML text, through the real loader.

    Accepts either one YAML string or a mapping of relative path to YAML, so a
    test can put rules in separate files and separate families when the layout
    is what is under test.
    """

    counter = {"n": 0}

    def build(source, manifest: str = MANIFEST) -> Ruleset:
        # A fresh tree per call: a test that builds two rulesets to compare
        # them must not end up loading the union of both.
        counter["n"] += 1
        root = tmp_path / f"ruleset{counter['n']}"
        root.mkdir()
        (root / "RULESET.yaml").write_text(manifest, encoding="utf-8")

        files = {"rules/rules.yaml": source} if isinstance(source, str) else source
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(text), encoding="utf-8")

        return load_ruleset(root)

    return build


@pytest.fixture(scope="session")
def bundled() -> Ruleset:
    """The ruleset PlainSpeak actually ships."""
    return load_ruleset()
