"""
End-to-end test suite for the LLMOps Agent API.

Covers:
  1. Jira health check          — credentials loaded from .env
  2. RBAC permissions           — PRODUCT_OWNER can create, DEVELOPER cannot
  3. Guardrail input validation — PII / policy violations rejected
  4. Planner unit               — mocked OpenAI, correct plan returned
  5. Tool agent (mock mode)     — no real Jira call, verifies mock path
  6. Full agent graph (mock)    — run_agent returns a non-empty string
  7. FastAPI /run endpoint      — HTTP 200 with output field
  8. FastAPI /health endpoint   — liveness check
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

load_dotenv(override=True)

# ── 1. Jira health check ─────────────────────────────────────────────────────

def test_jira_health():
    from agent.tools import check_jira_health
    result = check_jira_health()
    assert result["healthy"] is True, f"Jira health failed: {result.get('reason')}"
    assert "url" in result
    assert "user" in result


# ── 2. RBAC permissions ───────────────────────────────────────────────────────

def test_rbac_product_owner_can_create():
    from security.rbac import check_permission
    # Should not raise
    check_permission("alice@company.com", "create")


def test_rbac_developer_cannot_create():
    from security.rbac import USER_ROLES, check_permission
    # Temporarily register a developer user
    USER_ROLES["dev@company.com"] = "DEVELOPER"
    with pytest.raises(PermissionError):
        check_permission("dev@company.com", "create")
    del USER_ROLES["dev@company.com"]


def test_rbac_unknown_user_denied():
    from security.rbac import check_permission
    with pytest.raises(PermissionError):
        check_permission("nobody@company.com", "read")


# ── 3. Guardrail input validation ─────────────────────────────────────────────

def test_guardrail_accepts_valid_input():
    from guardrails.rules import validate_input
    # Should return without raising
    validate_input("Create a ticket for the login bug", "alice@company.com", "PRODUCT_OWNER", "test-session-001")


def test_guardrail_rejects_empty_input():
    from guardrails.rules import validate_input, GuardrailViolation
    with pytest.raises((GuardrailViolation, ValueError)):
        validate_input("", "alice@company.com", "PRODUCT_OWNER", "test-session-001")


# ── 4. Planner unit (mocked OpenAI) ──────────────────────────────────────────

@patch("agent.planner._call_openai", return_value="create_ticket")
def test_planner_create(mock_llm):
    from agent.planner import planner_agent
    state = {"input": "Create a ticket for bug #42", "role": "PRODUCT_OWNER"}
    result = planner_agent(state)
    assert result["plan"] == "create_ticket"


@patch("agent.planner._call_openai", return_value="view_ticket")
def test_planner_view(mock_llm):
    from agent.planner import planner_agent
    state = {"input": "Show me recent tickets", "role": "DEVELOPER"}
    result = planner_agent(state)
    assert result["plan"] == "view_ticket"


# ── 5. Tool agent — mock mode (no Jira creds patched out) ────────────────────

def test_tool_agent_mock_create():
    from agent import tools
    original_jira = tools.jira
    tools.jira = None  # force mock mode
    try:
        state = {
            "user": "alice@company.com",
            "plan": "create_ticket",
            "input": "Fix login bug",
        }
        result = tools.tool_agent(state)
        assert "mock" in result["tool_result"].lower()
    finally:
        tools.jira = original_jira


def test_tool_agent_mock_read():
    from agent import tools
    original_jira = tools.jira
    tools.jira = None
    try:
        state = {
            "user": "alice@company.com",
            "plan": "view_ticket",
            "input": "Show tickets",
        }
        result = tools.tool_agent(state)
        assert "mock" in result["tool_result"].lower()
    finally:
        tools.jira = original_jira


# ── 6. Full agent graph — all external calls mocked ──────────────────────────

@patch("agent.planner._call_openai", return_value="view_ticket")
@patch("agent.response.response_agent", return_value={"output": "Here are your tickets."})
def test_run_agent_end_to_end(mock_response, mock_llm):
    from agent import tools
    original_jira = tools.jira
    tools.jira = None
    try:
        from agent.graph import run_agent
        output = run_agent(
            user_input="Show me recent tickets",
            user="alice@company.com",
            role="PRODUCT_OWNER",
            session_id="test-session-001",
        )
        assert isinstance(output, str)
        assert len(output) > 0
    finally:
        tools.jira = original_jira


# ── 7. FastAPI /run endpoint ──────────────────────────────────────────────────

@patch("agent.planner._call_openai", return_value="view_ticket")
@patch("agent.response.response_agent", return_value={"output": "Mocked response."})
def test_api_run_endpoint(mock_response, mock_llm):
    from fastapi.testclient import TestClient
    from agent import tools
    original_jira = tools.jira
    tools.jira = None
    try:
        from app import app
        client = TestClient(app)
        payload = {
            "input": "Show me recent tickets",
            "user": "alice@company.com",
            "role": "PRODUCT_OWNER",
            "session_id": "test-session-001",
        }
        response = client.post("/run_agent", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "output" in data
        assert len(data["output"]) > 0
    finally:
        tools.jira = original_jira


# ── 8. FastAPI /health endpoint ───────────────────────────────────────────────

def test_api_health_endpoint():
    from fastapi.testclient import TestClient
    from app import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
