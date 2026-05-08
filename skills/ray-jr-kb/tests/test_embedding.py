"""Unit tests for embedding tool."""

import os
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))


@pytest.mark.asyncio
async def test_embed_text_empty():
    """embed_text raises ValueError for empty text."""
    from embedding import embed_text

    with pytest.raises(ValueError, match="empty"):
        await embed_text("")


@pytest.mark.asyncio
async def test_embed_text_whitespace():
    """embed_text raises ValueError for whitespace-only text."""
    from embedding import embed_text

    with pytest.raises(ValueError, match="empty"):
        await embed_text("   ")


@pytest.mark.asyncio
async def test_embed_text_success():
    """embed_text returns a list of floats."""
    from embedding import embed_text

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch("embedding._get_model", return_value=mock_model):
        result = await embed_text("hello world")
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(v, float) for v in result)


@pytest.mark.asyncio
async def test_embed_batch_empty():
    """embed_batch raises ValueError for empty list."""
    from embedding import embed_batch

    with pytest.raises(ValueError, match="empty"):
        await embed_batch([])


@pytest.mark.asyncio
async def test_embed_batch_success():
    """embed_batch returns list of vectors."""
    from embedding import embed_batch

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])

    with patch("embedding._get_model", return_value=mock_model):
        result = await embed_batch(["hello", "world"])
        assert len(result) == 2
        assert all(len(v) == 2 for v in result)


def test_configure_model():
    """configure_model resets the cached model."""
    from embedding import configure_model, _model_name
    import embedding

    configure_model("paraphrase-MiniLM-L6-v2")
    assert embedding._model_name == "paraphrase-MiniLM-L6-v2"
    assert embedding._model is None

    # Reset
    configure_model("all-MiniLM-L6-v2")
