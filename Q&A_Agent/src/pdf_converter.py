"""
src/pdf_converter.py
────────────────────
Converts the Markdown output file to a styled PDF using:

    Markdown → HTML (via the `markdown` library)
        → PDF  (via `xhtml2pdf` / pisa — pure Python, cross-platform)

Fallback
────────
If xhtml2pdf is not installed, the module logs a clear error and raises
ImportError with installation instructions.

Public API
──────────
    convert_markdown_to_pdf(md_path, pdf_path) → Path
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── CSS theme embedded in the HTML template ────────────────────────────────────
_CSS = """
@page {
    size: letter;
    margin: 1in 1in 1in 1in;
}

body {
    font-family: "Helvetica", "Arial", sans-serif;
    font-size: 10.5pt;
    line-height: 1.65;
    color: #212121;
}

h1 {
    font-size: 22pt;
    color: #1a237e;
    border-bottom: 2pt solid #1a237e;
    padding-bottom: 6pt;
    margin-bottom: 8pt;
}

h2 {
    font-size: 13pt;
    color: #0d47a1;
    margin-top: 18pt;
    margin-bottom: 6pt;
}

h3 {
    font-size: 11pt;
    color: #37474f;
}

p {
    margin: 0 0 8pt 0;
}

em {
    color: #546e7a;
}

strong {
    color: #1a237e;
}

ul {
    margin: 4pt 0 8pt 18pt;
    padding: 0;
}

li {
    margin-bottom: 4pt;
}

blockquote {
    background: #e8f5e9;
    border-left: 4pt solid #43a047;
    margin: 10pt 0 10pt 0;
    padding: 8pt 12pt;
    color: #1b5e20;
}

hr {
    border: none;
    border-top: 1pt solid #bdbdbd;
    margin: 14pt 0;
}

code {
    background: #f5f5f5;
    padding: 1pt 4pt;
    font-family: "Courier New", monospace;
    font-size: 9pt;
    border-radius: 2pt;
}

pre {
    background: #f5f5f5;
    padding: 10pt;
    font-size: 9pt;
    white-space: pre-wrap;
}

.correct-answer {
    color: #2e7d32;
    font-weight: bold;
}
"""

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <style>
{css}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


# ── Internal helpers ───────────────────────────────────────────────────────────

def _markdown_to_html(md_text: str) -> str:
    """Converts Markdown text to an HTML fragment using the `markdown` library."""
    try:
        import markdown as md_lib
    except ImportError as exc:
        raise ImportError(
            "The 'markdown' package is required. Install it with: "
            "pip install markdown"
        ) from exc

    extensions = ["extra", "nl2br", "sane_lists"]
    html_body = md_lib.markdown(md_text, extensions=extensions)
    return html_body


def _html_to_pdf(html: str, pdf_path: Path) -> None:
    """Renders *html* to a PDF file at *pdf_path* using xhtml2pdf."""
    try:
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise ImportError(
            "The 'xhtml2pdf' package is required. Install it with: "
            "pip install xhtml2pdf"
        ) from exc

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    # Encode to bytes — avoids encoding ambiguity across xhtml2pdf versions
    html_bytes = html.encode("utf-8")
    with open(pdf_path, "wb") as fh:
        result = pisa.CreatePDF(html_bytes, dest=fh, encoding="utf-8")

    if result.err:
        raise RuntimeError(
            f"xhtml2pdf reported {result.err} error(s) while generating the PDF. "
            "Check the log above for details."
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def convert_markdown_to_pdf(
    md_path: Path | str,
    pdf_path: Path | str,
) -> Path:
    """
    Converts a Markdown file to a styled PDF.

    Pipeline:
        .md file  →  markdown  →  HTML string  →  xhtml2pdf  →  .pdf file

    Args:
        md_path:  Path to the source Markdown file.
        pdf_path: Destination path for the generated PDF.

    Returns:
        Resolved path of the generated PDF.

    Raises:
        FileNotFoundError: If *md_path* does not exist.
        ImportError:       If required packages are not installed.
        RuntimeError:      If PDF generation fails.
    """
    md_path = Path(md_path)
    pdf_path = Path(pdf_path)

    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    logger.info("Reading Markdown from: %s", md_path)
    md_text = md_path.read_text(encoding="utf-8")

    logger.info("Converting Markdown → HTML …")
    html_body = _markdown_to_html(md_text)
    full_html = _HTML_TEMPLATE.format(css=_CSS, body=html_body)

    logger.info("Rendering HTML → PDF via xhtml2pdf …")
    _html_to_pdf(full_html, pdf_path)

    logger.info("PDF saved to: %s", pdf_path.resolve())
    return pdf_path.resolve()


# ── Backward-compat re-export ─────────────────────────────────────────────────
# Canonical implementation moved to src/output/pdf_converter.py.
from src.output.pdf_converter import convert_markdown_to_pdf  # noqa: F811, E402
