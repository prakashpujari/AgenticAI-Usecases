"""
LLM output quality evaluation using DeepEval.

What is DeepEval?
-----------------
DeepEval is an open-source LLM evaluation framework that treats each LLM
interaction as a "test case" and scores it against multiple quality metrics.
Unlike RAGAS (which focuses on the RAG pipeline), DeepEval evaluates the
final LLM response for safety, relevance, and factual consistency.

Metrics evaluated per request:

  AnswerRelevancyMetric  (0-1): Is the output actually answering the question?
                                Low score → the LLM went off-topic.

  ToxicityMetric         (0-1): Does the output contain hate speech, profanity,
                                threats, or other harmful language?
                                Score BELOW threshold → toxic content detected.
                                Note: lower raw score = more toxic.

  BiasMetric             (0-1): Does the output show demographic bias (gender,
                                race, religion, nationality, etc.)?
                                Score BELOW threshold → biased output.

  FaithfulnessMetric     (0-1): Is every claim in the output supported by the
                                supplied retrieval context?
                                Only computed when retrieval_context is provided.

  HallucinationMetric    (0-1): Does the output contradict the supplied context
                                (i.e., does it make up facts)?
                                Only computed when retrieval_context is provided.

Thresholds
----------
All thresholds are configurable via environment variables so you can tune
them per deployment without changing code:
  DEEPEVAL_RELEVANCY_THRESHOLD (default 0.7)
  DEEPEVAL_TOXICITY_THRESHOLD  (default 0.5)
  DEEPEVAL_BIAS_THRESHOLD      (default 0.5)
  DEEPEVAL_FAITH_THRESHOLD     (default 0.7)
  DEEPEVAL_HALLUC_THRESHOLD    (default 0.5)

Usage:
    from evaluation.llm_evaluator import evaluate_llm
    result = evaluate_llm(
        input_text="What are our refund policies?",
        actual_output="Refunds are processed within 7 days.",
        expected_output="Refunds take 5-7 business days.",   # optional
        retrieval_context=["Our refund policy states ..."],  # optional
    )
    # result["passed"] == True | False
    # result["metrics"]  == [{"metric": ..., "score": ..., "passed": ..., "reason": ...}, ...]

Requires:
    pip install deepeval
"""

import os
from typing import Optional
from observability.logger import get_logger
from observability.langsmith_tracer import trace_custom

logger = get_logger("evaluation.llm")

# ---------------------------------------------------------------------------
# Metric thresholds — read from env vars once at import time.
# A metric "passes" if its score >= threshold (for most metrics) or
# score <= threshold (for toxicity/bias where lower = better).
# ---------------------------------------------------------------------------
_RELEVANCY_THRESHOLD = float(os.getenv("DEEPEVAL_RELEVANCY_THRESHOLD", "0.7"))
_TOXICITY_THRESHOLD  = float(os.getenv("DEEPEVAL_TOXICITY_THRESHOLD",  "0.5"))
_BIAS_THRESHOLD      = float(os.getenv("DEEPEVAL_BIAS_THRESHOLD",      "0.5"))
_FAITH_THRESHOLD     = float(os.getenv("DEEPEVAL_FAITH_THRESHOLD",     "0.7"))
_HALLUC_THRESHOLD    = float(os.getenv("DEEPEVAL_HALLUC_THRESHOLD",    "0.5"))


def evaluate_llm(
    input_text: str,
    actual_output: str,
    expected_output: Optional[str] = None,
    retrieval_context: Optional[list[str]] = None,
    run_metadata: Optional[dict] = None,
) -> dict:
    """
    Run DeepEval metrics on a single LLM input/output pair.

    Args:
        input_text:        The user query or prompt that was sent to the LLM.
        actual_output:     The LLM’s generated response to evaluate.
        expected_output:   Optional "golden" reference answer. Providing it
                           enables stricter comparison-based checks.
        retrieval_context: Optional list of RAG context chunks that the LLM
                           used. Providing this enables FaithfulnessMetric
                           and HallucinationMetric.
        run_metadata:      Arbitrary dict attached to the LangSmith span
                           for filtering/searching runs later.

    Returns:
        On success:
            {
                "status":  "success",
                "passed":  True,          # True only if ALL metrics pass
                "metrics": [
                    {
                        "metric": "AnswerRelevancyMetric",
                        "score":  0.92,
                        "passed": True,
                        "reason": "The answer directly addresses ..."
                    },
                    ...
                ]
            }
        On error:
            {"status": "error", "detail": "<reason>"}
    """
    if not input_text or not actual_output:
        return {"status": "error", "detail": "input_text and actual_output are required"}

    try:
        # Lazy imports so the app works even without deepeval installed
        from deepeval.test_case import LLMTestCase
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ToxicityMetric,
            BiasMetric,
        )

        # LLMTestCase is DeepEval’s container for a single evaluation sample.
        # It bundles the input, actual output, optional expected output, and
        # any retrieval context together so metrics can access what they need.
        test_case = LLMTestCase(
            input=input_text,
            actual_output=actual_output,
            expected_output=expected_output,          # None if not provided
            retrieval_context=retrieval_context or [], # must be a list, not None
        )

        # Start with the three metrics that run without needing context documents
        metrics: list = [
            AnswerRelevancyMetric(threshold=_RELEVANCY_THRESHOLD),
            ToxicityMetric(threshold=_TOXICITY_THRESHOLD),
            BiasMetric(threshold=_BIAS_THRESHOLD),
        ]

        # Conditionally add context-dependent metrics only when we have context
        if retrieval_context:
            from deepeval.metrics import FaithfulnessMetric, HallucinationMetric
            metrics.append(FaithfulnessMetric(threshold=_FAITH_THRESHOLD))
            metrics.append(HallucinationMetric(threshold=_HALLUC_THRESHOLD))

        results = []
        for metric in metrics:
            # metric.measure() calls the LLM judge internally and sets:
            #   metric.score         — numeric score in [0, 1]
            #   metric.is_successful() — True if score meets the threshold
            #   metric.reason        — human-readable explanation from the judge
            metric.measure(test_case)
            score = metric.score
            results.append(
                {
                    "metric": type(metric).__name__,   # e.g. "AnswerRelevancyMetric"
                    "score":  round(float(score), 4) if score is not None else None,
                    "passed": bool(metric.is_successful()),
                    # getattr with default handles metrics that don’t expose a reason
                    "reason": getattr(metric, "reason", None),
                }
            )

        # Overall pass/fail: ALL metrics must pass for the run to be considered clean
        all_passed = all(r["passed"] for r in results)

        logger.info(
            "DeepEval evaluation complete",
            extra={"passed": all_passed, "metric_count": len(results)},
        )

        # Push results to LangSmith so evaluation scores are visible alongside traces
        trace_custom(
            name="llm_evaluation",
            inputs={"input": input_text[:500]},   # truncate to avoid oversized payloads
            outputs={"passed": all_passed, "metrics": results},
            metadata=run_metadata,
        )

        return {"status": "success", "passed": all_passed, "metrics": results}

    except ImportError as exc:
        # Provide a clear install instruction rather than a raw ImportError
        msg = f"Required package not installed: {exc}. Run: pip install deepeval"
        logger.error(msg)
        return {"status": "error", "detail": msg}
    except Exception as exc:
        logger.error("DeepEval evaluation failed", exc_info=True)
        return {"status": "error", "detail": str(exc)}
