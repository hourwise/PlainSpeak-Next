"""Parsing Markdown into the document representation.

Block structure comes from `markdown-it-py`, which reports a line range for
every block token. Converting those to character offsets is exact.

Inline structure is the hard part, and the reason this module is longer than it
looks like it should be. markdown-it reports inline tokens as a stream of
content and markup with **no source offsets**, so the offsets have to be
recovered by scanning the block's source text and locating each token in turn.

Scanning can fail. Markdown decodes escapes and entities, so a `text` token's
content is not always a literal substring of the source: `a \\* b` parses to the
content `a * b`, which does not appear in the source at all. When a token
cannot be located exactly, this parser does not guess and does not approximate.
It marks the enclosing block untransformable and records why. An edit applied
at a wrong offset produces a corrupted document, which is a far worse outcome
than a document that was left alone.
"""
from __future__ import annotations

from typing import Optional

from markdown_it import MarkdownIt
from markdown_it.token import Token

from .model import (
    Block,
    CodeBlock,
    CodeSpan,
    Document,
    Emphasis,
    Heading,
    HtmlBlock,
    Inline,
    LineBreak,
    Link,
    ListBlock,
    ListItem,
    Paragraph,
    Quote,
    RawInline,
    REASON_LINK_TARGET,
    REASON_UNLOCATABLE,
    Span,
    Table,
    Text,
    ThematicBreak,
    content_hash,
)

PROVENANCE = "markdown-it-py/commonmark+table+strikethrough"


def _parser() -> MarkdownIt:
    r"""The Markdown dialect this project reads.

    CommonMark plus the two GitHub extensions that change how *structure* is
    read rather than how it is styled. Tables matter because an unrecognised
    table is parsed as a paragraph, and a paragraph is something the engine
    would consider editable.

    `text_join` is disabled deliberately. It merges escapes and entities into
    the surrounding text token, replacing `\*` with `*` and `&amp;` with `&`,
    which leaves the token content no longer a substring of the source. The
    scan would then fail and take the whole paragraph out of scope. Keeping the
    tokens separate preserves their source form in `markup`, so an ordinary
    paragraph containing an escaped character stays editable.
    """
    return (
        MarkdownIt("commonmark")
        .enable("table")
        .enable("strikethrough")
        .disable("text_join")
    )


def parse(source: str) -> Document:
    """Parse Markdown into a `Document`."""
    document = Document(
        source=source,
        source_format="markdown",
        provenance=PROVENANCE,
    )
    tokens = _parser().parse(source)
    offsets = _line_offsets(source)
    builder = _Builder(source, offsets)
    document.blocks = builder.build(tokens, path=())
    return document


def _line_offsets(source: str) -> list[int]:
    """Character offset of the start of each line, plus a final sentinel."""
    offsets = [0]
    for index, character in enumerate(source):
        if character == "\n":
            offsets.append(index + 1)
    offsets.append(len(source))
    return offsets


class _Builder:
    """Turns a flat markdown-it token stream into a tree of nodes."""

    def __init__(self, source: str, offsets: list[int]) -> None:
        self.source = source
        self.offsets = offsets

    # ── spans ──────────────────────────────────────────────────────────────

    def span_for(self, token: Token) -> Span:
        """The trimmed character span of a block token's line range."""
        if not token.map:
            return Span(0, 0)
        start_line, end_line = token.map
        start = self.offsets[min(start_line, len(self.offsets) - 1)]
        end = self.offsets[min(end_line, len(self.offsets) - 1)]
        raw = self.source[start:end]
        return Span(
            start + (len(raw) - len(raw.lstrip())),
            end - (len(raw) - len(raw.rstrip())),
        )

    def node_kwargs(self, span: Span, path: tuple[int, ...]) -> dict:
        return {
            "span": span,
            "path": path,
            "provenance": PROVENANCE,
            "original_hash": content_hash(span.text(self.source)),
        }

    # ── blocks ─────────────────────────────────────────────────────────────

    def build(self, tokens: list[Token], path: tuple[int, ...]) -> list[Block]:
        """Consume a token stream, returning the blocks at this nesting level."""
        blocks: list[Block] = []
        index = 0

        while index < len(tokens):
            token = tokens[index]
            child_path = path + (len(blocks),)

            if token.type.endswith("_close"):
                # Handled by whichever `_open` opened it.
                index += 1
                continue

            block, index = self._build_one(tokens, index, child_path)
            if block is not None:
                blocks.append(block)

        return blocks

    def _build_one(
        self, tokens: list[Token], index: int, path: tuple[int, ...]
    ) -> tuple[Optional[Block], int]:
        token = tokens[index]
        span = self.span_for(token)
        kwargs = self.node_kwargs(span, path)

        if token.type == "paragraph_open":
            inline = tokens[index + 1]
            node = Paragraph(**kwargs, content=self._inline(inline, span, path))
            self._propagate_unlocatable(node)
            return node, self._skip_to_close(tokens, index, "paragraph")

        if token.type == "heading_open":
            inline = tokens[index + 1]
            node = Heading(
                **kwargs,
                level=len(token.markup),
                content=self._inline(inline, span, path),
            )
            self._propagate_unlocatable(node)
            return node, self._skip_to_close(tokens, index, "heading")

        if token.type == "blockquote_open":
            end = self._matching_close(tokens, index, "blockquote")
            node = Quote(**kwargs, content=self.build(tokens[index + 1 : end], path))
            return node, end + 1

        if token.type in ("bullet_list_open", "ordered_list_open"):
            kind = "bullet_list" if token.type.startswith("bullet") else "ordered_list"
            end = self._matching_close(tokens, index, kind)
            node = ListBlock(
                **kwargs,
                ordered=kind == "ordered_list",
                items=self._list_items(tokens[index + 1 : end], path),
            )
            return node, end + 1

        if token.type == "fence" or token.type == "code_block":
            return CodeBlock(**kwargs, language=token.info.strip(), code=token.content), index + 1

        if token.type == "table_open":
            end = self._matching_close(tokens, index, "table")
            # The table's own map covers the whole block, so its interior
            # tokens need no separate treatment: nothing inside is editable.
            return Table(**self.node_kwargs(self.span_for(token), path)), end + 1

        if token.type == "hr":
            return ThematicBreak(**kwargs), index + 1

        if token.type == "html_block":
            return HtmlBlock(**kwargs), index + 1

        # An unrecognised block token is treated as opaque rather than as
        # prose. Being wrong in this direction costs a missed improvement;
        # being wrong in the other costs a corrupted document.
        if token.type.endswith("_open"):
            end = self._matching_close(tokens, index, token.type[: -len("_open")])
            node = HtmlBlock(**kwargs)
            return node, end + 1

        return None, index + 1

    def _list_items(self, tokens: list[Token], path: tuple[int, ...]) -> list[ListItem]:
        items: list[ListItem] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token.type != "list_item_open":
                index += 1
                continue
            end = self._matching_close(tokens, index, "list_item")
            item_path = path + (len(items),)
            span = self.span_for(token)
            items.append(
                ListItem(
                    **self.node_kwargs(span, item_path),
                    content=self.build(tokens[index + 1 : end], item_path),
                )
            )
            index = end + 1
        return items

    @staticmethod
    def _matching_close(tokens: list[Token], index: int, kind: str) -> int:
        """Index of the `<kind>_close` matching the `<kind>_open` at `index`."""
        depth = 0
        for offset in range(index, len(tokens)):
            token = tokens[offset]
            if token.type == f"{kind}_open":
                depth += 1
            elif token.type == f"{kind}_close":
                depth -= 1
                if depth == 0:
                    return offset
        return len(tokens) - 1

    @staticmethod
    def _skip_to_close(tokens: list[Token], index: int, kind: str) -> int:
        return _Builder._matching_close(tokens, index, kind) + 1

    @staticmethod
    def _propagate_unlocatable(block: Block) -> None:
        """If any inline could not be located, the whole block is off limits.

        A block with one unlocated token has, by definition, offsets we cannot
        trust anywhere after it — the scan lost its place. Refusing the block
        is the only honest response.
        """
        for node in block.walk():
            if node.untransformable_reason == REASON_UNLOCATABLE:
                block.mark_untransformable(REASON_UNLOCATABLE)
                return

    # ── inlines ────────────────────────────────────────────────────────────

    def _inline(self, token: Token, region: Span, path: tuple[int, ...]) -> list[Inline]:
        """Recover inline nodes, with offsets found by scanning the source."""
        if token.type != "inline" or not token.children:
            return []
        scanner = _Scanner(self.source, region)
        nodes = self._inline_children(list(token.children), scanner, path, index=0)[0]
        return nodes

    def _inline_children(
        self,
        tokens: list[Token],
        scanner: "_Scanner",
        path: tuple[int, ...],
        index: int,
        stop_at: Optional[str] = None,
    ) -> tuple[list[Inline], int]:
        nodes: list[Inline] = []

        while index < len(tokens):
            token = tokens[index]
            if stop_at and token.type == stop_at:
                return nodes, index + 1

            child_path = path + (len(nodes),)
            node, index = self._build_inline(tokens, index, scanner, child_path)
            if node is not None:
                nodes.append(node)

        return nodes, index

    def _build_inline(
        self,
        tokens: list[Token],
        index: int,
        scanner: "_Scanner",
        path: tuple[int, ...],
    ) -> tuple[Optional[Inline], int]:
        token = tokens[index]

        if token.type == "text":
            if not token.content:
                return None, index + 1
            span = scanner.locate(token.content)
            return Text(**self.node_kwargs_or_lost(span, path), text=token.content), index + 1

        if token.type == "code_inline":
            span = scanner.locate(token.content)
            return CodeSpan(**self.node_kwargs_or_lost(span, path), code=token.content), index + 1

        if token.type in ("softbreak", "hardbreak"):
            span = scanner.locate("\n")
            return (
                LineBreak(**self.node_kwargs_or_lost(span, path), hard=token.type == "hardbreak"),
                index + 1,
            )

        if token.type in ("em_open", "strong_open", "s_open"):
            kind = {"em_open": "em", "strong_open": "strong", "s_open": "s"}[token.type]
            start = scanner.locate(token.markup)
            content, index = self._inline_children(
                tokens, scanner, path, index + 1, stop_at=token.type.replace("_open", "_close")
            )
            end = scanner.locate(token.markup)
            span = _joined(start, end, scanner)
            return Emphasis(**self.node_kwargs_or_lost(span, path), kind=kind, content=content), index

        if token.type == "link_open":
            href = token.attrGet("href") or ""
            autolink = token.markup == "autolink"
            start = scanner.locate("<" if autolink else "[")
            content, index = self._inline_children(
                tokens, scanner, path, index + 1, stop_at="link_close"
            )
            # The destination follows the closing bracket. Locating it is what
            # lets a validator prove no edit ever lands inside a URL. It is a
            # soft lookup: a reference link keeps its destination in a
            # definition elsewhere in the document, so not finding it here is
            # normal and must not invalidate the surrounding paragraph.
            href_span = scanner.try_locate(href) if href else None
            end = scanner.position_span()
            span = _joined(start, end, scanner)
            node = Link(
                **self.node_kwargs_or_lost(span, path),
                href=href,
                title=token.attrGet("title") or "",
                content=content,
                href_span=href_span,
            )
            if autolink:
                # An autolink's "text" is its URL. Nothing inside is prose.
                node.mark_untransformable(REASON_LINK_TARGET)
            return node, index

        if token.type in ("html_inline", "image", "text_special"):
            # For an escape or an entity, `markup` is the source form and
            # `content` is the decoded character; only the former is findable.
            probe = token.markup or token.content
            span = scanner.locate(probe) if probe else None
            return RawInline(**self.node_kwargs_or_lost(span, path)), index + 1

        # Anything unrecognised is opaque, not prose.
        return RawInline(**self.node_kwargs_or_lost(None, path)), index + 1

    def node_kwargs_or_lost(self, span: Optional[Span], path: tuple[int, ...]) -> dict:
        if span is None:
            return {
                "span": Span(0, 0),
                "path": path,
                "provenance": PROVENANCE,
                "original_hash": "",
                "transformable": False,
                "untransformable_reason": REASON_UNLOCATABLE,
            }
        return self.node_kwargs(span, path)


def _joined(start: Optional[Span], end: Optional[Span], scanner: "_Scanner") -> Optional[Span]:
    if start is None:
        return None
    finish = end.end if end is not None else scanner.cursor
    return Span(start.start, max(start.end, finish))


class _Scanner:
    """Locates inline tokens in the source by scanning forward.

    Strictly forward: the cursor never moves back. markdown-it emits inline
    tokens in document order, so a token found *before* an earlier one would
    mean the scan has lost its place, and a wrong offset here is exactly the
    failure this whole design exists to prevent.
    """

    def __init__(self, source: str, region: Span) -> None:
        self.source = source
        self.region = region
        self.cursor = region.start
        self.lost = False

    def locate(self, needle: str) -> Optional[Span]:
        """Find `needle` at or after the cursor, advancing past it."""
        if self.lost or not needle:
            return None
        found = self.source.find(needle, self.cursor, self.region.end)
        if found < 0:
            # One retry collapsing internal whitespace: Markdown joins wrapped
            # lines, so a token's content can span a line break that the source
            # writes as "\n" and the token writes as " ".
            found = self._find_whitespace_insensitive(needle)
        if found is None or found < 0:
            self.lost = True
            return None
        end = found + self._matched_length(needle, found)
        self.cursor = end
        return Span(found, end)

    def try_locate(self, needle: str) -> Optional[Span]:
        """Locate `needle` without failing the scan if it is absent."""
        if self.lost or not needle:
            return None
        found = self.source.find(needle, self.cursor, self.region.end)
        if found < 0:
            return None
        self.cursor = found + len(needle)
        return Span(found, self.cursor)

    def position_span(self) -> Span:
        """A zero-width span at the current cursor."""
        return Span(self.cursor, self.cursor)

    def _find_whitespace_insensitive(self, needle: str) -> Optional[int]:
        """Locate `needle` allowing any run of whitespace to match any other.

        Returns the start offset, and leaves `_matched_length` able to report
        how much source the match actually consumed.
        """
        self._matched: Optional[tuple[int, int]] = None
        source, start, limit = self.source, self.cursor, self.region.end
        needle_parts = needle.split()
        if not needle_parts:
            return None

        cursor = start
        while True:
            first = source.find(needle_parts[0], cursor, limit)
            if first < 0:
                return None
            position = first + len(needle_parts[0])
            ok = True
            for part in needle_parts[1:]:
                gap = position
                while gap < limit and source[gap].isspace():
                    gap += 1
                if not source.startswith(part, gap):
                    ok = False
                    break
                position = gap + len(part)
            if ok:
                self._matched = (first, position)
                return first
            cursor = first + 1

    def _matched_length(self, needle: str, found: int) -> int:
        matched = getattr(self, "_matched", None)
        if matched and matched[0] == found:
            self._matched = None
            return matched[1] - found
        return len(needle)
