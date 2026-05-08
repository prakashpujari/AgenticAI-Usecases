"""
Role-Based Access Control (RBAC) for the Jira Automation Agent.
Enforces that agents only reference projects / components the caller is entitled to.
"""
from __future__ import annotations

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Pattern that matches Jira issue keys such as PROJ-123
_JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+)-\d+\b")


class RBACFilter:
    """Filter and contextualise inputs according to RBAC rules."""

    # ------------------------------------------------------------------
    def filter_input(
        self,
        text: str,
        allowed_projects: List[str],
        allowed_components: List[str],
    ) -> Tuple[str, List[str]]:
        """
        Scan *text* for references to Jira projects outside *allowed_projects*.
        Redacts disallowed keys and returns (filtered_text, violation_list).
        """
        violations: list[str] = []
        allowed_set = set(allowed_projects)

        def _replace(match: re.Match) -> str:
            project_key = match.group(1)
            if project_key not in allowed_set:
                violations.append(
                    f"Reference to non-allowed project key: {project_key}"
                )
                return "[REDACTED_KEY]"
            return match.group(0)

        filtered = _JIRA_KEY_RE.sub(_replace, text)

        if violations:
            logger.warning("RBAC violations in input: %s", violations)

        return filtered, violations

    # ------------------------------------------------------------------
    def build_rbac_context(
        self,
        allowed_projects: List[str],
        allowed_components: List[str],
        user_role: str,
    ) -> str:
        """
        Return an RBAC context block to be injected at the top of every
        agent prompt so models stay within authorised boundaries.
        """
        projects_str = ", ".join(allowed_projects) if allowed_projects else "none"
        components_str = ", ".join(allowed_components) if allowed_components else "none"
        return (
            "=== RBAC CONSTRAINTS (MANDATORY) ===\n"
            f"User role       : {user_role}\n"
            f"Allowed projects: {projects_str}\n"
            f"Allowed components: {components_str}\n"
            "Rules:\n"
            "  • Only create / reference issues in the allowed projects above.\n"
            "  • Never fabricate Jira keys, issue numbers, or system names.\n"
            "  • Never reference data, systems, or projects outside this context.\n"
            "=== END RBAC CONSTRAINTS ===\n"
        )


# Module-level singleton
rbac_filter = RBACFilter()
