"""pricewatch.web.context — Web-layer dependency and context helpers.

Provides thin wrappers for accessing Flask app-context resources
(DB session, config flags, etc.) from Blueprint route handlers.

These helpers are the *only* place where Blueprint code should reach
into ``current_app.extensions``; they keep that coupling in one place.
"""
from __future__ import annotations

from flask import current_app


def get_db_session():
    """Return the scoped SQLAlchemy session bound to the current app context.

    Usage inside a route handler::

        session = get_db_session()()  # call the scoped-session to get a Session
    """
    return current_app.extensions["db_scoped_session"]

