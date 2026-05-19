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

from __future__ import annotations   # make all type annotations lazy strings

import json
import re
import time
from dataclasses import dataclass
from typing import Any

# Heavy LangChain / Groq imports are done LAZILY inside functions so that
# importing this module in a background worker thread does NOT trigger
# sentence-transformers or other slow library initialisation.
#
# Rule: stdlib only at module level; third-party inside def bodies.

def _parse_retry_after(exc: Exception) -> float | None:
    m = re.search(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", str(exc))
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2))
    return None


# langsmith.traceable checks LANGCHAIN_TRACING_V2 at call time (not import time),
# so it correctly activates whenever the env var is set — even if it was set after
# the module was first imported (e.g. by setup_langsmith() in server.py).
try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):  # type: ignore[misc]
        """No-op when langsmith is not installed."""
        def decorator(fn):
            return fn
        return args[0] if args and callable(args[0]) else decorator

import config
from observability.logger import get_logger

logger = get_logger(__name__)

# ─── LLM retry + fallback ─────────────────────────────────────────────────────

_RETRYABLE_SIGNALS = (
    "rate_limit", "timeout", "503", "502", "500",
    "overloaded", "connection", "too many requests", "429",
)


def _is_retryable(exc: Exception) -> bool:
    msg = f"{type(exc).__name__} {exc}".lower()
    return any(sig in msg for sig in _RETRYABLE_SIGNALS)


@dataclass
class LLMCallResult:
    content: str
    provider: str
    model: str
    attempts: int
    total_latency_ms: float


def _build_groq_llm(model: str):
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=model,
        api_key=config.GROQ_API_KEY,
        temperature=config.TEMPERATURE,
        max_retries=0,
        request_timeout=30,
    )


def _build_gemini_llm():
    """Google Gemini — free-tier fallback. Key must be from aistudio.google.com/apikey."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        google_api_key=config.GEMINI_API_KEY,
        temperature=config.TEMPERATURE,
        max_retries=0,
    )


def _hf_provider_for(model_id: str) -> str:
    """Look up the live inference provider for a HuggingFace model."""
    import urllib.request as _ur, json as _js
    try:
        req = _ur.Request(
            f"https://huggingface.co/api/models/{model_id}?expand=inferenceProviderMapping",
            headers={"Authorization": f"Bearer {config.HF_API_KEY}"},
        )
        with _ur.urlopen(req, timeout=10) as r:
            info = _js.loads(r.read())
        mapping = info.get("inferenceProviderMapping", {})
        for provider, details in mapping.items():
            if details.get("status") == "live":
                return provider
    except Exception:
        pass
    return "hf-inference"  # fallback


def _build_hf_llm():
    """
    Hugging Face Inference via the router (auto-detects provider per model).
    Token MUST have 'Make calls to the serverless Inference API' permission.
    Fix: huggingface.co/settings/tokens → New token (Fine-grained) →
         Inference → tick 'Make calls to the serverless Inference API'.
    """
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
    provider = _hf_provider_for(config.HF_MODEL)
    logger.info("HuggingFace provider for %s: %s", config.HF_MODEL, provider)
    endpoint = HuggingFaceEndpoint(
        repo_id=config.HF_MODEL,
        huggingfacehub_api_token=config.HF_API_KEY,
        max_new_tokens=4096,
        temperature=config.TEMPERATURE,
        task="text-generation",
        provider=provider,
    )
    return ChatHuggingFace(llm=endpoint)


def _providers() -> list[tuple[str, str, callable]]:
    """
    Provider order — optimised for lowest latency first, quality fallback.

    Groq LPU hardware delivers 10-20× faster token generation than GPU-based
    serving. Putting Groq first cuts LLM latency from ~3 s to ~0.6 s.

      1. Groq llama-3.3-70b-versatile  — PRIMARY: best quality at Groq speed
      2. Groq llama-3.1-8b-instant     — FALLBACK 1: 3× faster, 3× higher quota
      3. Groq gemma2-9b-it             — FALLBACK 2: independent quota bucket
      4. Google Gemini                 — FALLBACK 3: quality net (slower GPU)
      5. Groq llama-3.2-3b-preview     — FALLBACK 4: emergency, near-zero latency
      6. HuggingFace                   — LAST RESORT: high latency, unreliable

    Each Groq model has an INDEPENDENT daily/per-minute quota, so rotating
    through them maximises capacity before reaching slower external providers.
    """
    providers = []

    # ── 1–3. Groq models — fastest inference (Groq LPU hardware) ─────────────
    # Order: quality-first (70B), then high-quota fast (8B), then spare bucket
    groq_models = [
        config.GROQ_MODEL,           # llama-3.3-70b-versatile  (~600ms, 6k TPM)
        config.GROQ_FALLBACK_MODEL,  # llama-3.1-8b-instant     (~150ms, 20k TPM)
        "gemma2-9b-it",              # spare quota bucket        (~350ms, 15k TPM)
        "llama-3.2-3b-preview",      # emergency ultra-fast      (~100ms,  7k TPM)
    ]
    seen: set[str] = set()
    for m in groq_models:
        if m and m not in seen:
            seen.add(m)
            providers.append(("groq", m, lambda _m=m: _build_groq_llm(_m)))

    # ── 4. Gemini — quality backstop when all Groq quotas exhausted ──────────
    # Gemini 2.5 Flash uses thinking tokens which add 0.5–2 s overhead;
    # good quality insurance but not suitable as the primary latency path.
    if config.GEMINI_API_KEY:
        providers.append(("gemini", config.GEMINI_MODEL, _build_gemini_llm))

    # ── 5. HuggingFace — absolute last resort (2–8 s, shared infra) ──────────
    if config.HF_API_KEY:
        providers.append(("huggingface", config.HF_MODEL, _build_hf_llm))

    return providers


def call_llm_with_retry(
    chain_input: dict,
    prompt,
    request_id: str = "unknown",
    max_attempts: int = 2,
    base_delay: float = 1.0,
) -> LLMCallResult:
    """
    Invoke the LLM chain with exponential-backoff retry and multi-provider fallback.

    Attempt order:
      1. Primary Groq model (GROQ_MODEL)
      2. Groq fallback model (GROQ_FALLBACK_MODEL)
      3. gemma2-9b-it on Groq  (higher independent quota)
      4. llama-3.2-3b-preview on Groq (highest Groq quota)
      5. Google Gemini (gemini-2.0-flash) — if GEMINI_API_KEY is set

    Switches to the next provider immediately on daily-quota exhaustion or
    after max_attempts transient retries.
    """
    from langchain_core.output_parsers import StrOutputParser

    t_start = time.monotonic()

    for backend, model_name, llm_factory in _providers():
        try:
            llm   = llm_factory()
            chain = prompt | llm | StrOutputParser()
        except Exception as build_exc:
            logger.warning("Failed to build LLM (%s %s): %s", backend, model_name, build_exc)
            continue

        for attempt in range(1, max_attempts + 1):
            try:
                content = chain.invoke(chain_input)
                latency = (time.monotonic() - t_start) * 1000
                logger.info(
                    "LLM call succeeded backend=%s attempt=%d latency=%.0fms",
                    backend, attempt, latency,
                    extra={"request_id": request_id, "backend": backend,
                           "attempt": attempt, "latency_ms": round(latency, 1)},
                )
                return LLMCallResult(
                    content=content,
                    provider=backend,
                    model=model_name,
                    attempts=attempt,
                    total_latency_ms=round(latency, 1),
                )

            except Exception as exc:
                retryable = _is_retryable(exc)
                logger.warning(
                    "LLM attempt failed [%d/%d] backend=%s retryable=%s error=%s",
                    attempt, max_attempts, backend, retryable, str(exc)[:300],
                    extra={"request_id": request_id, "backend": backend,
                           "attempt": attempt, "error_type": type(exc).__name__},
                )

                if not retryable:
                    break  # non-retryable (bad input, auth) — try next provider

                retry_after = _parse_retry_after(exc)
                if retry_after is not None and retry_after > 60:
                    # Daily limit: switching immediately is better than waiting
                    logger.warning("Quota exhausted on %s (%.0fs wait) — switching provider",
                                   backend, retry_after)
                    break

                wait = min((retry_after or base_delay * (2 ** (attempt - 1))) + 1, 30)
                if attempt < max_attempts:
                    logger.info("Rate-limited — waiting %.1f s", wait)
                    time.sleep(wait)

        logger.warning("Provider exhausted: backend=%s — trying next", backend)

    latency = (time.monotonic() - t_start) * 1000
    raise RuntimeError(
        "The AI service is temporarily unavailable due to high demand. "
        "Please try again in a few minutes."
        f" (request_id={request_id})"
    )

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
    request_id: str = "unknown",
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
        EnvironmentError: If GROQ_API_KEY is not configured.
        ValueError:       If the vector store is empty or LLM returns bad JSON.
    """
    if not config.GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Add it to a .env file at the project root."
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
            "embedding_model": config.EMBEDDING_MODEL,
        },
    )

    if not unique_docs:
        raise ValueError(
            "No documents retrieved from the vector store. "
            "Ensure the index was built successfully."
        )

    context = _build_context_from_docs(unique_docs)

    # ── Step 2: Build prompt ──────────────────────────────────────────────────
    from langchain_core.prompts import ChatPromptTemplate  # lazy
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human",  HUMAN_PROMPT),
    ])

    # ── Step 3: Invoke with retry + fallback ──────────────────────────────────
    logger.info(
        "Invoking LLM to generate %d questions (context: %d chars) …",
        num_questions, len(context),
        extra={"num_questions": num_questions, "context_len": len(context)},
    )
    result = call_llm_with_retry(
        chain_input={"num_questions": num_questions, "context": context},
        prompt=prompt,
        request_id=request_id,
    )
    raw_response = result.content

    logger.info(
        "LLM response received",
        extra={
            "provider":   result.provider,
            "model":      result.model,
            "attempts":   result.attempts,
            "latency_ms": result.total_latency_ms,
            "response_len": len(raw_response),
        },
    )

    # ── Step 4: Parse + validate ──────────────────────────────────────────────
    questions = _parse_json_response(raw_response)
    validated = [_validate_question(q, i) for i, q in enumerate(questions)]

    logger.info(
        "Generated and validated %d questions.",
        len(validated),
        extra={"question_count": len(validated)},
    )
    return validated


# ─── Large-document chunking constants ────────────────────────────────────────
#
# Groq free-tier TPM limits per model:
#   llama-3.3-70b  : 6 000 TPM  (≈24K chars/call fits in 1-min window)
#   llama-3.1-8b   : 20 000 TPM (≈80K chars/call)
#   gemma2-9b-it   : 15 000 TPM, but only 8K token *context* (≈32K chars max per call)
#   Gemini 2.5 Flash: 250 000 TPM, 1M token context (≈4M chars per call)
#
# Strategy:
#   • Docs ≤ _SINGLE_PASS_CHARS  → one LLM call with full text
#   • Docs >  _SINGLE_PASS_CHARS → map-reduce: split into _CHUNK_CHARS slices,
#     sample up to _MAX_QA_CHUNKS / _MAX_SUM_CHUNKS representative chunks,
#     run one LLM call per chunk, then synthesise.
#
# _CHUNK_CHARS is kept at 20 000 (≈5K tokens) so every Groq model including
# gemma2-9b-it (8K context) can handle any single chunk without a context error.

_CHUNK_CHARS     = 20_000   # max chars per LLM chunk call
_CHUNK_OVERLAP   = 300      # overlap to preserve context across chunk boundaries
_SINGLE_PASS_CHARS = 60_000 # docs ≤ this are sent in a single call (3× old limit)
_MAX_QA_CHUNKS   = 20       # max sample chunks used for Q&A  generation
_MAX_SUM_CHUNKS  = 30       # max chunks processed in summary map phase


def _smart_truncate(text: str, max_chars: int) -> str:
    """
    Safety-net truncation: head 60% + tail 40%.
    Used only as a last resort when the combined chunk summaries themselves
    overflow a single synthesis call.
    """
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.60)
    tail = max_chars - head
    return (
        text[:head]
        + "\n\n[... middle section omitted for length ...]\n\n"
        + text[-tail:]
    )


def _split_into_chunks(text: str, chunk_size: int = _CHUNK_CHARS,
                        overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks, preferring natural break points
    (paragraph → newline → sentence → word boundary).
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    total = len(text)

    while start < total:
        end = min(start + chunk_size, total)
        if end < total:
            search_from = start + (chunk_size * 3 // 4)
            for sep in ("\n\n", "\n", ". ", "! ", "? ", " "):
                p = text.rfind(sep, search_from, end)
                if p != -1:
                    end = p + len(sep)
                    break
        chunks.append(text[start:end].strip())
        if end >= total:
            break  # reached end of document — stop
        start = max(end - overlap, start + 1)

    return [c for c in chunks if c]


def _select_diverse_chunks(chunks: list[str], n: int) -> list[tuple[int, str]]:
    """
    Select n maximally topic-diverse chunks using TF-IDF + greedy farthest-point.

    Algorithm:
      1. Seed selection with chunk 0 (intro/overview) and chunk -1 (conclusion).
      2. At each step, pick the candidate chunk whose maximum cosine similarity
         to any already-selected chunk is the lowest (most different topic).
      3. Repeat until n chunks are selected, then sort by document order.

    This beats even-spacing because two adjacent chunks about the same topic
    are treated as one — only the more informative one is kept.

    Falls back to even spacing if sklearn is unavailable or the matrix build fails.
    """
    if len(chunks) <= n:
        return list(enumerate(chunks))

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        vectorizer = TfidfVectorizer(
            max_features=512,
            stop_words="english",
            sublinear_tf=True,      # dampen dominant high-frequency terms
            min_df=1,
        )
        matrix = vectorizer.fit_transform(chunks).toarray()  # (n_chunks, n_features)
        n_total = len(chunks)

        selected: list[int] = [0]               # always include the intro chunk
        if n > 1:
            selected.append(n_total - 1)        # always include the conclusion chunk

        while len(selected) < n:
            sel_vecs = matrix[selected]
            # Max similarity of every chunk to any already-selected chunk
            max_sims = cosine_similarity(matrix, sel_vecs).max(axis=1)
            for idx in selected:
                max_sims[idx] = 2.0             # exclude already-selected (score > 1)
            selected.append(int(np.argmin(max_sims)))   # most dissimilar chunk

        selected.sort()                         # restore document order
        result = [(i, chunks[i]) for i in selected]
        logger.debug(
            "Diversity selection: %d/%d chunks chosen (TF-IDF farthest-point)",
            n, n_total,
        )
        return result

    except Exception as exc:
        logger.debug("TF-IDF diversity selection unavailable (%s) — even spacing", exc)
        step = len(chunks) / n
        indices = [int(i * step) for i in range(n)]
        return [(i, chunks[i]) for i in indices]


def _deduplicate_questions(
    questions: list[QuestionDict],
    threshold: float = 0.65,
) -> list[QuestionDict]:
    """
    Remove near-duplicate questions by Jaccard token-overlap on question text.

    Two questions are duplicates when the Jaccard similarity of their
    lower-cased word sets exceeds `threshold`.  threshold=0.65 blocks
    paraphrasings ("What is X?" vs "Which describes X?") that occur when
    two overlapping chunks both generate questions about the same concept,
    while still allowing distinct questions on the same broad topic.
    """
    def _jaccard(a: str, b: str) -> float:
        sa, sb = set(a.lower().split()), set(b.lower().split())
        return len(sa & sb) / len(sa | sb) if sa | sb else 1.0

    kept: list[QuestionDict] = []
    for q in questions:
        q_text = q.get("question", "")
        if not any(_jaccard(q_text, k.get("question", "")) >= threshold for k in kept):
            kept.append(q)

    removed = len(questions) - len(kept)
    if removed:
        logger.info("Deduplication removed %d near-duplicate question(s)", removed)
    return kept


# ─── Prompt templates ──────────────────────────────────────────────────────────

_SUMMARISE_SYSTEM = """\
You are a document analysis assistant. Analyse the provided document text and \
produce a well-structured summary with these sections:

## Overview
A 2–3 sentence description of what the document covers.

## Key Topics
Bullet list of the main topics / sections covered.

## Key Facts & Details
The most important facts, data points, and details from the document.

## Key Takeaways
3–5 concise points a reader should remember.

Format your response in clean Markdown. Be comprehensive but concise."""

_SUMMARISE_HUMAN = "Analyse and structure the following document text:\n\n{text}"

# Map phase — one short summary per chunk
_CHUNK_SUM_SYSTEM = """\
You are a document analysis assistant.
Summarise the following section of a larger document in 4–6 sentences.
Focus on key facts, arguments, concepts, and details specific to this section.
Be specific and informative."""

_CHUNK_SUM_HUMAN = "[Section {n} of {total}]\n\n{text}"

# Reduce phase — synthesise all chunk summaries into a final structured summary
_COMBINE_SUM_SYSTEM = """\
You are a document synthesis expert.
You have been given short summaries of all sections of a large document.
Synthesise them into ONE comprehensive, well-structured document summary:

## Overview
2–3 sentences describing what the full document covers.

## Key Topics
Bullet list of all main topics covered across the document.

## Key Facts & Details
The most important facts, data points, and details drawn from across all sections.

## Key Takeaways
3–5 concise points a reader should remember.

Format in clean Markdown. Be comprehensive but concise."""

_COMBINE_SUM_HUMAN = "Section summaries to synthesise:\n\n{sections}"

# Q&A generation
_QA_DIRECT_SYSTEM = """\
You are an expert educator who creates rigorous multiple-choice exam questions.

Given the document text below, generate exactly {num_questions} multiple-choice question(s).

Return ONLY a valid JSON array. Each element must follow this exact schema:
{{
  "question_number": <int>,
  "question": "<question text>",
  "choices": {{"A": "<text>", "B": "<text>", "C": "<text>", "D": "<text>"}},
  "correct_answer": "<A|B|C|D>",
  "explanation": "<brief explanation>"
}}

Rules:
- Questions must be answerable from the provided text
- Each question must have exactly 4 choices (A-D) with exactly one correct answer
- Vary difficulty: include recall, comprehension, and analysis questions
- Do not add any text outside the JSON array"""

_QA_DIRECT_HUMAN = "Document text:\n\n{text}\n\nGenerate {num_questions} MCQ question(s)."


# ─── Internal helpers ──────────────────────────────────────────────────────────

def _parse_qa_response(raw: str) -> list[QuestionDict]:
    """Extract and parse JSON array from raw LLM output."""
    m = re.search(r"\[.*\]", raw.strip(), re.DOTALL)
    if not m:
        raise ValueError(f"LLM did not return a JSON array. Raw (first 500 chars):\n{raw[:500]}")
    return json.loads(m.group(0))


def _normalise_questions(raw_list: list, limit: int) -> list[QuestionDict]:
    """Normalise and re-number question dicts, trimming to at most `limit`."""
    result: list[QuestionDict] = []
    for i, q in enumerate(raw_list[:limit], start=1):
        result.append({
            "question_number": i,
            "question":        str(q.get("question", "")),
            "choices":         q.get("choices", {}),
            "correct_answer":  str(q.get("correct_answer", "A")),
            "explanation":     str(q.get("explanation", "")),
        })
    return result


# ─── Q&A generation ────────────────────────────────────────────────────────────

@traceable(name="generate_questions_from_text", run_type="llm", tags=["generation", "llm"])
def generate_questions_from_text(
    text: str,
    num_questions: int | None = None,
    request_id: str = "unknown",
) -> list[QuestionDict]:
    """
    Generate MCQ questions directly from raw document text — no RAG needed.

    Small documents (≤ 60 000 chars, ~30 pages):
        Single LLM call with the full text.

    Large documents (> 60 000 chars, up to 1 000+ pages):
        Map-reduce: split into 20 000-char chunks, sample up to
        _MAX_QA_CHUNKS evenly across the full document, generate
        questions per chunk, then merge and renumber.

    This ensures every part of the document — beginning, middle, and end —
    contributes questions rather than only the opening pages.
    """
    if not config.GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY is not set.")

    num_questions = num_questions or config.NUM_QUESTIONS

    from langchain_core.prompts import ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages([
        ("system", _QA_DIRECT_SYSTEM),
        ("human",  _QA_DIRECT_HUMAN),
    ])

    # ── Small document: single pass ────────────────────────────────────────────
    if len(text) <= _SINGLE_PASS_CHARS:
        result = call_llm_with_retry(
            chain_input={"text": text, "num_questions": num_questions},
            prompt=prompt,
            request_id=request_id,
        )
        questions = _normalise_questions(_parse_qa_response(result.content), num_questions)
        logger.info(
            "Q&A single-pass: %d questions via %s (%.0f ms, %d chars in)",
            len(questions), result.model, result.total_latency_ms, len(text),
        )
        return questions

    # ── Large document: map-reduce with diversity-aware chunk selection ────────
    chunks = _split_into_chunks(text, _CHUNK_CHARS, _CHUNK_OVERLAP)
    total_chunks = len(chunks)

    # Diversity selection: pick maximally topic-diverse chunks (TF-IDF farthest-point)
    # so we cover different subjects rather than repeating the most prominent topic.
    n_sample = min(total_chunks, _MAX_QA_CHUNKS)
    selected = _select_diverse_chunks(chunks, n_sample)

    # Questions per chunk — ceiling so we get at least num_questions total
    qs_per_chunk = max(1, (num_questions + len(selected) - 1) // len(selected))

    logger.info(
        "Q&A map-reduce: %d chars / %d total chunks → %d diverse chunks selected "
        "(%d q/chunk, %d requested)",
        len(text), total_chunks, len(selected), qs_per_chunk, num_questions,
    )

    all_raw: list[QuestionDict] = []
    for seq, (chunk_idx, chunk) in enumerate(selected):
        try:
            res = call_llm_with_retry(
                chain_input={"text": chunk, "num_questions": qs_per_chunk},
                prompt=prompt,
                request_id=f"{request_id}-c{chunk_idx}",
            )
            chunk_qs = _parse_qa_response(res.content)
            all_raw.extend(chunk_qs)
            logger.info(
                "Q&A chunk %d/%d (doc-chunk %d): %d questions via %s",
                seq + 1, len(selected), chunk_idx, len(chunk_qs), res.model,
            )
        except Exception as exc:
            logger.warning("Q&A chunk %d/%d failed: %s", seq + 1, len(selected), exc)

        if seq < len(selected) - 1:
            time.sleep(1.5)   # breathing room for Groq TPM limits

    # Deduplicate before normalising: remove near-identical questions that arise
    # when two topically similar chunks independently generate the same question.
    deduped = _deduplicate_questions(all_raw)
    questions = _normalise_questions(deduped, num_questions)
    logger.info(
        "Q&A map-reduce complete: %d/%d questions from %d diverse chunks "
        "(%d total, %d chars) — %d duplicates removed",
        len(questions), num_questions, len(selected), total_chunks, len(text),
        len(all_raw) - len(deduped),
    )
    return questions


# ─── Text summarisation ────────────────────────────────────────────────────────

@traceable(name="summarize_text", run_type="llm", tags=["generation", "llm"])
def summarize_text(text: str, request_id: str = "unknown") -> str:
    """
    Produce a structured Markdown summary of any document.

    Small documents (≤ 60 000 chars, ~30 pages):
        Single LLM call with full text.

    Large documents (> 60 000 chars, up to 1 000+ pages):
        Map phase  — one short paragraph summary per chunk (up to 30 chunks,
                     sampled evenly if the document has more).
        Reduce phase — synthesise all chunk summaries into one final
                       structured summary (Overview / Key Topics /
                       Key Facts / Key Takeaways).
    """
    if not config.GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY is not set.")

    from langchain_core.prompts import ChatPromptTemplate

    # ── Small document: single pass ────────────────────────────────────────────
    if len(text) <= _SINGLE_PASS_CHARS:
        prompt = ChatPromptTemplate.from_messages([
            ("system", _SUMMARISE_SYSTEM),
            ("human",  _SUMMARISE_HUMAN),
        ])
        result = call_llm_with_retry(
            chain_input={"text": text},
            prompt=prompt,
            request_id=request_id,
        )
        logger.info(
            "Summary single-pass: %d chars in → %d chars out (provider=%s)",
            len(text), len(result.content), result.provider,
        )
        return result.content

    # ── Large document: map-reduce with diversity-aware chunk selection ────────
    chunks = _split_into_chunks(text, _CHUNK_CHARS, _CHUNK_OVERLAP)
    total_chunks = len(chunks)

    # For summary we WANT all topics represented, so use diversity selection
    # to avoid over-summarising the most common topic in the document.
    n_sample = min(total_chunks, _MAX_SUM_CHUNKS)
    selected_pairs = _select_diverse_chunks(chunks, n_sample)
    selected_chunks = [c for _, c in selected_pairs]

    n = len(selected_chunks)
    logger.info(
        "Summary map-reduce: %d chars / %d total chunks → %d diverse chunks selected",
        len(text), total_chunks, n,
    )

    # Map phase: short summary of each selected chunk
    chunk_prompt = ChatPromptTemplate.from_messages([
        ("system", _CHUNK_SUM_SYSTEM),
        ("human",  _CHUNK_SUM_HUMAN),
    ])
    chunk_summaries: list[str] = []
    for i, chunk in enumerate(selected_chunks):
        try:
            res = call_llm_with_retry(
                chain_input={"text": chunk, "n": i + 1, "total": n},
                prompt=chunk_prompt,
                request_id=f"{request_id}-s{i}",
            )
            chunk_summaries.append(f"**Section {i + 1}/{n}:**\n{res.content.strip()}")
            logger.info("Summary chunk %d/%d complete via %s", i + 1, n, res.model)
        except Exception as exc:
            logger.warning("Summary chunk %d/%d failed: %s", i + 1, n, exc)
            chunk_summaries.append(f"**Section {i + 1}/{n}:** [section unavailable]")

        if i < n - 1:
            time.sleep(1.0)   # respect Groq TPM limits

    # Reduce phase: synthesise chunk summaries into final structured summary
    combined = "\n\n".join(chunk_summaries)
    # Safety net: if combined summaries themselves overflow a single call, truncate
    if len(combined) > _SINGLE_PASS_CHARS:
        combined = _smart_truncate(combined, _SINGLE_PASS_CHARS)

    combine_prompt = ChatPromptTemplate.from_messages([
        ("system", _COMBINE_SUM_SYSTEM),
        ("human",  _COMBINE_SUM_HUMAN),
    ])
    final = call_llm_with_retry(
        chain_input={"sections": combined},
        prompt=combine_prompt,
        request_id=f"{request_id}-s-combine",
    )

    logger.info(
        "Summary map-reduce complete: %d chunks → %d chars final summary (provider=%s)",
        n, len(final.content), final.provider,
    )
    return final.content
