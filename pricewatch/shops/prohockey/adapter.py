from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from pricewatch.core.plugin_base import BaseShopAdapter
from pricewatch.core.pagination import paginate_and_collect
from pricewatch.core.category_discovery import find_category_page
from pricewatch.core.models import ProductItem


class ProHockeyAdapter(BaseShopAdapter):
    name = "prohockey"
    domains = ("prohockey.com.ua", "www.prohockey.com.ua")
    is_reference = True

    def get_categories(self, client):
        host = next(iter(self.domains), None)
        if not host:
            return []
        base = f"http://{host}"

        try:
            resp = client.safe_get(base, session=client.session)
        except Exception as exc:
            print(f"get_categories: failed to fetch {base}: {exc}")
            return []

        if not resp:
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        out = []
        # Only look for links inside <a class="dropdown-item"> blocks
        # Accept either 'dropdown-item' or 'nav-link' classes
        containers = [
            a for a in soup.find_all('a', href=True)
            if 'dropdown-item' in (a.get('class') or []) or 'nav-link' in (a.get('class') or [])
        ]
        if not containers:
            print("  -> no .menu_round blocks found on the page")
            return []

        for block in containers:
            href = block['href']
            if not href.startswith('/catalog/'):
                continue
            name = block.get_text(strip=True)
            full = urljoin(base, href)
            # ensure same domain
            if urlparse(full).netloc != urlparse(base).netloc:
                continue
            print(f"  -> discovered hockeyworld category: {name} -> {full}")
            out.append({'name': name, 'url': full})

        return out

    def scrape_category(self, client, category):
        # TODO: move selectors/rules to templates loaded from YAML.
        #base = f"https://prohockey.com.ua/catalog/{category}"
        base= f"{category}" if category else "https://prohockey.com.ua/catalog"
        if category:
            found = find_category_page(client, client.session, "https://prohockey.com.ua", category)
            if found and found != base:
                print(f"  -> using discovered reference category page: {found}")
                base = found

        item_selectors = [
            'div[class*="product"][class*="item"]',
            "div.card",
            'div.row > div[class*="col"] > div[class*="product"]',
            "article.product",
            "div[data-product-id]",
            "div.catalog-item",
            "div.product",
            "div.item",
            "div.tz-item",
            "li.product",
            "div.catalog__item",
            ".catalog-card",
            ".product-list-item",
        ]

        name_selectors = [
            "a.product-title",
            "a.catalog-item__title",
            "h3 a",
            "h2 a",
            ".title a",
            ".product-name a",
            "h1",
            "h2",
            "h3",
            "h4",
            "a",
        ]

        price_selectors = [
            ".price .value",
            ".price",
            ".catalog-item__price",
            ".woocommerce-Price-amount",
            ".tov_price",
            ".product-price",
            '[class*="price"]',
        ]

        link_selectors = [
            "a.product-title",
            ".catalog-item__title a",
            "h3 a",
            "a",
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
                    source_site="prohockey.com.ua",
                )
            )
        return results

    def scrape_url(self, client, url, category=None):
        raise NotImplementedError("Reference adapter uses scrape_category")

