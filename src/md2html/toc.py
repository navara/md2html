"""Walk markdown-it tokens to extract document title and build a TOC."""

from __future__ import annotations

from collections.abc import Iterable
from html import escape


def extract_title_from_tokens(tokens) -> str | None:
    """Return the text of the first H1 in the token stream, or None."""
    for i, tok in enumerate(tokens):
        if tok.type != "heading_open" or tok.tag != "h1":
            continue
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

    parts: list[str] = [
        '<nav class="md2html-toc">',
        '<div class="md2html-toc-title">Contents</div>',
    ]
    # Stack of heading levels whose <ul> is currently open. A level jump
    # (h2 -> h4) opens a single nested list inside the open <li>, keeping the
    # output valid HTML: a <ul> is only ever a child of an <li> or the nav.
    open_levels: list[int] = []
    for level, slug, text in items:
        if not open_levels or level > open_levels[-1]:
            parts.append("<ul>")
            open_levels.append(level)
        else:
            parts.append("</li>")
            while len(open_levels) > 1 and open_levels[-2] >= level:
                parts.append("</ul></li>")
                open_levels.pop()
            open_levels[-1] = level
        parts.append(
            f'<li><a href="#{escape(slug, quote=True)}">{escape(text)}</a>'
        )

    parts.append("</li>")
    parts.append("</ul></li>" * (len(open_levels) - 1))
    parts.append("</ul>")
    parts.append("</nav>\n")
    return "".join(parts)


def _inline_text(children: Iterable) -> str:
    """Flatten inline tokens to readable plain text (drops emphasis, etc)."""
    out: list[str] = []
    for child in children:
        if child.type in ("text", "code_inline"):
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
