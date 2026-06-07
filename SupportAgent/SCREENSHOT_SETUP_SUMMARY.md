# 📸 Screenshot Capture Setup - Complete Summary

## ✨ What You Have Now

I've created **3 tools** to automatically capture 25 UI screenshots:

1. **`capture-screenshots.js`** - Puppeteer script that captures all screenshots
2. **`RUN_SCREENSHOT_CAPTURE.md`** - Detailed guide with troubleshooting
3. **`capture_screenshots.bat`** - Windows batch file for easy execution

---

## 🚀 Quick Start (Choose One)

### Option A: Windows Users (Easiest)

**Step 1:** Make sure services are running
```batch
# In Terminal/PowerShell:
./start_local.sh

# Wait for: "Platform is ready for testing!"
```

**Step 2:** Run the batch file
```batch
# In another Terminal/PowerShell:
capture_screenshots.bat

# Script will:
# ✅ Check if backend is running
# ✅ Install Puppeteer
# ✅ Launch browser
# ✅ Capture 25 screenshots
# ✅ Save to docs/screenshots/
```

---

### Option B: Manual (All Platforms)

**Step 1:** Start services
```bash
./start_local.sh
# Wait for all tests to pass ✅
```

**Step 2:** Install Puppeteer
```bash
npm install puppeteer
```

**Step 3:** Run capture script
```bash
node capture-screenshots.js
```

---

## 📋 What Happens During Capture

The script automatically:

1. **Verifies Backend** - Checks API is running
2. **Creates Test Data** - Makes a sample incident
3. **Launches Browser** - Opens automated browser window
4. **Captures Screenshots:**
   - Dashboard (5 screenshots)
   - Incident Details (6 screenshots)
   - Remediation (5 screenshots)
   - Metrics (4 screenshots)
   - API Documentation (3 screenshots)
5. **Saves Files** - All 25 PNGs go to `docs/screenshots/`
6. **Reports Summary** - Shows what was captured

---

## ✅ Expected Output

### Terminal 1 (Services)
```
========================================
AIOps Platform - End-to-End Test Suite
========================================

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

=== Access Information ===
Frontend: http://localhost:5173
Backend:  http://localhost:8000
```

### Terminal 2 (Screenshot Capture)
```
╔════════════════════════════════════════════════════════════════╗
║     AIOps Platform - Automated Screenshot Capture             ║
╚════════════════════════════════════════════════════════════════╝

🔍 Verifying services...
✅ Backend API is running

📋 Setting up test data...
✅ Test incident created: [UUID]

🌐 Launching browser...
📸 Capturing screenshots...

📸 Capturing: 01_dashboard_full_page
   ✅ Saved to: docs/screenshots/01_dashboard_full_page.png

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

## 📁 Files Created

```
SupportAgent/
├── capture-screenshots.js          ← Main Puppeteer script
├── capture_screenshots.bat         ← Windows batch runner
├── RUN_SCREENSHOT_CAPTURE.md       ← Detailed guide
└── SCREENSHOT_SETUP_SUMMARY.md     ← This file
```

---

## 🎯 What Gets Captured

### Dashboard (5)
✓ Full page view  
✓ KPI cards  
✓ Filters  
✓ Table header  
✓ Full table with data  

### Incident Details (6)
✓ Header  
✓ Info grid  
✓ Overview tab  
✓ RCA tab  
✓ Evidence tab  
✓ Action buttons  

### Remediation (5)
✓ Header & risk assessment  
✓ First action card  
✓ Multiple actions  
✓ Success criteria  
✓ Approval form  

### Metrics (4)
✓ KPI cards  
✓ Timeline chart  
✓ MTTD vs MTTR chart  
✓ Severity breakdown  

### API Documentation (3)
✓ Swagger overview  
✓ POST endpoint details  
✓ Response schema  

---

## ✨ After Capture Completes

### Verify Screenshots
```bash
# Check how many were captured
ls docs/screenshots/*.png | wc -l
# Should show: 25

# View them
start docs\screenshots  # Windows
open docs/screenshots   # macOS
nautilus docs/screenshots  # Linux
```

### Commit to Git
```bash
git add docs/screenshots/
git commit -m "Add 25 automated UI screenshots captured via Puppeteer"
git push origin main
```

### Update Documentation
```bash
# Create screenshot gallery
cat > docs/SCREENSHOT_GALLERY.md << 'EOF'
# AIOps Platform - Screenshot Gallery

All 25 screenshots captured automatically.

## Dashboard
![Full Dashboard](screenshots/01_dashboard_full_page.png)

[... add more ...]
EOF
```

---

## 🔧 Requirements

✅ **Already Have:**
- Docker & Docker Compose (for services)
- Python 3.11+ (for backend)
- Node.js & npm (for frontend)

✅ **Script Installs:**
- Puppeteer (npm package)
- Chromium browser (auto-downloaded)

---

## ⚡ Prerequisites Checklist

Before running, make sure:

- [ ] Docker is installed (`docker --version`)
- [ ] Docker Compose is installed (`docker-compose --version`)
- [ ] Node.js is installed (`node --version`)
- [ ] npm is installed (`npm --version`)
- [ ] You're in the project directory: `c:\pp\GitHub\AgenticAI-Usecases\SupportAgent`
- [ ] `.env` file exists (or run `cp .env.example .env`)

**Quick check:**
```bash
docker --version
docker-compose --version
node --version
npm --version
```

---

## 🚨 Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| "Backend not running" | Run `./start_local.sh` in Terminal 1 |
| "Puppeteer not found" | Run `npm install puppeteer` |
| "Chrome won't launch" | Edit script to use `headless: true` |
| "Screenshots blank" | Increase wait time in script (change 2000 to 5000) |
| "Port 5173 in use" | Kill process: `lsof -ti :5173 \| xargs kill -9` |
| "npm install fails" | Try: `npm install puppeteer --legacy-peer-deps` |

**Full troubleshooting:** See `RUN_SCREENSHOT_CAPTURE.md`

---

## 📊 Timeline

| Step | Time | Action |
|------|------|--------|
| 1 | 5 min | Run `./start_local.sh` |
| 2 | 1 min | Run `npm install puppeteer` |
| 3 | 5 min | Run `node capture-screenshots.js` |
| 4 | 1 min | Verify files in `docs/screenshots/` |
| **Total** | **~12 minutes** | **Complete workflow** |

---

## 🎯 Success Criteria

✅ **Capture is successful when:**

1. ✓ `./start_local.sh` runs without errors
2. ✓ All 13 tests show PASS
3. ✓ Backend API available at `http://localhost:8000`
4. ✓ Frontend loads at `http://localhost:5173`
5. ✓ Screenshot script runs without errors
6. ✓ 25 PNG files appear in `docs/screenshots/`
7. ✓ Each file is > 100KB (not blank)
8. ✓ Can open screenshots in image viewer
9. ✓ All 25 screenshots show real UI

---

## 📝 Next Steps After Capture

1. **Review Screenshots**
   ```bash
   # Open screenshots folder
   start docs\screenshots
   ```

2. **Create Gallery Documentation**
   ```bash
   # Reference in README.md or create new doc
   ```

3. **Commit to Git**
   ```bash
   git add docs/screenshots/
   git commit -m "Add 25 UI screenshots"
   git push
   ```

4. **Share with Team**
   - Upload to documentation system
   - Link from README
   - Share in team channels

---

## 💡 Pro Tips

1. **Keep services running** - Don't stop services until all screenshots are captured

2. **Watch the browser** - With `headless: false`, you'll see the browser open and navigate (cool to watch!)

3. **Parallel terminals** - Keep Terminal 1 for services, Terminal 2 for capture script

4. **Save screenshots** - They're in `docs/screenshots/` and safe to commit to git

5. **Rerun anytime** - If you need fresh screenshots, just run the script again

---

## 📞 Command Reference

```bash
# ============ SERVICES (Terminal 1) ============

# Start all services
./start_local.sh

# Stop services (keep data)
./start_local.sh --stop

# Reset everything
docker-compose down -v --remove-orphans

# ============ SCREENSHOTS (Terminal 2) ============

# Install Puppeteer
npm install puppeteer

# Run capture (Option 1 - direct)
node capture-screenshots.js

# Run capture (Option 2 - Windows batch)
capture_screenshots.bat

# Verify screenshots
ls docs/screenshots/*.png | wc -l

# View screenshots
start docs\screenshots

# ============ GIT ============

# Add screenshots to git
git add docs/screenshots/

# Commit
git commit -m "Add 25 automated UI screenshots"

# Push
git push origin main
```

---

## 🎬 Ready to Capture?

### Quick Start Command
```bash
# Terminal 1: Start services
./start_local.sh

# Terminal 2: Run capture
npm install puppeteer
node capture-screenshots.js
```

### Or use batch file (Windows):
```batch
capture_screenshots.bat
```

---

## ✅ You're All Set!

Everything is ready to automatically capture all 25 UI screenshots.

**Next action:**
1. Open 2 terminals/PowerShell windows
2. Terminal 1: Run `./start_local.sh`
3. Terminal 2: Run `npm install puppeteer && node capture-screenshots.js`
4. Wait for "Capture Complete!" message
5. Check `docs/screenshots/` for 25 PNG files

**Time to complete:** ~15 minutes ⏱️

---

**Happy screenshotting!** 📸🎉

