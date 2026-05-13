"""Walk markdown-it tokens to extract document title and build a TOC."""

from __future__ import annotations

from html import escape
from typing import Iterable


def extract_title_from_tokens(tokens) -> str | None:
    """Return the text of the first H1 in the token stream, or None."""
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h1":
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                return _inline_text(tokens[i + 1].children or [])
    return None


def build_toc_from_tokens(tokens) -> str:
    """Return a `<nav class="md2html-toc">` block of nested heading links.

    Skips H1 (the document title) so the TOC starts at H2. Each item links to
    the heading's id (added by the anchors plugin).
    """
    items: list[tuple[int, str, str]] = []  # (level, slug, text)
    for i, tok in enumerate(tokens):
        if tok.type != "heading_open":
            continue
        level = int(tok.tag[1])
        if level < 2:
            continue
        slug = _get_attr(tok, "id") or ""
        text = ""
        if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
            text = _inline_text(tokens[i + 1].children or [])
        if not slug or not text:
            continue
        items.append((level, slug, text))

    if not items:
        return ""

    min_level = min(level for level, _, _ in items)
    parts: list[str] = [
        '<nav class="md2html-toc">',
        '<div class="md2html-toc-title">Contents</div>',
    ]
    prev_level = min_level - 1
    li_open = False
    for level, slug, text in items:
        if level > prev_level:
            for _ in range(level - prev_level):
                parts.append("<ul>")
        elif level < prev_level:
            if li_open:
                parts.append("</li>")
                li_open = False
            for _ in range(prev_level - level):
                parts.append("</ul></li>")
        else:
            if li_open:
                parts.append("</li>")
                li_open = False
        parts.append(
            f'<li><a href="#{escape(slug, quote=True)}">{escape(text)}</a>'
        )
        li_open = True
        prev_level = level

    if li_open:
        parts.append("</li>")
    for _ in range(prev_level - min_level + 1):
        parts.append("</ul>")
    parts.append("</nav>\n")
    return "".join(parts)


def _inline_text(children: Iterable) -> str:
    """Flatten inline tokens to readable plain text (drops emphasis, etc)."""
    out: list[str] = []
    for child in children:
        if child.type == "text":
            out.append(child.content)
        elif child.type == "code_inline":
            out.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            out.append(" ")
        elif getattr(child, "children", None):
            out.append(_inline_text(child.children))
    return "".join(out).strip()


def _get_attr(token, name: str) -> str | None:
    """Look up an attribute on a markdown-it Token, regardless of attrs format."""
    if not token.attrs:
        return None
    if isinstance(token.attrs, dict):
        return token.attrs.get(name)
    for k, v in token.attrs:
        if k == name:
            return v
    return None
