import time
from memory.redis_store import get_memory, save_memory
from memory.pinecone_store import retrieve_context
from guardrails.rules import validate_output
from observability.logger import get_logger, trace_agent
from observability.metrics import increment, record_duration

logger = get_logger("agent.response")


@trace_agent("response")
def response_agent(state):
    start = time.perf_counter()
    session_id = state["session_id"]

    # ── memory read (non-fatal) ────────────────────────────────────────────────
    try:
        mem = get_memory(session_id)
    except Exception:
        logger.warning("Redis unavailable — memory read skipped", exc_info=True)
        mem = []

    # ── vector context retrieval (non-fatal) ──────────────────────────────────
    try:
        ctx = retrieve_context(state["input"])
    except Exception:
        logger.warning("Pinecone unavailable — context retrieval skipped", exc_info=True)
        ctx = ["context unavailable"]

    # ── compose output ────────────────────────────────────────────────────────
    raw_output = (
        f"Plan: {state['plan']} | "
        f"Tool: {state['tool_result']} | "
        f"History: {mem} | "
        f"Context: {ctx}"
    )

    # ── output guardrail ──────────────────────────────────────────────────────
    output = validate_output(raw_output)

    # ── memory write (non-fatal) ───────────────────────────────────────────────
    try:
        save_memory(session_id, state["input"], output)
    except Exception:
        logger.warning("Redis unavailable — memory write skipped", exc_info=True)

    increment("response.success")
    record_duration("response.latency_ms", (time.perf_counter() - start) * 1000)
    return {"output": output}
