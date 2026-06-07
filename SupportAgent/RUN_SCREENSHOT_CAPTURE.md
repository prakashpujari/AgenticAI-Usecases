# 📸 Automated Screenshot Capture Guide

## Quick Start (3 Steps)

This guide will automatically capture all 25 UI screenshots using Puppeteer.

---

## Step 1: Start AIOps Platform (Terminal 1)

```bash
# Navigate to project directory
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent

# Make sure services are not already running
docker-compose down

# Start all services
./start_local.sh
```

**Wait for:**
- ✅ All services to be healthy
- ✅ 13 tests to pass
- ✅ "Platform is ready for testing!" message

**You'll see:**
```
✅ PASS: health_check
✅ PASS: connector_health
✅ PASS: metrics_endpoint
...
✅ PASS: performance

Total: 13/13 tests passed
🎉 All tests passed!
```

**Expected URLs:**
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Step 2: Install Puppeteer Dependencies (Terminal 2)

```bash
# Navigate to project directory
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent

# Install Node.js dependencies (if not already done)
npm install puppeteer

# Or use yarn
yarn add puppeteer
```

**If npm install fails on Windows:**
```bash
# Try with npm ci instead
npm ci

# Or install with legacy peer deps
npm install --legacy-peer-deps
```

---

## Step 3: Run Screenshot Capture Script (Terminal 2)

```bash
# Run the capture script
node capture-screenshots.js
```

**Script will:**
1. ✅ Verify backend API is running
2. ✅ Create a test incident automatically
3. ✅ Launch browser window
4. ✅ Navigate to each page
5. ✅ Take screenshots
6. ✅ Save to `docs/screenshots/`
7. ✅ Display summary

**You'll see output like:**

```
╔════════════════════════════════════════════════════════════════╗
║     AIOps Platform - Automated Screenshot Capture             ║
║                                                                ║
║  This script will capture 25 screenshots of your UI            ║
╚════════════════════════════════════════════════════════════════╝

🔍 Verifying services...
✅ Backend API is running

📋 Setting up test data...
📝 Creating test incident...
✅ Test incident created: [UUID]

🌐 Launching browser...

📸 Capturing screenshots...

📸 Capturing: 01_dashboard_full_page
   URL: http://localhost:5173
   Description: Full dashboard view
   ✅ Saved to: docs/screenshots/01_dashboard_full_page.png

📸 Capturing: 02_dashboard_kpi_cards
   URL: http://localhost:5173
   Description: Dashboard KPI cards
   ✅ Saved to: docs/screenshots/02_dashboard_kpi_cards.png

[... continues for all 25 screenshots ...]

╔════════════════════════════════════════════════════════════════╗
║                 ✅ Capture Complete!                           ║
╚════════════════════════════════════════════════════════════════╝

📊 Summary:
   Total captured: 25
   Output directory: docs/screenshots

📋 Screenshots captured:
   Group 1: Dashboard (5)
   Group 2: Incident Details (6)
   Group 3: Remediation (5)
   Group 4: Metrics (4)
   Group 5: API Documentation (3)
```

---

## 📁 What Gets Captured

### Group 1: Dashboard (5)
- `01_dashboard_full_page.png` - Full dashboard view
- `02_dashboard_kpi_cards.png` - KPI cards
- `03_dashboard_filters.png` - Filter bar
- `04_incidents_table_header.png` - Table header
- `05_incidents_table_full.png` - Full table with data

### Group 2: Incident Details (6)
- `06_incident_details_header.png` - Incident header
- `07_incident_details_info_grid.png` - Info grid
- `08_incident_details_overview_tab.png` - Overview tab
- `09_incident_details_rca_tab.png` - RCA tab
- `10_incident_details_evidence_tab.png` - Evidence tab
- `11_incident_details_action_buttons.png` - Action buttons

### Group 3: Remediation (5)
- `12_remediation_header_risk.png` - Header & risk
- `13_remediation_actions_list_1.png` - First action
- `14_remediation_actions_list_2.png` - Multiple actions
- `15_remediation_success_criteria.png` - Success criteria
- `16_remediation_approval_form.png` - Approval form

### Group 4: Metrics (4)
- `17_metrics_kpi_cards.png` - KPI cards
- `18_metrics_timeline_chart.png` - Timeline chart
- `19_metrics_mttd_mttr_chart.png` - MTTD vs MTTR
- `20_metrics_severity_breakdown.png` - Severity breakdown

### Group 5: API Documentation (3)
- `21_api_swagger_overview.png` - Swagger overview
- `22_api_swagger_post_incident.png` - POST endpoint
- `23_api_swagger_response.png` - Response schema

---

## ✅ Verify Screenshots Captured

After the script completes:

```bash
# Count screenshots
ls -1 docs/screenshots/*.png | wc -l

# Should show: 25

# List all
ls -1 docs/screenshots/

# List with details
ls -lh docs/screenshots/
```

**Expected output:**
```
01_dashboard_full_page.png
02_dashboard_kpi_cards.png
03_dashboard_filters.png
...
23_api_swagger_response.png

Total: 25 files
```

---

## 🔧 Troubleshooting

### Issue: "Backend API not available"
**Solution:**
```bash
# Check if backend is running
curl http://localhost:8000/health

# If not running, in Terminal 1:
./start_local.sh

# Wait for "Platform is ready for testing!"
```

### Issue: "Could not find Chrome/Chromium"
**Solution:**
```bash
# Puppeteer downloads Chrome automatically
# But if it fails, reinstall:
npm uninstall puppeteer
npm install puppeteer

# Or force Chrome download:
npm rebuild puppeteer
```

### Issue: "Port 5173 or 8000 already in use"
**Solution:**
```bash
# Kill existing process on port 5173
lsof -ti :5173 | xargs kill -9

# Or change port in .env
API_PORT=8001
FRONTEND_PORT=5174

# Then restart
docker-compose down
./start_local.sh
```

### Issue: "Screenshot shows blank page"
**Solution:**
```bash
# The script waits 2-3 seconds for pages to load
# If pages are slow, manually increase wait time in capture-screenshots.js:

// Change this line in captureScreenshot function:
await page.waitForTimeout(config.wait || 2000);  // Increase to 5000

# Then run again:
node capture-screenshots.js
```

### Issue: "Browser won't launch"
**Solution:**
```bash
# Run in headless mode (no visual window)
# Edit capture-screenshots.js, change line:
headless: false  // Change to: headless: true

# This uses less resources and works better on Windows
```

---

## 📊 Expected Screenshots Size

Each screenshot is typically 300-800 KB. Total for all 25: ~15-20 MB

```bash
# Check total size
du -sh docs/screenshots/

# Check individual sizes
ls -lh docs/screenshots/
```

---

## 🚀 After Capturing Screenshots

### 1. Verify All 25 Captured
```bash
# Count
ls docs/screenshots/*.png | wc -l

# Should output: 25
```

### 2. Create Image Gallery
```bash
# The screenshots are ready to use in documentation
# Reference them in markdown like:
# ![Dashboard](docs/screenshots/01_dashboard_full_page.png)
```

### 3. Commit to Git
```bash
# Add screenshots to git
git add docs/screenshots/
git commit -m "Add 25 automated UI screenshots"
git push origin main
```

### 4. Update Documentation
```bash
# Add to README.md or create new SCREENSHOTS.md:
cat > docs/SCREENSHOTS.md << 'EOF'
# AIOps Platform - Screenshot Gallery

## Dashboard
![Dashboard Full Page](screenshots/01_dashboard_full_page.png)
![KPI Cards](screenshots/02_dashboard_kpi_cards.png)

[... continue for all 25 ...]
EOF
```

---

## 📝 Example: Full Workflow

**Terminal 1:**
```bash
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent
./start_local.sh

# Wait for: "Platform is ready for testing!"
```

**Terminal 2:**
```bash
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent

# Install dependencies
npm install puppeteer

# Run capture
node capture-screenshots.js

# Wait for: "Capture Complete!"

# Verify
ls -1 docs/screenshots/ | head -10
# Should show: 01_dashboard_full_page.png, 02_dashboard_kpi_cards.png, etc.
```

**Terminal 1 (cleanup later):**
```bash
# When done, stop services
./start_local.sh --stop

# Or completely reset
docker-compose down -v
```

---

## ✨ Success Criteria

✅ **Capture is successful when:**
1. Script runs without errors
2. All 25 screenshots are created
3. All files are > 100KB (not blank)
4. Files are in `docs/screenshots/`
5. You can open screenshots in image viewer
6. Screenshots show real UI (not blank pages)

---

## 🎯 Command Reference

```bash
# Start services
./start_local.sh

# Stop services
./start_local.sh --stop

# Install Puppeteer
npm install puppeteer

# Run capture script
node capture-screenshots.js

# View screenshots
open docs/screenshots  # macOS
start docs\screenshots # Windows
nautilus docs/screenshots # Linux

# Count screenshots
ls docs/screenshots/*.png | wc -l

# Cleanup old screenshots
rm -rf docs/screenshots/*

# Verify file sizes
ls -lh docs/screenshots/
```

---

## 📞 Support

If you encounter issues:

1. **Check logs:**
   ```bash
   docker-compose logs backend
   docker-compose logs frontend
   ```

2. **Verify services:**
   ```bash
   curl http://localhost:8000/health
   curl -I http://localhost:5173
   ```

3. **Full reset:**
   ```bash
   docker-compose down -v --remove-orphans
   rm -rf docs/screenshots/*
   ./start_local.sh
   npm install puppeteer
   node capture-screenshots.js
   ```

---

## 🎉 Next Steps

Once screenshots are captured:

1. ✅ Review screenshots in `docs/screenshots/`
2. ✅ Create documentation gallery
3. ✅ Commit to git
4. ✅ Push to GitHub
5. ✅ Share with team

---

**Ready? Let's capture those screenshots!** 📸

```bash
# In Terminal 1 (already running):
./start_local.sh

# In Terminal 2:
npm install puppeteer
node capture-screenshots.js
```

