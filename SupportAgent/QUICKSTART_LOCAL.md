# 🚀 AIOps Platform - Quickstart (5 Minutes)

## One-Command Setup

```bash
chmod +x start_local.sh
./start_local.sh
```

That's it! The script will:
1. ✅ Check prerequisites (Docker, Python)
2. ✅ Create `.env` file
3. ✅ Start all 7 services
4. ✅ Wait for services to be healthy
5. ✅ Run 13 end-to-end tests
6. ✅ Show access URLs

---

## 📋 What Gets Started

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | http://localhost:5173 | React UI for incident dashboard |
| **Backend API** | http://localhost:8000 | FastAPI REST endpoints |
| **API Docs** | http://localhost:8000/docs | Interactive Swagger UI |
| **PostgreSQL** | localhost:5432 | Incident database |
| **Redis** | localhost:6379 | Cache layer |
| **Milvus** | localhost:19530 | Vector search (KB articles) |
| **Prometheus** | http://localhost:9090 | Metrics & monitoring |
| **Jaeger** | http://localhost:16686 | Distributed tracing |

---

## 🎯 Complete Workflow (3 Minutes)

Once services are running, try this complete flow:

### 1. Create an Incident
```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Database Connection Pool Exhaustion",
    "description": "PostgreSQL at 95% connection utilization",
    "severity": "P2_HIGH",
    "affected_services": ["api", "database"],
    "affected_components": ["postgresql", "connection_pool"],
    "environment": "production",
    "detection_source": "prometheus",
    "confidence_score": 0.92,
    "business_impact": "Payment processing delayed"
  }' | jq .
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "incident_number": "INC-20240315120000-ABC12345",
  "title": "Database Connection Pool Exhaustion",
  "severity": "P2_HIGH",
  "status": "DETECTED",
  "confidence_score": 0.92,
  "created_at": "2024-03-15T12:00:00.123456"
}
```

### 2. Get Incident Details
```bash
INCIDENT_ID="550e8400-e29b-41d4-a716-446655440000"

curl http://localhost:8000/api/v1/incidents/$INCIDENT_ID | jq .
```

### 3. Run RCA (Root Cause Analysis)
```bash
curl -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/rca | jq .
```

**Response:**
```json
{
  "status": "rca_completed",
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "rca_report": {
    "root_cause": "Query N+1 problem in user service causing excess connections",
    "confidence_score": 0.92,
    "affected_systems": ["api", "database", "cache"],
    "recommended_fix": "Rollback recent deployment",
    "implementation_steps": [
      "kubectl rollout undo deployment/api",
      "Monitor connection pool",
      "Verify error rate returns to normal"
    ]
  }
}
```

### 4. Generate Remediation Playbook
```bash
curl -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/remediation | jq .
```

**Response:**
```json
{
  "status": "playbook_generated",
  "playbook": {
    "actions": [
      {
        "action_type": "scale_deployment",
        "action_name": "Temporarily increase connection pool",
        "estimated_duration_seconds": 30,
        "risk_level": "low"
      },
      {
        "action_type": "rollback_deployment",
        "action_name": "Rollback recent deployment",
        "estimated_duration_seconds": 60,
        "risk_level": "medium"
      }
    ],
    "estimated_total_duration_seconds": 120,
    "requires_approval": true,
    "success_criteria": [
      "Connection pool utilization drops below 80%",
      "Error rate returns to < 0.5%"
    ]
  }
}
```

### 5. View Platform Metrics
```bash
curl http://localhost:8000/api/v1/metrics | jq .
```

---

## 🌐 Access the UI

### Frontend Dashboard
```
Open: http://localhost:5173
```

**You'll see:**
- ✅ Real-time incident feed
- ✅ Incidents you just created
- ✅ Severity indicators (P1-P4)
- ✅ Status badges (DETECTED, ANALYZING, RESOLVED)
- ✅ Metrics dashboard with charts

### Interactive API Docs
```
Open: http://localhost:8000/docs
```

**Features:**
- ✅ Try each endpoint in your browser
- ✅ See request/response examples
- ✅ Test with your own data

---

## 📊 Database Access

### Connect to PostgreSQL
```bash
docker exec -it aiops_postgres psql -U aiops -d aiops_db
```

**Useful queries:**
```sql
-- View all incidents
SELECT id, incident_number, title, severity, status FROM incidents;

-- View by severity
SELECT severity, COUNT(*) as count FROM incidents GROUP BY severity;

-- View RCA reports
SELECT incident_id, root_cause, confidence_score FROM rca_reports;

-- View audit trail
SELECT action, actor, created_at FROM audit_logs ORDER BY created_at DESC;
```

### Redis CLI
```bash
docker exec -it aiops_redis redis-cli

# View cache keys
keys *

# Check cache size
dbsize

# Clear cache
FLUSHALL
```

---

## 🧪 Run Tests Anytime

```bash
# Full test suite
python3 tests/e2e_test.py

# Skip detailed output
python3 tests/e2e_test.py 2>/dev/null

# Test specific endpoint
curl -s http://localhost:8000/health | jq .
```

---

## 📋 Expected Test Results

When you run `./start_local.sh`, you should see:

```
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
✅ PASS: generate_remediation
✅ PASS: severity_classification
✅ PASS: database_connectivity
✅ PASS: redis_caching
✅ PASS: audit_logging
✅ PASS: performance

Total: 13/13 tests passed

🎉 All tests passed!
```

---

## 🛑 Stop Services

```bash
# Stop all services (keep data)
./start_local.sh --stop

# Or manually
docker-compose down

# Stop and reset database
docker-compose down -v
```

---

## 🐛 Troubleshooting

### Services not starting?
```bash
# Check logs
docker-compose logs backend

# Ensure ports are free
netstat -tulpn | grep 8000

# Rebuild containers
docker-compose down
docker-compose up -d --build
```

### Tests failing?
```bash
# Check API is running
curl http://localhost:8000/health

# Wait longer and retry
sleep 30
python3 tests/e2e_test.py

# Check backend logs
docker-compose logs -f backend
```

### Database connection error?
```bash
# Restart PostgreSQL
docker-compose restart postgres

# Or reset completely
docker-compose down -v
docker-compose up -d
```

---

## 🎓 Next Steps

### 1. **Configure Real API Keys**
Edit `.env` and add:
```env
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
DATADOG_API_KEY=dd_...
JIRA_API_TOKEN=ATATT_...
```

### 2. **Deploy to Kubernetes**
```bash
cd infrastructure/kubernetes
kubectl apply -f deployment.yaml
```

### 3. **Push to GitHub & CI/CD**
```bash
git add .
git commit -m "Initial AIOps platform setup"
git push
# GitHub Actions will automatically deploy!
```

### 4. **Monitor in Production**
- Prometheus: http://localhost:9090
- Jaeger: http://localhost:16686
- Logs: `docker-compose logs -f`

---

## 📚 Useful Commands

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs -f backend

# Check service health
docker-compose ps

# Execute command in container
docker exec aiops_backend python -c "import app; print(app.__version__)"

# Scale services
docker-compose up -d --scale backend=3

# Monitor resource usage
docker stats

# Clean up everything
docker-compose down -v --remove-orphans
```

---

## ✅ Verification Checklist

- [ ] `docker --version` shows Docker 20.10+
- [ ] `./start_local.sh` runs without errors
- [ ] Frontend loads at http://localhost:5173
- [ ] API responds at http://localhost:8000/health
- [ ] Can create incident via API
- [ ] Can run RCA on incident
- [ ] Can generate remediation
- [ ] All 13 tests pass
- [ ] Database has incident data
- [ ] Redis cache is working

---

## 🆘 Support

### Check Documentation
- Full setup: `LOCAL_SETUP_GUIDE.md`
- Architecture: `IMPLEMENTATION_GUIDE.md`
- API Reference: `QUICK_REFERENCE.md`
- Main README: `README.md`

### Common Issues
1. **Port already in use** → Change in `.env` (API_PORT)
2. **Docker not running** → Start Docker daemon
3. **Tests timeout** → Increase HEALTH_CHECK_RETRIES in `start_local.sh`
4. **Memory issues** → Increase Docker memory limit

---

## 🎉 Success!

If you see:
```
🎉 Platform is ready for testing!
```

You're all set! The complete AIOps platform is running locally with:
- ✅ Full incident detection & classification
- ✅ Root cause analysis (RCA) capability
- ✅ Auto-remediation playbook generation
- ✅ Human-in-the-loop approval workflow
- ✅ Enterprise observability & audit logging
- ✅ Real-time UI dashboard
- ✅ Production-grade architecture

**Happy testing!** 🚀
