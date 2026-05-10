"""
src/qa_generator.py
───────────────────
Uses LangChain LCEL + OpenAI ChatGPT to generate original multiple-choice
practice questions from retrieved document context.

Pipeline
────────
  context chunks (from FAISS retriever)
        │
        ▼
  ChatPromptTemplate  ──►  ChatOpenAI  ──►  StrOutputParser  ──►  JSON parser
        │
        ▼
  list[QuestionDict]

QuestionDict schema
───────────────────
{
    "question_number": int,
    "question":        str,
    "choices": {
        "A": str,
        "B": str,
        "C": str,
        "D": str,
    },
    "correct_answer": "A" | "B" | "C" | "D",
    "explanation":    str,
}

Public API
──────────
    generate_questions(retriever, num_questions) → list[QuestionDict]
"""

import json
import logging
import re
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI

import config

logger = logging.getLogger(__name__)

# Type alias for a single question dict
QuestionDict = dict[str, Any]

# ── System prompt ──────────────────────────────────────────────────────────────
#
# This prompt is the core "intelligence" directive for the LLM.
# It instructs the model to produce valid JSON and stay strictly within
# the provided context.
#
SYSTEM_PROMPT = """\
You are an expert educator and curriculum developer who specialises in creating \
high-quality, rigorous assessment questions.

Your task is to generate ORIGINAL multiple-choice practice questions based \
EXCLUSIVELY on the context provided below. Do NOT draw on any external knowledge \
or real exam questions from any certification body.

Rules you MUST follow:
1. Every question and every answer choice must be grounded in the provided context.
2. Generate exactly {num_questions} questions—no more, no less.
3. Each question must have exactly four choices labelled A, B, C, and D.
4. Exactly one choice must be unambiguously correct.
5. Vary cognitive levels: include recall, comprehension, application, and analysis \
questions.
6. The explanation must state WHY the correct answer is right AND briefly explain \
why each wrong answer is incorrect.
7. Return ONLY a valid JSON array—no prose, no markdown fences, no extra text.

Output format (strict JSON array):
[
  {{
    "question_number": 1,
    "question": "<question text ending with ?>",
    "choices": {{
      "A": "<choice text>",
      "B": "<choice text>",
      "C": "<choice text>",
      "D": "<choice text>"
    }},
    "correct_answer": "<A|B|C|D>",
    "explanation": "<detailed explanation>"
  }}
]
"""

HUMAN_PROMPT = """\
Generate {num_questions} multiple-choice questions based on the context below.

=== CONTEXT START ===
{context}
=== CONTEXT END ===
"""


# ── Internal helpers ───────────────────────────────────────────────────────────

def _build_context_from_docs(docs) -> str:
    """Joins a list of Documents into a single context string."""
    return "\n\n---\n\n".join(
        doc.page_content for doc in docs if doc.page_content.strip()
    )


def _parse_json_response(raw: str) -> list[QuestionDict]:
    """
    Robustly parses the LLM response string into a list of question dicts.

    Handles:
    - Raw JSON arrays
    - JSON wrapped in ```json … ``` fences
    - Minor leading/trailing whitespace

    Raises:
        ValueError: If no valid JSON array can be extracted.
    """
    # Strip markdown code fences if present
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Locate the JSON array boundaries
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            "LLM response does not contain a JSON array. "
            f"Raw response (first 500 chars):\n{raw[:500]}"
        )

    json_str = text[start : end + 1]

    try:
        questions: list[QuestionDict] = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse LLM JSON response: {exc}\n"
            f"Extracted JSON string (first 500 chars):\n{json_str[:500]}"
        ) from exc

    if not isinstance(questions, list):
        raise ValueError("Parsed JSON is not a list.")

    return questions


def _validate_question(q: QuestionDict, idx: int) -> QuestionDict:
    """
    Validates a single question dict and fills defaults for missing fields.
    Logs a warning for any structural issues but does not raise.
    """
    required_keys = {"question", "choices", "correct_answer", "explanation"}
    missing = required_keys - set(q.keys())
    if missing:
        logger.warning("Question %d is missing fields: %s", idx + 1, missing)

    choices = q.get("choices", {})
    if not isinstance(choices, dict) or set(choices.keys()) != {"A", "B", "C", "D"}:
        logger.warning("Question %d has malformed choices: %s", idx + 1, choices)

    correct = q.get("correct_answer", "")
    if correct not in ("A", "B", "C", "D"):
        logger.warning(
            "Question %d has invalid correct_answer: '%s'", idx + 1, correct
        )

    # Ensure question_number is set
    q.setdefault("question_number", idx + 1)
    return q


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_questions(
    vector_store: FAISS,
    num_questions: int | None = None,
) -> list[QuestionDict]:
    """
    Generates original multiple-choice questions from document context.

    Strategy:
    - Runs several broad topic queries against the FAISS retriever to ensure
      coverage across all document sections.
    - Deduplicates retrieved chunks by content hash.
    - Passes the combined context to the LLM via a ChatPromptTemplate.
    - Parses and validates the returned JSON.

    Args:
        vector_store: Populated FAISS instance with the document chunks.
        num_questions: How many questions to generate. Defaults to NUM_QUESTIONS.

    Returns:
        List of validated QuestionDict objects.

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not set.
        ValueError: If the LLM returns unparseable output.
    """
    if not config.OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )

    num_questions = num_questions or config.NUM_QUESTIONS

    # ── Step 1: Retrieve broad, representative context ────────────────────────
    # Using multiple topic queries to maximise chapter coverage
    broad_queries = [
        "cloud computing fundamentals and characteristics",
        "service models IaaS PaaS SaaS serverless",
        "deployment models public private hybrid cloud",
        "cloud security shared responsibility IAM encryption",
        "scalability availability disaster recovery",
        "cloud cost management FinOps pricing models",
        "containers Kubernetes microservices",
        "cloud networking VPC load balancing",
    ]

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4},
    )

    seen_contents: set[str] = set()
    all_docs = []

    for query in broad_queries:
        docs = retriever.invoke(query)
        for doc in docs:
            content_key = doc.page_content[:200]  # Deduplicate by content prefix
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                all_docs.append(doc)

    logger.info(
        "Retrieved %d unique context chunks from %d queries",
        len(all_docs),
        len(broad_queries),
    )

    if not all_docs:
        raise ValueError("No documents retrieved from the vector store.")

    context = _build_context_from_docs(all_docs)

    # ── Step 2: Build the LangChain LCEL chain ────────────────────────────────
    llm = ChatOpenAI(
        model=config.OPENAI_MODEL,
        api_key=config.OPENAI_API_KEY,
        temperature=config.TEMPERATURE,
        max_retries=3,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ]
    )

    chain = prompt | llm | StrOutputParser()

    # ── Step 3: Invoke the chain ───────────────────────────────────────────────
    logger.info(
        "Invoking LLM (%s) to generate %d questions …",
        config.OPENAI_MODEL,
        num_questions,
    )

    raw_response: str = chain.invoke(
        {
            "num_questions": num_questions,
            "context": context,
        }
    )

    logger.debug("Raw LLM response:\n%s", raw_response[:1000])

    # ── Step 4: Parse + validate ───────────────────────────────────────────────
    questions = _parse_json_response(raw_response)
    validated = [_validate_question(q, i) for i, q in enumerate(questions)]

    logger.info("Successfully generated and validated %d questions.", len(validated))
    return validated


# ── Backward-compat re-export ─────────────────────────────────────────────────
# Canonical implementation moved to src/generation/qa_generator.py.
from src.generation.qa_generator import generate_questions  # noqa: F811, E402
