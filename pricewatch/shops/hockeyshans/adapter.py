import re
import logging
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Any

from bs4 import BeautifulSoup

from pricewatch.core.plugin_base import BaseShopAdapter
from pricewatch.core.pagination import paginate_and_collect
from pricewatch.core.models import ProductItem
from pricewatch.core.category_discovery import find_category_page

logger = logging.getLogger(__name__)


class HockeyShansAdapter(BaseShopAdapter):
    name = "hockeyshans"
    domains = ("hockeyshans.com.ua", "old.hockeyshans.com.ua")

    def scrape_category(self, client, category):
        # Accept category as name, slug, or URL/path. Resolve to a category URL and scrape it.
        host = next(iter(self.domains), None)
        if not host:
            return []
        base = f"https://{host}"

        # If category already looks like a URL or path, resolve and scrape
        if isinstance(category, str) and (category.startswith('http') or category.startswith('/')):
            url = category if category.startswith('http') else urljoin(base, category)
            return self.scrape_url(client, url, category)

        # Try to find an exact or partial match from site categories
        cats = self.get_categories(client)
        key = (category or '').lower()
        for c in cats:
            if not c.get('name'):
                continue
            if key == c['name'].lower() or key in c['name'].lower() or key in c['url'].lower():
                return self.scrape_url(client, c['url'], category)

        # Fallback: try shared discovery helper
        candidate = find_category_page(client, client.session, base, category)
        if candidate:
            return self.scrape_url(client, candidate, category)

        return []

    def scrape_url(self, client, url, category=None):
        # pagination-aware scraping for hockeyshans
        parsed = urlparse(url if url.startswith("http") else "https://" + url)
        cat = None
        match = re.search(r"/category/(\d+)", parsed.path)
        if match:
            cat = match.group(1)
        if category and not cat:
            cat = str(category)

        if cat:
            base = f"https://hockeyshans.com.ua/category/{cat}"
        else:
            base = url if url.startswith("http") else "https://" + url

        item_selectors = [
            "div.thumbnail",
        ]

        name_selectors = [
            "div.caption h4",
        ]

        price_selectors = [
            ".btn-primary",
        ]

        link_selectors = [
            'a[href^="/item/"]',
        ]

        raw = paginate_and_collect(
            client,
            client.session,
            base,
            item_selectors,
            name_selectors,
            price_selectors,
            link_selectors,
        )
        results = []
        for r in raw:
            results.append(
                ProductItem(
                    name=r.get("name", ""),
                    price_raw=r.get("price", ""),
                    url=r.get("url", ""),
                    source_site="hockeyshans.com.ua",
                )
            )
        return results

    def get_categories(self, client):
        host = next(iter(self.domains), None)
        if not host:
            return []
        base = f"https://{host}"

        try:
            resp = client.safe_get(base, session=client.session)
        except Exception as exc:
            logger.warning("get_categories: failed to fetch %s: %s", base, exc)
            return []

        if not resp:
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        menu = soup.select_one('div.navbar.category')
        out = []
        seen = set()
        main_cat = ""
        for a in menu.find_all('a', href=True):
            href = a['href']
            if '/category/' not in href:
                main_cat = a.get_text(' ', strip=True)
                continue
            full = urljoin(base, href)
            if urlparse(full).netloc != urlparse(base).netloc:
                continue
            if full in seen:
                continue
            seen.add(full)
            part = a.get_text(' ', strip=True) or a.get('title') or ''
            name = ' | '.join(filter(None, [(main_cat or '').strip(), part.strip()]))
            out.append({'name': name, 'url': full})
        # Sort categories by name (case-insensitive) for deterministic output
        out.sort(key=lambda x: (x.get('name') or '').lower())
        return out

    def get_products_by_category(self, category: Dict[str, Any], client=None) -> List[Dict[str, Any]]:
        client = client or getattr(self, "_client", None)
        if client is None:
            raise ValueError("client is required")
        target = category.get("url") or category.get("name") or ""
        raw_items = self.scrape_category(client, target) if target else []
        products: List[Dict[str, Any]] = []
        for item in raw_items:
            products.append({
                "name": getattr(item, "name", ""),
                "product_url": getattr(item, "url", ""),
                "price": None,
                "price_raw": getattr(item, "price_raw", None),
                "currency": None,
                "description": None,
                "source_url": getattr(item, "source_site", None),
                "external_id": None,
                "is_available": None,
            })
        return products
