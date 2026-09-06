import pytest
from datetime import timedelta
from fastapi import HTTPException
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    require_roles,
)
from routes.live import extract_and_validate_stream_token


def test_password_hashing():
    raw = "ControlRoom#2026"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_create_and_decode():
    payload = {"sub": "operator1", "role": "operator"}
    token = create_access_token(payload, expires_minutes=15)
    decoded = decode_token(token)

    assert decoded["sub"] == "operator1"
    assert decoded["role"] == "operator"
    assert "exp" in decoded


def test_jwt_expired_or_tampered():
    # Expired token
    payload = {"sub": "operator1", "role": "operator"}
    expired_token = create_access_token(payload, expires_minutes=-10)

    with pytest.raises(HTTPException) as excinfo:
        decode_token(expired_token)
    assert excinfo.value.status_code == 401

    # Tampered token
    with pytest.raises(HTTPException) as excinfo:
        decode_token("invalid.token.signature")
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_role_authorization():
    admin_checker = require_roles(["admin"])
    operator_checker = require_roles(["admin", "operator"])

    admin_user = {"username": "admin", "role": "admin"}
    operator_user = {"username": "op1", "role": "operator"}
    viewer_user = {"username": "view1", "role": "viewer"}

    # Admin passes both
    assert await admin_checker(admin_user) == admin_user
    assert await operator_checker(admin_user) == admin_user

    # Operator passes operator checker, fails admin
    assert await operator_checker(operator_user) == operator_user
    with pytest.raises(HTTPException) as exc:
        await admin_checker(operator_user)
    assert exc.value.status_code == 403

    # Viewer fails both
    with pytest.raises(HTTPException) as exc:
        await admin_checker(viewer_user)
    assert exc.value.status_code == 403


def test_stream_token_extraction():
    token = create_access_token({"sub": "admin", "role": "admin"})

    # Valid query token
    user = extract_and_validate_stream_token(token=token, authorization=None)
    assert user["sub"] == "admin"
    assert user["role"] == "admin"

    # Valid header token
    user_header = extract_and_validate_stream_token(token=None, authorization=f"Bearer {token}")
    assert user_header["sub"] == "admin"

    # Missing token -> 401
    with pytest.raises(HTTPException) as exc:
        extract_and_validate_stream_token(token=None, authorization=None)
    assert exc.value.status_code == 401


def test_login_rate_limiter_unit():
    from services.auth_service import LoginRateLimiter
    limiter = LoginRateLimiter(max_attempts=3, lockout_seconds=60, window_seconds=60)

    # 1. First 2 failures: not locked
    limiter.record_failure("user1", "127.0.0.1")
    locked, _ = limiter.is_locked("user1", "127.0.0.1")
    assert locked is False

    limiter.record_failure("user1", "127.0.0.1")
    locked, _ = limiter.is_locked("user1", "127.0.0.1")
    assert locked is False

    # 2. 3rd failure: reaches threshold -> locked
    limiter.record_failure("user1", "127.0.0.1")
    locked, remaining = limiter.is_locked("user1", "127.0.0.1")
    assert locked is True
    assert 0 < remaining <= 60

    # 3. Different user or different IP is not locked
    locked2, _ = limiter.is_locked("user2", "127.0.0.1")
    assert locked2 is False
    locked3, _ = limiter.is_locked("user1", "192.168.1.100")
    assert locked3 is False

    # 4. Success resets counter
    limiter.record_success("user1", "127.0.0.1")
    locked_after, _ = limiter.is_locked("user1", "127.0.0.1")
    assert locked_after is False


def test_login_rate_limiting_api_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    from services.auth_service import login_rate_limiter
    from unittest.mock import AsyncMock, patch, MagicMock

    login_rate_limiter.reset_for_test()
    client = TestClient(app)

    # Mock DB with a seeded admin user
    class MockDB:
        def __init__(self):
            self.users = MagicMock()
            self.users.find_one = AsyncMock(return_value={
                "username": "admin",
                "passwordHash": hash_password("IBVAP@123"),
                "role": "admin",
                "fullName": "Administrator",
            })

    with patch("routes.auth.get_db", return_value=MockDB()):
        # 1. First 4 bad attempts: 401 with generic message
        for _ in range(4):
            res = client.post("/auth/login", json={"username": "admin", "password": "WrongPassword"})
            assert res.status_code == 401
            assert res.json()["detail"] == "Invalid username or password"

        # 2. 5th bad attempt triggers lockout
        res = client.post("/auth/login", json={"username": "admin", "password": "WrongPassword"})
        assert res.status_code == 401

        # 3. 6th attempt is blocked with 429
        res_locked = client.post("/auth/login", json={"username": "admin", "password": "IBVAP@123"})
        assert res_locked.status_code == 429
        assert "temporarily locked" in res_locked.json()["detail"]

        # Reset and verify successful login
        login_rate_limiter.reset_for_test()
        res_ok = client.post("/auth/login", json={"username": "admin", "password": "IBVAP@123"})
        assert res_ok.status_code == 200
        assert "access_token" in res_ok.json()

