"""Check that a frozen md2html executable really works, not just that it starts.

Usage: python packaging/smoke_test.py <path-to-executable> <expected-version>

Covers what freezing tends to break: templates loaded as package data, Pygments
lexers and styles found by name at runtime, and the linkify extra.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

DOC = """# Smoke ![i](x.png)

See https://example.com now.

```python
def f():
    return 1
```
"""

# Each marker proves one piece survived freezing.
EXPECTED = {
    '<span class="k">def</span>': "Pygments python lexer",
    "prefers-color-scheme": "github template with its light and dark styles",
    '<a href="https://example.com">': "linkify",
    'id="smoke-"': "heading anchors",
}


def run(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        output = result.stdout + result.stderr
        sys.exit(f"FAIL: {args} exited {result.returncode}\n{output}")
    return result.stdout


def main() -> None:
    # Resolved because Windows will not run a relative path like dist/md2html.exe.
    exe, version = str(Path(sys.argv[1]).resolve()), sys.argv[2]

    reported = run(exe, "--version").strip()
    if reported != f"md2html {version}":
        sys.exit(f"FAIL: --version printed {reported!r}, expected 'md2html {version}'")
    print(f"ok: {reported}")

    if "github" not in run(exe, "--list-templates").split():
        sys.exit("FAIL: --list-templates does not list github")
    print("ok: templates listed")

    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp, "doc.md"), Path(tmp, "doc.html")
        src.write_text(DOC, encoding="utf-8")
        run(exe, str(src), "-t", "github", "-o", str(out))
        html = out.read_text(encoding="utf-8")

    missing = [what for marker, what in EXPECTED.items() if marker not in html]
    if missing:
        sys.exit(f"FAIL: rendered page lacks: {', '.join(missing)}")
    print(f"ok: rendered page has {', '.join(EXPECTED.values())}")


if __name__ == "__main__":
    main()
