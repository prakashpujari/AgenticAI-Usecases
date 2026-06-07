import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from anthropic import Anthropic

from app.config import settings
from app.connectors.base import LogEntry, MetricData

logger = logging.getLogger(__name__)


class RCAAgent:
    """Root Cause Analysis Agent using Claude."""

    def __init__(self):
        self.client = Anthropic()
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    def _format_evidence(self, evidence: Dict[str, Any]) -> str:
        """Format evidence for LLM analysis."""
        formatted = "## Evidence Summary\n\n"

        if logs := evidence.get("logs", []):
            formatted += f"### Error Logs ({len(logs)} entries)\n"
            for log in logs[:10]:  # Top 10 logs
                formatted += f"- [{log.get('timestamp')}] {log.get('level')}: {log.get('message')}\n"
            formatted += "\n"

        if metrics := evidence.get("metrics", []):
            formatted += f"### Metrics ({len(metrics)} data points)\n"
            for metric in metrics[:10]:
                formatted += f"- {metric.get('metric_name')}: {metric.get('value')} at {metric.get('timestamp')}\n"
            formatted += "\n"

        if services := evidence.get("affected_services", []):
            formatted += f"### Affected Services\n"
            for service in services:
                formatted += f"- {service}\n"
            formatted += "\n"

        if traces := evidence.get("traces", []):
            formatted += f"### Distributed Traces ({len(traces)} entries)\n"
            for trace in traces[:5]:
                formatted += f"- {trace.get('service')}: {trace.get('operation')} ({trace.get('status')})\n"
            formatted += "\n"

        return formatted

    async def analyze_root_cause(
        self,
        incident_title: str,
        incident_description: str,
        evidence: Dict[str, Any],
        similar_incidents: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Analyze root cause using Claude."""
        try:
            formatted_evidence = self._format_evidence(evidence)

            similar_context = ""
            if similar_incidents:
                similar_context = "\n## Similar Past Incidents\n"
                for incident in similar_incidents[:5]:
                    similar_context += f"- **{incident.get('title')}** ({incident.get('date')})\n"
                    similar_context += f"  Root Cause: {incident.get('root_cause')}\n"
                    similar_context += f"  Resolution: {incident.get('resolution')}\n\n"

            prompt = f"""You are an expert SRE and incident commander. Analyze the following incident and determine the root cause.

## Incident Details
**Title**: {incident_title}
**Description**: {incident_description}

{formatted_evidence}

{similar_context}

Based on the evidence provided, please provide:

1. **Root Cause**: The most likely root cause of this incident
2. **Confidence Score**: Your confidence in this analysis (0.0-1.0)
3. **Affected Systems**: List of systems affected by this issue
4. **Contributing Factors**: Other factors that may have contributed
5. **Timeline**: Reconstructed timeline of events
6. **Recommended Fix**: Specific steps to resolve this issue
7. **Prevention Measures**: How to prevent this in the future

Please format your response as JSON with these exact keys:
{{
    "root_cause": "...",
    "confidence_score": 0.85,
    "affected_systems": ["system1", "system2"],
    "contributing_factors": ["factor1", "factor2"],
    "timeline": [
        {{"time": "...", "event": "..."}},
    ],
    "recommended_fix": "...",
    "implementation_steps": ["step1", "step2"],
    "prevention_measures": ["measure1", "measure2"],
    "key_insights": ["insight1", "insight2"]
}}
"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            response_text = response.content[0].text

            # Parse JSON from response
            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    rca_json = json.loads(response_text[json_start:json_end])
                else:
                    rca_json = {
                        "root_cause": response_text,
                        "confidence_score": 0.5,
                        "affected_systems": [],
                        "contributing_factors": [],
                        "timeline": [],
                        "recommended_fix": "Manual investigation required",
                        "implementation_steps": [],
                        "prevention_measures": [],
                    }
            except json.JSONDecodeError:
                rca_json = {
                    "root_cause": response_text,
                    "confidence_score": 0.5,
                    "affected_systems": [],
                    "contributing_factors": [],
                    "timeline": [],
                    "recommended_fix": "Manual investigation required",
                    "implementation_steps": [],
                    "prevention_measures": [],
                }

            logger.info(f"RCA completed: {rca_json.get('root_cause', 'Unknown')}")
            return rca_json

        except Exception as e:
            logger.error(f"Failed to analyze root cause: {e}")
            return {
                "root_cause": f"Failed to analyze: {str(e)}",
                "confidence_score": 0.0,
                "affected_systems": [],
                "contributing_factors": [],
                "timeline": [],
                "recommended_fix": "Manual analysis required",
                "implementation_steps": [],
                "prevention_measures": [],
                "error": str(e),
            }

    async def get_kb_recommendations(
        self,
        root_cause: str,
        affected_systems: List[str],
        kb_articles: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Get KB article recommendations based on RCA."""
        try:
            prompt = f"""Based on the following root cause analysis, recommend relevant knowledge base articles and resolution steps.

**Root Cause**: {root_cause}
**Affected Systems**: {', '.join(affected_systems)}

Available KB Articles:
{json.dumps(kb_articles or [], indent=2)[:2000]}

Please recommend the 3 most relevant articles and why they apply to this incident.
Format as JSON:
[
    {{"article_id": "...", "title": "...", "relevance": 0.95, "reason": "..."}},
]
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
                json_start = response_text.find("[")
                json_end = response_text.rfind("]") + 1
                if json_start != -1 and json_end > json_start:
                    recommendations = json.loads(response_text[json_start:json_end])
                else:
                    recommendations = []
            except json.JSONDecodeError:
                recommendations = []

            return recommendations

        except Exception as e:
            logger.error(f"Failed to get KB recommendations: {e}")
            return []
