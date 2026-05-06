# Tenant Isolation

Multi-tenant isolation middleware for Ray_jr knowledge base platform.

## Overview

Provides database-level and vector store-level tenant isolation for FastAPI applications, ensuring secure data separation between enterprise accounts.

## Features

- Database-level isolation with tenant_id column filtering
- Vector store namespace isolation (tenant:<tenant_id>:private)
- SQLAlchemy query filter injection
- FastAPI middleware integration
- Tenant context management
- Request-scoped tenant identification

## Dependencies

- fastapi >= 0.104.0
- sqlalchemy >= 2.0.0
- pydantic >= 2.0.0

## Installation

```bash
pip install -e .
```

## Usage

```python
from tenant_isolation import TenantIsolationMiddleware, get_current_tenant
from fastapi import FastAPI, Depends

app = FastAPI()
app.add_middleware(TenantIsolationMiddleware)

@app.get("/data")
async def get_data(tenant_id: str = Depends(get_current_tenant)):
    # tenant_id is automatically extracted from JWT token
    # All database queries are automatically filtered by tenant_id
    return {"tenant": tenant_id}
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
