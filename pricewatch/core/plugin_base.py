from abc import ABC, abstractmethod
from typing import Any, Dict, List
from urllib.parse import urlparse


class BaseShopAdapter(ABC):
    name = ""
    domains = ()
    is_reference = False

    def match(self, url: str) -> bool:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        host = parsed.netloc.lower()
        return any(host == domain or host.endswith(f".{domain}") for domain in self.domains)

    def get_categories(self, client):
        return []

    @abstractmethod
    def scrape_category(self, client, category):
        raise NotImplementedError

    @abstractmethod
    def scrape_url(self, client, url, category=None):
        raise NotImplementedError

    def get_products_by_category(self, category: Dict[str, Any], client=None) -> List[Dict[str, Any]]:
        """Fetch products for the provided category DTO.

        Category DTO must be a dict with these keys (any missing key should be None):
        {
            "id": int | None,
            "external_id": str | None,
            "name": str,
            "url": str | None,
        }

        Each returned product DTO should look like:
        {
            "external_id": str | None,
            "name": str,
            "price": float | int | None,
            "price_raw": str | None,
            "currency": str | None,
            "description": str | None,
            "product_url": str,
            "source_url": str | None,
            "is_available": bool | None,
        }
        """
        raise NotImplementedError
