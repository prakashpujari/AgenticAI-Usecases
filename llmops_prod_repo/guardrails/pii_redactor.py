"""
PII (Personally Identifiable Information) detection and redaction layer.

What is PII and why redact it?
-------------------------------
PII is any data that could identify a specific individual: names, email
addresses, phone numbers, social-security numbers, credit card numbers, etc.
Regulations such as GDPR (Europe), CCPA (California), and HIPAA (healthcare)
require that PII is not stored or transmitted without explicit consent.

This module sits between the LLM's raw output and the API response: it scans
the text and replaces any detected PII with safe placeholder tokens, e.g.:
    "Call Alice at 555-123-4567" → "Call <PERSON> at <PHONE_NUMBER>"

Design: two-layer architecture
--------------------------------
Primary engine — Microsoft Presidio:
  Presidio is an open-source NLP engine that uses a fine-tuned spaCy model to
  detect PII with high accuracy, including entity types like PERSON that regex
  alone cannot reliably detect.
  Install: pip install presidio-analyzer presidio-anonymizer
  Model:   python -m spacy download en_core_web_lg

Fallback — hand-written regex patterns:
  Used automatically when Presidio is not installed or fails. Covers the most
  common structured PII types (email, phone, SSN, credit card, IP address).

Environment variable:
  PII_REDACTION_ENABLED=true|false  (default: true)
  Set to false in development environments where you want to see raw output.
"""

import os
import re
from observability.logger import get_logger

logger = get_logger("guardrails.pii")

_REDACTION_ENABLED = os.getenv("PII_REDACTION_ENABLED", "true").lower() == "true"

# ── Presidio bootstrap ─────────────────────────────────────────────────────────
_presidio_available = False
_analyzer = None
_anonymizer = None

if _REDACTION_ENABLED:
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
        _presidio_available = True
        logger.info("Presidio PII engine initialised")
    except ImportError:
        logger.warning("presidio-analyzer/presidio-anonymizer not installed — using regex fallback")

# ── Presidio entity list ───────────────────────────────────────────────────────
_PRESIDIO_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "US_SSN",
    "US_PASSPORT",
    "LOCATION",
    "DATE_TIME",
    "NRP",
]

# ── Regex fallback patterns (pattern, replacement_tag) ────────────────────────
_REGEX_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Email
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "<EMAIL_ADDRESS>"),
    # US phone (various formats)
    (re.compile(r"\b(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b"), "<PHONE_NUMBER>"),
    # US SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "<US_SSN>"),
    # Major credit card numbers (Visa, MC, Amex, Discover)
    (
        re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|"
            r"3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|"
            r"6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        "<CREDIT_CARD>",
    ),
    # IPv4 address
    (re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"), "<IP_ADDRESS>"),
    # US passport (letter + 8 digits)
    (re.compile(r"\b[A-Z]{1,2}[0-9]{6,9}\b"), "<US_PASSPORT>"),
]


# ---------------------------------------------------------------------------
# Public API — call these functions from other modules
# ---------------------------------------------------------------------------

def redact_pii(text: str) -> str:
    """
    Detect and replace PII in *text* with placeholder tokens.

    Routing logic:
      - If redaction is disabled (env var)  → return text unchanged.
      - If Presidio is available            → use Presidio (higher accuracy).
      - Otherwise                           → use regex fallback.

    This function is safe to call multiple times on the same text; applying
    it twice will not corrupt already-redacted placeholders.

    Args:
        text: Any string that may contain PII.

    Returns:
        A new string with PII replaced, or the original string if redaction
        is disabled or the text is empty.
    """
    if not text or not _REDACTION_ENABLED:
        return text

    if _presidio_available:
        return _presidio_redact(text)
    return _regex_redact(text)


def detect_pii(text: str) -> list[dict]:
    """
    Scan text and return detected PII entities WITHOUT modifying the text.

    Used for compliance audit logging — we record what types of PII
    the user sent so security teams can monitor trends over time.

    Only available when Presidio is installed; returns an empty list otherwise.

    Returns:
        List of dicts: [{"entity_type": "EMAIL_ADDRESS", "score": 0.85}, ...]
        Confidence score is in 0–1 range (Presidio uses NLP confidence).
    """
    if not text or not _presidio_available:
        return []
    try:
        results = _analyzer.analyze(text=text, entities=_PRESIDIO_ENTITIES, language="en")
        return [
            {"entity_type": r.entity_type, "score": round(r.score, 3)}
            for r in results
        ]
    except Exception:
        logger.warning("PII detection scan failed", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Internal helpers — not part of the public API (prefixed with _)
# ---------------------------------------------------------------------------

def _presidio_redact(text: str) -> str:
    """
    Use Presidio's two-step pipeline to redact PII:
      Step 1 (Analyzer)   — find PII spans, return RecognizerResult objects.
      Step 2 (Anonymizer) — replace each span with a token like <EMAIL_ADDRESS>.

    Falls back to regex redaction if Presidio raises any exception so the
    output guardrail never completely fails.
    """
    try:
        from presidio_anonymizer.entities import OperatorConfig

        # Step 1: find all PII entity spans in the text
        results = _analyzer.analyze(text=text, entities=_PRESIDIO_ENTITIES, language="en")
        if not results:
            return text

        # Build an operator config for each entity type:
        # OperatorConfig("replace", {"new_value": "<TOKEN>"}) means
        # "replace this span with the given token string"
        operators = {
            entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
            for entity in _PRESIDIO_ENTITIES
        }
        # Step 2: apply replacements and return the cleaned text
        anonymized = _anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        redacted = anonymized.text
        logger.info(
            "Presidio PII redacted",
            extra={"entities_found": len(results)},
        )
        return redacted
    except Exception:
        # Presidio failed for an unexpected reason — degrade to regex
        logger.warning("Presidio redaction error — falling back to regex", exc_info=True)
        return _regex_redact(text)


def _regex_redact(text: str) -> str:
    """
    Apply all regex patterns sequentially and return the redacted text.

    Each pattern.sub() call replaces all non-overlapping matches in a single
    pass, which is O(n * m) where n=text length and m=number of patterns.
    We keep a reference to the original to detect whether anything changed
    and log accordingly.
    """
    original = text
    for pattern, replacement in _REGEX_PATTERNS:
        # re.Pattern.sub() replaces every match with the replacement string
        text = pattern.sub(replacement, text)
    if text != original:
        logger.info("Regex PII redacted from text")
    return text
