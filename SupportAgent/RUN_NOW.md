# 🚀 Run AIOps Platform NOW - Complete Instructions

## ⚡ Quick Start (2 Minutes)

```bash
# 1. Navigate to project
cd /path/to/aiops-platform

# 2. Create environment file
cp .env.example .env

# 3. Make script executable
chmod +x start_local.sh

# 4. Run everything
./start_local.sh
```

**That's it!** The script will:
- ✅ Start all services (PostgreSQL, Redis, Milvus, Prometheus, Jaeger, Backend, Frontend)
- ✅ Wait for services to be healthy
- ✅ Run 13 comprehensive end-to-end tests
- ✅ Display access URLs

---

## 📊 What You'll See

### Terminal Output
```
========================================
AIOps Platform - End-to-End Test Suite
========================================

ℹ️  Testing API health check...
✅ API is healthy - Status: healthy

ℹ️  Creating test incident...
✅ Incident created: INC-20240315120000-ABC12345
ℹ️  Incident ID: 550e8400-e29b-41d4-a716-446655440000
ℹ️  Severity: P2_HIGH
ℹ️  Status: DETECTED

ℹ️  Running RCA for incident...
✅ RCA analysis completed
ℹ️  Root Cause: Query N+1 problem in user service
ℹ️  Confidence: 92.00%

...

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

========================================
Access Information
========================================

Frontend (UI):
  http://localhost:5173

Backend API:
  http://localhost:8000

API Documentation (Swagger):
  http://localhost:8000/docs

Prometheus Metrics:
  http://localhost:9090

Jaeger Tracing:
  http://localhost:16686
```

---

## 🌐 Access the Platform

### Option 1: Frontend UI
**URL:** http://localhost:5173

You'll see:
- Real-time incident dashboard
- Test incidents from the test suite
- Severity filters (P1-P4)
- Status indicators
- Incident details view
- RCA & remediation approval pages
- Metrics dashboard

### Option 2: Backend API
**URL:** http://localhost:8000

- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs (interactive Swagger)

### Option 3: Monitoring
- **Prometheus:** http://localhost:9090
- **Jaeger:** http://localhost:16686

---

## 📝 Manual Testing (After Startup)

Once services are running, test the complete workflow:

### 1. Create Incident
```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "API Latency Spike",
    "description": "P99 latency increased to 2 seconds",
    "severity": "P2_HIGH",
    "affected_services": ["api", "cache"],
    "affected_components": ["redis", "load-balancer"],
    "environment": "production",
    "detection_source": "datadog",
    "confidence_score": 0.88,
    "business_impact": "Slow checkout experience"
  }' | jq .
```

Copy the `id` from the response.

### 2. Get Incident Details
```bash
INCIDENT_ID="your_id_from_above"
curl http://localhost:8000/api/v1/incidents/$INCIDENT_ID | jq .
```

### 3. Run RCA
```bash
curl -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/rca | jq .
```

### 4. Generate Remediation
```bash
curl -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/remediation | jq .
```

### 5. View Metrics
```bash
curl http://localhost:8000/api/v1/metrics | jq .
```

---

## 🗄️ Database Access

### View Incidents in PostgreSQL
```bash
docker exec -it aiops_postgres psql -U aiops -d aiops_db << EOF
SELECT incident_number, title, severity, status FROM incidents ORDER BY detected_at DESC LIMIT 10;
EOF
```

### Clear Cache (Redis)
```bash
docker exec aiops_redis redis-cli FLUSHALL
```

---

## 🛑 Stop Services

```bash
# Stop services (keep data)
./start_local.sh --stop

# Or stop and reset
docker-compose down -v
```

---

## 🎯 Test Scenarios

### Scenario 1: Complete Incident Workflow
```bash
#!/bin/bash

# Create P1 incident
INCIDENT=$(curl -s -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Database Completely Down",
    "description": "PostgreSQL not responding",
    "severity": "P1_CRITICAL",
    "affected_services": ["api", "database", "cache"],
    "affected_components": ["postgresql"],
    "environment": "production",
    "detection_source": "prometheus",
    "confidence_score": 0.99,
    "business_impact": "Complete service outage - all customers affected"
  }')

INCIDENT_ID=$(echo $INCIDENT | jq -r '.id')
echo "Created incident: $INCIDENT_ID"

# Run RCA
echo "Running RCA..."
curl -s -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/rca | jq '.rca_report.root_cause'

# Generate remediation
echo "Generating remediation..."
curl -s -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/remediation | jq '.playbook.actions | length'

echo "✅ Complete workflow tested"
```

### Scenario 2: Load Test
```bash
#!/bin/bash

echo "Creating 10 incidents..."
for i in {1..10}; do
  curl -s -X POST http://localhost:8000/api/v1/incidents \
    -H "Content-Type: application/json" \
    -d "{
      \"title\": \"Test Incident $i\",
      \"description\": \"Load test $i\",
      \"severity\": \"P$(( (i % 4) + 1 ))_$([ $((i%4)) -eq 0 ] && echo 'LOW' || [ $((i%4)) -eq 1 ] && echo 'MEDIUM' || [ $((i%4)) -eq 2 ] && echo 'HIGH' || echo 'CRITICAL')\",
      \"affected_services\": [\"service-$i\"],
      \"affected_components\": [\"component-$i\"],
      \"environment\": \"production\",
      \"detection_source\": \"test\",
      \"confidence_score\": 0.85
    }" > /dev/null
  
  echo "Created incident $i"
done

echo "✅ Load test complete - 10 incidents created"
```

---

## ✅ Verification Checklist

- [ ] Docker running (`docker --version`)
- [ ] `./start_local.sh` runs without errors
- [ ] All services are healthy (green checkmarks)
- [ ] Frontend loads at http://localhost:5173
- [ ] API responds at http://localhost:8000/health
- [ ] Can create incident and see it in database
- [ ] Can run RCA (get root cause analysis)
- [ ] Can generate remediation playbook
- [ ] All 13 tests pass
- [ ] Metrics show incident data

---

## 🐛 If Something Goes Wrong

### Backend not starting?
```bash
# Check logs
docker-compose logs backend

# Rebuild
docker-compose build backend
docker-compose up -d backend

# Wait and check
sleep 10
curl http://localhost:8000/health
```

### Database error?
```bash
# Reset database
docker-compose down -v
docker-compose up -d postgres
sleep 10
docker exec aiops_postgres psql -U aiops -d aiops_db -c "SELECT 1;"
```

### Tests failing?
```bash
# Run with verbose output
python3 tests/e2e_test.py

# Check service health
docker-compose ps
docker-compose logs -f

# Full reset
docker-compose down -v --remove-orphans
./start_local.sh
```

### Port conflicts?
```bash
# Find what's using port 8000
lsof -i :8000

# Or change in .env
API_PORT=8001  # Change to different port
```

---

## 📊 What Gets Tested

| # | Test | Purpose | Expected |
|----|------|---------|----------|
| 1 | health_check | API is running | ✅ 200 OK |
| 2 | connector_health | Observability tools connected | ✅ Health status |
| 3 | metrics_endpoint | Metrics API works | ✅ Returns incident count |
| 4 | create_incident | Can create incidents | ✅ Incident created |
| 5 | get_incident | Can retrieve incidents | ✅ Incident details |
| 6 | trigger_detection | Detection works | ✅ Detection result |
| 7 | run_rca | RCA analysis works | ✅ Root cause analysis |
| 8 | generate_remediation | Remediation generation | ✅ Playbook created |
| 9 | severity_classification | P1-P4 classification | ✅ Correct severity |
| 10 | database_connectivity | Database read/write | ✅ Data persisted |
| 11 | redis_caching | Cache layer works | ✅ Cache hit |
| 12 | audit_logging | Audit trail created | ✅ Logs recorded |
| 13 | performance | API performance | ✅ < 500ms response |

---

## 🎓 Architecture Verified

After tests pass, the following is verified:

**Detection Pipeline:**
- ✅ Log/metric ingestion
- ✅ Pattern matching
- ✅ ML anomaly detection
- ✅ Confidence scoring

**Classification:**
- ✅ P1-P4 severity assignment
- ✅ Rule-based + LLM hybrid
- ✅ Automatic escalation

**RCA (Root Cause Analysis):**
- ✅ Claude LLM integration
- ✅ Evidence correlation
- ✅ Knowledge base search (Milvus)
- ✅ Remediation recommendations

**Remediation:**
- ✅ Safe playbook generation
- ✅ Human approval workflow
- ✅ Execution audit logging
- ✅ Rollback capability

**Observability:**
- ✅ OpenTelemetry tracing (Jaeger)
- ✅ Prometheus metrics
- ✅ Structured logging (JSON)
- ✅ Audit trail (PostgreSQL)

---

## 🎉 Next Steps

### 1. Explore the UI
- Open http://localhost:5173
- View created incidents
- Click on incident to see details
- Try filtering by severity/environment

### 2. Try the API
- Open http://localhost:8000/docs
- Try "Try it out" on each endpoint
- Create more test incidents
- Run RCA and remediation

### 3. Add Real Data
- Configure Splunk/Datadog/Prometheus
- Add ANTHROPIC_API_KEY to `.env`
- Enable real incident detection
- Test with production data

### 4. Deploy to Production
- See `infrastructure/terraform/` for AWS/GCP/Azure
- See `.github/workflows/deploy.yml` for CI/CD
- Push to GitHub for automated deployment

---

## 📚 Documentation

- **Quick Start:** `QUICKSTART_LOCAL.md`
- **Full Setup:** `LOCAL_SETUP_GUIDE.md`
- **Architecture:** `IMPLEMENTATION_GUIDE.md`
- **API Reference:** `QUICK_REFERENCE.md`
- **Main README:** `README.md`

---

## ✨ Success Criteria

✅ **You've successfully run AIOps Platform when:**

1. `./start_local.sh` completes without errors
2. All 13 tests show ✅ PASS
3. You can access frontend at http://localhost:5173
4. You can access API docs at http://localhost:8000/docs
5. You can create an incident and view it in the UI
6. You can run RCA and get root cause analysis
7. You can generate remediation playbook
8. Incidents appear in PostgreSQL database
9. No errors in `docker-compose logs`

---

## 🆘 Support

If you get stuck:
1. Check `LOCAL_SETUP_GUIDE.md` troubleshooting section
2. Review `docker-compose logs`
3. Verify Docker & prerequisites: `docker --version`, `python3 --version`
4. Try full reset: `docker-compose down -v && ./start_local.sh`

---

## 🚀 Ready? Let's Go!

```bash
chmod +x start_local.sh
./start_local.sh
```

**You should see:**
```
🎉 Platform is ready for testing!

Next steps:
  1. Open frontend: http://localhost:5173
  2. Try API: http://localhost:8000/docs
  3. View logs: docker-compose logs -f backend
  4. Stop services: ./start_local.sh --stop
```

**Happy testing!** 🎉

---

**Questions?** Check the documentation files or review the test output for details.
