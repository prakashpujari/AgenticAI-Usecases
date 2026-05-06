"""
RAG (Retrieval-Augmented Generation) pipeline evaluation using RAGAS.

What is RAG?
------------
RAG is a pattern where the LLM doesn’t answer purely from its training data.
Instead, it first retrieves relevant documents from a vector database (e.g.
Pinecone) and then uses those documents as extra context when generating the
answer. This improves factual accuracy and reduces hallucinations.

What is RAGAS?
--------------
RAGAS (Retrieval-Augmented Generation Assessment) is an open-source framework
that measures RAG pipeline quality without requiring human labellers.
It uses an LLM-as-judge approach to score four key dimensions:

  faithfulness       (0-1): Is every claim in the answer actually supported
                            by the retrieved context chunks?
                            Low score → the model is hallucinating.

  answer_relevancy   (0-1): Does the answer directly address the question?
                            Low score → the answer is off-topic.

  context_precision  (0-1): Of all retrieved chunks, how many are actually
                            useful for answering this question?
                            Low score → the retriever is returning noise.

  context_recall     (0-1): Does the combined context cover everything stated
                            in the ground-truth answer?
                            Low score → the retriever is missing key documents.
                            Requires ground_truths to be supplied.

How to use this module
----------------------
Call evaluate_rag() after collecting a set of (question, answer, context)
triples from your system. Typical evaluation workflow:
  1. Run a sample of real user queries through the full agent pipeline.
  2. Collect the generated answers and the Pinecone context chunks used.
  3. Pass them here along with optional human-written ground-truth answers.
  4. Review the scores in LangSmith or the /evaluate/rag API response.

Example:
    from evaluation.rag_evaluator import evaluate_rag
    result = evaluate_rag(
        questions=["What is X?"],
        answers=["X is ..."],
        contexts=[["chunk1", "chunk2"]],
        ground_truths=["X is ..."],   # optional but enables context_recall
    )
    # result["metrics"] == {"faithfulness": 0.92, "answer_relevancy": 0.87, ...}

Requires:
    pip install ragas datasets
"""

import os
from typing import Optional
from observability.logger import get_logger
from observability.langsmith_tracer import trace_custom

logger = get_logger("evaluation.rag")


def evaluate_rag(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: Optional[list[str]] = None,
    run_metadata: Optional[dict] = None,
) -> dict:
    """
    Run RAGAS evaluation on a batch of RAG question/answer/context triples.

    Args:
        questions:     List of user queries sent to the RAG pipeline.
                       Must have the same length as answers and contexts.
        answers:       List of LLM-generated answers, one per question.
        contexts:      List of lists of context strings — each inner list holds
                       the text chunks retrieved from the vector DB for that query.
                       e.g. contexts[0] = ["chunk A", "chunk B"] for questions[0].
        ground_truths: Optional list of reference/golden answers.
                       Required for context_recall; enables a stricter evaluation.
        run_metadata:  Optional dict forwarded to LangSmith for filtering runs.

    Returns:
        On success:
            {"status": "success", "metrics": {"faithfulness": 0.92, ...}, "n_samples": 5}
        On error:
            {"status": "error", "detail": "<reason>"}
    """
    # Validate inputs upfront to give clear error messages instead of cryptic RAGAS errors
    if not questions or not answers or not contexts:
        return {"status": "error", "detail": "questions, answers, and contexts must all be non-empty"}

    if len(questions) != len(answers) or len(questions) != len(contexts):
        return {"status": "error", "detail": "questions, answers, and contexts must have equal length"}

    if ground_truths and len(ground_truths) != len(questions):
        return {"status": "error", "detail": "ground_truths length must match questions length"}

    try:
        # Lazy imports — the app still starts even if ragas/datasets aren’t installed
        from datasets import Dataset             # HuggingFace Dataset (RAGAS input format)
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import (
            faithfulness,        # claim-level grounding check
            answer_relevancy,    # question-answer relevance
            context_precision,   # fraction of useful retrieved chunks
            context_recall,      # coverage of ground truth by context
        )

        # Build the dict that will become a HuggingFace Dataset
        data: dict = {
            "question": questions,
            "answer":   answers,
            "contexts": contexts,   # must be list[list[str]] not list[str]
        }

        # Start with the three metrics that don’t require ground truths
        metrics = [faithfulness, answer_relevancy, context_precision]

        # context_recall needs a reference answer to know what the context should cover
        if ground_truths:
            data["ground_truth"] = ground_truths
            metrics.append(context_recall)

        # Convert to HuggingFace Dataset — RAGAS requires this format
        dataset = Dataset.from_dict(data)

        # ragas_evaluate() calls the LLM for each metric on each sample (expensive!)
        result = ragas_evaluate(dataset=dataset, metrics=metrics)

        # Extract only numeric scores and round to 4 decimal places
        scores = {
            k: round(float(v), 4)
            for k, v in result.items()
            if isinstance(v, (int, float))
        }

        logger.info("RAGAS evaluation complete", extra={"scores": scores, "n_samples": len(questions)})

        # Push results to LangSmith as a searchable custom span
        trace_custom(
            name="rag_evaluation",
            inputs={"n_samples": len(questions), "has_ground_truths": bool(ground_truths)},
            outputs=scores,
            metadata=run_metadata,
        )

        return {"status": "success", "metrics": scores, "n_samples": len(questions)}

    except ImportError as exc:
        # Provide an actionable error message rather than a confusing traceback
        msg = f"Required package not installed: {exc}. Run: pip install ragas datasets"
        logger.error(msg)
        return {"status": "error", "detail": msg}
    except Exception as exc:
        logger.error("RAGAS evaluation failed", exc_info=True)
        return {"status": "error", "detail": str(exc)}
