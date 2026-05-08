"""Unit tests for rag_engine tool."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "rag_engine", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "vector_store", "src"))


@pytest.mark.asyncio
async def test_rag_query_empty_question():
    """rag_query raises ValueError for empty question."""
    from rag_engine import rag_query

    with pytest.raises(ValueError, match="empty"):
        await rag_query(
            question="",
            namespace="test",
            embed_fn=lambda x: [0.1, 0.2],
        )


@pytest.mark.asyncio
async def test_rag_query_not_initialized():
    """rag_query raises RuntimeError when engine not initialized."""
    import rag_engine as re_tool
    re_tool._engine = None

    with pytest.raises(RuntimeError, match="not initialized"):
        await re_tool.rag_query(
            question="What is X?",
            namespace="test",
            embed_fn=lambda x: [0.1, 0.2],
        )


@pytest.mark.asyncio
async def test_rag_stream_empty_question():
    """rag_stream raises ValueError for empty question."""
    from rag_engine import rag_stream

    with pytest.raises(ValueError, match="empty"):
        async for _ in rag_stream(
            question="",
            namespace="test",
            embed_fn=lambda x: [0.1, 0.2],
        ):
            pass


@pytest.mark.asyncio
async def test_rag_stream_not_initialized():
    """rag_stream raises RuntimeError when engine not initialized."""
    import rag_engine as re_tool
    re_tool._engine = None

    with pytest.raises(RuntimeError, match="not initialized"):
        async for _ in re_tool.rag_stream(
            question="What is X?",
            namespace="test",
            embed_fn=lambda x: [0.1, 0.2],
        ):
            pass
