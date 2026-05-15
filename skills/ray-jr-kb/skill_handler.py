"""CowAgent Skill handler for Ray-JR Knowledge Base.

Implements all /kb commands:
  /kb ask <question>  — RAG-based knowledge base Q&A
  /kb upload          — Upload documents (with file attachments)
  /kb list            — List uploaded documents
  /kb status          — Knowledge base status
  /kb sync            — Sync from Git repository
"""

import logging
import os
import time
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.document_parser import parse_pdf, parse_word, chunk_text
from tools.embedding import embed_batch, embed_text
from tools.tenant_mapper import resolve_tenant, TenantInfo
from tools.vector_store import init_qdrant, index_documents, search_documents
from tools.rag_engine import rag_query
from tools.query_rewriter import rewrite_query

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


# ---------------------------------------------------------------------------
# /kb ask — RAG question answering
# ---------------------------------------------------------------------------


async def handle_kb_ask(context: Dict[str, Any]) -> str:
    """Handle the ``/kb ask <question>`` command.

    Embeds the question, retrieves relevant documents from the user's
    namespace, and generates an answer via Claude API.
    """
    try:
        tenant_info = resolve_tenant(context)
    except ValueError as exc:
        return f"❌ 无法识别用户身份：{exc}"

    msg: Any = context.get("msg")
    if msg is None:
        return "❌ 无法读取消息内容"

    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
    # Extract question: strip "/kb ask " prefix
    question = content.strip()
    for prefix in ("/kb ask ", "/kb ask"):
        if question.lower().startswith(prefix):
            question = question[len(prefix):].strip()
            break

    if not question:
        return "请提供问题。用法：/kb ask <你的问题>"

    namespace = tenant_info.namespace
    init_qdrant(host=QDRANT_HOST, port=QDRANT_PORT)

    start_time = time.time()

    # Query rewrite for better retrieval
    search_query = await rewrite_query(question)

    try:
        result = await rag_query(
            question=search_query,
            namespace=namespace,
            embed_fn=embed_text,
        )
    except RuntimeError as e:
        return f"❌ {e}"
    except ConnectionError:
        return "❌ 无法连接到后端服务，请检查服务状态后重试。"
    except Exception as e:
        logger.error("Error in /kb ask: %s", e, exc_info=True)
        return f"❌ 处理问题时发生错误：{type(e).__name__}: {e}"

    elapsed = time.time() - start_time
    answer = result.get("answer", "")
    sources = result.get("sources", [])

    lines = [answer, ""]
    if sources:
        lines.append("参考来源：")
        for i, src in enumerate(sources, 1):
            lines.append(f"  [{i}] {src}")
    lines.append("")
    lines.append(f"（耗时 {elapsed:.1f}s）")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# /kb list — List uploaded documents
# ---------------------------------------------------------------------------


async def handle_kb_list(context: Dict[str, Any]) -> str:
    """Handle the ``/kb list`` command.

    Queries Qdrant for all unique documents in the user's namespace.
    """
    try:
        tenant_info = resolve_tenant(context)
    except ValueError as exc:
        return f"❌ 无法识别用户身份：{exc}"

    namespace = tenant_info.namespace
    init_qdrant(host=QDRANT_HOST, port=QDRANT_PORT)

    try:
        # Search with a zero vector to get all docs (scroll approach)
        # We use search_documents with a dummy query to list metadata
        docs = await search_documents(
            query_vector=[0.0] * 384,
            namespace=namespace,
            top_k=100,
        )
    except Exception as e:
        logger.error("Error listing documents: %s", e)
        return f"❌ 查询知识库失败：{e}"

    if not docs:
        return "📚 你的知识库为空。\n\n使用 `/kb upload` 上传文档，或 `/kb sync` 从仓库同步。"

    # Group by doc_id to get unique documents
    doc_map: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        meta = doc.get("metadata", {}) if isinstance(doc, dict) else getattr(doc, "metadata", {})
        doc_id = meta.get("doc_id", "unknown")
        if doc_id not in doc_map:
            doc_map[doc_id] = {
                "filename": meta.get("filename", "未知文件"),
                "total_chunks": meta.get("total_chunks", 1),
                "uploaded_at": meta.get("uploaded_at", ""),
            }

    lines = ["📚 你的知识库文档：", ""]
    total_chunks = 0
    for i, (doc_id, info) in enumerate(doc_map.items(), 1):
        date_str = info["uploaded_at"][:10] if info["uploaded_at"] else "未知"
        lines.append(f"{i}. {info['filename']} — {info['total_chunks']} 片段 — {date_str}")
        total_chunks += info["total_chunks"]

    lines.append("")
    lines.append(f"共 {len(doc_map)} 个文档，{total_chunks} 个片段")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# /kb status — Knowledge base status
# ---------------------------------------------------------------------------


async def handle_kb_status(context: Dict[str, Any]) -> str:
    """Handle the ``/kb status`` command.

    Reports knowledge base connection status and statistics.
    """
    try:
        tenant_info = resolve_tenant(context)
    except ValueError as exc:
        return f"❌ 无法识别用户身份：{exc}"

    namespace = tenant_info.namespace
    init_qdrant(host=QDRANT_HOST, port=QDRANT_PORT)

    lines = ["📊 知识库状态：", ""]

    # Check Qdrant connectivity
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        collections = client.get_collections().collections
        col_names = [c.name for c in collections]
        has_namespace = namespace in col_names

        if has_namespace:
            info = client.get_collection(namespace)
            lines.append(f"- 状态：正常运行")
            lines.append(f"- 文档片段数：{info.points_count}")
            lines.append(f"- 向量维度：{info.config.params.vectors.size}")
        else:
            lines.append("- 状态：正常运行（命名空间为空）")
            lines.append("- 文档片段数：0")
    except Exception as e:
        lines.append(f"- 状态：❌ 连接失败 ({e})")

    lines.append(f"- 存储命名空间：{namespace}")
    lines.append(f"- Qdrant 地址：{QDRANT_HOST}:{QDRANT_PORT}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# /kb sync — Sync from Git repository
# ---------------------------------------------------------------------------


async def handle_kb_sync(context: Dict[str, Any]) -> str:
    """Handle the ``/kb sync`` command.

    Pulls latest documents from the configured Git repository and indexes
    new/modified files into the user's namespace.
    """
    try:
        tenant_info = resolve_tenant(context)
    except ValueError as exc:
        return f"❌ 无法识别用户身份：{exc}"

    namespace = tenant_info.namespace
    reply = Reply()
    reply.add("🔄 正在同步知识库仓库...")

    try:
        from app.kb_sync import KnowledgeBaseSync
        syncer = KnowledgeBaseSync()
        result = syncer.sync()
    except ImportError:
        return "❌ 同步模块未安装，请检查部署配置。"
    except Exception as e:
        logger.error("Sync failed: %s", e, exc_info=True)
        return f"❌ 同步失败：{e}"

    if not result.success:
        return f"❌ 同步失败：{result.error}"

    new_files = result.new_files or []
    if not new_files:
        reply.add("✅ 同步完成，没有新文件需要索引。")
        return reply.render()

    reply.add(f"发现 {len(new_files)} 个新/修改文件，正在索引...")

    # Index new files
    init_qdrant(host=QDRANT_HOST, port=QDRANT_PORT)
    indexed_count = 0
    from app.kb_sync import KnowledgeBaseSync
    syncer = KnowledgeBaseSync()
    base_path = syncer.local_path

    for filepath in new_files:
        full_path = str(base_path / filepath)
        ext = Path(filepath).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        try:
            text = await _parse_file(full_path, ext)
            if not text or not text.strip():
                continue
            chunks = await chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
            if not chunks:
                continue

            vectors = await embed_batch(chunks)
            doc_id = uuid.uuid4().hex[:12]
            now_iso = datetime.now(timezone.utc).isoformat()

            vector_docs = []
            for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
                vector_docs.append({
                    "id": f"{doc_id}_{idx}",
                    "text": chunk,
                    "vector": vector,
                    "metadata": {
                        "doc_id": doc_id,
                        "filename": filepath,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                        "uploaded_at": now_iso,
                        "tenant_id": tenant_info.tenant_id,
                        "source": "sync",
                    },
                })

            await index_documents(vector_docs, namespace=namespace)
            indexed_count += 1
        except Exception as e:
            logger.warning("Failed to index %s: %s", filepath, e)

    reply.add(f"✅ 同步完成！成功索引 {indexed_count} 个文件。")
    return reply.render()


# ---------------------------------------------------------------------------
# Main command router
# ---------------------------------------------------------------------------


async def handle_skill(context: Dict[str, Any]) -> str:
    """Main entry point for the ray-jr-kb CowAgent Skill.

    Routes /kb subcommands to the appropriate handler.

    Args:
        context: CowAgent context dictionary.

    Returns:
        Reply string.
    """
    msg: Any = context.get("msg")
    if msg is None:
        return "❌ 无法读取消息内容"

    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
    content = content.strip()

    # Parse subcommand
    if content.lower().startswith("/kb"):
        content = content[3:].strip()

    parts = content.split(maxsplit=1)
    subcommand = parts[0].lower() if parts else ""

    if subcommand == "ask":
        return await handle_kb_ask(context)
    elif subcommand == "upload":
        return await handle_kb_upload(context)
    elif subcommand == "list":
        return await handle_kb_list(context)
    elif subcommand == "status":
        return await handle_kb_status(context)
    elif subcommand == "sync":
        return await handle_kb_sync(context)
    elif subcommand in ("help", ""):
        return (
            "知识库命令帮助：\n\n"
            "/kb ask <问题>    — 向知识库提问\n"
            "/kb upload        — 上传文档（附带文件）\n"
            "/kb list          — 列出已上传文档\n"
            "/kb status        — 查看知识库状态\n"
            "/kb sync          — 从仓库同步知识库\n"
            "/kb help          — 显示此帮助"
        )
    else:
        return f"未知命令：/kb {subcommand}\n\n输入 /kb help 查看可用命令。"
