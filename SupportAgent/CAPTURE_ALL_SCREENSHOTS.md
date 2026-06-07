# 🎬 AIOps Platform - Screenshot Capture Walkthrough

**Total Screenshots:** 25  
**Estimated Time:** 30-45 minutes  
**Difficulty:** Easy - just follow the steps!

---

## ✅ Pre-Flight Checklist

Before starting, ensure:
- [ ] Frontend running at http://localhost:5173
- [ ] Backend running at http://localhost:8000
- [ ] Both services healthy
- [ ] `docs/screenshots/` folder created

**Quick check:**
```bash
mkdir -p docs/screenshots
curl http://localhost:8000/health
curl -I http://localhost:5173
```

---

## 📸 Screenshot Capture Instructions

### **STEP 1: Create Test Data (2 minutes)**

Open terminal and run:

```bash
# Create incident
INCIDENT=$(curl -s -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Database Connection Pool Exhaustion",
    "description": "PostgreSQL connection pool at 95% utilization causing API timeouts",
    "severity": "P2_HIGH",
    "affected_services": ["api-server", "database", "cache"],
    "affected_components": ["postgresql", "connection_pool"],
    "environment": "production",
    "detection_source": "prometheus",
    "confidence_score": 0.92,
    "business_impact": "Payment processing delayed for 500+ customers",
    "customer_impact": 500
  }')

# Save the incident ID
INCIDENT_ID=$(echo $INCIDENT | jq -r '.id')
echo "Created incident: $INCIDENT_ID"

# Run RCA
curl -s -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/rca > /dev/null

# Generate remediation
curl -s -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/remediation > /dev/null

echo "Test data ready! Incident ID: $INCIDENT_ID"
```

**Save the INCIDENT_ID** - you'll need it for several screenshots.

---

## 🖼️ Screenshot Workflow

### **GROUP 1: Dashboard Screenshots (5 minutes)**

#### **Screenshot #1: Dashboard Full Page**
**How to capture:**
1. Open: http://localhost:5173
2. Wait 3 seconds for data to load
3. Take screenshot of entire page
4. **Save as:** `docs/screenshots/01_dashboard_full_page.png`

**What should be visible:**
- Navigation bar (AIOps Platform)
- 4 KPI cards at top
- Filter bar
- Incident table with multiple rows
- Your created incident in the table

**Mac:** Cmd + Shift + 4, then Space, click window  
**Windows:** Win + Shift + S  
**Linux:** Print Screen

---

#### **Screenshot #2: Dashboard KPI Cards**
**How to capture:**
1. Same page: http://localhost:5173
2. Scroll to top
3. Focus on the 4 cards:
   - Total Incidents
   - P1 Critical
   - Analyzing
   - Resolved
4. Take screenshot of just these 4 cards
5. **Save as:** `docs/screenshots/02_dashboard_kpi_cards.png`

---

#### **Screenshot #3: Dashboard Filters**
**How to capture:**
1. Same page: http://localhost:5173
2. Locate filter bar below KPI cards
3. Click "Severity" dropdown
4. Capture with dropdown open showing P1, P2, P3, P4 options
5. **Save as:** `docs/screenshots/03_dashboard_filters.png`

---

#### **Screenshot #4: Incidents Table Header**
**How to capture:**
1. Same page: http://localhost:5173
2. Scroll down to incident table
3. Capture the header row with columns:
   - Incident
   - Severity
   - Status
   - Services
   - Confidence
   - Detected
4. **Save as:** `docs/screenshots/04_incidents_table_header.png`

---

#### **Screenshot #5: Incidents Table (Multiple Rows)**
**How to capture:**
1. Same page: http://localhost:5173
2. Scroll to incident table
3. Capture 5-10 incident rows
4. Show different colors (P1/P2/P3/P4)
5. Show different statuses
6. **Save as:** `docs/screenshots/05_incidents_table_full.png`

---

### **GROUP 2: Incident Details Screenshots (8 minutes)**

#### **Screenshot #6: Incident Details - Header**
**How to capture:**
1. On dashboard, click your created incident
2. Go to: http://localhost:5173/incidents/{INCIDENT_ID}
3. Capture the header section showing:
   - Title: "Database Connection Pool Exhaustion"
   - Incident #: INC-...
   - Severity: P2_HIGH (orange badge)
   - Status
4. **Save as:** `docs/screenshots/06_incident_details_header.png`

---

#### **Screenshot #7: Incident Details - Info Grid**
**How to capture:**
1. Same page, scroll down
2. Capture the information grid showing:
   - Status: DETECTED
   - Severity: P2_HIGH
   - Affected Services: [api-server, database, cache]
   - Affected Components: [postgresql, connection_pool]
   - Environment: production
   - Confidence Score: 92%
   - Business Impact: [description]
3. **Save as:** `docs/screenshots/07_incident_details_info_grid.png`

---

#### **Screenshot #8: Incident Details - Overview Tab**
**How to capture:**
1. Same page
2. Scroll down to tabs (Overview, RCA, Evidence)
3. Click "Overview" tab
4. Capture the content showing:
   - Full description
   - Affected services list
   - Affected components list
5. **Save as:** `docs/screenshots/08_incident_details_overview_tab.png`

---

#### **Screenshot #9: Incident Details - RCA Tab**
**How to capture:**
1. Same page
2. Click "RCA" tab
3. Wait for RCA data to load
4. Capture showing:
   - Root Cause analysis
   - Affected Systems
   - Contributing Factors
   - Timeline
   - Recommended Fix
5. **Save as:** `docs/screenshots/09_incident_details_rca_tab.png`

**Note:** If RCA shows "Running...", wait 10 seconds and refresh.

---

#### **Screenshot #10: Incident Details - Evidence Tab**
**How to capture:**
1. Same page
2. Click "Evidence" tab
3. Capture showing:
   - Evidence sections
   - Log entries
   - Metric data
   - Relevance scores
4. **Save as:** `docs/screenshots/10_incident_details_evidence_tab.png`

---

#### **Screenshot #11: Incident Details - Action Buttons**
**How to capture:**
1. Same page
2. Scroll to top of incident details
3. Locate action buttons:
   - "Run RCA" (blue)
   - "Generate Remediation" (green)
   - Other action buttons
4. Capture clearly
5. **Save as:** `docs/screenshots/11_incident_details_action_buttons.png`

---

### **GROUP 3: Remediation Screenshots (6 minutes)**

#### **Screenshot #12: Remediation - Header & Risk**
**How to capture:**
1. On incident details page
2. Click "Generate Remediation" button
3. Navigate to: http://localhost:5173/remediation/{INCIDENT_ID}
4. Capture top section showing:
   - Title: "Remediation Approval"
   - Risk Level: Medium
   - Estimated Duration
   - Requires Approval: Yes
5. **Save as:** `docs/screenshots/12_remediation_header_risk.png`

---

#### **Screenshot #13: Remediation - First Action**
**How to capture:**
1. Same page
2. Scroll down to "Actions" section
3. Capture the first remediation action card:
   - Action name (e.g., "Restart API Server")
   - Description
   - Risk level: Low
   - Duration: 30 seconds
   - Rollback possible: Yes
4. **Save as:** `docs/screenshots/13_remediation_actions_list_1.png`

---

#### **Screenshot #14: Remediation - Second Action**
**How to capture:**
1. Same page
2. Scroll down
3. Capture the second action card:
   - Action name (e.g., "Rollback Deployment")
   - Risk level: Medium
   - Duration: 60 seconds
   - Include implementation details/code
4. **Save as:** `docs/screenshots/14_remediation_actions_list_2.png`

---

#### **Screenshot #15: Remediation - Success Criteria**
**How to capture:**
1. Same page
2. Scroll down to "Success Criteria" section
3. Capture the checklist:
   - [ ] Connection pool utilization < 80%
   - [ ] Error rate < 0.5%
   - [ ] P99 latency < 500ms
   - [ ] No customer errors
4. **Save as:** `docs/screenshots/15_remediation_success_criteria.png`

---

#### **Screenshot #16: Remediation - Approval Form**
**How to capture:**
1. Same page
2. Scroll to bottom
3. Capture the approval section:
   - Comment textarea
   - "Approve & Execute" button (green)
   - "Reject" button (red)
4. **Save as:** `docs/screenshots/16_remediation_approval_form.png`

---

### **GROUP 4: Metrics Screenshots (5 minutes)**

#### **Screenshot #17: Metrics - KPI Cards**
**How to capture:**
1. Open: http://localhost:5173/metrics
2. Capture the top 4 KPI cards:
   - Detection Accuracy: XX%
   - Avg MTTD: XX min
   - Avg MTTR: XX min
   - Auto-Remediation Success: XX%
3. **Save as:** `docs/screenshots/17_metrics_kpi_cards.png`

---

#### **Screenshot #18: Metrics - Timeline Chart**
**How to capture:**
1. Same page
2. Scroll to first chart
3. Capture "Incidents Over Time" showing:
   - Bar chart
   - Time on X-axis
   - Count on Y-axis
   - Legend: Detected, Analyzing, Resolved
4. **Save as:** `docs/screenshots/18_metrics_timeline_chart.png`

---

#### **Screenshot #19: Metrics - MTTD vs MTTR Chart**
**How to capture:**
1. Same page
2. Scroll to second chart
3. Capture line chart showing:
   - MTTD line (blue)
   - MTTR line (orange)
   - Daily data points
   - Legend
4. **Save as:** `docs/screenshots/19_metrics_mttd_mttr_chart.png`

---

#### **Screenshot #20: Metrics - Severity Breakdown**
**How to capture:**
1. Same page
2. Scroll down
3. Capture "Incidents by Severity" section:
   - P1 Critical: XX% (Red)
   - P2 High: XX% (Orange)
   - P3 Medium: XX% (Yellow)
   - P4 Low: XX% (Blue)
4. **Save as:** `docs/screenshots/20_metrics_severity_breakdown.png`

---

### **GROUP 5: API Documentation Screenshots (4 minutes)**

#### **Screenshot #21: API Swagger UI**
**How to capture:**
1. Open: http://localhost:8000/docs
2. Wait for Swagger to load
3. Capture the full page showing:
   - "AIOps Platform" title
   - List of API endpoints
   - Tag categories (incidents, detection, etc.)
4. **Save as:** `docs/screenshots/21_api_swagger_overview.png`

---

#### **Screenshot #22: API POST Incident Endpoint**
**How to capture:**
1. Same page
2. Find "POST /api/v1/incidents"
3. Click to expand
4. Capture showing:
   - Method: POST
   - Path: /api/v1/incidents
   - Request body schema
   - Required fields
5. **Save as:** `docs/screenshots/22_api_swagger_post_incident.png`

---

#### **Screenshot #23: API Response Schema**
**How to capture:**
1. Same expanded endpoint
2. Scroll down to "Responses"
3. Capture the response section showing:
   - Status: 200
   - Response schema
   - Example JSON response
4. **Save as:** `docs/screenshots/23_api_swagger_response.png`

---

### **GROUP 6: System Status Screenshots (3 minutes)**

#### **Screenshot #24: Docker Services Status**
**How to capture:**
1. Open terminal
2. Run:
   ```bash
   docker-compose ps
   ```
3. Screenshot the output showing all services "Up"
4. **Save as:** `docs/screenshots/24_docker_services_status.png`

---

#### **Screenshot #25: API Health Check**
**How to capture:**
1. In terminal, run:
   ```bash
   curl http://localhost:8000/health | jq .
   ```
2. Screenshot the JSON response:
   ```json
   {
     "status": "healthy",
     "timestamp": "...",
     "environment": "development"
   }
   ```
3. **Save as:** `docs/screenshots/25_api_health_check.png`

---

## ✅ Verification Checklist

After capturing all 25 screenshots, run:

```bash
# Count screenshots
echo "Total screenshots: $(ls docs/screenshots/*.png 2>/dev/null | wc -l)"

# Should show: Total screenshots: 25

# List all
ls -1 docs/screenshots/

# Create summary
cat > docs/SCREENSHOTS_CAPTURED.txt << 'EOF'
✅ AIOps Platform - 25 Screenshots Captured

Dashboard (5):
☑ 01_dashboard_full_page.png
☑ 02_dashboard_kpi_cards.png
☑ 03_dashboard_filters.png
☑ 04_incidents_table_header.png
☑ 05_incidents_table_full.png

Incident Details (6):
☑ 06_incident_details_header.png
☑ 07_incident_details_info_grid.png
☑ 08_incident_details_overview_tab.png
☑ 09_incident_details_rca_tab.png
☑ 10_incident_details_evidence_tab.png
☑ 11_incident_details_action_buttons.png

Remediation (5):
☑ 12_remediation_header_risk.png
☑ 13_remediation_actions_list_1.png
☑ 14_remediation_actions_list_2.png
☑ 15_remediation_success_criteria.png
☑ 16_remediation_approval_form.png

Metrics (4):
☑ 17_metrics_kpi_cards.png
☑ 18_metrics_timeline_chart.png
☑ 19_metrics_mttd_mttr_chart.png
☑ 20_metrics_severity_breakdown.png

API Documentation (3):
☑ 21_api_swagger_overview.png
☑ 22_api_swagger_post_incident.png
☑ 23_api_swagger_response.png

System Status (2):
☑ 24_docker_services_status.png
☑ 25_api_health_check.png

Total: 25/25 ✅
Location: docs/screenshots/
EOF

cat docs/SCREENSHOTS_CAPTURED.txt
```

---

## 🎯 Timeline

**Estimated timing:**
- Group 1 (Dashboard): 5 min
- Group 2 (Incident Details): 8 min
- Group 3 (Remediation): 6 min
- Group 4 (Metrics): 5 min
- Group 5 (API): 4 min
- Group 6 (System): 3 min
- **Total: ~30-45 minutes**

---

## 🐛 Troubleshooting

### Issue: Screenshot shows blank page
**Solution:** Wait 3-5 seconds for page to load, then take screenshot

### Issue: RCA tab shows "Running..."
**Solution:** Wait 10 seconds and refresh the page (F5)

### Issue: Remediation page won't load
**Solution:** Refresh and try again, or create a new incident

### Issue: API Swagger won't expand
**Solution:** Click the endpoint name to toggle expand/collapse

---

## 📋 After Capturing All Screenshots

1. **Organize:** All 25 PNGs should be in `docs/screenshots/`

2. **Create index:**
   ```bash
   cat > docs/SCREENSHOT_INDEX.md << 'EOF'
   # AIOps Platform - Screenshot Gallery
   
   ## Dashboard
   ![Dashboard](screenshots/01_dashboard_full_page.png)
   
   ## Incident Details
   ![Incident Details](screenshots/06_incident_details_header.png)
   
   [... continue for all groups ...]
   EOF
   ```

3. **Generate documentation:**
   ```bash
   cat > docs/UI_REFERENCE.md << 'EOF'
   # AIOps Platform - UI Reference Guide
   
   Complete visual guide with 25 screenshots...
   EOF
   ```

---

## 🎉 Next Steps

Once all 25 screenshots are captured:

1. ✅ Screenshots stored in `docs/screenshots/`
2. ✅ Update README.md with screenshot references
3. ✅ Create UI documentation
4. ✅ Share with team

---

**Start capturing now and let me know when done!** 🎬
