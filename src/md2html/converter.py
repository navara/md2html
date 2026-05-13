"""Convert Markdown text to a self-contained HTML document."""

from __future__ import annotations

import re
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
    r"^\s*\d+(?:\.\d+)?\s*(?:ch|px|em|rem|vw|vh|%|pc|pt|cm|mm|in)?\s*$"
)


def _load_resource(name: str) -> str:
    return resources.files("md2html.templates").joinpath(name).read_text(encoding="utf-8")


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


def _make_md(with_anchors: bool) -> MarkdownIt:
    md = MarkdownIt(
        "gfm-like",
        {"html": True, "linkify": True, "typographer": False, "breaks": False},
    )
    if with_anchors:
        md.use(
            anchors_plugin,
            min_level=1,
            max_level=6,
            permalink=True,
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
    """Convert markdown text into a complete, self-contained HTML document."""
    if template not in TEMPLATES:
        raise ValueError(
            f"Unknown template {template!r}. Choose from: {', '.join(TEMPLATES)}"
        )

    md = _make_md(with_anchors=with_anchors)
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
    out = base_html
    for marker, value in replacements.items():
        out = out.replace(marker, value)
    return out


def _html_escape_title(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
