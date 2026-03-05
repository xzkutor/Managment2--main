from urllib.parse import urlparse, urljoin

from pricewatch.core.plugin_base import BaseShopAdapter
from pricewatch.core.models import ProductItem
from bs4 import BeautifulSoup


class HockeyShopAdapter(BaseShopAdapter):
    name = "hockeyshop"
    domains = ("hockeyshop.com.ua", "www.hockeyshop.com.ua")

    def scrape_category(self, client, category):
        raise NotImplementedError("HockeyShop adapter does not support scrape_category via this method; use scrape_url with a category URL or implement discovery")

    def get_next_page(self, bsoup):
        if not bsoup:
            return None

        # look for rel=next first
        a = bsoup.find('a', rel='next', href=True)
        if a:
            return a['href']

        # common pagination containers
        container = bsoup.find('div', id='bottom-pagination') or bsoup.find('ul', class_='pagination') or bsoup.find('div', class_='pagination') or bsoup.select_one('.pager')
        if not container:
            return None

        anchors = container.find_all('a', href=True)
        if not anchors:
            return None
        # prefer rel or explicit next-class anchors
        for a in anchors:
            if a.get('rel') and 'next' in (a.get('rel') or []):
                return a['href']
            cls = ' '.join(a.get('class') or [])
            if 'next' in cls or 'pager-next' in cls or 'arrow' in cls:
                return a['href']

        # otherwise look for anchor whose text indicates "next" (avoid numeric page links)
        for a in anchors:
            txt = (a.get_text(strip=True) or a.get('title') or '').strip()
            if not txt:
                continue
            norm = txt.replace('ё', 'е').lower()
            # skip pure numbers
            if norm.isdigit():
                continue
            if any(k in norm for k in ('вперед', 'далее', 'следующая', 'next', '»', '›', '>')):
                # ensure not disabled (parent <li> with class disabled)
                parent_li = a.find_parent('li')
                if parent_li:
                    if 'disabled' in (parent_li.get('class') or []):
                        continue
                href = a['href']
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    return href

        return None

    def scrape_url(self, client, url, category=None):
        """Scrape products from a hockeyshop category page.

        This mirrors the hockeyworld approach but tuned to hockeyshop URL patterns and classes.
        """
        current = url if url.startswith('http') else 'https://' + url
        print(f"HockeyShopAdapter.scrape_url: fetching {current} (category={category})")

        items = []
        visited = set()
        page_count = 0
        max_pages = 30

        while current and page_count < max_pages:
            if current in visited:
                break
            visited.add(current)
            page_count += 1

            resp = client.safe_get(current, session=client.session)
            if not resp:
                break

            soup = BeautifulSoup(resp.content, 'html.parser')
            # Prefer the product grid used on hockeyshop category pages
            product_nodes = soup.select('.product-grid-area ul li')
            # If not present, try the specific long selector or common fallbacks
            if not product_nodes:
                # use the detailed selector provided by the user as a fallback for single-item selection
                product_nodes = soup.select('#shop_grid_page .product-grid-area ul li')
            if not product_nodes:
                product_nodes = soup.find_all('div', class_='product') or soup.find_all('div', class_='catalog-item')
            # fallback: any element with data-product attribute
            if not product_nodes:
                product_nodes = soup.find_all(attrs={'data-product': True}) or []

            # filter out nodes that don't look like product items (avoid pagination/listing cruft)
            filtered = []
            for node in product_nodes:
                if node.select_one('div.item-info div.item-title a') or node.select_one('a.product-link') or node.select_one('a[href*="/p/"]'):
                    filtered.append(node)

            print(f"  -> page {page_count}: found {len(filtered)} product nodes (raw {len(product_nodes)}) on {current}")

            for node in filtered:
                # anchor/title inside the product item (user-provided path)
                a = node.select_one('div.item-info div.item-title a') or node.select_one('a.product-link') or node.find('a', href=True)
                name = a.get_text(' ', strip=True) if a else ''
                link = a['href'] if a and a.has_attr('href') else None

                # price: try multiple likely selectors
                price_node = node.select_one('div.PricesalesPrice') or node.select_one('.PricesalesPrice') or node.select_one('.price') or node.select_one('.product-price') or node.select_one('span.price')
                price = price_node.get_text(' ', strip=True) if price_node else ''

                full_link = urljoin(current, link) if link else current
                domain = urlparse(full_link).netloc

                items.append(ProductItem(name=name, price_raw=price, url=full_link, source_site=domain))

            next_href = self.get_next_page(soup)
            if not next_href:
                break
            next_url = urljoin(current, next_href)
            print(f"  -> pagination: next page found -> {next_url}")
            current = next_url

        # If category provided, filter by keyword as last resort
        if category:
            key = category.lower()
            before = len(items)
            items = [it for it in items if key in (it.name or '').lower() or key in (it.url or '').lower()]
            print(f"  -> filtered {before} -> {len(items)} items using category '{category}'")

        print(f"  -> returning {len(items)} items")
        return items

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

        menu = soup.select_one('div.mega-menu-category')

        for a in menu.find_all('a', href=True):
            href = a['href']
            if not href.startswith('/c/'):
                continue
            name = a.get_text(' ', strip=True) or a.get('title') or ''
            full = urljoin(base, href)
            if urlparse(full).netloc != urlparse(base).netloc:
                continue
            out.append({'name': name, 'url': full})

        # Sort categories by name (case-insensitive) for deterministic output
        out.sort(key=lambda x: (x.get('name') or '').lower())

        return out
