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

# Match an image whose destination contains a space but is not already wrapped
# in <angle brackets>. CommonMark only permits spaces in bracketed destinations,
# so unbracketed ones with spaces (common in markdown generated from PDFs)
# silently fail to parse as images. We rewrite them to the bracketed form.
_UNBRACKETED_IMG_WITH_SPACE_RE = re.compile(
    r"""
    (!\[(?:[^\]\\\n]|\\.)*\])     # 1: ![alt]
    \(\s*                          # opening paren + optional space
    ((?!<)                         # destination must not already start with <
        [^()\s<>][^()\n<>"]*?      # at least one non-space char, then anything
        \s                         # require at least one literal space
        [^()\n<>"]*?               # more dest chars (no quote so we don't slurp titles)
    )
    \s*\)                          # closing paren (allow trailing whitespace)
    """,
    re.VERBOSE,
)


_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")


def _normalize_image_urls(md_text: str) -> str:
    """Wrap unbracketed image destinations that contain spaces in <...>.

    CommonMark refuses spaces in unbracketed link destinations, which makes
    ``![alt](path/with spaces.jpg)`` fall back to plain text. Tools that emit
    markdown from PDFs frequently produce exactly this pattern. Re-emitting
    the destination as ``<path/with spaces.jpg>`` makes markdown-it parse it
    as an image. Titles like ``![alt](dest "title")`` and already-bracketed
    destinations are left alone, as is anything inside a fenced code block.
    """

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}(<{m.group(2).strip()}>)"

    out: list[str] = []
    fence: tuple[str, int] | None = None  # (fence char, opening run length)
    for line in md_text.splitlines(keepends=True):
        if fence is not None:
            out.append(line)
            m = _FENCE_CLOSE_RE.match(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]:
                fence = None
            continue
        m = _FENCE_OPEN_RE.match(line)
        if m:
            fence = (m.group(1)[0], len(m.group(1)))
            out.append(line)
            continue
        out.append(_UNBRACKETED_IMG_WITH_SPACE_RE.sub(repl, line))
    return "".join(out)


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
