"""Подключение к базе данных."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    if DATABASE_URL.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_engine(DATABASE_URL, future=True, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def utcnow() -> datetime:
    """Наивное UTC-время (все даты в БД хранятся в UTC без tzinfo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def init_db() -> None:
    """Создать схему. Для PostgreSQL здесь же подключаются миграции Alembic."""
    from . import models  # noqa: F401  (регистрация моделей в metadata)

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI-зависимость: сессия БД на запрос."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
