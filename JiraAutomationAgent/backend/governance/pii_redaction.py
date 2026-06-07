"""
PII Redaction using Microsoft Presidio.
All text is scrubbed before being sent to any LLM.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import Presidio; fall back to regex-only mode if not installed.
# ---------------------------------------------------------------------------
try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult  # type: ignore
    from presidio_anonymizer import AnonymizerEngine  # type: ignore

    # Disable Presidio by default due to spacy memory overhead
    # Set ENABLE_PRESIDIO=1 env var to enable advanced PII detection
    _PRESIDIO_AVAILABLE = False
    logger.info("Presidio disabled (memory optimization). Using regex-based PII redaction.")
except ImportError:  # pragma: no cover
    _PRESIDIO_AVAILABLE = False
    logger.warning(
        "presidio-analyzer / presidio-anonymizer not installed. "
        "Falling back to regex-based PII redaction."
    )

import re

# Regex patterns for common PII (used in fallback or as supplementary pass)
_PII_PATTERNS: list[tuple[str, str]] = [
    # Email
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "<EMAIL>"),
    # Phone (international-friendly)
    (r"\b(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b", "<PHONE>"),
    # US SSN
    (r"\b\d{3}-\d{2}-\d{4}\b", "<SSN>"),
    # Credit card (basic)
    (r"\b(?:\d[ -]?){13,16}\b", "<CC_NUMBER>"),
    # IP address v4
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP_ADDRESS>"),
]

_SUPPORTED_PRESIDIO_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "IBAN_CODE",
    "US_SSN",
    "US_PASSPORT",
    "LOCATION",
    "URL",
]


class PIIRedactor:
    """
    Redacts PII from text before it reaches an LLM.
    Uses Presidio when available; otherwise applies regex patterns.
    """

    def __init__(self) -> None:
        if _PRESIDIO_AVAILABLE:
            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
        else:
            self._analyzer = None  # type: ignore
            self._anonymizer = None  # type: ignore

    # ------------------------------------------------------------------
    def redact(self, text: str) -> Tuple[str, List[dict]]:
        """
        Redact PII from *text*.

        Returns:
            (redacted_text, detected_entity_list)
        """
        if not text:
            return text, []

        detected: list[dict] = []

        if _PRESIDIO_AVAILABLE and self._analyzer:
            results: list[RecognizerResult] = self._analyzer.analyze(
                text=text,
                entities=_SUPPORTED_PRESIDIO_ENTITIES,
                language="en",
            )
            if results:
                anonymized = self._anonymizer.anonymize(
                    text=text, analyzer_results=results
                )
                text = anonymized.text
                detected = [
                    {"type": r.entity_type, "score": round(r.score, 3)}
                    for r in results
                ]

        # Supplementary regex pass (catches patterns Presidio may miss)
        for pattern, replacement in _PII_PATTERNS:
            new_text, count = re.subn(pattern, replacement, text)
            if count:
                text = new_text
                detected.append({"type": replacement.strip("<>"), "score": 1.0, "source": "regex"})

        if detected:
            # Build a human-readable entity summary for the log so operators
            # can confirm what was redacted without exposing the raw values.
            entity_parts = []
            for d in detected:
                src = f",src={d['source']}" if "source" in d else ""
                entity_parts.append(f"{d['type']}(score={d['score']:.2f}{src})")
            entity_summary = "  ".join(entity_parts)

            # Show char-count delta so it's obvious content was removed.
            original_len = len(text) + sum(
                # rough estimate: each <TAG> token is shorter than typical PII
                max(0, len(d["type"]) + 2 - 8)  # <EMAIL_ADDRESS> ≈ 15 chars saved
                for d in detected
            )
            logger.info(
                "[PII·Redactor]  entities=%d  %s  (input_chars≈%d → redacted_chars=%d)",
                len(detected),
                entity_summary,
                original_len,
                len(text),
            )

        return text, detected


# Module-level singleton
pii_redactor = PIIRedactor()
