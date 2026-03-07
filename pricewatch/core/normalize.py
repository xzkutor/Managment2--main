import re
from typing import Any, Dict, List, Optional, Tuple
from rapidfuzz import fuzz, process

# ----------------------------
# Helpers: parsing/normalizing
# ----------------------------

BRANDS = {
    "bauer": "BAUER",
    "ccm": "CCM",
    "true": "TRUE",
    "graf": "GRAF",
    "jackson": "JACKSON",
    "edea": "EDEA",
    "tour": "TOUR",
    "warrior": "WARRIOR",
    "mission": "MISSION",
}

LEVEL_RULES = [
    (re.compile(r"\b(sr|senior|взросл|доросл)\b", re.I), "SR"),
    (re.compile(r"\b(int|intermediate|intermidiate|підліт|подрост)\b", re.I), "INT"),
    (re.compile(r"\b(jr|junior|юниор|юніор)\b", re.I), "JR"),
    (re.compile(r"\b(yth|youth|детск|дитяч)\b", re.I), "YTH"),
]

# Hockey-specific critical attributes ─ hard/strong conflict penalties
_FLEX_RX = re.compile(r"\b(flex\s*)?(\d{2,3})\s*flex\b", re.I)
_FLEX_NUM_RX = re.compile(r"\bflex[-\s]?(\d{2,3})\b", re.I)

_HAND_RX = re.compile(
    r"\b(left|right|lh|rh|l\.h\.|r\.h\.|ліво|право|лів|прав)\b", re.I
)
_HAND_NORM = {
    "left": "L", "lh": "L", "l.h.": "L", "ліво": "L", "лів": "L",
    "right": "R", "rh": "R", "r.h.": "R", "право": "R", "прав": "R",
}

# e.g. "P28", "P92", "Backstrom", "Kane" pattern curves
_CURVE_RX = re.compile(r"\b(P\d{1,3}|[A-Z][a-z]{3,}(?:\s[A-Z][a-z]+)?)\b")

# Dress/skate sizes: numeric like 9.5, 10D, 8EE  or string sizes 30", 152cm
_SIZE_RX = re.compile(r"\b(\d{1,3}(?:[.,]\d)?)(?:\s*(?:D|EE|E|W|R|cm|mm|\"|\'))?\b")

PENALTY_FLEX_CONFLICT = 40.0
PENALTY_HAND_CONFLICT = 50.0
PENALTY_LEVEL_CONFLICT = 25.0
PENALTY_CURVE_CONFLICT = 20.0

BONUS_TOKEN_NUMERIC = 10.0
BONUS_TOKEN_ALPHA = 4.0

# Matching thresholds
MIN_CANDIDATE_SCORE = 65.0   # minimum to appear as a candidate at all
HIGH_CONFIDENCE_SCORE = 85.0  # placed in confirmed_matches without user action
MIN_GAP = 6.0                # minimum gap to second candidate to be non-ambiguous


def _extract_flex(title: str) -> Optional[int]:
    m = _FLEX_NUM_RX.search(title) or _FLEX_RX.search(title)
    if m:
        try:
            return int(m.group(m.lastindex))
        except Exception:
            pass
    return None


def _extract_hand(title: str) -> Optional[str]:
    m = _HAND_RX.search(title)
    if not m:
        return None
    raw = m.group(0).lower().rstrip(".")
    return _HAND_NORM.get(raw)

NOISE_RX = re.compile(
    r"\b("
    r"купити|купить|новинка|акція|знижка|хіт|top|sale|"
    r"official|гарантія|подарунок|уцінка|комплект"
    r")\b",
    re.I,
)

MAIN_NORMALIZED = []

def _field(item: Any, key: str, default: Any = None) -> Any:
    if item is None:
        return default
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)

def _get_title(item: Any) -> str:
    return str(_field(item, "name") or _field(item, "title") or "").strip()

def _normalize_title(s: str) -> str:
    s = s.lower()
    s = s.replace("—", " ").replace("-", " ").replace("/", " ").replace("+", " ")
    s = re.sub(r"[^\w\s\.]", " ", s, flags=re.U)
    s = re.sub(r"\s+", " ", s).strip()
    s = NOISE_RX.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _extract_brand(title: str) -> Optional[str]:
    t = title.lower()
    for k, v in BRANDS.items():
        if re.search(rf"\b{k}\b", t):
            return v
    return None

def _extract_level(title: str) -> Optional[str]:
    for rx, lvl in LEVEL_RULES:
        if rx.search(title):
            return lvl
    return None

def _extract_tokens(title: str) -> Tuple[str, ...]:
    t = title.upper()
    tokens = set()

    # TF9, FT8, FT860, M40, X5, XF70...
    for m in re.findall(r"\b[A-Z]{1,3}\d{1,4}[A-Z]?\b", t):
        tokens.add(m)

    # series tokens (helpful even outside skates)
    for series in [
        "JETSPEED", "TACKS", "RIBCOR", "VAPOR", "SUPREME",
        "CATALYST", "HZRDUS", "NEXT", "XF", "MACH", "HYPERLITE", "SHADOW"
    ]:
        if re.search(rf"\b{series}\b", t):
            tokens.add(series)

    # Hyperlite 2 => HYPERLITE2
    m = re.search(r"\b(HYPERLITE|MACH|SHADOW)\s*(\d)\b", t)
    if m:
        tokens.add(f"{m.group(1)}{m.group(2)}")

    # 3X PRO => 3XPRO
    m = re.search(r"\b(\dX)\s*PRO\b", t)
    if m:
        tokens.add(f"{m.group(1)}PRO")

    return tuple(sorted(tokens))

def _parse_price_uah(price_raw: Any) -> Optional[int]:
    if price_raw is None:
        return None
    s = str(price_raw)
    m = re.search(r"(\d[\d\s]*)\s*грн", s, re.I) or re.search(r"(\d[\d\s]*)грн", s, re.I)
    if not m:
        return None
    return int(re.sub(r"\s+", "", m.group(1)))

def _prep(items: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    out = []
    for it in items:
        title = _get_title(it)
        norm = _normalize_title(title)
        # numeric price: prefer explicit ``price`` field (float), fall back to raw string
        price_uah = None
        explicit_price = _field(it, "price")
        if explicit_price is not None:
            try:
                price_uah = int(float(explicit_price))
            except (TypeError, ValueError):
                pass
        if price_uah is None:
            price_uah = _parse_price_uah(_field(it, "price_raw"))
        out.append({
            "_src": source,
            "_raw": it,  # keep original dict
            "_title": title,
            "_norm": norm,
            "_price_uah": price_uah,
            "_url": _field(it, "url"),
            "_brand": _extract_brand(title),
            "_level": _extract_level(title),
            "_tokens": _extract_tokens(title),
            "_flex": _extract_flex(title),
            "_hand": _extract_hand(title),
        })
    return out

def _pair_score(
    a: Dict[str, Any],
    b: Dict[str, Any],
) -> Tuple[float, Dict[str, Any]]:
    """Return (score, details_dict).

    score is a raw float that can exceed 100 due to bonuses; callers cap it.
    details_dict is suitable for tooltip/debug.
    """
    details: Dict[str, Any] = {}

    # Hard brand block: if both brands are known and differ → impossible match
    if a["_brand"] and b["_brand"] and a["_brand"] != b["_brand"]:
        details["brand_conflict"] = f"{a['_brand']} vs {b['_brand']}"
        return -1e9, details

    base = float(fuzz.token_set_ratio(a["_norm"], b["_norm"]))  # 0..100
    details["fuzzy_base"] = round(base, 1)

    # Token bonus
    inter = set(a["_tokens"]).intersection(b["_tokens"])
    token_bonus = 0.0
    if inter:
        strong = [t for t in inter if any(ch.isdigit() for ch in t)]
        token_bonus = BONUS_TOKEN_NUMERIC * len(strong) + BONUS_TOKEN_ALPHA * (len(inter) - len(strong))
    details["token_bonus"] = round(token_bonus, 1)
    details["shared_tokens"] = sorted(inter)

    # Hard penalties
    penalty = 0.0

    # Level/age-class conflict
    if a["_level"] and b["_level"] and a["_level"] != b["_level"]:
        penalty += PENALTY_LEVEL_CONFLICT
        details["level_conflict"] = f"{a['_level']} vs {b['_level']}"

    # Flex conflict (hockey sticks)
    flex_a, flex_b = a.get("_flex"), b.get("_flex")
    if flex_a is not None and flex_b is not None and flex_a != flex_b:
        penalty += PENALTY_FLEX_CONFLICT
        details["flex_conflict"] = f"{flex_a} vs {flex_b}"

    # Handedness conflict
    hand_a, hand_b = a.get("_hand"), b.get("_hand")
    if hand_a is not None and hand_b is not None and hand_a != hand_b:
        penalty += PENALTY_HAND_CONFLICT
        details["hand_conflict"] = f"{hand_a} vs {hand_b}"

    # Weak price modifier: only adjust by up to ±5 points; never blocks
    price_mod = 0.0
    pa, pb = a.get("_price_uah"), b.get("_price_uah")
    if pa and pb and pa > 0 and pb > 0:
        ratio = min(pa, pb) / max(pa, pb)  # 0..1 (1 = identical)
        if ratio >= 0.90:
            price_mod = 3.0   # very close price → small bonus
        elif ratio < 0.50:
            price_mod = -5.0  # >2× divergence → small penalty
        details["price_mod"] = round(price_mod, 1)
        details["price_ratio"] = round(ratio, 2)

    score = base + token_bonus - penalty + price_mod
    details["total_score"] = round(score, 1)
    return score, details

def _color_for_matched(main_price: Optional[int], other_price: Optional[int]) -> str:
    # only compare if both prices are known
    if main_price is None or other_price is None:
        return "none"
    if main_price < other_price:
        return "green"
    if main_price > other_price:
        return "yellow"
    return "none"

# ----------------------------
# Public API
# ----------------------------

def heuristic_match(
    reference_items: List[Dict[str, Any]],
    target_items: List[Dict[str, Any]],
    *,
    top_k: int = 25,
    min_score: float = MIN_CANDIDATE_SCORE,
    min_gap: float = MIN_GAP,
) -> List[Dict[str, Any]]:
    """Match two lists of product dicts using brand/token/fuzzy heuristics.

    Each item dict must have a ``name`` (or ``title``) key.  Optional keys
    ``price_raw`` / ``price``, ``url`` are used for price comparison and URL
    storage.

    Returns a flat list of result dicts, each with:
      - ``status``:        ``"matched"`` | ``"ambiguous"`` | ``"no_match"``
      - ``color``:         ``"green"`` | ``"yellow"`` | ``"none"`` | ``"blue"`` | ``"red"``
      - ``main``:          original reference item dict (or ``None``)
      - ``other``:         original target item dict (or ``None``)
      - ``score``:         best raw score (float, when computed)
      - ``score_percent``: score capped to 0-100 (int), suitable for display
      - ``score_details``: dict with breakdown fields suitable for tooltip/debug
      - ``gap``:           score gap to second-best candidate (float, when computed)
      - ``candidates``:    top-N ambiguous candidates (only when ``status=="ambiguous"``)
                           each candidate has ``score``, ``score_percent``,
                           ``score_details`` and ``item`` fields.

    ``min_score`` defaults to ``MIN_CANDIDATE_SCORE`` (65) and ``min_gap`` to
    ``MIN_GAP`` (6).  Do not change without re-testing matching quality.
    """
    main_prep = _prep(reference_items, "main")
    other_prep = _prep(target_items, "other")

    other_by_brand: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for b in other_prep:
        other_by_brand.setdefault(b["_brand"], []).append(b)
        other_by_brand.setdefault(None, []).append(b)

    other_index_map = {id(obj): idx for idx, obj in enumerate(other_prep)}
    used_other_idx: set = set()
    results: List[Dict[str, Any]] = []

    for a in main_prep:
        pool = other_by_brand.get(a["_brand"], other_by_brand.get(None, []))
        if not pool:
            results.append({
                "status": "no_match", "color": "blue",
                "main": a["_raw"], "other": None,
            })
            continue

        norms = [b["_norm"] for b in pool]
        cands = process.extract(a["_norm"], norms, scorer=fuzz.token_set_ratio, limit=top_k)

        scored: List[Tuple[float, Dict[str, Any], Dict[str, Any]]] = []
        for _, _, idx in cands:
            b = pool[idx]
            sc, det = _pair_score(a, b)
            scored.append((sc, b, det))
        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            results.append({
                "status": "no_match", "color": "blue",
                "main": a["_raw"], "other": None,
            })
            continue

        best_score, best, best_det = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else -1e9
        gap = best_score - second_score

        score_pct = max(0, min(100, int(round(best_score))))

        if best_score < min_score:
            results.append({
                "status": "no_match", "color": "blue",
                "main": a["_raw"], "other": None,
                "score": float(best_score),
                "score_percent": score_pct,
                "score_details": best_det,
                "gap": float(gap),
            })
            continue

        if gap < min_gap:
            # Ambiguous — emit one entry per reference product with candidates list
            candidates_payload = []
            for s, cb, cd in scored[:5]:
                if s < min_score:
                    break
                candidates_payload.append({
                    "score": float(s),
                    "score_percent": max(0, min(100, int(round(s)))),
                    "score_details": cd,
                    "item": cb["_raw"],
                })
            results.append({
                "status": "ambiguous", "color": "blue",
                "main": a["_raw"], "other": None,
                "score": float(best_score),
                "score_percent": score_pct,
                "score_details": best_det,
                "gap": float(gap),
                "candidates": candidates_payload,
            })
            # Also mark best target-side product as referenced (for target-only calc)
            results.append({
                "status": "ambiguous", "color": "red",
                "main": None, "other": best["_raw"],
                "score": float(best_score),
                "score_percent": score_pct,
                "score_details": best_det,
                "gap": float(gap),
            })
            continue

        b_idx = other_index_map.get(id(best))
        if b_idx is not None:
            used_other_idx.add(b_idx)
        results.append({
            "status": "matched",
            "color": _color_for_matched(a["_price_uah"], best["_price_uah"]),
            "main": a["_raw"], "other": best["_raw"],
            "score": float(best_score),
            "score_percent": score_pct,
            "score_details": best_det,
            "gap": float(gap),
        })

    for idx, b in enumerate(other_prep):
        if idx not in used_other_idx:
            results.append({
                "status": "no_match", "color": "red",
                "main": None, "other": b["_raw"],
            })

    return results


def product_exists_on_main(
    main_list_or_title,
    other_list: List[Dict[str, Any]] | None = None,
    *,
    top_k: int = 25,
    min_score: float = 78.0,
    min_gap: float = 6.0,
) -> List[Dict[str, Any]]:
    """
    Dual-purpose helper:
    - If called with a single string argument (title), returns bool indicating whether
      the normalized title exists in MAIN_NORMALIZED. This keeps compatibility with
      legacy convenience callers/tests.
    - If called with two lists (main_list, other_list) behaves as before and returns
      a list of result dicts describing matches/no-matches.
    """
    # Convenience single-title check: product_exists_on_main(title)
    if other_list is None and isinstance(main_list_or_title, str):
        # fuzzy match against MAIN_NORMALIZED entries
        title_norm = normalize_title(main_list_or_title)
        for m in MAIN_NORMALIZED:
            try:
                score = fuzz.token_set_ratio(title_norm, m)
            except Exception:
                score = 0.0
            if score >= min_score:
                return True
        return False

    # Backward-compatible full matcher: delegates to heuristic_match
    return heuristic_match(
        main_list_or_title,
        other_list or [],
        top_k=top_k,
        min_score=min_score,
        min_gap=min_gap,
    )

def parse_price(price_str):
    if not price_str:
        return "", ""
    m = re.search(r"([\d\s,.]+)\s*([^\d\s]+)", price_str)
    if m:
        value = m.group(1).strip()
        curr = m.group(2).strip()
        return value, curr
    return price_str.strip(), ""


def parse_price_value(price_str: str) -> Tuple[Optional[float], str]:
    if not price_str:
        return None, ""
    value_str, currency = parse_price(price_str)
    if not value_str:
        return None, currency or ""

    s = value_str.replace(' ', '').replace('\u00A0', '').replace(',', '.')
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None, currency or ""
    num_s = m.group(0)
    try:
        return float(num_s), currency or ""
    except Exception:
        return None, currency or ""


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

