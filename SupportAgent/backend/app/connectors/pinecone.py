"""
Pinecone Vector Database Connector - Store and search incident knowledge base
"""

import os
import logging
from typing import Optional, List, Dict
import httpx
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class PineconeConnector:
    """Connector to integrate with Pinecone vector database"""

    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY", "")
        self.host = os.getenv("PINECONE_HOST", "")
        self.index = os.getenv("PINECONE_INDEX", "aiops-knowledge-base")
        self.environment = os.getenv("PINECONE_ENVIRONMENT", "")
        self.enabled = bool(self.api_key and self.host)

        if self.enabled:
            logger.info(f"Pinecone connector initialized: {self.host}")
            self.base_url = self.host
            self.headers = {
                "Api-Key": self.api_key,
                "Content-Type": "application/json"
            }
        else:
            logger.warning("Pinecone connector disabled: Missing API key or host")

    async def upsert_vectors(
        self,
        vectors: List[Dict],
        namespace: str = "incidents"
    ) -> bool:
        """
        Upsert vectors into Pinecone

        Args:
            vectors: List of vectors with id, values, and metadata
            namespace: Pinecone namespace for organizing data

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.warning("Pinecone disabled, skipping upsert")
            return False

        try:
            payload = {
                "vectors": vectors,
                "namespace": namespace
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/vectors/upsert",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code in (200, 201):
                    logger.info(f"Upserted {len(vectors)} vectors to Pinecone")
                    return True
                else:
                    logger.error(f"Pinecone upsert error: {response.status_code} - {response.text}")
                    return False

        except Exception as error:
            logger.error(f"Error upserting vectors: {str(error)}")
            return False

    async def query_vectors(
        self,
        query_vector: List[float],
        top_k: int = 5,
        namespace: str = "incidents",
        filter: Optional[Dict] = None
    ) -> Optional[List[Dict]]:
        """
        Query similar vectors from Pinecone

        Args:
            query_vector: Query vector (embedding)
            top_k: Number of results to return
            namespace: Pinecone namespace
            filter: Metadata filter

        Returns:
            List of similar vectors with metadata
        """
        if not self.enabled:
            logger.warning("Pinecone disabled, skipping query")
            return None

        try:
            payload = {
                "vector": query_vector,
                "topK": top_k,
                "namespace": namespace,
                "includeMetadata": True
            }

            if filter:
                payload["filter"] = filter

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/query",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    matches = result.get("matches", [])
                    logger.info(f"Found {len(matches)} similar vectors")
                    return matches
                else:
                    logger.error(f"Pinecone query error: {response.status_code}")
                    return None

        except Exception as error:
            logger.error(f"Error querying vectors: {str(error)}")
            return None

    async def store_incident_knowledge(
        self,
        incident_id: str,
        incident_title: str,
        incident_description: str,
        rca_analysis: str,
        embedding: List[float],
        severity: str = "MEDIUM",
        tags: List[str] = None
    ) -> bool:
        """
        Store incident knowledge as vectors for future RCA lookups

        Args:
            incident_id: Internal incident ID
            incident_title: Incident title
            incident_description: Full description
            rca_analysis: Root cause analysis result
            embedding: Vector embedding (1536 dimensions for OpenAI)
            severity: Incident severity
            tags: Related tags for filtering

        Returns:
            True if stored successfully
        """
        if not self.enabled:
            return False

        try:
            vector_entry = {
                "id": f"incident-{incident_id}",
                "values": embedding,
                "metadata": {
                    "incident_id": incident_id,
                    "title": incident_title,
                    "description": incident_description,
                    "rca_analysis": rca_analysis,
                    "severity": severity,
                    "tags": tags or [],
                    "stored_at": datetime.utcnow().isoformat(),
                    "type": "incident"
                }
            }

            vectors = [vector_entry]
            return await self.upsert_vectors(vectors, namespace="incidents")

        except Exception as error:
            logger.error(f"Error storing incident knowledge: {str(error)}")
            return False

    async def find_similar_incidents(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> Optional[List[Dict]]:
        """
        Find similar historical incidents for RCA reference

        Args:
            query_embedding: Query vector embedding
            top_k: Number of similar incidents to return
            min_similarity: Minimum similarity score (0-1)

        Returns:
            List of similar incidents with their RCA results
        """
        if not self.enabled:
            return None

        try:
            matches = await self.query_vectors(
                query_vector=query_embedding,
                top_k=top_k,
                namespace="incidents",
                filter={"type": {"$eq": "incident"}}
            )

            if not matches:
                return None

            # Filter by similarity score
            similar_incidents = []
            for match in matches:
                score = match.get("score", 0)
                if score >= min_similarity:
                    metadata = match.get("metadata", {})
                    similar_incidents.append({
                        "incident_id": metadata.get("incident_id"),
                        "title": metadata.get("title"),
                        "rca_analysis": metadata.get("rca_analysis"),
                        "severity": metadata.get("severity"),
                        "similarity_score": score,
                        "stored_at": metadata.get("stored_at")
                    })

            logger.info(f"Found {len(similar_incidents)} similar incidents")
            return similar_incidents if similar_incidents else None

        except Exception as error:
            logger.error(f"Error finding similar incidents: {str(error)}")
            return None

    async def store_knowledge_article(
        self,
        article_id: str,
        title: str,
        content: str,
        category: str,
        embedding: List[float],
        tags: List[str] = None
    ) -> bool:
        """
        Store knowledge base article for RCA reference

        Args:
            article_id: Unique article ID
            title: Article title
            content: Article content
            category: Article category (e.g., "networking", "database")
            embedding: Vector embedding
            tags: Search tags

        Returns:
            True if stored successfully
        """
        if not self.enabled:
            return False

        try:
            vector_entry = {
                "id": f"kb-{article_id}",
                "values": embedding,
                "metadata": {
                    "article_id": article_id,
                    "title": title,
                    "content": content,
                    "category": category,
                    "tags": tags or [],
                    "stored_at": datetime.utcnow().isoformat(),
                    "type": "knowledge_article"
                }
            }

            vectors = [vector_entry]
            return await self.upsert_vectors(vectors, namespace="knowledge_base")

        except Exception as error:
            logger.error(f"Error storing knowledge article: {str(error)}")
            return False

    async def search_knowledge_base(
        self,
        query_embedding: List[float],
        top_k: int = 3,
        category: Optional[str] = None
    ) -> Optional[List[Dict]]:
        """
        Search knowledge base for relevant articles

        Args:
            query_embedding: Query vector embedding
            top_k: Number of results
            category: Optional category filter

        Returns:
            List of relevant knowledge articles
        """
        if not self.enabled:
            return None

        try:
            filter_obj = {"type": {"$eq": "knowledge_article"}}
            if category:
                filter_obj["category"] = {"$eq": category}

            matches = await self.query_vectors(
                query_vector=query_embedding,
                top_k=top_k,
                namespace="knowledge_base",
                filter=filter_obj
            )

            if not matches:
                return None

            articles = []
            for match in matches:
                metadata = match.get("metadata", {})
                articles.append({
                    "article_id": metadata.get("article_id"),
                    "title": metadata.get("title"),
                    "content": metadata.get("content"),
                    "category": metadata.get("category"),
                    "relevance_score": match.get("score", 0)
                })

            return articles if articles else None

        except Exception as error:
            logger.error(f"Error searching knowledge base: {str(error)}")
            return None

    async def delete_vector(self, vector_id: str, namespace: str = "incidents") -> bool:
        """Delete a vector"""
        if not self.enabled:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/vectors/delete",
                    json={"ids": [vector_id], "namespace": namespace},
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code in (200, 204)
        except Exception as error:
            logger.error(f"Error deleting vector: {str(error)}")
            return False

    async def health_check(self) -> Dict:
        """Check Pinecone connector health"""
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "Pinecone connector not configured"
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/describe_index_stats",
                    headers=self.headers,
                    timeout=10.0
                )

                if response.status_code == 200:
                    stats = response.json()
                    return {
                        "status": "healthy",
                        "host": self.host,
                        "index": self.index,
                        "total_vectors": stats.get("total_vector_count", 0),
                        "namespaces": list(stats.get("namespaces", {}).keys())
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}",
                        "host": self.host
                    }

        except Exception as error:
            return {
                "status": "error",
                "error": str(error),
                "host": self.host
            }
