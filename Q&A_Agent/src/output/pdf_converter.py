"""
src/output/pdf_converter.py
────────────────────────────
Converts the Markdown output file to a styled PDF using a two-stage pipeline:

    .md file  →  markdown (Python lib)  →  HTML string
                                              │
                                              ▼
                                        xhtml2pdf / pisa
                                              │
                                              ▼
                                           .pdf file

Why this stack?
───────────────
• The `markdown` library is a pure-Python Markdown-to-HTML converter.  It is
  widely used, actively maintained, and requires no system dependencies.

• xhtml2pdf (pisa) converts HTML+CSS to PDF entirely in Python.  Unlike
  wkhtmltopdf or Playwright-based converters it requires no headless browser
  or system binaries, making it suitable for serverless and containerised
  environments.

• The combination is lightweight (~5 MB total), cross-platform (Windows,
  macOS, Linux), and produces acceptable print-quality PDFs for technical
  documents.

Known xhtml2pdf limitations
─────────────────────────────
xhtml2pdf supports a subset of CSS 2.1.  Several CSS features will silently
fail or crash:

  ❌ @page sub-rules (@top-center, @bottom-center, etc.) — CRASHES with
     "NotImplementedType object is not iterable".  These have been removed
     from _CSS.  Page numbers are NOT rendered in the footer.

  ❌ CSS variables (var(--color))
  ❌ Flexbox / Grid
  ❌ border-radius on most block elements

  ✅ Basic typography, colours, margins, lists, blockquotes, tables, <hr>

Bug fix note
─────────────
Previous versions passed the HTML string directly to pisa.CreatePDF().
On Windows this caused UnicodeDecodeError for non-ASCII characters in
the content (e.g. the ✅ emoji in the correct-answer blockquote).

Fix: encode the HTML to bytes before passing it and set encoding="utf-8":
    pisa.CreatePDF(html.encode("utf-8"), dest=fh, encoding="utf-8")

Public API
──────────
    convert_markdown_to_pdf(md_path, pdf_path) → Path
"""

from pathlib import Path

from observability.logger import get_logger

logger = get_logger(__name__)


# ─── Embedded CSS theme ─────────────────────────────────────────────────────────
#
# Why embed CSS rather than use an external file?
#   xhtml2pdf requires all CSS to be inline in the HTML document.  Using a
#   <link> tag to an external .css file only works when the file is served
#   over HTTP — not from a local path in a headless conversion context.
#   Embedding the CSS as a Python string constant guarantees it is always
#   available and keeps the module self-contained.
#
# Note: @bottom-center is intentionally absent — see module docstring.
#
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

.pdf-brand-footer {
    margin-top: 24pt;
    padding-top: 8pt;
    border-top: 1pt solid #e0e0e0;
    text-align: center;
    font-size: 8pt;
    color: #9e9e9e;
    letter-spacing: 0.5pt;
}

.pdf-brand-footer span {
    color: #3949ab;
    font-weight: bold;
}
"""

# Minimal but valid HTML5 document template.
# {css}  → substituted with _CSS above.
# {body} → substituted with the HTML produced by the markdown library.
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
<div class="pdf-brand-footer">
  Powered by <span>PrakashPujariAI</span>
</div>
</body>
</html>
"""


# ─── Internal helpers ──────────────────────────────────────────────────────────

def _markdown_to_html(md_text: str) -> str:
    """
    Converts a Markdown string to an HTML body fragment.

    Extensions used:
      • "extra"       — tables, fenced code blocks, footnotes, definition lists
      • "nl2br"       — converts single newlines to <br> tags, improving
                        paragraph rendering in the PDF
      • "sane_lists"  — fixes inconsistent list rendering for mixed list types

    Why not use a Jinja template or a richer Markdown processor?
      For the output volume of this pipeline (10–20 questions) the standard
      `markdown` library is sufficient.  Heavier dependencies (mistune,
      commonmark) would add complexity without measurable benefit.

    Args:
        md_text: Raw Markdown string.

    Returns:
        HTML body fragment (no <html>/<head> wrapper).

    Raises:
        ImportError: If the `markdown` package is not installed.
    """
    try:
        import markdown as md_lib  # deferred to keep module importable without it
    except ImportError as exc:
        raise ImportError(
            "The 'markdown' package is required for PDF conversion. "
            "Install it with: pip install markdown"
        ) from exc

    return md_lib.markdown(
        md_text,
        extensions=["extra", "nl2br", "sane_lists"],
    )


def _html_to_pdf(html: str, pdf_path: Path) -> None:
    """
    Renders an HTML string to a PDF file using xhtml2pdf.

    Encoding note (Windows fix):
      pisa.CreatePDF() has two code paths depending on whether it receives
      a str or bytes object.  On Windows, passing str can trigger a
      UnicodeDecodeError for multi-byte characters (e.g. the ✅ emoji used
      in answer blockquotes).

      Solution: encode the HTML to UTF-8 bytes first, then pass
      encoding="utf-8" as a keyword argument.  This forces pisa to use
      Python's UTF-8 codec for the byte stream, avoiding the crash.

    Args:
        html:     Full HTML document string (with <html>/<head>/<body>).
        pdf_path: Destination path for the generated PDF file.

    Raises:
        ImportError:  If xhtml2pdf is not installed.
        RuntimeError: If pisa reports conversion errors.
    """
    try:
        from xhtml2pdf import pisa  # deferred to keep module importable without it
    except ImportError as exc:
        raise ImportError(
            "The 'xhtml2pdf' package is required for PDF conversion. "
            "Install it with: pip install xhtml2pdf"
        ) from exc

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Encode HTML to bytes — avoids UnicodeDecodeError on Windows (see docstring)
    html_bytes = html.encode("utf-8")

    with open(pdf_path, "wb") as fh:
        result = pisa.CreatePDF(html_bytes, dest=fh, encoding="utf-8")

    if result.err:
        # result.err is the count of errors; details are printed by pisa to stdout
        raise RuntimeError(
            f"xhtml2pdf reported {result.err} error(s) while generating the PDF. "
            "Review the output above for details."
        )


# ─── Public API ────────────────────────────────────────────────────────────────

def convert_markdown_to_pdf(
    md_path: Path | str,
    pdf_path: Path | str,
) -> Path:
    """
    Converts a Markdown file to a styled PDF document.

    Pipeline:
        md_path  →  read UTF-8 text
                 →  _markdown_to_html()  (Markdown → HTML fragment)
                 →  wrap in _HTML_TEMPLATE with embedded _CSS
                 →  _html_to_pdf()       (HTML+CSS → PDF via xhtml2pdf)
                 →  pdf_path

    Args:
        md_path:  Source Markdown file path.
        pdf_path: Destination PDF file path.  Parent dirs created if needed.

    Returns:
        Resolved absolute path of the generated PDF.

    Raises:
        FileNotFoundError: If md_path does not exist.
        ImportError:       If markdown or xhtml2pdf are not installed.
        RuntimeError:      If PDF generation fails.
    """
    md_path  = Path(md_path)
    pdf_path = Path(pdf_path)

    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    logger.info(
        "Reading Markdown from: %s",
        md_path.resolve(),
        extra={"md_path": str(md_path.resolve())},
    )
    md_text = md_path.read_text(encoding="utf-8")

    logger.debug(
        "Markdown content: %d chars",
        len(md_text),
        extra={"md_char_count": len(md_text)},
    )

    logger.info("Converting Markdown → HTML …")
    html_body = _markdown_to_html(md_text)
    full_html = _HTML_TEMPLATE.format(css=_CSS, body=html_body)

    logger.info(
        "Rendering HTML → PDF via xhtml2pdf … (%d HTML chars)",
        len(full_html),
        extra={"html_char_count": len(full_html)},
    )
    _html_to_pdf(full_html, pdf_path)

    resolved = pdf_path.resolve()
    logger.info(
        "PDF saved: %s",
        resolved,
        extra={"pdf_path": str(resolved)},
    )
    return resolved
