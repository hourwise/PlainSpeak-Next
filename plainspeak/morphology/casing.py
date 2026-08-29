"""Reproducing the capitalisation of the word being replaced.

A replacement has to look like it belongs where it lands. Lower-casing whatever
was found would turn a sentence-initial "Utilise" into "use"; reproducing an
arbitrary pattern would invent emphasis the author never wrote.

So there are four shapes the engine can reproduce, and everything else fails
closed. "uTiLiSe" gets no replacement at all, which costs one missed
substitution and avoids writing a word in a casing nobody chose.
"""
from __future__ import annotations

from typing import Optional

from .policy import CASE_SHAPES


def shape_of(surface: str) -> Optional[str]:
    """Classify capitalisation, or `None` when it cannot be reproduced."""
    if not any(character.isalpha() for character in surface):
        return "lower"
    if surface == surface.lower():
        return "lower"
    if surface == surface.upper():
        # A single capital letter reads as a sentence start far more often than
        # as an acronym, so it is treated as one.
        return "upper" if len(surface.strip()) > 1 else "sentence"

    words = [word for word in surface.split() if any(c.isalpha() for c in word)]
    if words and all(word[:1].isupper() and word[1:] == word[1:].lower() for word in words):
        return "title" if len(words) > 1 else "sentence"
    if surface[:1].isupper() and surface[1:] == surface[1:].lower():
        return "sentence"
    return None


def apply_shape(target: str, shape: str) -> str:
    """Render `target` in one of the reproducible shapes."""
    if shape not in CASE_SHAPES:
        raise ValueError(f"unknown case shape {shape!r}; known: {list(CASE_SHAPES)}")
    if shape == "lower":
        return target.lower()
    if shape == "upper":
        return target.upper()
    if shape == "sentence":
        return target[:1].upper() + target[1:]
    return " ".join(word[:1].upper() + word[1:] for word in target.split(" "))


def match_casing(surface: str, target: str) -> Optional[str]:
    """Render `target` to match how `surface` was written, or `None`.

    `None` means the surface's capitalisation has no mechanical equivalent, and
    the caller should refuse rather than choose one.
    """
    shape = shape_of(surface)
    return None if shape is None else apply_shape(target, shape)
