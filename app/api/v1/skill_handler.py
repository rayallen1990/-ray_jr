"""Skill command handler — exposes /kb sync and related operations as API endpoints.

The ``/kb sync`` workflow:
1. Clone or pull the configured knowledge-base Git repository.
2. Scan for new / modified documents (PDF, DOCX, DOC, TXT, MD).
3. Parse each document and split into text chunks.
4. Index chunks into the Qdrant vector store under the tenant namespace.
"""

import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.kb_sync import KnowledgeBaseSync, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response / request schemas
# ---------------------------------------------------------------------------

class FileProcessResult(BaseModel):
    """Result of processing a single document file."""
    file_name: str
    chunks: int
    status: str  # "ok" | "skipped" | "error"
    error: Optional[str] = None


class SyncResponse(BaseModel):
    """Response returned by the /kb sync endpoint."""
    success: bool
    message: str
    new_files_count: int = 0
    processed: List[FileProcessResult] = Field(default_factory=list)
    total_chunks: int = 0
    error: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Response for repository status query."""
    cloned: bool
    path: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None
    message: Optional[str] = None
    document_count: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers — document parsing & indexing
# ---------------------------------------------------------------------------

def _get_parser_for_file(file_path: Path):
    """Return the appropriate parser instance for a file, or None if unsupported."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        from document_parser import PdfParser
        return PdfParser()
    if ext in {".docx", ".doc"}:
        from document_parser import WordParser
        return WordParser()
    if ext in {".txt", ".md"}:
        return _PlainTextParser()
    return None


class _PlainTextParser:
    """Minimal parser for plain-text and Markdown files."""

    def parse(self, file_path: str) -> str:
        return Path(file_path).read_text(encoding="utf-8", errors="replace")


def _parse_and_chunk(file_path: Path) -> List[str]:
    """Parse a document and return text chunks."""
    parser = _get_parser_for_file(file_path)
    if parser is None:
        return []

    from document_parser import chunk_text

    text: str = parser.parse(str(file_path))
    if not text.strip():
        return []
    return chunk_text(text)


def _index_chunks(
    chunks: List[str],
    file_name: str,
    tenant_id: str,
) -> None:
    """Index text chunks into Qdrant via the vector_store package.

    Embedding generation is stubbed with a zero-vector when no embedding
    service is configured — callers should replace this with a real
    embedding call (e.g. OpenAI ``text-embedding-3-small``) in production.
    """
    from vector_store import QdrantVectorStore, VectorDocument

    store = QdrantVectorStore(host=settings.qdrant_host, port=settings.qdrant_port)
    namespace = f"tenant:{tenant_id}:private"

    # Build vector documents
    # NOTE: Replace the placeholder vector with a real embedding call.
    vector_dim = 1536  # OpenAI text-embedding-3-small dimension
    documents: List[VectorDocument] = []
    for idx, chunk in enumerate(chunks):
        doc = VectorDocument(
            id=str(uuid.uuid4()),
            text=chunk,
            vector=[0.0] * vector_dim,  # placeholder — wire up real embeddings
            metadata={
                "source_file": file_name,
                "chunk_index": idx,
                "tenant_id": tenant_id,
            },
        )
        documents.append(doc)

    store.add(documents, namespace)
    logger.info(
        "Indexed %d chunks from %s into namespace %s",
        len(documents), file_name, namespace,
    )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.post("/sync", response_model=SyncResponse)
async def kb_sync(
    repo_url: Optional[str] = Query(
        default=None, description="Override the default repository URL"
    ),
    branch: Optional[str] = Query(
        default=None, description="Override the default branch"
    ),
    tenant_id: str = Query(
        default="default", description="Tenant ID for vector store namespace isolation"
    ),
    index: bool = Query(
        default=True, description="Whether to parse and index new documents"
    ),
) -> SyncResponse:
    """Sync the knowledge-base Git repository, then parse and index new documents.

    Workflow:
    1. Clone or pull the repository.
    2. Detect new / modified document files.
    3. Parse each file and split into text chunks.
    4. Index chunks into the Qdrant vector store.
    """
    syncer = KnowledgeBaseSync(
        repo_url=repo_url,
        branch=branch,
    )

    # Step 1 — git clone / pull
    try:
        sync_result = syncer.sync()
    except Exception as exc:
        logger.exception("Unexpected error during git sync")
        raise HTTPException(status_code=500, detail=f"Git sync failed: {exc}") from exc

    if not sync_result.success:
        return SyncResponse(
            success=False,
            message="Git sync failed",
            error=sync_result.error,
        )

    # Step 2 — determine which files to process
    files_to_process: List[str] = sync_result.new_files
    if not files_to_process and sync_result.is_fresh_clone:
        # On fresh clone scan_documents already populated new_files
        files_to_process = sync_result.new_files

    if not files_to_process:
        return SyncResponse(
            success=True,
            message="Repository is up to date — no new documents to process.",
        )

    if not index:
        return SyncResponse(
            success=True,
            message=f"Sync complete. {len(files_to_process)} new file(s) detected (indexing skipped).",
            new_files_count=len(files_to_process),
        )

    # Step 3 & 4 — parse, chunk, and index each document
    processed: List[FileProcessResult] = []
    total_chunks = 0

    for rel_path in files_to_process:
        abs_path = syncer.local_path / rel_path
        file_name = Path(rel_path).name

        if abs_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            processed.append(FileProcessResult(
                file_name=file_name, chunks=0, status="skipped",
            ))
            continue

        try:
            chunks = _parse_and_chunk(abs_path)
            if not chunks:
                processed.append(FileProcessResult(
                    file_name=file_name, chunks=0, status="skipped",
                    error="No text extracted",
                ))
                continue

            _index_chunks(chunks, file_name, tenant_id)
            total_chunks += len(chunks)
            processed.append(FileProcessResult(
                file_name=file_name, chunks=len(chunks), status="ok",
            ))
        except Exception as exc:
            logger.exception("Failed to process %s", rel_path)
            processed.append(FileProcessResult(
                file_name=file_name, chunks=0, status="error",
                error=str(exc),
            ))

    ok_count = sum(1 for p in processed if p.status == "ok")
    return SyncResponse(
        success=True,
        message=(
            f"Sync complete. {ok_count}/{len(files_to_process)} document(s) "
            f"parsed and indexed ({total_chunks} chunks total)."
        ),
        new_files_count=len(files_to_process),
        processed=processed,
        total_chunks=total_chunks,
    )


@router.get("/status", response_model=SyncStatusResponse)
async def kb_status() -> SyncStatusResponse:
    """Return the current sync status of the knowledge-base repository."""
    syncer = KnowledgeBaseSync()
    status = syncer.get_status()

    doc_count = 0
    if status.get("cloned"):
        doc_count = len(syncer.scan_documents())

    return SyncStatusResponse(
        cloned=status.get("cloned", False),
        path=status.get("path"),
        branch=status.get("branch"),
        commit=status.get("commit"),
        message=status.get("message"),
        document_count=doc_count,
        error=status.get("error"),
    )


@router.get("/documents")
async def kb_documents() -> dict:
    """List all supported documents currently in the local knowledge-base repository."""
    syncer = KnowledgeBaseSync()
    if not syncer.is_cloned():
        return {"cloned": False, "documents": []}

    docs = syncer.scan_documents()
    return {"cloned": True, "document_count": len(docs), "documents": docs}
