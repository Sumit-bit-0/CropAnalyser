"""MSP/FRP assured-price reference for the processor selling channel.

Loads the curated data/raw/msp_frp.csv once. assured_price() returns the
processor price = MSP/FRP * (1 + premium). The premium is a documented estimate
(processors often pay a little above the floor); it is labeled estimated in the
UI and overridable per-crop via the optional premium_pct column.
"""
import csv
from config import DATA_RAW

PREMIUM_PCT_DEFAULT = 5.0
_CSV = DATA_RAW / "msp_frp.csv"
_TABLE = None  # {crop: [row, ...]} built lazily; tests reset to None to reload


def _rows():
    """All CSV rows as dicts. Split out so tests can monkeypatch the source."""
    with _CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _load():
    global _TABLE
    if _TABLE is None:
        table = {}
        for r in _rows():
            table.setdefault(r["crop"].strip().lower(), []).append(r)
        _TABLE = table
    return _TABLE


def assured_price(crop, year=None):
    rows = _load().get((crop or "").strip().lower())
    if not rows:
        return {"available": False, "msp": None, "basis": None,
                "premium_pct": PREMIUM_PCT_DEFAULT, "processor_price": None}
    candidates = [r for r in rows if year is None or int(r["year"]) <= year]
    if not candidates:
        candidates = rows
    row = max(candidates, key=lambda r: int(r["year"]))
    msp = float(row["msp_per_quintal"])
    raw_prem = (row.get("premium_pct") or "").strip()
    premium = float(raw_prem) if raw_prem else PREMIUM_PCT_DEFAULT
    return {
        "available": True,
        "msp": msp,
        "basis": row["basis"].strip(),
        "premium_pct": premium,
        "processor_price": round(msp * (1 + premium / 100), 2),
    }
