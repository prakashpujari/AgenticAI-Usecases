#!/usr/bin/env python
"""Debug script to test backend API without going through the frontend."""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from backend.config import settings
from backend.graph.workflow import workflow
from backend.graph.state import JiraAgentState
import uuid


async def test_workflow():
    """Test the workflow directly."""
    print("=" * 80)
    print("BACKEND WORKFLOW DEBUG TEST")
    print("=" * 80)

    print(f"\n[CONFIG] Configuration:")
    print(f"  LLM Provider: {settings.llm_provider}")
    print(f"  Model: {settings.groq_model if settings.llm_provider == 'groq' else settings.openai_model}")
    print(f"  Pinecone Index: {settings.pinecone_index_name}")
    print(f"  Jira URL: {settings.jira_base_url}")
    print(f"  LangSmith Enabled: {settings.langchain_tracing_v2}")

    print(f"\n[TEST] Testing workflow with simple input...")

    # Create initial state
    initial_state = JiraAgentState(
        raw_input="Test database connection timeout issue",
        jira_key=None,
        mode="create",
        allowed_projects=["MC"],
        allowed_components=[],
        user_role="engineer",
        user_id="debug-test",
        normalized_input="",
        redacted_input="",
        pii_detected=[],
        rbac_violations=[],
        rbac_context="",
        dedupe_matches=[],
        retrieved_context=[],
        formatted_context="",
        ticket_drafts=[],
        review_result={},
        explainer_output={},
        validation_errors=[],
        is_valid=False,
        create_in_jira=False,
        created_issues=[],
        iteration_count=0,
        max_iterations=2,
        error=None,
        trace_id=str(uuid.uuid4()),
    )

    print(f"  Trace ID: {initial_state['trace_id']}")
    print(f"  Input: {initial_state['raw_input']}")

    try:
        print("\n[WAIT] Running workflow (this may take 30-60 seconds)...")
        final_state = await workflow.ainvoke(initial_state)

        print("\n[OK] Workflow completed successfully!")

        print(f"\n[RESULTS]:")
        print(f"  Tickets generated: {len(final_state.get('ticket_drafts', []))}")
        print(f"  Dedupe matches: {len(final_state.get('dedupe_matches', []))}")
        print(f"  Has review: {bool(final_state.get('review_result'))}")
        print(f"  Has explainer: {bool(final_state.get('explainer_output'))}")
        print(f"  Errors: {final_state.get('error')}")

        if final_state.get("ticket_drafts"):
            print(f"\n[TICKET] First ticket:")
            ticket = final_state["ticket_drafts"][0]
            print(f"  Type: {ticket.get('issue_type')}")
            print(f"  Title: {ticket.get('title')}")
            print(f"  Priority: {ticket.get('priority')}")

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}")
        print(f"        {str(e)}")
        print(f"\n[TRACE]Full traceback:")
        import traceback
        traceback.print_exc()

        # Additional debugging info
        print(f"\n[CHECK] Environment check:")
        try:
            import openai
            print(f"  OK OpenAI library installed")
        except ImportError:
            print(f"  MISSING OpenAI library NOT installed")

        try:
            import groq
            print(f"  OK Groq library installed")
        except ImportError:
            print(f"  MISSING Groq library NOT installed")

        try:
            import pinecone
            print(f"  OK Pinecone library installed")
        except ImportError:
            print(f"  MISSING Pinecone library NOT installed")


if __name__ == "__main__":
    asyncio.run(test_workflow())
