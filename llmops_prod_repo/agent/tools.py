import os
import time
from atlassian import Jira
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import pybreaker

from security.rbac import check_permission
from observability.logger import get_logger, trace_agent
from observability.breakers import jira_breaker
from observability.metrics import increment, record_duration

logger = get_logger("agent.tools")

jira_url     = os.getenv("JIRA_URL")
jira_user    = os.getenv("JIRA_USER")
jira_token   = os.getenv("JIRA_TOKEN")
jira_project = os.getenv("JIRA_PROJECT", "MC")

if jira_url and jira_user and jira_token:
    jira = Jira(url=jira_url, username=jira_user, password=jira_token)
else:
    jira = None
    logger.warning("Jira credentials not set — running in mock mode")


def check_jira_health() -> dict:
    """Validate that Jira URL, username, and token are configured and the connection is reachable."""
    missing = [name for name, val in [
        ("JIRA_URL", jira_url),
        ("JIRA_USER", jira_user),
        ("JIRA_TOKEN", jira_token),
    ] if not val]

    if missing:
        return {"healthy": False, "reason": f"Missing credentials: {', '.join(missing)}"}

    try:
        jira.myself()
        return {"healthy": True, "url": jira_url, "user": jira_user}
    except Exception as exc:
        return {"healthy": False, "reason": str(exc)}


@retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _jira_create(summary: str) -> dict:
    return jira_breaker.call(
        lambda: jira.create_issue(fields={
            "project":     {"key": jira_project},
            "summary":     summary,
            "description": "Created by AI agent",
            "issuetype":   {"name": "Task"},
        })
    )


@retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _jira_fetch() -> list[str]:
    result = jira_breaker.call(
        lambda: jira.jql("project = TEST ORDER BY created DESC", limit=5)
    )
    return [
        f"{i['key']}: {i['fields']['summary']}"
        for i in result.get("issues", [])
    ]


@trace_agent("tools")
def tool_agent(state):
    user = state["user"]
    plan = state["plan"]
    start = time.perf_counter()

    try:
        if "create" in plan:
            check_permission(user, "create")
            if jira:
                issue = _jira_create(state["input"])
                result = f"Ticket {issue['key']} created"
            else:
                result = "Ticket created (mock)"
            increment("tool.create.success")
        else:
            check_permission(user, "read")
            if jira:
                tickets = _jira_fetch()
                result = f"Recent tickets: {', '.join(tickets)}"
            else:
                result = "Ticket viewed (mock)"
            increment("tool.read.success")

        record_duration("tool.latency_ms", (time.perf_counter() - start) * 1000)
        return {"tool_result": result}

    except PermissionError:
        increment("tool.permission_denied")
        raise
    except pybreaker.CircuitBreakerError as exc:
        increment("tool.circuit_open")
        logger.error("Jira circuit breaker is open", exc_info=True)
        raise RuntimeError("Jira service temporarily unavailable.") from exc
    except Exception as exc:
        increment("tool.error")
        logger.error("Tool agent failed", exc_info=True)
        raise
