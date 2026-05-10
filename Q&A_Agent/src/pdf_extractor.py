"""
src/pdf_extractor.py
────────────────────
Extracts raw text from a PDF file using pypdf, then applies a cleaning
pipeline to produce normalized, retrieval-ready text.

Public API
──────────
    extract_text(pdf_path)  → raw text string
    clean_text(raw_text)    → cleaned text string
    extract_and_clean(pdf_path) → cleaned text string
"""

import logging
import re
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)


# ── Extraction ─────────────────────────────────────────────────────────────────

def extract_text(pdf_path: Path | str) -> str:
    """
    Extracts all text from a PDF file, page by page.

    Args:
        pdf_path: Path to the source PDF.

    Returns:
        Raw concatenated text from all pages.

    Raises:
        FileNotFoundError: If the PDF does not exist at the given path.
        ValueError: If the PDF has no extractable text.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))

    if len(reader.pages) == 0:
        raise ValueError(f"PDF has no pages: {pdf_path}")

    page_texts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            page_texts.append(text)
            logger.debug("Extracted %d chars from page %d", len(text), page_number)
        else:
            logger.warning("Page %d yielded no text (may be an image-only page)", page_number)

    raw_text = "\n\n".join(page_texts)

    if not raw_text.strip():
        raise ValueError("No extractable text found in the PDF.")

    logger.info(
        "Extracted text from %d pages (%d chars total)",
        len(reader.pages),
        len(raw_text),
    )
    return raw_text


# ── Cleaning ──────────────────────────────────────────────────────────────────

def clean_text(raw_text: str) -> str:
    """
    Cleans and normalises extracted PDF text.

    Steps applied (in order):
    1. Normalize unicode whitespace and line endings
    2. Remove hyphenated line-break artifacts  (word-\\n  → word)
    3. Merge intra-paragraph soft line breaks
    4. Collapse multiple blank lines to a single blank line
    5. Strip leading/trailing whitespace per paragraph
    6. Remove lines that are clearly page-number artifacts

    Args:
        raw_text: Raw text as returned by extract_text().

    Returns:
        Clean, normalised text ready for chunking.
    """
    text = raw_text

    # 1. Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Rejoin hyphenated words split across lines
    text = re.sub(r"-\n(\w)", r"\1", text)

    # 3. Merge soft line-breaks within a paragraph
    #    (single \n not preceded/followed by blank lines → space)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # 4. Collapse runs of 3+ newlines to exactly two
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. Strip leading/trailing spaces on each line
    text = "\n".join(line.strip() for line in text.splitlines())

    # 6. Drop lone numeric lines (page number artifacts)
    text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)

    # 7. Collapse any blank lines introduced in step 6
    text = re.sub(r"\n{3,}", "\n\n", text)

    cleaned = text.strip()
    logger.info("Text cleaned: %d chars → %d chars", len(raw_text), len(cleaned))
    return cleaned


# ── Combined helper ────────────────────────────────────────────────────────────

def extract_and_clean(pdf_path: Path | str) -> str:
    """
    Convenience function: extract raw text from *pdf_path* then clean it.

    Args:
        pdf_path: Path to the source PDF.

    Returns:
        Cleaned text string.
    """
    raw = extract_text(pdf_path)
    return clean_text(raw)


# ── Backward-compat re-export ─────────────────────────────────────────────────
# Canonical implementation moved to src/ingestion/pdf_extractor.py.
from src.ingestion.pdf_extractor import (  # noqa: F811, E402
    extract_text,
    clean_text,
    extract_and_clean,
)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    from config import SAMPLE_PDF_PATH

    path = sys.argv[1] if len(sys.argv) > 1 else SAMPLE_PDF_PATH
    text = extract_and_clean(path)
    print(text[:2000])
    print(f"\n... ({len(text)} chars total)")
