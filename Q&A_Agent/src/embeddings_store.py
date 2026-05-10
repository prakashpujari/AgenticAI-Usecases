"""
src/embeddings_store.py
───────────────────────
Handles:
  1. Splitting clean text into overlapping chunks (RecursiveCharacterTextSplitter)
  2. Creating OpenAI embeddings for each chunk
  3. Storing the embedded chunks in a FAISS vector store (persisted to disk)
  4. Loading a previously saved FAISS index
  5. Exposing a retriever for downstream Q&A use

Public API
──────────
    split_text(text)                    → list[Document]
    build_vector_store(chunks)          → FAISS
    load_vector_store()                 → FAISS
    get_retriever(vector_store, k)      → VectorStoreRetriever
    get_all_documents(vector_store)     → list[Document]
"""

import logging
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

logger = logging.getLogger(__name__)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_embeddings() -> OpenAIEmbeddings:
    """Instantiate OpenAIEmbeddings with the configured model and API key."""
    if not config.OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
    return OpenAIEmbeddings(
        model=config.OPENAI_EMBEDDING_MODEL,
        api_key=config.OPENAI_API_KEY,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def split_text(text: str) -> list[Document]:
    """
    Splits *text* into overlapping chunks using RecursiveCharacterTextSplitter.

    The splitter tries to split on paragraph boundaries first, then sentence
    boundaries, then word boundaries—preserving semantic coherence.

    Args:
        text: Cleaned document text.

    Returns:
        List of LangChain Document objects, each carrying the chunk text as
        ``page_content`` and a ``chunk_index`` metadata field.

    Raises:
        ValueError: If *text* is empty or too short to split meaningfully.
    """
    if not text or len(text.strip()) < 100:
        raise ValueError("Text is too short to produce meaningful chunks.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )

    chunks = splitter.create_documents([text])

    # Attach positional metadata for traceability
    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["char_count"] = len(chunk.page_content)

    logger.info(
        "Split text into %d chunks (chunk_size=%d, overlap=%d)",
        len(chunks),
        config.CHUNK_SIZE,
        config.CHUNK_OVERLAP,
    )
    return chunks


def build_vector_store(chunks: list[Document]) -> FAISS:
    """
    Creates a FAISS vector store from *chunks* and persists it to disk.

    Args:
        chunks: List of Document chunks produced by split_text().

    Returns:
        Populated FAISS vector store.

    Raises:
        ValueError: If *chunks* is empty.
        EnvironmentError: If OPENAI_API_KEY is missing.
    """
    if not chunks:
        raise ValueError("Cannot build a vector store from an empty chunk list.")

    logger.info("Creating embeddings for %d chunks …", len(chunks))
    embeddings = _get_embeddings()

    vector_store = FAISS.from_documents(chunks, embeddings)

    # Persist to disk so we can reload without re-embedding
    config.FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(config.FAISS_INDEX_PATH))

    logger.info("FAISS index saved to: %s", config.FAISS_INDEX_PATH)
    return vector_store


def load_vector_store() -> FAISS:
    """
    Loads a previously saved FAISS vector store from disk.

    Returns:
        Loaded FAISS vector store.

    Raises:
        FileNotFoundError: If no saved index exists at FAISS_INDEX_PATH.
        EnvironmentError: If OPENAI_API_KEY is missing.
    """
    index_dir = Path(config.FAISS_INDEX_PATH)
    index_file = index_dir / "index.faiss"
    if not index_file.exists():
        raise FileNotFoundError(
            f"No FAISS index found at '{index_dir}'. "
            "Run the pipeline at least once to build the index."
        )

    embeddings = _get_embeddings()
    vector_store = FAISS.load_local(
        str(index_dir),
        embeddings,
        allow_dangerous_deserialization=True,  # Safe: we wrote this file ourselves
    )
    logger.info("FAISS index loaded from: %s", index_dir)
    return vector_store


def get_retriever(vector_store: FAISS, k: int | None = None):
    """
    Creates a similarity-search retriever from *vector_store*.

    Args:
        vector_store: Populated FAISS instance.
        k: Number of chunks to retrieve per query. Defaults to TOP_K_RETRIEVAL.

    Returns:
        VectorStoreRetriever configured for similarity search.
    """
    k = k or config.TOP_K_RETRIEVAL
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )
    logger.info("Retriever created with k=%d", k)
    return retriever


def get_all_documents(vector_store: FAISS) -> list[Document]:
    """
    Returns every document stored in the FAISS index.

    Useful when the document is small enough to pass entirely to the LLM.

    Args:
        vector_store: Populated FAISS instance.

    Returns:
        List of all Document objects in the store.
    """
    # FAISS stores docs in its docstore dict
    docs = list(vector_store.docstore._dict.values())
    logger.info("Retrieved all %d documents from FAISS store", len(docs))
    return docs


# ── Backward-compat re-export ─────────────────────────────────────────────────
# Canonical implementation moved to src/retrieval/embeddings_store.py.
from src.retrieval.embeddings_store import (  # noqa: F811, E402
    split_text,
    build_vector_store,
    load_vector_store,
    get_retriever,
    get_all_documents,
)
