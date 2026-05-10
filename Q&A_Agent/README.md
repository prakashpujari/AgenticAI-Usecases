# Q&A Agent — End-to-End RAG Pipeline

An automated pipeline that ingests a PDF document, builds a semantic vector index, generates multiple-choice questions using GPT-4o, and exports the results as both Markdown and a styled PDF — with full observability via structured logging, per-stage metrics, and LangSmith tracing.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [How It Works — Step by Step](#how-it-works--step-by-step)
4. [Setup & Installation](#setup--installation)
5. [Configuration Reference](#configuration-reference)
6. [Running the Pipeline](#running-the-pipeline)
7. [Outputs](#outputs)
8. [Observability](#observability)
9. [LangSmith Tracing](#langsmith-tracing)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Q&A Agent Pipeline                             │
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │  Stage 1 │    │  Stage 2 │    │  Stage 3 │    │    Stage 4       │  │
│  │ Generate │───▶│ Extract  │───▶│  Split   │───▶│  Embed + Build   │  │
│  │   PDF    │    │  Text    │    │  Chunks  │    │  FAISS Index     │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────────────┘  │
│   ReportLab        pypdf          LangChain         OpenAI Embeddings   │
│                                  TextSplitter      text-embedding-3-    │
│                                                         small           │
│                                                              │           │
│                                                              ▼           │
│  ┌──────────┐    ┌──────────┐    ┌───────────────────────────────────┐  │
│  │  Stage 7 │    │  Stage 6 │    │            Stage 5                │  │
│  │ MD → PDF │◀───│ Format   │◀───│     Retrieve + Generate Q&A       │  │
│  │          │    │ Markdown │    │  FAISS similarity search → GPT-4o │  │
│  └──────────┘    └──────────┘    └───────────────────────────────────┘  │
│   xhtml2pdf      output_         LangChain LCEL chain:                  │
│                  formatter       Prompt | ChatOpenAI | StrOutputParser   │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
          Structured        Per-stage       LangSmith
           Logging           Metrics         Tracing
         (JSON Lines)      (JSON report)   (UI traces)
```

### Key Technology Choices

| Concern | Technology | Why |
|---|---|---|
| LLM | GPT-4o via LangChain | State-of-the-art reasoning; JSON output mode for reliable structured responses |
| Embeddings | `text-embedding-3-small` | Cost-effective; 1536-dim; excellent semantic fidelity |
| Vector store | FAISS (CPU) | Zero infra overhead; persisted to disk; fast local similarity search |
| Text splitting | LangChain `RecursiveCharacterTextSplitter` | Respects sentence/paragraph boundaries; configurable overlap |
| Chain composition | LangChain LCEL (`|` pipe operator) | Declarative, auto-traced by LangSmith |
| PDF creation | ReportLab | Pure Python; full layout control |
| PDF extraction | pypdf | Lightweight; page-by-page text extraction |
| MD → PDF | xhtml2pdf | Pure Python HTML→PDF; no external binaries needed |
| Observability | Python `logging` + LangSmith | Structured JSON log file + real-time LLM trace UI |

---

## Project Structure

```
Q&A_Agent/
│
├── main.py                    # Entry point — orchestrates all 7 stages
├── config.py                  # All settings (env vars + defaults)
├── requirements.txt           # Python dependencies
├── .env                       # Your secrets (gitignored)
├── .env.example               # Template for new contributors
├── .gitignore
│
├── src/
│   ├── ingestion/
│   │   ├── pdf_generator.py   # Stage 1 — creates sample PDF with ReportLab
│   │   └── pdf_extractor.py   # Stage 2 — extracts + cleans text from PDF
│   │
│   ├── retrieval/
│   │   └── embeddings_store.py # Stages 3–4 — chunks text, embeds, builds FAISS
│   │
│   ├── generation/
│   │   └── qa_generator.py    # Stage 5 — retrieves context + calls GPT-4o
│   │
│   ├── output/
│   │   ├── output_formatter.py # Stage 6 — renders questions as Markdown
│   │   └── pdf_converter.py   # Stage 7 — converts Markdown → styled PDF
│   │
│   └── pipeline/
│       └── stages.py          # Thin wrappers: adds metrics + @traceable to each stage
│
├── observability/
│   ├── logger.py              # Structured logging (console + JSON Lines file)
│   ├── metrics.py             # Per-stage timing + metadata (PipelineMetrics)
│   └── langsmith_tracer.py    # LangSmith initialisation + connectivity check
│
├── data/
│   ├── sample_document.pdf    # Auto-generated source PDF (gitignored)
│   └── faiss_index/           # Persisted FAISS index files (gitignored)
│
└── output/
    ├── qa_output.md           # Generated Q&A in Markdown (gitignored)
    ├── qa_output.pdf          # Generated Q&A as PDF (gitignored)
    └── pipeline_metrics.json  # Per-stage timing report (gitignored)
```

---

## How It Works — Step by Step

### Stage 1 — Generate Sample PDF

**File:** `src/ingestion/pdf_generator.py`

ReportLab creates a multi-page PDF on the topic of **Cloud Computing** (covering IaaS/PaaS/SaaS, deployment models, security, cost optimisation, etc.). This acts as the source document for the pipeline.

- Skipped automatically if `data/sample_document.pdf` already exists.
- In production you would swap this for any real PDF.

---

### Stage 2 — Extract & Clean Text

**File:** `src/ingestion/pdf_extractor.py`

pypdf reads the PDF page by page and concatenates the raw text. A cleaning pass normalises whitespace and removes artefacts (ligatures, control characters) that confuse the tokeniser.

```
PDF (binary) ──pypdf──▶ raw text (per page) ──clean──▶ clean string
                         "16529 chars"                  "16521 chars"
```

---

### Stage 3 — Split Text into Chunks

**File:** `src/retrieval/embeddings_store.py` → `split_text()`

LangChain's `RecursiveCharacterTextSplitter` divides the cleaned text into overlapping chunks:

```
clean text (16 521 chars)
       │
       ▼  chunk_size=1000, overlap=200
  [ chunk_0 ][ chunk_1 ][ chunk_2 ] … [ chunk_23 ]
       │───200 chars overlap───│
```

- Each chunk becomes a `Document` object carrying the text + optional metadata.
- Overlap ensures a sentence that falls near a boundary appears in both adjacent chunks, so the retriever can always find full context.

---

### Stage 4 — Embed Chunks & Build FAISS Index

**File:** `src/retrieval/embeddings_store.py` → `build_vector_store()`

Each of the 24 chunks is converted to a **1536-dimensional vector** by OpenAI's `text-embedding-3-small` model. FAISS indexes these vectors for fast approximate nearest-neighbour search.

```
chunk_0 (text) ──OpenAI API──▶ [0.02, -0.15, 0.83, … ] (1536 floats)
chunk_1 (text) ──OpenAI API──▶ [0.11,  0.04, 0.61, … ]
       …
chunk_23                      ▶ [ … ]
                                      │
                              FAISS.from_documents()
                                      │
                              index saved to data/faiss_index/
```

The index is persisted to disk so subsequent runs can skip re-embedding (if you choose to add that optimisation).

---

### Stage 5 — Retrieve Context & Generate Questions

**File:** `src/generation/qa_generator.py`

This is the core RAG (Retrieval-Augmented Generation) stage. It has two sub-steps:

#### 5a. Multi-Query Retrieval

8 topic-specific queries are run against the FAISS index (e.g., "Cloud deployment models", "Cloud security and compliance"). Each query returns the top-K most similar chunks. Duplicates are removed, yielding ~24 unique context chunks.

```
query_1: "Cloud service models IaaS PaaS SaaS"
              │
              ▼  FAISS similarity search (top-15)
         [chunk_3, chunk_7, chunk_12, …]
query_2: "Cloud security compliance"
              │
              ▼
         [chunk_1, chunk_5, chunk_9, …]
              …
         ──────────────────────────────
         deduplicate → 24 unique chunks
```

#### 5b. LLM Generation (LCEL Chain)

All context chunks are concatenated and passed to GPT-4o via a LangChain LCEL chain:

```
ChatPromptTemplate
       │  (system prompt: "generate {n} MCQs as JSON…")
       │  (human: context + instructions)
       ▼
  ChatOpenAI (gpt-4o, temperature=0.3)
       │
       ▼
  StrOutputParser
       │
       ▼
  JSON parse + validate
       │
       ▼
  list of 10 QuestionDicts:
  {
    "question": "What does IaaS stand for?",
    "options": {"A": "…", "B": "…", "C": "…", "D": "…"},
    "correct_answer": "B",
    "explanation": "IaaS stands for …"
  }
```

---

### Stage 6 — Format as Markdown

**File:** `src/output/output_formatter.py`

The validated question list is rendered into a structured Markdown document:

```markdown
# Q&A: Cloud Computing Fundamentals

## Question 1
**What does IaaS stand for?**

- A) Internet as a Service
- B) Infrastructure as a Service  ✓
- C) Integration as a Service
- D) Intelligence as a Service

**Explanation:** IaaS stands for Infrastructure as a Service …
```

Saved to `output/qa_output.md`.

---

### Stage 7 — Convert Markdown to PDF

**File:** `src/output/pdf_converter.py`

A two-pass conversion:

```
qa_output.md
     │
     ▼  markdown library
  HTML string (with CSS styling)
     │
     ▼  xhtml2pdf (pisa)
  qa_output.pdf
```

The CSS applies fonts, colours, spacing, and page margins so the PDF is readable and professionally formatted.

---

## Setup & Installation

### Prerequisites

- Python 3.12+
- An [OpenAI API key](https://platform.openai.com/api-keys) (GPT-4o access required)
- *(Optional)* A [LangSmith API key](https://smith.langchain.com) for tracing

### 1. Clone the repository

```bash
git clone <repo-url>
cd Q&A_Agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux
```

Edit `.env`:

```env
# Required
OPENAI_API_KEY=sk-...

# Optional overrides (defaults shown)
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
NUM_QUESTIONS=10
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K_RETRIEVAL=15
TEMPERATURE=0.3

# LangSmith tracing (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=qa-agent
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI secret key |
| `OPENAI_MODEL` | `gpt-4o` | Chat model for Q&A generation |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for FAISS |
| `NUM_QUESTIONS` | `10` | Number of MCQs to generate |
| `CHUNK_SIZE` | `1000` | Max characters per text chunk |
| `CHUNK_OVERLAP` | `200` | Overlapping characters between chunks |
| `TOP_K_RETRIEVAL` | `15` | Chunks returned per similarity query |
| `TEMPERATURE` | `0.3` | LLM sampling temperature (0 = deterministic) |
| `LOG_LEVEL` | `INFO` | Console log verbosity (`DEBUG`/`INFO`/`WARNING`) |
| `LOG_TO_FILE` | `true` | Enable rotating JSON log file |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | *(empty)* | LangSmith API key |
| `LANGCHAIN_PROJECT` | `qa-agent` | LangSmith project name |

---

## Running the Pipeline

```bash
python main.py
```

Expected output (≈ 20–30 seconds):

```
12:41:33  INFO  LangSmith tracing ENABLED  project='qa-agent'
12:41:49  INFO  Pipeline 2a3a3614 starting — model=gpt-4o  questions=10
12:41:49  INFO  [1/7] Sample PDF already exists, skipping
12:41:49  INFO  [2/7] Extracting and cleaning text from PDF …
12:41:49  INFO        ✓ Extracted 16521 characters
12:41:49  INFO  [3/7] Splitting text into chunks …
12:41:49  INFO        ✓ 24 chunks created
12:41:52  INFO  [4/7] Building FAISS vector store …
12:41:52  INFO        ✓ FAISS index built and saved
12:41:52  INFO  [5/7] Generating 10 questions with gpt-4o …
12:42:08  INFO        ✓ 10 questions generated
12:42:08  INFO  [6/7] Formatting questions as Markdown …
12:42:08  INFO  [7/7] Converting Markdown → PDF …
12:42:10  INFO  Pipeline 2a3a3614 — COMPLETE

────────────────────────────────────────────────
  Stage                    Status     Duration
────────────────────────────────────────────────
  generate_sample_pdf      success      0.00s
  extract_text             success      0.04s
  split_text               success      0.00s
  build_vector_store       success      3.13s
  generate_questions       success     16.38s
  format_markdown          success      0.00s
  convert_to_pdf           success      1.16s
────────────────────────────────────────────────
  Total: 20.9 s
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Pipeline completed successfully |
| `1` | Configuration error (missing API key, bad env var) |
| `2` | Runtime error (API failure, file not found) |

---

## Outputs

| File | Description |
|---|---|
| `output/qa_output.md` | 10 MCQs with options, correct answer, and explanation in Markdown |
| `output/qa_output.pdf` | Styled PDF version of the Markdown |
| `output/pipeline_metrics.json` | Machine-readable per-stage timing and metadata |
| `logs/qa_agent.log` | Rotating structured log (JSON Lines format) |

---

## Observability

### Structured Logging

Every log line is emitted to two sinks simultaneously:

- **Console** — human-readable with ANSI colours and aligned columns
- **`logs/qa_agent.log`** — JSON Lines format, one JSON object per line, for log aggregation tools

```json
{"ts":"2026-05-10T12:42:08+00:00","level":"INFO","logger":"src.generation.qa_generator",
 "message":"Generated and validated 10 questions.","module":"qa_generator","line":290}
```

### Pipeline Metrics

`output/pipeline_metrics.json` is written after every run:

```json
{
  "pipeline_id": "2a3a3614",
  "status": "success",
  "total_duration_s": 20.9,
  "stages": {
    "build_vector_store": {
      "status": "success",
      "duration_s": 3.13,
      "metadata": {
        "chunk_count": 24,
        "embedding_model": "text-embedding-3-small",
        "index_path": "data/faiss_index"
      }
    }
  }
}
```

---

## LangSmith Tracing

When `LANGCHAIN_TRACING_V2=true`, every pipeline run is captured in the [LangSmith UI](https://smith.langchain.com) under the **qa-agent** project.

### What is traced

```
Q&A Pipeline [2a3a3614]          ← parent run (main.py)
├── stage_generate_pdf           ← @traceable  tag: ingestion
├── stage_extract_text           ← @traceable  tag: ingestion
├── stage_split_text             ← @traceable  tag: ingestion
├── stage_build_vector_store     ← @traceable  tag: retrieval
├── stage_generate_questions     ← @traceable  tag: generation, llm
│   ├── generate_questions       ← @traceable  tag: qa-generation, llm
│   └── ChatOpenAI               ← auto-traced by LCEL
│       ├── ChatPromptTemplate   ← auto-traced
│       └── StrOutputParser      ← auto-traced
├── stage_format_markdown        ← @traceable  tag: output
└── stage_convert_to_pdf         ← @traceable  tag: output
```

### Per-run metadata visible in LangSmith

- `pipeline_id` — unique 8-char run ID for correlation with local logs
- `model` — e.g. `gpt-4o`
- `num_questions` — e.g. `10`
- Full prompt sent to GPT-4o
- Full LLM response
- Token usage (prompt tokens, completion tokens, total)
- Per-call latency

### Enabling tracing

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=qa-agent
```

When disabled (default), `contextlib.nullcontext()` is used — zero performance overhead.
