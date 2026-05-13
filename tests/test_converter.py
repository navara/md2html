"""Smoke tests for the md2html converter."""

from __future__ import annotations

from pathlib import Path

import pytest

from md2html import TEMPLATES, convert

FIXTURES = Path(__file__).parent / "fixtures"
KITCHEN_SINK = FIXTURES / "kitchen-sink.md"


@pytest.fixture(scope="module")
def kitchen_sink_md() -> str:
    return KITCHEN_SINK.read_text(encoding="utf-8")


@pytest.mark.parametrize("template", TEMPLATES)
def test_renders_for_each_template(kitchen_sink_md: str, template: str) -> None:
    html = convert(kitchen_sink_md, template=template, source_path=KITCHEN_SINK)
    assert "<!doctype html>" in html.lower()
    assert "<style>" in html
    assert "<main class=\"md2html\">" in html
    # No external resource references.
    assert "<link rel=\"stylesheet\"" not in html.lower()
    assert "<script src" not in html.lower()
    # Title extracted from the first H1.
    assert "<title>Kitchen Sink</title>" in html


def test_pygments_classes_present(kitchen_sink_md: str) -> None:
    html = convert(kitchen_sink_md, template="github")
    # The Pygments fence renderer emits <div class="highlight">.
    assert 'class="highlight"' in html
    # Python keyword tokens get the .k class.
    assert ' class="k"' in html


def test_heading_anchors_present(kitchen_sink_md: str) -> None:
    html = convert(kitchen_sink_md, template="github", with_anchors=True)
    assert ' id="kitchen-sink"' in html
    assert "header-anchor" in html


def test_heading_anchors_disabled(kitchen_sink_md: str) -> None:
    html = convert(kitchen_sink_md, template="github", with_anchors=False)
    assert 'class="header-anchor"' not in html


def test_toc_only_when_requested(kitchen_sink_md: str) -> None:
    html_off = convert(kitchen_sink_md, template="github")
    html_on = convert(kitchen_sink_md, template="github", with_toc=True)
    assert '<nav class="md2html-toc"' not in html_off
    assert '<nav class="md2html-toc"' in html_on
    # TOC should link to actual heading ids.
    assert '<a href="#code"' in html_on


def test_inline_images(kitchen_sink_md: str, tmp_path: Path) -> None:
    html_off = convert(
        kitchen_sink_md,
        template="github",
        source_path=KITCHEN_SINK,
        inline_images=False,
    )
    assert 'src="sample.png"' in html_off

    html_on = convert(
        kitchen_sink_md,
        template="github",
        source_path=KITCHEN_SINK,
        inline_images=True,
    )
    assert "data:image/png;base64," in html_on
    assert 'src="sample.png"' not in html_on


def test_remote_image_not_inlined() -> None:
    md = "![alt](https://example.com/img.png)"
    html = convert(md, template="github", source_path=KITCHEN_SINK, inline_images=True)
    assert "https://example.com/img.png" in html


def test_tables_and_tasklists(kitchen_sink_md: str) -> None:
    html = convert(kitchen_sink_md, template="basic-light")
    assert "<table>" in html
    assert "task-list-item" in html
    assert 'type="checkbox"' in html


def test_unknown_language_falls_back() -> None:
    md = "```not-a-language\nsome text\n```\n"
    html = convert(md, template="minimal-light")
    assert "some text" in html
    # Falls back to plain pre/code, not Pygments tokens.
    assert "language-not-a-language" in html


def test_invalid_template_raises() -> None:
    with pytest.raises(ValueError):
        convert("# x", template="does-not-exist")


def test_all_twelve_templates_registered() -> None:
    expected = {
        "minimal-light", "minimal-dark", "basic-light", "basic-dark",
        "github", "polished",
        "solarized-light", "solarized-dark", "dracula", "nord",
        "gruvbox-dark", "midnight",
    }
    assert set(TEMPLATES) == expected


def test_default_widths_are_50_percent_wider(kitchen_sink_md: str) -> None:
    # The post-bump defaults: 70ch -> 105ch, 76ch -> 114ch (via _basic.css),
    # 980px -> 1470px, 68ch -> 102ch.
    assert "max-width: 105ch" in convert(kitchen_sink_md, template="minimal-light")
    assert "max-width: 105ch" in convert(kitchen_sink_md, template="minimal-dark")
    assert "max-width: 114ch" in convert(kitchen_sink_md, template="basic-light")
    assert "max-width: 114ch" in convert(kitchen_sink_md, template="basic-dark")
    assert "max-width: 1470px" in convert(kitchen_sink_md, template="github")
    assert "max-width: 102ch" in convert(kitchen_sink_md, template="polished")


@pytest.mark.parametrize(
    "template",
    ["solarized-light", "solarized-dark", "dracula", "nord", "gruvbox-dark", "midnight"],
)
def test_new_palette_templates_use_basic_shell(kitchen_sink_md: str, template: str) -> None:
    html = convert(kitchen_sink_md, template=template)
    # The _basic.css shell defines max-width: 114ch and uses the variable scaffolding.
    assert "max-width: 114ch" in html
    assert "--accent:" in html
    assert "--soft-bg:" in html


def test_width_override_numeric_treated_as_ch(kitchen_sink_md: str) -> None:
    html = convert(kitchen_sink_md, template="github", width="80")
    # Override is appended after the template, so the template's own max-width
    # still appears but the override should also be there.
    assert "max-width: 80ch" in html


def test_width_override_with_unit_passes_through(kitchen_sink_md: str) -> None:
    html = convert(kitchen_sink_md, template="dracula", width="1200px")
    assert "max-width: 1200px" in html


def test_width_override_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        convert("# x", template="github", width="; body { display:none } /*")


def test_midnight_has_neon_glow() -> None:
    html = convert("# Hello\n\n```py\nprint('hi')\n```", template="midnight")
    # The midnight palette adds neon glow rules on top of _basic.css.
    assert "text-shadow" in html
    assert "box-shadow" in html
