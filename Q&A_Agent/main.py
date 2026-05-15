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
import argparse
from pathlib import Path

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

logger = get_logger("qa_agent.main")


# ── Pipeline orchestrator ─────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    --input / -i  Path to any supported document OR an http(s):// URL.
                  Supported formats: PDF, TXT, MD, RST, CSV, DOCX, XLSX.
                  When omitted the pipeline generates (or reuses) the built-in
                  Cloud Computing sample PDF.
    """
    parser = argparse.ArgumentParser(
        prog="qa_agent",
        description=(
            "Q&A Agent — generate MCQ questions from any document.\n"
            "Supported input: PDF, TXT, MD, DOCX, XLSX, CSV, or any http(s):// URL."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i", "--input",
        metavar="PATH_OR_URL",
        default=None,
        help=(
            "Path to an input document (PDF / TXT / MD / DOCX / XLSX / CSV) "
            "or an http(s):// URL.  When omitted, a sample Cloud Computing PDF "
            "is generated automatically."
        ),
    )
    return parser.parse_args()


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
    # ── Parse CLI arguments ────────────────────────────────────────────────────
    args = _parse_args()
    input_source: Path | str | None = None
    if args.input:
        raw = args.input.strip()
        import re as _re
        if _re.match(r"^https?://", raw, _re.IGNORECASE):
            input_source = raw          # URL — keep as str
        else:
            input_source = Path(raw)    # Local path
            if not input_source.exists():
                logger.error("Input file not found: %s", input_source.resolve())
                sys.exit(1)

    # ── Pre-flight: validate configuration ────────────────────────────────────
    if not config.GROQ_API_KEY:
        logger.error(
            "GROQ_API_KEY is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Set GROQ_API_KEY=<your Groq key>\n"
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
        config.GROQ_MODEL,
        config.NUM_QUESTIONS,
        extra={
            "pipeline_id":   metrics.pipeline_id,
            "model":         config.GROQ_MODEL,
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
                    "model":         config.GROQ_MODEL,
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
        _run_pipeline(metrics, input_source=input_source)


def _run_pipeline(metrics: PipelineMetrics, *, input_source: "Path | str | None" = None) -> None:
    """
    Inner pipeline runner — delegates to the LangGraph state machine.

    Stage 1 (PDF generation / source resolution) still runs here because it
    predates the graph and requires CLI-specific logic (--input flag handling).
    All remaining stages (2-7) are orchestrated by the LangGraph graph.
    """
    from src.pipeline.stages import stage_generate_pdf
    from src.pipeline.graph import run_pipeline_graph

    try:
        # ── Stage 1: Resolve / generate source document ───────────────────────
        if input_source is not None:
            resolved_source = input_source
            source_label = (
                Path(input_source).name
                if not str(input_source).startswith("http")
                else str(input_source)
            )
            logger.info("[1/7] Custom input: %s", resolved_source)
            with metrics.stage("generate_sample_pdf") as s:
                s.add("skipped", True)
                s.add("input_source", str(resolved_source))

        elif config.SAMPLE_PDF_PATH.exists():
            resolved_source = config.SAMPLE_PDF_PATH
            source_label    = config.SAMPLE_PDF_PATH.name
            logger.info("[1/7] Reusing existing sample PDF: %s", resolved_source)
            with metrics.stage("generate_sample_pdf") as s:
                s.add("skipped", True)

        else:
            logger.info("[1/7] Generating sample PDF …")
            resolved_source = stage_generate_pdf(config.SAMPLE_PDF_PATH, metrics)
            source_label    = config.SAMPLE_PDF_PATH.name
            logger.info("      ✓ PDF created: %s", resolved_source)

        # ── Stages 2-7: LangGraph state machine ──────────────────────────────
        run_pipeline_graph(
            input_source    = str(resolved_source),
            pipeline_id     = metrics.pipeline_id,
            output_mode     = "questions",
            num_questions   = config.NUM_QUESTIONS,
            request_id      = metrics.pipeline_id,
            source_label    = source_label,
            output_md_path  = str(config.OUTPUT_MARKDOWN_PATH),
            output_pdf_path = str(config.OUTPUT_PDF_PATH),
            metrics         = metrics,
        )

    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc,
                     extra={"pipeline_id": metrics.pipeline_id})
        metrics.finish_pipeline(status="failed")
        metrics.save_report(config.METRICS_REPORT_PATH)
        sys.exit(1)

    except FileNotFoundError as exc:
        logger.error("File error: %s", exc,
                     extra={"pipeline_id": metrics.pipeline_id})
        metrics.finish_pipeline(status="failed")
        metrics.save_report(config.METRICS_REPORT_PATH)
        sys.exit(2)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected pipeline error: %s", exc,
                         extra={"pipeline_id": metrics.pipeline_id})
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
