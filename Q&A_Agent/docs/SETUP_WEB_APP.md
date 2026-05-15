# 🚀 FastAPI Gateway + React UI Setup Guide

## Overview

Your Q&A Agent now has a complete modern web application:

```
┌─────────────────────────────────────────────┐
│   React Frontend (Port 5173)                │
│   ✨ Modern, responsive UI                  │
│   ✓ Drag-and-drop file upload               │
│   ✓ Real-time job status                    │
│   ✓ PDF download                            │
│   ✓ Tailwind CSS styling                    │
└──────────────────┬──────────────────────────┘
                   │ HTTP REST API
┌──────────────────▼──────────────────────────┐
│   FastAPI Gateway (Port 8000)               │
│   ⚡ High-performance async API             │
│   ✓ Rate limiting (10 req/min)              │
│   ✓ Request queuing (FIFO)                  │
│   ✓ SQLite job tracking                     │
│   ✓ Auto-generated Swagger docs             │
│   ✓ CORS enabled                            │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│   Q&A Pipeline (Sequential)                 │
│   📄 Document loading                       │
│   🔤 Text extraction & chunking             │
│   🧠 OpenAI embeddings                      │
│   ❓ MCQ generation                         │
│   📑 PDF conversion                         │
└─────────────────────────────────────────────┘
```

## Quick Start (All-in-One)

**Simplest way to run everything:**

```bash
python run_all.py
```

This will:
1. ✓ Install all Python dependencies
2. ✓ Install all Node.js dependencies  
3. ✓ Start the API server (port 8000)
4. ✓ Start the React dev server (port 5173)
5. ✓ Open the browser to http://localhost:5173

## Manual Setup

### Step 1: Start the API Server

```bash
# Terminal 1
python start_server.py
```

You'll see:
```
📦 Installing dependencies...
🚀 Starting Q&A Agent API Server...
📍 API endpoint: http://localhost:8000
📖 API documentation: http://localhost:8000/docs
```

Visit http://localhost:8000/docs to see the interactive API documentation.

### Step 2: Start the React Frontend

```bash
# Terminal 2
start_frontend.bat     # Windows
# or
bash start_frontend.sh # macOS/Linux
```

The frontend will start on http://localhost:5173.

## Using the Web UI

### 1. Upload a Document

- **Click or drag-and-drop** a file onto the upload area
- **Supported formats:**
  - PDF documents
  - Text files (TXT, MD, RST)
  - Word documents (DOCX)
  - Excel sheets (XLSX, CSV)
  - Public URLs (http://, https://)

### 2. Configure Questions

- Set the **number of questions** (1-20, default: 5)
- Click **"Generate Questions"**

### 3. Monitor Progress

- Your job ID appears immediately
- Status updates in **real-time**
- Queue position shown if waiting
- Processing indicators during generation

### 4. Download Results

Once completed:
- **View Results**: See generated Q&A in the results panel
- **Download PDF**: Get a styled PDF with all questions
- **Preview**: View PDF directly in browser

## API Reference

### Health Check
```bash
curl http://localhost:8000/health
```

### Submit a Document
```bash
curl -X POST http://localhost:8000/api/qa/generate \
  -F "file=@document.pdf" \
  -F "num_questions=5"
```

**Response:**
```json
{
  "pipeline_id": "abc12def",
  "status": "queued",
  "created_at": "2026-05-10T14:23:45.123456",
  "message": "Job queued. Position in queue: 0"
}
```

### Check Job Status
```bash
curl http://localhost:8000/api/qa/status/abc12def
```

**Possible statuses:**
- `queued` — Waiting in queue
- `processing` — Currently running
- `completed` — Done, results available
- `failed` — Error occurred

### Download Result
```bash
curl -O http://localhost:8000/api/qa/file/abc12def/abc12def_qa.pdf
```

## Rate Limiting

The API is **throttled** to prevent overload:

| Endpoint | Limit |
|----------|-------|
| `/api/qa/generate` | 10 requests/minute |
| `/api/qa/status/*` | 30 requests/minute |
| `/api/qa/download/*` | 20 requests/minute |
| Global | 100 requests/minute |

Limits are **per IP address** and reset every minute.

## Job Queue

Jobs are processed **one at a time** (FIFO):

1. **Submit** → Job enters queue with unique ID
2. **Wait** → Position shown in real-time
3. **Process** → API processes documents sequentially
4. **Complete** → Results ready for download

This prevents:
- ❌ Resource exhaustion
- ❌ API rate limit hits
- ❌ Memory overflow
- ✓ Stable performance

## Configuration

Edit the `.env` file to customize:

```bash
# OpenAI settings
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Pipeline settings
NUM_QUESTIONS=5
CHUNK_SIZE=1000
CHUNK_OVERLAP=100

# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=true
```

## Folder Structure

```
.
├── api/
│   ├── server.py           ← FastAPI application
│   ├── jobs.db             ← SQLite job database
│   ├── uploads/            ← Temporary uploaded files
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── components/     ← React components
│   │   ├── App.jsx         ← Main app
│   │   └── main.jsx        ← Entry point
│   ├── vite.config.js      ← Vite configuration
│   ├── tailwind.config.js  ← Tailwind CSS
│   └── package.json
├── start_server.py         ← Start API
├── start_frontend.bat      ← Start React (Windows)
├── start_frontend.sh       ← Start React (Unix)
├── run_all.py              ← Start everything
├── requirements.txt        ← Python dependencies
├── config.py              ← Configuration
├── main.py                ← CLI version
├── src/                   ← Pipeline implementation
├── output/                ← Generated Q&A files
└── logs/                  ← Application logs
```

## Troubleshooting

### Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9  # macOS/Linux
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process  # Windows
```

### API not responding
- Check: `curl http://localhost:8000/health`
- View logs: `tail -f logs/qa_agent.log`
- Check API started: `python start_server.py`

### Frontend not loading
- Check Node.js: `node --version` (need 18+)
- Delete `frontend/node_modules`: `rm -rf frontend/node_modules`
- Reinstall: `cd frontend && npm install`
- Start again: `npm run dev`

### Jobs stuck in "processing"
- Check OpenAI API key is valid
- Check logs: `tail -f logs/qa_agent.log`
- Check disk space for output files
- Try restarting the API server

### CORS errors in browser console
- Ensure API running on port 8000
- Ensure React running on port 5173
- Check `api/server.py` CORS settings

## Performance Tips

### For Production
1. **Use Redis** for rate limiting (better than in-memory)
2. **Use PostgreSQL** instead of SQLite
3. **Use Celery** for job queue (instead of threading)
4. **Build React** and serve as static files
5. **Use gunicorn/nginx** as reverse proxy
6. **Enable HTTPS** with valid SSL certificate

### For Large Files
- Increase file size limit in `api/server.py`:
  ```python
  if file.size and file.size > 500 * 1024 * 1024:  # 500 MB
  ```
- Use async processing with Celery
- Implement file streaming for downloads

## Development Workflow

### React Changes
- Files in `frontend/src/` auto-reload
- Check browser console for errors
- View Network tab for API calls

### API Changes
- Files in `api/` auto-reload (with `--reload`)
- Check logs for errors
- Test with `curl` or API docs (`/docs`)

### Backend Changes
- Modify `src/pipeline/` modules
- Restart API server
- Test with `python main.py` to isolate

## Next Steps

✅ **Now running:** API + Web UI with rate limiting
🎯 **Consider adding:**
- [ ] Authentication (JWT tokens)
- [ ] Email notifications on completion
- [ ] Batch processing (multiple documents)
- [ ] WebSocket for real-time updates
- [ ] Result history/dashboard
- [ ] User accounts & quotas
- [ ] S3/Cloud storage integration
- [ ] Admin panel for queue management

## Support

For questions or issues:
1. Check the logs: `tail -f logs/qa_agent.log`
2. Review API docs: http://localhost:8000/docs
3. See main [README.md](./README.md) for pipeline details

---

**Happy question-generating! 🎉**
