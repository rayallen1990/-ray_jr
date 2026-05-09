"""Unit tests for skill_handler /kb upload command."""

import os
import sys
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set up import paths
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "tools")
)
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..")
)
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "packages",
        "document_parser", "src",
    ),
)
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "packages",
        "vector_store", "src",
    ),
)


def _make_context(
    user_id: str = "user123",
    channel: str = "dingtalk",
    attachments: list = None,
    is_group: bool = False,
) -> dict:
    """Build a minimal CowAgent context dict for testing."""
    return {
        "channel_type": channel,
        "msg": {
            "from_user_id": user_id,
            "from_user_nickname": "测试用户",
            "is_group": is_group,
            "attachments": attachments or [],
        },
    }


# -----------------------------------------------------------------------
# Test: no attachments
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_no_attachments():
    """Returns error message when no attachments are provided."""
    from skill_handler import handle_kb_upload

    ctx = _make_context(attachments=[])
    result = await handle_kb_upload(ctx)
    assert "未检测到文件附件" in result


# -----------------------------------------------------------------------
# Test: invalid context (no msg)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_no_msg():
    """Returns error when context has no msg field."""
    from skill_handler import handle_kb_upload

    result = await handle_kb_upload({"channel_type": "web"})
    assert "无法" in result


# -----------------------------------------------------------------------
# Test: unsupported file type
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_unsupported_extension():
    """Skips files with unsupported extensions."""
    from skill_handler import handle_kb_upload

    attachment = {
        "filename": "image.png",
        "content": b"fake image data",
    }
    ctx = _make_context(attachments=[attachment])
    result = await handle_kb_upload(ctx)
    assert "不支持的文件格式" in result


# -----------------------------------------------------------------------
# Test: file too large
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_file_too_large():
    """Skips files exceeding the size limit."""
    from skill_handler import handle_kb_upload, MAX_FILE_SIZE

    attachment = {
        "filename": "huge.pdf",
        "content": b"x" * (MAX_FILE_SIZE + 1),
    }
    ctx = _make_context(attachments=[attachment])
    result = await handle_kb_upload(ctx)
    assert "文件过大" in result


# -----------------------------------------------------------------------
# Test: successful upload (mocked pipeline)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_success():
    """Full upload pipeline succeeds with mocked tools."""
    from skill_handler import handle_kb_upload

    fake_text = "Hello " * 200  # ~1200 chars -> 2 chunks at 800/100

    attachment = {
        "filename": "manual.pdf",
        "content": b"%PDF-1.4 fake content for testing",
    }
    ctx = _make_context(attachments=[attachment])

    with (
        patch("skill_handler.parse_pdf", new_callable=AsyncMock, return_value=fake_text),
        patch(
            "skill_handler.chunk_text",
            new_callable=AsyncMock,
            return_value=["chunk1", "chunk2"],
        ),
        patch(
            "skill_handler.embed_batch",
            new_callable=AsyncMock,
            return_value=[[0.1, 0.2], [0.3, 0.4]],
        ),
        patch("skill_handler.init_qdrant") as mock_init,
        patch(
            "skill_handler.index_documents",
            new_callable=AsyncMock,
            return_value=2,
        ),
    ):
        result = await handle_kb_upload(ctx)

    assert "文档已成功索引到知识库" in result
    assert "manual.pdf" in result
    assert "片段数：2" in result


# -----------------------------------------------------------------------
# Test: TXT file upload
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_txt_file():
    """TXT files are read directly without PDF/Word parser."""
    from skill_handler import handle_kb_upload

    text_content = "这是一段测试文本。" * 100

    attachment = {
        "filename": "notes.txt",
        "content": text_content.encode("utf-8"),
    }
    ctx = _make_context(attachments=[attachment])

    with (
        patch(
            "skill_handler.chunk_text",
            new_callable=AsyncMock,
            return_value=["chunk1"],
        ),
        patch(
            "skill_handler.embed_batch",
            new_callable=AsyncMock,
            return_value=[[0.1, 0.2]],
        ),
        patch("skill_handler.init_qdrant"),
        patch(
            "skill_handler.index_documents",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        result = await handle_kb_upload(ctx)

    assert "文档已成功索引到知识库" in result
    assert "notes.txt" in result


# -----------------------------------------------------------------------
# Test: Word file upload
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_docx_file():
    """DOCX files are dispatched to parse_word."""
    from skill_handler import handle_kb_upload

    attachment = {
        "filename": "report.docx",
        "content": b"PK\x03\x04 fake docx",
    }
    ctx = _make_context(attachments=[attachment])

    with (
        patch(
            "skill_handler.parse_word",
            new_callable=AsyncMock,
            return_value="Word document content",
        ),
        patch(
            "skill_handler.chunk_text",
            new_callable=AsyncMock,
            return_value=["chunk1"],
        ),
        patch(
            "skill_handler.embed_batch",
            new_callable=AsyncMock,
            return_value=[[0.1]],
        ),
        patch("skill_handler.init_qdrant"),
        patch(
            "skill_handler.index_documents",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        result = await handle_kb_upload(ctx)

    assert "文档已成功索引到知识库" in result
    assert "report.docx" in result


# -----------------------------------------------------------------------
# Test: empty document after parsing
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_empty_after_parse():
    """Reports error when parsed document is empty."""
    from skill_handler import handle_kb_upload

    attachment = {
        "filename": "empty.pdf",
        "content": b"%PDF-1.4 empty",
    }
    ctx = _make_context(attachments=[attachment])

    with patch(
        "skill_handler.parse_pdf",
        new_callable=AsyncMock,
        return_value="",
    ):
        result = await handle_kb_upload(ctx)

    assert "内容为空" in result


# -----------------------------------------------------------------------
# Test: multiple files
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_multiple_files():
    """Processes multiple attachments sequentially."""
    from skill_handler import handle_kb_upload

    attachments = [
        {"filename": "doc1.pdf", "content": b"pdf data"},
        {"filename": "doc2.txt", "content": "text data".encode("utf-8")},
    ]
    ctx = _make_context(attachments=attachments)

    with (
        patch(
            "skill_handler.parse_pdf",
            new_callable=AsyncMock,
            return_value="PDF text content",
        ),
        patch(
            "skill_handler.chunk_text",
            new_callable=AsyncMock,
            return_value=["chunk1"],
        ),
        patch(
            "skill_handler.embed_batch",
            new_callable=AsyncMock,
            return_value=[[0.1]],
        ),
        patch("skill_handler.init_qdrant"),
        patch(
            "skill_handler.index_documents",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        result = await handle_kb_upload(ctx)

    assert "doc1.pdf" in result
    assert "doc2.txt" in result
    # Two success markers
    assert result.count("文档已成功索引到知识库") == 2


# -----------------------------------------------------------------------
# Test: mixed valid and invalid files
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_mixed_valid_invalid():
    """Skips invalid files but processes valid ones."""
    from skill_handler import handle_kb_upload

    attachments = [
        {"filename": "good.pdf", "content": b"pdf data"},
        {"filename": "bad.exe", "content": b"binary"},
    ]
    ctx = _make_context(attachments=attachments)

    with (
        patch(
            "skill_handler.parse_pdf",
            new_callable=AsyncMock,
            return_value="Good PDF",
        ),
        patch(
            "skill_handler.chunk_text",
            new_callable=AsyncMock,
            return_value=["chunk1"],
        ),
        patch(
            "skill_handler.embed_batch",
            new_callable=AsyncMock,
            return_value=[[0.1]],
        ),
        patch("skill_handler.init_qdrant"),
        patch(
            "skill_handler.index_documents",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        result = await handle_kb_upload(ctx)

    assert "文档已成功索引到知识库" in result
    assert "不支持的文件格式" in result


# -----------------------------------------------------------------------
# Test: tenant isolation via namespace
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_uses_correct_namespace():
    """Documents are indexed into the correct tenant namespace."""
    from skill_handler import handle_kb_upload

    attachment = {
        "filename": "secret.pdf",
        "content": b"pdf data",
    }
    ctx = _make_context(user_id="userA", channel="feishu", attachments=[attachment])

    captured_ns = {}

    async def fake_index(docs, namespace):
        captured_ns["ns"] = namespace
        return len(docs)

    with (
        patch(
            "skill_handler.parse_pdf",
            new_callable=AsyncMock,
            return_value="Secret content",
        ),
        patch(
            "skill_handler.chunk_text",
            new_callable=AsyncMock,
            return_value=["chunk1"],
        ),
        patch(
            "skill_handler.embed_batch",
            new_callable=AsyncMock,
            return_value=[[0.1]],
        ),
        patch("skill_handler.init_qdrant"),
        patch("skill_handler.index_documents", side_effect=fake_index),
    ):
        await handle_kb_upload(ctx)

    assert captured_ns["ns"] == "tenant:feishu:userA:private"


# -----------------------------------------------------------------------
# Test: file_path attachment (already on disk)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_with_file_path(tmp_path):
    """Handles attachments that provide a file_path instead of content."""
    from skill_handler import handle_kb_upload

    # Create a temp txt file
    txt_file = tmp_path / "existing.txt"
    txt_file.write_text("已存在的文件内容", encoding="utf-8")

    attachment = {
        "filename": "existing.txt",
        "file_path": str(txt_file),
    }
    ctx = _make_context(attachments=[attachment])

    with (
        patch(
            "skill_handler.chunk_text",
            new_callable=AsyncMock,
            return_value=["chunk1"],
        ),
        patch(
            "skill_handler.embed_batch",
            new_callable=AsyncMock,
            return_value=[[0.1]],
        ),
        patch("skill_handler.init_qdrant"),
        patch(
            "skill_handler.index_documents",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        result = await handle_kb_upload(ctx)

    assert "文档已成功索引到知识库" in result
    # Original file should not be deleted
    assert txt_file.exists()


# -----------------------------------------------------------------------
# Test: validate_file helper
# -----------------------------------------------------------------------


def test_validate_file_valid():
    """Returns None for valid files."""
    from skill_handler import _validate_file

    assert _validate_file("doc.pdf", 1024) is None
    assert _validate_file("doc.docx", 1024) is None
    assert _validate_file("doc.txt", 1024) is None


def test_validate_file_bad_extension():
    """Returns error for unsupported extension."""
    from skill_handler import _validate_file

    result = _validate_file("file.zip", 1024)
    assert result is not None
    assert "不支持" in result


def test_validate_file_too_large():
    """Returns error for oversized file."""
    from skill_handler import _validate_file, MAX_FILE_SIZE

    result = _validate_file("file.pdf", MAX_FILE_SIZE + 1)
    assert result is not None
    assert "文件过大" in result


# -----------------------------------------------------------------------
# Test: Reply helper
# -----------------------------------------------------------------------


def test_reply_render():
    """Reply renders accumulated parts separated by newlines."""
    from skill_handler import Reply

    r = Reply()
    r.add("line1")
    r.add("line2")
    assert r.render() == "line1\nline2"


def test_reply_empty():
    """Empty reply renders empty string."""
    from skill_handler import Reply

    assert Reply().render() == ""
