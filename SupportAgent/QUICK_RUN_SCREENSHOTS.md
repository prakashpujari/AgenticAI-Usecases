# 🚀 Quick Start - Capture Screenshots NOW

## Windows PowerShell (Easiest)

### Step 1: Start Services (PowerShell Window 1)
```powershell
./start_local.sh

# Wait for: ✅ All tests passed!
```

### Step 2: Run Capture (PowerShell Window 2)
```powershell
.\capture_screenshots.ps1

# Script will:
# ✅ Check if backend is running
# ✅ Install Puppeteer  
# ✅ Launch browser
# ✅ Capture 25 screenshots
# ✅ Save to docs/screenshots/
```

**That's it!** When complete, you'll have 25 PNG files in `docs/screenshots/`

---

## If PowerShell Script Won't Run

### Error: "Cannot be loaded because running scripts is disabled"

**Solution:** Open PowerShell as Administrator and run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try again:
```powershell
.\capture_screenshots.ps1
```

---

## Alternative: Batch File

If PowerShell gives issues, use batch file instead:

### Step 1: Start Services (Command Prompt Window 1)
```batch
start_local.sh

# Wait for all tests to pass
```

### Step 2: Run Capture (Command Prompt Window 2)
```batch
.\capture_screenshots.bat
```

---

## Alternative: Manual Command

```powershell
# Install
npm install puppeteer

# Run
node capture-screenshots.js
```

---

## ✅ When Complete

You'll see:
```
✅ Capture Complete!
📊 Summary:
   Total captured: 25
   Output directory: docs\screenshots
```

Then check:
```powershell
# View files
start docs\screenshots

# Count files
(Get-ChildItem docs\screenshots\*.png).Count
# Should show: 25
```

---

## 🎯 Quick Commands

| Action | Command |
|--------|---------|
| Start services | `./start_local.sh` |
| Capture screenshots (PowerShell) | `.\capture_screenshots.ps1` |
| Capture screenshots (Batch) | `.\capture_screenshots.bat` |
| Manual capture | `npm install puppeteer && node capture-screenshots.js` |
| View screenshots | `start docs\screenshots` |
| Count files | `(Get-ChildItem docs\screenshots\*.png).Count` |

---

**Ready? Run `.\capture_screenshots.ps1` now!** 📸

