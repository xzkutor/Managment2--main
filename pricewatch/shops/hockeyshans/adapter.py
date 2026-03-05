import re
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from pricewatch.core.plugin_base import BaseShopAdapter
from pricewatch.core.pagination import paginate_and_collect
from pricewatch.core.models import ProductItem
from pricewatch.core.category_discovery import find_category_page


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

        # selectors tuned for hockeyshans-style markup
        item_selectors = [
            "div.thumbnail",
            "ul.products li",
            "div.product-item",
        ]

        name_selectors = [
            "div.caption h4",
            "h4 a",
            "a.product-link",
            "img[alt]",
        ]

        price_selectors = [
            ".price",
            ".product-price",
            ".PricesalesPrice",
        ]

        link_selectors = [
            'a[href^="/item/"]',
            "a.product-link",
            "a[href*='/p/']",
            "a",
        ]

        results = []
        visited = set()
        current = base
        page_count = 0
        max_pages = 20

        while current and page_count < max_pages:
            if current in visited:
                break
            visited.add(current)
            page_count += 1

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
                        source_site="hockeyshans.com.ua",
                    )
                )

            # check paginator on the page HTML
            try:
                resp = client.safe_get(current, session=client.session)
            except Exception as exc:
                print(f"  -> failed to fetch {current} for pagination: {exc}")
                break
            if not resp:
                break
            soup = BeautifulSoup(resp.content, "html.parser")
            # look for paginator containers
            pager = soup.find('ul', class_='pagination') or soup.find('div', class_='pagination') or soup.select_one('.pager')
            if pager:
                # try to find next page link
                li_items = pager.find_all('li') if pager.name == 'ul' else pager.find_all('a')
                next_href = None
                # if ul/li structure, inspect last li
                if li_items and pager.name == 'ul':
                    last_li = li_items[-1]
                    if 'disabled' not in (last_li.get('class') or []):
                        a = last_li.find('a', href=True)
                        if a:
                            next_href = a['href']
                else:
                    # look for anchor text indicating next
                    for a in pager.find_all('a', href=True):
                        txt = (a.get_text(strip=True) or '').lower()
                        if any(k in txt for k in ('next', 'вперед', 'далее', '›', '>')):
                            next_href = a['href']
                            break

                if not next_href:
                    break

                next_url = urljoin(current, next_href)
                if not next_url or next_url in visited:
                    break
                print(f"  -> pagination: next page -> {next_url}")
                current = next_url
                continue

            # no paginator found -> stop after single page
            print(f"  -> warning: no paginator found on {current}; stopping after single page")
            break

        return results

    def get_categories(self, client):
        host = next(iter(self.domains), None)
        if not host:
            return []
        base = f"https://{host}"

        try:
            resp = client.safe_get(base, session=client.session)
        except Exception as exc:
            print(f"get_categories: failed to fetch {base}: {exc}")
            return []

        if not resp:
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        out = []
        seen = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/category/' not in href:
                continue
            full = urljoin(base, href)
            if urlparse(full).netloc != urlparse(base).netloc:
                continue
            if full in seen:
                continue
            seen.add(full)
            name = a.get_text(' ', strip=True) or a.get('title') or ''
            out.append({'name': name, 'url': full})
        # Sort categories by name (case-insensitive) for deterministic output
        out.sort(key=lambda x: (x.get('name') or '').lower())
        return out
