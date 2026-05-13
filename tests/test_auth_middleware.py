"""Tests for auth_middleware package"""

import pytest
from datetime import timedelta

import auth_middleware


@pytest.fixture(autouse=True)
def _configure():
    auth_middleware.configure(secret_key="test-secret-key", algorithm="HS256")


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = auth_middleware.hash_password("mypassword123")
        assert hashed != "mypassword123"
        assert auth_middleware.verify_password("mypassword123", hashed)

    def test_wrong_password(self):
        hashed = auth_middleware.hash_password("correct")
        assert not auth_middleware.verify_password("wrong", hashed)


class TestJWT:
    def test_create_and_decode_access_token(self):
        data = {"sub": "user-1", "tenant_id": "tenant-1", "role": "admin", "email": "a@b.com"}
        token = auth_middleware.create_access_token(data)
        payload = auth_middleware.decode_token(token)
        assert payload["sub"] == "user-1"
        assert payload["tenant_id"] == "tenant-1"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        data = {"sub": "user-2", "tenant_id": "tenant-2", "role": "user", "email": "b@c.com"}
        token = auth_middleware.create_refresh_token(data)
        payload = auth_middleware.decode_token(token)
        assert payload["sub"] == "user-2"
        assert payload["type"] == "refresh"

    def test_expired_token(self):
        from fastapi import HTTPException
        data = {"sub": "user-1", "tenant_id": "t1", "role": "user"}
        token = auth_middleware.create_access_token(data, expires_delta=timedelta(seconds=-1))
        with pytest.raises(HTTPException) as exc_info:
            auth_middleware.decode_token(token)
        assert exc_info.value.status_code == 401

    def test_invalid_token(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            auth_middleware.decode_token("not.a.valid.token")


class TestUserPayload:
    def test_dataclass_fields(self):
        p = auth_middleware.UserPayload(user_id="u1", tenant_id="t1", role="admin", email="x@y.com")
        assert p.user_id == "u1"
        assert p.tenant_id == "t1"
        assert p.role == "admin"
        assert p.email == "x@y.com"
