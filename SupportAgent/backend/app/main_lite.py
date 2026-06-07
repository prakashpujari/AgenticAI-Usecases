"""
Minimal AIOps Platform API - Fast startup version for local development
This is a lightweight version that works without heavy dependencies
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime
import uuid
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="AIOps Platform Lite",
    description="Minimal local development version",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo
incidents_db = {}
rca_db = {}

@app.on_event("startup")
async def startup():
    logger.info("AIOps Platform Lite starting...")
    logger.info("API Documentation: http://localhost:8000/docs")

@app.on_event("shutdown")
async def shutdown():
    logger.info("AIOps Platform Lite shutting down...")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": "development",
        "mode": "lite"
    }

# Get all incidents
@app.get("/api/v1/incidents")
async def list_incidents():
    """List all incidents"""
    incidents = list(incidents_db.values())
    return {
        "total": len(incidents),
        "incidents": incidents
    }

# Create incident
@app.post("/api/v1/incidents")
async def create_incident(
    title: str,
    description: str,
    severity: str = "P3_MEDIUM",
    affected_services: list = None,
    affected_components: list = None,
    environment: str = "production",
    detection_source: str = "api",
    confidence_score: float = 0.5,
    business_impact: str = None,
    customer_impact: int = 0
):
    """Create a new incident"""
    incident_id = str(uuid.uuid4())
    incident_number = f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"

    incident = {
        "id": incident_id,
        "incident_number": incident_number,
        "title": title,
        "description": description,
        "severity": severity,
        "status": "DETECTED",
        "affected_services": affected_services or [],
        "affected_components": affected_components or [],
        "environment": environment,
        "detection_source": detection_source,
        "confidence_score": confidence_score,
        "business_impact": business_impact,
        "customer_impact": customer_impact,
        "detected_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    incidents_db[incident_id] = incident
    logger.info(f"Incident created: {incident_number}")
    return incident

# Get incident details
@app.get("/api/v1/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get incident details"""
    if incident_id not in incidents_db:
        return {"error": "Incident not found"}, 404
    return incidents_db[incident_id]

# Update incident
@app.put("/api/v1/incidents/{incident_id}")
async def update_incident(incident_id: str, status: str = None):
    """Update incident status"""
    if incident_id not in incidents_db:
        return {"error": "Incident not found"}, 404

    if status:
        incidents_db[incident_id]["status"] = status
        incidents_db[incident_id]["updated_at"] = datetime.utcnow().isoformat()

    return incidents_db[incident_id]

# Run RCA
@app.post("/api/v1/incidents/{incident_id}/rca")
async def run_rca(incident_id: str):
    """Run RCA analysis (mock)"""
    if incident_id not in incidents_db:
        return {"error": "Incident not found"}, 404

    incident = incidents_db[incident_id]

    rca_report = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "root_cause": f"Analysis of {incident['title']}",
        "affected_systems": incident["affected_components"],
        "contributing_factors": ["High memory usage", "CPU spike", "Database connection pool exhaustion"],
        "timeline": [
            {"timestamp": "2024-01-15T10:00:00Z", "event": "Issue detected"},
            {"timestamp": "2024-01-15T10:05:00Z", "event": "Alerts triggered"},
            {"timestamp": "2024-01-15T10:10:00Z", "event": "Investigation started"}
        ],
        "recommended_fix": "Restart affected services and optimize resource allocation",
        "implementation_steps": ["Step 1", "Step 2", "Step 3"],
        "prevention_measures": ["Add monitoring", "Increase capacity", "Implement auto-scaling"],
        "confidence_score": 0.85,
        "analysis_completed_at": datetime.utcnow().isoformat()
    }

    rca_db[incident_id] = rca_report
    incidents_db[incident_id]["status"] = "ANALYZING"

    return {
        "status": "completed",
        "rca_report": rca_report
    }

# Generate remediation
@app.post("/api/v1/incidents/{incident_id}/remediation")
async def generate_remediation(incident_id: str):
    """Generate remediation playbook (mock)"""
    if incident_id not in incidents_db:
        return {"error": "Incident not found"}, 404

    playbook = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "status": "pending_approval",
        "risk_level": "medium",
        "estimated_duration_minutes": 15,
        "actions": [
            {
                "id": "action-1",
                "name": "Restart API Server",
                "description": "Restart the affected API service",
                "action_type": "restart_pod",
                "risk_level": "low",
                "duration_seconds": 30,
                "rollback_possible": True,
                "parameters": {"service": "api-server", "replicas": 3}
            },
            {
                "id": "action-2",
                "name": "Scale Database Connections",
                "description": "Increase database connection pool size",
                "action_type": "scale_deployment",
                "risk_level": "medium",
                "duration_seconds": 60,
                "rollback_possible": True,
                "parameters": {"resource": "postgresql", "pool_size": 50}
            }
        ],
        "success_criteria": [
            "API response time < 500ms",
            "Error rate < 0.5%",
            "Database connections < 80%",
            "No customer-facing errors"
        ],
        "created_at": datetime.utcnow().isoformat()
    }

    incidents_db[incident_id]["status"] = "REMEDIATION_PENDING"

    return playbook

# Get metrics
@app.get("/api/v1/metrics")
async def get_metrics():
    """Get platform metrics"""
    return {
        "total_incidents": len(incidents_db),
        "incidents_by_severity": {
            "P1_CRITICAL": sum(1 for i in incidents_db.values() if i["severity"] == "P1_CRITICAL"),
            "P2_HIGH": sum(1 for i in incidents_db.values() if i["severity"] == "P2_HIGH"),
            "P3_MEDIUM": sum(1 for i in incidents_db.values() if i["severity"] == "P3_MEDIUM"),
            "P4_LOW": sum(1 for i in incidents_db.values() if i["severity"] == "P4_LOW"),
        },
        "incidents_by_status": {
            "DETECTED": sum(1 for i in incidents_db.values() if i["status"] == "DETECTED"),
            "ANALYZING": sum(1 for i in incidents_db.values() if i["status"] == "ANALYZING"),
            "REMEDIATION_PENDING": sum(1 for i in incidents_db.values() if i["status"] == "REMEDIATION_PENDING"),
            "RESOLVED": sum(1 for i in incidents_db.values() if i["status"] == "RESOLVED"),
        },
        "mttd_minutes": 16.6,
        "mttr_minutes": 49.0,
        "detection_accuracy": 0.942,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
