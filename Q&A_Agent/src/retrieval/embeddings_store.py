"""
src/retrieval/embeddings_store.py
──────────────────────────────────
Manages the per-job FAISS vector store lifecycle:
  • Split clean text into overlapping chunks
  • Embed chunks with sentence-transformers/all-MiniLM-L6-v2 (local, free, fast)
  • Build an in-memory FAISS index for similarity search
  • Expose a retriever for downstream Q&A generation

Why FAISS?
──────────
FAISS (Facebook AI Similarity Search) is a CPU-efficient, zero-cost library
for approximate nearest-neighbour search.  It runs entirely in-memory — no
server, no network calls, no cost.  For per-job document collections (dozens
to hundreds of chunks) it provides sub-millisecond query times on a single CPU.

Each job creates its own isolated FAISS instance: built from the job's chunks,
queried during generation, then garbage-collected.  No shared state between
concurrent jobs; no disk persistence needed.

Why sentence-transformers/all-MiniLM-L6-v2?
────────────────────────────────────────────
384-dimensional dense embeddings.  Fast on CPU (50–200 ms for a typical
document), strong semantic retrieval quality, entirely free (runs locally,
no API key needed, model downloaded once at container startup).

Why overlapping chunks?
───────────────────────
RecursiveCharacterTextSplitter with ~1,000-char chunks and 200-char overlap
ensures sentences spanning chunk boundaries appear in at least one complete
chunk, preventing fragmented context reaching the LLM.

Public API
──────────
    split_text(text)                    → list[Document]
    build_vector_store(chunks)          → FAISS   (in-memory, per-job)
    get_retriever(vector_store, k)      → VectorStoreRetriever
    get_all_documents(vector_store)     → list[Document]
"""

import os

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from observability.logger import get_logger

logger = get_logger(__name__)

# Lazy singleton — importing HuggingFaceEmbeddings triggers the full
# sentence-transformers / transformers chain which is slow on first import.
# Deferring it avoids adding ~3 s to server startup.
_embeddings = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        # Suppress TF / tokenizer noise before importing heavy deps
        os.environ.setdefault("USE_TORCH",              "1")
        os.environ.setdefault("USE_TF",                 "0")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from langchain_huggingface import HuggingFaceEmbeddings  # noqa: PLC0415
        _embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL,           # all-MiniLM-L6-v2
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Embedding model loaded: %s", config.EMBEDDING_MODEL)
    return _embeddings


# ─── Text splitting ────────────────────────────────────────────────────────────

def split_text(text: str) -> list[Document]:
    """
    Split cleaned text into overlapping LangChain Document chunks.

    Separator priority (RecursiveCharacterTextSplitter):
      1. "\\n\\n"  paragraph break  (strongest semantic boundary)
      2. "\\n"     line break
      3. ". "      sentence boundary
      4. " "       word boundary
      5. ""        hard character split (last resort)

    Args:
        text: Cleaned plain text from the ingestion layer.

    Returns:
        List of Document objects ready for FAISS.from_documents().

    Raises:
        ValueError: If text is empty.
    """
    if not text.strip():
        raise ValueError("Cannot split empty text.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,       # default 1000 chars (~250 tokens)
        chunk_overlap=config.CHUNK_OVERLAP, # default 200 chars overlap
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[Document] = splitter.create_documents([text])

    logger.info(
        "Split text into %d chunks (size=%d, overlap=%d)",
        len(chunks), config.CHUNK_SIZE, config.CHUNK_OVERLAP,
        extra={"num_chunks": len(chunks), "chunk_size": config.CHUNK_SIZE,
               "chunk_overlap": config.CHUNK_OVERLAP},
    )
    return chunks


# ─── Vector store construction ─────────────────────────────────────────────────

def build_vector_store(chunks: list[Document]) -> FAISS:
    """
    Embed chunks and build an in-memory FAISS index for this job.

    The index is NOT persisted to disk — it lives only for the duration of
    the pipeline run (build → retrieve → generate → discard).  This avoids
    stale-index bugs and concurrent-write races when multiple jobs run in
    parallel on the same server.

    Args:
        chunks: Documents from split_text().

    Returns:
        In-memory FAISS vector store ready for similarity search.

    Raises:
        ValueError: If chunks is empty.
    """
    if not chunks:
        raise ValueError("Cannot build a vector store from an empty chunk list.")

    embeddings = _get_embeddings()

    logger.info(
        "Building FAISS index from %d chunks (model: %s) …",
        len(chunks), config.EMBEDDING_MODEL,
        extra={"num_chunks": len(chunks), "embedding_model": config.EMBEDDING_MODEL},
    )

    # FAISS.from_documents embeds all chunks in one batched call and builds
    # an IndexFlatL2 (exact L2 nearest-neighbour) index in memory.
    vector_store = FAISS.from_documents(chunks, embeddings)

    logger.info(
        "FAISS index ready — %d vectors, dim=%d",
        vector_store.index.ntotal,
        vector_store.index.d,
        extra={"num_vectors": vector_store.index.ntotal,
               "dim": vector_store.index.d},
    )
    return vector_store


# ─── Retriever helpers ─────────────────────────────────────────────────────────

def get_retriever(vector_store: FAISS, k: int | None = None):
    """
    Wrap the FAISS vector store in a LangChain retriever.

    Args:
        vector_store: In-memory FAISS instance from build_vector_store().
        k: Chunks to return per query.  Defaults to config.TOP_K_RETRIEVAL.

    Returns:
        VectorStoreRetriever with similarity search configured.
    """
    k = k if k is not None else config.TOP_K_RETRIEVAL
    return vector_store.as_retriever(search_kwargs={"k": k})


def get_all_documents(vector_store: FAISS) -> list[Document]:
    """
    Return ALL documents stored in the vector store as a flat list.

    Used by the Q&A generator to sample topics evenly across the full corpus
    rather than biasing retrieval towards the first query's nearest neighbours.

    Note: Accesses FAISS.docstore._dict which is a LangChain implementation
    detail; may need updating if langchain-community changes its internals.

    Args:
        vector_store: In-memory FAISS instance.

    Returns:
        List of all Document objects (arbitrary order).
    """
    return list(vector_store.docstore._dict.values())
