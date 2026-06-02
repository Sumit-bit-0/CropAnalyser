"""Canonical crop catalog for CropAdvisor — the Phase 0 alignment artifact.

The three data sources speak different crop vocabularies:
  - Suitability model : Crop_recommendation.csv `label` (22 crops, lowercase)
  - Regional history  : "Crop Production data.csv" `Crop` (126, title-case)
  - Market prices     : `prices.commodity` (384, verbose names)

A crop is a valid CropAdvisor candidate when it has BOTH regional production
history AND market prices. The soil/climate suitability model only knows 22
crops (the Crop_recommendation.csv labels), so a crop that exists in history +
market but NOT in that model carries `suitability: None` — it is recommended on
regional + market evidence and simply skips the agronomic term (the fusion layer
degrades per-crop). This is what lets staples the soil model never saw — wheat,
sugarcane, potato, mustard — be recommended at all. Modules import
CANONICAL_CROPS so every layer agrees on names; `validate()` checks every alias
still exists in its source (run `python -m analysis.crop_catalog`).

Excluded (present in the soil model but missing a market/production match):
  - kidneybeans : production = "Rajmash Kholar" (Rajma) but no clean market match
  - muskmelon   : market = "Karbuja (Musk Melon)" but no production-history crop
"""

import re
from dataclasses import dataclass


@dataclass
class CropIdentity:
    canonical: str
    display_name: str
    mandi_name: str | None
    prices_name: str | None
    has_mandi: bool
    has_forecast: bool


# canonical -> {suitability label (or None if outside the 22-crop soil model),
#               production Crop aliases, market commodity aliases}
CANONICAL_CROPS: dict[str, dict] = {
    "rice":        {"suitability": "rice",        "production": ["Rice", "Paddy"],
                    "market": ["Rice", "Paddy (Common)", "Paddy (Basmati)",
                               "Paddy (Dhan)(Common)", "Paddy (Dhan)(Basmati)"]},
    "maize":       {"suitability": "maize",       "production": ["Maize"],
                    "market": ["Maize"]},
    "chickpea":    {"suitability": "chickpea",    "production": ["Gram"],
                    "market": ["Bengal Gram (Gram)(Whole)", "Kabuli Chana (Chickpeas-White)"]},
    "pigeonpeas":  {"suitability": "pigeonpeas",  "production": ["Arhar/Tur"],
                    "market": ["Arhar (Tur/Red Gram)(Whole)", "Arhar", "Red Gram"]},
    "mothbeans":   {"suitability": "mothbeans",   "production": ["Moth"],
                    "market": ["Moath Dal", "Mataki"]},
    "mungbean":    {"suitability": "mungbean",    "production": ["Moong(Green Gram)"],
                    "market": ["Green Gram (Moong)(Whole)"]},
    "blackgram":   {"suitability": "blackgram",   "production": ["Blackgram", "Urad"],
                    "market": ["Black Gram (Urd Beans)(Whole)"]},
    "lentil":      {"suitability": "lentil",      "production": ["Lentil", "Masoor"],
                    "market": ["Lentil (Masur)(Whole)"]},
    "cotton":      {"suitability": "cotton",      "production": ["Cotton(lint)", "Kapas"],
                    "market": ["Cotton"]},
    "jute":        {"suitability": "jute",        "production": ["Jute"],
                    "market": ["Jute"]},
    "coffee":      {"suitability": "coffee",      "production": ["Coffee"],
                    "market": ["Coffee"]},
    "coconut":     {"suitability": "coconut",     "production": ["Coconut"],
                    "market": ["Coconut"]},
    "banana":      {"suitability": "banana",      "production": ["Banana"],
                    "market": ["Banana"]},
    "mango":       {"suitability": "mango",       "production": ["Mango"],
                    "market": ["Mango"]},
    "grapes":      {"suitability": "grapes",      "production": ["Grapes"],
                    "market": ["Grapes"]},
    "apple":       {"suitability": "apple",       "production": ["Apple"],
                    "market": ["Apple"]},
    "orange":      {"suitability": "orange",      "production": ["Orange"],
                    "market": ["Orange"]},
    "papaya":      {"suitability": "papaya",      "production": ["Papaya"],
                    "market": ["Papaya"]},
    "pomegranate": {"suitability": "pomegranate", "production": ["Pome Granet"],
                    "market": ["Pomegranate"]},
    "watermelon":  {"suitability": "watermelon",  "production": ["Water Melon"],
                    "market": ["Water Melon"]},

    # --- Expansion: major Indian field crops with production history + market
    # prices but OUTSIDE the 22-crop soil model (suitability=None). Without
    # these, regions like Bihar/Begusarai could never see wheat/sugarcane/maize
    # surface even though they dominate locally.
    "wheat":       {"suitability": None, "production": ["Wheat"],
                    "market": ["Wheat"]},
    "sugarcane":   {"suitability": None, "production": ["Sugarcane"],
                    "market": ["Sugarcane"]},
    "potato":      {"suitability": None, "production": ["Potato"],
                    "market": ["Potato"]},
    "mustard":     {"suitability": None, "production": ["Rapeseed &Mustard"],
                    "market": ["Mustard"]},
    "onion":       {"suitability": None, "production": ["Onion"],
                    "market": ["Onion"]},
    "soyabean":    {"suitability": None, "production": ["Soyabean"],
                    "market": ["Soyabean"]},
    "groundnut":   {"suitability": None, "production": ["Groundnut"],
                    "market": ["Groundnut"]},
    "bajra":       {"suitability": None, "production": ["Bajra"],
                    "market": ["Bajra (Pearl Millet/Cumbu)"]},
    "jowar":       {"suitability": None, "production": ["Jowar"],
                    "market": ["Jowar (Sorghum)"]},
    "ragi":        {"suitability": None, "production": ["Ragi"],
                    "market": ["Ragi (Finger Millet)"]},
    "barley":      {"suitability": None, "production": ["Barley"],
                    "market": ["Barley (Jau)"]},
    "sunflower":   {"suitability": None, "production": ["Sunflower"],
                    "market": ["Sunflower"]},
    "sesamum":     {"suitability": None, "production": ["Sesamum"],
                    "market": ["Sesamum (Sesame,Gingelly,Til)"]},
    "turmeric":    {"suitability": None, "production": ["Turmeric"],
                    "market": ["Turmeric"]},
    "garlic":      {"suitability": None, "production": ["Garlic"],
                    "market": ["Garlic"]},
    "tapioca":     {"suitability": None, "production": ["Tapioca"],
                    "market": ["Tapioca"]},
}

# Candidate crops: those with confirmed production history + market coverage.
# (Some have suitability=None — scored on regional+market only.)
WHITELIST: list[str] = sorted(CANONICAL_CROPS.keys())


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# normalized alias -> canonical crop key, built once from the catalog
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _c, _m in CANONICAL_CROPS.items():
    for _a in [_c] + _m["production"] + _m["market"]:
        _ALIAS_TO_CANONICAL[_norm(_a)] = _c

# normalized commodity -> actual DB string; lazily loaded, monkeypatched in tests
_MANDI_MAP: dict[str, str] | None = None
_PRICES_MAP: dict[str, str] | None = None


def _commodity_maps():
    global _MANDI_MAP, _PRICES_MAP
    if _MANDI_MAP is None or _PRICES_MAP is None:
        from database import query
        _MANDI_MAP = {_norm(x): x for x in query("SELECT DISTINCT commodity FROM mandi_prices")["commodity"]}
        _PRICES_MAP = {_norm(x): x for x in query("SELECT DISTINCT commodity FROM prices")["commodity"]}
    return _MANDI_MAP, _PRICES_MAP


def resolve_crop(name: str) -> CropIdentity:
    """Resolve any crop name (canonical, alias, or raw commodity) to its name in
    each tool vocabulary plus availability flags. has_forecast mirrors prices
    presence (forecasts are built on the prices series)."""
    mandi_map, prices_map = _commodity_maps()
    n = _norm(name)
    canonical = _ALIAS_TO_CANONICAL.get(n, (name or "").lower())
    if canonical in CANONICAL_CROPS:
        m = CANONICAL_CROPS[canonical]
        aliases = [canonical] + m["production"] + m["market"]
        display = canonical
    else:
        aliases = [name]
        display = name
    mandi_name = next((mandi_map[_norm(a)] for a in aliases if _norm(a) in mandi_map), None)
    prices_name = next((prices_map[_norm(a)] for a in aliases if _norm(a) in prices_map), None)
    return CropIdentity(canonical=canonical, display_name=display,
                        mandi_name=mandi_name, prices_name=prices_name,
                        has_mandi=mandi_name is not None,
                        has_forecast=prices_name is not None)


def list_all_crops() -> list[CropIdentity]:
    """Deduped union of every crop in the prices and mandi tables, each resolved
    to its identity + availability flags. Powers the shared crop picker."""
    mandi_map, prices_map = _commodity_maps()
    seen: dict[str, CropIdentity] = {}
    for actual in list(prices_map.values()) + list(mandi_map.values()):
        ident = resolve_crop(actual)
        if ident.canonical not in seen:
            seen[ident.canonical] = ident
    return sorted(seen.values(), key=lambda i: i.display_name.lower())


def validate() -> dict:
    """Assert every alias still exists in its live source. Returns a coverage report."""
    import pandas as pd
    from database import query

    DS = r"E:\DataSETAgri"
    suit = {str(v).strip().lower() for v in
            pd.read_csv(fr"{DS}\Crop_recommendation.csv", usecols=["label"])["label"]}
    prod = {str(v).strip() for v in
            pd.read_csv(fr"{DS}\Crop Production data.csv", usecols=["Crop"])["Crop"]}
    mkt = {str(v).strip() for v in query("SELECT DISTINCT commodity FROM prices")["commodity"]}

    problems = []
    for crop, m in CANONICAL_CROPS.items():
        if m["suitability"] is not None and m["suitability"].lower() not in suit:
            problems.append(f"{crop}: suitability label '{m['suitability']}' not found")
        if not any(p in prod for p in m["production"]):
            problems.append(f"{crop}: no production alias {m['production']} found")
        if not any(x in mkt for x in m["market"]):
            problems.append(f"{crop}: no market alias {m['market']} found")
    return {"whitelist_size": len(WHITELIST), "problems": problems}


if __name__ == "__main__":
    rep = validate()
    print(f"Whitelist ({rep['whitelist_size']} crops): {', '.join(WHITELIST)}")
    if rep["problems"]:
        print("\nPROBLEMS:")
        for p in rep["problems"]:
            print(" -", p)
    else:
        print("\nAll aliases validated against live sources. OK")
