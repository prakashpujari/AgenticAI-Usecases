# Q&A Agent — API Gateway + React Frontend

This directory contains the complete web application for the Q&A Agent, including:
- **FastAPI Gateway** (`api/server.py`) — REST API with rate limiting and request queuing
- **React Frontend** (`frontend/`) — Modern, responsive UI for document upload and result viewing

## Architecture

```
┌──────────────────────────────────────┐
│        React Frontend                │
│  (http://localhost:5173)             │
│                                      │
│  • Document upload (drag & drop)     │
│  • Job status tracking               │
│  • Result download                   │
└──────────────────┬───────────────────┘
                   │ HTTP REST API
┌──────────────────▼───────────────────┐
│        FastAPI Gateway               │
│  (http://localhost:8000)             │
│                                      │
│  ✓ Rate limiting (10 req/min)        │
│  ✓ Request queuing                   │
│  ✓ CORS enabled                      │
│  ✓ Async job processing              │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│    Q&A Agent Pipeline                │
│  (Ingestion → Embedding → LLM)       │
│                                      │
│  • Universal document loader         │
│  • Text extraction & chunking        │
│  • FAISS vector store                │
│  • OpenAI GPT-4 / ChatGPT            │
│  • Markdown & PDF output             │
└──────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for React frontend)
- OpenAI API key
- (Optional) npm or yarn for package management

### 1. Install Backend Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the FastAPI Server
```bash
python start_server.py
```
The API will be available at: http://localhost:8000

### 3. Start the React Frontend (in a new terminal)
```bash
# On Windows
start_frontend.bat

# On macOS/Linux
bash start_frontend.sh
```
The UI will be available at: http://localhost:5173

## API Endpoints

### Health Check
```http
GET /health
```
Simple health check endpoint.

### Submit a Job
```http
POST /api/qa/generate
Content-Type: multipart/form-data

file: <PDF, TXT, MD, DOCX, XLSX, CSV>
num_questions: 5
```

**Response:**
```json
{
  "pipeline_id": "a1b2c3d4",
  "status": "queued",
  "created_at": "2026-05-10T14:23:45.123456",
  "message": "Job queued. Position in queue: 0"
}
```

### Get Job Status
```http
GET /api/qa/status/{pipeline_id}
```

**Response:**
```json
{
  "pipeline_id": "a1b2c3d4",
  "status": "completed",
  "created_at": "2026-05-10T14:23:45.123456",
  "updated_at": "2026-05-10T14:26:12.654321",
  "input_source": "path/to/document.pdf",
  "result_markdown": "# Q&A\n\n## Question 1\n...",
  "result_pdf_path": "/output/a1b2c3d4_qa.pdf",
  "error_message": null,
  "queue_position": null
}
```

### Download Result
```http
GET /api/qa/file/{pipeline_id}/{filename}
```

## Rate Limiting

The API enforces rate limiting to prevent abuse and resource exhaustion:

- **Global limit**: 100 requests/minute per IP
- **Job submission**: 10 uploads/minute per IP
- **Status checking**: 30 checks/minute per IP
- **File download**: 20 downloads/minute per IP

When the rate limit is exceeded, the API returns `HTTP 429 Too Many Requests`.

## Job Queue

Jobs are processed sequentially by a single background worker thread. This ensures:
- Stable resource usage (no parallel API calls)
- Deterministic queue ordering (FIFO)
- No memory exhaustion
- Graceful degradation under load

New jobs are immediately queued and assigned a unique `pipeline_id` that can be used to track progress.

## Supported Input Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| PDF    | `.pdf` | Extracted via pypdf |
| Plain Text | `.txt`, `.md`, `.rst`, `.csv`, `.log`, `.json`, `.yaml`, `.html` | UTF-8 encoding |
| Word | `.docx` | Requires `python-docx` |
| Excel | `.xlsx`, `.xls` | Requires `openpyxl` |
| URLs | `http://`, `https://` | Automatically downloaded |

## Configuration

API and pipeline settings are read from:
1. `.env` file (project root)
2. OS environment variables (take precedence)

Key variables:
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o                    # default
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
NUM_QUESTIONS=5                        # default
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
LOG_LEVEL=INFO
```

See `.env.example` for full reference.

## Development

### Frontend Development
```bash
cd frontend
npm run dev              # Start dev server with hot reload
npm run build           # Build for production
npm run lint            # Run ESLint
```

### API Development
```bash
# Run with auto-reload on code changes
python start_server.py

# Run without reload
uvicorn api.server:app --host 0.0.0.0 --port 8000

# View API docs (interactive)
# http://localhost:8000/docs
```

### Debugging
```bash
# Check API health
curl http://localhost:8000/health

# View API OpenAPI schema
curl http://localhost:8000/openapi.json

# Monitor job queue (tail logs)
tail -f logs/qa_agent.log
```

## Production Deployment

For production, consider:

1. **Rate Limiting Backend**: Use Redis instead of in-memory storage
   ```python
   # In api/server.py
   limiter = Limiter(
       key_func=get_remote_address,
       storage_uri="redis://localhost:6379",
   )
   ```

2. **Job Queue**: Replace threading with Celery + Redis
   ```bash
   pip install celery redis
   celery -A api.tasks worker --loglevel=info
   ```

3. **Frontend**: Build and serve as static files
   ```bash
   cd frontend && npm run build
   # Serve frontend/dist/ with nginx or FastAPI's StaticFiles
   ```

4. **HTTPS**: Use Uvicorn behind a reverse proxy (nginx, Caddy)

5. **Database**: Use PostgreSQL instead of SQLite
   ```python
   # In api/server.py
   DATABASE_URL = "postgresql://user:password@localhost/qa_agent"
   ```

## Troubleshooting

### API not connecting to frontend
- Check that the API is running on port 8000
- Check CORS settings in `api/server.py` (allow localhost:5173)
- Check browser console for CORS errors

### Jobs stuck in "processing" status
- Check logs: `tail -f logs/qa_agent.log`
- Ensure OpenAI API key is set and valid
- Check available disk space for output files

### React build errors
- Delete `frontend/node_modules` and `frontend/package-lock.json`
- Run `npm install` again
- Check Node version: `node --version` (should be 18+)

## License

MIT

## Contact

For issues or questions, see the main [README.md](../README.md)
