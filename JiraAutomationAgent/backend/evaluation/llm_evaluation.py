"""
LLM Evaluation script using DeepEval.

Evaluates generated Jira ticket quality on:
  - GEval: Clarity
  - GEval: AC Quality (Gherkin format)
  - GEval: Priority Correctness
  - GEval: Schema Adherence
  - Hallucination detection

Usage:
    python -m evaluation.llm_evaluation
    python -m evaluation.llm_evaluation --output results/llm_eval.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

try:
    from deepeval import evaluate as deepeval_evaluate  # type: ignore
    from deepeval.metrics import GEval, HallucinationMetric  # type: ignore
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams  # type: ignore
    _DEEPEVAL_AVAILABLE = True
except ImportError:
    _DEEPEVAL_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import settings
from backend.agents.generator_agent import generator_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Sample inputs for evaluation ──────────────────────────────────────────────

EVAL_INPUTS = [
    {
        "input": (
            "Users are reporting that the checkout button sometimes doesn't work "
            "on mobile Safari iOS 17. Clicks are registered but nothing happens. "
            "This has been happening since last Tuesday's release."
        ),
        "allowed_projects": ["PROJ"],
        "rbac_context": "Allowed projects: PROJ",
        "expected_issue_type": "Bug",
        "expected_priority_range": ["P0", "P1"],
    },
    {
        "input": (
            "As a product owner, I need a feature where users can save their cart "
            "and return to it later. This is important for reducing cart abandonment."
        ),
        "allowed_projects": ["PROJ"],
        "rbac_context": "Allowed projects: PROJ",
        "expected_issue_type": "Story",
        "expected_priority_range": ["P1", "P2"],
    },
    {
        "input": (
            "Q4 initiative: Build a new onboarding flow for enterprise customers. "
            "Includes SSO integration, bulk user import, admin dashboard."
        ),
        "allowed_projects": ["PROJ"],
        "rbac_context": "Allowed projects: PROJ",
        "expected_issue_type": "Epic",
        "expected_priority_range": ["P1", "P2"],
    },
]


def build_deepeval_metrics():
    """Build DeepEval GEval metrics for Jira ticket quality."""
    clarity_metric = GEval(
        name="Ticket Clarity",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        criteria=(
            "The Jira ticket has a clear, concise title. "
            "The description is unambiguous and provides enough context for a developer to implement. "
            "There are no vague terms like 'sometimes', 'maybe', or 'it should work'."
        ),
        threshold=0.7,
    )

    ac_quality_metric = GEval(
        name="Acceptance Criteria Quality",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        criteria=(
            "Acceptance criteria are written in valid Gherkin format with Given/When/Then structure. "
            "Each scenario is testable, specific, and covers the happy path and edge cases. "
            "There is at least one acceptance criterion."
        ),
        threshold=0.7,
    )

    priority_metric = GEval(
        name="Priority Correctness",
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        criteria=(
            "The assigned priority (P0-P3) is appropriate for the described problem. "
            "P0 = production down/critical, P1 = major feature/blocker, "
            "P2 = standard feature, P3 = minor/nice-to-have. "
            "The priority_reasoning field explains the choice."
        ),
        threshold=0.7,
    )

    schema_metric = GEval(
        name="Schema Adherence",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        criteria=(
            "The output contains all required fields: issue_type, title, summary, description, "
            "acceptance_criteria, priority, priority_reasoning, labels, project_key. "
            "issue_type is one of: Epic, Story, Bug, Task, Sub-task. "
            "priority is one of: P0, P1, P2, P3."
        ),
        threshold=0.9,
    )

    hallucination_metric = HallucinationMetric(threshold=0.2)

    return [clarity_metric, ac_quality_metric, priority_metric, schema_metric, hallucination_metric]


async def generate_test_cases() -> list:
    """Run the generator agent on sample inputs and build DeepEval test cases."""
    if not _DEEPEVAL_AVAILABLE:
        logger.error("DeepEval not installed. Run: pip install deepeval")
        return []

    test_cases = []
    for sample in EVAL_INPUTS:
        logger.info("Generating tickets for: %.60s", sample["input"])
        tickets = await generator_agent.generate(
            input_text=sample["input"],
            context="No RAG context available.",
            rbac_context=sample["rbac_context"],
        )

        if not tickets:
            logger.warning("No tickets generated for input: %.60s", sample["input"])
            continue

        output_json = json.dumps({"tickets": tickets}, indent=2)
        context = [
            f"Expected issue type: {sample['expected_issue_type']}",
            f"Expected priority range: {sample['expected_priority_range']}",
        ]

        test_case = LLMTestCase(
            input=sample["input"],
            actual_output=output_json,
            context=context,
            retrieval_context=context,
        )
        test_cases.append(test_case)

    return test_cases


async def main(output_path: str | None = None) -> None:
    if not _DEEPEVAL_AVAILABLE:
        logger.error(
            "DeepEval is not installed.\n"
            "Install with: pip install deepeval\n"
            "Then set OPENAI_API_KEY environment variable."
        )
        return

    logger.info("Building DeepEval test cases…")
    test_cases = await generate_test_cases()

    if not test_cases:
        logger.error("No test cases generated. Aborting.")
        return

    metrics = build_deepeval_metrics()
    logger.info("Running DeepEval evaluation on %d test cases…", len(test_cases))

    results = deepeval_evaluate(test_cases=test_cases, metrics=metrics)

    summary = {
        "total_test_cases": len(test_cases),
        "results": [
            {
                "input": tc.input[:80],
                "metrics": {
                    m.name: {
                        "score": getattr(m, "score", None),
                        "passed": getattr(m, "is_successful", lambda: None)(),
                        "reason": getattr(m, "reason", ""),
                    }
                    for m in metrics
                },
            }
            for tc in test_cases
        ],
    }

    logger.info("Evaluation complete:\n%s", json.dumps(summary, indent=2))

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info("Results saved to %s", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM ticket quality evaluation with DeepEval")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()
    asyncio.run(main(output_path=args.output))
