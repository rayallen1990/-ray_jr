"""Test chat API for knowledge base"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    tenant_id: str = "test-tenant"


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Test chat endpoint (simplified version without RAG)

    TODO: Integrate with RAG engine and vector store
    """
    # Placeholder response
    return ChatResponse(
        answer=f"这是一个测试回答。您的问题是：{request.question}\n\n"
               "当前系统正在开发中，RAG 引擎尚未完全集成。\n"
               "文档已上传：HMI组态软件FStudio 用户手册-07.docx (80MB)\n\n"
               "下一步需要：\n"
               "1. 解析文档内容\n"
               "2. 文本分块\n"
               "3. 生成向量嵌入\n"
               "4. 存入 Qdrant\n"
               "5. 实现检索和生成",
        sources=["HMI组态软件FStudio 用户手册-07.docx"]
    )


@router.get("/status")
async def status():
    """Get knowledge base status"""
    import os
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
        "status": "development",
        "documents_uploaded": len(documents),
        "documents": documents,
        "rag_engine": "not_integrated",
        "vector_store": "not_initialized"
    }
