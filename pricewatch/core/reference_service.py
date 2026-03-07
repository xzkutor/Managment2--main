from urllib.parse import urlparse
import logging

from .normalize import MAIN_NORMALIZED, normalize_title
from .models import ProductItem, ParsedPrice
from .normalize import parse_price

logger = logging.getLogger(__name__)


class ReferenceCatalogBuilder:
    def __init__(self, reference_adapter, client):
        self.reference_adapter = reference_adapter
        self.client = client

    def build(self, categories=None):
        if categories is None:
            categories = self.reference_adapter.get_categories(self.client)
            logger.info("fetch_main_site_products: discovered %d categories", len(categories))
        results = []
        for cat in categories:
            if isinstance(cat, dict):
                cat_key = cat.get('name') or cat.get('url') or ''
            else:
                cat_key = cat
            logger.info("fetch_main_site_products: category=%s", cat_key)
            items = self.reference_adapter.scrape_category(self.client, category=cat_key)
            for it in items:
                price_value, price_currency = parse_price(it.price_raw)
                parsed_price = ParsedPrice(price_value, price_currency)
                results.append(
                    ProductItem(
                        name=it.name,
                        price_raw=it.price_raw,
                        url=it.url,
                        source_site=it.source_site or (urlparse(it.url).netloc or "prohockey.com.ua"),
                        parsed_price=parsed_price,
                    )
                )
        MAIN_NORMALIZED.clear()
        for r in results:
            MAIN_NORMALIZED.append(normalize_title(r.name))
        return results
