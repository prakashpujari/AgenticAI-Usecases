"""
src/__init__.py
───────────────
Q&A Agent source package.

Sub-package layout
──────────────────
  src/ingestion/   — document loading, text extraction, PDF generation
  src/retrieval/   — text splitting + FAISS vector store
  src/generation/  — LangChain LCEL chain for MCQ generation + summarization
  src/output/      — Markdown formatter + PDF converter
  src/pipeline/    — LangGraph state machine (graph.py) + stage wrappers (stages.py)
"""
