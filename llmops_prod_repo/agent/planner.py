import os
import time
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import pybreaker

from observability.logger import get_logger, trace_agent
from observability.breakers import openai_breaker
from observability.metrics import increment, record_duration

logger = get_logger("agent.planner")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@retry(
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _call_openai(prompt: str) -> str:
    """Isolated OpenAI call wrapped with circuit breaker and retry."""
    return openai_breaker.call(
        lambda: client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            timeout=15,
        ).choices[0].message.content.strip()
    )


@trace_agent("planner")
def planner_agent(state):
    start = time.perf_counter()
    try:
        prompt = (
            f"User Role: {state['role']}\n"
            f"Query: {state['input']}\n"
            "Respond with exactly one of: create_ticket, view_ticket"
        )
        plan = _call_openai(prompt)
        # Normalise — default to view_ticket if LLM returns unexpected text
        if "create" not in plan.lower():
            plan = "view_ticket"
        else:
            plan = "create_ticket"
        increment("planner.success")
        record_duration("planner.latency_ms", (time.perf_counter() - start) * 1000)
        return {"plan": plan}
    except pybreaker.CircuitBreakerError as exc:
        increment("planner.circuit_open")
        logger.error("OpenAI circuit breaker is open", exc_info=True)
        raise RuntimeError("Planning service temporarily unavailable.") from exc
    except Exception as exc:
        increment("planner.error")
        logger.error("Planner agent failed", exc_info=True)
        raise
