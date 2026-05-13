"""md2html command-line entry point."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from . import __version__
from .converter import DEFAULT_TEMPLATE, TEMPLATES, convert


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="md2html",
        description=(
            "Convert Markdown to a self-contained HTML file with themed CSS and "
            "syntax-highlighted code. Accepts a single .md file or a folder."
        ),
    )
    p.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Markdown file or directory containing .md files",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Output file (when input is a file) or directory (when input is a "
            "directory). Defaults to alongside the source with .html extension."
        ),
    )
    p.add_argument(
        "-t",
        "--template",
        default=DEFAULT_TEMPLATE,
        choices=TEMPLATES,
        help="Visual template to apply (default: %(default)s)",
    )
    p.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="When input is a directory, recurse into subdirectories",
    )
    p.add_argument(
        "--toc",
        action="store_true",
        help="Prepend an auto-generated table of contents",
    )
    p.add_argument(
        "--no-anchors",
        action="store_true",
        help="Disable heading anchor links (on by default)",
    )
    p.add_argument(
        "--inline-images",
        action="store_true",
        help="Embed local images as base64 data URIs in the HTML",
    )
    p.add_argument(
        "--width",
        help=(
            "Override the column width. Plain numbers are interpreted as "
            "ch (character widths); explicit units are passed through. "
            "Examples: 90, 80ch, 1200px, 60rem."
        ),
    )
    p.add_argument(
        "--watch",
        action="store_true",
        help="Re-render on file changes (Ctrl-C to stop)",
    )
    p.add_argument(
        "--list-templates",
        action="store_true",
        help="List available templates and exit",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"md2html {__version__}",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list_templates:
        for name in TEMPLATES:
            print(name)
        return 0

    if args.path is None:
        parser.error("path is required (or pass --list-templates / --version)")

    src: Path = args.path
    if not src.exists():
        parser.error(f"path not found: {src}")

    options = {
        "template": args.template,
        "with_toc": args.toc,
        "with_anchors": not args.no_anchors,
        "inline_images": args.inline_images,
        "width": args.width,
    }

    if src.is_file():
        out = args.output if args.output else src.with_suffix(".html")
        if out.is_dir():
            out = out / (src.stem + ".html")
        _convert_one(src, out, options)
        if args.watch:
            _watch_file(src, out, options)
    else:
        out_dir = args.output if args.output else src
        files = _collect_md_files(src, recursive=args.recursive)
        if not files:
            print(f"No .md files found in {src}", file=sys.stderr)
            return 1
        for f in files:
            target = _target_for(f, src, out_dir)
            _convert_one(f, target, options)
        if args.watch:
            _watch_dir(src, out_dir, options, recursive=args.recursive)
    return 0


def _collect_md_files(directory: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.md" if recursive else "*.md"
    return sorted(p for p in directory.glob(pattern) if p.is_file())


def _target_for(source_file: Path, source_root: Path, output_root: Path) -> Path:
    rel = source_file.relative_to(source_root)
    return (output_root / rel).with_suffix(".html")


def _convert_one(src: Path, out: Path, options: dict) -> None:
    markdown_text = src.read_text(encoding="utf-8")
    html = convert(markdown_text, source_path=src, **options)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] rendered {src} -> {out}")


def _watch_file(src: Path, out: Path, options: dict) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    src_resolved = src.resolve()

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):  # type: ignore[override]
            if event.is_directory:
                return
            if Path(event.src_path).resolve() != src_resolved:
                return
            try:
                _convert_one(src, out, options)
            except Exception as exc:  # noqa: BLE001
                print(f"Error: {exc}", file=sys.stderr)

    observer = Observer()
    observer.schedule(Handler(), str(src.parent), recursive=False)
    observer.start()
    print(f"Watching {src}. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def _watch_dir(src_dir: Path, out_dir: Path, options: dict, recursive: bool) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    src_dir_resolved = src_dir.resolve()

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):  # type: ignore[override]
            if event.is_directory:
                return
            p = Path(event.src_path)
            if p.suffix.lower() != ".md":
                return
            p_resolved = p.resolve()
            try:
                p_resolved.relative_to(src_dir_resolved)
            except ValueError:
                return
            if not recursive and p_resolved.parent != src_dir_resolved:
                return
            target = _target_for(p, src_dir, out_dir)
            try:
                _convert_one(p, target, options)
            except Exception as exc:  # noqa: BLE001
                print(f"Error: {exc}", file=sys.stderr)

        on_created = on_modified

    observer = Observer()
    observer.schedule(Handler(), str(src_dir), recursive=recursive)
    observer.start()
    print(f"Watching {src_dir} (recursive={recursive}). Ctrl-C to stop.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    sys.exit(main())
