from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    JSON, Enum as SQLEnum, ForeignKey, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


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


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True)
    incident_number = Column(String(50), unique=True, index=True)
    servicenow_id = Column(String(50), nullable=True, index=True)
    jira_key = Column(String(50), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    severity = Column(SQLEnum(SeverityLevel), nullable=False, default=SeverityLevel.P3)
    status = Column(SQLEnum(IncidentStatus), nullable=False, default=IncidentStatus.DETECTED)
    confidence_score = Column(Float, nullable=False)
    affected_services = Column(JSON)  # List of service names
    affected_components = Column(JSON)  # List of component names
    environment = Column(String(50), nullable=False)  # prod, staging, dev
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    impact_duration_minutes = Column(Integer, nullable=True)
    detection_source = Column(String(100), nullable=False)  # splunk, datadog, prometheus
    business_impact = Column(Text, nullable=True)
    customer_impact = Column(Integer, default=0)  # number of affected customers

    # Relationships
    rca_reports = relationship("RCAReport", back_populates="incident")
    remediation_actions = relationship("RemediationAction", back_populates="incident")
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.incident_id", back_populates="incident")
    evidence = relationship("Evidence", back_populates="incident")

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_severity_status", "severity", "status"),
        Index("idx_detected_at", "detected_at"),
        Index("idx_environment", "environment"),
    )


class RCAReport(Base):
    __tablename__ = "rca_reports"

    id = Column(String(36), primary_key=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    root_cause = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=False)
    affected_systems = Column(JSON)
    contributing_factors = Column(JSON)
    timeline = Column(JSON)  # List of events with timestamps
    similar_incidents = Column(JSON)  # Historical incidents with similarities
    recommended_fix = Column(Text)
    implementation_steps = Column(JSON)
    prevention_measures = Column(JSON)
    knowledge_base_references = Column(JSON)  # Links to KB articles

    incident = relationship("Incident", back_populates="rca_reports")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_incident_id", "incident_id"),
    )


class RemediationAction(Base):
    __tablename__ = "remediation_actions"

    id = Column(String(36), primary_key=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)  # restart_pod, scale_deployment, etc.
    action_name = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(RemediationStatus), nullable=False, default=RemediationStatus.PENDING_APPROVAL)
    playbook = Column(JSON)  # Detailed steps
    confidence_score = Column(Float)

    # Approval workflow
    requires_approval = Column(Boolean, default=True)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_comment = Column(Text, nullable=True)

    # Execution
    executed_by = Column(String(100), nullable=True)
    executed_at = Column(DateTime, nullable=True)
    execution_duration_seconds = Column(Integer, nullable=True)
    execution_output = Column(Text, nullable=True)
    execution_error = Column(Text, nullable=True)

    # Rollback
    rolled_back = Column(Boolean, default=False)
    rollback_executed_at = Column(DateTime, nullable=True)

    incident = relationship("Incident", back_populates="remediation_actions")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_incident_remediation", "incident_id", "status"),
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    evidence_type = Column(String(50), nullable=False)  # log, metric, trace, event
    source = Column(String(100), nullable=False)  # splunk, datadog, prometheus
    raw_data = Column(JSON)
    processed_data = Column(JSON)
    search_query = Column(Text, nullable=True)
    time_range_start = Column(DateTime, nullable=False)
    time_range_end = Column(DateTime, nullable=False)
    relevance_score = Column(Float, default=0.0)

    incident = relationship("Incident", back_populates="evidence")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_incident_evidence", "incident_id", "evidence_type"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)  # INCIDENT_CREATED, REMEDIATION_APPROVED, etc.
    actor = Column(String(100), nullable=False)
    actor_type = Column(String(50), nullable=False)  # USER, AGENT, SYSTEM
    changes = Column(JSON)  # What changed
    reason = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    incident = relationship("Incident", foreign_keys=[incident_id], back_populates="audit_logs")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_action_actor", "action", "actor"),
        Index("idx_created_at", "created_at"),
    )


class MLAnomalyModel(Base):
    __tablename__ = "ml_anomaly_models"

    id = Column(String(36), primary_key=True)
    model_type = Column(String(50), nullable=False)  # isolation_forest, lstm, etc.
    source = Column(String(100), nullable=False)  # splunk, datadog, prometheus
    metric_type = Column(String(100), nullable=False)  # cpu_usage, error_rate, latency, etc.
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)

    model_path = Column(String(500), nullable=False)
    metadata = Column(JSON)  # Model-specific metadata (hyperparameters, etc.)
    feature_names = Column(JSON)  # Feature names used for training

    last_training_at = Column(DateTime, nullable=True)
    last_inference_at = Column(DateTime, nullable=True)
    training_samples_count = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_model_source_metric", "source", "metric_type", "is_active"),
    )


class KnowledgeBaseArticle(Base):
    __tablename__ = "knowledge_base_articles"

    id = Column(String(36), primary_key=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)
    tags = Column(JSON)
    related_incidents = Column(JSON)  # IDs of similar incidents
    embedding = Column(JSON, nullable=True)  # Vector embedding for RAG
    source = Column(String(100), nullable=True)  # internal, external, confluence, wiki
    url = Column(String(1000), nullable=True)
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    views_count = Column(Integer, default=0)
    helpful_count = Column(Integer, default=0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_category_tags", "category"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    roles = Column(JSON, default=["viewer"])  # viewer, analyst, engineer, admin
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    permissions = Column(JSON)  # Additional ABAC permissions

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_username_active", "username", "is_active"),
    )
