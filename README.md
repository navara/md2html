# md2html

Convert Markdown files to **self-contained HTML** — no external CSS, no external JS,
optionally no external images. Twelve built-in themes, Pygments syntax highlighting,
and a watch mode for live preview.

## Features

- **CommonMark + GFM** — tables, task lists, strikethrough, autolinks
- **Plus**: footnotes, definition lists, heading anchors with slug ids
- **Twelve themes**: `minimal-light`, `minimal-dark`, `basic-light`, `basic-dark`,
  `github` (auto light/dark via `prefers-color-scheme`), `polished`,
  `solarized-light`, `solarized-dark`, `dracula`, `nord`, `gruvbox-dark`, `midnight`
- **Syntax highlighting** via Pygments (all 500+ supported languages)
- **Self-contained output**: all CSS inlined; pass `--inline-images` to embed
  local images as base64 data URIs too (only files with a recognised image
  extension are embedded, so a stray `<img src="../secrets.env">` cannot
  smuggle itself into the output)
- **Raw HTML** in the source is passed through verbatim, as CommonMark
  specifies. Nothing md2html emits reaches the network, but a document that
  writes its own `<script src="https://...">` still can, so `--no-raw-html`
  escapes raw HTML to text when the self-contained property has to hold for
  input you did not write
- **Configurable column width** — sensible defaults per template, override
  with `--width`
- **Batch mode**: point it at a directory and every `.md` becomes `.html`;
  a file that fails is reported on stderr, the rest still render, and the
  exit code is non-zero
- **Watch mode**: re-render on save for live preview
- **Auto TOC**: pass `--toc` to prepend a navigable table of contents
  (headings get ids for the TOC links even with `--no-anchors`)

## Install

From a checkout:

```bash
pip install -e .
```

Or with `pipx` to get an isolated CLI:

```bash
pipx install .
```

Requires Python 3.10+. Dependencies: `markdown-it-py[linkify]`, `mdit-py-plugins`,
`Pygments`, `watchdog`.

## Usage

```bash
# Convert one file (output: doc.html next to doc.md)
md2html doc.md

# Choose a template
md2html doc.md -t github
md2html doc.md -t polished

# Send output somewhere else
md2html doc.md -o /tmp/out.html    # a value with an extension is a file
md2html doc.md -o /tmp/site        # no extension (or a trailing separator)
                                   # means a directory: /tmp/site/doc.html

# Convert every .md in a folder, output alongside sources
md2html ./docs

# Convert recursively into a mirrored output tree
md2html ./docs -r -o ./site -t github

# Add a table of contents
md2html doc.md --toc

# Replace an existing output (skip-existing is the default)
md2html doc.md --overwrite
md2html ./docs --overwrite          # regenerate the whole folder

# Embed local images as data URIs (truly portable)
md2html doc.md --inline-images

# Escape raw HTML rather than passing it through
md2html doc.md --no-raw-html

# Override column width (plain number = ch; unit accepted otherwise)
md2html doc.md --width 90          # 90ch
md2html doc.md --width 1200px      # explicit px
md2html doc.md --width 70rem       # rem also works

# Watch for changes and re-render
md2html doc.md --watch

# List available templates
md2html --list-templates
```

Or run as a module without installing the CLI shim:

```bash
python -m md2html doc.md -t github
```

## Templates

| Template          | Look                                                       | Pygments style    |
| ----------------- | ---------------------------------------------------------- | ----------------- |
| `minimal-light`   | White, system sans, almost no chrome                       | `default`         |
| `minimal-dark`    | Near-black counterpart                                     | `monokai`         |
| `basic-light`     | White with accent color, bordered tables and code          | `friendly`        |
| `basic-dark`      | GitHub-ish dark counterpart                                | `dracula`         |
| `github`          | Faithful GH-README look, auto adapts to system theme       | github light/dark |
| `polished`        | Warm cream paper, serif body, sans headings, accents       | `monokai`         |
| `solarized-light` | The classic Solarized cream palette                        | `solarized-light` |
| `solarized-dark`  | Solarized teal-dark counterpart                            | `solarized-dark`  |
| `dracula`         | Dracula — purple / pink / cyan on `#282a36`                | `dracula`         |
| `nord`            | Nord — frosty blues on cool slate                          | `nord`            |
| `gruvbox-dark`    | Warm yellow + brown on dark, retro Gruvbox look            | `gruvbox-dark`    |
| `midnight`        | Deep navy with cyan/magenta neon glow on headings and code | `fruity`          |

Most templates share a common stylesheet (`_basic.css`) and customize only the
palette via CSS variables — adding a new theme is one file with ~10 lines.
Templates with unique typography (`minimal-*`, `github`, `polished`) stand on
their own.

All styles are scoped under `main.md2html` so embedding the rendered HTML into
another page won't leak styles.

### Column width

All templates default to a `1470px` reading column (matching `github`) for
visual consistency across themes. Pass `--width` to override:

```bash
md2html doc.md --width 80          # 80ch
md2html doc.md --width 1280px      # exact pixel width
md2html doc.md --width 60rem       # any CSS length unit works
```

Plain numbers are interpreted as `ch` (character widths). Anything else is
passed through after a sanity check.

## Programmatic use

```python
from md2html import convert

html = convert(
    "# Hello\n\nSome **markdown**.",
    template="github",
    with_toc=True,
)
```

`convert()` returns the complete HTML document as a string.

## Development

### With [uv](https://docs.astral.sh/uv/) (recommended)

```bash
uv sync                    # creates .venv, installs editable + locked dev deps
uv run pytest              # run tests
uv run md2html doc.md      # run the CLI without activating the venv
uv build                   # build wheel + sdist into dist/
```

`uv.lock` is committed so every contributor and CI run gets bit-identical
transitive dependencies.

### With stock pip / venv

```bash
py -m venv .venv
.venv\Scripts\python -m pip install -e . pytest build
.venv\Scripts\pytest
.venv\Scripts\python -m build
```

Tests live in `tests/test_converter.py` and exercise every template against
the `tests/fixtures/kitchen-sink.md` document.

## Out of scope

- Custom CSS injection — fork or extend the template files instead
- Mermaid / KaTeX rendering — they would require JS, breaking the
  self-contained guarantee
- PDF output

## License

MIT
