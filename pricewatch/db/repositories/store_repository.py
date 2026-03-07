from __future__ import annotations

from sqlalchemy.orm import Session

from pricewatch.db.models import Store


def get_store(session: Session, store_id: int) -> Store | None:
    return session.get(Store, store_id)


def get_store_by_name(session: Session, name: str) -> Store | None:
    return session.query(Store).filter(Store.name == name).one_or_none()


def list_stores(session: Session) -> list[Store]:
    return session.query(Store).order_by(Store.name).all()


def get_or_create_store(session: Session, name: str, *, is_reference: bool = False, base_url: str | None = None) -> Store:
    store = get_store_by_name(session, name)
    if store:
        updated = False
        if base_url is not None and base_url != store.base_url:
            store.base_url = base_url
            updated = True
        if is_reference != store.is_reference:
            store.is_reference = is_reference
            updated = True
        if updated:
            session.flush()
        return store
    store = Store(name=name, is_reference=is_reference, base_url=base_url)
    session.add(store)
    session.flush()
    return store
