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

# ---------------------------------------------------------------------------
# Domain dictionaries – hockey/sports product classification
# ---------------------------------------------------------------------------

# A) Product type keywords – (pattern, canonical_type)
#    Goalie-modified types are resolved in _extract_product_type.
#    Order matters: more specific patterns must come before generic ones.
PRODUCT_TYPE_KEYWORDS: List[Tuple[str, str]] = [
    # Goalie-specific gear (resolved via GOALIE_KEYWORDS modifier)
    (r"ловушк|пастк|trapper\b|catcher\b|goalie\s+glove|goalie\s+catch", "GOALIE_GLOVE"),
    (r"\bблокер\b|\bblocker\b|\bблін\b", "GOALIE_BLOCKER"),
    (r"goalie\s+stick|воротарськ\s+ключк|воротарськ\s+клюшк|вратарск\s+клюшк", "GOALIE_STICK"),
    (r"goalie\s+skat|воротарськ\s+ковзан|воротарськ\s+конь", "GOALIE_SKATES"),
    (r"goalie\s+helm|воротарськ\s+шолом|вратарск\s+шлем", "GOALIE_HELMET"),
    (r"goalie\s+pad|воротарськ\s+щитк|вратарск\s+щитк|leg\s+pad", "GOALIE_PADS"),
    (r"goalie\s+pant|воротарськ\s+шорт|вратарск\s+шорт", "GOALIE_PANTS"),
    (r"goalie\s+chest|chest\s+protector|воротарськ\s+нагрудн|вратарск\s+нагрудн", "GOALIE_CHEST"),
    # Sticks
    (r"\bклюшк\b|\bключк\b|\bстік\b|\bstick\b|\bперо\b|\bтруба\b|\bкрюк\b", "STICK"),
    # Skates – prefix \bskat catches skates/skating; Cyrillic roots without trailing \b
    (r"\bковзан|\bконьк|\bskat", "SKATES"),
    # Gloves – prefix \bglove catches gloves; Cyrillic roots
    (r"\bкраг|\bрукавич|\bперчатк|\bglove", "GLOVES"),
    # Shin guards
    (r"\bщитк\b|\bнаколінник\b|\bnakolennik\b|\bshin\b|\bshin.guard\b", "SHIN_GUARDS"),
    # Elbow pads
    (r"\bналокітник\b|\bnalocitnik\b|\belbow\b|\belbow.pad\b", "ELBOW_PADS"),
    # Shoulder / chest protector (player)
    (r"\bнагрудник\b(?!.*воротар)|\bshoulder\b|\bshoulder.pad\b", "SHOULDER_PADS"),
    # Helmet (player)
    (r"\bшолом\b|\bшлем\b|\bhelmet\b", "HELMET"),
    # Pants / girdle
    (r"\bшорти\b|\bшорт\b|\bgirdle\b|\bpant\b", "PANTS"),
    # Neck guard
    (r"\bneck.guard\b|\bneckguard\b|\bнашийник\b|\bзахист.шиї\b", "NECK_GUARD"),
    # Jock / jill
    (r"\bjock\b|\bjill\b|\bракушк\b", "JOCK_JILL"),
    # Wrist guard
    (r"\bwrist.guard\b|\bзахист.зап\b", "WRIST_GUARD"),
    # Bag / backpack / cover
    (r"\bбаул\b|\bсумк\b|\bbag\b|\bbackpack\b|\bчохол\b|\bчехол\b", "BAG"),
    # Generic accessory markers (require contextual token – enforced in extractor)
    (r"\blaces\b|\bшнурк\b|\brunner\b|\bholder\b|\bsteel\b|\bvisor\b",    "ACCESSORY"),
    (r"\btape\b|\bвоск\b|\bwax\b|\bbottle\b|\bpuck\b|\banti.fog\b",        "ACCESSORY"),
    (r"\bmouthguard\b|\bзахист.рота\b|\bнасадк\b",                          "ACCESSORY"),
]

# Accessory context tokens – presence required to classify something as BAG/ACCESSORY
_ACCESSORY_CONTEXT_RX = re.compile(
    r"\b(баул|сумк|bag|backpack|чохол|чехол|laces|шнурк|runner|holder|steel|"
    r"visor|tape|wax|bottle|puck|anti.fog|mouthguard|насадк|sharpen)\b",
    re.I,
)

# Core equipment tokens – presence prevents ACCESSORY classification
_CORE_EQUIP_RX = re.compile(
    r"\bstick\b|\bклюшк|\bключк|\bskat|\bковзан|\bконь|\bglove|\bкраг|\bрукавич|\bперчатк|"
    r"\bhelmet\b|\bшолом|\bшлем|\bshin\b|\bщитк|\belbow\b|\bналокітник|"
    r"\bshoulder\b|\bнагрудник|\bpant\b|\bшорт|\bpad\b|\bловушк|\bпастк|"
    r"\bblocker\b|\bблокер\b",
    re.I | re.UNICODE,
)

# B) Sport context keywords
SPORT_CONTEXT_KEYWORDS: List[Tuple[str, str]] = [
    (r"\binline\b|\broller\b|\bроликов\b|\bstreet\s+hockey\b|\bвуличний\s+хокей\b", "INLINE_HOCKEY"),
    (r"\bfloorball\b|\bфлорбол\b", "FLOORBALL"),
    (r"\bhockey\b|\bхокей\b|\bhokej\b", "ICE_HOCKEY"),
]

# C) Goalie keywords
# Cyrillic \b is unreliable in Python re (Unicode word boundaries).
# We use prefix roots without trailing \b for Cyrillic terms; ASCII terms keep \b.
GOALIE_KEYWORDS = re.compile(
    r"воротар|вратар|\bgoalie\b|\bgoalkeeper\b",
    re.I | re.UNICODE,
)

# D) Curve tokens (named + coded)
CURVE_TOKENS = re.compile(
    r"\b(P28|P29|P88|P90\s*TM|P90TM|P92|P30|P31|P40|P46)\b", re.I
)

# E) Skate fit tokens
SKATE_FIT_TOKENS = re.compile(
    r"\b(FIT\s*1|FIT\s*2|FIT\s*3|FIT1|FIT2|FIT3|\bD\b|\bEE\b|wide|regular)\b", re.I
)

# F) Expanded MODEL_SERIES (used in _extract_tokens)
MODEL_SERIES: List[str] = [
    # Bauer skate lines
    "VAPOR", "SUPREME", "NEXUS", "HYPERLITE", "MACH", "SHADOW",
    # CCM skate / stick lines
    "JETSPEED", "TACKS", "RIBCOR", "SUPER TACKS",
    # Stick lines
    "CATALYST", "HZRDUS",
    # Short stick model codes  (handled via regex in _extract_tokens)
    # Inline / roller
    "MISSION", "TOUR",
    # Series suffixes / sub-lines
    "PRODIGY", "ELITE", "VIZION",
    # Warrior
    "GRIPTAC", "POWERFLY",
    # True / Graf / misc
    "GSX",
]

# Compound series that need normalised merged token (pattern -> canonical)
_COMPOUND_SERIES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bSUPER\s+TACKS\b"),  "SUPERTACKS"),
    (re.compile(r"\bFT6\s+PRO\b"),       "FT6PRO"),
    (re.compile(r"\bFT4\s+PRO\b"),       "FT4PRO"),
    (re.compile(r"\bM5\s+PRO\b"),        "M5PRO"),
    (re.compile(r"\bM50\s+PRO\b"),       "M50PRO"),
    (re.compile(r"\bX5\s+PRO\b"),        "X5PRO"),
    (re.compile(r"\bX4\s+PRO\b"),        "X4PRO"),
    (re.compile(r"\b3X\s+PRO\b"),        "3XPRO"),
    (re.compile(r"\b3S\s+PRO\b"),        "3SPRO"),
    (re.compile(r"\bAS-?V\b"),           "ASV"),
    (re.compile(r"\bFLY-?TI\b"),         "FLYTI"),
    (re.compile(r"\bFLY\s*TI\b"),        "FLYTI"),
    (re.compile(r"\b(\dX)\s*PRO\b"),     None),  # handled dynamically below
]

# ---------------------------------------------------------------------------
# Penalty / bonus constants
# ---------------------------------------------------------------------------

PENALTY_FLEX_CONFLICT     = 40.0
PENALTY_HAND_CONFLICT     = 60.0
PENALTY_LEVEL_CONFLICT    = 25.0
PENALTY_CURVE_CONFLICT    = 20.0
PENALTY_SKATE_FIT_CONFLICT = 30.0
PENALTY_SIZE_CONFLICT     = 15.0

BONUS_TOKEN_NUMERIC  = 10.0
BONUS_TOKEN_ALPHA    = 4.0
BONUS_PRODUCT_TYPE   = 5.0
BONUS_SPORT_CONTEXT  = 3.0
BONUS_GOALIE         = 4.0
BONUS_SERIES         = 8.0
BONUS_CURVE          = 6.0
BONUS_HAND           = 5.0
BONUS_FLEX           = 4.0
BONUS_SKATE_FIT      = 6.0

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


# ---------------------------------------------------------------------------
# Domain-aware extractors (hockey/sports)
# ---------------------------------------------------------------------------

def _extract_goalie_flag(title: str) -> bool:
    """Return True when the title contains a goalie marker."""
    return bool(GOALIE_KEYWORDS.search(title))


def _extract_product_type(title: str) -> Optional[str]:
    """Classify the product into a canonical type using PRODUCT_TYPE_KEYWORDS.

    Goalie flag is applied as a modifier: if the title has a goalie marker
    and the matched type is a player type, the goalie variant is returned
    where one exists.

    ACCESSORY is only assigned when:
      - an accessory context token is present (bag/laces/tape/etc.)
      - AND no core equipment token is present (stick/skate/glove/etc.)
    """
    t = title.lower()
    is_goalie = _extract_goalie_flag(title)

    _PLAYER_TO_GOALIE = {
        "STICK":  "GOALIE_STICK",
        "SKATES": "GOALIE_SKATES",
        "GLOVES": "GOALIE_GLOVE",
        "HELMET": "GOALIE_HELMET",
        "PANTS":  "GOALIE_PANTS",
    }

    for pattern, ptype in PRODUCT_TYPE_KEYWORDS:
        if re.search(pattern, t, re.I):
            if ptype in ("BAG", "ACCESSORY"):
                # Require contextual accessory token and no core equipment token
                if not _ACCESSORY_CONTEXT_RX.search(t):
                    continue
                if _CORE_EQUIP_RX.search(t):
                    continue
            if is_goalie and ptype in _PLAYER_TO_GOALIE:
                return _PLAYER_TO_GOALIE[ptype]
            return ptype
    return None


def _extract_sport_context(title: str) -> Optional[str]:
    """Return sport context: ICE_HOCKEY | INLINE_HOCKEY | FLOORBALL | None."""
    t = title.lower()
    for pattern, ctx in SPORT_CONTEXT_KEYWORDS:
        if re.search(pattern, t, re.I):
            return ctx
    return None


def _extract_curve(title: str) -> Optional[str]:
    """Extract hockey curve code (e.g. P28, P92, P90TM).

    Named curves (Backstrom, Kane, etc.) are left for fuzzy matching via tokens.
    """
    m = CURVE_TOKENS.search(title)
    if m:
        # Normalise: remove spaces, uppercase
        return re.sub(r"\s+", "", m.group(0)).upper()
    # Fallback to old generic curve regex (P-number)
    m2 = re.search(r"\b(P\d{1,3}(?:TM)?)\b", title, re.I)
    if m2:
        return m2.group(1).upper()
    return None


def _extract_skate_fit(title: str) -> Optional[str]:
    """Extract Bauer skate fit designation: FIT1 / FIT2 / FIT3 / D / EE / wide / regular."""
    m = SKATE_FIT_TOKENS.search(title)
    if not m:
        return None
    raw = re.sub(r"\s+", "", m.group(0)).upper()
    # Normalise width tokens
    if raw == "WIDE":
        return "EE"
    if raw == "REGULAR":
        return "D"
    return raw


def _extract_numeric_size_tokens(title: str) -> Tuple[str, ...]:
    """Extract numeric size tokens (skate size, stick length, etc.).

    Returns a sorted tuple of normalised size strings found in the title.
    Only sizes in plausible hockey product ranges (3–17 for skates,
    30–160 for stick lengths in cm, 3.5–15 half-sizes) are captured.
    """
    t = title.upper()
    sizes: set = set()

    # Skate / shoe size: e.g. 9, 9.5, 10D, 8EE, 7.5EE
    for m in re.finditer(
        r"\b(\d{1,2}(?:[.,]\d)?)(?:\s*(?:D|EE|E|W|R))?\b", t
    ):
        raw = m.group(1).replace(",", ".")
        try:
            val = float(raw)
        except ValueError:
            continue
        if 2.0 <= val <= 16.0:
            sizes.add(raw)

    # Stick length in cm: 135cm, 152 cm
    for m in re.finditer(r"\b(\d{2,3})\s*CM\b", t):
        sizes.add(f"{m.group(1)}CM")

    return tuple(sorted(sizes))


def _extract_accessory_flag(title: str) -> bool:
    """Return True only when the title is clearly an accessory (not core equipment).

    Requires:
      - at least one accessory context token (bag, laces, tape, etc.)
      - no core equipment token (stick, skate, glove, etc.)
    """
    t = title.lower()
    return bool(_ACCESSORY_CONTEXT_RX.search(t)) and not bool(_CORE_EQUIP_RX.search(t))


def _extract_tokens(title: str) -> Tuple[str, ...]:
    t = title.upper()
    tokens = set()

    # Compound / multi-word series first (must run on upper-cased string)
    for rx, canonical in _COMPOUND_SERIES:
        if canonical is None:
            # dynamic rule: e.g. \b(\dX)\s*PRO\b → NXPROx
            m = rx.search(t)
            if m:
                tokens.add(f"{m.group(1)}PRO")
        elif rx.search(t):
            tokens.add(canonical)

    # Single-word series from MODEL_SERIES (skip multi-word ones already handled)
    for series in MODEL_SERIES:
        s_up = series.upper()
        if " " in s_up:
            continue  # handled by _COMPOUND_SERIES
        if re.search(rf"\b{re.escape(s_up)}\b", t):
            tokens.add(s_up)

    # Alphanumeric model tokens: FT6, M5, X5, AS580, XF70, N37 …
    for m in re.findall(r"\b[A-Z]{1,3}\d{1,4}[A-Z]?\b", t):
        tokens.add(m)

    # Additional short numeric-alpha like 3S, 3X (not caught by above due to leading digit)
    for m in re.findall(r"\b\dX\b|\b\dS\b", t):
        tokens.add(m)

    # Versioned series: HYPERLITE2, MACH2, SHADOW2
    m = re.search(r"\b(HYPERLITE|MACH|SHADOW)\s*(\d)\b", t)
    if m:
        tokens.add(f"{m.group(1)}{m.group(2)}")

    # Curve codes like P28, P92, P90TM
    cm = CURVE_TOKENS.search(t)
    if cm:
        tokens.add(re.sub(r"\s+", "", cm.group(0)).upper())

    # Skate fit tokens
    fm = SKATE_FIT_TOKENS.search(t)
    if fm:
        fit = re.sub(r"\s+", "", fm.group(0)).upper()
        tokens.add(fit)

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
            # Domain-aware fields
            "_product_type":  _extract_product_type(title),
            "_sport_context": _extract_sport_context(title),
            "_goalie":        _extract_goalie_flag(title),
            "_curve":         _extract_curve(title),
            "_skate_fit":     _extract_skate_fit(title),
            "_size_tokens":   _extract_numeric_size_tokens(title),
            "_accessory_flag": _extract_accessory_flag(title),
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

    # ── Hard brand block ──────────────────────────────────────────────────────
    # If both brands are known and differ → impossible match
    if a["_brand"] and b["_brand"] and a["_brand"] != b["_brand"]:
        details["brand_conflict"] = f"{a['_brand']} vs {b['_brand']}"
        return -1e9, details

    # ── Hard domain rejects (checked before fuzzy – in priority order) ────────

    # 1. Sport context conflict (ice vs inline vs floorball)
    sc_a, sc_b = a.get("_sport_context"), b.get("_sport_context")
    if sc_a and sc_b and sc_a != sc_b:
        details["sport_context_conflict"] = f"{sc_a} vs {sc_b}"
        return -1e9, details

    # 2. Goalie conflict (one is clearly goalie, other is not)
    g_a, g_b = a.get("_goalie", False), b.get("_goalie", False)
    if g_a != g_b:
        # Allow through only when both product types are None (ambiguous titles)
        pt_a, pt_b = a.get("_product_type"), b.get("_product_type")
        if pt_a is not None or pt_b is not None:
            details["goalie_conflict"] = f"goalie={g_a} vs goalie={g_b}"
            return -1e9, details

    # 3. Product type conflict (incompatible equipment categories)
    pt_a, pt_b = a.get("_product_type"), b.get("_product_type")
    if pt_a and pt_b and pt_a != pt_b:
        # Define which pairs can still be considered compatible
        _COMPATIBLE_PAIRS = {
            frozenset({"STICK", "GOALIE_STICK"}),       # handled by goalie conflict above
            frozenset({"SKATES", "GOALIE_SKATES"}),
            frozenset({"GLOVES", "GOALIE_GLOVE"}),
            frozenset({"HELMET", "GOALIE_HELMET"}),
            frozenset({"PANTS", "GOALIE_PANTS"}),
        }
        pair = frozenset({pt_a, pt_b})
        if pair not in _COMPATIBLE_PAIRS:
            details["product_type_conflict"] = f"{pt_a} vs {pt_b}"
            return -1e9, details

    # 4. Accessory vs core product conflict
    acc_a, acc_b = a.get("_accessory_flag", False), b.get("_accessory_flag", False)
    if acc_a != acc_b:
        details["accessory_conflict"] = f"accessory={acc_a} vs accessory={acc_b}"
        return -1e9, details

    # ── Fuzzy base ────────────────────────────────────────────────────────────
    base = float(fuzz.token_set_ratio(a["_norm"], b["_norm"]))  # 0..100
    details["fuzzy_base"] = round(base, 1)
    details["product_type"]  = pt_a
    details["sport_context"] = sc_a

    # ── Token bonus ───────────────────────────────────────────────────────────
    inter = set(a["_tokens"]).intersection(b["_tokens"])
    token_bonus = 0.0
    if inter:
        strong = [t for t in inter if any(ch.isdigit() for ch in t)]
        token_bonus = BONUS_TOKEN_NUMERIC * len(strong) + BONUS_TOKEN_ALPHA * (len(inter) - len(strong))
    details["token_bonus"] = round(token_bonus, 1)
    details["shared_tokens"] = sorted(inter)

    # Track shared series tokens for display
    _series_upper = {s.upper() for s in MODEL_SERIES if " " not in s}
    _compound_canonical = {c for _, c in _COMPOUND_SERIES if c}
    shared_series = sorted(inter & (_series_upper | _compound_canonical))
    if shared_series:
        details["shared_series"] = shared_series

    # ── Penalties ─────────────────────────────────────────────────────────────
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

    # Curve conflict
    curve_a, curve_b = a.get("_curve"), b.get("_curve")
    if curve_a and curve_b and curve_a != curve_b:
        penalty += PENALTY_CURVE_CONFLICT
        details["curve_conflict"] = f"{curve_a} vs {curve_b}"

    # Skate fit conflict
    fit_a, fit_b = a.get("_skate_fit"), b.get("_skate_fit")
    if fit_a and fit_b and fit_a != fit_b:
        penalty += PENALTY_SKATE_FIT_CONFLICT
        details["skate_fit_conflict"] = f"{fit_a} vs {fit_b}"

    # Size token conflict (medium penalty – do not hard reject)
    size_a, size_b = set(a.get("_size_tokens") or ()), set(b.get("_size_tokens") or ())
    if size_a and size_b and not size_a.intersection(size_b):
        penalty += PENALTY_SIZE_CONFLICT
        details["size_conflict"] = f"{sorted(size_a)} vs {sorted(size_b)}"

    # ── Domain bonuses ────────────────────────────────────────────────────────
    bonus = 0.0

    # Product type match
    if pt_a and pt_b and pt_a == pt_b:
        bonus += BONUS_PRODUCT_TYPE

    # Sport context match
    if sc_a and sc_b and sc_a == sc_b:
        bonus += BONUS_SPORT_CONTEXT

    # Goalie match (both are goalie)
    if g_a and g_b:
        bonus += BONUS_GOALIE

    # Series match – bonus per shared series token
    if shared_series:
        bonus += BONUS_SERIES * len(shared_series)

    # Curve match
    if curve_a and curve_b and curve_a == curve_b:
        bonus += BONUS_CURVE

    # Hand match
    if hand_a and hand_b and hand_a == hand_b:
        bonus += BONUS_HAND

    # Flex match
    if flex_a is not None and flex_b is not None and flex_a == flex_b:
        bonus += BONUS_FLEX

    # Skate fit match
    if fit_a and fit_b and fit_a == fit_b:
        bonus += BONUS_SKATE_FIT

    details["domain_bonus"] = round(bonus, 1)

    # ── Weak price modifier ───────────────────────────────────────────────────
    # Only adjust by up to ±5 points; never blocks
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

    score = base + token_bonus + bonus - penalty + price_mod
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

