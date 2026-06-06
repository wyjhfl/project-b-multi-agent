from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from app.auth.models import User, UserRole
from app.auth.password import hash_password, verify_password
from app.storage.database import get_session_factory
from app.storage.models import UserRow


class PostgresUserStore:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def create_user(self, username: str, password: str, roles: list[UserRole], disabled: bool = False) -> User:
        with self._session_factory() as session:
            existing = session.query(UserRow).filter_by(username=username).first()
            if existing is not None:
                raise ValueError(f"User {username} already exists")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            row = UserRow(
                user_id=f"usr_{uuid.uuid4().hex[:12]}",
                username=username,
                password_hash=hash_password(password),
                roles=self._serialize_roles(roles),
                disabled=1 if disabled else 0,
                created_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._row_to_user(row)

    def get_user_by_username(self, username: str) -> User | None:
        with self._session_factory() as session:
            row = session.query(UserRow).filter_by(username=username).first()
            if row is None:
                return None
            return self._row_to_user(row)

    def authenticate_user(self, username: str, password: str) -> User | None:
        user = self.get_user_by_username(username)
        if user is None:
            return None
        if user.disabled:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def seed_default_admin_if_empty(self) -> None:
        with self._session_factory() as session:
            has_user = session.query(UserRow.user_id).first() is not None
        if has_user:
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

    def _serialize_roles(self, roles: list[UserRole]) -> str:
        return ",".join(role.value if isinstance(role, UserRole) else str(role) for role in roles)

    def _parse_roles(self, raw_roles: str | None) -> list[UserRole]:
        parsed: list[UserRole] = []
        for item in (raw_roles or "").split(","):
            value = item.strip()
            if not value:
                continue
            try:
                parsed.append(UserRole(value))
            except ValueError:
                continue
        return parsed or [UserRole.viewer]

    def _row_to_user(self, row: UserRow) -> User:
        created_at = row.created_at
        if created_at is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return User(
            user_id=row.user_id,
            username=row.username,
            password_hash=row.password_hash,
            roles=self._parse_roles(row.roles),
            disabled=bool(row.disabled),
            created_at=created_at,
        )
