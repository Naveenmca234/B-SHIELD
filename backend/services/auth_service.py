"""
Authentication & Authorization service.
- Passwords hashed with bcrypt (passlib)
- Stateless auth via JWT (python-jose)
- Role-based route protection via FastAPI dependencies
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Tuple, Union
from collections import defaultdict
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

import bcrypt
from config import settings
from database.mongodb import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class LoginRateLimiter:
    """
    In-memory brute-force protection tracking failed login attempts
    by combination of username + client IP.
    """
    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 300, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.window_seconds = window_seconds
        self.failures: Dict[str, List[float]] = defaultdict(list)
        self.lockouts: Dict[str, float] = {}

    def _key(self, username: str, ip: str) -> str:
        return f"{username.strip().lower()}@{ip.strip()}"

    def is_locked(self, username: str, ip: str) -> Tuple[bool, int]:
        key = self._key(username, ip)
        now = time.time()
        locked_until = self.lockouts.get(key, 0)
        if now < locked_until:
            remaining = int(locked_until - now) + 1
            return True, remaining
        if key in self.lockouts:
            del self.lockouts[key]
        return False, 0

    def record_failure(self, username: str, ip: str):
        key = self._key(username, ip)
        now = time.time()
        self.failures[key] = [t for t in self.failures[key] if now - t < self.window_seconds]
        self.failures[key].append(now)

        if len(self.failures[key]) >= self.max_attempts:
            self.lockouts[key] = now + self.lockout_seconds
            self.failures[key] = []

    def record_success(self, username: str, ip: str):
        key = self._key(username, ip)
        self.failures.pop(key, None)
        self.lockouts.pop(key, None)

    def reset_for_test(self):
        self.failures.clear()
        self.lockouts.clear()


login_rate_limiter = LoginRateLimiter()


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_token(token)
    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    db = get_db()
    if db is not None:
        user = await db.users.find_one({"username": username})
        if not user:
            raise HTTPException(status_code=401, detail="User no longer exists")

    return {"username": username, "role": role}


def require_roles(allowed_roles: List[str]):
    """FastAPI dependency factory for role-based route protection."""
    normalized_allowed = [r.lower() for r in allowed_roles]

    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "").lower()
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.get('role')}' is not permitted to perform this action.",
            )
        return current_user

    return role_checker


def require_role(allowed_roles: Union[List[str], str]):
    """Alias for require_roles supporting both single string or list with case-insensitivity."""
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
    return require_roles(allowed_roles)


require_admin = require_roles(["admin"])
require_operator = require_roles(["admin", "operator"])
require_any = require_roles(["admin", "operator", "viewer"])


class SimpleRateLimiter:
    """Sliding-window in-memory rate limiter for rate-limiting heavy endpoints like PDF export."""
    def __init__(self, max_requests: int = 15, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str):
        now = time.time()
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window_seconds]
        if len(self.requests[key]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait a moment before trying again.",
            )
        self.requests[key].append(now)


pdf_export_limiter = SimpleRateLimiter(max_requests=20, window_seconds=60)

