"""
main.py
───────
Entry point for the end-to-end Q&A Agent pipeline.

Stage flow
──────────
  1. Generate sample PDF  (skipped if already on disk)
  2. Extract + clean text from the PDF
  3. Split text into overlapping RAG-ready chunks
  4. Embed chunks with OpenAI + persist FAISS index
  5. Retrieve context + generate original MCQ via OpenAI Chat API
  6. Format Q&A as structured Markdown
  7. Convert Markdown → styled PDF via xhtml2pdf

Observability
─────────────
  • setup_logging()       — initialises the structured logging stack
                            (coloured console + JSON Lines log file)
                            MUST be called before any other local import
                            that logs on module load.
  • PipelineMetrics       — tracks per-stage timing and metadata;
                            saves a machine-readable JSON report at the end.

Each stage function lives in src/pipeline/stages.py and accepts a
PipelineMetrics instance.  The metrics context manager automatically marks
a stage as "failed" and re-raises on exception.

Run
───
    python main.py

Environment
───────────
    Copy .env.example → .env and set OPENAI_API_KEY before running.

Exit codes
──────────
    0  pipeline completed successfully
    1  configuration / environment error (missing API key, bad config)
    2  runtime / API / file error
"""

import sys

# ── Observability must be initialised FIRST ───────────────────────────────────
# setup_logging() configures the root Python logger before any library code
# (langchain, openai, faiss) is imported.  Importing those libraries first
# can cause them to attach their own handlers, leading to duplicate log lines.
from observability import setup_logging, PipelineMetrics, setup_langsmith

setup_logging()
_langsmith_active = setup_langsmith()  # sets LANGCHAIN_* env vars; returns bool

# ── Local imports (after logging is configured) ───────────────────────────────
import config
from observability.logger import get_logger
from src.pipeline.stages import (
    stage_generate_pdf,
    stage_extract_text,
    stage_split_text,
    stage_build_vector_store,
    stage_generate_questions,
    stage_format_markdown,
    stage_convert_to_pdf,
)

logger = get_logger("qa_agent.main")


# ── Pipeline orchestrator ─────────────────────────────────────────────────────

def main() -> None:
    """
    Runs the complete Q&A generation pipeline end-to-end.

    Observability:
      • A PipelineMetrics instance is created and passed to every stage.
      • On success:  metrics.finish_pipeline("success") saves the JSON report
                     and prints a human-readable summary table.
      • On failure:  metrics.finish_pipeline("failed") is called so the partial
                     report is still written — useful for debugging which stage
                     failed and how long earlier stages took.

    Exit codes:
        0 – success
        1 – configuration / environment error
        2 – runtime / API error
    """
    # ── Pre-flight: validate configuration ────────────────────────────────────
    if not config.OPENAI_API_KEY:
        logger.error(
            "OPENAI_API_KEY is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Set OPENAI_API_KEY=<your OpenAI key>\n"
            "  3. Re-run:  python main.py"
        )
        sys.exit(1)

    # ── Initialise metrics tracker ─────────────────────────────────────────────
    # Each pipeline run gets a unique 8-character pipeline_id derived from UUID4.
    # This ID appears in all log lines emitted by get_logger(), so an entire run
    # can be correlated in the JSON log file with a simple grep.
    metrics = PipelineMetrics()
    metrics.start_pipeline()

    logger.info(
        "Pipeline %s starting — model=%s  questions=%d",
        metrics.pipeline_id,
        config.OPENAI_MODEL,
        config.NUM_QUESTIONS,
        extra={
            "pipeline_id":   metrics.pipeline_id,
            "model":         config.OPENAI_MODEL,
            "num_questions": config.NUM_QUESTIONS,
        },
    )

    # ── LangSmith parent trace context ────────────────────────────────────────
    # langsmith.trace() creates a parent run in the LangSmith UI that every
    # downstream @traceable stage call and LCEL chain invocation is nested under.
    # The pipeline_id, model, and num_questions become searchable metadata on
    # every run in the project.
    #
    # When LangSmith is disabled (_langsmith_active=False), contextlib.nullcontext()
    # is used instead — zero overhead, no side effects.
    import contextlib
    if _langsmith_active:
        try:
            from langsmith import trace as _ls_trace
            _trace_ctx = _ls_trace(
                name=f"Q&A Pipeline [{metrics.pipeline_id}]",
                run_type="chain",
                metadata={
                    "pipeline_id":   metrics.pipeline_id,
                    "model":         config.OPENAI_MODEL,
                    "num_questions": config.NUM_QUESTIONS,
                    "project":       config.LANGCHAIN_PROJECT,
                },
                tags=["qa-agent", "pipeline"],
            )
        except Exception:  # noqa: BLE001 — tracing must never block the pipeline
            _trace_ctx = contextlib.nullcontext()
    else:
        _trace_ctx = contextlib.nullcontext()

    with _trace_ctx:
        _run_pipeline(metrics)


def _run_pipeline(metrics: PipelineMetrics) -> None:
    """
    Inner pipeline runner — all 7 stage calls, error handling, and final reporting.

    Separated from main() so it can be cleanly wrapped in the LangSmith parent
    trace context manager without nesting the entire main() body inside a try/with.
    """
    try:
        # ── Stage 1: Generate sample source PDF ───────────────────────────────
        # Skips creation if the PDF already exists on disk (idempotent).
        if config.SAMPLE_PDF_PATH.exists():
            logger.info(
                "[1/7] Sample PDF already exists, skipping: %s",
                config.SAMPLE_PDF_PATH,
            )
            pdf_path = config.SAMPLE_PDF_PATH
            # Record a synthetic (instant) stage so the metrics report is complete
            with metrics.stage("generate_sample_pdf") as s:
                s.add("skipped",  True)
                s.add("pdf_path", str(pdf_path))
        else:
            logger.info("[1/7] Generating sample PDF …")
            pdf_path = stage_generate_pdf(config.SAMPLE_PDF_PATH, metrics)
            logger.info("      ✓ PDF created: %s", pdf_path)

        # ── Stage 2: Extract and clean text ───────────────────────────────────
        logger.info("[2/7] Extracting and cleaning text from PDF …")
        clean_text = stage_extract_text(pdf_path, metrics)
        logger.info("      ✓ Extracted %d characters", len(clean_text))

        # ── Stage 3: Split text into chunks ───────────────────────────────────
        logger.info("[3/7] Splitting text into chunks …")
        chunks = stage_split_text(clean_text, metrics)
        logger.info("      ✓ %d chunks created", len(chunks))

        # ── Stage 4: Embed chunks + build FAISS index ──────────────────────────
        logger.info(
            "[4/7] Building FAISS vector store (%d chunks, embedding model: %s) …",
            len(chunks),
            config.OPENAI_EMBEDDING_MODEL,
        )
        logger.info("      (Calls the OpenAI Embeddings API — may take a few seconds)")
        vector_store = stage_build_vector_store(chunks, metrics)
        logger.info("      ✓ FAISS index built and saved to %s", config.FAISS_INDEX_PATH)

        # ── Stage 5: Generate MCQ questions ───────────────────────────────────
        logger.info(
            "[5/7] Generating %d questions with %s …",
            config.NUM_QUESTIONS,
            config.OPENAI_MODEL,
        )
        logger.info("      (Calls the OpenAI Chat API — may take ~20–40 s)")
        questions = stage_generate_questions(vector_store, metrics)
        logger.info("      ✓ %d questions generated", len(questions))

        # ── Stage 6: Format as Markdown ────────────────────────────────────────
        logger.info("[6/7] Formatting questions as Markdown …")
        stage_format_markdown(
            questions,
            source_name=config.SAMPLE_PDF_PATH.name,
            output_path=config.OUTPUT_MARKDOWN_PATH,
            metrics=metrics,
        )
        logger.info("      ✓ Markdown saved: %s", config.OUTPUT_MARKDOWN_PATH)

        # ── Stage 7: Convert to PDF ────────────────────────────────────────────
        logger.info("[7/7] Converting Markdown → PDF …")
        pdf_output = stage_convert_to_pdf(
            config.OUTPUT_MARKDOWN_PATH,
            config.OUTPUT_PDF_PATH,
            metrics,
        )
        logger.info("      ✓ PDF saved: %s", pdf_output)

    except EnvironmentError as exc:
        # Raised by qa_generator if OPENAI_API_KEY is missing at call time
        logger.error("Configuration error: %s", exc, extra={"pipeline_id": metrics.pipeline_id})
        metrics.finish_pipeline(status="failed")
        metrics.save_report(config.METRICS_REPORT_PATH)
        sys.exit(1)

    except FileNotFoundError as exc:
        logger.error("File error: %s", exc, extra={"pipeline_id": metrics.pipeline_id})
        metrics.finish_pipeline(status="failed")
        metrics.save_report(config.METRICS_REPORT_PATH)
        sys.exit(2)

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Unexpected error during pipeline: %s",
            exc,
            extra={"pipeline_id": metrics.pipeline_id},
        )
        metrics.finish_pipeline(status="failed")
        metrics.save_report(config.METRICS_REPORT_PATH)
        sys.exit(2)

    # ── Success path ───────────────────────────────────────────────────────────
    metrics.finish_pipeline(status="success")
    metrics.save_report(config.METRICS_REPORT_PATH)

    logger.info("")
    logger.info("=" * 60)
    logger.info("  Pipeline %s — COMPLETE", metrics.pipeline_id)
    logger.info("  Markdown  → %s", config.OUTPUT_MARKDOWN_PATH)
    logger.info("  PDF       → %s", config.OUTPUT_PDF_PATH)
    logger.info("  Metrics   → %s", config.METRICS_REPORT_PATH)
    logger.info("=" * 60)

    # Print the human-readable timing summary table to stdout
    metrics.print_summary()


if __name__ == "__main__":
    main()
