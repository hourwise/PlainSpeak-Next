"""Loading and validating a ruleset.

Rules are configuration adjacent to code, and the loader treats them that way.
It parses with `yaml.safe_load`, which constructs only plain data — no object
instantiation, no imports, no code paths reachable from a rule file. Everything
past that point is the schema validator, which accepts a fixed vocabulary and
rejects everything else, including unknown keys.

A malformed bundled rule raises. It is not skipped with a warning, because a
skipped rule looks exactly like a rule that decided not to fire, and the
difference would only show up as prose quietly not being improved.

Load order does not matter. Files are read in whatever order the filesystem
offers, and the resulting ruleset is sorted by rule identity before anything
downstream sees it, so the ruleset hash, the match order and every decision
that follows are the same on every machine.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

import yaml

from .canonical import ruleset_hash
from .schema import MODE_DIAGNOSTIC, MODE_PROTECTED, MODE_SAFE_FIX, Rule, RuleError, build_rule

BUNDLED_ROOT = Path(__file__).parent / "bundled"
MANIFEST_NAME = "RULESET.yaml"

#: A single rule file has no business being large. The cap is generous for a
#: readable rule and small enough that a malformed or hostile file cannot
#: exhaust memory before the parser has a chance to reject it.
MAX_RULE_FILE_BYTES = 64 * 1024
MAX_RULES = 5000


class RulesetError(ValueError):
    """The ruleset as a whole is invalid — a duplicate ID, a bad manifest."""


@dataclass(frozen=True)
class Ruleset:
    """An immutable, loaded ruleset.

    Treat it as frozen in the strong sense: nothing downstream may add, remove
    or alter a rule, because the hash was computed over what is here and an
    altered ruleset would carry an identity that no longer describes it.
    """

    version: str
    hash: str
    rules: tuple[Rule, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", tuple(self.rules))

    def __iter__(self) -> Iterator[Rule]:
        return iter(self.rules)

    def __len__(self) -> int:
        return len(self.rules)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self.rules)

    def by_id(self, rule_id: str) -> Optional[Rule]:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def of_mode(self, mode: str) -> tuple[Rule, ...]:
        return tuple(rule for rule in self.rules if rule.mode == mode)

    @property
    def safe_fixes(self) -> tuple[Rule, ...]:
        return self.of_mode(MODE_SAFE_FIX)

    @property
    def diagnostics(self) -> tuple[Rule, ...]:
        return self.of_mode(MODE_DIAGNOSTIC)

    @property
    def protections(self) -> tuple[Rule, ...]:
        return self.of_mode(MODE_PROTECTED)


def load_ruleset(root: Optional[Path] = None) -> Ruleset:
    """Load, validate and identify a ruleset from a directory tree.

    Defaults to the rules bundled with the package. Raises `RuleError` for a
    bad rule and `RulesetError` for a bad collection of otherwise-valid rules.
    """
    root = Path(root) if root is not None else BUNDLED_ROOT
    if not root.is_dir():
        raise RulesetError(f"ruleset directory not found: {root}")

    version = _read_manifest(root)
    rules = _load_rules(root)
    _check_collection(rules)

    ordered = tuple(sorted(rules, key=lambda rule: (rule.id, rule.version)))
    return Ruleset(version=version, hash=ruleset_hash(ordered, version), rules=ordered)


def _read_manifest(root: Path) -> str:
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RulesetError(f"ruleset manifest not found: {manifest_path}")

    data = yaml.safe_load(manifest_path.read_bytes().decode("utf-8"))
    if not isinstance(data, dict):
        raise RulesetError(f"{MANIFEST_NAME} must contain a mapping")
    unknown = sorted(set(data) - {"ruleset_version", "description"})
    if unknown:
        raise RulesetError(f"{MANIFEST_NAME} has unknown field(s): {', '.join(unknown)}")

    version = data.get("ruleset_version")
    if not isinstance(version, str) or not version.strip():
        raise RulesetError(f"{MANIFEST_NAME} must declare a non-empty ruleset_version")
    return version


def _rule_files(root: Path) -> list[Path]:
    """Every rule file under `root`, in whatever order the filesystem gives.

    Deliberately not sorted. Sorting here would hide an order dependency
    downstream rather than prevent one; the ruleset is sorted by identity after
    loading, and the tests shuffle this list to prove nothing depends on it.
    """
    return [
        path
        for path in root.rglob("*.yaml")
        if path.name != MANIFEST_NAME
    ]


def _load_rules(root: Path) -> list[Rule]:
    rules: list[Rule] = []
    for path in _rule_files(root):
        rules.extend(_load_file(path, root))
        if len(rules) > MAX_RULES:
            raise RulesetError(f"ruleset exceeds {MAX_RULES} rules")
    if not rules:
        raise RulesetError(f"no rules found under {root}")
    return rules


def _load_file(path: Path, root: Path) -> list[Rule]:
    raw = path.read_bytes()
    if len(raw) > MAX_RULE_FILE_BYTES:
        raise RulesetError(
            f"{path.name} is {len(raw)} bytes, limit is {MAX_RULE_FILE_BYTES}"
        )

    source = _relative_source(path, root)
    try:
        # safe_load constructs plain data only: no arbitrary object
        # instantiation, no imports, nothing that can reach the interpreter.
        documents = list(yaml.safe_load_all(raw.decode("utf-8")))
    except yaml.YAMLError as exc:
        raise RuleError("", source, f"invalid YAML: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise RuleError("", source, f"file is not valid UTF-8: {exc}") from exc

    family = _family_of(path, root)
    loaded = []
    for index, document in enumerate(documents):
        if document is None:
            continue
        label = source if len(documents) == 1 else f"{source}#{index}"
        loaded.append(build_rule(document, label, family=family))
    if not loaded:
        raise RuleError("", source, "file contains no rules")
    return loaded


def _relative_source(path: Path, root: Path) -> str:
    """A stable, platform-independent name for a rule file.

    Always forward slashes: a validation message that read `clarity\\framing.yaml`
    on one machine and `clarity/framing.yaml` on another would make error output
    — which ends up in test expectations — platform-dependent.
    """
    try:
        relative = path.relative_to(root)
    except ValueError:
        return path.name
    return "/".join(relative.parts)


def _family_of(path: Path, root: Path) -> str:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return ""
    return parts[0] if len(parts) > 1 else ""


def _check_collection(rules: Sequence[Rule]) -> None:
    """Rules that are individually valid can still be invalid together."""
    by_id: dict[str, Rule] = {}
    for rule in rules:
        existing = by_id.get(rule.id)
        if existing is not None:
            # Two rules sharing an ID is never a merge to reconcile: the ID is a
            # public, permanent identity, and duplicating one means an audit
            # record could refer to either.
            raise RulesetError(
                f"duplicate rule id {rule.id}: defined by both "
                f"'{existing.name}' (v{existing.version}) and '{rule.name}' (v{rule.version})"
            )
        by_id[rule.id] = rule

    identities = [rule.identity for rule in rules]
    if len(identities) != len(set(identities)):
        raise RulesetError("duplicate rule identity (id, version) in the ruleset")


def bundled_families() -> tuple[str, ...]:
    """The family directories present in the bundled tree."""
    return tuple(
        sorted(
            entry.name
            for entry in BUNDLED_ROOT.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        )
    )
