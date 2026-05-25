from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine = None
_session_factory = None


def create_engine_from_settings() -> None:
    global _engine, _session_factory
    if settings.storage_backend == "postgres" and settings.database_url:
        _engine = create_engine(settings.database_url, echo=settings.debug)
    else:
        _engine = create_engine(
            "sqlite:///" + settings.runtime_db_path,
            echo=settings.debug,
            connect_args={"check_same_thread": False},
        )
    _session_factory = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)


def get_engine():
    if _engine is None:
        create_engine_from_settings()
    return _engine


def get_session_factory() -> sessionmaker:
    if _session_factory is None:
        create_engine_from_settings()
    return _session_factory


def check_database_health() -> dict[str, str]:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(type(engine).text("SELECT 1") if hasattr(engine, "text") else __import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok", "backend": settings.storage_backend}
    except Exception as e:
        return {"status": "error", "backend": settings.storage_backend, "error": str(e)}
