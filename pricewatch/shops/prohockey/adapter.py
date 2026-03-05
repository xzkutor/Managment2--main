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

        # Sort categories by name (case-insensitive) before returning
        out.sort(key=lambda x: (x.get('name') or '').lower())

        return out

    def get_next_page(self, bsoup):
        """Return next-page href from pager.

        Pager is expected to be a <ul class="pagination"> with multiple <li> elements
        containing <a> anchors. We inspect the last <li>: if its <a> text (normalized)
        equals 'вперед' and the <li> does NOT have class 'disabled', return the href
        from that <a>. Otherwise return None.
        """
        if not bsoup:
            return None

        pager = bsoup.find('ul', class_='pagination')
        if not pager:
            return None

        li_items = pager.find_all('li')
        if not li_items:
            return None

        last_li = li_items[-1]
        # If last li has class 'disabled', there's no next page
        li_classes = last_li.get('class') or []
        if 'disabled' in li_classes:
            return None

        a = last_li.find('a', href=True)
        if not a:
            return None

        title = (a.get_text(strip=True) or '').strip()
        # normalize 'ё' -> 'е' and lowercase for robust comparison
        norm = title.replace('ё', 'е').lower()
        if norm == 'вперед':
            return a['href']

        return None


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
                "div.product-item",
        ]

        name_selectors = [
            "h4.card-title",
        ]

        price_selectors = [
            "div.price-line",
        ]

        link_selectors = [
            "a.product-link",
        ]

        # Iterate pages starting from base; use get_next_page to discover next page href
        results = []
        visited = set()
        current = base
        page_count = 0
        max_pages = 20

        while current and page_count < max_pages:
            if current in visited:
                print(f"  -> already visited {current}, stopping pagination")
                break
            visited.add(current)
            page_count += 1

            # extract items from current page (paginate_and_collect performs a single-page extract)
            try:
                raw = paginate_and_collect(
                    client,
                    client.session,
                    current,
                    item_selectors,
                    name_selectors,
                    price_selectors,
                    link_selectors,
                )
            except Exception as exc:
                print(f"  -> failed to extract items from {current}: {exc}")
                break

            for r in raw:
                results.append(
                    ProductItem(
                        name=r.get("name", ""),
                        price_raw=r.get("price", ""),
                        url=r.get("url", ""),
                        source_site="prohockey.com.ua",
                    )
                )

            # fetch page HTML to locate next page via get_next_page
            try:
                resp = client.safe_get(current, session=client.session)
            except Exception as exc:
                print(f"  -> failed to fetch {current} for pagination: {exc}")
                break
            if not resp:
                print(f"  -> no response for pagination from {current}")
                break

            soup = BeautifulSoup(resp.content, "html.parser")
            next_href = self.get_next_page(soup)
            if not next_href:
                break

            # resolve next URL relative to current
            next_url = urljoin(current, next_href)
            current = next_url

        return results

    def scrape_url(self, client, url, category=None):
        raise NotImplementedError("Reference adapter uses scrape_category")
