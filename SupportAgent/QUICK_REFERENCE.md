# AIOps Platform - Quick Reference Guide

## Starting Services

### Local Development
```bash
# Start all services (PostgreSQL, Redis, Milvus, Prometheus, Jaeger, Backend, Frontend)
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop all services
docker-compose down
```

### Production (Kubernetes)
```bash
# Deploy to K8s cluster
kubectl apply -f infrastructure/kubernetes/deployment.yaml

# Check pod status
kubectl get pods -n aiops

# Port forwarding for testing
kubectl port-forward svc/aiops-backend-service 8000:8000 -n aiops
```

---

## Common API Calls

### Trigger Incident Detection
```bash
curl -X POST http://localhost:8000/api/v1/incidents/detect \
  -H "Content-Type: application/json" \
  -d '{"check_logs": true, "check_metrics": true, "lookback_hours": 1}'
```

### Create Incident Manually
```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Database Connection Pool Exhausted",
    "description": "PostgreSQL connection pool at 95% utilization",
    "severity": "P2_HIGH",
    "affected_services": ["api", "database"],
    "affected_components": ["postgresql", "connection_pool"],
    "environment": "production",
    "detection_source": "prometheus",
    "confidence_score": 0.92,
    "business_impact": "Payment processing delayed"
  }'
```

### Get Incident Details
```bash
curl http://localhost:8000/api/v1/incidents/{incident_id} | jq
```

### Trigger RCA
```bash
curl -X POST http://localhost:8000/api/v1/incidents/{incident_id}/rca
```

### Generate Remediation Playbook
```bash
curl -X POST http://localhost:8000/api/v1/incidents/{incident_id}/remediation
```

### Approve Remediation
```bash
curl -X POST http://localhost:8000/api/v1/remediation/{action_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved_by": "john.engineer@company.com",
    "approval_comment": "Looks good, increasing pool to 200"
  }'
```

### Check Platform Health
```bash
curl http://localhost:8000/health | jq

curl http://localhost:8000/api/v1/connectors/health | jq
```

### Get Metrics
```bash
curl http://localhost:8000/api/v1/metrics | jq
```

---

## Database Queries

### Connect to PostgreSQL
```bash
docker exec -it aiops_postgres psql -U aiops -d aiops_db
```

### View Recent Incidents
```sql
SELECT id, incident_number, title, severity, status, confidence_score, detected_at
FROM incidents
ORDER BY detected_at DESC
LIMIT 10;
```

### View Incident Details
```sql
SELECT * FROM incidents WHERE id = 'incident_id';
SELECT * FROM rca_reports WHERE incident_id = 'incident_id';
SELECT * FROM remediation_actions WHERE incident_id = 'incident_id';
SELECT * FROM evidence WHERE incident_id = 'incident_id';
```

### View Audit Trail
```sql
SELECT * FROM audit_logs
WHERE incident_id = 'incident_id'
ORDER BY created_at DESC;
```

### Get P1 Critical Incidents (Last 24h)
```sql
SELECT incident_number, title, detected_at, status
FROM incidents
WHERE severity = 'P1_CRITICAL'
  AND detected_at > NOW() - INTERVAL '24 hours'
ORDER BY detected_at DESC;
```

### Get Statistics
```sql
SELECT
  severity,
  COUNT(*) as count,
  AVG(EXTRACT(EPOCH FROM (resolved_at - detected_at)) / 60) as avg_mttr_minutes
FROM incidents
WHERE resolved_at IS NOT NULL
GROUP BY severity;
```

---

## Redis Operations

### Connect to Redis
```bash
docker exec -it aiops_redis redis-cli
```

### View Cache Keys
```bash
keys *
```

### Clear Cache
```bash
FLUSHALL
```

### Get Cache Entry
```bash
GET prompt:{hash}
GET embed:{hash}
```

---

## Milvus Vector Search

### Connect to Milvus
```bash
python -c "
from pymilvus import connections
connections.connect(host='localhost', port=19530)

# List collections
from pymilvus import list_collections
print(list_collections())
"
```

### Search Similar Incidents
```python
from pymilvus import Collection
from app.connectors.milvus import MilvusClient

client = MilvusClient()
similar = client.search_similar_incidents(
    incident_description="Database connection pool exhaustion",
    top_k=5
)
```

---

## Monitoring & Logs

### View Backend Logs
```bash
docker logs -f aiops_backend

# Filter by severity
docker logs aiops_backend | grep ERROR
docker logs aiops_backend | grep "RCA completed"
```

### View Prometheus Metrics
```
http://localhost:9090

# Example queries:
- aiops_incidents_total
- aiops_detection_accuracy
- aiops_mttd_seconds
- aiops_mttr_seconds
```

### View Jaeger Traces
```
http://localhost:16686

# Search by service: aiops-backend
# Search by operation: detect_incidents, run_rca
```

---

## ML Model Training & Deployment

### Train Isolation Forest
```bash
python -c "
from app.ml.anomaly_detection import IsolationForestAnomalyDetector
import numpy as np

detector = IsolationForestAnomalyDetector()
X = np.random.randn(1000, 10)
detector.train(X, feature_names=['cpu', 'memory', ...])
detector.save('./models/isolation_forest.pkl')
print('Model trained and saved')
"
```

### Train LSTM
```bash
python -c "
from app.ml.anomaly_detection import LSTMAnomalyDetector
import numpy as np

lstm = LSTMAnomalyDetector(lookback_window=24)
X = np.random.randn(500, 24)
lstm.train(X, epochs=50)
lstm.save('./models/lstm')
print('LSTM trained and saved')
"
```

### Load & Use Models
```bash
python -c "
from app.ml.anomaly_detection import IsolationForestAnomalyDetector
import numpy as np

detector = IsolationForestAnomalyDetector.load('./models/isolation_forest.pkl')
X_new = np.random.randn(100, 10)
predictions, scores = detector.predict(X_new)
print(f'Anomalies found: {(predictions == -1).sum()}')
"
```

---

## Deployment Operations

### AWS EKS
```bash
# Deploy
cd infrastructure/terraform/aws
terraform apply -var-file=prod.tfvars

# Get kubeconfig
aws eks update-kubeconfig --region us-east-1 --name aiops-cluster

# Scale nodes
aws autoscaling set-desired-capacity \
  --auto-scaling-group-name <asg-name> \
  --desired-capacity 5
```

### GCP GKE
```bash
# Deploy
cd infrastructure/terraform/gcp
terraform apply -var-file=prod.tfvars

# Get kubeconfig
gcloud container clusters get-credentials aiops-cluster \
  --region us-central1 \
  --project my-project

# Scale cluster
gcloud container clusters update aiops-cluster \
  --num-nodes 5 \
  --region us-central1
```

### Azure AKS
```bash
# Deploy
cd infrastructure/terraform/azure
terraform apply -var-file=prod.tfvars

# Get kubeconfig
az aks get-credentials \
  --resource-group aiops-rg \
  --name aiops-cluster

# Scale cluster
az aks scale \
  --resource-group aiops-rg \
  --name aiops-cluster \
  --node-count 5
```

---

## Troubleshooting Commands

### Check Service Health
```bash
# Backend
curl http://localhost:8000/health

# Database
docker exec aiops_postgres pg_isready

# Redis
docker exec aiops_redis redis-cli ping

# Milvus
curl http://localhost:19530/healthz

# Prometheus
curl http://localhost:9090/-/healthy
```

### Check Logs for Errors
```bash
# Recent errors in backend
docker logs aiops_backend 2>&1 | grep -i error | tail -20

# Check database connection errors
docker logs aiops_backend 2>&1 | grep -i "database\|connection"

# Check LLM errors
docker logs aiops_backend 2>&1 | grep -i "claude\|anthropic"
```

### Restart Services
```bash
# Restart backend only
docker-compose restart backend

# Restart entire stack
docker-compose restart

# Full rebuild
docker-compose down
docker-compose up -d --build
```

### Check Resource Usage
```bash
docker stats

# Or for K8s
kubectl top nodes -n aiops
kubectl top pods -n aiops
```

---

## Configuration Changes

### Update Environment Variables
```bash
# Edit .env file
nano .env

# Restart backend to pick up changes
docker-compose restart backend

# Or for K8s:
kubectl set env deployment/aiops-backend \
  -n aiops \
  LOG_LEVEL=DEBUG
```

### Update Database Connection
```bash
# For local development
DATABASE_URL=postgresql+asyncpg://aiops:aiops@postgres:5432/aiops_db

# For production (RDS)
DATABASE_URL=postgresql+asyncpg://aiops:pwd@aiops-db.xyz.us-east-1.rds.amazonaws.com:5432/aiops_db
```

### Update LLM Model
```bash
# In .env
LLM_MODEL=claude-3-opus-20240229  # Upgrade to Opus for better quality
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
```

---

## Useful Shortcuts

### View Real-time Incident Feed
```bash
watch -n 5 'curl -s http://localhost:8000/api/v1/incidents | jq ".[:5]"'
```

### Monitor Detection Accuracy
```bash
python -c "
import requests
import time

while True:
    metrics = requests.get('http://localhost:8000/api/v1/metrics').json()
    print(f\"Accuracy: {metrics['detection_accuracy']:.1%}\")
    time.sleep(10)
"
```

### Check Model Performance
```bash
python -c "
from app.ml.anomaly_detection import IsolationForestAnomalyDetector
detector = IsolationForestAnomalyDetector.load('./models/isolation_forest.pkl')
# Check model metadata
"
```

---

## Emergency Operations

### Kill Runaway Process
```bash
# Find process
docker ps | grep aiops

# Kill specific container
docker stop aiops_backend

# Or K8s pod
kubectl delete pod <pod-name> -n aiops
```

### Database Backup
```bash
docker exec aiops_postgres pg_dump -U aiops aiops_db > backup.sql
```

### Database Restore
```bash
docker exec -i aiops_postgres psql -U aiops aiops_db < backup.sql
```

### Rollback Deployment
```bash
kubectl rollout undo deployment/aiops-backend -n aiops
kubectl rollout undo deployment/aiops-frontend -n aiops
```

---

## Quick Links

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686
- **Milvus**: localhost:19530
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

---

## Support Resources

- **Docs**: See `README.md` and `IMPLEMENTATION_GUIDE.md`
- **Issues**: Check GitHub issues
- **Slack**: #aiops-platform channel
- **On-call**: See PagerDuty rotation
