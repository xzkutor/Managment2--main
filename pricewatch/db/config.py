from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional, Type

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import scoped_session, sessionmaker, Session

from .base import Base

DEFAULT_DB_URL = "sqlite:///pricewatch.db"
IN_MEMORY_URL = "sqlite+pysqlite:///:memory:"


def _coerce_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def resolve_database_url(app_config: Optional[dict] = None) -> str:
    if app_config and app_config.get("DATABASE_URL"):
        return str(app_config["DATABASE_URL"])
    return os.getenv("DATABASE_URL", DEFAULT_DB_URL)


def should_skip_create_all(app_config: Optional[dict] = None) -> bool:
    if _coerce_bool(os.getenv("DB_SKIP_CREATE_ALL")):
        return True
    flask_env = (app_config or {}).get("FLASK_ENV") or os.getenv("FLASK_ENV", "")
    return flask_env.lower() == "production"


def init_engine(app_config: Optional[dict] = None) -> Engine:
    url = resolve_database_url(app_config)
    echo = _coerce_bool(str((app_config or {}).get("DB_DEBUG_SQL", os.getenv("DB_DEBUG_SQL", ""))))
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=echo, future=True, connect_args=connect_args)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_scoped_session(factory: sessionmaker[Session]):
    return scoped_session(factory)


def init_db(engine: Engine, *, base: Type[Base] = Base, app_config: Optional[dict] = None) -> None:
    if should_skip_create_all(app_config):
        return
    base.metadata.create_all(engine)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_test_engine_and_session():
    engine = create_engine(IN_MEMORY_URL, echo=False, future=True, connect_args={"check_same_thread": False})
    factory = get_session_factory(engine)
    Base.metadata.create_all(engine)
    return engine, factory
