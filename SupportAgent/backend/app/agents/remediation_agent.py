import logging
import json
import subprocess
from typing import Any, Dict, List, Optional
from anthropic import Anthropic

from app.config import settings
from app.models import SeverityLevel

logger = logging.getLogger(__name__)


class RemediationAgent:
    """Agent for generating and executing remediation playbooks."""

    REMEDIATION_TEMPLATES = {
        "restart_pod": {
            "description": "Restart a Kubernetes pod",
            "parameters": ["pod_name", "namespace"],
            "implementation": "kubectl -n {namespace} delete pod {pod_name}",
        },
        "scale_deployment": {
            "description": "Scale a Kubernetes deployment",
            "parameters": ["deployment_name", "namespace", "replicas"],
            "implementation": "kubectl -n {namespace} scale deployment {deployment_name} --replicas={replicas}",
        },
        "restart_service": {
            "description": "Restart a service",
            "parameters": ["service_name", "command"],
            "implementation": "systemctl restart {service_name}",
        },
        "clear_cache": {
            "description": "Clear application cache",
            "parameters": ["cache_type"],
            "implementation": "redis-cli FLUSHALL",
        },
        "rollback_deployment": {
            "description": "Rollback a deployment",
            "parameters": ["deployment_name", "namespace"],
            "implementation": "kubectl -n {namespace} rollout undo deployment/{deployment_name}",
        },
        "rotate_certificate": {
            "description": "Rotate SSL certificate",
            "parameters": ["cert_name", "domain"],
            "implementation": "Manual certificate rotation required",
        },
        "increase_resource": {
            "description": "Increase resource limits",
            "parameters": ["resource_type", "target_value"],
            "implementation": "Manual resource limit adjustment",
        },
    }

    def __init__(self):
        self.client = Anthropic()
        self.model = settings.llm_model

    async def generate_remediation_playbook(
        self,
        root_cause: str,
        affected_systems: List[str],
        severity: SeverityLevel,
        environment: str,
    ) -> Dict[str, Any]:
        """Generate a remediation playbook using Claude."""
        try:
            prompt = f"""You are an expert SRE. Generate a detailed remediation playbook for the following incident.

**Root Cause**: {root_cause}
**Affected Systems**: {', '.join(affected_systems)}
**Severity**: {severity.value}
**Environment**: {environment}

Available remediation actions:
{json.dumps(list(self.REMEDIATION_TEMPLATES.keys()), indent=2)}

Please provide a step-by-step remediation plan. Format as JSON:
{{
    "actions": [
        {{
            "action_type": "restart_pod",
            "action_name": "Restart API Server",
            "description": "...",
            "parameters": {{"pod_name": "api-server-1", "namespace": "production"}},
            "estimated_duration_seconds": 30,
            "risk_level": "low",
            "rollback_possible": true,
            "prerequisite_checks": ["Check pod logs", "Verify no active requests"],
            "post_action_validation": ["Check pod status", "Verify service health"]
        }}
    ],
    "estimated_total_duration_seconds": 120,
    "risk_assessment": "low|medium|high",
    "requires_approval": true,
    "can_auto_execute": false,
    "success_criteria": ["Metric returns to normal", "Error rate drops below 5%"],
    "rollback_steps": ["...", "..."]
}}
"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
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
                    playbook = json.loads(response_text[json_start:json_end])
                else:
                    playbook = {
                        "actions": [],
                        "estimated_total_duration_seconds": 0,
                        "risk_assessment": "high",
                        "requires_approval": True,
                        "can_auto_execute": False,
                        "success_criteria": [],
                        "rollback_steps": [],
                    }
            except json.JSONDecodeError:
                playbook = {
                    "actions": [],
                    "estimated_total_duration_seconds": 0,
                    "risk_assessment": "high",
                    "requires_approval": True,
                    "can_auto_execute": False,
                    "success_criteria": [],
                    "rollback_steps": [],
                }

            # Add validation
            playbook["is_valid"] = len(playbook.get("actions", [])) > 0

            logger.info(f"Generated remediation playbook with {len(playbook.get('actions', []))} actions")
            return playbook

        except Exception as e:
            logger.error(f"Failed to generate remediation playbook: {e}")
            return {
                "actions": [],
                "estimated_total_duration_seconds": 0,
                "risk_assessment": "high",
                "requires_approval": True,
                "can_auto_execute": False,
                "success_criteria": [],
                "rollback_steps": [],
                "is_valid": False,
                "error": str(e),
            }

    async def execute_remediation(
        self,
        action: Dict[str, Any],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute a remediation action."""
        try:
            action_type = action.get("action_type")
            parameters = action.get("parameters", {})

            if action_type not in self.REMEDIATION_TEMPLATES:
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}",
                }

            template = self.REMEDIATION_TEMPLATES[action_type]
            command = template["implementation"]

            # Format command with parameters
            for key, value in parameters.items():
                command = command.replace(f"{{{key}}}", str(value))

            logger.info(f"Executing remediation: {action_type} - {command}")

            if dry_run:
                return {
                    "success": True,
                    "action_type": action_type,
                    "command": command,
                    "output": "[DRY RUN] Command would execute successfully",
                    "dry_run": True,
                }

            # Execute command (with safety checks)
            if not self._is_safe_command(command):
                return {
                    "success": False,
                    "error": "Command blocked for safety reasons",
                    "action_type": action_type,
                }

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                return {
                    "success": result.returncode == 0,
                    "action_type": action_type,
                    "command": command,
                    "output": result.stdout,
                    "error": result.stderr if result.returncode != 0 else None,
                    "return_code": result.returncode,
                }

            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "action_type": action_type,
                    "error": "Command execution timeout",
                }

        except Exception as e:
            logger.error(f"Failed to execute remediation: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _is_safe_command(self, command: str) -> bool:
        """Check if a command is safe to execute."""
        blocked_patterns = [
            "rm -rf /",
            "dd if=",
            "format",
            ":(){:|:&};:",  # Fork bomb
            "curl | bash",
            "wget -O - | bash",
        ]

        for pattern in blocked_patterns:
            if pattern.lower() in command.lower():
                logger.warning(f"Blocked potentially dangerous command: {command}")
                return False

        return True

    async def validate_remediation_success(
        self,
        incident_id: str,
        success_criteria: List[str],
        environment: str,
    ) -> Dict[str, Any]:
        """Validate if remediation was successful."""
        try:
            validation_prompt = f"""Evaluate whether the following success criteria have been met for incident {incident_id}:

**Success Criteria**:
{json.dumps(success_criteria, indent=2)}

**Environment**: {environment}

Please check each criterion and provide a validation report.
Format as JSON:
{{
    "overall_success": true,
    "validations": [
        {{"criterion": "...", "met": true, "evidence": "..."}},
    ],
    "remediation_effective": true,
    "recommendations": ["..."]
}}
"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": validation_prompt,
                    }
                ],
            )

            response_text = response.content[0].text

            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    validation = json.loads(response_text[json_start:json_end])
                else:
                    validation = {
                        "overall_success": False,
                        "validations": [],
                        "remediation_effective": False,
                        "recommendations": [],
                    }
            except json.JSONDecodeError:
                validation = {
                    "overall_success": False,
                    "validations": [],
                    "remediation_effective": False,
                    "recommendations": [],
                }

            return validation

        except Exception as e:
            logger.error(f"Failed to validate remediation: {e}")
            return {
                "overall_success": False,
                "error": str(e),
            }
