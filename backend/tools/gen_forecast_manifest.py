"""One-off: build saved_models/forecast_manifest.json = {state: [commodities]}
for every (state, commodity) that has a trained .pt locally. Reads the canonical
pairs from the DB (summary_crop_markup) so we never fragile-parse filenames.
Run with DATABASE_URL pointed at any DB that has summary_crop_markup (Neon works).
"""
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

MODELS_DIR = Path(__file__).resolve().parents[2] / "saved_models"


def _safe(state: str, commodity: str) -> str:
    return f"{state}_{commodity}".replace(" ", "_").replace("/", "-")


def main() -> None:
    url = os.environ["DATABASE_URL"]
    eng = create_engine(url, future=True)
    with eng.connect() as c:
        pairs = c.execute(text("SELECT state, commodity FROM summary_crop_markup")).all()
    cat: dict[str, list[str]] = {}
    for state, commodity in pairs:
        if (MODELS_DIR / f"{_safe(state, commodity)}.pt").exists():
            cat.setdefault(state, []).append(commodity)
    cat = {s: sorted(v) for s, v in sorted(cat.items())}
    out = MODELS_DIR / "forecast_manifest.json"
    out.write_text(json.dumps(cat, ensure_ascii=False))
    states = len(cat)
    commodities = sum(len(v) for v in cat.values())
    print(f"states={states} commodities={commodities} bytes={out.stat().st_size}", file=sys.stderr)


if __name__ == "__main__":
    main()
