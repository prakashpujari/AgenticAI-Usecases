from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, borrower, documents, underwriting, utilities

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(borrower.router)
router.include_router(documents.router)
router.include_router(underwriting.router)
router.include_router(utilities.router)
