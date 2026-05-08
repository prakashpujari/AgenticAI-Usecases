import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from agent.graph import run_agent
from guardrails.rules import validate_input, GuardrailViolation
from observability.logger import get_logger, set_correlation_id, get_correlation_id
from observability.metrics import increment, record_duration, get_snapshot
from evaluation.rag_evaluator import evaluate_rag
from evaluation.llm_evaluator import evaluate_llm

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="LLMOps Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Correlation-ID middleware ──────────────────────────────────────────────────
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    set_correlation_id(cid)
    start = time.perf_counter()

    response: Response = await call_next(request)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Correlation-ID"] = cid
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

    logger.info(
        "HTTP request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
        },
    )
    record_duration("http.latency_ms", elapsed_ms, {"path": request.url.path})
    return response


# ── Request schema ─────────────────────────────────────────────────────────────
class AgentRequest(BaseModel):
    input: str
    user: str
    role: str
    session_id: str

    @field_validator("input", "user", "role", "session_id")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


# ── Main agent endpoint ────────────────────────────────────────────────────────
@app.post("/run_agent")
async def run_agent_endpoint(request: AgentRequest):
    cid = get_correlation_id()
    logger.info(
        "Agent request received",
        extra={"user": request.user, "role": request.role, "correlation_id": cid},
    )
    increment("api.run_agent.requests")

    # Input guardrails
    try:
        validate_input(request.input, request.user, request.role, request.session_id)
    except GuardrailViolation as e:
        increment("api.run_agent.guardrail_blocked")
        logger.warning("Guardrail blocked request", extra={"reason": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

    try:
        res = run_agent(request.input, request.user, request.role, request.session_id)
        increment("api.run_agent.success")
        return {"output": res, "correlation_id": cid}
    except PermissionError as e:
        increment("api.run_agent.forbidden")
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        # Circuit-breaker / downstream unavailable
        increment("api.run_agent.service_unavailable")
        logger.error("Downstream service unavailable", exc_info=True)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        increment("api.run_agent.errors")
        logger.error("Unhandled agent error", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Config endpoint ────────────────────────────────────────────────────────────
@app.get("/config")
async def config():
    return {"jira_url": os.getenv("JIRA_URL", "")}


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Metrics endpoint ───────────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    return get_snapshot()


# ── RAG evaluation endpoint ────────────────────────────────────────────────────
class RAGEvalRequest(BaseModel):
    questions: list[str]
    answers: list[str]
    contexts: list[list[str]]
    ground_truths: Optional[list[str]] = None

    @field_validator("questions", "answers", "contexts")
    @classmethod
    def must_not_be_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("List must not be empty")
        return v


@app.post("/evaluate/rag")
async def rag_evaluation(request: RAGEvalRequest):
    """
    Evaluate a RAG pipeline using RAGAS metrics.

    Metrics returned: faithfulness, answer_relevancy, context_precision,
    context_recall (when ground_truths are supplied).
    """
    cid = get_correlation_id()
    increment("api.evaluate_rag.requests")
    result = evaluate_rag(
        questions=request.questions,
        answers=request.answers,
        contexts=request.contexts,
        ground_truths=request.ground_truths,
        run_metadata={"correlation_id": cid},
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["detail"])
    increment("api.evaluate_rag.success")
    return result


# ── LLM evaluation endpoint ────────────────────────────────────────────────────
class LLMEvalRequest(BaseModel):
    input_text: str
    actual_output: str
    expected_output: Optional[str] = None
    retrieval_context: Optional[list[str]] = None

    @field_validator("input_text", "actual_output")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


@app.post("/evaluate/llm")
async def llm_evaluation(request: LLMEvalRequest):
    """
    Evaluate a single LLM response using DeepEval metrics.

    Metrics: AnswerRelevancy, Toxicity, Bias, and optionally
    Faithfulness + Hallucination when retrieval_context is provided.
    """
    cid = get_correlation_id()
    increment("api.evaluate_llm.requests")
    result = evaluate_llm(
        input_text=request.input_text,
        actual_output=request.actual_output,
        expected_output=request.expected_output,
        retrieval_context=request.retrieval_context,
        run_metadata={"correlation_id": cid},
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["detail"])
    increment("api.evaluate_llm.success")
    return result


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_config=None,   # disable uvicorn default logging; we use structured logs
        access_log=False,
    )
