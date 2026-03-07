from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Tuple

from sqlalchemy.orm import Session, sessionmaker

from pricewatch.db.config import create_test_engine_and_session, session_scope
from pricewatch.db.base import Base


def make_test_session_factory() -> Tuple[Session, sessionmaker[Session]]:
    engine, factory = create_test_engine_and_session()
    return factory(), factory


@contextmanager
def test_session_scope() -> Iterator[Session]:
    engine, factory = create_test_engine_and_session()
    try:
        with session_scope(factory) as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
