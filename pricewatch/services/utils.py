from __future__ import annotations
from urllib.parse import urlparse

from pricewatch.core.registry import get_registry
from pricewatch.db.models import Store


def resolve_adapter_for_store(store: Store):
    """Try to find adapter for given store by name, domain, or reference flag."""
    registry = get_registry()
    for adapter in registry.adapters:
        if adapter.name == store.name:
            return adapter
    if store.base_url:
        host = urlparse(store.base_url if store.base_url.startswith("http") else f"https://{store.base_url}").netloc
        for adapter in registry.adapters:
            domains = getattr(adapter, "domains", ()) or ()
            if any(host == d or host.endswith(f".{d}") for d in domains):
                return adapter
    if getattr(store, "is_reference", False):
        try:
            return registry.reference_adapter()
        except Exception:
            pass
    return None
