"""Chat API - knowledge base Q&A powered by RAG engine"""

import json
import time
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from auth_middleware import get_current_user, UserPayload
from tenant_isolation import get_tenant_namespace

logger = logging.getLogger(__name__)
router = APIRouter()


class SourceRef(BaseModel):
    doc_id: str
    filename: str
    chunk_text: str = ""
    score: float = 0.0


class ChatRequest(BaseModel):
    question: str
    history: List[str] = []
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceRef] = []
    rewritten_query: Optional[str] = None
    latency_ms: int


def _get_rag_engine():
    """Lazy-init RAG engine with current config."""
    from rag_engine.engine import RagEngine
    from vector_store import QdrantVectorStore

    vs = QdrantVectorStore(host=settings.qdrant_host, port=settings.qdrant_port)
    return RagEngine(
        vector_store=vs,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        provider=settings.llm_provider,
        top_k=settings.rag_top_k,
    )


def _get_embed_fn():
    """Return embedding function using OpenAI-compatible API."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    def embed(text: str) -> List[float]:
        resp = client.embeddings.create(model="text-embedding-ada-002", input=text)
        return resp.data[0].embedding

    return embed


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: UserPayload = Depends(get_current_user)):
    """Knowledge base Q&A endpoint."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    namespace = get_tenant_namespace(user.tenant_id)
    start = time.time()

    try:
        engine = _get_rag_engine()
        embed_fn = _get_embed_fn()
        response = engine.query(
            question=request.question, namespace=namespace, embed_fn=embed_fn
        )
    except RuntimeError as e:
        logger.error("RAG query failed for tenant %s: %s", user.tenant_id, e)
        raise HTTPException(status_code=503, detail=str(e))

    latency_ms = int((time.time() - start) * 1000)
    sources = [
        SourceRef(doc_id=s, filename=s, chunk_text="", score=0.0)
        for s in response.sources
    ]
    return ChatResponse(
        answer=response.answer, sources=sources, latency_ms=latency_ms
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, user: UserPayload = Depends(get_current_user)):
    """Streaming knowledge base Q&A endpoint (SSE)."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    namespace = get_tenant_namespace(user.tenant_id)

    async def event_generator():
        start = time.time()
        try:
            engine = _get_rag_engine()
            embed_fn = _get_embed_fn()
            async for token in engine.stream(
                question=request.question, namespace=namespace, embed_fn=embed_fn
            ):
                yield f"data: {json.dumps({'type': 'chunk', 'content': token}, ensure_ascii=False)}\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
            return

        latency_ms = int((time.time() - start) * 1000)
        yield f"data: {json.dumps({'type': 'done', 'latency_ms': latency_ms}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/status")
async def status():
    """Get knowledge base status"""
    from pathlib import Path

    data_path = Path("./data/documents")
    documents = []

    if data_path.exists():
        for file in data_path.rglob("*"):
            if file.is_file() and file.suffix in [".pdf", ".docx", ".doc"]:
                documents.append({
                    "name": file.name,
                    "size": f"{file.stat().st_size / 1024 / 1024:.2f} MB",
                    "path": str(file.relative_to(data_path))
                })

    return {
        "status": "active",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "documents_uploaded": len(documents),
        "documents": documents,
    }
