import logging
import json
from typing import Any, Dict, List, Optional
from anthropic import Anthropic

from app.config import settings
from app.models import SeverityLevel

logger = logging.getLogger(__name__)


class IncidentClassificationAgent:
    """Agent for classifying incident severity and impact."""

    CLASSIFICATION_RULES = {
        "P1_CRITICAL": {
            "keywords": [
                "service down",
                "database down",
                "payment failure",
                "authentication failure",
                "customer visible outage",
                "multiple services affected",
            ],
            "threshold_confidence": 0.95,
            "examples": [
                "Complete service outage",
                "Authentication system down",
                "Payment processing failure",
                "Database completely unavailable",
            ],
        },
        "P2_HIGH": {
            "keywords": [
                "high error rate",
                "elevated latency",
                "api failures",
                "kafka lag",
                "partial service degradation",
                "single service critical error",
            ],
            "threshold_confidence": 0.85,
            "examples": [
                "Error rate > 5%",
                "Latency > 1 second",
                "Single critical service down",
                "API returning errors",
            ],
        },
        "P3_MEDIUM": {
            "keywords": [
                "warning threshold breach",
                "memory growth",
                "retry storm",
                "slow queries",
                "minor threshold breach",
            ],
            "threshold_confidence": 0.70,
            "examples": [
                "Memory leak detected",
                "CPU usage > 80%",
                "Retry storms",
                "Warning logs spike",
            ],
        },
        "P4_LOW": {
            "keywords": [
                "informational alert",
                "minor threshold breach",
                "debug logs",
            ],
            "threshold_confidence": 0.50,
            "examples": [
                "Minor metric fluctuation",
                "Informational logs",
                "Non-critical alerts",
            ],
        },
    }

    def __init__(self):
        self.client = Anthropic()
        self.model = settings.llm_model

    def _rule_based_classification(
        self,
        title: str,
        description: str,
        affected_services: List[str],
        error_rate: Optional[float] = None,
        latency: Optional[float] = None,
        log_count: Optional[int] = None,
    ) -> tuple[SeverityLevel, float]:
        """Rule-based classification."""
        text = f"{title} {description}".lower()

        # Check P1
        for keyword in self.CLASSIFICATION_RULES["P1_CRITICAL"]["keywords"]:
            if keyword.lower() in text:
                return SeverityLevel.P1, 0.95

        # Check P2
        for keyword in self.CLASSIFICATION_RULES["P2_HIGH"]["keywords"]:
            if keyword.lower() in text:
                if error_rate and error_rate > 0.05:
                    return SeverityLevel.P2, 0.90
                if latency and latency > 1000:
                    return SeverityLevel.P2, 0.90
                return SeverityLevel.P2, 0.85

        # Check P3
        for keyword in self.CLASSIFICATION_RULES["P3_MEDIUM"]["keywords"]:
            if keyword.lower() in text:
                return SeverityLevel.P3, 0.75

        # Check number of affected services
        if len(affected_services) >= 3:
            return SeverityLevel.P2, 0.80

        return SeverityLevel.P4, 0.60

    async def classify_incident(
        self,
        title: str,
        description: str,
        affected_services: List[str],
        affected_components: List[str],
        error_rate: Optional[float] = None,
        latency: Optional[float] = None,
        customer_impact: int = 0,
        evidence_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify incident using both rules and LLM."""
        try:
            # Rule-based classification
            rule_severity, rule_confidence = self._rule_based_classification(
                title, description, affected_services, error_rate, latency
            )

            # LLM-based classification
            prompt = f"""Classify the severity of this incident.

**Incident Title**: {title}
**Description**: {description}
**Affected Services**: {', '.join(affected_services)}
**Affected Components**: {', '.join(affected_components)}
**Customer Impact**: {customer_impact} customers
**Error Rate**: {error_rate or 'N/A'}
**Latency**: {latency or 'N/A'}ms

{f"**Evidence**: {evidence_summary}" if evidence_summary else ""}

Classify as P1 (Critical), P2 (High), P3 (Medium), or P4 (Low) based on:
- Severity of impact
- Number of affected services/customers
- Business criticality
- Recovery difficulty

Format as JSON:
{{
    "severity_level": "P1_CRITICAL",
    "confidence_score": 0.95,
    "impact_assessment": "...",
    "business_impact": "...",
    "escalation_recommended": true,
    "reasoning": "..."
}}
"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            response_text = response.content[0].text

            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    classification = json.loads(response_text[json_start:json_end])
                else:
                    classification = {
                        "severity_level": rule_severity.value,
                        "confidence_score": rule_confidence,
                    }
            except json.JSONDecodeError:
                classification = {
                    "severity_level": rule_severity.value,
                    "confidence_score": rule_confidence,
                }

            # Map severity string to enum
            severity_map = {
                "P1_CRITICAL": SeverityLevel.P1,
                "P2_HIGH": SeverityLevel.P2,
                "P3_MEDIUM": SeverityLevel.P3,
                "P4_LOW": SeverityLevel.P4,
            }

            llm_severity_str = classification.get("severity_level", "P4_LOW")
            llm_severity = severity_map.get(llm_severity_str, SeverityLevel.P4)
            llm_confidence = classification.get("confidence_score", 0.5)

            # Combine rule and LLM results (weighted average)
            final_confidence = 0.6 * rule_confidence + 0.4 * llm_confidence

            # Use LLM severity if confidence is high
            final_severity = llm_severity if llm_confidence > 0.7 else rule_severity

            logger.info(
                f"Classified incident: {final_severity.value} (confidence: {final_confidence:.2f})"
            )

            return {
                "severity": final_severity,
                "confidence_score": final_confidence,
                "rule_based_severity": rule_severity,
                "rule_confidence": rule_confidence,
                "llm_severity": llm_severity,
                "llm_confidence": llm_confidence,
                "impact_assessment": classification.get("impact_assessment", ""),
                "business_impact": classification.get("business_impact", ""),
                "escalation_recommended": classification.get("escalation_recommended", final_severity == SeverityLevel.P1),
                "reasoning": classification.get("reasoning", ""),
            }

        except Exception as e:
            logger.error(f"Failed to classify incident: {e}")
            rule_severity, rule_confidence = self._rule_based_classification(
                title, description, affected_services, error_rate, latency
            )

            return {
                "severity": rule_severity,
                "confidence_score": rule_confidence,
                "rule_based_severity": rule_severity,
                "rule_confidence": rule_confidence,
                "error": str(e),
            }

    async def assign_severity_p1_to_p4(
        self,
        incident_data: Dict[str, Any],
    ) -> SeverityLevel:
        """Direct assignment of severity P1-P4."""
        try:
            classification = await self.classify_incident(
                title=incident_data.get("title", ""),
                description=incident_data.get("description", ""),
                affected_services=incident_data.get("affected_services", []),
                affected_components=incident_data.get("affected_components", []),
                error_rate=incident_data.get("error_rate"),
                latency=incident_data.get("latency"),
                customer_impact=incident_data.get("customer_impact", 0),
                evidence_summary=incident_data.get("evidence_summary"),
            )

            return classification["severity"]

        except Exception as e:
            logger.error(f"Failed to assign severity: {e}")
            return SeverityLevel.P4
