import json
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from .extract import (
    extract_products_from_json,
    scan_for_json_in_html,
    find_first,
    normalize_link,
    extract_text,
)


PAGE_LIMIT = 16


def paginate_and_collect(client, session, base_url, item_selectors, name_selectors, price_selectors, link_selectors, page_limit=PAGE_LIMIT):
    """
    Attempts to paginate using a pattern. It will try to detect a working pagination scheme.
    """
    parsed = urlparse(base_url)
    base_without_query = base_url.split("?")[0]

    def pattern_replace(n):
        if "page=" in base_url:
            import re
            return re.sub(r"(page=)\d+", r"\1{}".format(n), base_url)
        return None

    def pattern_query(n):
        sep = "&" if parsed.query else "?"
        return f"{base_without_query}{sep}page={n}"

    def pattern_path(n):
        return f"{base_without_query.rstrip('/')}/page/{n}/"

    patterns = [pattern_replace, pattern_query, pattern_path]

    def check_for_json(resp, url_for_base):
        ctype = resp.headers.get("Content-Type", "")
        if "application/json" in ctype or resp.text.strip().startswith(("{", "[")):
            try:
                data = resp.json()
            except Exception:
                try:
                    data = json.loads(resp.text)
                except Exception:
                    return []
            products = extract_products_from_json(data, url_for_base)
            if products:
                print(f"Extracted {len(products)} items from JSON at {url_for_base}")
                return products
        return []

    def find_and_try_api(soup):
        import re
        urls = set()
        for script in soup.find_all("script"):
            txt = script.string or script.get_text()
            if not txt:
                continue
            for match in re.findall(r"fetch\(['\"]([^'\"]+)['\"]", txt):
                urls.add(match)
            for match in re.findall(r"axios\.get\(['\"]([^'\"]+)['\"]", txt):
                urls.add(match)
            for match in re.findall(r"\$\.getJSON\(['\"]([^'\"]+)['\"]", txt):
                urls.add(match)
        for u in urls:
            full = urljoin(base_url, u)
            resp = client.safe_get(full, session=session)
            if resp:
                extracted = check_for_json(resp, full)
                if extracted:
                    return extracted
        return []

    chosen = None
    for pat in patterns:
        url1 = pat(1)
        if not url1:
            continue
        resp = client.safe_get(url1, session=session)
        if not resp:
            continue
        products = check_for_json(resp, url1)
        if products:
            return products

        soup = BeautifulSoup(resp.content, "html.parser")
        items = find_first(soup, item_selectors)
        if items:
            chosen = pat
            print(f"Found {len(items)} items with selectors at {url1}")
            break

    if chosen is None:
        print(f"Trying base URL without pagination: {base_url}")
        resp = client.safe_get(base_url, session=session)
        if not resp:
            print(f"Failed to get response from {base_url}")
            return []
        json_products = check_for_json(resp, base_url)
        if json_products:
            return json_products

        soup = BeautifulSoup(resp.content, "html.parser")
        items = find_first(soup, item_selectors)
        if items:
            chosen = lambda n: base_url if n == 1 else None
            print(f"Found {len(items)} items at base URL")
        else:
            print(f"No items found with selectors: {item_selectors}")
            preview = soup.prettify()[:2000].encode("ascii", errors="replace").decode("ascii")
            print(f"HTML preview: {preview}")

            inline = scan_for_json_in_html(soup, base_url)
            if inline:
                return inline

            api_results = find_and_try_api(soup)
            if api_results:
                return api_results

            print("Attempting fallback heuristic to locate product-like blocks...")
            candidates = []
            import re
            product_class_keywords = re.compile(r"product|prod|card|catalog|tov(ar)?|goods|item|listing", re.I)
            price_pattern = re.compile(r"(\d+[\s\u00A0]?\d{0,3}[,.]?\d{0,2})\s*(₴|UAH|грн|грн\.|uah|\$)", re.I)

            for a in soup.select("a[href]"):
                href = a.get("href", "").strip()
                if not href or href.startswith("#") or href.startswith("tel:") or href.startswith("mailto:"):
                    continue

                if href in ("/", "") or href.lower().startswith("javascript:"):
                    continue

                parent = a
                found = False
                for _ in range(4):
                    classes = parent.get("class") or []
                    cls_str = " ".join(classes) if isinstance(classes, (list, tuple)) else str(classes)
                    text = parent.get_text(separator=" ", strip=True)

                    has_price = bool(price_pattern.search(text))
                    has_img = bool(parent.select_one("img"))
                    has_product_class = bool(product_class_keywords.search(cls_str))

                    is_product_href = bool(re.search(r"/(product|products|item|tov(ar)?|goods|p/|sku|sku-|product-)|-[0-9]{2,}$", href, re.I))

                    positive_signals = 0
                    if has_img or has_price:
                        positive_signals += 1
                    if has_product_class or is_product_href:
                        positive_signals += 1

                    if positive_signals >= 2:
                        candidates.append(parent)
                        found = True
                        break

                    if parent.parent is None:
                        break
                    parent = parent.parent

                if found:
                    continue

            seen = set()
            items = []
            for c in candidates:
                classes = c.get("class")
                if isinstance(classes, list):
                    classes = tuple(classes)
                key = (c.name, classes, c.get_text()[:200])
                if key in seen:
                    continue
                seen.add(key)
                items.append(c)

            if items:
                print(f"Fallback found {len(items)} candidate items")
                results = []
                for item in items:
                    name_el = None
                    for sel in name_selectors:
                        el = item.select_one(sel)
                        if el and el.get_text(strip=True):
                            name_el = el
                            break

                    price_el = None
                    for sel in price_selectors:
                        el = item.select_one(sel)
                        if el and el.get_text(strip=True):
                            price_el = el
                            break

                    link_el = None
                    for sel in link_selectors:
                        el = item.select_one(sel)
                        if el and el.has_attr("href"):
                            link_el = el
                            break

                    name = extract_text(name_el) if name_el else ""
                    if not name and item.name == "a" and item.has_attr("title"):
                        name = item["title"]
                    if not name:
                        img = item.select_one("img[alt]")
                        if img:
                            name = img.get("alt", "")

                    price = extract_text(price_el) if price_el else ""
                    url = normalize_link(base_url, link_el["href"] if link_el else "")

                    if not price:
                        price_text_candidates = item.select("*")
                        for cand in price_text_candidates:
                            txt = cand.get_text(strip=True)
                            if any(ch.isdigit() for ch in txt) and ("UAH" in txt or "₴" in txt or " грн" in txt or "грн" in txt or "$" in txt):
                                price = txt
                                break

                    results.append({"name": name, "price": price, "url": url})

                return results
            else:
                print("Fallback failed — no candidate product blocks found")
                return []

    results = []
    page = 1
    empty_page_count = 0
    limit = page_limit
    if client.fast_mode and limit is None:
        limit = 5
    while True:
        if limit and page > limit:
            print(f"page limit {limit} reached, stopping pagination")
            break
        target_url = chosen(page)
        if not target_url:
            break

        print(f"Fetching: {target_url}")
        resp = client.safe_get(target_url, session=session)
        if not resp:
            break

        soup = BeautifulSoup(resp.content, "html.parser")
        items = find_first(soup, item_selectors)
        if not items:
            print(f"No items found on page {page} (url: {target_url}), stopping pagination.")
            break

        page_had_valid_items = False
        for item in items:
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

            link_el = None
            for sel in link_selectors:
                el = item.select_one(sel)
                if el and el.has_attr("href"):
                    link_el = el
                    break

            if (name_el and name_el.get_text(strip=True)) or (link_el and link_el.get("href")):
                page_had_valid_items = True
                break

        if not page_had_valid_items:
            empty_page_count += 1
            print(f"page {page} has no valid items ({empty_page_count}/3 empty)")
            if empty_page_count >= 3:
                print("stopping pagination after 3 consecutive empty pages")
                break
            page += 1
            continue
        else:
            empty_page_count = 0

        for item in items:
            name_el = None
            for sel in name_selectors:
                el = item.select_one(sel)
                if el and el.get_text(strip=True):
                    name_el = el
                    break

            price_el = None
            for sel in price_selectors:
                el = item.select_one(sel)
                if el and el.get_text(strip=True):
                    price_el = el
                    break

            link_el = None
            for sel in link_selectors:
                el = item.select_one(sel)
                if el and el.has_attr("href"):
                    link_el = el
                    break

            name = extract_text(name_el) if name_el else ""
            price = extract_text(price_el) if price_el else ""
            url = normalize_link(target_url, link_el["href"] if link_el else "")

            if not price:
                price_text_candidates = item.select("*")
                for cand in price_text_candidates:
                    txt = cand.get_text(strip=True)
                    if any(ch.isdigit() for ch in txt) and ("UAH" in txt or "₴" in txt or " грн" in txt or "грн" in txt or "$" in txt):
                        price = txt
                        break

            results.append({"name": name, "price": price, "url": url})

        page += 1

    return results

