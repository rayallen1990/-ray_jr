"""Vector store interface and Qdrant implementation"""

from typing import List, Dict, Any, Protocol
from dataclasses import dataclass


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
        """Add documents to the vector store"""
        ...

    def search(
        self, query_vector: List[float], namespace: str, top_k: int = 5
    ) -> List[VectorDocument]:
        """Search for similar documents"""
        ...

    def delete(self, doc_ids: List[str], namespace: str) -> None:
        """Delete documents by ID"""
        ...


class QdrantVectorStore:
    """Qdrant vector database implementation"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError:
                raise ImportError("qdrant-client required: pip install qdrant-client")
            self._client = QdrantClient(host=self.host, port=self.port)
        return self._client

    def add(self, documents: List[VectorDocument], namespace: str) -> None:
        """Add documents to Qdrant collection (namespace)"""
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(id=doc.id, vector=doc.vector, payload={"text": doc.text, **doc.metadata})
            for doc in documents
        ]
        self.client.upsert(collection_name=namespace, points=points)

    def search(
        self, query_vector: List[float], namespace: str, top_k: int = 5
    ) -> List[VectorDocument]:
        """Search Qdrant for similar vectors"""
        results = self.client.search(
            collection_name=namespace, query_vector=query_vector, limit=top_k
        )
        return [
            VectorDocument(
                id=str(hit.id),
                text=hit.payload.get("text", ""),
                vector=hit.vector or [],
                metadata={k: v for k, v in hit.payload.items() if k != "text"},
            )
            for hit in results
        ]

    def delete(self, doc_ids: List[str], namespace: str) -> None:
        """Delete documents from Qdrant"""
        self.client.delete(collection_name=namespace, points_selector=doc_ids)
