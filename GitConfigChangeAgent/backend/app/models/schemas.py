from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import List, Optional


class ConfigType(str, Enum):
    yaml = "yaml"
    properties = "properties"
    constants = "constants"


class Mode(str, Enum):
    dry_run = "dry-run"
    apply = "apply"


class ConfigScope(BaseModel):
    group_ids: Optional[List[int]] = []
    project_ids: Optional[List[int]] = []


class ConfigChangeRequestCreate(BaseModel):
    config_type: ConfigType
    old_value: str
    new_value: str
    key_path: Optional[str] = None
    scope: ConfigScope
    mode: Mode
    branch_strategy: str = "feature-per-project"
    open_merge_requests: bool = False
    description: Optional[str] = None


class RunSummaryResponse(BaseModel):
    run_id: str
    config_type: ConfigType
    mode: Mode
    status: str
    projects_scanned: int
    files_scanned: int
    files_matched: int
    files_changed: int
    risk_score: float
    created_at: datetime


class ProjectSummary(BaseModel):
    project_id: int
    name: str
    files_matched: int
    files_changed: int
    merge_request_url: Optional[str] = None


class RunMetrics(BaseModel):
    projects_scanned: int
    files_scanned: int
    files_matched: int
    files_changed: int
    lines_added: int
    lines_removed: int


class EvaluationResult(BaseModel):
    risk_score: float
    missed_references: List[str] = []
    recommendations: List[str] = []


class AuditInfo(BaseModel):
    initiated_by: str
    approved_by: Optional[str] = None
    approval_required: bool
    run_type: str


class RunDetailResponse(BaseModel):
    run_id: str
    config_type: ConfigType
    mode: Mode
    status: str
    created_at: datetime
    user_id: str
    scope: ConfigScope
    metrics: RunMetrics
    projects: List[ProjectSummary]
    audit: AuditInfo
    evaluation: EvaluationResult


class DiffResponse(BaseModel):
    file_id: str
    project_id: int
    path: str
    type: ConfigType
    status: str
    diff: str
    summary: str
    llm_rationale: str


class SearchRequest(BaseModel):
    query: str
    scope: ConfigScope


class SearchMatch(BaseModel):
    project_id: int
    file_path: str
    filename: Optional[str] = None
    ref: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    matches: List[SearchMatch]


class ApplyFileChange(BaseModel):
    project_id: int
    file_path: str
    new_content: str
    commit_message: str
    action: Optional[str] = "update"  # create|update|delete


class ApplyChangeRequest(BaseModel):
    branch_name: Optional[str] = None
    target_branch: Optional[str] = None
    changes: List[ApplyFileChange]
    open_merge_request: bool = False


class ApplyChangeResult(BaseModel):
    project_id: int
    branch: str
    commit_id: Optional[str] = None
    merge_request_url: Optional[str] = None
    success: bool
    message: Optional[str] = None


class ApplyChangeResponse(BaseModel):
    results: List[ApplyChangeResult]


class EstimateRequest(BaseModel):
    query: str
    scope: ConfigScope


class ProjectEstimate(BaseModel):
    project_id: int
    name: Optional[str] = None
    files_matched: int


class EstimateResponse(BaseModel):
    query: str
    projects_scanned: int
    files_matched: int
    details: List[ProjectEstimate]
