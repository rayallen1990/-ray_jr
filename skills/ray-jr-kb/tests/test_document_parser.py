"""Unit tests for document_parser tool."""

import os
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "document_parser", "src"))


@pytest.mark.asyncio
async def test_parse_pdf_file_not_found():
    """parse_pdf raises FileNotFoundError for missing files."""
    from document_parser import parse_pdf

    with pytest.raises(FileNotFoundError):
        await parse_pdf("/nonexistent/file.pdf")


@pytest.mark.asyncio
async def test_parse_word_file_not_found():
    """parse_word raises FileNotFoundError for missing files."""
    from document_parser import parse_word

    with pytest.raises(FileNotFoundError):
        await parse_word("/nonexistent/file.docx")


@pytest.mark.asyncio
async def test_chunk_text_empty():
    """chunk_text returns empty list for empty input."""
    from document_parser import chunk_text

    result = await chunk_text("")
    assert result == []


@pytest.mark.asyncio
async def test_chunk_text_basic():
    """chunk_text splits text into expected chunks."""
    from document_parser import chunk_text

    text = "a" * 2000
    chunks = await chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) == 3
    assert all(len(c) <= 800 for c in chunks)


@pytest.mark.asyncio
async def test_chunk_text_short_text():
    """chunk_text returns single chunk for short text."""
    from document_parser import chunk_text

    text = "Hello world"
    chunks = await chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


@pytest.mark.asyncio
async def test_parse_pdf_success():
    """parse_pdf returns text when file exists and is valid."""
    from document_parser import parse_pdf

    with patch("document_parser.pdf_parser.PdfParser.parse", return_value="PDF content"):
        with patch("os.path.isfile", return_value=True):
            result = await parse_pdf("/fake/file.pdf")
            assert result == "PDF content"


@pytest.mark.asyncio
async def test_parse_word_success():
    """parse_word returns text when file exists and is valid."""
    from document_parser import parse_word

    with patch("document_parser.word_parser.WordParser.parse", return_value="Word content"):
        with patch("os.path.isfile", return_value=True):
            result = await parse_word("/fake/file.docx")
            assert result == "Word content"
