"""
src/generation/qa_generator.py
────────────────────────────────
Uses LangChain LCEL + OpenAI Chat API to generate original multiple-choice
practice questions from retrieved document context.

Architecture
────────────
The chain follows the LangChain Expression Language (LCEL) pipe model:

    ChatPromptTemplate | ChatOpenAI | StrOutputParser
           │                  │               │
           │                  │               └─ converts AIMessage → str
           │                  └─ gpt-4o, temperature 0.3
           └─ system + human messages, filled with num_questions + context

Why LCEL?
─────────
LCEL (LangChain Expression Language) composes Runnable objects with the `|`
operator.  Each step receives the output of the previous step as input.
Benefits:
  • Automatically supports async, streaming, and batching.
  • Each step is individually testable and replaceable.
  • Adding middleware (logging, retries, caching) requires no structural changes.

Why multiple broad queries?
────────────────────────────
A single generic query like "cloud computing" would retrieve the top-k chunks
most similar to that query — likely the introduction and a few well-known
sections, biasing question generation toward those topics.

By using 8 topic-specific queries that map to the 8 document chapters, we
sample 4 unique chunks per topic, accumulate them, and deduplicate by content
prefix.  This produces a balanced, representative context that covers all
chapters roughly equally.

QuestionDict schema
────────────────────
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
    generate_questions(vector_store, num_questions) → list[QuestionDict]
"""

import json
import re
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import traceable

import config
from observability.logger import get_logger

logger = get_logger(__name__)

# Type alias: a single Q&A dict as returned by the LLM and validated by us
QuestionDict = dict[str, Any]

# ─── Prompt templates ──────────────────────────────────────────────────────────
#
# Two-message prompt:
#   1. system  — persona + output rules (stable across all invocations)
#   2. human   — the actual task with injected context (variable per call)
#
# Why separate system + human messages?
#   OpenAI's chat completion API gives the system message special weight.
#   Placing the structural rules (valid JSON, exact count, etc.) in the
#   system message reduces the likelihood of the model ignoring them.
#   The human message mimics a real user instruction, which the model is
#   trained to follow.
#
# Why f-string template variables ({num_questions}, {context})?
#   ChatPromptTemplate.from_messages() uses Python-style {variable} placeholders.
#   These are resolved at call time by passing a dict to chain.invoke().
#   Double-braces ({{ }}) are literal braces in the output (e.g. JSON format).
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


# ─── Internal helpers ──────────────────────────────────────────────────────────

def _build_context_from_docs(docs) -> str:
    """
    Joins a list of LangChain Documents into a single context string.

    Each document is separated by a horizontal-rule marker ("---") to give
    the LLM a visual hint that the content shifts to a different source chunk.
    Empty/whitespace-only chunks are filtered out to avoid wasting tokens.

    Args:
        docs: Iterable of LangChain Document objects.

    Returns:
        Concatenated context string.
    """
    return "\n\n---\n\n".join(
        doc.page_content for doc in docs if doc.page_content.strip()
    )


def _parse_json_response(raw: str) -> list[QuestionDict]:
    """
    Robustly extracts a JSON array from the raw LLM output string.

    The LLM sometimes wraps JSON in markdown code fences (```json ... ```)
    even when explicitly told not to.  This function handles both cases:

      Case 1 — plain JSON:      "[{...}, {...}]"
      Case 2 — fenced JSON:     "```json\\n[{...}]\\n```"

    Extraction strategy:
      1. Look for a markdown fence pattern; if found, extract the inner text.
      2. Find the first "[" and last "]" in the (possibly unwrapped) text.
      3. Call json.loads() on the extracted slice.

    Args:
        raw: Raw string response from the LLM.

    Returns:
        List of question dicts.

    Raises:
        ValueError: If no valid JSON array can be extracted or parsed.
    """
    text = raw.strip()

    # Step 1: Remove markdown code fences if the model added them anyway
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()
        logger.debug("Markdown code fence stripped from LLM response.")

    # Step 2: Extract the JSON array boundaries
    start = text.find("[")
    end   = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            "LLM response does not contain a JSON array.\n"
            f"Raw response (first 500 chars):\n{raw[:500]}"
        )

    json_str = text[start : end + 1]

    # Step 3: Parse
    try:
        questions: list[QuestionDict] = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON parse failed: {exc}\n"
            f"Extracted JSON (first 500 chars):\n{json_str[:500]}"
        ) from exc

    if not isinstance(questions, list):
        raise ValueError(
            f"Parsed JSON is not a list, got: {type(questions).__name__}"
        )

    return questions


def _validate_question(q: QuestionDict, idx: int) -> QuestionDict:
    """
    Validates structural integrity of a single question dict.

    Does NOT raise on validation failures — only logs warnings.
    This ensures the pipeline continues to deliver partial results even
    when the LLM produces an imperfect response for one or two questions.

    Validations performed:
      • All required top-level keys are present.
      • "choices" is a dict with exactly the keys A, B, C, D.
      • "correct_answer" is one of "A", "B", "C", "D".
      • "question_number" is set (filled with idx+1 if missing).

    Args:
        q:   Question dict from _parse_json_response().
        idx: Zero-based position in the returned list (for log messages).

    Returns:
        The (possibly mutated) question dict.
    """
    required_keys = {"question", "choices", "correct_answer", "explanation"}
    missing = required_keys - set(q.keys())
    if missing:
        logger.warning(
            "Question %d missing fields: %s",
            idx + 1,
            missing,
            extra={"question_idx": idx, "missing_fields": list(missing)},
        )

    choices = q.get("choices", {})
    if not isinstance(choices, dict) or set(choices.keys()) != {"A", "B", "C", "D"}:
        logger.warning(
            "Question %d has malformed choices: %s",
            idx + 1,
            choices,
            extra={"question_idx": idx},
        )

    correct = q.get("correct_answer", "")
    if correct not in ("A", "B", "C", "D"):
        logger.warning(
            "Question %d has invalid correct_answer: '%s'",
            idx + 1,
            correct,
            extra={"question_idx": idx, "correct_answer": correct},
        )

    # Fill question_number if the LLM omitted it
    q.setdefault("question_number", idx + 1)
    return q


# ─── Public API ────────────────────────────────────────────────────────────────

@traceable(
    name="generate_questions",
    run_type="chain",
    # Tags appear as filterable labels in the LangSmith UI.
    # The actual num_questions value is captured from the function's input.
    tags=["qa-generation", "llm"],
)
def generate_questions(
    vector_store: FAISS,
    num_questions: int | None = None,
) -> list[QuestionDict]:
    """
    Generates original MCQ questions from the document vector store.

    Full pipeline:
      1. Run 8 broad topic queries against the FAISS retriever to collect
         representative context chunks from across all document chapters.
      2. Deduplicate collected chunks by the first 200 characters of content
         (a fast, lightweight proxy for exact deduplication that avoids
         expensive full-text comparison).
      3. Assemble all unique chunks into a single context string.
      4. Build a ChatPromptTemplate | ChatOpenAI | StrOutputParser chain.
      5. Invoke the chain; receive raw JSON string from the LLM.
      6. Parse JSON → list[QuestionDict] and validate each entry.

    Why 8 queries?
      The sample PDF has exactly 8 chapters.  One query per chapter ensures
      each chapter contributes at least 4 unique chunks to the context.
      Duplicate chunks are discarded, so the context stays within the LLM's
      context window even if chunks overlap heavily.

    Why deduplication by content prefix?
      Two chunks are "the same" if their first 200 characters are identical.
      This is cheaper than hashing the full text and effective enough for our
      use case where duplicates only arise from overlapping FAISS results for
      closely related queries.

    Args:
        vector_store:  Populated FAISS vector store.
        num_questions: Override for config.NUM_QUESTIONS.

    Returns:
        Validated list of QuestionDict objects.

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not configured.
        ValueError:       If the vector store is empty or LLM returns bad JSON.
        openai.APIError:  On API communication failure.
    """
    if not config.OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Add it to a .env file at the project root."
        )

    num_questions = num_questions or config.NUM_QUESTIONS

    # ── Step 1: Multi-query retrieval for broad chapter coverage ─────────────
    # Each query string is designed to match vocabulary from one of the 8 chapters.
    # Similarity search will return 4 chunks per query (k=4); after deduplication
    # we typically end up with 20–30 unique chunks from the full document.
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
        search_kwargs={"k": 4},  # 4 chunks per query × 8 queries = up to 32 before dedup
    )

    # Track already-seen chunks to avoid sending duplicate context to the LLM.
    # Using the first 200 chars as the deduplication key: fast and sufficient.
    seen_prefixes: set[str] = set()
    unique_docs = []

    for query in broad_queries:
        docs = retriever.invoke(query)
        for doc in docs:
            prefix = doc.page_content[:200]
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                unique_docs.append(doc)

    logger.info(
        "Retrieved %d unique context chunks from %d topic queries",
        len(unique_docs),
        len(broad_queries),
        extra={
            "unique_chunks":  len(unique_docs),
            "query_count":    len(broad_queries),
            "embedding_model": config.OPENAI_EMBEDDING_MODEL,
        },
    )

    if not unique_docs:
        raise ValueError(
            "No documents retrieved from the vector store. "
            "Ensure the index was built successfully."
        )

    context = _build_context_from_docs(unique_docs)

    # ── Step 2: Build the LCEL chain ─────────────────────────────────────────
    # ChatOpenAI wraps the OpenAI chat completion endpoint.
    # max_retries=3: automatically retries on transient HTTP errors (429, 5xx)
    # temperature=0.3: low randomness → consistent, factual answers
    llm = ChatOpenAI(
        model=config.OPENAI_MODEL,
        api_key=config.OPENAI_API_KEY,
        temperature=config.TEMPERATURE,
        max_retries=3,
    )

    # Two-message prompt: system (rules) + human (task + context)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human",  HUMAN_PROMPT),
    ])

    # LCEL pipe: prompt → LLM → string extractor
    # StrOutputParser converts AIMessage.content to a plain Python str.
    chain = prompt | llm | StrOutputParser()

    # ── Step 3: Invoke the chain ──────────────────────────────────────────────
    logger.info(
        "Invoking '%s' to generate %d questions (context: %d chars) …",
        config.OPENAI_MODEL,
        num_questions,
        len(context),
        extra={
            "model":         config.OPENAI_MODEL,
            "num_questions": num_questions,
            "context_len":   len(context),
        },
    )

    raw_response: str = chain.invoke({
        "num_questions": num_questions,
        "context":       context,
    })

    logger.debug(
        "Raw LLM response (%d chars, first 500 shown):\n%s",
        len(raw_response),
        raw_response[:500],
        extra={"response_len": len(raw_response)},
    )

    # ── Step 4: Parse + validate ──────────────────────────────────────────────
    questions  = _parse_json_response(raw_response)
    validated  = [_validate_question(q, i) for i, q in enumerate(questions)]

    logger.info(
        "Generated and validated %d questions.",
        len(validated),
        extra={"question_count": len(validated)},
    )
    return validated
