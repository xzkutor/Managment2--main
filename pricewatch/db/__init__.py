"""Database package for pricewatch.

Provides SQLAlchemy engine/session helpers, models, and repository layer.
"""

from .config import init_engine, init_db, get_session_factory, get_scoped_session
from .base import Base
from . import models  # noqa: F401  # ensure models are registered

__all__ = [
    "Base",
    "init_engine",
    "init_db",
    "get_session_factory",
    "get_scoped_session",
]
