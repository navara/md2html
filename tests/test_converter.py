"""Smoke tests for the md2html converter."""

from __future__ import annotations

import os
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


def test_uppercase_scheme_image_not_inlined() -> None:
    md = "![alt](HTTPS://example.com/img.png)"
    html = convert(md, template="github", source_path=KITCHEN_SINK, inline_images=True)
    assert "HTTPS://example.com/img.png" in html


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


@pytest.mark.parametrize("template", list(TEMPLATES))
def test_default_width_is_uniform(kitchen_sink_md: str, template: str) -> None:
    # Every template ships the same 1470px reading column so the rendered output
    # looks consistently wide regardless of which theme is chosen.
    html = convert(kitchen_sink_md, template=template)
    assert "max-width: 1470px" in html


@pytest.mark.parametrize(
    "template",
    ["solarized-light", "solarized-dark", "dracula", "nord", "gruvbox-dark", "midnight"],
)
def test_new_palette_templates_use_basic_shell(kitchen_sink_md: str, template: str) -> None:
    html = convert(kitchen_sink_md, template=template)
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


def test_width_override_rejects_space_between_number_and_unit() -> None:
    # "80 px" would be emitted verbatim and is not valid CSS.
    with pytest.raises(ValueError):
        convert("# x", template="github", width="80 px")


def test_toc_without_anchors_still_has_ids_and_links() -> None:
    md = "# Title\n\n## Section One\n"
    html = convert(md, template="github", with_anchors=False, with_toc=True)
    assert '<nav class="md2html-toc"' in html
    assert '<a href="#section-one"' in html
    assert 'id="section-one"' in html
    # But no visible permalink anchors were requested.
    assert 'class="header-anchor"' not in html


def test_toc_with_skipped_heading_levels_is_valid_html() -> None:
    md = "# T\n\n## A\n\n#### B\n\n## C\n"
    html = convert(md, template="github", with_toc=True)
    toc = html.split('<nav class="md2html-toc">')[1].split("</nav>")[0]
    # A <ul> must never be a direct child of another <ul>.
    assert "<ul><ul>" not in toc
    assert toc.count("<ul>") == toc.count("</ul>")
    assert toc.count("<li>") == toc.count("</li>")
    for slug in ("#a", "#b", "#c"):
        assert f'href="{slug}"' in toc


def test_heading_without_sluggable_text_gets_a_usable_id() -> None:
    """An image-only heading slugifies to "", an invalid id whose permalink
    just jumps to the top of the page."""
    html = convert("# T\n\n## ![img](x.png)\n", template="github", with_anchors=True)
    assert 'id=""' not in html
    assert 'href="#"' not in html
    assert 'id="section"' in html
    assert 'href="#section"' in html


def test_fallback_heading_ids_stay_unique() -> None:
    html = convert("# T\n\n## ![a](x.png)\n\n## !!!\n", template="github")
    assert 'id="section"' in html
    assert 'id="section-1"' in html


def test_ordinary_heading_ids_are_unchanged_by_the_fallback() -> None:
    html = convert("# Title\n\n## Same\n\n## Same\n", template="github")
    for slug in ('id="title"', 'id="same"', 'id="same-1"'):
        assert slug in html
    assert "section" not in html


def test_midnight_has_neon_glow() -> None:
    html = convert("# Hello\n\n```py\nprint('hi')\n```", template="midnight")
    # The midnight palette adds neon glow rules on top of _basic.css.
    assert "text-shadow" in html
    assert "box-shadow" in html


# --- regression: image URLs with spaces (and apostrophes) ---


def test_image_url_with_spaces_renders_as_img() -> None:
    """CommonMark forbids spaces in unbracketed image destinations; pdf2mdml
    and similar tools commonly emit them anyway. We auto-bracket them."""
    md = "![Image](images/Foo Bar.jpg)"
    html = convert(md, template="minimal-light")
    assert "<img " in html
    # markdown-it percent-encodes the space when rendering, which is fine.
    assert 'src="images/Foo%20Bar.jpg"' in html
    # The literal markdown should NOT survive as plain text.
    assert "![Image](images/Foo Bar.jpg)" not in html


def test_image_url_with_apostrophe_and_spaces() -> None:
    md = "![Image](images/Adventurer's Guide-1-1.jpg)"
    html = convert(md, template="minimal-light")
    assert "<img " in html
    assert "Adventurer's%20Guide-1-1.jpg" in html


def test_already_bracketed_image_url_is_untouched() -> None:
    md = "![Image](<images/Already Bracketed.jpg>)"
    html = convert(md, template="minimal-light")
    assert "<img " in html
    # We must not produce double angle-brackets like (<<...>>).
    assert "<<" not in html


def test_image_url_with_title_left_alone_when_no_space_in_dest() -> None:
    md = '![alt](file.jpg "the title")'
    html = convert(md, template="minimal-light")
    assert "<img " in html
    assert 'title="the title"' in html


def test_image_with_space_inside_code_fence_is_untouched() -> None:
    """The space-in-destination rewrite must not alter fenced code content."""
    md = "```\n![Image](images/Foo Bar.jpg)\n```\n"
    html = convert(md, template="minimal-light")
    assert "![Image](images/Foo Bar.jpg)" in html
    assert "&lt;images/Foo Bar.jpg&gt;" not in html
    assert "<img " not in html


def test_image_after_code_fence_is_still_normalized() -> None:
    md = "```\ncode\n```\n\n![Image](images/Foo Bar.jpg)\n"
    html = convert(md, template="minimal-light")
    assert 'src="images/Foo%20Bar.jpg"' in html


# --- CLI: skip-existing default and --overwrite ---


def test_cli_skips_existing_output_by_default(tmp_path: Path, capsys) -> None:
    from md2html.cli import main

    src = tmp_path / "doc.md"
    out = tmp_path / "doc.html"
    src.write_text("# Hello", encoding="utf-8")
    assert main([str(src), "-o", str(out)]) == 0
    first = out.read_text(encoding="utf-8")
    assert "Hello" in first

    # Modify the source. Re-running without --overwrite should NOT update the
    # output and should announce the skip.
    src.write_text("# Hello World", encoding="utf-8")
    capsys.readouterr()  # drain prior output
    assert main([str(src), "-o", str(out)]) == 0
    captured = capsys.readouterr()
    assert "skipped" in captured.out
    assert out.read_text(encoding="utf-8") == first


def test_cli_overwrite_flag_replaces_existing_output(tmp_path: Path) -> None:
    from md2html.cli import main

    src = tmp_path / "doc.md"
    out = tmp_path / "doc.html"
    src.write_text("# Hello", encoding="utf-8")
    main([str(src), "-o", str(out)])
    first = out.read_text(encoding="utf-8")

    src.write_text("# Hello World", encoding="utf-8")
    assert main([str(src), "-o", str(out), "--overwrite"]) == 0
    second = out.read_text(encoding="utf-8")
    assert second != first
    assert "Hello World" in second


def test_cli_directory_mode_mixes_skip_and_render(tmp_path: Path, capsys) -> None:
    from md2html.cli import main

    src_dir = tmp_path / "docs"
    src_dir.mkdir()
    (src_dir / "a.md").write_text("# A", encoding="utf-8")
    (src_dir / "b.md").write_text("# B", encoding="utf-8")
    out_dir = tmp_path / "out"

    # First pass: both render.
    assert main([str(src_dir), "-o", str(out_dir)]) == 0
    assert (out_dir / "a.html").exists()
    assert (out_dir / "b.html").exists()

    # Delete one output, leave the other. Second pass should render only the
    # missing one and skip the surviving one.
    (out_dir / "a.html").unlink()
    capsys.readouterr()
    assert main([str(src_dir), "-o", str(out_dir)]) == 0
    captured = capsys.readouterr()
    assert "rendered" in captured.out  # a.html was missing
    assert "skipped" in captured.out  # b.html existed


def test_cli_returns_1_and_continues_after_bad_file(tmp_path: Path, capsys) -> None:
    from md2html.cli import main

    src_dir = tmp_path / "docs"
    src_dir.mkdir()
    (src_dir / "bad.md").write_bytes(b"\xff\xfenot utf-8 \xff")
    (src_dir / "good.md").write_text("# Good", encoding="utf-8")
    out_dir = tmp_path / "out"

    assert main([str(src_dir), "-o", str(out_dir)]) == 1
    captured = capsys.readouterr()
    assert "bad.md" in captured.err
    # The good file must still be rendered despite the earlier failure.
    assert (out_dir / "good.html").exists()


def test_cli_strips_utf8_bom(tmp_path: Path) -> None:
    from md2html.cli import main

    src = tmp_path / "doc.md"
    out = tmp_path / "doc.html"
    src.write_bytes(b"\xef\xbb\xbf# Title\n")
    assert main([str(src), "-o", str(out)]) == 0
    html = out.read_text(encoding="utf-8")
    assert "<title>Title</title>" in html
    assert "﻿" not in html


# --- regression: the space-in-destination rewrite must not touch verbatim text ---


def _body(html: str) -> str:
    return html.split('<main class="md2html">')[1].split("</main>")[0]


def test_image_with_space_inside_inline_code_is_untouched() -> None:
    """A code span shows markdown source verbatim; rewriting it corrupts it."""
    html = convert("Use `![Image](images/Foo Bar.jpg)` here.\n", template="minimal-light")
    assert "<code>![Image](images/Foo Bar.jpg)</code>" in html
    assert "<img " not in html


def test_image_with_space_inside_indented_code_is_untouched() -> None:
    html = convert("text\n\n    ![Image](images/Foo Bar.jpg)\n", template="minimal-light")
    assert "![Image](images/Foo Bar.jpg)" in _body(html)
    assert "&lt;images/Foo Bar.jpg&gt;" not in html
    assert "<img " not in html


def test_image_with_space_inside_html_block_is_untouched() -> None:
    html = convert(
        "<div>\n![Image](images/Foo Bar.jpg)\n</div>\n", template="minimal-light"
    )
    assert "![Image](images/Foo Bar.jpg)" in _body(html)
    assert "<img " not in html


def test_image_with_space_beside_a_code_span_is_still_normalized() -> None:
    """Guard against over-skipping: only the span itself is protected."""
    html = convert("See `code` then ![Image](images/Foo Bar.jpg)\n", template="minimal-light")
    assert 'src="images/Foo%20Bar.jpg"' in html


def test_image_with_space_inside_list_item_is_still_normalized() -> None:
    """Four spaces inside a list is list content, not an indented code block."""
    html = convert("- item\n\n    ![Image](images/Foo Bar.jpg)\n", template="minimal-light")
    assert 'src="images/Foo%20Bar.jpg"' in html


def test_image_with_spaces_and_single_quoted_title() -> None:
    """The title must survive outside the angle brackets, not land in the src."""
    html = convert("![alt](images/Foo Bar.jpg 'the title')\n", template="minimal-light")
    assert 'src="images/Foo%20Bar.jpg"' in html
    assert 'title="the title"' in html


def test_image_with_spaces_and_double_quoted_title() -> None:
    html = convert('![alt](images/Foo Bar.jpg "the title")\n', template="minimal-light")
    assert 'src="images/Foo%20Bar.jpg"' in html
    assert 'title="the title"' in html


# --- --inline-images must embed images only ---


def test_inline_images_skips_non_image_files(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    doc = tmp_path / "doc.md"
    doc.write_text("![x](secret.txt)\n", encoding="utf-8")
    html = convert(
        doc.read_text(encoding="utf-8"),
        template="github",
        source_path=doc,
        inline_images=True,
    )
    assert ";base64," not in html
    assert "TOP SECRET" not in html
    assert 'src="secret.txt"' in html


def test_inline_images_skips_non_image_reached_by_traversal(tmp_path: Path) -> None:
    (tmp_path / "secret.env").write_text("API_KEY=hunter2", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    doc = docs / "doc.md"
    doc.write_text("![x](../secret.env)\n", encoding="utf-8")
    html = convert(
        doc.read_text(encoding="utf-8"),
        template="github",
        source_path=doc,
        inline_images=True,
    )
    assert ";base64," not in html
    assert "hunter2" not in html


def test_inline_images_skips_unknown_extension(tmp_path: Path) -> None:
    (tmp_path / "blob.weird").write_bytes(b"\x00\x01\x02")
    doc = tmp_path / "doc.md"
    doc.write_text("![x](blob.weird)\n", encoding="utf-8")
    html = convert(
        doc.read_text(encoding="utf-8"),
        template="github",
        source_path=doc,
        inline_images=True,
    )
    assert ";base64," not in html


# --- CLI: file discovery, output resolution, atomic writes ---


def test_collect_md_files_is_case_insensitive(tmp_path: Path) -> None:
    """Path.glob('*.md') matches .MD on Windows but not on POSIX."""
    from md2html.cli import _collect_md_files

    for name in ("a.md", "B.MD", "c.Md", "d.txt"):
        (tmp_path / name).write_text("# x", encoding="utf-8")
    found = {p.name for p in _collect_md_files(tmp_path, recursive=False)}
    assert found == {"a.md", "B.MD", "c.Md"}


def test_cli_output_without_extension_is_treated_as_directory(tmp_path: Path) -> None:
    from md2html.cli import main

    src = tmp_path / "doc.md"
    src.write_text("# D", encoding="utf-8")
    outdir = tmp_path / "build"  # does not exist yet
    assert main([str(src), "-o", str(outdir)]) == 0
    assert outdir.is_dir()
    assert (outdir / "doc.html").is_file()


def test_cli_output_with_trailing_separator_is_treated_as_directory(
    tmp_path: Path,
) -> None:
    from md2html.cli import main

    src = tmp_path / "doc.md"
    src.write_text("# D", encoding="utf-8")
    outdir = tmp_path / "site.v2"  # a suffix, so only the separator marks it
    assert main([str(src), "-o", str(outdir) + os.sep]) == 0
    assert (outdir / "doc.html").is_file()


def test_cli_output_with_extension_is_a_file(tmp_path: Path) -> None:
    from md2html.cli import main

    src = tmp_path / "doc.md"
    src.write_text("# D", encoding="utf-8")
    out = tmp_path / "nested" / "page.html"
    assert main([str(src), "-o", str(out)]) == 0
    assert out.is_file()


def test_cli_leaves_no_temp_files_behind(tmp_path: Path) -> None:
    from md2html.cli import main

    src = tmp_path / "doc.md"
    src.write_text("# D", encoding="utf-8")
    out_dir = tmp_path / "out"
    assert main([str(src), "-o", str(out_dir)]) == 0
    assert [p.name for p in out_dir.iterdir()] == ["doc.html"]


def test_cli_failed_write_leaves_previous_output_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rename is the commit point, so a failure must not truncate the old file."""
    import md2html.cli as cli

    src = tmp_path / "doc.md"
    out = tmp_path / "doc.html"
    src.write_text("# First", encoding="utf-8")
    assert cli.main([str(src), "-o", str(out)]) == 0
    before = out.read_text(encoding="utf-8")

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    src.write_text("# Second", encoding="utf-8")
    monkeypatch.setattr(cli.os, "replace", boom)
    assert cli.main([str(src), "-o", str(out), "--overwrite"]) == 1
    assert out.read_text(encoding="utf-8") == before
    assert not [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]


# --- watch mode: event coalescing and target resolution ---


def test_debouncer_collapses_a_burst_into_one_render() -> None:
    """One save is several filesystem events; they must yield one render."""
    from md2html.cli import _Debouncer

    d = _Debouncer(quiet=0.25)
    doc = Path("a.md")
    for t in (0.00, 0.05, 0.10, 0.15):
        d.note(doc, t)
    assert d.due(0.20) == []  # still inside the quiet window
    assert d.due(0.40) == [doc]  # one render for the whole burst
    assert d.due(1.00) == []  # and not repeated afterwards


def test_debouncer_releases_each_path_on_its_own_timer() -> None:
    from md2html.cli import _Debouncer

    d = _Debouncer(quiet=0.25)
    a, b = Path("a.md"), Path("b.md")
    d.note(a, 0.0)
    d.note(b, 0.1)
    assert d.due(0.30) == [a]
    assert d.due(0.40) == [b]


def test_debouncer_renders_again_after_a_later_edit() -> None:
    from md2html.cli import _Debouncer

    d = _Debouncer(quiet=0.25)
    doc = Path("a.md")
    d.note(doc, 0.0)
    assert d.due(0.3) == [doc]
    d.note(doc, 1.0)
    assert d.due(1.3) == [doc]


def test_watch_target_mirrors_into_the_output_tree(tmp_path: Path) -> None:
    from md2html.cli import _watch_target

    root, out = tmp_path / "docs", tmp_path / "site"
    assert (
        _watch_target(root / "sub" / "a.md", root, out, recursive=True)
        == out / "sub" / "a.html"
    )
    assert _watch_target(root / "B.MD", root, out, recursive=False) == out / "B.html"


@pytest.mark.parametrize(
    "relative, recursive",
    [
        ("notes.txt", True),  # not markdown
        (".doc.html.ab12.tmp", True),  # our own atomic-write temp file
        ("sub/a.md", False),  # subdirectory, but not recursive
    ],
)
def test_watch_target_ignores_irrelevant_changes(
    tmp_path: Path, relative: str, recursive: bool
) -> None:
    from md2html.cli import _watch_target

    root, out = tmp_path / "docs", tmp_path / "site"
    assert _watch_target(root / relative, root, out, recursive=recursive) is None


def test_watch_target_ignores_paths_outside_the_root(tmp_path: Path) -> None:
    from md2html.cli import _watch_target

    root, out = tmp_path / "docs", tmp_path / "site"
    assert _watch_target(tmp_path / "elsewhere.md", root, out, recursive=True) is None


def test_inline_images_handles_apostrophes_in_src(tmp_path: Path) -> None:
    """Regression: the --inline-images regex used to fail when the src
    attribute contained an apostrophe inside double quotes."""
    img_dir = tmp_path / "imgs"
    img_dir.mkdir()
    img = img_dir / "Adventurer's-1-1.jpg"
    # A 1x1 valid JPEG is overkill; any bytes prove the read path.
    img.write_bytes(b"\xff\xd8\xff\xd9")
    src_md = tmp_path / "doc.md"
    src_md.write_text(
        f"![x](imgs/{img.name})\n", encoding="utf-8"
    )
    html = convert(
        src_md.read_text(encoding="utf-8"),
        template="github",
        source_path=src_md,
        inline_images=True,
    )
    assert "data:image/jpeg;base64," in html
    assert "Adventurer's-1-1.jpg" not in html  # original src replaced
