import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, init_db, close_db
from app.models import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
    RCAReportCreate,
    RCAReportResponse,
    RemediationActionCreate,
    RemediationActionApprove,
    RemediationActionResponse,
)
from app.schemas import Incident, RCAReport, RemediationAction, IncidentStatus, RemediationStatus
from app.agents.detection_agent import IncidentDetectionAgent
from app.agents.rca_agent import RCAAgent
from app.agents.remediation_agent import RemediationAgent
from app.agents.classification_agent import IncidentClassificationAgent

logger = logging.getLogger(__name__)

# Global agent instances
detection_agent = None
rca_agent = None
remediation_agent = None
classification_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting AIOps Platform")
    await init_db()

    global detection_agent, rca_agent, remediation_agent, classification_agent
    detection_agent = IncidentDetectionAgent()
    rca_agent = RCAAgent()
    remediation_agent = RemediationAgent()
    classification_agent = IncidentClassificationAgent()

    await detection_agent.initialize()

    yield

    # Shutdown
    logger.info("Shutting down AIOps Platform")
    await detection_agent.cleanup()
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Health Check ====================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
    }


# ==================== Detection Endpoints ====================

@app.post("/api/v1/incidents/detect")
async def trigger_detection(
    check_logs: bool = True,
    check_metrics: bool = True,
    lookback_hours: int = 1,
):
    """Trigger incident detection."""
    try:
        result = await detection_agent.detect_incidents(
            check_logs=check_logs,
            check_metrics=check_metrics,
            lookback_hours=lookback_hours,
        )

        if result.get("incident_detected"):
            return {
                "status": "incident_detected",
                "confidence": result.get("overall_confidence_score", 0),
                "details": result,
            }
        else:
            return {
                "status": "no_incident",
                "confidence": 0,
                "details": result,
            }

    except Exception as e:
        logger.error(f"Detection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {str(e)}",
        )


# ==================== Incident Endpoints ====================

@app.post("/api/v1/incidents", response_model=IncidentResponse)
async def create_incident(
    incident: IncidentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new incident."""
    try:
        # Classify incident severity
        classification = await classification_agent.classify_incident(
            title=incident.title,
            description=incident.description or "",
            affected_services=incident.affected_services,
            affected_components=incident.affected_components,
            customer_impact=incident.customer_impact,
        )

        new_incident = Incident(
            id=str(uuid.uuid4()),
            incident_number=f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}",
            title=incident.title,
            description=incident.description,
            severity=classification["severity"],
            status=IncidentStatus.DETECTED,
            confidence_score=incident.confidence_score,
            affected_services=incident.affected_services,
            affected_components=incident.affected_components,
            environment=incident.environment,
            detection_source=incident.detection_source,
            business_impact=incident.business_impact,
            customer_impact=incident.customer_impact,
            detected_at=datetime.utcnow(),
        )

        db.add(new_incident)
        await db.commit()
        await db.refresh(new_incident)

        logger.info(f"Created incident: {new_incident.incident_number}")

        return new_incident

    except Exception as e:
        logger.error(f"Failed to create incident: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create incident: {str(e)}",
        )


@app.get("/api/v1/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get incident details."""
    try:
        from sqlalchemy import select

        result = await db.execute(select(Incident).where(Incident.id == incident_id))
        incident = result.scalars().first()

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        return incident

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get incident: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get incident: {str(e)}",
        )


# ==================== RCA Endpoints ====================

@app.post("/api/v1/incidents/{incident_id}/rca")
async def run_rca(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Run RCA for an incident."""
    try:
        from sqlalchemy import select

        # Get incident
        result = await db.execute(select(Incident).where(Incident.id == incident_id))
        incident = result.scalars().first()

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        # Prepare evidence (mock for now)
        evidence = {
            "logs": [],
            "metrics": [],
            "traces": [],
            "affected_services": incident.affected_services,
        }

        # Run RCA
        rca_result = await rca_agent.analyze_root_cause(
            incident_title=incident.title,
            incident_description=incident.description or "",
            evidence=evidence,
        )

        # Store RCA report
        rca_report = RCAReport(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            root_cause=rca_result.get("root_cause", ""),
            confidence_score=rca_result.get("confidence_score", 0),
            affected_systems=rca_result.get("affected_systems", []),
            contributing_factors=rca_result.get("contributing_factors", []),
            timeline=rca_result.get("timeline", []),
            recommended_fix=rca_result.get("recommended_fix", ""),
            implementation_steps=rca_result.get("implementation_steps", []),
            prevention_measures=rca_result.get("prevention_measures", []),
            knowledge_base_references=[],
        )

        db.add(rca_report)
        incident.status = IncidentStatus.ANALYZING
        await db.commit()

        logger.info(f"RCA completed for incident {incident_id}")

        return {
            "status": "rca_completed",
            "incident_id": incident_id,
            "rca_report": rca_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RCA failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RCA failed: {str(e)}",
        )


# ==================== Remediation Endpoints ====================

@app.post("/api/v1/incidents/{incident_id}/remediation")
async def generate_remediation(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate remediation playbook for an incident."""
    try:
        from sqlalchemy import select

        result = await db.execute(select(Incident).where(Incident.id == incident_id))
        incident = result.scalars().first()

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        # Get RCA (if exists)
        rca_result = await db.execute(
            select(RCAReport).where(RCAReport.incident_id == incident_id)
        )
        rca_report = rca_result.scalars().first()

        root_cause = rca_report.root_cause if rca_report else "Unknown"

        # Generate playbook
        playbook = await remediation_agent.generate_remediation_playbook(
            root_cause=root_cause,
            affected_systems=incident.affected_services,
            severity=incident.severity,
            environment=incident.environment,
        )

        return {
            "status": "playbook_generated",
            "incident_id": incident_id,
            "playbook": playbook,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remediation generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Remediation generation failed: {str(e)}",
        )


@app.post("/api/v1/remediation/{action_id}/approve")
async def approve_remediation(
    action_id: str,
    approval: RemediationActionApprove,
    db: AsyncSession = Depends(get_db),
):
    """Approve a remediation action."""
    try:
        from sqlalchemy import select

        result = await db.execute(
            select(RemediationAction).where(RemediationAction.id == action_id)
        )
        action = result.scalars().first()

        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Remediation action not found",
            )

        action.status = RemediationStatus.APPROVED
        action.approved_by = approval.approved_by
        action.approved_at = datetime.utcnow()
        action.approval_comment = approval.approval_comment

        await db.commit()

        logger.info(f"Approved remediation action {action_id}")

        return {
            "status": "approved",
            "action_id": action_id,
            "approved_by": approval.approved_by,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval failed: {str(e)}",
        )


# ==================== Metrics Endpoints ====================

@app.get("/api/v1/metrics")
async def get_platform_metrics(db: AsyncSession = Depends(get_db)):
    """Get platform metrics."""
    try:
        from sqlalchemy import select, func

        total_incidents = await db.execute(select(func.count(Incident.id)))
        total_count = total_incidents.scalar()

        return {
            "total_incidents": total_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}",
        )


# ==================== Health Endpoints ====================

@app.get("/api/v1/connectors/health")
async def check_connector_health():
    """Check health of all connectors."""
    try:
        splunk_health = await detection_agent.splunk.health_check()
        datadog_health = await detection_agent.datadog.health_check()
        prometheus_health = await detection_agent.prometheus.health_check()

        return {
            "splunk": "healthy" if splunk_health else "unhealthy",
            "datadog": "healthy" if datadog_health else "unhealthy",
            "prometheus": "healthy" if prometheus_health else "unhealthy",
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
