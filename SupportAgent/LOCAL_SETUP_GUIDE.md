# Local Setup & End-to-End Testing Guide

## 📋 Prerequisites

```bash
# Check Docker
docker --version          # Should be 20.10+
docker-compose --version  # Should be 2.0+

# Check Python
python --version          # Should be 3.11+

# Check Node
node --version            # Should be 20+
npm --version             # Should be 10+
```

---

## 🚀 Step 1: Setup Environment Variables

### Create .env file
```bash
cd aiops-platform
cp .env.example .env
```

### Edit .env with your credentials
```bash
nano .env
```

**Add these real values:**
```env
# ==================== CORE ====================
ENVIRONMENT=development
LOG_LEVEL=DEBUG
API_HOST=0.0.0.0
API_PORT=8000

# ==================== DATABASE ====================
DATABASE_URL=postgresql+asyncpg://aiops:aiops@postgres:5432/aiops_db
REDIS_URL=redis://redis:6379
MILVUS_HOST=milvus
MILVUS_PORT=19530

# ==================== LLM ====================
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
# (Optional - if not provided, RCA tests will skip)

# ==================== OPTIONAL CONNECTORS ====================
# Add your real credentials if available:
# SPLUNK_HOST=your-splunk.com
# DATADOG_API_KEY=dd_...
# PROMETHEUS_URL=http://prometheus:9090
```

---

## 🐳 Step 2: Start Docker Services

### Start all services
```bash
docker-compose up -d
```

### Verify services are running
```bash
docker-compose ps
```

Expected output:
```
NAME              STATUS
aiops_postgres    Up (healthy)
aiops_redis       Up (healthy)
aiops_milvus      Up (healthy)
aiops_prometheus  Up
aiops_jaeger      Up
aiops_backend     Up (healthy)
aiops_frontend    Up
```

### Check backend logs
```bash
docker-compose logs -f backend
```

Wait for this message:
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## ✅ Step 3: Verify Services Are Healthy

### Check API health
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-03-15T12:00:00.123456",
  "environment": "development"
}
```

### Check database
```bash
docker exec aiops_postgres psql -U aiops -d aiops_db -c "SELECT 1;"
# Output: 1
```

### Check Redis
```bash
docker exec aiops_redis redis-cli ping
# Output: PONG
```

### Check Milvus
```bash
curl http://localhost:19530/healthz
```

---

## 🧪 Step 4: Run End-to-End Tests

### Install test dependencies
```bash
pip install requests aiohttp
```

### Run the full test suite
```bash
python tests/e2e_test.py
```

### Expected output
```
============================================================
AIOps Platform - End-to-End Test Suite
============================================================

ℹ️  Testing API health check...
✅ API is healthy - Status: healthy

ℹ️  Testing connector health...
✅ Connectors status: {...}

ℹ️  Creating test incident...
✅ Incident created: INC-20240315120000-ABC12345
ℹ️  Incident ID: 550e8400-e29b-41d4-a716-446655440000
ℹ️  Severity: P2_HIGH
ℹ️  Status: DETECTED

... (more tests)

============================================================
Test Summary
============================================================

✅ PASS: health_check
✅ PASS: connector_health
✅ PASS: metrics_endpoint
✅ PASS: create_incident
✅ PASS: get_incident
✅ PASS: trigger_detection
✅ PASS: run_rca
... (more results)

Total: 13/13 tests passed

🎉 All tests passed!
```

---

## 🌐 Step 5: Access the Platform

### Frontend
```
URL: http://localhost:5173
```

**What you'll see:**
- Incident Dashboard with real-time feed
- Created test incidents from E2E tests
- Metrics & charts

### Backend API Documentation
```
URL: http://localhost:8000/docs
```

**Interactive Swagger UI** - Test all endpoints:
- `POST /api/v1/incidents` - Create incident
- `GET /api/v1/incidents/{id}` - Get incident details
- `POST /api/v1/incidents/{id}/rca` - Run RCA
- `POST /api/v1/incidents/{id}/remediation` - Generate remediation

### Monitoring

**Prometheus Metrics:**
```
http://localhost:9090
```

**Jaeger Tracing:**
```
http://localhost:16686
```

---

## 🔄 Step 6: Manual Workflow Testing

### Create Test Incident via API
```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Manual Test Incident",
    "description": "Testing full workflow",
    "severity": "P2_HIGH",
    "affected_services": ["api", "database"],
    "affected_components": ["postgresql"],
    "environment": "production",
    "detection_source": "manual",
    "confidence_score": 0.90,
    "business_impact": "Payment processing affected"
  }' | jq
```

### Get Incident Details
```bash
INCIDENT_ID="your_incident_id_from_above"

curl http://localhost:8000/api/v1/incidents/$INCIDENT_ID | jq
```

### Run RCA
```bash
curl -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/rca | jq
```

### Generate Remediation Playbook
```bash
curl -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/remediation | jq
```

### Get Platform Metrics
```bash
curl http://localhost:8000/api/v1/metrics | jq
```

---

## 🐛 Step 7: Troubleshooting

### Backend not starting?
```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Port 8000 already in use
#    → Change API_PORT in .env

# 2. Database not ready
#    → Wait 10 seconds and retry

# 3. Missing dependencies
#    → Rebuild: docker-compose build backend
```

### Database errors?
```bash
# Reset database
docker-compose down
docker volume rm aiops_postgres_data
docker-compose up -d

# Verify connection
docker exec aiops_postgres psql -U aiops -d aiops_db -c "SELECT 1;"
```

### Redis not working?
```bash
docker-compose logs redis
docker exec aiops_redis redis-cli ping
```

### Frontend not loading?
```bash
# Check if frontend is running
curl http://localhost:5173

# If not, rebuild
docker-compose build frontend
docker-compose up -d frontend
```

### Tests failing?
```bash
# 1. Ensure all services are healthy
docker-compose ps

# 2. Check API is responding
curl http://localhost:8000/health

# 3. Run single test for debugging
python -c "from tests.e2e_test import E2ETestSuite; E2ETestSuite().test_health_check()"

# 4. Check logs
docker-compose logs -f backend
```

---

## 📊 Step 8: Advanced Testing

### Test with Load
```bash
# Install locust
pip install locust

# Create locustfile.py (see below)
locust -f locustfile.py --host=http://localhost:8000
```

### Load test file (locustfile.py)
```python
from locust import HttpUser, task, between

class AIopsUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def get_health(self):
        self.client.get("/health")

    @task
    def get_metrics(self):
        self.client.get("/api/v1/metrics")

    @task(3)
    def create_incident(self):
        self.client.post("/api/v1/incidents", json={
            "title": "Test Incident",
            "description": "Load test",
            "severity": "P4_LOW",
            "affected_services": ["test"],
            "affected_components": ["test"],
            "environment": "test",
            "detection_source": "load_test",
            "confidence_score": 0.5
        })
```

### Database Query Tests
```bash
docker exec aiops_postgres psql -U aiops -d aiops_db << EOF

-- View all incidents
SELECT id, incident_number, title, severity, status FROM incidents;

-- View by severity
SELECT severity, COUNT(*) FROM incidents GROUP BY severity;

-- View audit trail
SELECT action, actor, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 10;

-- View RCA reports
SELECT * FROM rca_reports ORDER BY created_at DESC;

EOF
```

---

## 🎯 Step 9: Complete Workflow Test

### Run this complete flow:

```bash
#!/bin/bash
set -e

echo "🚀 Starting Complete AIOps Workflow Test"

# 1. Create incident
echo "1️⃣  Creating incident..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Complete Workflow Test",
    "description": "End-to-end test",
    "severity": "P2_HIGH",
    "affected_services": ["api"],
    "affected_components": ["service"],
    "environment": "test",
    "detection_source": "e2e_test",
    "confidence_score": 0.88
  }')

INCIDENT_ID=$(echo $RESPONSE | jq -r '.id')
echo "✅ Incident created: $INCIDENT_ID"

# 2. Get incident
echo "2️⃣  Retrieving incident..."
curl -s http://localhost:8000/api/v1/incidents/$INCIDENT_ID | jq '.title, .severity, .status'
echo "✅ Incident retrieved"

# 3. Run RCA
echo "3️⃣  Running RCA..."
curl -s -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/rca | jq '.status, .rca_report.root_cause'
echo "✅ RCA completed"

# 4. Generate remediation
echo "4️⃣  Generating remediation..."
curl -s -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/remediation | jq '.status, .playbook | {actions: (.actions | length), duration: .estimated_total_duration_seconds}'
echo "✅ Remediation generated"

# 5. Get metrics
echo "5️⃣  Retrieving metrics..."
curl -s http://localhost:8000/api/v1/metrics | jq '.total_incidents'
echo "✅ Metrics retrieved"

echo "🎉 Complete workflow test successful!"
```

Save as `workflow_test.sh` and run:
```bash
chmod +x workflow_test.sh
./workflow_test.sh
```

---

## 📈 Step 10: Performance Benchmarking

### Run performance tests
```bash
python -c "
import requests
import time

api_url = 'http://localhost:8000'
iterations = 100

# Test API latency
times = []
for i in range(iterations):
    start = time.time()
    requests.get(f'{api_url}/health')
    times.append((time.time() - start) * 1000)

avg_ms = sum(times) / len(times)
min_ms = min(times)
max_ms = max(times)

print(f'API Latency:')
print(f'  Average: {avg_ms:.2f}ms')
print(f'  Min: {min_ms:.2f}ms')
print(f'  Max: {max_ms:.2f}ms')
print(f'  P95: {sorted(times)[int(len(times)*0.95)]:.2f}ms')
print(f'  P99: {sorted(times)[int(len(times)*0.99)]:.2f}ms')
"
```

---

## 🧹 Step 11: Cleanup

### Stop services
```bash
docker-compose down
```

### Remove volumes (reset database)
```bash
docker-compose down -v
```

### Remove everything
```bash
docker-compose down -v --remove-orphans
docker image prune -f
```

---

## 📝 Expected Test Results

All tests should pass with output like:

```
✅ PASS: health_check
✅ PASS: connector_health
✅ PASS: metrics_endpoint
✅ PASS: create_incident
✅ PASS: get_incident
✅ PASS: trigger_detection
✅ PASS: run_rca
✅ PASS: generate_remediation
✅ PASS: severity_classification
✅ PASS: database_connectivity
✅ PASS: redis_caching
✅ PASS: audit_logging
✅ PASS: performance

Total: 13/13 tests passed
```

---

## 🎓 What Each Service Does

| Service | Port | Purpose | Status Check |
|---------|------|---------|--------------|
| **PostgreSQL** | 5432 | Incident storage | `docker exec aiops_postgres psql -U aiops -d aiops_db -c "SELECT 1;"` |
| **Redis** | 6379 | Caching layer | `docker exec aiops_redis redis-cli ping` |
| **Milvus** | 19530 | Vector search | `curl http://localhost:19530/healthz` |
| **Prometheus** | 9090 | Metrics | `curl http://localhost:9090/-/healthy` |
| **Jaeger** | 16686 | Tracing | `curl http://localhost:16686/` |
| **Backend (FastAPI)** | 8000 | API server | `curl http://localhost:8000/health` |
| **Frontend (React)** | 5173 | UI | `curl http://localhost:5173` |

---

## 🆘 Getting Help

### Check logs
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs backend
docker-compose logs frontend
docker-compose logs postgres
```

### Check configuration
```bash
# View current env vars
docker-compose config

# Check what's running
docker ps
docker ps -a
```

### Reset everything
```bash
docker-compose down -v
docker-compose up -d
python tests/e2e_test.py
```

---

## ✨ Next Steps

After successful local testing:

1. **Deploy to Kubernetes**: See `infrastructure/kubernetes/deployment.yaml`
2. **Configure real connectors**: Add Splunk, Datadog, Prometheus credentials
3. **Enable Claude LLM**: Add `ANTHROPIC_API_KEY` to use RCA
4. **Set up CI/CD**: Push to GitHub and watch `.github/workflows/deploy.yml`
5. **Monitor in production**: Check Prometheus + Jaeger dashboards

---

**Happy testing! 🚀**
