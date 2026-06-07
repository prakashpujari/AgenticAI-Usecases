from typing import Any
from loguru import logger
from app.core.config import settings


class PineconeService:
    def __init__(self) -> None:
        self.api_key = settings.pinecone_api_key
        self.environment = settings.pinecone_environment
        self.index_name = settings.pinecone_index

    async def upsert_embeddings(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        logger.debug("Pinecone upsert %d items", len(items))
        return {"upserted_count": len(items)}

    async def query_semantic(self, vector: list[float], top_k: int = 20) -> list[dict[str, Any]]:
        logger.debug("Pinecone semantic query top_k=%d", top_k)
        return []
