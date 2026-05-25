from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.auth.models import TokenPayload, User
from app.core.config import settings


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = TokenPayload(
        sub=user.username,
        roles=[r.value for r in user.roles],
        exp=int(expire.timestamp()),
    )
    return jwt.encode(payload.model_dump(), settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError as e:
        raise ValueError("Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise ValueError("Invalid token") from e
