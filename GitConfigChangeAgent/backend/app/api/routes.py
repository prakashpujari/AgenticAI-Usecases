from fastapi import APIRouter, Depends, HTTPException, status
from app.models.schemas import (
    ConfigChangeRequestCreate,
    RunSummaryResponse,
    RunDetailResponse,
    DiffResponse,
    EstimateRequest,
    EstimateResponse,
    SearchRequest,
    SearchResponse,
    ApplyChangeRequest,
    ApplyChangeResponse,
)
from app.services.orchestration_service import OrchestrationService
from app.services.auth_service import AuthService

router = APIRouter()

@router.get("/healthz")
async def health_check():
    """Public health check endpoint for API clients."""
    return {"status": "ok"}

@router.post("/runs", response_model=RunSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_run(request: ConfigChangeRequestCreate, user=Depends(AuthService.get_current_user)):
    service = OrchestrationService()
    run = await service.create_run(request=request, user=user)
    return run

@router.get("/runs", response_model=list[RunSummaryResponse])
async def list_runs(user=Depends(AuthService.get_current_user), limit: int = 20, offset: int = 0):
    service = OrchestrationService()
    return await service.list_runs(user=user, limit=limit, offset=offset)

@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: str, user=Depends(AuthService.get_current_user)):
    service = OrchestrationService()
    run = await service.get_run(run_id=run_id, user=user)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run

@router.get("/runs/{run_id}/files/{file_id}/diff", response_model=DiffResponse)
async def get_diff(run_id: str, file_id: str, user=Depends(AuthService.get_current_user)):
    service = OrchestrationService()
    return await service.get_diff(run_id=run_id, file_id=file_id, user=user)


@router.post("/estimate", response_model=EstimateResponse)
async def estimate(request: EstimateRequest, user=Depends(AuthService.get_current_user)):
    """Estimate how many files across selected projects/groups match the query."""
    service = OrchestrationService()
    result = await service.estimate_impacted_files(query=request.query, scope=request)
    return result


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, user=Depends(AuthService.get_current_user)):
    """Search across configured GitLab projects/groups and return matching file paths."""
    service = OrchestrationService()
    result = await service.search_files(query=request.query, scope=request)
    return result


@router.post("/apply", response_model=ApplyChangeResponse)
async def apply_changes(request: ApplyChangeRequest, user=Depends(AuthService.get_current_user)):
    """Apply confirmed file changes via GitLab API (branch, commit, optional MR)."""
    service = OrchestrationService()
    result = await service.apply_changes(request=request, user=user)
    return result
