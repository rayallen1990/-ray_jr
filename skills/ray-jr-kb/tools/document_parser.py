"""Document parser tool - wraps packages/document_parser for Skill use.

Provides simplified functions for PDF/Word parsing and text chunking.
"""

import logging
from typing import List

from document_parser.pdf_parser import PdfParser
from document_parser.word_parser import WordParser
from document_parser.chunker import chunk_text as _chunk_text

logger = logging.getLogger(__name__)

_pdf_parser = PdfParser()
_word_parser = WordParser()


async def parse_pdf(file_path: str) -> str:
    """Parse a PDF file and return extracted text.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Extracted text content from all pages.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a valid PDF.
    """
    import os

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    try:
        text = _pdf_parser.parse(file_path)
        logger.info("Parsed PDF: %s (%d chars)", file_path, len(text))
        return text
    except Exception as e:
        logger.error("Failed to parse PDF %s: %s", file_path, e)
        raise ValueError(f"Failed to parse PDF: {e}") from e


async def parse_word(file_path: str) -> str:
    """Parse a Word (.docx) file and return extracted text.

    Args:
        file_path: Absolute path to the Word file.

    Returns:
        Extracted text content from all paragraphs.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a valid Word document.
    """
    import os

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Word file not found: {file_path}")

    try:
        text = _word_parser.parse(file_path)
        logger.info("Parsed Word: %s (%d chars)", file_path, len(text))
        return text
    except Exception as e:
        logger.error("Failed to parse Word %s: %s", file_path, e)
        raise ValueError(f"Failed to parse Word document: {e}") from e


async def chunk_text(
    text: str, chunk_size: int = 800, overlap: int = 100
) -> List[str]:
    """Split text into overlapping chunks for embedding.

    Args:
        text: Input text to split.
        chunk_size: Target characters per chunk (default 800).
        overlap: Overlapping characters between chunks (default 100).

    Returns:
        List of text chunks.
    """
    if not text:
        return []

    chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    logger.info("Chunked text into %d pieces (size=%d, overlap=%d)", len(chunks), chunk_size, overlap)
    return chunks
