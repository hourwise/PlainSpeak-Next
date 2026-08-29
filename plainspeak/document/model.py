"""The document intermediate representation.

A document is not a string. Treating it as one is why the inherited engine
cannot tell a heading from a quotation, or a code fence from a paragraph, and
why it will happily rewrite the inside of a URL.

The representation here is built on one commitment: **every node knows exactly
which characters of the original source it came from**. That single property
gives us the rest for free —

- serialising an unedited document returns the original bytes, because the
  original bytes are what it holds;
- an edit is a span replacement, so a transformation plan is just a list of
  span replacements that can be validated and ordered before anything is
  applied;
- a node whose source location cannot be established exactly is marked
  untransformable rather than guessed at.

That last point is the whole safety argument. A parser that is unsure where a
piece of prose lives in the source must say so, because an edit applied at the
wrong offset is a corrupted document, and a corrupted document is worse than an
unimproved one.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterator, Optional, Sequence


def content_hash(text: str) -> str:
    """The provenance hash for a piece of original source."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class Span:
    """A half-open character range `[start, end)` into the document source."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span: [{self.start}, {self.end})")

    def __len__(self) -> int:
        return self.end - self.start

    def text(self, source: str) -> str:
        return source[self.start : self.end]

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: "Span") -> bool:
        return self.start <= other.start and other.end <= self.end


# Why a node may not be transformed. Recorded rather than implied, so that a
# report can say *why* a passage was left alone — "inside a code block" and
# "the parser could not locate it" are very different answers to a user asking
# why nothing happened.
REASON_CODE = "code is not prose"
REASON_QUOTE = "quoted material must not be reworded"
REASON_TABLE = "table structure is significant"
REASON_RAW = "raw markup is not prose"
REASON_LINK_TARGET = "a link destination is an address, not prose"
REASON_UNLOCATABLE = "the parser could not establish this node's source offsets"
REASON_INHERITED = "an enclosing node is not transformable"


@dataclass
class Node:
    """Common state every node carries, whether block or inline."""

    span: Span
    #: Index path from the document root, e.g. `(3, 1, 0)`. Identifies a node's
    #: place in the tree independently of its source offsets, so a change
    #: record can name a location that survives re-parsing.
    path: tuple[int, ...] = ()
    #: Which parser produced this node, e.g. `"markdown-it-py/commonmark"`.
    provenance: str = ""
    #: SHA-256 of the original source slice, captured at parse time. If a node's
    #: current source no longer hashes to this, something has rewritten the
    #: document underneath us.
    original_hash: str = ""
    transformable: bool = True
    #: Empty when `transformable`; otherwise one of the REASON_* constants.
    untransformable_reason: str = ""

    @property
    def location(self) -> str:
        """The node's path as a readable string, for reports and audit records."""
        return ".".join(str(index) for index in self.path) or "root"

    def mark_untransformable(self, reason: str) -> None:
        self.transformable = False
        self.untransformable_reason = reason

    def children(self) -> Sequence["Node"]:
        return ()

    def walk(self) -> Iterator["Node"]:
        """Yield this node and every descendant, in document order."""
        yield self
        for child in self.children():
            yield from child.walk()

    def verify(self, source: str) -> bool:
        """Check the source still matches what was hashed at parse time."""
        return content_hash(self.span.text(source)) == self.original_hash


# ── Inline nodes ───────────────────────────────────────────────────────────


@dataclass
class Inline(Node):
    """Marker base for nodes that live inside a block."""


@dataclass
class Text(Inline):
    """A run of prose. This is the only thing the engine may rewrite."""

    text: str = ""


@dataclass
class CodeSpan(Inline):
    """An inline code span. Never prose, however much it looks like a word."""

    code: str = ""

    def __post_init__(self) -> None:
        self.mark_untransformable(REASON_CODE)


@dataclass
class RawInline(Inline):
    """Inline HTML or any other markup passed through untouched."""

    def __post_init__(self) -> None:
        self.mark_untransformable(REASON_RAW)


@dataclass
class LineBreak(Inline):
    """A soft or hard break inside a block."""

    hard: bool = False


@dataclass
class Emphasis(Inline):
    """Emphasised or strongly emphasised text.

    The emphasis markers themselves are not prose, but the text between them
    is, so this node holds children rather than a string.
    """

    kind: str = "em"  # "em" | "strong" | "s"
    content: list[Inline] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class Link(Inline):
    """A link. Its text is prose; its destination emphatically is not."""

    href: str = ""
    title: str = ""
    content: list[Inline] = field(default_factory=list)
    #: The span covering the destination, so a validator can prove no edit
    #: ever lands inside it.
    href_span: Optional[Span] = None

    def children(self) -> Sequence[Node]:
        return self.content


# ── Block nodes ────────────────────────────────────────────────────────────


@dataclass
class Block(Node):
    """Marker base for top-level and nested structural nodes."""


@dataclass
class Paragraph(Block):
    content: list[Inline] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class Heading(Block):
    level: int = 1
    content: list[Inline] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class Quote(Block):
    """Quoted material.

    Marked untransformable by default: rewording somebody else's words and
    leaving them inside quotation marks misattributes them. Prose inside a
    quote is still parsed and still analysed — it is only edits that are
    refused.
    """

    content: list[Block] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.mark_untransformable(REASON_QUOTE)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class ListItem(Block):
    content: list[Block] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class ListBlock(Block):
    ordered: bool = False
    items: list[ListItem] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.items


@dataclass
class CodeBlock(Block):
    language: str = ""
    code: str = ""

    def __post_init__(self) -> None:
        self.mark_untransformable(REASON_CODE)


@dataclass
class Table(Block):
    """A table, held as opaque source.

    Cell contents are prose, but the alignment row and the pipe structure are
    not, and getting that wrong silently destroys the table. Until the cell
    spans are parsed properly, the whole block is off limits.
    """

    def __post_init__(self) -> None:
        self.mark_untransformable(REASON_TABLE)


@dataclass
class ThematicBreak(Block):
    def __post_init__(self) -> None:
        self.mark_untransformable(REASON_RAW)


@dataclass
class HtmlBlock(Block):
    def __post_init__(self) -> None:
        self.mark_untransformable(REASON_RAW)


# ── The document ───────────────────────────────────────────────────────────


@dataclass
class Document:
    """A parsed document, and the source it was parsed from.

    The source is kept in full and is the authority. Nodes index into it; they
    do not replace it. Serialising a document that has not been edited is
    therefore not a reconstruction — it is the original string.
    """

    source: str
    source_format: str
    blocks: list[Block] = field(default_factory=list)
    provenance: str = ""
    source_hash: str = ""

    def __post_init__(self) -> None:
        if not self.source_hash:
            self.source_hash = content_hash(self.source)

    def walk(self) -> Iterator[Node]:
        for block in self.blocks:
            yield from block.walk()

    def prose_spans(self) -> list[Span]:
        """Every span the engine is allowed to rewrite, in document order.

        A `Text` node qualifies only if it is transformable *and* nothing
        enclosing it forbids transformation — which is why this walks the tree
        rather than filtering a flat list. A paragraph inside a block quote
        contains perfectly ordinary prose; it is still not ours to reword.
        """
        spans: list[Span] = []

        def visit(node: Node, blocked: bool) -> None:
            blocked = blocked or not node.transformable
            if isinstance(node, Text) and not blocked and len(node.span):
                spans.append(node.span)
            for child in node.children():
                visit(child, blocked)

        for block in self.blocks:
            visit(block, False)
        return spans

    def text_of(self, span: Span) -> str:
        return span.text(self.source)

    def serialise(self, replacements: Sequence[tuple[Span, str]] = ()) -> str:
        """Render the document, optionally replacing some spans.

        With no replacements this returns `self.source` unchanged — the
        round-trip guarantee is structural rather than something the serialiser
        has to be careful about.

        Replacements are applied right to left so that earlier offsets stay
        valid, and are rejected if they overlap, because two edits to the same
        characters have no defined meaning and silently letting one win is how
        a deterministic engine stops being deterministic.
        """
        if not replacements:
            return self.source

        ordered = sorted(replacements, key=lambda pair: (pair[0].start, pair[0].end))
        for (left, _), (right, _) in zip(ordered, ordered[1:]):
            if left.overlaps(right):
                raise ValueError(
                    f"overlapping replacements: [{left.start}, {left.end}) "
                    f"and [{right.start}, {right.end})"
                )

        result = self.source
        for span, text in reversed(ordered):
            if span.end > len(result):
                raise ValueError(f"span [{span.start}, {span.end}) is outside the source")
            result = result[: span.start] + text + result[span.end :]
        return result
