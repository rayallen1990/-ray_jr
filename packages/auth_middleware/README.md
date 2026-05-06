# Auth Middleware

Authentication middleware for Ray_jr knowledge base platform.

## Overview

Provides JWT-based authentication and authorization for FastAPI applications, with user verification and tenant permission injection.

## Features

- JWT token generation and validation
- Password hashing with bcrypt
- User authentication and verification
- FastAPI middleware integration
- Token-based session management
- Tenant context injection

## Dependencies

- fastapi >= 0.104.0
- python-jose[cryptography] >= 3.3.0
- passlib[bcrypt] >= 1.7.4
- pydantic >= 2.0.0
- python-multipart >= 0.0.6

## Installation

```bash
pip install -e .
```

## Usage

```python
from auth_middleware import AuthMiddleware, create_access_token, verify_password

# Create JWT token
token = create_access_token(
    data={"sub": "user@example.com", "tenant_id": "tenant_123"}
)

# Verify password
is_valid = verify_password("plain_password", "hashed_password")

# Add middleware to FastAPI app
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(AuthMiddleware, secret_key="your-secret-key")
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
