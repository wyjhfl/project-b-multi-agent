from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class UserRole(str, Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"
    auditor = "auditor"


class User(BaseModel):
    user_id: str
    username: str
    password_hash: str
    roles: list[UserRole]
    disabled: bool = False
    created_at: datetime | None = None


class TokenPayload(BaseModel):
    sub: str
    roles: list[str]
    exp: int


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    username: str
    roles: list[str]
    disabled: bool
