"""RAG engine tool - wraps packages/rag_engine for Skill use.

Provides simplified functions for retrieval-augmented generation queries.
"""

import logging
from typing import List, AsyncIterator, Optional, Callable

from rag_engine.engine import RagEngine, RagResponse
from vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

_engine: Optional[RagEngine] = None


def _init_engine(
    vector_store: QdrantVectorStore,
    api_key: str,
    model: str = "claude-sonnet-4-5-20250929",
    top_k: int = 5,
) -> RagEngine:
    """Initialize the RAG engine with given configuration."""
    global _engine
    _engine = RagEngine(
        vector_store=vector_store,
        api_key=api_key,
        model=model,
        top_k=top_k,
    )
    logger.info("RAG engine initialized (model=%s, top_k=%d)", model, top_k)
    return _engine


async def rag_query(
    question: str,
    namespace: str,
    embed_fn: Callable[[str], List[float]],
    vector_store: Optional[QdrantVectorStore] = None,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-5-20250929",
    top_k: int = 5,
) -> dict:
    """Execute a RAG query: retrieve relevant docs and generate an answer.

    Args:
        question: User question to answer.
        namespace: Vector store namespace (tenant isolation).
        embed_fn: Function that takes text and returns embedding vector.
        vector_store: QdrantVectorStore instance (uses cached if None).
        api_key: Anthropic API key (uses cached engine if None).
        model: Claude model to use (default claude-sonnet-4-5-20250929).
        top_k: Number of documents to retrieve (default 5).

    Returns:
        Dict with 'answer' (str) and 'sources' (List[str]).

    Raises:
        ValueError: If required parameters are missing.
        RuntimeError: If engine is not initialized and no config provided.
    """
    global _engine

    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    if vector_store and api_key:
        _init_engine(vector_store, api_key, model=model, top_k=top_k)
    elif _engine is None:
        raise RuntimeError(
            "RAG engine not initialized. Provide vector_store and api_key, "
            "or call rag_query with full config first."
        )

    response: RagResponse = _engine.query(
        question=question, namespace=namespace, embed_fn=embed_fn
    )
    logger.info("RAG query answered (%d sources)", len(response.sources))
    return {"answer": response.answer, "sources": response.sources}


async def rag_stream(
    question: str,
    namespace: str,
    embed_fn: Callable[[str], List[float]],
    vector_store: Optional[QdrantVectorStore] = None,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-5-20250929",
    top_k: int = 5,
) -> AsyncIterator[str]:
    """Stream a RAG answer token by token.

    Args:
        question: User question to answer.
        namespace: Vector store namespace (tenant isolation).
        embed_fn: Function that takes text and returns embedding vector.
        vector_store: QdrantVectorStore instance (uses cached if None).
        api_key: Anthropic API key (uses cached engine if None).
        model: Claude model to use.
        top_k: Number of documents to retrieve.

    Yields:
        Answer text tokens as they are generated.

    Raises:
        ValueError: If required parameters are missing.
        RuntimeError: If engine is not initialized and no config provided.
    """
    global _engine

    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    if vector_store and api_key:
        _init_engine(vector_store, api_key, model=model, top_k=top_k)
    elif _engine is None:
        raise RuntimeError(
            "RAG engine not initialized. Provide vector_store and api_key."
        )

    logger.info("Starting RAG stream for question: %s...", question[:50])
    async for token in _engine.stream(
        question=question, namespace=namespace, embed_fn=embed_fn
    ):
        yield token
