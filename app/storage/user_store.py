from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from app.auth.models import User, UserRole
from app.auth.password import hash_password, verify_password


class InMemoryUserStore:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    def create_user(self, username: str, password: str, roles: list[UserRole], disabled: bool = False) -> User:
        if username in self._users:
            raise ValueError(f"User {username} already exists")
        user = User(
            user_id=f"usr_{uuid.uuid4().hex[:12]}",
            username=username,
            password_hash=hash_password(password),
            roles=roles,
            disabled=disabled,
            created_at=datetime.now(timezone.utc),
        )
        self._users[username] = user
        return user

    def get_user_by_username(self, username: str) -> User | None:
        return self._users.get(username)

    def authenticate_user(self, username: str, password: str) -> User | None:
        user = self._users.get(username)
        if user is None:
            return None
        if user.disabled:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def seed_default_admin_if_empty(self) -> None:
        if self._users:
            return
        dev_admin_password = os.environ.get("DEV_ADMIN_PASSWORD", "admin123")
        self.create_user(
            username="admin",
            password=dev_admin_password,
            roles=[UserRole.admin],
        )
        self.create_user(
            username="operator",
            password=dev_admin_password,
            roles=[UserRole.operator],
        )
        self.create_user(
            username="viewer",
            password=dev_admin_password,
            roles=[UserRole.viewer],
        )
        self.create_user(
            username="auditor",
            password=dev_admin_password,
            roles=[UserRole.auditor],
        )
