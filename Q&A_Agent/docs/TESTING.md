# Q&A Agent — Test Cases & Execution Guide

## Table of Contents

1. [Test Strategy](#test-strategy)
2. [Setup](#setup)
3. [Unit Tests](#unit-tests)
   - [Document Loader](#1-document-loader)
   - [PDF Extractor](#2-pdf-extractor)
   - [Embeddings Store](#3-embeddings-store)
   - [QA Generator](#4-qa-generator)
   - [Output Formatter](#5-output-formatter)
   - [PDF Converter](#6-pdf-converter)
   - [Observability](#7-observability)
4. [Integration Tests](#integration-tests)
   - [Pipeline Stages](#8-pipeline-stages)
   - [API Server](#9-api-server)
5. [End-to-End Tests](#end-to-end-tests)
6. [Test Execution](#test-execution)
7. [Test Coverage Report](#test-coverage-report)

---

## Test Strategy

| Layer | What it tests | Mocks external calls? | File |
|-------|--------------|----------------------|------|
| **Unit** | Single function/class in isolation | Yes (OpenAI, filesystem) | `tests/unit/` |
| **Integration** | Module interactions, pipeline stages | Partially (OpenAI only) | `tests/integration/` |
| **E2E** | Full API + pipeline against live server | No | `test_e2e.py` |

---

## Setup

### Install test dependencies

```bash
pip install pytest pytest-asyncio pytest-cov httpx pytest-mock
```

### Directory structure

```
Q&A_Agent/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_document_loader.py
│   │   ├── test_pdf_extractor.py
│   │   ├── test_embeddings_store.py
│   │   ├── test_qa_generator.py
│   │   ├── test_output_formatter.py
│   │   ├── test_pdf_converter.py
│   │   └── test_observability.py
│   └── integration/
│       ├── __init__.py
│       ├── test_pipeline_stages.py
│       └── test_api_server.py
├── test_e2e.py              # Existing E2E suite
└── TESTING.md
```

### `tests/conftest.py`

```python
import pytest
import tempfile
import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory):
    """Creates a real minimal PDF for tests that need a file on disk."""
    p = tmp_path_factory.mktemp("data") / "test_doc.pdf"
    c = canvas.Canvas(str(p), pagesize=letter)
    c.drawString(100, 750, "Cloud computing enables scalable infrastructure.")
    c.drawString(100, 730, "IaaS provides virtualized compute resources on demand.")
    c.drawString(100, 710, "PaaS abstracts server management from developers.")
    c.showPage()
    c.save()
    return p


@pytest.fixture(scope="session")
def sample_txt(tmp_path_factory):
    p = tmp_path_factory.mktemp("data") / "test_doc.txt"
    p.write_text("Cloud computing enables scalable infrastructure.\n"
                 "IaaS provides virtualized compute resources on demand.\n"
                 "PaaS abstracts server management from developers.\n")
    return p


@pytest.fixture
def mock_openai_embeddings(mocker):
    """Patches OpenAIEmbeddings so no real API call is made."""
    import numpy as np
    mock = mocker.patch("langchain_openai.OpenAIEmbeddings")
    instance = mock.return_value
    instance.embed_documents.return_value = [
        np.random.rand(1536).tolist() for _ in range(5)
    ]
    instance.embed_query.return_value = np.random.rand(1536).tolist()
    return instance


@pytest.fixture
def mock_chat_openai(mocker):
    """Patches ChatOpenAI to return a canned MCQ string."""
    mock = mocker.patch("langchain_openai.ChatOpenAI")
    instance = mock.return_value
    instance.__or__ = lambda self, other: other  # make LCEL chain work
    return instance


SAMPLE_QUESTIONS = [
    {
        "question": "What is IaaS?",
        "options": {"A": "Infra as a Service", "B": "Infra as a Script",
                    "C": "Internet as a Service", "D": "Integration as a Service"},
        "correct_answer": "A",
        "explanation": "IaaS provides virtualized compute, storage and networking."
    }
]
```

---

## Unit Tests

### 1. Document Loader

**File:** `tests/unit/test_document_loader.py`

```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.ingestion.document_loader import load_document


class TestLoadDocumentTxt:
    def test_loads_plain_text_file(self, sample_txt):
        result = load_document(str(sample_txt))
        assert "Cloud computing" in result
        assert len(result) > 0

    def test_loads_pathlib_path(self, sample_txt):
        result = load_document(sample_txt)  # Path object, not str
        assert isinstance(result, str)

    def test_raises_for_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_document("/nonexistent/path/doc.txt")

    def test_raises_for_unsupported_extension(self, tmp_path):
        f = tmp_path / "doc.xyz"
        f.write_text("content")
        with pytest.raises(ValueError, match="Unsupported"):
            load_document(str(f))


class TestLoadDocumentPdf:
    def test_loads_pdf_returns_string(self, sample_pdf):
        result = load_document(str(sample_pdf))
        assert isinstance(result, str)
        assert len(result) > 10

    def test_pdf_content_extracted(self, sample_pdf):
        result = load_document(str(sample_pdf))
        assert "Cloud computing" in result or "scalable" in result


class TestLoadDocumentUrl:
    def test_loads_http_url(self):
        mock_html = "<html><body><p>Test article content here.</p></body></html>"
        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__ = lambda s: s
            mock_url.return_value.__exit__ = MagicMock(return_value=False)
            mock_url.return_value.read.return_value = mock_html.encode()
            result = load_document("http://example.com/article")
        assert "Test article content" in result

    def test_loads_youtube_url(self):
        mock_transcript = [{"text": "Welcome to this video"}, {"text": "about cloud computing"}]
        with patch("youtube_transcript_api.YouTubeTranscriptApi.get_transcript",
                   return_value=mock_transcript):
            result = load_document("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "Welcome to this video" in result
        assert "cloud computing" in result

    def test_youtube_transcript_api_missing(self):
        with patch.dict("sys.modules", {"youtube_transcript_api": None}):
            with pytest.raises(ImportError):
                load_document("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


class TestLoadDocumentDocx:
    def test_loads_docx(self, tmp_path):
        pytest.importorskip("docx")
        import docx
        d = docx.Document()
        d.add_paragraph("Cloud computing paragraph.")
        path = tmp_path / "test.docx"
        d.save(str(path))
        result = load_document(str(path))
        assert "Cloud computing" in result

    def test_docx_missing_raises_import_error(self, tmp_path):
        path = tmp_path / "test.docx"
        path.write_bytes(b"fake docx")
        with patch.dict("sys.modules", {"docx": None}):
            with pytest.raises(ImportError):
                load_document(str(path))


class TestLoadDocumentExcel:
    def test_loads_xlsx(self, tmp_path):
        pytest.importorskip("openpyxl")
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws["A1"] = "Header"
        ws["A2"] = "Cloud data"
        path = tmp_path / "test.xlsx"
        wb.save(str(path))
        result = load_document(str(path))
        assert "Cloud data" in result
```

---

### 2. PDF Extractor

**File:** `tests/unit/test_pdf_extractor.py`

```python
import pytest
from src.ingestion.pdf_extractor import extract_text, clean_text, extract_and_clean


class TestExtractText:
    def test_returns_string(self, sample_pdf):
        result = extract_text(sample_pdf)
        assert isinstance(result, str)

    def test_raises_for_missing_pdf(self):
        with pytest.raises(FileNotFoundError):
            extract_text("/nonexistent/file.pdf")

    def test_nonempty_for_valid_pdf(self, sample_pdf):
        result = extract_text(sample_pdf)
        assert len(result.strip()) > 0


class TestCleanText:
    def test_removes_hyphenated_line_breaks(self):
        raw = "knowl-\nedge is power"
        assert "knowledge" in clean_text(raw)

    def test_collapses_multiple_blank_lines(self):
        raw = "Para one.\n\n\n\n\nPara two."
        cleaned = clean_text(raw)
        assert "\n\n\n" not in cleaned

    def test_removes_standalone_page_numbers(self):
        raw = "Some text.\n1\nMore text."
        cleaned = clean_text(raw)
        assert cleaned.count("\n1\n") == 0

    def test_preserves_meaningful_content(self):
        raw = "Cloud computing is scalable."
        assert "Cloud computing is scalable" in clean_text(raw)

    def test_empty_string_returns_empty(self):
        assert clean_text("") == ""


class TestExtractAndClean:
    def test_pipeline_returns_string(self, sample_pdf):
        result = extract_and_clean(sample_pdf)
        assert isinstance(result, str)

    def test_pipeline_content_present(self, sample_pdf):
        result = extract_and_clean(sample_pdf)
        assert len(result) > 20
```

---

### 3. Embeddings Store

**File:** `tests/unit/test_embeddings_store.py`

```python
import pytest
from unittest.mock import MagicMock, patch
from langchain.schema import Document
from src.retrieval.embeddings_store import split_text, build_vector_store, load_vector_store


class TestSplitText:
    def test_returns_list_of_documents(self):
        text = "A " * 600 + ". " + "B " * 600
        chunks = split_text(text)
        assert isinstance(chunks, list)
        assert all(isinstance(c, Document) for c in chunks)

    def test_chunk_size_respected(self):
        text = "word " * 5000
        chunks = split_text(text, chunk_size=500, chunk_overlap=50)
        for chunk in chunks:
            assert len(chunk.page_content) <= 600  # allow minor overrun

    def test_empty_text_returns_empty_list(self):
        assert split_text("") == []

    def test_short_text_single_chunk(self):
        text = "Short content."
        chunks = split_text(text)
        assert len(chunks) == 1


class TestBuildVectorStore:
    def test_returns_faiss_store(self, mock_openai_embeddings, tmp_path):
        with patch("src.retrieval.embeddings_store.OpenAIEmbeddings",
                   return_value=mock_openai_embeddings):
            with patch("langchain_community.vectorstores.FAISS.from_documents") as mock_faiss:
                mock_faiss.return_value = MagicMock()
                docs = [Document(page_content="Cloud computing scales on demand.")]
                store = build_vector_store(docs, persist_path=tmp_path)
                mock_faiss.assert_called_once()

    def test_persists_index_to_disk(self, mock_openai_embeddings, tmp_path):
        mock_faiss_instance = MagicMock()
        with patch("src.retrieval.embeddings_store.OpenAIEmbeddings",
                   return_value=mock_openai_embeddings):
            with patch("langchain_community.vectorstores.FAISS.from_documents",
                       return_value=mock_faiss_instance):
                docs = [Document(page_content="Test content.")]
                build_vector_store(docs, persist_path=tmp_path)
                mock_faiss_instance.save_local.assert_called_once()


class TestLoadVectorStore:
    def test_raises_if_index_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_vector_store(tmp_path / "nonexistent")

    def test_loads_saved_index(self, mock_openai_embeddings, tmp_path):
        index_path = tmp_path / "faiss_index"
        index_path.mkdir()
        (index_path / "index.faiss").touch()
        (index_path / "index.pkl").touch()
        mock_faiss = MagicMock()
        with patch("langchain_community.vectorstores.FAISS.load_local",
                   return_value=mock_faiss):
            with patch("src.retrieval.embeddings_store.OpenAIEmbeddings",
                       return_value=mock_openai_embeddings):
                store = load_vector_store(index_path)
                assert store == mock_faiss
```

---

### 4. QA Generator

**File:** `tests/unit/test_qa_generator.py`

```python
import pytest
from unittest.mock import MagicMock, patch
from src.generation.qa_generator import generate_questions, validate_questions


VALID_LLM_RESPONSE = """
1. What is IaaS?
A) Infrastructure as a Service
B) Internet as a Service
C) Integration as a Script
D) Instance as a Service
Correct Answer: A
Explanation: IaaS provides virtualized compute, storage and networking resources.

2. What does PaaS abstract from developers?
A) Business logic
B) Server management
C) User authentication
D) Database queries
Correct Answer: B
Explanation: PaaS abstracts infrastructure concerns so developers focus on code.
"""


class TestValidateQuestions:
    def test_valid_questions_pass(self, SAMPLE_QUESTIONS):
        from tests.conftest import SAMPLE_QUESTIONS
        result = validate_questions(SAMPLE_QUESTIONS)
        assert result == SAMPLE_QUESTIONS

    def test_rejects_question_missing_correct_answer(self):
        bad = [{"question": "Q?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "explanation": "exp"}]
        with pytest.raises((ValueError, KeyError)):
            validate_questions(bad)

    def test_rejects_question_with_fewer_than_4_options(self):
        bad = [{"question": "Q?", "options": {"A": "a", "B": "b"},
                "correct_answer": "A", "explanation": "exp"}]
        with pytest.raises(ValueError):
            validate_questions(bad)


class TestGenerateQuestions:
    def test_returns_list_of_dicts(self, mock_chat_openai):
        mock_store = MagicMock()
        mock_store.as_retriever.return_value.get_relevant_documents.return_value = [
            MagicMock(page_content="Cloud computing scales.")
        ]
        with patch("src.generation.qa_generator.ChatOpenAI", return_value=mock_chat_openai):
            with patch("src.generation.qa_generator._parse_llm_output",
                       return_value=[{"question": "Q?", "options": {"A":"a","B":"b","C":"c","D":"d"},
                                      "correct_answer":"A", "explanation":"exp"}]):
                result = generate_questions(mock_store, num_questions=1)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_each_question_has_required_keys(self, mock_chat_openai):
        mock_store = MagicMock()
        mock_store.as_retriever.return_value.get_relevant_documents.return_value = [
            MagicMock(page_content="Test content.")
        ]
        required_keys = {"question", "options", "correct_answer", "explanation"}
        with patch("src.generation.qa_generator.ChatOpenAI", return_value=mock_chat_openai):
            with patch("src.generation.qa_generator._parse_llm_output",
                       return_value=[{"question":"Q?","options":{"A":"a","B":"b","C":"c","D":"d"},
                                      "correct_answer":"A","explanation":"exp"}]):
                result = generate_questions(mock_store, num_questions=1)
        for q in result:
            assert required_keys.issubset(q.keys()), f"Missing keys: {required_keys - q.keys()}"
```

---

### 5. Output Formatter

**File:** `tests/unit/test_output_formatter.py`

```python
import pytest
from src.output.output_formatter import format_questions_as_markdown


QUESTIONS = [
    {
        "question": "What is IaaS?",
        "options": {"A": "Infra as a Service", "B": "Internet as a Service",
                    "C": "Integration as a Script", "D": "Instance as a Service"},
        "correct_answer": "A",
        "explanation": "IaaS provides virtualized compute resources."
    },
    {
        "question": "What does PaaS abstract?",
        "options": {"A": "Business logic", "B": "Server management",
                    "C": "User auth", "D": "DB queries"},
        "correct_answer": "B",
        "explanation": "PaaS removes infrastructure concerns."
    }
]


class TestFormatQuestionsAsMarkdown:
    def test_returns_string(self):
        result = format_questions_as_markdown(QUESTIONS)
        assert isinstance(result, str)

    def test_contains_all_questions(self):
        result = format_questions_as_markdown(QUESTIONS)
        assert "What is IaaS?" in result
        assert "What does PaaS abstract?" in result

    def test_contains_all_options(self):
        result = format_questions_as_markdown(QUESTIONS)
        for opt in ["Infra as a Service", "Internet as a Service",
                    "Integration as a Script", "Instance as a Service"]:
            assert opt in result

    def test_marks_correct_answer(self):
        result = format_questions_as_markdown(QUESTIONS)
        assert "A" in result  # correct answer is visible

    def test_includes_explanation(self):
        result = format_questions_as_markdown(QUESTIONS)
        assert "virtualized compute resources" in result

    def test_empty_list_returns_empty_or_placeholder(self):
        result = format_questions_as_markdown([])
        assert isinstance(result, str)

    def test_question_numbering(self):
        result = format_questions_as_markdown(QUESTIONS)
        assert "1" in result
        assert "2" in result
```

---

### 6. PDF Converter

**File:** `tests/unit/test_pdf_converter.py`

```python
import pytest
from pathlib import Path
from src.output.pdf_converter import convert_markdown_to_pdf


SAMPLE_MARKDOWN = """# Q&A Output

## Question 1
**What is IaaS?**

- A) Infra as a Service ✓
- B) Internet as a Service
- C) Integration as a Script
- D) Instance as a Service

**Explanation:** IaaS provides virtualized compute resources.
"""


class TestConvertMarkdownToPdf:
    def test_creates_pdf_file(self, tmp_path):
        out_path = tmp_path / "output.pdf"
        convert_markdown_to_pdf(SAMPLE_MARKDOWN, str(out_path))
        assert out_path.exists()

    def test_pdf_is_nonempty(self, tmp_path):
        out_path = tmp_path / "output.pdf"
        convert_markdown_to_pdf(SAMPLE_MARKDOWN, str(out_path))
        assert out_path.stat().st_size > 500  # non-trivial PDF

    def test_pdf_starts_with_pdf_magic_bytes(self, tmp_path):
        out_path = tmp_path / "output.pdf"
        convert_markdown_to_pdf(SAMPLE_MARKDOWN, str(out_path))
        with open(out_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_raises_for_invalid_output_path(self):
        with pytest.raises((OSError, FileNotFoundError)):
            convert_markdown_to_pdf(SAMPLE_MARKDOWN, "/nonexistent/dir/output.pdf")
```

---

### 7. Observability

**File:** `tests/unit/test_observability.py`

```python
import pytest
import json
import time
from observability.metrics import PipelineMetrics


class TestPipelineMetrics:
    def test_stage_success_recorded(self):
        m = PipelineMetrics(pipeline_id="test-001")
        m.start_stage("extract_text")
        time.sleep(0.01)
        m.end_stage("extract_text", status="success", metadata={"char_count": 100})
        report = m.get_report()
        assert report["stages"]["extract_text"]["status"] == "success"
        assert report["stages"]["extract_text"]["duration_s"] > 0

    def test_stage_failure_recorded(self):
        m = PipelineMetrics(pipeline_id="test-002")
        m.start_stage("build_vector_store")
        m.end_stage("build_vector_store", status="failed", metadata={"error": "API timeout"})
        report = m.get_report()
        assert report["stages"]["build_vector_store"]["status"] == "failed"

    def test_total_duration_computed(self):
        m = PipelineMetrics(pipeline_id="test-003")
        m.start_stage("stage_a")
        time.sleep(0.02)
        m.end_stage("stage_a", status="success")
        report = m.get_report()
        assert report["total_duration_s"] >= 0.02

    def test_metadata_stored(self):
        m = PipelineMetrics(pipeline_id="test-004")
        m.start_stage("generate_questions")
        m.end_stage("generate_questions", status="success",
                    metadata={"model": "gpt-4o", "question_count": 10})
        report = m.get_report()
        assert report["stages"]["generate_questions"]["metadata"]["model"] == "gpt-4o"

    def test_json_serializable(self):
        m = PipelineMetrics(pipeline_id="test-005")
        m.start_stage("format_markdown")
        m.end_stage("format_markdown", status="success")
        report = m.get_report()
        json.dumps(report)  # must not raise

    def test_pipeline_id_in_report(self):
        m = PipelineMetrics(pipeline_id="abc-123")
        report = m.get_report()
        assert report["pipeline_id"] == "abc-123"
```

---

## Integration Tests

### 8. Pipeline Stages

**File:** `tests/integration/test_pipeline_stages.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from langchain.schema import Document
from src.pipeline.stages import (
    stage_extract_text,
    stage_split_text,
    stage_build_vector_store,
    stage_generate_questions,
    stage_format_markdown,
    stage_convert_to_pdf,
)
from observability.metrics import PipelineMetrics


@pytest.fixture
def metrics():
    return PipelineMetrics(pipeline_id="integ-test")


class TestStageExtractText:
    def test_extract_text_from_pdf(self, sample_pdf, metrics):
        text = stage_extract_text(str(sample_pdf), metrics)
        assert isinstance(text, str)
        assert len(text) > 10

    def test_records_metrics(self, sample_pdf, metrics):
        stage_extract_text(str(sample_pdf), metrics)
        report = metrics.get_report()
        assert "extract_text" in report["stages"]
        assert report["stages"]["extract_text"]["status"] == "success"

    def test_records_char_count_in_metadata(self, sample_pdf, metrics):
        stage_extract_text(str(sample_pdf), metrics)
        meta = metrics.get_report()["stages"]["extract_text"]["metadata"]
        assert "char_count" in meta
        assert meta["char_count"] > 0


class TestStageSplitText:
    def test_returns_documents(self, metrics):
        text = "word " * 2000
        chunks = stage_split_text(text, metrics)
        assert len(chunks) > 0
        assert all(isinstance(c, Document) for c in chunks)

    def test_records_chunk_count(self, metrics):
        text = "word " * 2000
        stage_split_text(text, metrics)
        meta = metrics.get_report()["stages"]["split_text"]["metadata"]
        assert meta["chunk_count"] > 0


class TestStageBuildVectorStore:
    def test_creates_vector_store(self, mock_openai_embeddings, metrics, tmp_path):
        docs = [Document(page_content="Cloud computing scales.")]
        mock_faiss = MagicMock()
        with patch("src.retrieval.embeddings_store.OpenAIEmbeddings",
                   return_value=mock_openai_embeddings):
            with patch("langchain_community.vectorstores.FAISS.from_documents",
                       return_value=mock_faiss):
                store = stage_build_vector_store(docs, metrics, persist_path=tmp_path)
        assert store is not None

    def test_records_embedding_model(self, mock_openai_embeddings, metrics, tmp_path):
        docs = [Document(page_content="Test.")]
        mock_faiss = MagicMock()
        with patch("src.retrieval.embeddings_store.OpenAIEmbeddings",
                   return_value=mock_openai_embeddings):
            with patch("langchain_community.vectorstores.FAISS.from_documents",
                       return_value=mock_faiss):
                stage_build_vector_store(docs, metrics, persist_path=tmp_path)
        meta = metrics.get_report()["stages"]["build_vector_store"]["metadata"]
        assert "embedding_model" in meta


class TestStageGenerateMarkdownPdf:
    def test_format_and_convert_pipeline(self, metrics, tmp_path):
        questions = [
            {"question": "Q?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
             "correct_answer": "A", "explanation": "Because A."}
        ]
        md = stage_format_markdown(questions, metrics)
        assert "Q?" in md

        out_pdf = tmp_path / "out.pdf"
        stage_convert_to_pdf(md, str(out_pdf), metrics)
        assert out_pdf.exists()
        assert out_pdf.stat().st_size > 100
```

---

### 9. API Server

**File:** `tests/integration/test_api_server.py`

```python
import pytest
import time
import io
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from fastapi.testclient import TestClient
from api.server import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_response_has_status_field(self, client):
        resp = client.get("/health")
        body = resp.json()
        assert "status" in body
        assert body["status"] == "healthy"

    def test_response_has_version_and_timestamp(self, client):
        resp = client.get("/health")
        body = resp.json()
        assert "version" in body
        assert "timestamp" in body


class TestGenerateEndpoint:
    def _make_pdf_bytes(self):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.drawString(100, 750, "Cloud computing overview.")
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()

    def test_submit_pdf_returns_pipeline_id(self, client):
        pdf_bytes = self._make_pdf_bytes()
        with patch("api.server._run_pipeline_job"):  # prevent real execution
            resp = client.post(
                "/api/qa/generate",
                files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
                data={"num_questions": "3"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "pipeline_id" in body
        assert len(body["pipeline_id"]) > 0

    def test_submit_returns_queued_status(self, client):
        pdf_bytes = self._make_pdf_bytes()
        with patch("api.server._run_pipeline_job"):
            resp = client.post(
                "/api/qa/generate",
                files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
                data={"num_questions": "3"},
            )
        assert resp.json()["status"] == "queued"

    def test_rejects_unsupported_file_type(self, client):
        resp = client.post(
            "/api/qa/generate",
            files={"file": ("test.exe", b"MZ", "application/octet-stream")},
            data={"num_questions": "3"},
        )
        assert resp.status_code in (400, 422)

    def test_rejects_missing_file(self, client):
        resp = client.post("/api/qa/generate", data={"num_questions": "3"})
        assert resp.status_code == 422


class TestStatusEndpoint:
    def test_unknown_pipeline_id_returns_404(self, client):
        resp = client.get("/api/qa/status/nonexistent-id-xyz")
        assert resp.status_code == 404

    def test_known_job_returns_status(self, client):
        pdf_bytes = b"%PDF-1.4 fake"
        with patch("api.server._run_pipeline_job"):
            submit = client.post(
                "/api/qa/generate",
                files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
                data={"num_questions": "1"},
            )
        pipeline_id = submit.json()["pipeline_id"]
        resp = client.get(f"/api/qa/status/{pipeline_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pipeline_id"] == pipeline_id
        assert body["status"] in ("queued", "processing", "completed", "failed")


class TestGenerateSourceEndpoint:
    def test_submit_url_returns_pipeline_id(self, client):
        with patch("api.server._run_pipeline_job"):
            resp = client.post(
                "/api/qa/generate-source",
                json={"source": "https://example.com/article", "num_questions": 3},
            )
        assert resp.status_code == 200
        assert "pipeline_id" in resp.json()

    def test_rejects_empty_source(self, client):
        resp = client.post(
            "/api/qa/generate-source",
            json={"source": "", "num_questions": 3},
        )
        assert resp.status_code in (400, 422)


class TestRateLimiting:
    def test_rate_limit_triggers_after_threshold(self, client):
        """Submit many requests rapidly; expect 429 eventually."""
        responses = []
        for _ in range(15):
            resp = client.post(
                "/api/qa/generate",
                files={"file": ("t.pdf", b"%PDF-fake", "application/pdf")},
                data={"num_questions": "1"},
            )
            responses.append(resp.status_code)
        assert 429 in responses, "Rate limiter never triggered"
```

---

## End-to-End Tests

The existing `test_e2e.py` covers the full live-server workflow. Run it against a running server:

```bash
# Terminal 1: start the API server
python start_server.py

# Terminal 2: run E2E tests
python test_e2e.py
```

### Additional E2E scenarios to add to `test_e2e.py`

```python
# Append these test cases to the existing test_e2e.py

def test_generate_source_youtube():
    """Submit a YouTube URL and poll until completion."""
    resp = requests.post(f"{BASE_URL}/api/qa/generate-source", json={
        "source": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "num_questions": 3
    })
    assert resp.status_code == 200
    pipeline_id = resp.json()["pipeline_id"]

    for _ in range(60):
        status = requests.get(f"{BASE_URL}/api/qa/status/{pipeline_id}").json()
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(3)

    assert status["status"] == "completed", f"Job failed: {status.get('error_message')}"


def test_download_pdf_after_completion(completed_pipeline_id):
    resp = requests.get(f"{BASE_URL}/api/qa/download/{completed_pipeline_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "download_url" in data

    file_resp = requests.get(f"{BASE_URL}{data['download_url']}")
    assert file_resp.status_code == 200
    assert file_resp.content[:5] == b"%PDF-"


def test_concurrent_submissions():
    """Submit 3 jobs simultaneously; all should be queued or completed."""
    import concurrent.futures

    def submit():
        return requests.post(
            f"{BASE_URL}/api/qa/generate",
            files={"file": ("doc.pdf", open("data/sample_document.pdf", "rb"), "application/pdf")},
            data={"num_questions": "2"},
        ).json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: submit(), range(3)))

    pipeline_ids = [r["pipeline_id"] for r in results]
    assert len(set(pipeline_ids)) == 3, "Each job should have a unique pipeline_id"
```

---

## Test Execution

### Run all unit tests

```bash
pytest tests/unit/ -v
```

### Run all integration tests

```bash
pytest tests/integration/ -v
```

### Run all tests with coverage

```bash
pytest tests/ --cov=src --cov=api --cov=observability \
       --cov-report=term-missing --cov-report=html
# Open htmlcov/index.html for the visual report
```

### Run a specific test file

```bash
pytest tests/unit/test_document_loader.py -v
```

### Run a specific test class or case

```bash
pytest tests/unit/test_document_loader.py::TestLoadDocumentUrl -v
pytest tests/unit/test_document_loader.py::TestLoadDocumentUrl::test_loads_http_url -v
```

### Run with output (no capture)

```bash
pytest tests/ -v -s
```

### Run only fast tests (skip slow integration)

```bash
pytest tests/unit/ -v -m "not slow"
```

### CI-friendly one-liner

```bash
pytest tests/ -q --tb=short --cov=src --cov=api --cov-fail-under=70
```

---

## Test Coverage Report

Target coverage thresholds:

| Module | Target |
|--------|--------|
| `src/ingestion/document_loader.py` | 85% |
| `src/ingestion/pdf_extractor.py` | 90% |
| `src/retrieval/embeddings_store.py` | 80% |
| `src/generation/qa_generator.py` | 75% |
| `src/output/output_formatter.py` | 90% |
| `src/output/pdf_converter.py` | 85% |
| `src/pipeline/stages.py` | 80% |
| `api/server.py` | 75% |
| `observability/metrics.py` | 90% |

### Generate HTML coverage report

```bash
pytest tests/ --cov=src --cov=api --cov=observability \
       --cov-report=html:coverage_report
# Then open coverage_report/index.html
```

---

## Quick Reference — Pytest Markers

Add these markers to `pytest.ini` or `pyproject.toml`:

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
markers =
    slow: marks tests as slow (run with -m slow)
    integration: marks integration tests
    e2e: marks end-to-end tests requiring a live server
```

Usage:

```bash
pytest tests/ -m "not slow"          # skip slow tests
pytest tests/ -m "integration"       # only integration
pytest test_e2e.py -m "e2e"          # only E2E
```
