import os
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import pybreaker

from observability.logger import get_logger
from observability.breakers import pinecone_breaker

logger = get_logger("memory.pinecone")

pinecone_api_key = os.getenv("PINECONE_API_KEY")
openai_api_key   = os.getenv("OPENAI_API_KEY")
index_name       = os.getenv("PINECONE_INDEX", "default-index")

if pinecone_api_key and openai_api_key:
    pc = Pinecone(api_key=pinecone_api_key)
    embeddings = OpenAIEmbeddings(api_key=openai_api_key)
    try:
        index = pc.Index(index_name)
        logger.info("Pinecone index connected", extra={"index": index_name})
    except Exception:
        logger.warning("Pinecone index not found — running without vector memory", exc_info=True)
        index = None
else:
    pc = None
    embeddings = None
    index = None
    logger.warning("Pinecone/OpenAI keys not set — vector memory disabled")


@retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def retrieve_context(query: str) -> list[str]:
    if not (index and embeddings):
        return ["mock context"]

    try:
        def _query():
            vector = embeddings.embed_query(query)
            results = index.query(vector=vector, top_k=3, include_metadata=True)
            return [
                match.metadata["text"]
                for match in results.matches
                if match.metadata and "text" in match.metadata
            ]

        return pinecone_breaker.call(_query)
    except pybreaker.CircuitBreakerError:
        logger.error("Pinecone circuit breaker open — returning empty context")
        return ["context unavailable"]
    except Exception:
        logger.error("Pinecone query failed", exc_info=True)
        return ["context unavailable"]
