"""
src/retrieval/embeddings_store.py
──────────────────────────────────
Manages the FAISS vector store lifecycle:
  • Split clean text into overlapping chunks
  • Embed chunks with OpenAI text-embedding-3-small
  • Persist the FAISS index to disk for reuse across runs
  • Expose a similarity-search retriever for downstream Q&A

Why FAISS?
──────────
FAISS (Facebook AI Similarity Search) is a battle-tested, CPU-efficient
approximate nearest-neighbour library.  For document collections up to
millions of chunks it provides millisecond query times without requiring a
running server (unlike Pinecone, Weaviate, or Qdrant).  The entire index
lives in a local directory — perfect for a self-contained pipeline.

Why text-embedding-3-small?
───────────────────────────
At 1,536 dimensions it delivers strong retrieval quality while being
significantly cheaper and faster than text-embedding-ada-002 or
text-embedding-3-large.  For a single PDF source document the quality
difference vs. the larger model is negligible.

Why overlapping chunks?
───────────────────────
RecursiveCharacterTextSplitter produces chunks of ~1,000 characters with a
200-character overlap.  The overlap ensures that sentences spanning a chunk
boundary are fully captured in at least one chunk, preventing fragmented
context being sent to the LLM.

Public API
──────────
    split_text(text)                    → list[Document]
    build_vector_store(chunks)          → FAISS
    load_vector_store()                 → FAISS
    get_retriever(vector_store, k)      → VectorStoreRetriever
    get_all_documents(vector_store)     → list[Document]
"""

import os
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from observability.logger import get_logger

logger = get_logger(__name__)

# Lazy singleton — HuggingFaceEmbeddings is NOT imported at module level to
# avoid the sentence-transformers → transformers → heavy import chain running
# in a background worker thread (causes a Windows hang on first import).
_embeddings = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        # Set env vars before the first import of langchain_huggingface
        os.environ["USE_TORCH"] = "1"
        os.environ["USE_TF"]    = "0"
        os.environ.setdefault("HF_HUB_OFFLINE",       "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE",  "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM","false")
        from langchain_huggingface import HuggingFaceEmbeddings  # noqa: PLC0415
        _embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


# ─── Text splitting ────────────────────────────────────────────────────────────

def split_text(text: str) -> list[Document]:
    """
    Splits cleaned text into overlapping LangChain Document chunks.

    Splitter strategy
    ──────────────────
    RecursiveCharacterTextSplitter tries each separator in the provided list
    in order, falling back to the next one only if the chunk would still
    exceed chunk_size.  Our separator priority:

      1. "\\n\\n"  — paragraph boundary (strongest semantic break)
      2. "\\n"     — line break (weaker, intra-paragraph)
      3. ". "      — sentence boundary (preserves readable sentences)
      4. " "       — word boundary (last resort before hard character split)
      5. ""        — hard character split (fallback, rare)

    This hierarchy maximises the semantic coherence of each chunk, which
    directly improves retrieval precision.

    chunk_size vs. chunk_overlap
    ─────────────────────────────
    config.CHUNK_SIZE  (default 1000) is measured in characters, not tokens.
    OpenAI's text-embedding-3-small has an 8,191-token context limit; 1,000
    characters is roughly 250 tokens — well within the limit while being
    large enough to give the LLM meaningful context.

    config.CHUNK_OVERLAP (default 200) causes a 200-character sliding window
    so boundary sentences appear in both their preceding and following chunks.

    Args:
        text: Cleaned text from pdf_extractor.clean_text().

    Returns:
        List of LangChain Document objects, each with page_content populated
        and an empty metadata dict.

    Raises:
        ValueError: If the input text is empty.
    """
    if not text.strip():
        raise ValueError("Cannot split empty text.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        # Priority-ordered separators — see module docstring for rationale
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    # split_text returns plain strings; create_documents wraps them in
    # Document objects, which is the type expected by FAISS.from_documents().
    chunks: list[Document] = splitter.create_documents([text])

    logger.info(
        "Split text into %d chunks (chunk_size=%d, overlap=%d)",
        len(chunks),
        config.CHUNK_SIZE,
        config.CHUNK_OVERLAP,
        extra={
            "num_chunks":    len(chunks),
            "chunk_size":    config.CHUNK_SIZE,
            "chunk_overlap": config.CHUNK_OVERLAP,
        },
    )
    return chunks


# ─── Vector store construction ─────────────────────────────────────────────────

def build_vector_store(chunks: list[Document]) -> FAISS:
    """
    Embeds *chunks* and stores them in a FAISS vector index on disk.

    Persistence strategy
    ─────────────────────
    FAISS.save_local(path) writes two files:
      • index.faiss  — the binary ANN index (vectors + graph structure)
      • index.pkl    — a pickle of the LangChain docstore (text + metadata)

    Both files must remain co-located for load_vector_store() to work.
    The directory is defined in config.FAISS_INDEX_PATH.

    Embedding cost
    ──────────────
    This function calls the OpenAI Embeddings API once per batch (LangChain
    batches the chunks internally).  For a typical single PDF (~50 chunks)
    this costs fractions of a cent.  For larger corpora consider a local
    embedding model to avoid API costs.

    Args:
        chunks: Documents produced by split_text().

    Returns:
        The in-memory FAISS vector store (also persisted to disk).

    Raises:
        ValueError: If chunks list is empty.
        openai.APIError: On OpenAI API failure.
    """
    if not chunks:
        raise ValueError("Cannot build a vector store from an empty chunk list.")

    embeddings = _get_embeddings()

    logger.info(
        "Building FAISS vector store from %d chunks using model '%s' …",
        len(chunks),
        config.EMBEDDING_MODEL,
        extra={"num_chunks": len(chunks), "embedding_model": config.EMBEDDING_MODEL},
    )

    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_store.save_local(str(config.FAISS_INDEX_PATH))

    logger.info(
        "FAISS index persisted to %s",
        config.FAISS_INDEX_PATH,
        extra={"index_path": str(config.FAISS_INDEX_PATH)},
    )
    return vector_store


# ─── Vector store loading ──────────────────────────────────────────────────────

def load_vector_store() -> FAISS:
    """
    Loads a previously persisted FAISS index from disk.

    Security note on allow_dangerous_deserialization
    ─────────────────────────────────────────────────
    LangChain's FAISS.load_local() uses pickle (via index.pkl) to restore the
    docstore.  Because arbitrary code can be embedded in a pickle file,
    LangChain requires explicit opt-in via allow_dangerous_deserialization=True.

    This is SAFE here because:
      1. The pickle file was created in the same pipeline run by build_vector_store().
      2. The file is stored locally under a project-controlled directory.
      3. No untrusted third party has write access to config.FAISS_INDEX_PATH.

    In a production environment where the index file might come from an
    external source, you should use a safer serialisation format or verify
    the file's integrity (checksum/signature) before loading.

    Returns:
        Loaded FAISS vector store, ready for similarity searches.

    Raises:
        FileNotFoundError: If the index files do not exist on disk.
    """
    index_path = config.FAISS_INDEX_PATH
    if not (index_path / "index.faiss").exists():
        raise FileNotFoundError(
            f"FAISS index not found at {index_path}. "
            "Run the pipeline first to generate the index."
        )

    embeddings = _get_embeddings()

    vector_store = FAISS.load_local(
        str(index_path),
        embeddings,
        allow_dangerous_deserialization=True,  # intentional — see docstring
    )

    logger.info(
        "FAISS index loaded from %s",
        index_path,
        extra={"index_path": str(index_path)},
    )
    return vector_store


# ─── Retriever helpers ─────────────────────────────────────────────────────────

def get_retriever(vector_store: FAISS, k: int | None = None):
    """
    Wraps the FAISS vector store in a LangChain retriever.

    The retriever provides a standardised .invoke(query) interface used by
    LangChain expression chains (LCEL).  k controls how many chunks are
    returned per query — more chunks = more context but higher LLM cost.

    Args:
        vector_store: An in-memory FAISS instance.
        k: Number of chunks to return per query.  Defaults to config.TOP_K.

    Returns:
        VectorStoreRetriever configured for similarity search.
    """
    k = k if k is not None else config.TOP_K
    return vector_store.as_retriever(search_kwargs={"k": k})


def get_all_documents(vector_store: FAISS) -> list[Document]:
    """
    Returns ALL documents stored in the vector store as a flat list.

    This is used by the Q&A generator to run broad thematic queries —
    it needs to know the full corpus so it can sample topics evenly
    rather than biasing towards whichever chunk matches the first query.

    Implementation detail:
        FAISS.docstore._dict is the internal LangChain docstore dictionary
        keyed by UUID string.  Accessing it directly is an implementation
        detail of langchain-community; it may change in future versions.

    Args:
        vector_store: An in-memory FAISS instance.

    Returns:
        List of all Document objects in insertion order (arbitrary).
    """
    return list(vector_store.docstore._dict.values())
