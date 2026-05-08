"""
LangGraph multi-agent workflow.

Flow:
  normalize_inputs
    → rbac_filter
    → dedupe
    → retrieve
    → generate
    → review ──(APPROVED or max_iterations)──→ explain → validate → create → END
              └──(CHANGES_REQUIRED)──────────→ refine  ↩
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from .state import JiraAgentState
from ..agents.generator_agent import generator_agent
from ..agents.reviewer_agent import reviewer_agent
from ..agents.refiner_agent import refiner_agent
from ..agents.explainer_agent import explainer_agent
from ..agents.jira_writer_agent import jira_writer_agent
from ..agents.pinecone_memory_agent import pinecone_memory_agent
from ..governance.pii_redaction import pii_redactor
from ..governance.rbac import rbac_filter
from ..governance.guardrails import validate_tickets
from ..rag.retriever import rag_retriever
from ..rag.reranker import reranker
from ..observability.tracer import set_trace_id, get_trace_id, log_layer, log_layer_warn
from ..config import settings as _settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Node implementations
# ═══════════════════════════════════════════════════════════════════════════════


async def normalize_inputs(state: JiraAgentState) -> Dict[str, Any]:
    """Strip PII from raw input and assign a trace ID."""
    raw = state.get("raw_input", "")

    # pii_redactor uses regex (and optionally presidio) to mask emails,
    # phone numbers, SSNs, etc. before any text reaches the LLM.
    redacted, pii_entities = pii_redactor.redact(raw)
    normalized = redacted.strip()

    trace_id = state.get("trace_id") or str(uuid.uuid4())

    # Bind trace_id to this async context so all downstream log_layer calls
    # automatically include it without needing to pass it as an argument.
    set_trace_id(trace_id)

    if pii_entities:
        entity_detail = "  ".join(
            f"{e['type']}(score={e.get('score', 0):.2f})"
            for e in pii_entities
        )
        log_layer("WORKFLOW", "normalize",
                  raw_chars=len(raw),
                  normalized_chars=len(normalized),
                  pii_count=len(pii_entities),
                  redacted_entities=f"[{entity_detail}]")
    else:
        log_layer("WORKFLOW", "normalize",
                  raw_chars=len(raw),
                  normalized_chars=len(normalized),
                  pii_count=0,
                  status="clean")

    logger.info("[normalize_inputs] PII entities: %d | trace_id: %s", len(pii_entities), trace_id)
    return {
        "normalized_input": normalized,   # PII-safe text passed to all downstream nodes
        "redacted_input": redacted,        # stored for audit log
        "pii_detected": pii_entities,      # list of redacted entity types
        "trace_id": trace_id,
    }


async def rbac_filter_node(state: JiraAgentState) -> Dict[str, Any]:
    """Enforce RBAC on normalised input and build context string for agents."""
    set_trace_id(state.get("trace_id", ""))  # re-bind in this node's async context
    text = state.get("normalized_input", "")
    allowed_projects = state.get("allowed_projects", [])
    allowed_components = state.get("allowed_components", [])
    user_role = state.get("user_role", "product_owner")

    # filter_input scrubs references to project keys the caller isn't
    # allowed to access, preventing prompt-injection via forbidden keys.
    filtered_text, violations = rbac_filter.filter_input(text, allowed_projects, allowed_components)
    rbac_ctx = rbac_filter.build_rbac_context(allowed_projects, allowed_components, user_role)

    if violations:
        log_layer_warn("WORKFLOW", "rbac_filter",
                       violations=len(violations),
                       detail=violations)
        logger.warning("[rbac_filter] %d violation(s): %s", len(violations), violations)
    else:
        log_layer("WORKFLOW", "rbac_filter",
                  role=user_role,
                  projects=allowed_projects,
                  violations=0)

    return {
        "normalized_input": filtered_text,  # may differ from input if forbidden keys were removed
        "rbac_violations": violations,
        "rbac_context": rbac_ctx,            # injected verbatim at the top of every LLM prompt
    }


async def dedupe_node(state: JiraAgentState) -> Dict[str, Any]:
    """Check Pinecone + Redis for potential duplicate issues."""
    set_trace_id(state.get("trace_id", ""))
    input_text = state.get("normalized_input", "")

    # Embeds the input and queries Pinecone for semantically similar issues.
    # Results are hard-blocked at create_node — the reviewer only provides
    # advisory feedback, the actual gate is code-level.
    matches = await pinecone_memory_agent.check_duplicates(input_text)
    if matches:
        match_summary = "  ".join(
            f"{m.get('jira_key','?')}(score={m.get('similarity_score',0):.3f})"
            for m in matches[:5]
        )
        log_layer_warn("WORKFLOW", "dedupe",
                       matches=len(matches),
                       threshold=_settings.dedupe_threshold,
                       top=f"[{match_summary}]",
                       action="HARD_BLOCK")
    else:
        log_layer("WORKFLOW", "dedupe", matches=0, status="no_duplicates")
    logger.info("[dedupe] %d potential duplicate(s) found", len(matches))
    return {"dedupe_matches": matches}


async def retrieve_node(state: JiraAgentState) -> Dict[str, Any]:
    """RAG retrieval: Pinecone → Redis cache → LLM reranking."""
    set_trace_id(state.get("trace_id", ""))
    query = state.get("normalized_input", "")

    # Fetch up to 10 candidates from Pinecone (vector similarity);
    # reranker then scores them by relevance and keeps the top 5.
    # The final formatted string is injected into every LLM prompt as
    # "existing similar issues for reference".
    raw_results = await rag_retriever.retrieve(query, top_k=10)
    reranked = await reranker.rerank(query, raw_results, top_k=5)
    formatted = rag_retriever.format_context(reranked)

    if reranked:
        result_summary = "  ".join(
            f"{r.get('jira_key','?')}(score={r.get('similarity_score',0):.3f})"
            for r in reranked[:5]
        )
        log_layer("WORKFLOW", "retrieve",
                  raw_hits=len(raw_results),
                  reranked=len(reranked),
                  top=f"[{result_summary}]")
    else:
        log_layer("WORKFLOW", "retrieve",
                  raw_hits=len(raw_results),
                  reranked=0,
                  status="no_context")

    logger.info("[retrieve] %d result(s) after reranking", len(reranked))
    return {
        "retrieved_context": reranked,     # raw list forwarded to the API response
        "formatted_context": formatted,    # prompt-ready text block
    }


async def generate_node(state: JiraAgentState) -> Dict[str, Any]:
    """Invoke the Generator Agent to produce ticket drafts."""
    set_trace_id(state.get("trace_id", ""))
    tickets = await generator_agent.generate(
        input_text=state.get("normalized_input", ""),
        context=state.get("formatted_context", ""),
        rbac_context=state.get("rbac_context", ""),
    )
    if tickets:
        titles = [
            f"{t.get('title','?')[:45]}({t.get('issue_type','?')}/{t.get('priority','?')})"
            for t in tickets
        ]
        log_layer("WORKFLOW", "generate",
                  drafts=len(tickets),
                  tickets=titles)
    else:
        log_layer_warn("WORKFLOW", "generate", drafts=0, status="generation_failed")
    logger.info("[generate] %d ticket draft(s) produced", len(tickets))
    return {
        "ticket_drafts": tickets,
        "iteration_count": 0,   # reset so the review/refine loop starts fresh
    }


async def review_node(state: JiraAgentState) -> Dict[str, Any]:
    """Invoke the Reviewer Agent to evaluate ticket quality."""
    set_trace_id(state.get("trace_id", ""))
    result = await reviewer_agent.review(
        tickets=state.get("ticket_drafts", []),
        dedupe_matches=state.get("dedupe_matches", []),
        context=state.get("formatted_context", ""),
    )
    new_count = state.get("iteration_count", 0) + 1
    feedback_snippet = result.get("feedback", "")[:120].replace("\n", " ")
    log_layer("WORKFLOW", "review",
              status=result.get("status"),
              iteration=new_count,
              feedback_chars=len(result.get("feedback", "")),
              feedback_preview=f'"{feedback_snippet}"')
    logger.info("[review] Status: %s | Iteration: %d", result.get("status"), new_count)
    return {
        "review_result": result,
        "iteration_count": new_count,
    }


async def refine_node(state: JiraAgentState) -> Dict[str, Any]:
    """Invoke the Refiner Agent to address reviewer feedback."""
    set_trace_id(state.get("trace_id", ""))
    feedback = state.get("review_result", {}).get("feedback", "")
    refined = await refiner_agent.refine(
        tickets=state.get("ticket_drafts", []),
        feedback=feedback,
        rbac_context=state.get("rbac_context", ""),
    )
    log_layer("WORKFLOW", "refine",
              refined=len(refined),
              feedback_preview=f'"{feedback[:80].replace(chr(10), " ")}"')
    logger.info("[refine] %d ticket(s) refined", len(refined))
    # Overwrite ticket_drafts; the graph loops back to review_node next.
    return {"ticket_drafts": refined}


async def explain_node(state: JiraAgentState) -> Dict[str, Any]:
    """Invoke the Explainer Agent to generate PO coaching."""
    set_trace_id(state.get("trace_id", ""))
    explanation = await explainer_agent.explain(tickets=state.get("ticket_drafts", []))
    log_layer("WORKFLOW", "explain",
              tickets=len(state.get("ticket_drafts", [])),
              principles=len(explanation.get("principles", [])),
              applied=len(explanation.get("applied_to_this_ticket", [])))
    logger.info("[explain] Coaching output generated")
    return {"explainer_output": explanation}


async def validate_node(state: JiraAgentState) -> Dict[str, Any]:
    """Run guardrail validation on final ticket drafts."""
    set_trace_id(state.get("trace_id", ""))
    violations = validate_tickets(state.get("ticket_drafts", []))
    is_valid = len(violations) == 0
    if not is_valid:
        log_layer_warn("WORKFLOW", "validate",
                       tickets=len(state.get("ticket_drafts", [])),
                       violations=len(violations),
                       detail=violations[:5])
        logger.warning("[validate] %d guardrail violation(s): %s", len(violations), violations[:3])
    else:
        log_layer("WORKFLOW", "validate",
                  tickets=len(state.get("ticket_drafts", [])),
                  violations=0,
                  passed=True)
    return {
        "validation_errors": violations,
        "is_valid": is_valid,  # consumed by create_node to gate Jira writes
    }


async def create_node(state: JiraAgentState) -> Dict[str, Any]:
    """Create Jira issues (if valid and create_in_jira=True) and upsert to Pinecone memory."""
    set_trace_id(state.get("trace_id", ""))
    is_valid = state.get("is_valid", False)
    tickets = state.get("ticket_drafts", [])
    dedupe_matches = state.get("dedupe_matches", [])
    create_in_jira = state.get("create_in_jira", False)

    # ── Hard duplicate block ──────────────────────────────────────────────
    # When dedupe_node found matches above the similarity threshold, block
    # creation unconditionally — regardless of create_in_jira or LLM review.
    # This prevents the soft LLM reviewer from accidentally approving duplicates.
    if dedupe_matches:
        top = dedupe_matches[0]
        top_detail = (
            f"{top.get('jira_key', '?')} "
            f"(score={top.get('similarity_score', 0):.3f}, "
            f"title=\"{top.get('title', '')[:60]}\")"
        )
        all_keys = [m.get('jira_key', '?') for m in dedupe_matches]
        log_layer_warn("WORKFLOW", "create",
                       status="DUPLICATE_BLOCKED",
                       top_match=top_detail,
                       total_matches=len(dedupe_matches),
                       existing_keys=all_keys)
        logger.warning("[create] BLOCKED — %d duplicate(s) found, top: %s", len(dedupe_matches), top_detail)
        return {
            "created_issues": [{
                "status": "DUPLICATE_BLOCKED",
                "error": (
                    f"Creation blocked — {len(dedupe_matches)} similar ticket(s) already exist "
                    f"in the knowledge base. Top match: {top_detail}"
                ),
            }]
        }

    # Guard: never write a ticket that failed schema/guardrail validation.
    if not is_valid:
        errors = state.get("validation_errors", [])
        log_layer_warn("WORKFLOW", "create",
                       status="blocked",
                       reason="guardrail_violations",
                       errors=errors[:3])
        logger.warning("[create] Skipped due to validation errors: %s", errors[:2])
        return {
            "created_issues": [
                {"error": f"Validation failed: {'; '.join(errors[:3])}"}
            ]
        }

    if not create_in_jira:
        # Dry-run: upsert approved drafts with synthetic keys so the Pinecone
        # knowledge base is populated for future RAG lookups and dedupe checks.
        trace_id = state.get("trace_id", "draft")[:8]
        draft_created = [
            {"jira_key": f"DRAFT-{trace_id}-{i + 1}", "title": t.get("title", "")}
            for i, t in enumerate(tickets)
        ]
        await pinecone_memory_agent.upsert_issues(draft_created, tickets)
        log_layer("WORKFLOW", "create",
                  status="skipped",
                  reason="create_in_jira=False",
                  pinecone_upserted=len(draft_created))
        logger.info("[create] Dry-run — upserted %d draft(s) to Pinecone", len(draft_created))
        return {"created_issues": []}

    # Write to Jira, then immediately upsert the created issues into Pinecone
    # so future requests can detect them as potential duplicates.
    created = await jira_writer_agent.write(tickets)
    await pinecone_memory_agent.upsert_issues(created, tickets)

    created_keys = [i.get("jira_key") for i in created if i.get("jira_key")]
    failed_titles = [i.get("title", "?") for i in created if not i.get("jira_key")]
    log_layer("WORKFLOW", "create",
              created=len(created_keys),
              keys=created_keys,
              failed=len(failed_titles))
    logger.info("[create] %d issue(s) created in Jira", len(created))
    return {"created_issues": created}


# ═══════════════════════════════════════════════════════════════════════════════
# Conditional edge routers
# ═══════════════════════════════════════════════════════════════════════════════


def dedupe_router(state: JiraAgentState) -> str:
    """
    Route after the dedupe node:
      - "create"   if duplicates were found  → hard-block at create_node
                   (skips generate/review/explain/validate, saving LLM calls)
      - "retrieve" if no duplicates found   → normal generation pipeline
    """
    if state.get("dedupe_matches"):
        logger.info("[router] Duplicates found → skipping to create (hard block)")
        return "create"
    return "retrieve"


def review_router(state: JiraAgentState) -> str:
    """
    Route after the review node:
      - "explain"  if APPROVED or max iterations exhausted
      - "refine"   if CHANGES_REQUIRED and iterations remain
    """
    status = state.get("review_result", {}).get("status", "CHANGES_REQUIRED")
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 2)

    if status == "APPROVED":
        logger.info("[router] APPROVED → explain")
        return "explain"

    # Safety valve: if the LLM keeps requesting changes but we've hit the
    # iteration cap, force the pipeline forward rather than looping forever.
    if iteration_count >= max_iterations:
        logger.info("[router] Max iterations (%d) reached → forcing explain", max_iterations)
        return "explain"

    logger.info("[router] CHANGES_REQUIRED (iter %d/%d) → refine", iteration_count, max_iterations)
    return "refine"


# ═══════════════════════════════════════════════════════════════════════════════
# Graph construction
# ═══════════════════════════════════════════════════════════════════════════════


def build_workflow() -> StateGraph:
    graph = StateGraph(JiraAgentState)

    # ── Register all 10 nodes ─────────────────────────────────────────────
    graph.add_node("normalize_inputs", normalize_inputs)  # PII redaction + trace ID
    graph.add_node("rbac_filter", rbac_filter_node)        # project/role enforcement
    graph.add_node("dedupe", dedupe_node)                  # Pinecone similarity check
    graph.add_node("retrieve", retrieve_node)              # RAG context retrieval
    graph.add_node("generate", generate_node)              # LLM ticket draft generation
    graph.add_node("review", review_node)                  # LLM quality review
    graph.add_node("refine", refine_node)                  # LLM feedback-driven refinement
    graph.add_node("explain", explain_node)                # PO coaching explanation
    graph.add_node("validate", validate_node)              # schema + guardrail checks
    graph.add_node("create", create_node)                  # Jira write + Pinecone upsert

    # ── Entry point ───────────────────────────────────────────────────────
    graph.set_entry_point("normalize_inputs")

    # ── Linear pre-processing pipeline ───────────────────────────────────
    # Each step enriches the state before the LLM nodes run.
    graph.add_edge("normalize_inputs", "rbac_filter")
    graph.add_edge("rbac_filter", "dedupe")

    # ── Duplicate gate ────────────────────────────────────────────────────
    # If dedupe found matches, jump directly to create (which hard-blocks).
    # This avoids wasting LLM calls generating a ticket we will refuse anyway.
    graph.add_conditional_edges(
        "dedupe",
        dedupe_router,
        {"retrieve": "retrieve", "create": "create"},
    )
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "review")

    # ── Conditional review branch ─────────────────────────────────────────
    # review_router decides: APPROVED → explain, CHANGES_REQUIRED → refine.
    graph.add_conditional_edges(
        "review",
        review_router,
        {"refine": "refine", "explain": "explain"},
    )

    # ── Refine-review feedback loop ───────────────────────────────────────
    # Refine rewrites ticket_drafts then hands control back to review.
    # The loop is bounded by max_iterations (see review_router).
    graph.add_edge("refine", "review")

    # ── Approval / terminal path ──────────────────────────────────────────
    graph.add_edge("explain", "validate")
    graph.add_edge("validate", "create")
    graph.add_edge("create", END)

    return graph


# Compile once at import time; the compiled graph is a coroutine-safe
# async callable reused for every incoming request.
workflow = build_workflow().compile()
