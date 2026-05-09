"""CowAgent Skill handler for Ray-JR Knowledge Base.

Implements the /kb upload command: receives file attachments from CowAgent
context, parses documents, chunks text, generates embeddings, and indexes
into the user's tenant-isolated Qdrant namespace.
"""

import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.document_parser import parse_pdf, parse_word, chunk_text
from tools.embedding import embed_batch
from tools.tenant_mapper import resolve_tenant, TenantInfo
from tools.vector_store import init_qdrant, index_documents

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100 MB
CHUNK_SIZE: int = 800
CHUNK_OVERLAP: int = 100
EMBED_BATCH_SIZE: int = 32
SUPPORTED_EXTENSIONS: Dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "word",
    ".doc": "word",
    ".txt": "text",
}

QDRANT_HOST: str = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT: int = int(os.environ.get("QDRANT_PORT", "6333"))

# ---------------------------------------------------------------------------
# Reply helper
# ---------------------------------------------------------------------------


class Reply:
    """Accumulates reply parts and renders a single message string."""

    def __init__(self) -> None:
        self._parts: List[str] = []

    def add(self, text: str) -> None:
        self._parts.append(text)

    def render(self) -> str:
        return "\n".join(self._parts)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _get_file_extension(filename: str) -> str:
    """Return lowercased file extension including the dot."""
    return Path(filename).suffix.lower()


def _validate_file(filename: str, file_size: int) -> Optional[str]:
    """Validate file type and size. Returns error message or None."""
    ext = _get_file_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS.keys()))
        return f"不支持的文件格式 {ext}。支持的格式：{allowed}"

    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        return f"文件过大（{file_size / (1024 * 1024):.1f} MB），最大允许 {max_mb:.0f} MB"

    return None


async def _save_attachment_to_temp(attachment: Any) -> str:
    """Save a CowAgent attachment to a temporary file and return the path.

    Supports both dict-like and object-style attachment access.

    Args:
        attachment: CowAgent attachment object with content/data and filename.

    Returns:
        Absolute path to the saved temporary file.

    Raises:
        ValueError: If the attachment has no usable content.
    """
    def _get(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    filename: str = _get(attachment, "filename") or _get(attachment, "name") or "unknown"
    content: Optional[bytes] = (
        _get(attachment, "content")
        or _get(attachment, "data")
        or _get(attachment, "file_content")
    )

    # If content is a string path, the file is already on disk
    file_path: Optional[str] = _get(attachment, "file_path") or _get(attachment, "path")
    if file_path and os.path.isfile(file_path):
        return file_path

    if content is None:
        raise ValueError(f"附件 {filename} 没有可读取的内容")

    if isinstance(content, str):
        content = content.encode("utf-8")

    ext = _get_file_extension(filename)
    tmp_dir = tempfile.mkdtemp(prefix="rayjr_upload_")
    tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}{ext}")

    with open(tmp_path, "wb") as f:
        f.write(content)

    logger.info("Saved attachment '%s' to %s (%d bytes)", filename, tmp_path, len(content))
    return tmp_path


# ---------------------------------------------------------------------------
# Parse dispatcher
# ---------------------------------------------------------------------------


async def _parse_file(file_path: str, ext: str) -> str:
    """Dispatch to the appropriate parser based on file extension.

    Args:
        file_path: Path to the file on disk.
        ext: Lowercased file extension (e.g. ".pdf").

    Returns:
        Extracted text content.
    """
    file_type = SUPPORTED_EXTENSIONS.get(ext, "")
    if file_type == "pdf":
        return await parse_pdf(file_path)
    elif file_type == "word":
        return await parse_word(file_path)
    elif file_type == "text":
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ---------------------------------------------------------------------------
# Core upload pipeline
# ---------------------------------------------------------------------------


async def _process_upload(
    file_path: str,
    filename: str,
    file_size: int,
    tenant_info: TenantInfo,
    reply: Reply,
) -> Dict[str, Any]:
    """Run the full upload pipeline for a single file.

    Steps:
        1. Parse document text
        2. Chunk text
        3. Generate embeddings (batch)
        4. Index into Qdrant

    Args:
        file_path: Absolute path to the file on disk.
        filename: Original filename for display.
        file_size: File size in bytes.
        tenant_info: Resolved tenant information.
        reply: Reply accumulator for progress messages.

    Returns:
        Dict with document metadata (doc_id, filename, chunk_count, etc.).
    """
    ext = _get_file_extension(filename)
    doc_id = uuid.uuid4().hex[:12]
    namespace = tenant_info.namespace

    # 1. Parse
    reply.add(f"📄 正在解析文档 {filename}...")
    text = await _parse_file(file_path, ext)
    if not text or not text.strip():
        raise ValueError(f"文档 {filename} 解析后内容为空")
    logger.info("Parsed '%s': %d chars", filename, len(text))

    # 2. Chunk
    chunks = await chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        raise ValueError(f"文档 {filename} 分块后无有效片段")
    reply.add(f"✓ 文档解析完成，共 {len(chunks)} 个片段")
    logger.info("Chunked '%s' into %d pieces", filename, len(chunks))

    # 3. Embed (batch, with progress)
    total = len(chunks)
    all_vectors: List[List[float]] = []

    for batch_start in range(0, total, EMBED_BATCH_SIZE):
        batch_end = min(batch_start + EMBED_BATCH_SIZE, total)
        batch_texts = chunks[batch_start:batch_end]
        vectors = await embed_batch(batch_texts)
        all_vectors.extend(vectors)
        reply.add(f"⏳ 正在生成向量嵌入 ({batch_end}/{total})...")

    logger.info("Generated %d embeddings for '%s'", len(all_vectors), filename)

    # 4. Build docs for indexing
    now_iso = datetime.now(timezone.utc).isoformat()
    vector_docs: List[Dict[str, Any]] = []
    for idx, (chunk, vector) in enumerate(zip(chunks, all_vectors)):
        vector_docs.append({
            "id": f"{doc_id}_{idx}",
            "text": chunk,
            "vector": vector,
            "metadata": {
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": idx,
                "total_chunks": total,
                "file_size": file_size,
                "uploaded_at": now_iso,
                "tenant_id": tenant_info.tenant_id,
            },
        })

    # 5. Index into Qdrant
    init_qdrant(host=QDRANT_HOST, port=QDRANT_PORT)
    indexed = await index_documents(vector_docs, namespace=namespace)
    logger.info(
        "Indexed %d chunks for '%s' into namespace '%s'",
        indexed, filename, namespace,
    )

    reply.add(f"✅ 文档已成功索引到知识库！")
    reply.add("")
    reply.add("文档信息：")
    reply.add(f"- 文件名：{filename}")
    reply.add(f"- 大小：{file_size / (1024 * 1024):.2f} MB")
    reply.add(f"- 片段数：{total}")
    reply.add(f"- 文档 ID：{doc_id}")

    return {
        "doc_id": doc_id,
        "filename": filename,
        "file_size": file_size,
        "chunk_count": total,
        "namespace": namespace,
        "uploaded_at": now_iso,
    }


# ---------------------------------------------------------------------------
# CowAgent skill entry point
# ---------------------------------------------------------------------------


async def handle_kb_upload(context: Dict[str, Any]) -> str:
    """Handle the ``/kb upload`` command from CowAgent.

    Extracts attachments from ``context["msg"]``, resolves the user's tenant,
    and runs the upload pipeline for each attached file.

    Args:
        context: CowAgent context dictionary containing msg, channel_type, etc.

    Returns:
        Reply string with progress and result information.
    """
    reply = Reply()

    # --- Resolve tenant ---
    try:
        tenant_info = resolve_tenant(context)
    except ValueError as exc:
        logger.error("Failed to resolve tenant: %s", exc)
        return f"❌ 无法识别用户身份：{exc}"

    # --- Extract attachments ---
    msg: Any = context.get("msg")
    if msg is None:
        return "❌ 无法读取消息内容"

    if isinstance(msg, dict):
        attachments = msg.get("attachments", [])
    else:
        attachments = getattr(msg, "attachments", [])

    if not attachments:
        return (
            "❌ 未检测到文件附件。\n"
            "请使用 `/kb upload` 命令并附带文件（支持 PDF、Word、TXT 格式）。"
        )

    # --- Process each attachment ---
    results: List[Dict[str, Any]] = []
    for attachment in attachments:
        def _get(obj: Any, key: str, default: Any = None) -> Any:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        filename: str = (
            _get(attachment, "filename")
            or _get(attachment, "name")
            or "unknown"
        )

        # Determine file size
        content = (
            _get(attachment, "content")
            or _get(attachment, "data")
            or _get(attachment, "file_content")
        )
        file_path_hint: Optional[str] = (
            _get(attachment, "file_path") or _get(attachment, "path")
        )

        if file_path_hint and os.path.isfile(file_path_hint):
            file_size = os.path.getsize(file_path_hint)
        elif content is not None:
            file_size = len(content) if isinstance(content, (bytes, bytearray)) else len(content.encode("utf-8"))
        else:
            file_size = 0

        # Validate
        error = _validate_file(filename, file_size)
        if error:
            reply.add(f"⚠️ 跳过文件 {filename}：{error}")
            continue

        try:
            saved_path = await _save_attachment_to_temp(attachment)
            result = await _process_upload(
                file_path=saved_path,
                filename=filename,
                file_size=file_size,
                tenant_info=tenant_info,
                reply=reply,
            )
            results.append(result)
        except Exception as exc:
            logger.exception("Failed to process '%s'", filename)
            reply.add(f"❌ 处理文件 {filename} 失败：{exc}")
        finally:
            # Clean up temp file (only if we created it)
            if file_path_hint and os.path.isfile(file_path_hint):
                pass  # Don't delete files we didn't create
            elif "saved_path" in locals() and os.path.isfile(saved_path):
                try:
                    os.unlink(saved_path)
                    parent = os.path.dirname(saved_path)
                    if parent and os.path.isdir(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                except OSError:
                    pass

    if not results:
        reply.add("未成功处理任何文件。")

    return reply.render()
