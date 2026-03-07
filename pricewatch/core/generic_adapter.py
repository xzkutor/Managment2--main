from urllib.parse import urlparse, urljoin
import logging

from .plugin_base import BaseShopAdapter
from .pagination import paginate_and_collect
from .category_discovery import find_category_page
from .models import ProductItem
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class GenericAdapter(BaseShopAdapter):
    name = "generic"
    domains = ()

    def scrape_category(self, client, category):
        raise NotImplementedError("Generic adapter does not support scrape_category")

    def scrape_url(self, client, url, category=None):
        base = url if url.startswith("http") else "https://" + url
        if category:
            candidate = find_category_page(client, client.session, base, category)
            if candidate and candidate != base:
                logger.info("discovered category page on target site: %s", candidate)
                base = candidate

        raw = paginate_and_collect(
            client,
            client.session,
            base,
            item_selectors=[],
            name_selectors=[],
            price_selectors=[],
            link_selectors=[],
        )
        logger.info("paginate_and_collect returned %d raw items", len(raw))

        results = []
        for it in raw:
            name = it.get("name", "")
            price = it.get("price", "")
            link = it.get("url", "")
            domain = urlparse(link or base).netloc
            results.append(
                ProductItem(
                    name=name,
                    price_raw=price,
                    url=link,
                    source_site=domain,
                )
            )

        if category:
            key = category.lower()
            before = len(results)
            results = [
                r
                for r in results
                if key in (r.name or "").lower()
                or key in (r.url or "").lower()
            ]
            logger.info("filtered %d -> %d items using category '%s'", before, len(results), category)

        return results

    def get_categories(self, client):
        """Discover category links on a target site.

        Returns a list of dicts: {'name': <link text>, 'url': <absolute url>}.
        The method is heuristic: it fetches the site root and any canonical domain
        root and scans <a> tags for likely category links (href containing
        keywords or having descriptive text). It preserves existing print-style
        output used throughout the project.
        """
        # build candidate roots to fetch
        base_candidates = []
        # If domains are configured, use the first domain as the base host
        host = next(iter(self.domains), None)
        if host:
            base_candidates.append(f"https://{host}")
        # also try the generic 'example' or caller-provided host via client.last_url? keep simple
        # fall back to empty list if nothing found

        seen = {}
        for base in base_candidates:
            try:
                resp = client.safe_get(base, session=client.session)
            except Exception as exc:
                logger.warning("get_categories: failed to fetch %s: %s", base, exc)
                continue
            if not resp:
                continue
            soup = BeautifulSoup(resp.content, "html.parser")
            domain = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(" ", strip=True)
                if not text:
                    continue
                full = urljoin(domain, href)
                # only keep links that stay on the same domain
                if urlparse(full).netloc != urlparse(domain).netloc:
                    continue
                href_l = href.lower()
                text_l = text.lower()
                # heuristics for category links
                if any(k in href_l for k in ("category", "catalog", "catalogue", "catalogue", "products", "shop")) or (
                    len(text_l) > 2 and len(text_l.split()) <= 4
                ):
                    if full not in seen:
                        seen[full] = text
                        logger.debug("discovered category candidate: %s -> %s", text, full)
        # prepare output list
        out = []
        for url, name in seen.items():
            out.append({'name': name, 'url': url})
        # Sort categories by name (case-insensitive) for deterministic output
        out.sort(key=lambda x: (x.get('name') or '').lower())
        return out
