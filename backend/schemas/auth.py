from pydantic import BaseModel
from typing import Literal, Optional

Role = Literal["admin", "operator", "viewer"]


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    role: Role
    fullName: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    username: str
    password: str
    role: Role
    fullName: Optional[str] = None
