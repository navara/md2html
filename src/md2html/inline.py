"""Inline local images in rendered HTML as base64 data URIs."""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote

# Match the src attribute of <img> tags. Captures: (prefix, quote, value).
# The value uses ``.*?`` with the captured quote as the terminator so it
# correctly handles apostrophes inside double-quoted src (and vice versa).
_IMG_SRC_RE = re.compile(
    r'(<img\b[^>]*?\bsrc=)(["\'])(.*?)\2',
    re.IGNORECASE | re.DOTALL,
)

# Anything with a URL scheme (http:, https:, data:, file:, mailto:, ...) or a
# protocol-relative prefix is not a local file. A scheme needs two or more
# characters before the colon, so Windows drive paths like C:/x.png still
# count as local.
_NON_LOCAL_RE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]+:|//)")


def inline_images_in_html(html: str, *, base_dir: Path) -> str:
    """Replace `<img src="local/path.png">` with `<img src="data:...;base64,...">`.

    URLs with a scheme (`http:`, `https:`, `data:`, ...) and protocol-relative
    `//` URLs are left alone. So are files whose extension is not a known image
    type: without that guard, a document written by someone else could point an
    `<img>` at `../secrets.env` and have its contents baked into the output as
    base64. Missing files are left alone too, so the rendered file at least
    shows a broken image rather than blowing up.

    Relative paths that climb out of ``base_dir`` are still honoured, because
    a sibling `../assets/logo.png` is an ordinary and legitimate layout.
    """

    def replace(m: re.Match[str]) -> str:
        src = m.group(3).strip()
        if _NON_LOCAL_RE.match(src):
            return m.group(0)
        # markdown-it percent-encodes spaces and other unsafe URL chars in src,
        # but the file on disk has the literal characters, so decode first.
        decoded = unquote(src)
        path = (base_dir / decoded).resolve()
        mime, _ = mimetypes.guess_type(path.name)
        if mime is None or not mime.startswith("image/"):
            return m.group(0)
        try:
            data = path.read_bytes()
        except OSError:
            return m.group(0)
        b64 = base64.b64encode(data).decode("ascii")
        return f"{m.group(1)}{m.group(2)}data:{mime};base64,{b64}{m.group(2)}"

    return _IMG_SRC_RE.sub(replace, html)
