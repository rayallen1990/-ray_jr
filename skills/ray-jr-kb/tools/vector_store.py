"""Vector store tool - wraps packages/vector_store for Skill use.

Provides simplified functions for Qdrant vector database operations.
"""

import logging
from typing import List, Dict, Any, Optional

from vector_store import QdrantVectorStore, VectorDocument

logger = logging.getLogger(__name__)

_store: Optional[QdrantVectorStore] = None


def init_qdrant(host: str = "localhost", port: int = 6333) -> QdrantVectorStore:
    """Initialize and return a Qdrant vector store client.

    Args:
        host: Qdrant server host (default "localhost").
        port: Qdrant server port (default 6333).

    Returns:
        Configured QdrantVectorStore instance.
    """
    global _store
    _store = QdrantVectorStore(host=host, port=port)
    logger.info("Initialized Qdrant client: %s:%d", host, port)
    return _store


def _get_store() -> QdrantVectorStore:
    """Get the current store instance, raising if not initialized."""
    if _store is None:
        raise RuntimeError("Vector store not initialized. Call init_qdrant() first.")
    return _store


async def index_documents(
    docs: List[Dict[str, Any]], namespace: str
) -> int:
    """Index documents into the vector store.

    Args:
        docs: List of dicts with keys: id, text, vector, metadata.
        namespace: Collection/namespace for tenant isolation.

    Returns:
        Number of documents indexed.

    Raises:
        RuntimeError: If vector store is not initialized.
        ValueError: If docs format is invalid.
    """
    store = _get_store()

    vector_docs = []
    for doc in docs:
        if not all(k in doc for k in ("id", "text", "vector")):
            raise ValueError("Each doc must have 'id', 'text', and 'vector' keys")
        vector_docs.append(
            VectorDocument(
                id=doc["id"],
                text=doc["text"],
                vector=doc["vector"],
                metadata=doc.get("metadata", {}),
            )
        )

    store.add(vector_docs, namespace=namespace)
    logger.info("Indexed %d documents into namespace '%s'", len(vector_docs), namespace)
    return len(vector_docs)


async def search_documents(
    query_vector: List[float], namespace: str, top_k: int = 5
) -> List[Dict[str, Any]]:
    """Search for similar documents by vector.

    Args:
        query_vector: Query embedding vector.
        namespace: Collection/namespace to search in.
        top_k: Number of results to return (default 5).

    Returns:
        List of matching documents as dicts with id, text, metadata.

    Raises:
        RuntimeError: If vector store is not initialized.
    """
    store = _get_store()

    results = store.search(query_vector, namespace=namespace, top_k=top_k)
    logger.info("Search returned %d results from namespace '%s'", len(results), namespace)

    return [
        {"id": doc.id, "text": doc.text, "metadata": doc.metadata}
        for doc in results
    ]


async def delete_documents(doc_ids: List[str], namespace: str) -> int:
    """Delete documents from the vector store by ID.

    Args:
        doc_ids: List of document IDs to delete.
        namespace: Collection/namespace containing the documents.

    Returns:
        Number of documents requested for deletion.

    Raises:
        RuntimeError: If vector store is not initialized.
    """
    store = _get_store()

    store.delete(doc_ids, namespace=namespace)
    logger.info("Deleted %d documents from namespace '%s'", len(doc_ids), namespace)
    return len(doc_ids)
