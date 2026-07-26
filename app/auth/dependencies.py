from __future__ import annotations

from functools import wraps
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_access_token
from app.auth.models import TokenPayload, UserRole
from app.core.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)

ROLE_HIERARCHY: dict[str, set[str]] = {
    "admin": {"admin", "operator", "viewer", "auditor"},
    "operator": {"operator", "viewer"},
    "auditor": {"auditor", "viewer"},
    "viewer": {"viewer"},
}

ENDPOINT_PERMISSIONS: dict[str, set[str]] = {
    "tasks:create": {"admin", "operator"},
    "tasks:read": {"admin", "operator", "viewer", "auditor"},
    "approvals:decide": {"admin", "operator"},
    "approvals:read": {"admin", "operator", "viewer", "auditor"},
    "audit:read": {"admin", "auditor"},
    "audit:export": {"admin", "auditor"},
    "metrics:read": {"admin", "operator", "viewer", "auditor"},
    "tools:call": {"admin", "operator"},
    "tools:read": {"admin", "operator", "viewer", "auditor"},
    "eval:run": {"admin", "operator"},
    "eval:read": {"admin", "operator", "viewer", "auditor"},
    "memory:read": {"admin", "operator", "viewer", "auditor"},
    "memory:manage": {"admin", "operator"},
    "nl2sql:run": {"admin", "operator"},
    "reflection:run": {"admin", "operator"},
    "skills:read": {"admin", "operator", "viewer", "auditor"},
    "snapshot:read": {"admin", "operator", "viewer", "auditor"},
    "snapshot:manage": {"admin"},
}


class DevUser:
    def __init__(self) -> None:
        self.username = "system"
        self.roles = ["admin"]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> DevUser | TokenPayload:
    if not settings.auth_enabled:
        return DevUser()

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
    return payload


async def optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> DevUser | TokenPayload | None:
    if not settings.auth_enabled:
        return DevUser()

    if credentials is None:
        return None

    try:
        return decode_access_token(credentials.credentials)
    except ValueError:
        return None


def require_roles(*required_roles: str) -> Callable:
    async def role_checker(
        current_user: DevUser | TokenPayload = Depends(get_current_user),
    ) -> DevUser | TokenPayload:
        if not settings.rbac_enabled:
            return current_user

        if isinstance(current_user, DevUser):
            return current_user

        user_roles = set(current_user.roles)
        allowed_roles = set(required_roles)

        expanded = set()
        for role in user_roles:
            expanded.update(ROLE_HIERARCHY.get(role, {role}))

        if not expanded & allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user_roles} not authorized. Required: {allowed_roles}",
            )
        return current_user

    return role_checker


def require_permission(permission: str) -> Callable:
    allowed_roles = ENDPOINT_PERMISSIONS.get(permission, {"admin"})

    async def permission_checker(
        current_user: DevUser | TokenPayload = Depends(get_current_user),
    ) -> DevUser | TokenPayload:
        if not settings.rbac_enabled:
            return current_user

        if isinstance(current_user, DevUser):
            return current_user

        user_roles = set(current_user.roles)
        expanded = set()
        for role in user_roles:
            expanded.update(ROLE_HIERARCHY.get(role, {role}))

        if not expanded & allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for {permission}",
            )
        return current_user

    return permission_checker
