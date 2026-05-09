"""Vector store interface and Qdrant implementation with Redis caching"""

import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """Represents a document with vector embedding"""
    id: str
    text: str
    vector: List[float]
    metadata: Dict[str, Any]


class VectorStore(Protocol):
    """Protocol for vector store implementations"""

    def add(self, documents: List[VectorDocument], namespace: str) -> None:
        ...

    def search(
        self, query_vector: List[float], namespace: str, top_k: int = 5
    ) -> List[VectorDocument]:
        ...

    def delete(self, doc_ids: List[str], namespace: str) -> None:
        ...


class QdrantVectorStore:
    """Qdrant vector database implementation with optional Redis caching"""

    def __init__(
        self,
        host: str,
        port: int,
        redis_url: Optional[str] = None,
        cache_ttl: int = 300,
    ):
        self.host = host
        self.port = port
        self.cache_ttl = cache_ttl
        self._client = None
        self._redis = None
        if redis_url:
            self._init_redis(redis_url)

    def _init_redis(self, redis_url: str) -> None:
        try:
            import redis
            self._redis = redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("Redis cache connected: %s", redis_url)
        except Exception as e:
            logger.warning("Redis unavailable, caching disabled: %s", e)
            self._redis = None

    @property
    def client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError:
                raise ImportError("qdrant-client required: pip install qdrant-client")
            try:
                self._client = QdrantClient(host=self.host, port=self.port)
            except Exception as e:
                logger.error("Qdrant connection failed: %s", e)
                raise ConnectionError(f"Cannot connect to Qdrant at {self.host}:{self.port}: {e}")
        return self._client

    def _cache_key(self, query_vector: List[float], namespace: str, top_k: int) -> str:
        digest = hashlib.md5(json.dumps(query_vector, separators=(",", ":")).encode()).hexdigest()
        return f"vs:{namespace}:{top_k}:{digest}"

    def _from_cache(self, key: str) -> Optional[List[VectorDocument]]:
        if self._redis is None:
            return None
        try:
            data = self._redis.get(key)
            if data:
                logger.debug("Cache hit: %s", key)
                return [VectorDocument(**d) for d in json.loads(data)]
        except Exception as e:
            logger.warning("Cache read error: %s", e)
        return None

    def _to_cache(self, key: str, docs: List[VectorDocument]) -> None:
        if self._redis is None:
            return
        try:
            payload = json.dumps([
                {"id": d.id, "text": d.text, "vector": d.vector, "metadata": d.metadata}
                for d in docs
            ])
            self._redis.setex(key, self.cache_ttl, payload)
        except Exception as e:
            logger.warning("Cache write error: %s", e)

    def add(self, documents: List[VectorDocument], namespace: str) -> None:
        """Add documents to Qdrant collection (namespace)"""
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(id=doc.id, vector=doc.vector, payload={"text": doc.text, **doc.metadata})
            for doc in documents
        ]
        try:
            self.client.upsert(collection_name=namespace, points=points)
            logger.info("Added %d documents to namespace '%s'", len(documents), namespace)
        except Exception as e:
            logger.error("Failed to add documents to Qdrant: %s", e)
            raise

    def search(
        self, query_vector: List[float], namespace: str, top_k: int = 5
    ) -> List[VectorDocument]:
        """Search Qdrant for similar vectors, with Redis cache"""
        cache_key = self._cache_key(query_vector, namespace, top_k)
        cached = self._from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            results = self.client.search(
                collection_name=namespace, query_vector=query_vector, limit=top_k
            )
        except Exception as e:
            logger.error("Qdrant search failed for namespace '%s': %s", namespace, e)
            raise ConnectionError(f"Vector search failed: {e}")

        docs = [
            VectorDocument(
                id=str(hit.id),
                text=hit.payload.get("text", ""),
                vector=hit.vector or [],
                metadata={k: v for k, v in hit.payload.items() if k != "text"},
            )
            for hit in results
        ]
        self._to_cache(cache_key, docs)
        return docs

    def delete(self, doc_ids: List[str], namespace: str) -> None:
        """Delete documents from Qdrant"""
        try:
            self.client.delete(collection_name=namespace, points_selector=doc_ids)
            logger.info("Deleted %d documents from namespace '%s'", len(doc_ids), namespace)
        except Exception as e:
            logger.error("Failed to delete documents: %s", e)
            raise
