from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request, status

from schemas.auth import LoginRequest, TokenResponse, UserOut, UserCreate
from services.auth_service import (
    verify_password, create_access_token, require_admin, hash_password, get_current_user,
    login_rate_limiter,
)
from database.mongodb import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    locked, remaining = login_rate_limiter.is_locked(payload.username, client_ip)
    if locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Access temporarily locked. Try again in {remaining}s.",
        )

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable. Please try again shortly.")

    user = await db.users.find_one({"username": payload.username})
    if not user or not verify_password(payload.password, user.get("passwordHash", "")):
        login_rate_limiter.record_failure(payload.username, client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    login_rate_limiter.record_success(payload.username, client_ip)
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return TokenResponse(
        access_token=token,
        user=UserOut(username=user["username"], role=user["role"], fullName=user.get("fullName")),
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    # Stateless JWT - logout is handled client-side by discarding the token.
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    db = get_db()
    user = await db.users.find_one({"username": current_user["username"]}) if db is not None else None
    return UserOut(
        username=current_user["username"],
        role=current_user["role"],
        fullName=user.get("fullName") if user else None,
    )


@router.get("/users")
async def list_users(current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        return []
    users = []
    async for u in db.users.find({}, {"passwordHash": 0}):
        u["_id"] = str(u["_id"])
        users.append(u)
    return users


@router.post("/users")
async def create_user(payload: UserCreate, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    existing = await db.users.find_one({"username": payload.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    doc = {
        "username": payload.username,
        "passwordHash": hash_password(payload.password),
        "role": payload.role,
        "fullName": payload.fullName,
        "createdAt": datetime.utcnow().isoformat(),
    }
    await db.users.insert_one(doc)
    return {"message": "User created", "username": payload.username}


@router.delete("/users/{username}")
async def delete_user(username: str, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    result = await db.users.delete_one({"username": username})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}
