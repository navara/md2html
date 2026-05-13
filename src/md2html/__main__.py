"""Allow `python -m md2html`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
