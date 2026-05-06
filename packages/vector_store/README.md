# Vector Store

Vector database wrapper for Ray_jr knowledge base platform.

## Overview

Provides a unified interface for vector storage and semantic search using Qdrant, with multi-tenant namespace isolation and embedding generation.

## Features

- Qdrant vector database integration
- Semantic search with similarity scoring
- Multi-tenant namespace isolation (tenant:<tenant_id>:private)
- Embedding generation using sentence-transformers
- Batch document ingestion
- Metadata filtering support

## Dependencies

- qdrant-client >= 1.7.0
- sentence-transformers >= 2.2.0
- pydantic >= 2.0.0
- numpy >= 1.24.0

## Installation

```bash
pip install -e .
```

## Usage

```python
from vector_store import VectorStore

store = VectorStore(
    host="localhost",
    port=6333,
    tenant_id="tenant_123"
)

# Add documents
store.add_documents([
    {"text": "HMI configuration guide", "metadata": {"type": "manual"}},
    {"text": "Troubleshooting steps", "metadata": {"type": "guide"}}
])

# Search
results = store.search("How to configure HMI?", top_k=5)
```

## Development

Install with dev dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```
