"""md2html command-line entry point."""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from . import __version__
from .converter import DEFAULT_TEMPLATE, TEMPLATES, _normalize_width, convert

# How long a file must stay quiet before we re-render it, and how often the
# watch loop checks. One save is several filesystem events; the wait folds
# them into a single render.
_DEBOUNCE_SECONDS = 0.25
_POLL_SECONDS = 0.05


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
        help=(
            "Output file (when input is a file) or directory (when input is a "
            "directory). Defaults to alongside the source with .html extension. "
            "With a file input, a value that names an existing directory, ends "
            "in a path separator, or carries no file extension is treated as a "
            "directory to write into."
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
        help=(
            "Disable heading anchor links (on by default). With --toc, "
            "headings still get ids so the TOC links keep working."
        ),
    )
    p.add_argument(
        "--inline-images",
        action="store_true",
        help="Embed local images as base64 data URIs in the HTML",
    )
    p.add_argument(
        "--no-raw-html",
        action="store_true",
        help=(
            "Escape raw HTML in the source instead of passing it through. "
            "Raw HTML is allowed by default, which lets a document reference "
            "external scripts or styles; this flag guarantees the output is "
            "self-contained whatever the input contains."
        ),
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
        help="Re-render on file changes (Ctrl-C to stop). Implies --overwrite.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Replace existing .html output files. By default, an existing "
            "output is left untouched and a 'skipped' line is printed instead."
        ),
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

    if args.width is not None:
        try:
            _normalize_width(args.width)
        except ValueError as exc:
            parser.error(str(exc))

    options = {
        "template": args.template,
        "with_toc": args.toc,
        "with_anchors": not args.no_anchors,
        "inline_images": args.inline_images,
        "width": args.width,
        "allow_raw_html": not args.no_raw_html,
    }

    # Watch mode is opt-in for continuous regeneration, so it implies
    # --overwrite for both the initial render and every re-render.
    overwrite = args.overwrite or args.watch

    if src.is_file():
        out = _output_for_file(src, args.output)
        ok = _convert_one(src, out, options, overwrite=overwrite)
        if args.watch:
            _watch_file(src, out, options)
        return 0 if ok else 1
    else:
        out_dir = Path(args.output) if args.output else src
        files = _collect_md_files(src, recursive=args.recursive)
        if not files:
            print(f"No .md files found in {src}", file=sys.stderr)
            return 1
        failed = 0
        for f in files:
            target = _target_for(f, src, out_dir)
            if not _convert_one(f, target, options, overwrite=overwrite):
                failed += 1
        if args.watch:
            _watch_dir(src, out_dir, options, recursive=args.recursive)
        return 1 if failed else 0


def _output_for_file(src: Path, output: str | None) -> Path:
    """Resolve where a single-file conversion should be written.

    ``-o`` is read as a directory when it names one, ends in a separator, or
    has no extension. Without the last two rules, ``-o build/`` for a directory
    that does not exist yet would quietly produce a file called ``build``.
    """
    if output is None:
        return src.with_suffix(".html")
    out = Path(output)
    if out.is_dir() or output.endswith(("/", "\\")) or out.suffix == "":
        return out / (src.stem + ".html")
    return out


def _collect_md_files(directory: Path, recursive: bool) -> list[Path]:
    # Filter on the suffix rather than globbing "*.md": Path.glob is
    # case-sensitive on POSIX but not on Windows, so a glob would convert
    # README.MD on one platform and skip it on the other. _watch_dir already
    # compares suffixes case-insensitively; this matches it.
    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in directory.glob(pattern) if p.is_file() and p.suffix.lower() == ".md"
    )


def _target_for(source_file: Path, source_root: Path, output_root: Path) -> Path:
    rel = source_file.relative_to(source_root)
    return (output_root / rel).with_suffix(".html")


def _write_atomic(out: Path, text: str) -> None:
    """Write via a sibling temp file and rename it into place.

    A plain write truncates first, so an interrupted run (or a browser
    reloading mid-render in watch mode) can observe a half-written document.
    ``os.replace`` is atomic on both POSIX and Windows.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=out.parent, prefix=f".{out.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _convert_one(src: Path, out: Path, options: dict, *, overwrite: bool) -> bool:
    """Render one file. Returns False (after printing the error) on failure."""
    ts = datetime.now().strftime("%H:%M:%S")
    if out.exists() and not overwrite:
        print(f"[{ts}] skipped {out} (already exists; pass --overwrite to replace)")
        return True
    try:
        # utf-8-sig strips a leading BOM, common in files saved on Windows.
        markdown_text = src.read_text(encoding="utf-8-sig")
        html = convert(markdown_text, source_path=src, **options)
        _write_atomic(out, html)
    except Exception as exc:  # noqa: BLE001
        print(f"[{ts}] error   {src}: {exc}", file=sys.stderr)
        return False
    print(f"[{ts}] rendered {src} -> {out}")
    return True


class _Debouncer:
    """Collapse the burst of events one save produces into a single render.

    Editors emit several modify events per save, and atomic savers add a
    create and a rename on top, so an undebounced watcher renders the same
    file three or four times. Waiting for a quiet period also means we read
    the file after the editor has finished writing it rather than midway.

    ``now`` is passed in rather than read from the clock so the coalescing
    can be tested without sleeping.
    """

    def __init__(self, quiet: float = _DEBOUNCE_SECONDS) -> None:
        self._quiet = quiet
        self._pending: dict[Path, float] = {}
        self._lock = threading.Lock()

    def note(self, path: Path, now: float) -> None:
        with self._lock:
            self._pending[path] = now

    def due(self, now: float) -> list[Path]:
        """Pop the paths that have been quiet for long enough."""
        with self._lock:
            ready = sorted(
                p for p, seen in self._pending.items() if now - seen >= self._quiet
            )
            for path in ready:
                del self._pending[path]
        return ready


def _watch_target(
    changed: Path, src_root: Path, out_root: Path, recursive: bool
) -> Path | None:
    """Output path for a changed file under a watched directory, or None.

    ``changed`` and ``src_root`` are both resolved; ``out_root`` may be
    relative, since it is only ever joined onto.
    """
    if changed.suffix.lower() != ".md":
        return None
    try:
        rel = changed.relative_to(src_root)
    except ValueError:
        return None
    if not recursive and changed.parent != src_root:
        return None
    return (out_root / rel).with_suffix(".html")


def _watch(
    root: Path,
    *,
    recursive: bool,
    resolve: Callable[[Path], tuple[Path, Path] | None],
    options: dict,
    banner: str,
) -> None:
    """Watch ``root`` and re-render on change until interrupted.

    ``resolve`` maps a changed (resolved) path to the (source, output) pair
    to render, or None to ignore the event.
    """
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    pending = _Debouncer()

    def note(path_str) -> None:
        if not path_str:
            return
        # resolve() can fail on a path that vanished between event and handler.
        with contextlib.suppress(OSError):
            pending.note(Path(path_str).resolve(), time.monotonic())

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):  # type: ignore[override]
            if not event.is_directory:
                note(event.src_path)

        on_created = on_modified

        def on_moved(self, event):  # type: ignore[override]
            # Editors that save atomically write a temp file and rename it
            # over the original; that arrives as a move event.
            if not event.is_directory:
                note(getattr(event, "dest_path", None))

    observer = Observer()
    observer.schedule(Handler(), str(root), recursive=recursive)
    observer.start()
    print(banner)
    try:
        while True:
            time.sleep(_POLL_SECONDS)
            for changed in pending.due(time.monotonic()):
                job = resolve(changed)
                if job is not None:
                    _convert_one(*job, options, overwrite=True)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


def _watch_file(src: Path, out: Path, options: dict) -> None:
    src_resolved = src.resolve()

    def resolve(changed: Path) -> tuple[Path, Path] | None:
        # Report the path the user typed, not the resolved one.
        return (src, out) if changed == src_resolved else None

    _watch(
        src_resolved.parent,
        recursive=False,
        resolve=resolve,
        options=options,
        banner=f"Watching {src}. Ctrl-C to stop.",
    )


def _watch_dir(src_dir: Path, out_dir: Path, options: dict, recursive: bool) -> None:
    # Watchdog reports absolute paths, so compare and slice against the
    # resolved source root (src_dir itself may be relative).
    src_dir_resolved = src_dir.resolve()

    def resolve(changed: Path) -> tuple[Path, Path] | None:
        target = _watch_target(changed, src_dir_resolved, out_dir, recursive)
        return None if target is None else (changed, target)

    _watch(
        src_dir_resolved,
        recursive=recursive,
        resolve=resolve,
        options=options,
        banner=f"Watching {src_dir} (recursive={recursive}). Ctrl-C to stop.",
    )


if __name__ == "__main__":
    sys.exit(main())
