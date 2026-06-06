from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import create_access_token, decode_access_token
from app.auth.models import LoginRequest, TokenResponse, UserInfo, User
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer_scheme = HTTPBearer(auto_error=False)

_user_store = None


def _get_user_store():
    global _user_store
    if _user_store is None:
        from app.storage.factory import get_user_store
        _user_store = get_user_store()
        _user_store.seed_default_admin_if_empty()
    return _user_store


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    store = _get_user_store()
    user = store.authenticate_user(request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(user)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserInfo)
async def get_me(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    store = _get_user_store()
    user = store.get_user_by_username(payload.sub)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return UserInfo(username=user.username, roles=[r.value for r in user.roles], disabled=user.disabled)
