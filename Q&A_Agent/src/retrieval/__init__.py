"""
src/retrieval/__init__.py
─────────────────────────
Retrieval sub-package.

Responsible for:
  • Splitting clean text into overlapping chunks for RAG
  • Creating OpenAI embeddings and storing them in a FAISS vector store
  • Persisting and loading the FAISS index to/from disk
  • Exposing a similarity-search retriever for downstream Q&A use
"""
