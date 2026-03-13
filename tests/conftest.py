"""Shared pytest fixtures for integration tests.

These fixtures wire the Flask test app and the session helpers to the
*same* in-memory SQLite engine so that data committed through a session
helper is immediately visible to Flask endpoints called via test_client().

Usage in a test
---------------

    def test_something(flask_app, client, db_session_scope):
        with db_session_scope() as session:
            # insert rows through session ...
            session.flush()   # IDs are assigned
            ref_cat_id = ref_cat.id
        # session is committed on exit

        resp = client.get(f"/api/categories/{ref_cat_id}/mapped-target-categories")
        assert resp.status_code == 200
        assert resp.get_json()["mapped_target_categories"] != []
"""
from __future__ import annotations

import os as _os

# Suppress scheduler autostart for the entire test process.
# This must happen before `app` module is imported (which triggers create_app()
# at module level and would otherwise start a real background thread).
# conftest.py is loaded by pytest before any test-module imports, so this
# setdefault runs before `from app import app` in test files.
_os.environ.setdefault("SCHEDULER_ENABLED", "false")

from contextlib import contextmanager
from typing import Iterator

import pytest
from sqlalchemy.orm import Session

from pricewatch.db.testing import make_test_db
from pricewatch.db.config import session_scope


@pytest.fixture()
def shared_engine():
    """Fresh in-memory SQLite engine with tables created.  Torn down after each test."""
    engine, factory, scoped = make_test_db()
    yield engine, factory, scoped
    scoped.remove()
    from pricewatch.db.base import Base
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def flask_app(shared_engine):
    """Flask application instance wired to the test engine.

    The app is created with TESTING=True (suppresses bootstrap) and then its
    DB extensions are replaced with the shared test engine/factory/scoped_session
    so that Flask routes read from the same in-memory DB as the test helpers.
    """
    from app import create_app

    engine, factory, scoped = shared_engine

    test_app = create_app({
        "TESTING": True,
        "DATABASE_URL": str(engine.url),
    })

    # Inject the *exact same* engine/factory/scoped_session so there is only
    # one connection pool and data written before the request is visible inside it.
    with test_app.app_context():
        test_app.extensions["db_engine"] = engine
        test_app.extensions["db_session_factory"] = factory
        test_app.extensions["db_scoped_session"] = scoped

    test_app.config["TESTING"] = True
    return test_app


@pytest.fixture()
def client(flask_app):
    """Flask test client backed by the shared test DB."""
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def db_session_scope(shared_engine):
    """Context-manager factory that yields a committed session using the shared engine.

    Example::

        with db_session_scope() as session:
            store = get_or_create_store(session, "MyStore", is_reference=True)
            session.flush()
            store_id = store.id
        # committed here — visible to Flask client
    """
    _engine, factory, _scoped = shared_engine

    @contextmanager
    def _scope() -> Iterator[Session]:
        with session_scope(factory) as session:
            yield session

    return _scope

