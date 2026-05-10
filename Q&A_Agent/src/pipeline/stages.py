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

from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

import config
from observability.metrics import PipelineMetrics
from langsmith import traceable
# ── Domain imports ─────────────────────────────────────────────────────────────
# Each domain module is imported from its new canonical location.
# The original src/*.py files are kept as backward-compat stubs.
from src.ingestion.pdf_generator  import create_sample_pdf
from src.ingestion.pdf_extractor  import extract_and_clean
from src.ingestion.document_loader import load_document
from src.retrieval.embeddings_store import (
    split_text,
    build_vector_store,
    load_vector_store,
    get_all_documents,
)
from src.generation.qa_generator  import generate_questions
from src.output.output_formatter  import format_questions_to_markdown
from src.output.pdf_converter     import convert_markdown_to_pdf

QuestionDict = dict[str, Any]


# ─── Stage 1: Generate sample PDF ─────────────────────────────────────────────
@traceable(name="stage_generate_pdf", run_type="tool", tags=["ingestion"])
def stage_generate_pdf(
    output_path: Path | str,
    metrics: PipelineMetrics,
) -> Path:
    """
    Creates the sample Cloud Computing PDF using ReportLab.

    Metrics recorded:
      • pdf_path    — resolved path of the generated file
      • file_size_b — file size in bytes (useful for detecting empty files)

    Args:
        output_path: Where to write the PDF.
        metrics:     Active pipeline metrics tracker.

    Returns:
        Resolved Path of the generated PDF.
    """
    with metrics.stage("generate_sample_pdf") as s:
        pdf_path = create_sample_pdf(output_path)
        s.add("pdf_path",    str(pdf_path))
        s.add("file_size_b", pdf_path.stat().st_size)
    return pdf_path


# ─── Stage 2: Extract and clean text ──────────────────────────────────────────
@traceable(name="stage_extract_text", run_type="tool", tags=["ingestion"])
def stage_extract_text(
    input_source: Path | str,
    metrics: PipelineMetrics,
) -> str:
    """
    Loads and cleans text from any supported document source.

    Supported formats: PDF, TXT, MD, RST, CSV, DOCX, XLSX, or any HTTP(S) URL.

    Metrics recorded:
      • char_count    — character count of the cleaned text
      • input_source  — source file path or URL

    Args:
        input_source: Local file path (any supported format) or http(s):// URL.
        metrics:      Active pipeline metrics tracker.

    Returns:
        Cleaned text string.
    """
    with metrics.stage("extract_text") as s:
        text = load_document(input_source)
        s.add("char_count",   len(text))
        s.add("input_source", str(input_source))
    return text


# ─── Stage 3: Split text into chunks ──────────────────────────────────────────
@traceable(name="stage_split_text", run_type="tool", tags=["ingestion"])
def stage_split_text(
    text: str,
    metrics: PipelineMetrics,
) -> list[Document]:
    """
    Splits cleaned text into overlapping Document chunks for embedding.

    Metrics recorded:
      • chunk_count  — total number of chunks produced
      • chunk_size   — configured chunk character limit
      • chunk_overlap — configured overlap character count

    Args:
        text:    Cleaned text from stage_extract_text.
        metrics: Active pipeline metrics tracker.

    Returns:
        List of LangChain Document objects.
    """
    with metrics.stage("split_text") as s:
        chunks = split_text(text)
        s.add("chunk_count",   len(chunks))
        s.add("chunk_size",    config.CHUNK_SIZE)
        s.add("chunk_overlap", config.CHUNK_OVERLAP)
    return chunks


# ─── Stage 4: Build / load vector store ───────────────────────────────────────

@traceable(name="stage_build_vector_store", run_type="tool", tags=["retrieval"])
def stage_build_vector_store(
    chunks: list[Document],
    metrics: PipelineMetrics,
) -> FAISS:
    """
    Embeds chunks with OpenAI and persists them to a FAISS index.

    Metrics recorded:
      • chunk_count     — number of chunks embedded
      • embedding_model — model name used for embedding
      • index_path      — directory where the index was saved

    Args:
        chunks:  Documents from stage_split_text.
        metrics: Active pipeline metrics tracker.

    Returns:
        In-memory FAISS vector store (also persisted to disk).
    """
    with metrics.stage("build_vector_store") as s:
        vector_store = build_vector_store(chunks)
        s.add("chunk_count",     len(chunks))
        s.add("embedding_model", config.OPENAI_EMBEDDING_MODEL)
        s.add("index_path",      str(config.FAISS_INDEX_PATH))
    return vector_store


# ─── Stage 5: Generate questions ──────────────────────────────────────────────

@traceable(name="stage_generate_questions", run_type="chain", tags=["generation", "llm"])
def stage_generate_questions(
    vector_store: FAISS,
    metrics: PipelineMetrics,
    num_questions: int | None = None,
) -> list[QuestionDict]:
    """
    Queries the vector store and calls the LLM to produce MCQ questions.

    Metrics recorded:
      • question_count — number of questions returned
      • llm_model      — model name used for generation
      • temperature    — sampling temperature (for reproducibility audit)

    Args:
        vector_store:  Populated FAISS instance from stage_build_vector_store.
        metrics:       Active pipeline metrics tracker.
        num_questions: Optional override for question count.

    Returns:
        List of validated QuestionDict objects.
    """
    with metrics.stage("generate_questions") as s:
        questions = generate_questions(vector_store, num_questions=num_questions)
        s.add("question_count", len(questions))
        s.add("llm_model",      config.OPENAI_MODEL)
        s.add("temperature",    config.TEMPERATURE)
        s.add("requested_questions", num_questions or config.NUM_QUESTIONS)
    return questions


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
