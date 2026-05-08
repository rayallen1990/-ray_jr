"""Embedding tool - provides text embedding via sentence-transformers.

Supports both local sentence-transformers models and OpenAI embedding API.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_model = None
_model_name: str = "all-MiniLM-L6-v2"


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers required: pip install sentence-transformers"
            )
        _model = SentenceTransformer(_model_name)
        logger.info("Loaded embedding model: %s", _model_name)
    return _model


async def embed_text(text: str) -> List[float]:
    """Generate an embedding vector for the given text.

    Uses sentence-transformers (all-MiniLM-L6-v2) by default for local,
    fast embedding generation without external API calls.

    Args:
        text: Input text to embed.

    Returns:
        Embedding vector as a list of floats.

    Raises:
        ValueError: If text is empty.
        ImportError: If sentence-transformers is not installed.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    result = vector.tolist()
    logger.debug("Embedded text (%d chars) -> vector dim %d", len(text), len(result))
    return result


async def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embedding vectors for a batch of texts.

    More efficient than calling embed_text repeatedly for multiple texts.

    Args:
        texts: List of input texts to embed.

    Returns:
        List of embedding vectors.

    Raises:
        ValueError: If texts list is empty.
    """
    if not texts:
        raise ValueError("Cannot embed empty text list")

    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32)
    results = [v.tolist() for v in vectors]
    logger.info("Batch embedded %d texts -> dim %d", len(texts), len(results[0]) if results else 0)
    return results


def configure_model(model_name: str) -> None:
    """Switch the embedding model.

    Args:
        model_name: Name of a sentence-transformers compatible model.
    """
    global _model, _model_name
    _model = None
    _model_name = model_name
    logger.info("Embedding model configured: %s (will load on next use)", model_name)
