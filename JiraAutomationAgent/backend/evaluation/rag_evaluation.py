"""
RAG Evaluation script using Ragas.

Evaluates the RAG pipeline on:
  - context_precision
  - context_recall
  - faithfulness
  - answer_relevancy

Usage:
    python -m evaluation.rag_evaluation
    python -m evaluation.rag_evaluation --output results/rag_eval.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Ragas + LangChain imports (install via requirements.txt)
try:
    from ragas import evaluate  # type: ignore
    from ragas.metrics import (  # type: ignore
        context_precision,
        context_recall,
        faithfulness,
        answer_relevancy,
    )
    from datasets import Dataset  # type: ignore
    _RAGAS_AVAILABLE = True
except ImportError:
    _RAGAS_AVAILABLE = False

from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import settings
from backend.rag.retriever import rag_retriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Sample evaluation dataset ─────────────────────────────────────────────────
# In production, replace with real PO questions & ground-truth answers.

EVAL_SAMPLES = [
    {
        "question": "How do we handle payment failures on the checkout page?",
        "ground_truth": (
            "Payment failures should trigger a retry mechanism with user-friendly error "
            "messages, log the failure for support teams, and offer alternative payment methods."
        ),
    },
    {
        "question": "What is the acceptance criteria for user login?",
        "ground_truth": (
            "Given the user is on the login page, when they enter valid credentials, "
            "then they should be authenticated and redirected to the dashboard within 2 seconds."
        ),
    },
    {
        "question": "How should we handle mobile notification permission requests?",
        "ground_truth": (
            "The app should request notification permissions on first launch with a clear "
            "explanation, respect user denial, and allow re-requesting via app settings."
        ),
    },
]


async def build_eval_dataset() -> list[dict]:
    """Retrieve context for each question using the RAG pipeline."""
    records = []
    for sample in EVAL_SAMPLES:
        question = sample["question"]
        logger.info("Retrieving context for: %s", question[:60])

        retrieved = await rag_retriever.retrieve(question, top_k=5)
        contexts = [
            f"[{r.get('jira_key', 'N/A')}] {r.get('title', '')} — {r.get('summary', '')}"
            for r in retrieved
        ]

        # Generate an answer using retrieved context
        context_text = "\n".join(contexts) or "No context available."
        answer = (
            f"Based on the existing Jira issues, the relevant context is:\n{context_text}"
        )

        records.append(
            {
                "question": question,
                "answer": answer,
                "contexts": contexts or ["No relevant issues found."],
                "ground_truth": sample["ground_truth"],
            }
        )
    return records


def run_ragas_evaluation(records: list[dict], output_path: str | None = None) -> None:
    if not _RAGAS_AVAILABLE:
        logger.error(
            "Ragas is not installed. Run: pip install ragas datasets"
        )
        return

    dataset = Dataset.from_list(records)

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )

    logger.info("Running Ragas evaluation on %d samples…", len(records))
    result = evaluate(
        dataset=dataset,
        metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
        llm=llm,
        embeddings=embeddings,
    )

    scores = result.to_pandas()
    logger.info("\n%s", scores.to_string())

    summary = {
        "context_precision": float(scores["context_precision"].mean()),
        "context_recall": float(scores["context_recall"].mean()),
        "faithfulness": float(scores["faithfulness"].mean()),
        "answer_relevancy": float(scores["answer_relevancy"].mean()),
    }
    logger.info("Summary: %s", json.dumps(summary, indent=2))

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(
                {"summary": summary, "per_sample": scores.to_dict(orient="records")},
                f,
                indent=2,
            )
        logger.info("Results saved to %s", output_path)


async def main(output_path: str | None = None) -> None:
    records = await build_eval_dataset()
    run_ragas_evaluation(records, output_path=output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG pipeline evaluation with Ragas")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()
    asyncio.run(main(output_path=args.output))
