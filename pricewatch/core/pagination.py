import logging

from bs4 import BeautifulSoup

from .extract import (
    find_first,
    normalize_link,
    extract_text,
)

logger = logging.getLogger(__name__)


def paginate_and_collect(client, session, base_url, item_selectors, name_selectors, price_selectors, link_selectors):
    """
    Single-page extraction of product-like items.

    This function deliberately does NOT attempt to detect or traverse pagination
    or fetch JSON APIs. It performs exactly one HTTP request to `base_url`,
    finds product-containing blocks using `item_selectors`, and for each block
    extracts `name`, `price` and `url` using the provided selectors.

    Returns a list of dicts: {"name": ..., "price": ..., "url": ...}.
    """
    try:
        resp = client.safe_get(base_url, session=session)
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", base_url, exc)
        return []

    if not resp:
        logger.warning("No response for %s", base_url)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    items = find_first(soup, item_selectors)
    if not items:
        logger.debug("No items found with selectors: %s", item_selectors)
        return []

    results = []
    for item in items:
        # name element
        name_el = None
        for sel in name_selectors:
            el = item.select_one(sel)
            if el and el.get_text(strip=True):
                name_el = el
                break
        if not name_el and item.name == "a" and item.has_attr("title"):
            name_el = item
        if not name_el:
            img = item.select_one("img[alt]")
            if img:
                name_el = img

        # price element
        price_el = None
        for sel in price_selectors:
            el = item.select_one(sel)
            if el and el.get_text(strip=True):
                price_el = el
                break

        # link element
        link_el = None
        for sel in link_selectors:
            el = item.select_one(sel)
            if el and el.has_attr("href"):
                link_el = el
                break

        name = extract_text(name_el) if name_el else ""
        # additional fallbacks for name
        if not name and item.name == "a" and item.has_attr("title"):
            name = item.get("title", "")
        if not name:
            img = item.select_one("img[alt]")
            if img:
                name = img.get("alt", "")

        price = extract_text(price_el) if price_el else ""
        # fallback: search child nodes for anything that looks like a price
        if not price:
            for cand in item.select("*"):
                txt = cand.get_text(strip=True)
                if any(ch.isdigit() for ch in txt) and ("UAH" in txt or "₴" in txt or " грн" in txt or "грн" in txt or "$" in txt):
                    price = txt
                    break

        url = normalize_link(base_url, link_el["href"] if link_el else "")

        results.append({"name": name, "price": price, "url": url})

    return results

