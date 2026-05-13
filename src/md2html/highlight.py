"""Pygments-based syntax highlighting for fenced code blocks."""

from __future__ import annotations

from html import escape
from typing import Union

from pygments import highlight as _pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

# template name → Pygments style (str) or (light, dark) tuple for media-query swap
_TEMPLATE_PYGMENTS: dict[str, Union[str, tuple[str, str]]] = {
    "minimal-light": "default",
    "minimal-dark": "monokai",
    "basic-light": "friendly",
    "basic-dark": "dracula",
    "github": ("default", "github-dark"),
    "polished": "monokai",
    "solarized-light": "solarized-light",
    "solarized-dark": "solarized-dark",
    "dracula": "dracula",
    "nord": "nord",
    "gruvbox-dark": "gruvbox-dark",
    "midnight": "fruity",
}


def highlight_code(source: str, lang: str | None) -> str:
    """Render a fenced code block as `<div class="highlight"><pre>...</pre></div>`.

    Falls back to escaped plain text if the language is unknown or absent.
    """
    if lang:
        try:
            lexer = get_lexer_by_name(lang, stripall=False)
        except ClassNotFound:
            return _plain_fence(source, lang)
    else:
        lexer = TextLexer(stripall=False)
    formatter = HtmlFormatter(cssclass="highlight", nowrap=False)
    return _pygments_highlight(source, lexer, formatter)


def _plain_fence(source: str, lang: str) -> str:
    cls = f' class="language-{escape(lang)}"' if lang else ""
    return f'<div class="highlight"><pre><code{cls}>{escape(source)}</code></pre></div>'


def get_pygments_css(template: str) -> str:
    """Return CSS rules for the given template's chosen Pygments style.

    For the `github` template, light and dark styles are emitted with a
    `prefers-color-scheme: dark` media query for automatic theme switching.
    """
    style = _TEMPLATE_PYGMENTS.get(template, "default")
    if isinstance(style, tuple):
        light_style, dark_style = style
        light_css = HtmlFormatter(style=light_style).get_style_defs(".highlight")
        dark_css = HtmlFormatter(style=dark_style).get_style_defs(".highlight")
        return f"{light_css}\n@media (prefers-color-scheme: dark) {{\n{dark_css}\n}}"
    return HtmlFormatter(style=style).get_style_defs(".highlight")
