"""Unit tests for vector_store tool."""

import os
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "vector_store", "src"))


def test_init_qdrant():
    """init_qdrant creates a store instance."""
    from vector_store import init_qdrant

    store = init_qdrant(host="localhost", port=6333)
    assert store is not None
    assert store.host == "localhost"
    assert store.port == 6333


@pytest.mark.asyncio
async def test_index_documents_not_initialized():
    """index_documents raises RuntimeError when store not initialized."""
    import vector_store as vs_tool
    vs_tool._store = None

    with pytest.raises(RuntimeError, match="not initialized"):
        await vs_tool.index_documents([], namespace="test")


@pytest.mark.asyncio
async def test_index_documents_invalid_format():
    """index_documents raises ValueError for invalid doc format."""
    from vector_store import init_qdrant, index_documents

    init_qdrant("localhost", 6333)
    with pytest.raises(ValueError, match="must have"):
        await index_documents([{"id": "1"}], namespace="test")


@pytest.mark.asyncio
async def test_search_documents_not_initialized():
    """search_documents raises RuntimeError when store not initialized."""
    import vector_store as vs_tool
    vs_tool._store = None

    with pytest.raises(RuntimeError, match="not initialized"):
        await vs_tool.search_documents([0.1, 0.2], namespace="test")


@pytest.mark.asyncio
async def test_delete_documents_not_initialized():
    """delete_documents raises RuntimeError when store not initialized."""
    import vector_store as vs_tool
    vs_tool._store = None

    with pytest.raises(RuntimeError, match="not initialized"):
        await vs_tool.delete_documents(["id1"], namespace="test")
