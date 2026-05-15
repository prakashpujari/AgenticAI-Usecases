"""
src/pipeline/graph.py
──────────────────────
LangGraph orchestration for the Q&A Agent pipeline.

Replaces the imperative if/elif branching in server.py and main.py with a
typed state machine that explicitly models every valid execution path.

Graph topology
──────────────

          ┌─────────────────┐
          │  extract_text   │  (always)
          └────────┬────────┘
                   │
          route_after_extract
         ┌─────────┴──────────┐
         │                    │
   text / both            questions
         │                    │
  ┌──────▼───────┐    ┌───────▼──────┐
  │ summarize    │    │  split_text  │
  └──────┬───────┘    └───────┬──────┘
         │                    │
  route_after_summarize        │
  ┌──────┴──────┐              │
  │             │              │
 text          both            │
  │             └──────────────┼──► build_vector_store
  │                            │
  │             ┌──────────────┘
  │             │
  │    ┌────────▼──────────┐
  │    │ build_vector_store│
  │    └────────┬──────────┘
  │             │
  │    ┌────────▼──────────┐
  │    │ generate_questions│
  │    └────────┬──────────┘
  │             │
  └──────────►──┤
                │
       ┌────────▼──────────┐
       │  format_output    │  (branches on output_mode internally)
       └────────┬──────────┘
                │
       ┌────────▼──────────┐
       │   convert_pdf     │
       └────────┬──────────┘
                │
              [END]

State schema
─────────────
PipelineState holds all data produced by each stage.  Later nodes read from
earlier nodes' outputs via the shared state dict.  FAISS vector stores are
held in-memory (not serialisable) — no checkpointer is used.

Public API
──────────
    build_pipeline_graph() → CompiledStateGraph
    run_pipeline_graph(...)  → PipelineResult
"""

import logging
import time
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

import config
from observability.metrics import PipelineMetrics

logger = logging.getLogger("qa_agent.pipeline.graph")


# ── State schema ───────────────────────────────────────────────────────────────

class PipelineState(TypedDict, total=False):
    # ── Inputs (required at graph entry) ─────────────────────────────────────
    input_source: str          # local path or URL
    num_questions: int
    output_mode: str           # "text" | "questions" | "both"
    request_id: str
    pipeline_id: str
    source_label: str          # human-readable name for output headers
    output_md_path: str
    output_pdf_path: str

    # ── Stage outputs ─────────────────────────────────────────────────────────
    clean_text: str
    chunks: list               # list[langchain Document]
    vector_store: Any          # FAISS — in-memory only, not serialisable
    summary: str
    questions: list            # list[QuestionDict]
    markdown_content: str

    # ── Observability ─────────────────────────────────────────────────────────
    metrics: Any               # PipelineMetrics instance


# ── Node definitions ───────────────────────────────────────────────────────────

def _node_extract_text(state: PipelineState) -> dict:
    from src.pipeline.stages import stage_extract_text
    metrics: PipelineMetrics = state["metrics"]
    clean_text = stage_extract_text(state["input_source"], metrics)
    logger.info(
        "extract_text complete: %d chars",
        len(clean_text),
        extra={"pipeline_id": state.get("pipeline_id"), "char_count": len(clean_text)},
    )
    return {"clean_text": clean_text}


def _node_summarize_text(state: PipelineState) -> dict:
    from src.pipeline.stages import stage_summarize_text
    metrics: PipelineMetrics = state["metrics"]
    summary = stage_summarize_text(
        state["clean_text"],
        metrics,
        request_id=state.get("request_id", "unknown"),
    )
    logger.info(
        "summarize_text complete: %d chars",
        len(summary),
        extra={"pipeline_id": state.get("pipeline_id")},
    )
    return {"summary": summary}


def _node_generate_questions(state: PipelineState) -> dict:
    """Generate MCQ questions directly from clean text — no embeddings needed."""
    from src.generation.qa_generator import generate_questions_from_text
    from observability.metrics import PipelineMetrics
    metrics: PipelineMetrics = state["metrics"]
    with metrics.stage("generate_questions"):
        questions = generate_questions_from_text(
            text=state["clean_text"],
            num_questions=state.get("num_questions") or config.NUM_QUESTIONS,
            request_id=state.get("request_id", "unknown"),
        )
    logger.info(
        "generate_questions complete: %d questions",
        len(questions),
        extra={"pipeline_id": state.get("pipeline_id"), "question_count": len(questions)},
    )
    return {"questions": questions}


def _node_format_output(state: PipelineState) -> dict:
    """Format Markdown output — branches on output_mode."""
    from src.pipeline.stages import (
        stage_format_markdown,
        stage_format_text,
        stage_format_combined,
    )
    metrics: PipelineMetrics = state["metrics"]
    mode         = state["output_mode"]
    source_label = state.get("source_label", state["input_source"])
    md_path      = Path(state["output_md_path"])

    if mode == "text":
        stage_format_text(state["summary"], source_label, md_path, metrics)
    elif mode == "questions":
        stage_format_markdown(state["questions"], source_name=source_label,
                              output_path=md_path, metrics=metrics)
    else:  # "both"
        stage_format_combined(state["summary"], state["questions"],
                              source_label, md_path, metrics)

    logger.info(
        "format_output complete (mode=%s)",
        mode,
        extra={"pipeline_id": state.get("pipeline_id"), "output_mode": mode},
    )
    return {}


def _node_convert_pdf(state: PipelineState) -> dict:
    from src.pipeline.stages import stage_convert_to_pdf
    metrics: PipelineMetrics = state["metrics"]
    result_path = stage_convert_to_pdf(
        Path(state["output_md_path"]),
        Path(state["output_pdf_path"]),
        metrics,
    )
    markdown_content = Path(state["output_md_path"]).read_text(encoding="utf-8")
    logger.info(
        "convert_pdf complete: %s",
        result_path,
        extra={"pipeline_id": state.get("pipeline_id")},
    )
    return {"markdown_content": markdown_content}


# ── Routing functions ──────────────────────────────────────────────────────────

def _route_after_extract(state: PipelineState) -> str:
    """
    questions → generate_questions  (direct text → LLM, no embedding)
    text/both → summarize_text
    """
    mode = state.get("output_mode", "questions")
    if mode == "questions":
        return "generate_questions"
    return "summarize_text"


def _route_after_summarize(state: PipelineState) -> str:
    """
    text → format_output
    both → generate_questions
    """
    mode = state.get("output_mode", "questions")
    if mode == "text":
        return "format_output"
    return "generate_questions"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_pipeline_graph():
    """Compile the LangGraph state machine (embedding-free)."""
    workflow = StateGraph(PipelineState)

    workflow.add_node("extract_text",       _node_extract_text)
    workflow.add_node("summarize_text",     _node_summarize_text)
    workflow.add_node("generate_questions", _node_generate_questions)
    workflow.add_node("format_output",      _node_format_output)
    workflow.add_node("convert_pdf",        _node_convert_pdf)

    workflow.set_entry_point("extract_text")

    workflow.add_conditional_edges(
        "extract_text",
        _route_after_extract,
        {"summarize_text": "summarize_text", "generate_questions": "generate_questions"},
    )

    workflow.add_conditional_edges(
        "summarize_text",
        _route_after_summarize,
        {"format_output": "format_output", "generate_questions": "generate_questions"},
    )

    workflow.add_edge("generate_questions", "format_output")
    workflow.add_edge("format_output",      "convert_pdf")
    workflow.add_edge("convert_pdf",        END)

    return workflow.compile()


# ── Singleton compiled graph (built once per process) ─────────────────────────
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_pipeline_graph()
    return _compiled_graph


# ── Public runner ──────────────────────────────────────────────────────────────

def run_pipeline_graph(
    *,
    input_source: str,
    pipeline_id: str,
    output_mode: str = "questions",
    num_questions: int | None = None,
    request_id: str = "unknown",
    source_label: str | None = None,
    output_md_path: str | None = None,
    output_pdf_path: str | None = None,
    metrics: PipelineMetrics | None = None,
) -> dict:
    """
    Run the full pipeline via LangGraph and return the final state.

    Manages the PipelineMetrics lifecycle and constructs the initial state.
    The caller is responsible for error handling at the job/process level.

    Returns the final PipelineState dict (after all nodes have run).
    Raises any stage exception so the caller can mark the job as failed.
    """
    if metrics is None:
        metrics = PipelineMetrics()
        metrics.pipeline_id = pipeline_id
        metrics.start_pipeline()

    if num_questions is None:
        num_questions = config.NUM_QUESTIONS

    md_path  = output_md_path  or str(config.OUTPUT_DIR / f"{pipeline_id}_qa.md")
    pdf_path = output_pdf_path or str(config.OUTPUT_DIR / f"{pipeline_id}_qa.pdf")

    initial_state: PipelineState = {
        "input_source":   input_source,
        "pipeline_id":    pipeline_id,
        "output_mode":    output_mode,
        "num_questions":  num_questions,
        "request_id":     request_id,
        "source_label":   source_label or str(input_source),
        "output_md_path": md_path,
        "output_pdf_path": pdf_path,
        "metrics":        metrics,
    }

    t_start = time.monotonic()
    logger.info(
        "LangGraph pipeline starting  pipeline_id=%s  mode=%s",
        pipeline_id, output_mode,
        extra={"pipeline_id": pipeline_id, "output_mode": output_mode,
               "request_id": request_id},
    )

    graph  = _get_graph()
    result = graph.invoke(initial_state)

    elapsed = (time.monotonic() - t_start) * 1000
    logger.info(
        "LangGraph pipeline complete  pipeline_id=%s  elapsed=%.0fms",
        pipeline_id, elapsed,
        extra={"pipeline_id": pipeline_id, "elapsed_ms": elapsed},
    )

    metrics.finish_pipeline(status="success")
    return result
