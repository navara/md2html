"""md2html — convert Markdown to a self-contained HTML file with themes."""

__version__ = "0.1.0"

from .converter import DEFAULT_TEMPLATE, TEMPLATES, convert

__all__ = ["__version__", "DEFAULT_TEMPLATE", "TEMPLATES", "convert"]
