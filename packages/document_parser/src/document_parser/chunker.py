"""Text chunking utility for splitting documents into smaller pieces"""

from typing import List


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """
    Split text into chunks of approximately chunk_size characters with overlap.

    Args:
        text: Input text to chunk
        chunk_size: Target size for each chunk (default 800 chars)
        overlap: Number of overlapping characters between chunks (default 100)

    Returns:
        List of text chunks
    """
    if not text or chunk_size <= 0:
        return []

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks
