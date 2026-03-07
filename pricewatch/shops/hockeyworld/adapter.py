from urllib.parse import urlparse, urljoin
from typing import List, Dict, Any
import logging

from pricewatch.core.plugin_base import BaseShopAdapter
from pricewatch.core.models import ProductItem
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HockeyWorldAdapter(BaseShopAdapter):
    name = "hockeyworld"
    domains = ("www.hockeyworld.com.ua", "hockeyworld.com.ua")

    def scrape_category(self, client, category):
        raise NotImplementedError("HockeyWorld adapter does not support scrape_category")

    def get_next_page(self, bsoup):
        # Find the pager container by id 'bottom-pagination'
        container = bsoup.find('div', id='bottom-pagination')
        if not container:
            return None

        # Find all anchor elements inside the pager
        anchors = container.find_all('a', href=True)
        if not anchors:
            return None

        last = anchors[-1]
        # Prefer title attribute, fallback to visible text
        title = (last.get('title') or last.get_text(strip=True) or '').strip()
        # Normalize title to handle 'ё' vs 'е' variants and case
        norm = title.replace('ё', 'е').lower()
        # If the last anchor is the "next" control ("Вперёд" / "Вперед"), return its href
        if norm == 'вперед':
            return last['href']

        return None

    def scrape_url(self, client, url, category=None):
        """Scrape products from the given URL on hockeyworld site.

        Each product is expected inside <div class="product">.
        - price: inside <div class="PricesalesPrice"> (text)
        - description/name: inside <div class="product-s-desc"> (text)
        - product link: inside <div class="product-addtocart"> (first <a href> or data-href)
        """
        # Normalize start URL
        current = url if url.startswith('http') else 'https://' + url
        logger.info("HockeyWorldAdapter.scrape_url: fetching %s (category=%s)", current, category)

        items = []
        visited = set()
        max_pages = 20
        page_count = 0

        while current and page_count < max_pages:
            if current in visited:
                logger.debug("already visited %s, stopping pagination", current)
                break
            visited.add(current)
            page_count += 1

            resp = client.safe_get(current, session=client.session)
            if not resp:
                logger.warning("no response from %s", current)
                break

            soup = BeautifulSoup(resp.content, 'html.parser')
            product_nodes = soup.find_all('div', class_='product')
            logger.info("page %d: found %d product nodes on %s", page_count, len(product_nodes), current)

            for node in product_nodes:
                # extract name/description
                name_node = node.find('div', class_='product-s-desc')
                name = name_node.get_text(' ', strip=True) if name_node else ''

                # extract price (raw)
                price_node = node.find('div', class_='PricesalesPrice')
                price = price_node.get_text(' ', strip=True) if price_node else ''

                # extract link: prefer anchor inside product-addtocart
                link = None
                add_node = node.find('div', class_='product-addtocart')
                if add_node:
                    a = add_node.find('a', href=True)
                    if a:
                        link = a['href']
                    else:
                        # fallback: look for any element with data-href or onclick
                        data_href = add_node.get('data-href') or add_node.get('data-url')
                        if data_href:
                            link = data_href
                        else:
                            # try to find button with onclick containing URL
                            btn = add_node.find(attrs={'onclick': True})
                            if btn:
                                onclick = btn.get('onclick')
                                # try to extract a quoted URL
                                import re

                                m = re.search(r"['\"](https?://[^'\"]+)['\"]", onclick)
                                if m:
                                    link = m.group(1)

                # if still no link, try any <a> inside the product node
                if not link:
                    a_any = node.find('a', href=True)
                    if a_any:
                        link = a_any['href']

                # build absolute link relative to current page
                full_link = urljoin(current, link) if link else current

                domain = urlparse(full_link).netloc

                item = ProductItem(
                    name=name,
                    price_raw=price,
                    url=full_link,
                    source_site=domain,
                )
                items.append(item)

            # find next page href using get_next_page
            next_href = self.get_next_page(soup)
            if not next_href:
                break

            # resolve next URL relative to current
            next_url = urljoin(current, next_href)
            logger.info("pagination: next page found -> %s", next_url)
            current = next_url

        if category:
            key = category.lower()
            before = len(items)
            items = [it for it in items if key in (it.name or '').lower() or key in (it.url or '').lower()]
            logger.info("filtered %d -> %d items using category '%s'", before, len(items), category)

        logger.info("returning %d items", len(items))
        return items

    def get_categories(self, client):
        host = next(iter(self.domains), None)
        if not host:
            return []
        base = f"http://{host}"

        try:
            resp = client.safe_get(base, session=client.session)
        except Exception as exc:
            logger.warning("get_categories: failed to fetch %s: %s", base, exc)
            return []

        if not resp:
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        out = []
        # Only look for links inside <div class="menu_round"> blocks
        containers = soup.find_all('div', class_='menu_round')
        if not containers:
            logger.debug("no .menu_round blocks found on the page")
            return []

        for block in containers:
            for a in block.find_all('a', href=True):
                href = a['href']
                if not href.startswith('/kategorii-tovarov/'):
                    continue
                span = a.find('span')
                name = span.get_text(strip=True) if span else a.get_text(" ", strip=True)
                full = urljoin(base, href)
                # ensure same domain
                if urlparse(full).netloc != urlparse(base).netloc:
                    continue
                logger.debug("discovered hockeyworld category: %s -> %s", name, full)
                out.append({'name': name, 'url': full})

        # Sort categories by name (case-insensitive) for deterministic output
        out.sort(key=lambda x: (x.get('name') or '').lower())

        return out

    def get_products_by_category(self, category: Dict[str, Any], client=None) -> List[Dict[str, Any]]:
        """Return products as plain dict DTOs per adapter contract."""
        client = client or getattr(self, "_client", None)
        if client is None:
            raise ValueError("client is required")
        target = category.get("url") or category.get("name") or ""
        raw_items = self.scrape_url(client, target, category.get("name")) if target else []
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
