"""
src/pipeline/stages.py
───────────────────────
The orchestration layer that wraps each domain function in an observability
envelope.

Purpose
───────
Each public `stage_*` function:
  1. Accepts a `PipelineMetrics` instance as a keyword argument.
  2. Opens a metrics timing context (`with metrics.stage(name) as s:`).
  3. Delegates to the appropriate domain module (ingestion / retrieval /
     generation / output).
  4. Records key metadata on the stage scope helper (`s.add(key, value)`).
  5. Returns the domain function's result.

Why a separate orchestration layer?
─────────────────────────────────────
Separating stage orchestration from domain logic achieves three things:

  1. Testability — domain modules can be unit-tested without any observability
     machinery.  Stage wrappers can be tested with a mock PipelineMetrics.

  2. Single Responsibility — domain modules remain focused on their own
     concerns (PDF extraction, embedding, LLM calls).  Timing, counters, and
     structured metadata are entirely the orchestration layer's concern.

  3. Replaceability — the domain implementation can be swapped (e.g. swap
     FAISS for Chroma) without touching the metrics/timing wiring.

Error handling
──────────────
PipelineMetrics.stage() is a context manager that automatically marks the
stage as "failed" and re-raises on exception.  Stage functions here do NOT
catch exceptions — they propagate up to main.py which handles them at the
pipeline level.

Public API
──────────
    stage_generate_pdf(output_path, metrics)           → Path
    stage_extract_text(pdf_path, metrics)              → str
    stage_split_text(text, metrics)                    → list[Document]
    stage_build_vector_store(chunks, metrics)          → FAISS
    stage_generate_questions(vector_store, metrics)    → list[QuestionDict]
    stage_format_markdown(questions, source_name, output_path, metrics) → str
    stage_convert_to_pdf(md_path, pdf_path, metrics)   → Path
"""

from __future__ import annotations   # lazy annotations — no eager name resolution

from pathlib import Path
from typing import Any

import config
from observability.metrics import PipelineMetrics
from src.generation.qa_generator import _traceable as traceable, summarize_text
from src.ingestion.document_loader import load_document
from src.output.output_formatter import (
    format_questions_to_markdown,
    format_text_to_markdown,
    format_combined_to_markdown,
)
from src.output.pdf_converter import convert_markdown_to_pdf

QuestionDict = dict[str, Any]


# ─── Stage: Extract text ───────────────────────────────────────────────────────
@traceable(name="stage_extract_text", run_type="tool", tags=["ingestion"])
def stage_extract_text(input_source: Path | str, metrics: PipelineMetrics) -> str:
    """Load and clean text from any supported source (file or URL)."""
    with metrics.stage("extract_text") as s:
        text = load_document(input_source)
        s.add("char_count",   len(text))
        s.add("input_source", str(input_source))
    return text


# ─── Stage: Summarise via LLM ─────────────────────────────────────────────────
@traceable(name="stage_summarize_text", run_type="llm", tags=["generation", "llm"])
def stage_summarize_text(
    text: str,
    metrics: PipelineMetrics,
    request_id: str = "unknown",
) -> str:
    """Call the LLM to produce a structured Markdown summary of the extracted text."""
    with metrics.stage("summarize_text") as s:
        summary = summarize_text(text, request_id=request_id)
        s.add("input_len",   len(text))
        s.add("summary_len", len(summary))
        s.add("llm_model",   config.GROQ_MODEL)
    return summary


# ─── Stage 6: Format Markdown ──────────────────────────────────────────────────

@traceable(name="stage_format_markdown", run_type="tool", tags=["output"])
def stage_format_markdown(
    questions: list[QuestionDict],
    source_name: str,
    output_path: Path | str,
    metrics: PipelineMetrics,
) -> str:
    """
    Renders the question list as a structured Markdown document.

    Metrics recorded:
      • question_count — number of questions formatted
      • md_char_count  — character count of the Markdown output
      • output_path    — path where the Markdown was written

    Args:
        questions:   Validated QuestionDict list from stage_generate_questions.
        source_name: Name of the source PDF (displayed in the Markdown header).
        output_path: Destination path for the .md file.
        metrics:     Active pipeline metrics tracker.

    Returns:
        Full Markdown string.
    """
    with metrics.stage("format_markdown") as s:
        markdown_text = format_questions_to_markdown(
            questions,
            source_name=source_name,
            output_path=output_path,
        )
        s.add("question_count", len(questions))
        s.add("md_char_count",  len(markdown_text))
        s.add("output_path",    str(output_path))
    return markdown_text


# ─── Stage 6b: Format text-only Markdown ─────────────────────────────────────

@traceable(name="stage_format_text", run_type="tool", tags=["output"])
def stage_format_text(
    summary: str,
    source_name: str,
    output_path: Path | str,
    metrics: PipelineMetrics,
) -> str:
    """Render the LLM summary as a standalone Markdown document."""
    with metrics.stage("format_text") as s:
        markdown_text = format_text_to_markdown(
            summary,
            source_name=source_name,
            output_path=output_path,
        )
        s.add("md_char_count", len(markdown_text))
        s.add("output_path",   str(output_path))
    return markdown_text


# ─── Stage 6c: Format combined Markdown (text + questions) ───────────────────

@traceable(name="stage_format_combined", run_type="tool", tags=["output"])
def stage_format_combined(
    summary: str,
    questions: list[QuestionDict],
    source_name: str,
    output_path: Path | str,
    metrics: PipelineMetrics,
) -> str:
    """Render both the LLM summary and MCQ questions into a single Markdown document."""
    with metrics.stage("format_combined") as s:
        markdown_text = format_combined_to_markdown(
            summary,
            questions,
            source_name=source_name,
            output_path=output_path,
        )
        s.add("question_count", len(questions))
        s.add("md_char_count",  len(markdown_text))
        s.add("output_path",    str(output_path))
    return markdown_text


# ─── Stage 7: Convert Markdown to PDF ────────────────────────────────────────

@traceable(name="stage_convert_to_pdf", run_type="tool", tags=["output"])
def stage_convert_to_pdf(
    md_path: Path | str,
    pdf_path: Path | str,
    metrics: PipelineMetrics,
) -> Path:
    """
    Converts the Markdown file to a styled PDF using xhtml2pdf.

    Metrics recorded:
      • md_path        — source Markdown file
      • pdf_path       — destination PDF file
      • pdf_size_b     — size of the generated PDF in bytes

    Args:
        md_path:  Source .md file path.
        pdf_path: Destination .pdf file path.
        metrics:  Active pipeline metrics tracker.

    Returns:
        Resolved absolute Path of the generated PDF.
    """
    with metrics.stage("convert_to_pdf") as s:
        result_path = convert_markdown_to_pdf(md_path, pdf_path)
        s.add("md_path",    str(md_path))
        s.add("pdf_path",   str(result_path))
        s.add("pdf_size_b", result_path.stat().st_size)
    return result_path
