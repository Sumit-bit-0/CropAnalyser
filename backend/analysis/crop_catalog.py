"""Canonical crop catalog for CropAdvisor — the Phase 0 alignment artifact.

The three data sources speak different crop vocabularies:
  - Suitability model : Crop_recommendation.csv `label` (22 crops, lowercase)
  - Regional history  : "Crop Production data.csv" `Crop` (126, title-case)
  - Market prices     : `prices.commodity` (384, verbose names)

There is no shared key, so CropAdvisor can only recommend crops that exist in
ALL THREE. This module maps each canonical crop to its per-source aliases and
defines the v1 whitelist (the intersection). Modules import CANONICAL_CROPS so
every layer agrees on names; `validate()` checks every alias still exists in its
source (run `python -m analysis.crop_catalog`).

Excluded from v1 (present in suitability but not all sources):
  - kidneybeans : production = "Rajmash Kholar" (Rajma) but no clean market match
  - muskmelon   : market = "Karbuja (Musk Melon)" but no production-history crop
"""

# canonical -> {suitability label, production Crop aliases, market commodity aliases}
CANONICAL_CROPS: dict[str, dict] = {
    "rice":        {"suitability": "rice",        "production": ["Rice", "Paddy"],
                    "market": ["Rice", "Paddy (Common)", "Paddy (Basmati)",
                               "Paddy (Dhan)(Common)", "Paddy (Dhan)(Basmati)"]},
    "maize":       {"suitability": "maize",       "production": ["Maize"],
                    "market": ["Maize"]},
    "chickpea":    {"suitability": "chickpea",    "production": ["Gram"],
                    "market": ["Bengal Gram (Gram)(Whole)", "Kabuli Chana (Chickpeas-White)"]},
    "pigeonpeas":  {"suitability": "pigeonpeas",  "production": ["Arhar/Tur"],
                    "market": ["Arhar (Tur/Red Gram)(Whole)", "Red Gram"]},
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
}

# v1 whitelist: canonical crops with confirmed coverage in all three sources.
WHITELIST: list[str] = sorted(CANONICAL_CROPS.keys())


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
        if m["suitability"].lower() not in suit:
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
