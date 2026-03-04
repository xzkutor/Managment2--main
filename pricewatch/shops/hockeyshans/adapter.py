import re
from urllib.parse import urlparse

from pricewatch.core.plugin_base import BaseShopAdapter
from pricewatch.core.pagination import paginate_and_collect
from pricewatch.core.models import ProductItem


class HockeyShansAdapter(BaseShopAdapter):
    name = "hockeyshans"
    domains = ("hockeyshans.com.ua", "old.hockeyshans.com.ua")

    def scrape_category(self, client, category):
        raise NotImplementedError("HockeyShans adapter does not support scrape_category")

    def scrape_url(self, client, url, category=None):
        # TODO: move selectors/rules to templates loaded from YAML.
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
