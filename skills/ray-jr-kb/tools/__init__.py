"""Ray-JR Knowledge Base Skill Tools

Provides document parsing, vector storage, RAG query, embedding,
and CowAgent tenant mapping functions.
"""

from .document_parser import parse_pdf, parse_word, chunk_text
from .vector_store import init_qdrant, index_documents, search_documents, delete_documents
from .rag_engine import rag_query, rag_stream
from .embedding import embed_text
from .query_rewriter import rewrite_query
from .tenant_mapper import (
    TenantInfo,
    resolve_tenant,
    extract_user_from_context,
    generate_tenant_id,
    generate_namespace,
    generate_group_namespace,
)

__all__ = [
    "parse_pdf",
    "parse_word",
    "chunk_text",
    "init_qdrant",
    "index_documents",
    "search_documents",
    "delete_documents",
    "rag_query",
    "rag_stream",
    "embed_text",
    "rewrite_query",
    "TenantInfo",
    "resolve_tenant",
    "extract_user_from_context",
    "generate_tenant_id",
    "generate_namespace",
    "generate_group_namespace",
]
