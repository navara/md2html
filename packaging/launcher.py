"""Entry script for the PyInstaller build.

PyInstaller runs its entry script as a top-level module, so the relative import in
md2html/__main__.py would fail there; this one imports the package absolutely.
"""

from md2html.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
