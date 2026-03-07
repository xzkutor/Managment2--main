from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from pricewatch.db.models import Store
from pricewatch.db.repositories import list_stores, get_store, get_or_create_store


class StoreService:
    """Service helpers around store metadata and adapters."""

    def __init__(self, session: Session):
        self.session = session

    def list_stores(self) -> List[Store]:
        return list_stores(self.session)

    def get_store(self, store_id: int) -> Store:
        store = get_store(self.session, store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found")
        return store

    def get_reference_store(self) -> Store | None:
        return self.session.query(Store).filter(Store.is_reference.is_(True)).first()

    def register_store(self, *, name: str, base_url: str | None = None, is_reference: bool = False) -> Store:
        return get_or_create_store(self.session, name, base_url=base_url, is_reference=is_reference)

    def sync_with_registry(self, registry) -> List[Store]:
        """Ensure every adapter from the registry has a Store entry."""
        adapters = list(getattr(registry, "adapters", []) or [])
        synced_names: set[str] = set()
        for adapter in adapters:
            store = self.register_store(
                name=adapter.name,
                base_url=self._adapter_base_url(adapter),
                is_reference=bool(getattr(adapter, "is_reference", False)),
            )
            synced_names.add(store.name)
        try:
            reference_adapter = registry.reference_adapter()
        except Exception:
            reference_adapter = None
        if reference_adapter and reference_adapter.name not in synced_names:
            self.register_store(
                name=reference_adapter.name,
                base_url=self._adapter_base_url(reference_adapter),
                is_reference=True,
            )
        self.session.flush()
        return self.list_stores()

    @staticmethod
    def _adapter_base_url(adapter) -> str | None:
        base_url = getattr(adapter, "base_url", None)
        if base_url:
            return base_url
        domains = getattr(adapter, "domains", None) or []
        if domains:
            domain = domains[0]
            if domain.startswith("http://") or domain.startswith("https://"):
                return domain
            return f"https://{domain}"
        return None
