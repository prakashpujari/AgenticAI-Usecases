"""
src/__init__.py
───────────────
Q&A Agent source package — top-level namespace.

Sub-package layout (new canonical structure)
────────────────────────────────────────────
  src/ingestion/     — PDF creation (pdf_generator) and text extraction (pdf_extractor)
  src/retrieval/     — Text splitting + FAISS vector store (embeddings_store)
  src/generation/    — LangChain LCEL chain for MCQ generation (qa_generator)
  src/output/        — Markdown formatter (output_formatter) + PDF converter (pdf_converter)
  src/pipeline/      — Stage orchestration layer with PipelineMetrics (stages)

Backward-compat flat imports (still work after the modular refactor)
─────────────────────────────────────────────────────────────────────
    from src.pdf_generator   import create_sample_pdf
    from src.pdf_extractor   import extract_and_clean
    from src.embeddings_store import split_text, build_vector_store
    from src.qa_generator    import generate_questions
    from src.output_formatter import format_questions_to_markdown
    from src.pdf_converter   import convert_markdown_to_pdf

Each of those flat modules now re-exports from the new canonical location,
so legacy callers get the observability-instrumented implementations.
"""
