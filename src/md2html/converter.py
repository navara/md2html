"""Convert Markdown text to a self-contained HTML document."""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from .highlight import get_pygments_css, highlight_code
from .inline import inline_images_in_html
from .toc import build_toc_from_tokens, extract_title_from_tokens

TEMPLATES = (
    "minimal-light",
    "minimal-dark",
    "basic-light",
    "basic-dark",
    "github",
    "polished",
    "solarized-light",
    "solarized-dark",
    "dracula",
    "nord",
    "gruvbox-dark",
    "midnight",
)
DEFAULT_TEMPLATE = "github"

_EXTENDS_RE = re.compile(r"^\s*/\*!\s*@extends\s+([\w.\-]+)\s*\*/", re.MULTILINE)
_WIDTH_RE = re.compile(
    r"^\s*\d+(?:\.\d+)?(?:ch|px|em|rem|vw|vh|%|pc|pt|cm|mm|in)?\s*$"
)

# Match any image whose destination is not already wrapped in <angle brackets>.
# The paren body is captured whole (destination plus a possible title) and split
# up in ``_rewrite_image``; sorting the two apart in the regex itself cannot be
# done reliably, because the space before a title looks exactly like a space
# inside a destination.
_IMG_DEST_RE = re.compile(
    r"""
    (!\[(?:[^\]\\\n]|\\.)*\])     # 1: ![alt]
    \(\s*                          # opening paren + optional space
    ((?!<)[^()\n<>]*?)             # 2: destination, plus any title
    \s*\)                          # closing paren (allow trailing whitespace)
    """,
    re.VERBOSE,
)

# A quoted title at the very end of the paren body, e.g. ``dest "the title"``.
_TRAILING_TITLE_RE = re.compile(r"""\s+("[^"\n]*"|'[^'\n]*')$""")

# An inline code span: a run of backticks closed by a run of the same length.
# Spans may wrap across lines but never across a blank line, since that ends
# the enclosing block.
_CODE_SPAN_RE = re.compile(
    r"(?<!`)(`+)(?!`)(?:(?!\n[ \t]*\n).)+?(?<!`)\1(?!`)", re.DOTALL
)


def _rewrite_image(m: re.Match[str]) -> str:
    """Bracket an image destination that contains spaces; else leave it as-is.

    Any trailing quoted title is preserved outside the angle brackets, where
    CommonMark expects it.
    """
    body = m.group(2).strip()
    title = ""
    tm = _TRAILING_TITLE_RE.search(body)
    if tm:
        title = " " + tm.group(1)
        body = body[: tm.start()].rstrip()
    # A body that opens with a quote is malformed rather than a spacey path,
    # and a body without whitespace already parses fine.
    if not body or body[0] in "\"'" or not any(c.isspace() for c in body):
        return m.group(0)
    return f"{m.group(1)}(<{body}>{title})"


@lru_cache(maxsize=1)
def _structure_parser() -> MarkdownIt:
    """Parser used only to locate verbatim blocks; inline work is wasted here."""
    return MarkdownIt("gfm-like", {"html": True, "linkify": False})


def _verbatim_line_numbers(md_text: str) -> set[int]:
    """0-based line numbers whose content must be passed through untouched.

    Covers fenced code, indented code and raw HTML blocks. Asking the real
    block parser avoids the indentation heuristics a line scanner would need
    (and which get list items wrong: four spaces inside a list is content,
    not code).
    """
    lines: set[int] = set()
    for tok in _structure_parser().parse(md_text):
        if tok.type in ("fence", "code_block", "html_block") and tok.map:
            lines.update(range(tok.map[0], tok.map[1]))
    return lines


def _rewrite_outside_code_spans(text: str) -> str:
    out: list[str] = []
    pos = 0
    for m in _CODE_SPAN_RE.finditer(text):
        out.append(_IMG_DEST_RE.sub(_rewrite_image, text[pos : m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_IMG_DEST_RE.sub(_rewrite_image, text[pos:]))
    return "".join(out)


def _normalize_image_urls(md_text: str) -> str:
    """Wrap unbracketed image destinations that contain spaces in <...>.

    CommonMark refuses spaces in unbracketed link destinations, which makes
    ``![alt](path/with spaces.jpg)`` fall back to plain text. Tools that emit
    markdown from PDFs frequently produce exactly this pattern. Re-emitting
    the destination as ``<path/with spaces.jpg>`` makes markdown-it parse it
    as an image. Already-bracketed destinations are left alone, as is anything
    the reader is meant to see verbatim: fenced and indented code blocks, raw
    HTML blocks, and inline code spans.
    """
    # Nothing to fix in the overwhelming majority of documents, and this check
    # is far cheaper than the extra parse below.
    if not any(
        _rewrite_image(m) != m.group(0) for m in _IMG_DEST_RE.finditer(md_text)
    ):
        return md_text

    verbatim = _verbatim_line_numbers(md_text)
    chunks: list[str] = []
    buf: list[str] = []
    # Split on "\n" rather than splitlines(): markdown-it counts lines the same
    # way, whereas splitlines() also breaks on \x0b, \x0c and U+2028, which
    # would knock our indices out of step with the token maps.
    for i, line in enumerate(md_text.split("\n")):
        if i in verbatim:
            if buf:
                chunks.append(_rewrite_outside_code_spans("\n".join(buf)))
                buf.clear()
            chunks.append(line)
        else:
            buf.append(line)
    if buf:
        chunks.append(_rewrite_outside_code_spans("\n".join(buf)))
    return "\n".join(chunks)


@lru_cache(maxsize=None)
def _load_resource(name: str) -> str:
    return resources.files("md2html.templates").joinpath(name).read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _load_template_css(template: str) -> str:
    text = _load_resource(f"{template}.css")
    m = _EXTENDS_RE.search(text[:200])
    if m:
        parent = _load_resource(m.group(1))
        text = parent + "\n" + text
    return text


def _normalize_width(value: str) -> str:
    v = value.strip()
    if not _WIDTH_RE.match(v):
        raise ValueError(
            f"Invalid --width value {value!r}. Use a number (interpreted as ch) "
            "or a length with unit, e.g. '80', '90ch', '1200px', '60rem'."
        )
    return f"{v}ch" if v.replace(".", "", 1).isdigit() else v


@lru_cache(maxsize=None)
def _make_md(with_anchors: bool, with_heading_ids: bool) -> MarkdownIt:
    md = MarkdownIt(
        "gfm-like",
        {"html": True, "linkify": True, "typographer": False, "breaks": False},
    )
    if with_anchors or with_heading_ids:
        md.use(
            anchors_plugin,
            min_level=1,
            max_level=6,
            permalink=with_anchors,
            permalinkSymbol="#",
            permalinkBefore=False,
            permalinkSpace=True,
        )
    md.use(footnote_plugin)
    md.use(deflist_plugin)
    md.use(tasklists_plugin, enabled=True)

    def fence(tokens, idx, options, env):
        token = tokens[idx]
        info = (token.info or "").strip()
        lang = info.split()[0] if info else None
        return highlight_code(token.content, lang) + "\n"

    md.renderer.rules["fence"] = fence
    return md


def convert(
    source_md: str,
    *,
    template: str = DEFAULT_TEMPLATE,
    source_path: Path | None = None,
    with_anchors: bool = True,
    with_toc: bool = False,
    inline_images: bool = False,
    width: str | None = None,
    title_override: str | None = None,
) -> str:
    """Convert markdown text into a complete, self-contained HTML document.

    ``with_toc=True`` always gives headings ids (needed for the TOC links),
    even when ``with_anchors=False`` suppresses the visible permalink anchors.
    """
    if template not in TEMPLATES:
        raise ValueError(
            f"Unknown template {template!r}. Choose from: {', '.join(TEMPLATES)}"
        )

    source_md = _normalize_image_urls(source_md)

    # A TOC needs heading ids even when visible anchor links are disabled.
    md = _make_md(with_anchors, with_toc)
    env: dict = {}
    tokens = md.parse(source_md, env)
    body_html = md.renderer.render(tokens, md.options, env)

    title = title_override or extract_title_from_tokens(tokens) or (
        source_path.stem if source_path else "Document"
    )
    toc_html = build_toc_from_tokens(tokens) if with_toc else ""

    if inline_images and source_path is not None:
        body_html = inline_images_in_html(body_html, base_dir=source_path.parent)

    template_css = _load_template_css(template)
    if width:
        normalized = _normalize_width(width)
        template_css += f"\nmain.md2html {{ max-width: {normalized}; }}\n"
    pygments_css = get_pygments_css(template)
    base_html = _load_resource("base.html")

    replacements = {
        "<!--MD2HTML:TITLE-->": _html_escape_title(title),
        "<!--MD2HTML:TEMPLATE_CSS-->": template_css,
        "<!--MD2HTML:PYGMENTS_CSS-->": pygments_css,
        "<!--MD2HTML:TOC-->": toc_html,
        "<!--MD2HTML:BODY-->": body_html,
    }
    # Single pass, so a marker string occurring in the document content is
    # never itself substituted.
    marker_re = re.compile("|".join(map(re.escape, replacements)))
    return marker_re.sub(lambda m: replacements[m.group(0)], base_html)


def _html_escape_title(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
