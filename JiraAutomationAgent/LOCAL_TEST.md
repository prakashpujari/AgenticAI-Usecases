# 🧪 Local Testing - Quick Start

## ✅ Both Servers Running

### Frontend
```
🟢 Status: RUNNING
📍 URL: http://localhost:5174
📦 Framework: Vite + React
🔄 Hot Reload: Enabled
```

### Backend
```
🟢 Status: RUNNING
📍 URL: http://localhost:8000
📦 Framework: FastAPI
📊 Health: Degraded (Redis not running locally - expected)
```

---

## 🎯 Next Steps

### Step 1: Open Frontend in Browser

👉 **Go to**: http://localhost:5174

You should see the **JiraAI Automation Agent** dashboard load.

### Step 2: Check Browser Console

Open DevTools: **F12** or **Ctrl+Shift+I**

Look for:
- ✅ No major errors
- ✅ Network tab shows API calls
- ✅ Console is clean (maybe some warnings, OK)

### Step 3: Test API Connectivity

In browser console (F12 → Console tab), run:

```javascript
fetch('http://localhost:8000/health')
  .then(r => r.json())
  .then(d => console.log('Backend response:', d))
  .catch(e => console.error('Backend error:', e))
```

**Expected**: Should log: `{"status":"degraded","services":{"redis":"degraded","pinecone":"ok","jira":"ok"}}`

### Step 4: Try Creating a Ticket (if UI supports it)

1. Look for a "Create Ticket" button or form
2. Fill in sample data:
   - Title: "Test Database Issue"
   - Description: "Sample test issue"
3. Submit
4. Check:
   - Does response come back?
   - Any errors in console?
   - Does the UI update?

---

## 🔍 Troubleshooting

### "Cannot reach backend" Error

**Check**:
```bash
# Backend health
curl http://localhost:8000/health
# Should return: {"status":"degraded",...}

# Backend API docs
curl http://localhost:8000/docs
# Should return HTML (Swagger UI)
```

### Frontend shows blank page

**Check**:
- Open DevTools (F12)
- Look for JavaScript errors in Console
- Check Network tab for failed requests
- Try hard refresh: **Ctrl+Shift+R**

### Port 5174 instead of 5173

**This is OK!** Port 5173 was in use, so Vite used 5174 instead.
- Use: http://localhost:5174

---

## 📊 API Endpoints to Test

Once you get the UI working, try these API calls:

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Get recent tickets
curl http://localhost:8000/ai/recent-tickets?projects=MC

# 3. API documentation
# Open: http://localhost:8000/docs
```

---

## ✅ Success Criteria

You'll know everything is working when:

- [x] Frontend loads at http://localhost:5174
- [x] No major JavaScript errors in console
- [x] Browser can reach backend (test with fetch above)
- [x] UI is responsive and interactive
- [x] Forms can be filled and submitted
- [x] API responses come back without 404s

---

## 🚀 Next: Deploy to Production

Once you've verified locally:

1. **Deploy backend to Render** (5 min)
   - Follow: [ACTION_PLAN.md](ACTION_PLAN.md)
   - Get: https://jira-automation-backend.onrender.com

2. **Update Vercel frontend** (1 min)
   - Add `VITE_API_URL` env var with backend URL
   - Auto-redeploys

3. **Test production** (5 min)
   - Verify both systems work together
   - Share URLs with team

---

## 📝 Local Server Info

**Frontend Dev Server**:
- URL: http://localhost:5174
- Hot reload: Yes
- Build: Enabled
- CORS: Configured

**Backend API Server**:
- URL: http://localhost:8000
- Documentation: http://localhost:8000/docs
- Health: http://localhost:8000/health
- CORS: Configured for localhost:5173 and localhost:5174

---

## 💡 Tips

- Keep both terminal windows open
- If you modify code, both apps hot-reload
- Check console (F12) if anything seems wrong
- Backend logs are in the terminal where you started it
- Frontend logs are in browser console

---

## 🎯 Ready to Test?

Open your browser and go to: **http://localhost:5174**

Let me know what you see! 🚀

