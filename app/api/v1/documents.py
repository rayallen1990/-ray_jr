"""Document upload and review workflow API"""

import os
import uuid
import shutil
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

# In-memory storage for development (replace with database in production)
_documents_store: List[dict] = []

UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


class DocumentResponse(BaseModel):
    id: str
    tenant_id: str
    uploader_id: str
    file_name: str
    file_size: str
    status: str
    created_at: str
    reviewed_by: Optional[str] = None
    review_comment: Optional[str] = None


class ReviewRequest(BaseModel):
    reviewed_by: str = "admin"
    comment: str = ""


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Query(default="test-tenant"),
    uploader_id: str = Query(default="test-user"),
):
    """Upload a document for knowledge base"""
    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".doc", ".txt"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not supported. Allowed: {allowed_extensions}"
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
        )

    # Save file
    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    file_path = tenant_dir / f"{doc_id}{file_ext}"

    with open(file_path, "wb") as f:
        f.write(content)

    # Create document record
    doc = {
        "id": doc_id,
        "tenant_id": tenant_id,
        "uploader_id": uploader_id,
        "file_name": file.filename,
        "file_path": str(file_path),
        "file_size": f"{file_size / 1024 / 1024:.2f} MB",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "reviewed_by": None,
        "review_comment": None,
    }
    _documents_store.append(doc)

    return DocumentResponse(**doc)


@router.get("/list", response_model=List[DocumentResponse])
async def list_documents(
    tenant_id: str = Query(default=None),
    status: str = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
):
    """List uploaded documents"""
    docs = _documents_store
    if tenant_id:
        docs = [d for d in docs if d["tenant_id"] == tenant_id]
    if status:
        docs = [d for d in docs if d["status"] == status]
    return [DocumentResponse(**d) for d in docs[offset:offset + limit]]


@router.get("/pending", response_model=List[DocumentResponse])
async def list_pending_documents():
    """List documents pending review (admin)"""
    docs = [d for d in _documents_store if d["status"] == "pending"]
    return [DocumentResponse(**d) for d in docs]


@router.post("/{doc_id}/approve", response_model=DocumentResponse)
async def approve_document(doc_id: str, review: ReviewRequest):
    """Approve a document for indexing"""
    doc = next((d for d in _documents_store if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc["status"] = "approved"
    doc["reviewed_by"] = review.reviewed_by
    doc["review_comment"] = review.comment
    return DocumentResponse(**doc)


@router.post("/{doc_id}/reject", response_model=DocumentResponse)
async def reject_document(doc_id: str, review: ReviewRequest):
    """Reject a document"""
    doc = next((d for d in _documents_store if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc["status"] = "rejected"
    doc["reviewed_by"] = review.reviewed_by
    doc["review_comment"] = review.comment

    # Delete file
    file_path = Path(doc["file_path"])
    if file_path.exists():
        file_path.unlink()

    return DocumentResponse(**doc)


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document"""
    global _documents_store
    doc = next((d for d in _documents_store if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file
    file_path = Path(doc["file_path"])
    if file_path.exists():
        file_path.unlink()

    _documents_store = [d for d in _documents_store if d["id"] != doc_id]
    return {"message": "Document deleted"}
