from datetime import datetime
from typing import Optional, List, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class SeverityLevel(str, Enum):
    P1 = "P1_CRITICAL"
    P2 = "P2_HIGH"
    P3 = "P3_MEDIUM"
    P4 = "P4_LOW"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    ANALYZING = "ANALYZING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class RemediationStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


# Base Models
class IncidentBase(BaseModel):
    title: str
    description: Optional[str] = None
    severity: SeverityLevel
    affected_services: List[str]
    affected_components: List[str]
    environment: str
    detection_source: str
    confidence_score: float
    business_impact: Optional[str] = None
    customer_impact: int = 0


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[IncidentStatus] = None
    severity: Optional[SeverityLevel] = None
    business_impact: Optional[str] = None


class IncidentResponse(IncidentBase):
    id: str
    incident_number: str
    servicenow_id: Optional[str] = None
    jira_key: Optional[str] = None
    status: IncidentStatus
    detected_at: datetime
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    impact_duration_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RCAReportBase(BaseModel):
    root_cause: str
    confidence_score: float
    affected_systems: List[str]
    contributing_factors: List[str]
    timeline: List[Dict[str, Any]]
    recommended_fix: Optional[str] = None
    implementation_steps: Optional[List[str]] = None
    prevention_measures: Optional[List[str]] = None


class RCAReportCreate(RCAReportBase):
    incident_id: str


class RCAReportResponse(RCAReportBase):
    id: str
    incident_id: str
    similar_incidents: List[Dict[str, Any]]
    knowledge_base_references: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RemediationActionBase(BaseModel):
    action_type: str
    action_name: str
    description: Optional[str] = None
    playbook: Dict[str, Any]
    confidence_score: Optional[float] = None


class RemediationActionCreate(RemediationActionBase):
    incident_id: str


class RemediationActionApprove(BaseModel):
    approved_by: str
    approval_comment: Optional[str] = None


class RemediationActionExecute(BaseModel):
    executed_by: str


class RemediationActionResponse(RemediationActionBase):
    id: str
    incident_id: str
    status: RemediationStatus
    requires_approval: bool
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    executed_by: Optional[str] = None
    executed_at: Optional[datetime] = None
    execution_duration_seconds: Optional[int] = None
    execution_output: Optional[str] = None
    execution_error: Optional[str] = None
    rolled_back: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceBase(BaseModel):
    evidence_type: str
    source: str
    raw_data: Dict[str, Any]
    search_query: Optional[str] = None
    time_range_start: datetime
    time_range_end: datetime


class EvidenceCreate(EvidenceBase):
    incident_id: str


class EvidenceResponse(EvidenceBase):
    id: str
    incident_id: str
    processed_data: Optional[Dict[str, Any]] = None
    relevance_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogBase(BaseModel):
    action: str
    actor: str
    actor_type: str
    changes: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    incident_id: Optional[str] = None


class AuditLogResponse(AuditLogBase):
    id: str
    incident_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Detection Agent Models
class DetectedAnomaly(BaseModel):
    timestamp: datetime
    metric_name: str
    metric_value: float
    expected_value: float
    z_score: float
    anomaly_type: str
    source: str
    confidence: float


class DetectionResult(BaseModel):
    incident_detected: bool
    anomalies: List[DetectedAnomaly]
    affected_services: List[str]
    affected_components: List[str]
    severity_classification: SeverityLevel
    confidence_score: float
    evidence: List[Dict[str, Any]]


class MLAnomalyModelBase(BaseModel):
    model_type: str
    source: str
    metric_type: str
    version: int = 1
    is_active: bool = True


class MLAnomalyModelCreate(MLAnomalyModelBase):
    model_path: str
    metadata: Dict[str, Any]
    feature_names: List[str]


class MLAnomalyModelResponse(MLAnomalyModelBase):
    id: str
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    last_training_at: Optional[datetime] = None
    last_inference_at: Optional[datetime] = None
    training_samples_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseArticleBase(BaseModel):
    title: str
    content: str
    category: str
    tags: List[str] = []
    source: Optional[str] = None
    url: Optional[str] = None


class KnowledgeBaseArticleCreate(KnowledgeBaseArticleBase):
    pass


class KnowledgeBaseArticleResponse(KnowledgeBaseArticleBase):
    id: str
    related_incidents: List[str]
    embedding: Optional[List[float]] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    views_count: int = 0
    helpful_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Metrics Models
class IncidentMetrics(BaseModel):
    total_incidents: int
    p1_count: int
    p2_count: int
    p3_count: int
    p4_count: int
    avg_mttr_minutes: float
    avg_mttd_minutes: float
    auto_remediation_success_rate: float
    rca_accuracy: float
    false_positive_rate: float


class PlatformMetrics(BaseModel):
    detection_accuracy: float
    agent_success_rate: float
    avg_token_cost: float
    llm_calls_total: int
    avg_agent_iterations: float
    cache_hit_rate: float
