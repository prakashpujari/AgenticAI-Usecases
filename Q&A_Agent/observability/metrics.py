"""
observability/metrics.py
────────────────────────
Lightweight, zero-dependency pipeline metrics tracker.

Captures per-stage wall-clock timing and arbitrary metadata, then writes a
structured JSON report on pipeline completion.  The report is machine-readable
and can be imported into dashboards, alerting systems, or stored alongside
generated outputs for audit purposes.

Metrics captured per stage
──────────────────────────
  • stage_name    — human-readable label (e.g. "build_vector_store")
  • status        — "success" | "failed" | "skipped"
  • started_at    — ISO-8601 UTC timestamp
  • finished_at   — ISO-8601 UTC timestamp
  • duration_s    — wall-clock seconds (float, 4 decimal places)
  • metadata      — arbitrary key/value payload injected by each stage
                    (e.g. char_count, chunk_count, model_name, …)

Pipeline-level fields
─────────────────────
  • pipeline_id       — 8-char UUID4 prefix (correlates log lines to a run)
  • started_at        — pipeline start ISO-8601 UTC
  • finished_at       — pipeline end ISO-8601 UTC
  • total_duration_s  — wall-clock seconds for the full run
  • overall_status    — "success" | "failed" | "partial"
  • configuration     — snapshot of key config values at runtime
  • stages            — ordered list of StageResult dicts
  • stage_summary     — flat dict of {stage_name: {duration_s, status}}

Usage
─────
    from observability.metrics import PipelineMetrics

    metrics = PipelineMetrics()
    metrics.start_pipeline()

    with metrics.stage("extract_text") as s:
        text = extract_and_clean(pdf_path)
        s.add("char_count", len(text))     # attach metadata to THIS stage

    metrics.add_pipeline_metadata("source_pdf", str(pdf_path))
    metrics.finish_pipeline(status="success")
    metrics.save_report(config.METRICS_REPORT_PATH)
    metrics.print_summary()

Design notes
────────────
  • Uses time.perf_counter() for duration (monotonic, high-resolution).
  • Uses datetime.now(UTC) for human-readable timestamps.
  • No external dependencies — only stdlib (json, time, uuid, dataclasses).
  • NOT thread-safe by design — the pipeline is sequential.
"""

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

import config


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    """
    Returns the current UTC time as an ISO-8601 string with millisecond
    precision (e.g. '2026-05-10T11:42:01.234+00:00').

    We use timezone.utc rather than datetime.utcnow() because utcnow()
    returns a naive datetime that can be mistaken for local time by
    downstream consumers.
    """
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class StageResult:
    """
    Immutable record for a single pipeline stage execution.

    Lifecycle:
        1. Instantiated with stage_name + started_at before the stage runs.
        2. metadata is populated via add() during the stage.
        3. finished_at, duration_s, and status are set when the stage exits
           (success or failure) by the context manager in PipelineMetrics.

    Why a dataclass?
        Dataclasses give us __repr__ for free (useful during debugging) and
        enforce that all fields are explicitly named, avoiding positional
        argument mistakes.
    """
    stage_name: str

    # Timestamps are strings rather than datetime objects so to_dict() can
    # serialize them without a custom JSON encoder.
    started_at:  str   = ""
    finished_at: str   = ""
    duration_s:  float = 0.0

    # "pending" → "success" | "failed" | "skipped"
    status: str = "pending"

    # Free-form key/value store for stage-specific observability data
    # (e.g. char_count, chunk_count, model_name, index_path, …)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, key: str, value: Any) -> None:
        """
        Convenience method to add a metadata key/value pair.

        Equivalent to:  stage_result.metadata[key] = value
        Exposed here so the _StageScopeHelper yielded by metrics.stage()
        has a clean, intention-revealing API.
        """
        self.metadata[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Serialises the stage result to a plain dict for JSON output."""
        return {
            "stage_name":  self.stage_name,
            "status":      self.status,
            "started_at":  self.started_at,
            "finished_at": self.finished_at,
            # Round to 4 decimal places — precision beyond that is meaningless
            # for wall-clock measurements of seconds-long operations.
            "duration_s":  round(self.duration_s, 4),
            "metadata":    self.metadata,
        }


# ─── Context-manager helper ────────────────────────────────────────────────────

class _StageScopeHelper:
    """
    Thin wrapper yielded by PipelineMetrics.stage().

    Provides a focused interface for attaching metadata to the currently
    running stage without exposing the entire PipelineMetrics object.

    Design:
        We deliberately keep this class small.  The only operation the
        caller needs during a stage is "record this measurement".  Having
        a dedicated helper (rather than yielding the StageResult directly)
        lets us evolve the internal representation without breaking callers.
    """

    def __init__(self, result: StageResult) -> None:
        # Hold a reference to the underlying StageResult so mutations are
        # reflected in PipelineMetrics._stages.
        self._result = result

    def add(self, key: str, value: Any) -> None:
        """Attaches key/value metadata to the enclosing stage's result."""
        self._result.add(key, value)


# ─── Pipeline metrics tracker ─────────────────────────────────────────────────

class PipelineMetrics:
    """
    Tracks wall-clock timing and metadata for every stage in the pipeline.

    Typical lifecycle
    ─────────────────
        metrics = PipelineMetrics()
        metrics.start_pipeline()

        with metrics.stage("extract_text") as s:
            text = extract_and_clean(pdf_path)
            s.add("char_count", len(text))

        with metrics.stage("build_vector_store") as s:
            vs = build_vector_store(chunks)
            s.add("chunk_count", len(chunks))

        metrics.finish_pipeline(status="success")
        metrics.save_report(config.METRICS_REPORT_PATH)
        metrics.print_summary()

    Stage context manager behaviour
    ────────────────────────────────
        • On __enter__: records start time, creates a StageResult.
        • On __exit__ (success): sets status="success", records duration.
        • On __exit__ (exception): sets status="failed", records duration,
          then re-raises so the pipeline's error handling is not bypassed.

    Thread safety
    ─────────────
        NOT thread-safe.  The Q&A pipeline is strictly sequential so there
        is no need for locking overhead.  If the pipeline is ever made
        concurrent, a threading.Lock should guard _stages mutations.
    """

    def __init__(self) -> None:
        # Short pipeline ID: 8 chars of UUID4 is unique enough for a
        # single-machine process while keeping log lines short.
        self.pipeline_id: str = str(uuid.uuid4())[:8]

        # Monotonic start time — used to calculate total_duration_s.
        # We store this separately from _pipeline_start_iso because
        # datetime objects and perf_counter() serve different purposes:
        #   • perf_counter() → accurate duration measurement (monotonic)
        #   • datetime.now() → human-readable wall-clock timestamp
        self._pipeline_start_mono: float = 0.0
        self._pipeline_start_iso:  str   = ""
        self._pipeline_end_iso:    str   = ""
        self._total_duration_s:    float = 0.0
        self._overall_status:      str   = "pending"

        # Ordered list of completed stage results (in execution order)
        self._stages: list[StageResult] = []

        # Pipeline-level metadata not tied to any specific stage
        # (e.g. configuration snapshot, source PDF path)
        self._pipeline_metadata: dict[str, Any] = {}

    # ── Pipeline lifecycle ─────────────────────────────────────────────────────

    def start_pipeline(self) -> None:
        """
        Records the pipeline start time and captures the runtime configuration.

        Must be called before the first metrics.stage() context manager.

        The configuration snapshot is written into the report so that any
        future analysis can correlate results with the settings that produced
        them — essential when comparing runs with different NUM_QUESTIONS or
        TEMPERATURE values.
        """
        self._pipeline_start_mono = time.perf_counter()
        self._pipeline_start_iso  = _utc_now_iso()

        # Snapshot the key configuration values so the report is self-contained.
        # We include only the parameters that directly affect output quality/cost.
        self._pipeline_metadata["configuration"] = {
            "groq_model":      config.GROQ_MODEL,
            "num_questions":   config.NUM_QUESTIONS,
            "temperature":     config.TEMPERATURE,
            "chunk_chars":     20_000,   # _CHUNK_CHARS in qa_generator (no RAG/embeddings)
        }

    def finish_pipeline(self, status: str = "success") -> None:
        """
        Records the pipeline end time and overall status.

        Args:
            status: "success"  — all stages completed without errors.
                    "failed"   — at least one stage raised an exception.
                    "partial"  — pipeline ran but produced incomplete output.
        """
        self._pipeline_end_iso  = _utc_now_iso()
        self._total_duration_s  = time.perf_counter() - self._pipeline_start_mono
        self._overall_status    = status

    # ── Stage lifecycle ────────────────────────────────────────────────────────

    @contextmanager
    def stage(self, name: str) -> Generator[_StageScopeHelper, None, None]:
        """
        Context manager that wraps a single pipeline stage.

        Automatically:
            1. Creates a StageResult and records the start timestamp.
            2. Yields a _StageScopeHelper so the caller can attach metadata.
            3. On clean exit: sets status="success", records duration,
               appends the StageResult to the internal list.
            4. On exception: sets status="failed", records duration,
               appends the StageResult, then RE-RAISES the exception.
               This ensures the pipeline's outer try/except block still
               receives the exception and can log/handle it normally.

        Usage:
            with metrics.stage("build_vector_store") as s:
                vector_store = build_vector_store(chunks)
                s.add("chunk_count", len(chunks))      # recorded in JSON report
        """
        result = StageResult(
            stage_name=name,
            started_at=_utc_now_iso(),
        )
        # perf_counter() gives a monotonically increasing float in seconds.
        # It is immune to system clock adjustments (NTP, DST, etc.), making
        # it the correct choice for elapsed-time measurement.
        _stage_start_mono = time.perf_counter()

        helper = _StageScopeHelper(result)

        try:
            yield helper
            result.status = "success"
        except Exception:
            # Mark as failed but do NOT swallow the exception — the pipeline
            # orchestrator in main.py must handle it for proper error reporting.
            result.status = "failed"
            raise
        finally:
            # The finally block runs whether the stage succeeded or failed,
            # ensuring we always record duration and append the result.
            result.finished_at = _utc_now_iso()
            result.duration_s  = time.perf_counter() - _stage_start_mono
            self._stages.append(result)

    # ── Pipeline-level metadata ────────────────────────────────────────────────

    def add_pipeline_metadata(self, key: str, value: Any) -> None:
        """
        Adds an arbitrary key/value pair to the pipeline-level metadata.

        Use this for information that applies to the whole run but is not
        specific to any single stage (e.g. source PDF filename, output paths).
        """
        self._pipeline_metadata[key] = value

    # ── Serialisation & reporting ──────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """
        Serialises the full pipeline run to a plain dict.

        The dict is JSON-serialisable and contains all captured metrics.
        Fields:
            pipeline_id       — short run identifier
            overall_status    — success / failed / partial
            started_at        — UTC ISO-8601
            finished_at       — UTC ISO-8601
            total_duration_s  — float (wall-clock seconds)
            pipeline_metadata — configuration snapshot + extra fields
            stages            — list of StageResult dicts (in order)
            stage_summary     — flat {name: {duration_s, status}} for quick queries
        """
        return {
            "pipeline_id":       self.pipeline_id,
            "overall_status":    self._overall_status,
            "started_at":        self._pipeline_start_iso,
            "finished_at":       self._pipeline_end_iso,
            "total_duration_s":  round(self._total_duration_s, 4),
            "pipeline_metadata": self._pipeline_metadata,
            # Full ordered stage list with all metadata
            "stages": [s.to_dict() for s in self._stages],
            # Summary dict: keyed by stage name for easy programmatic access
            # (e.g. metrics["stage_summary"]["build_vector_store"]["duration_s"])
            "stage_summary": {
                s.stage_name: {
                    "duration_s": round(s.duration_s, 4),
                    "status":     s.status,
                }
                for s in self._stages
            },
        }

    def save_report(self, path: Path | str) -> Path:
        """
        Writes the pipeline metrics report as an indented JSON file.

        The report is written with indent=2 for human readability while
        remaining valid JSON for machine consumption.

        Args:
            path: Destination file path.  Parent directories are created
                  automatically if they do not yet exist.

        Returns:
            Resolved (absolute) path of the written report.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # default=str converts any non-serialisable types (Path, Enum, etc.)
        # to their string representation rather than raising TypeError.
        path.write_text(
            json.dumps(self.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        return path.resolve()

    def print_summary(self) -> None:
        """
        Prints a human-readable summary table of all stage results to stdout.

        Format:
            ─────────────────────────────────────────────────────────────────
              Pipeline Run  [abc12345]  —  SUCCESS
              Total: 42.3 s
            ─────────────────────────────────────────────────────────────────
              Stage                          Status     Duration
            ─────────────────────────────────────────────────────────────────
              generate_pdf                   success       0.34s
              extract_text                   success       0.12s
              ...
        """
        width = 70
        print("\n" + "─" * width)
        print(
            f"  Pipeline Run  [{self.pipeline_id}]  —  "
            f"{self._overall_status.upper()}"
        )
        print(f"  Total: {self._total_duration_s:.1f} s")
        print("─" * width)
        print(f"  {'Stage':<35} {'Status':<12} {'Duration':>10}")
        print("─" * width)
        for s in self._stages:
            status_str = s.status
            print(f"  {s.stage_name:<35} {status_str:<12} {s.duration_s:>9.2f}s")
        print("─" * width + "\n")
