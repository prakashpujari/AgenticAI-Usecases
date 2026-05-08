from __future__ import annotations

import structlog
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.exceptions import AppError, RateLimitError
from app.core.logging_config import configure_logging, get_logger
from app.core.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.infrastructure.cache.redis_client import close_redis
from app.infrastructure.metrics.prometheus import metrics_endpoint
from app.infrastructure.database.engine import get_engine, Base
# Import models so SQLAlchemy registers them before create_all
import app.infrastructure.database.models  # noqa: F401

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "application_starting",
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    # Create tables if they don't exist, then seed sample data
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_ready")
        await _seed_borrowers()
    except Exception as exc:  # noqa: BLE001
        logger.warning("database_init_failed", error=str(exc))

    yield
    # Shutdown: drain connections gracefully
    await close_redis()
    logger.info("application_stopped")


async def _seed_borrowers() -> None:
    """Insert sample borrowers if the table is empty."""
    from datetime import date
    from app.models.domain.borrower import (
        BorrowerProfile, IncomeType, LoanPurpose, PropertyType,
    )
    from app.repositories.borrower_repository import get_borrower_repository

    repo = get_borrower_repository()
    if await repo.count() > 0:
        return  # already seeded

    samples = [
        BorrowerProfile(
            id="brw_001", loan_number="LN-2024-001",
            first_name="James", last_name="Carter", ssn_last4="3821",
            date_of_birth=date(1985, 4, 12), email="jcarter@email.com",
            loan_amount=450_000, property_value=560_000,
            loan_purpose=LoanPurpose.PURCHASE, property_type=PropertyType.SINGLE_FAMILY,
            annual_income=120_000, income_type=IncomeType.W2,
            monthly_debts=1_200, credit_score=740,
            loan_program="CONV_30", loan_officer="Officer Smith",
        ),
        BorrowerProfile(
            id="brw_002", loan_number="LN-2024-002",
            first_name="Maria", last_name="Gonzalez", ssn_last4="5590",
            date_of_birth=date(1978, 9, 30), email="mgonzalez@email.com",
            loan_amount=320_000, property_value=360_000,
            loan_purpose=LoanPurpose.REFINANCE, property_type=PropertyType.CONDO,
            annual_income=85_000, income_type=IncomeType.SELF_EMPLOYED,
            monthly_debts=800, credit_score=695,
            loan_program="FHA_30", loan_officer="Officer Jones",
        ),
        BorrowerProfile(
            id="brw_003", loan_number="LN-2024-003",
            first_name="David", last_name="Kim", ssn_last4="7743",
            date_of_birth=date(1990, 1, 15), email="dkim@email.com",
            loan_amount=680_000, property_value=720_000,
            loan_purpose=LoanPurpose.PURCHASE, property_type=PropertyType.SINGLE_FAMILY,
            annual_income=210_000, income_type=IncomeType.W2,
            monthly_debts=2_500, credit_score=790,
            loan_program="JUMBO_30", loan_officer="Officer Williams",
        ),
        BorrowerProfile(
            id="brw_004", loan_number="LN-2024-004",
            first_name="Sarah", last_name="Thompson", ssn_last4="4412",
            date_of_birth=date(1982, 7, 22), email="sthompson@email.com",
            loan_amount=275_000, property_value=300_000,
            loan_purpose=LoanPurpose.REFINANCE, property_type=PropertyType.TOWNHOUSE,
            annual_income=95_000, income_type=IncomeType.W2,
            monthly_debts=600, credit_score=720,
            loan_program="CONV_30", loan_officer="Officer Brown",
        ),
        BorrowerProfile(
            id="brw_005", loan_number="LN-2024-005",
            first_name="Robert", last_name="Martinez", ssn_last4="9901",
            date_of_birth=date(1975, 3, 8), email="rmartinez@email.com",
            loan_amount=510_000, property_value=600_000,
            loan_purpose=LoanPurpose.PURCHASE, property_type=PropertyType.SINGLE_FAMILY,
            annual_income=175_000, income_type=IncomeType.SELF_EMPLOYED,
            monthly_debts=1_800, credit_score=762,
            loan_program="CONV_30", loan_officer="Officer Davis",
        ),
    ]
    for profile in samples:
        try:
            await repo.save(profile)
        except Exception as exc:  # noqa: BLE001
            logger.warning("seed_borrower_failed", id=profile.id, error=str(exc))

    logger.info("borrowers_seeded", count=len(samples))


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Internal Mortgage Utilities Platform — "
            "Borrower lookup, calculators, document tools, and underwriting utilities."
        ),
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost runs first) ──────────────────────
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        correlation_id = request.headers.get("X-Correlation-ID")
        log = logger.bind(
            error_code=exc.error_code,
            path=request.url.path,
            correlation_id=correlation_id,
        )
        if exc.status_code >= 500:
            log.error("app_error", message=exc.message)
        else:
            log.warning("app_error", message=exc.message)

        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "correlation_id": correlation_id,
                "details": exc.detail if exc.detail else [],
            },
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "correlation_id": request.headers.get("X-Correlation-ID"),
                "details": details,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "correlation_id": request.headers.get("X-Correlation-ID"),
                "details": [],
            },
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_v1_router)
    app.add_route("/metrics", metrics_endpoint)

    @app.get("/health", tags=["Operations"], include_in_schema=False)
    async def health_check() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": settings.app_version,
            "environment": settings.environment,
        }

    return app


app = create_app()
