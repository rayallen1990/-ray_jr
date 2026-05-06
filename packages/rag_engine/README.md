# RAG Engine

RAG (Retrieval Augmented Generation) dialogue engine for Ray_jr knowledge base platform.

## Overview

Provides intelligent question-answering capabilities by combining vector search with large language models, supporting streaming responses and context management.

## Features

- LangChain-based RAG pipeline
- Claude Sonnet 4.5 API integration (Anthropic)
- OpenAI API support for embeddings and completions
- Streaming response output via WebSocket
- Context window management
- Token counting and optimization with tiktoken
- Conversation history tracking
- Source citation and relevance scoring

## Dependencies

- langchain >= 0.1.0
- anthropic >= 0.18.0
- openai >= 1.12.0
- pydantic >= 2.0.0
- tiktoken >= 0.5.0

## Installation

```bash
pip install -e .
```

## Usage

```python
from rag_engine import RAGEngine

engine = RAGEngine(
    vector_store=vector_store,
    model="claude-sonnet-4.5",
    api_key="your-api-key"
)

# Synchronous query
response = engine.query("How to configure HMI display settings?")

# Streaming query
async for chunk in engine.query_stream("Troubleshoot connection issues"):
    print(chunk, end="")
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
