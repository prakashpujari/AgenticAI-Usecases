"""
Input & output guardrails for production safety.

What are guardrails?
--------------------
Guardrails are checks that run BEFORE the LLM sees the user's message (input
guardrails) and AFTER the LLM produces a response (output guardrails). They
protect the application from:
  - Malicious users trying to hijack the LLM (prompt injection)
  - Accidental or deliberate exposure of PII in responses
  - Harmful / toxic content in LLM outputs
  - Web attacks such as XSS and SQL injection embedded in prompts
  - Oversized payloads that could cause timeouts or memory pressure

Governance layers (applied in order):
  1. Length & blank checks           – fast, no regex needed
  2. Prompt-injection / OWASP patterns – compiled regex, O(n patterns)
  3. PII detection audit (input)     – logs entities, does NOT block
     PII redaction (output)          – replaces entities with placeholders
  4. OpenAI content moderation       – catches toxic/violent output
  5. User identity & role validation – rejects malformed emails / empty roles
"""
import os
import re
from observability.logger import get_logger
from guardrails.pii_redactor import redact_pii, detect_pii

logger = get_logger("guardrails")

# ---------------------------------------------------------------------------
# Tuneable limits — adjust these constants to match your SLA requirements.
# ---------------------------------------------------------------------------
MAX_INPUT_LENGTH  = 2000      # characters; prevents oversized prompts
MAX_OUTPUT_LENGTH = 10_000    # characters; prevents runaway LLM output

# Regex patterns that indicate prompt-injection or common web-attack vectors.
# Each pattern is compiled once at import time for maximum runtime performance.
BLOCKED_PATTERNS = [
    r"(?i)(ignore previous instructions)",     # classic prompt injection
    r"(?i)(you are now)",                       # persona hijack
    r"(?i)(jailbreak)",                         # jailbreak keyword
    r"(?i)(system\s*prompt)",                   # system-prompt extraction attempt
    r"(?i)(act as (a |an )?)",                  # role-hijack attempts
    r"(?i)(<script.*?>)",                       # XSS injection
    r"(?i)(drop\s+table|delete\s+from|insert\s+into|update\s+.+\s+set)",  # SQLi
    r"(?i)(\/etc\/passwd|\/proc\/self)",       # Linux path traversal
]
# Pre-compile patterns once; re.compile is expensive at scale
_COMPILED = [re.compile(p) for p in BLOCKED_PATTERNS]

# Valid actions the agent can plan (used for allow-list enforcement elsewhere)
VALID_ACTIONS = {"create_ticket", "view_ticket"}

# Regex for validating that `user` is a proper email address.
# We use this as the user identity format (e.g. alice@company.com).
VALID_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class GuardrailViolation(ValueError):
    """
    Custom exception raised when any guardrail check fails.

    Inherits from ValueError so callers can catch it specifically.
    FastAPI catches this in the endpoint and returns a 400 Bad Request.
    """


# ---------------------------------------------------------------------------
# Input guardrails
# ---------------------------------------------------------------------------

def validate_input(user_input: str, user: str, role: str, session_id: str) -> None:
    """
    Run all input guardrail checks.
    Raises GuardrailViolation (HTTP 400) on the first failed check.
    Returns None (implicitly) when all checks pass.

    Args:
        user_input: The raw text submitted by the user.
        user:       User identity string — must be a valid email address.
        role:       RBAC role string (e.g. "PRODUCT_OWNER", "DEVELOPER").
        session_id: Opaque session identifier (min 4 characters).
    """

    # Check 1 — reject empty or whitespace-only input immediately
    if not user_input or not user_input.strip():
        raise GuardrailViolation("Input must not be empty.")
    # Check 2 — reject inputs that would cause token-cost / timeout issues
    if len(user_input) > MAX_INPUT_LENGTH:
        raise GuardrailViolation(
            f"Input exceeds maximum length of {MAX_INPUT_LENGTH} characters."
        )

    # Check 3 — scan for prompt-injection and web-attack patterns
    # We iterate through all compiled patterns; the first match triggers a block.
    for pattern in _COMPILED:
        if pattern.search(user_input):
            logger.warning("Blocked input matches injection pattern", extra={"pattern": pattern.pattern})
            raise GuardrailViolation("Input contains disallowed content.")

    # Check 4 — enforce email format for user identity
    # This prevents privilege-escalation via crafted user strings.
    if not VALID_EMAIL_RE.match(user):
        raise GuardrailViolation("Invalid user identifier format.")

    # Check 5 — role must not be blank (RBAC downstream depends on it)
    if not role or not role.strip():
        raise GuardrailViolation("Role must not be empty.")

    # Check 6 — session_id sanity: must be present and at least 4 chars
    if not session_id or len(session_id) < 4:
        raise GuardrailViolation("session_id is too short or missing.")

    # Check 7 — PII audit on input.
    # We log detected PII entity types for compliance monitoring but we do NOT
    # block the request here. Instead, PII is redacted from the OUTPUT so the
    # LLM still gets the full context it needs to answer correctly.
    pii_hits = detect_pii(user_input)
    if pii_hits:
        logger.warning(
            "PII detected in user input — will be redacted from output",
            extra={"user": user, "entities": pii_hits},
        )

    logger.info("Input guardrails passed", extra={"user": user, "role": role})


def redact_input_pii(user_input: str) -> str:
    """
    Return a PII-redacted copy of user_input.

    Use this when you need to store or log the user's raw text (e.g., in Redis
    session memory or audit logs) without persisting sensitive personal data.
    The original string is never modified; a new redacted string is returned.
    """
    return redact_pii(user_input)


# ---------------------------------------------------------------------------
# Output guardrails
# ---------------------------------------------------------------------------

def validate_output(output: str) -> str:
    """
    Sanitize and PII-redact the agent's response before returning it to the client.

    Why sanitize output?
    The LLM may echo back PII from the user's input, fabricate sensitive-looking
    data, or produce content that violates usage policies. These checks run on
    every response regardless of the input's content.

    Steps applied in order:
      1. Strip null bytes and non-printable control characters
         (keep \\n and \\t which are legitimate in formatted output).
      2. Truncate to MAX_OUTPUT_LENGTH to prevent runaway responses.
      3. Redact PII using Presidio (or regex fallback).
      4. Call OpenAI moderation API to flag hate/violence/self-harm categories.

    Args:
        output: Raw string returned by the agent graph.

    Returns:
        The cleaned, redacted string safe to return to the caller.
    """
    if not output:
        return ""

    # Step 1 – strip control characters; keep printable ASCII, \n and \t
    # The regex matches byte ranges for non-printable chars excluding LF(\n) and TAB(\t)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", output)

    # Step 2 – enforce output length to protect against token-exhaustion attacks
    if len(cleaned) > MAX_OUTPUT_LENGTH:
        logger.warning(
            "Output truncated by guardrail",
            extra={"original_length": len(cleaned), "limit": MAX_OUTPUT_LENGTH},
        )
        cleaned = cleaned[:MAX_OUTPUT_LENGTH] + " [truncated]"

    # Step 3 – PII redaction: replace names, emails, SSNs, etc. with placeholders
    # e.g. "alice@company.com" becomes "<EMAIL_ADDRESS>"
    cleaned = redact_pii(cleaned)

    # Step 4 – OpenAI moderation: best-effort check; never blocks on API errors
    _openai_moderate(cleaned)

    return cleaned


def _openai_moderate(text: str) -> None:
    """
    Send text to the OpenAI Moderation API and log if any category is flagged.

    OpenAI's moderation endpoint is free and checks for:
      hate, harassment, violence, self-harm, sexual content, etc.

    Design decisions:
      - Non-blocking: if the API is down or the key is missing, we log a
        warning and carry on. Output is still returned to the caller.
      - We truncate to 2 000 chars because that is the API's character limit.
      - We only import openai inside this function so the rest of the module
        works without it.

    Args:
        text: The string to check (already PII-redacted at this point).
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not text.strip():
        return
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.moderations.create(input=text[:2000])  # API limit
        result = response.results[0]
        if result.flagged:
            categories = [
                cat for cat, flagged in result.categories.__dict__.items() if flagged
            ]
            logger.warning(
                "OpenAI moderation flagged output",
                extra={"categories": categories},
            )
    except Exception:
        logger.warning("OpenAI moderation check failed (non-fatal)", exc_info=True)
