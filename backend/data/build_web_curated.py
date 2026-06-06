"""Build data/raw/web_curated_units.csv from web-sourced "major industry"
directories (official rated lists / trade-association member directories).

Each source PDF is downloaded by hand into backend/tools/ingest/_staging/web/
(gitignored — raw dumps), parsed here into named facilities, geocoded
(pincode -> district centroid fallback), and written to a single committed CSV
that the `web_curated` ingest adapter loads. Re-runnable; grounded entirely in
the fetched documents (no invented facilities).

Sources wired so far:
  - cotton_ginning: Textiles Committee "List of Star Rated Ginning & Pressing
    Factories" (https://textilescommittee.gov.in/.../rating-lists-newss.pdf).

Add a source: drop its PDF in _staging/web/, write a parse_* function returning
[facility_type, name, state, district, pin, crop], and append it to SOURCES.

Usage: cd backend && venv/Scripts/python.exe -m data.build_web_curated
"""
import re

import pandas as pd

from config import DATA_RAW, ROOT
from analysis.geo import normalize_state, get_centroid, STATE_CENTROIDS

WEB_DIR = ROOT / "backend" / "tools" / "ingest" / "_staging" / "web"
OUT_CSV = DATA_RAW / "web_curated_units.csv"
_STATE_TOKENS = {normalize_state(s) for s in STATE_CENTROIDS}


def _clean_name(raw: str) -> str:
    name = (raw or "").split("\n")[0].strip().rstrip(",.")
    name = re.sub(r"\s+", " ", name)
    return name.title()


def parse_cotton_rated_pdf() -> pd.DataFrame:
    """Textiles-Committee star-rated ginning & pressing factories PDF.

    Layout: state-name section rows, then one row per unit with REGN NO
    (G&P/####), NAME & ADDRESS, DIST/TALUKA, contact, RATING."""
    import pdfplumber
    pdf_path = WEB_DIR / "cotton_rated_2025.pdf"
    cur_state, recs = None, []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            for tbl in pg.extract_tables():
                for row in tbl:
                    c0 = (row[0] or "").strip()
                    if c0 and all((x is None or str(x).strip() == "")
                                  for x in row[1:]):
                        if normalize_state(c0) in _STATE_TOKENS:
                            cur_state = c0.title()
                        continue
                    regn = (row[1] or "").strip() if len(row) > 1 else ""
                    if not regn.startswith("G&P"):
                        continue
                    addr = row[2] or ""
                    pins = re.findall(r"(\d{3})\s?(\d{3})", addr)
                    recs.append({
                        "facility_type": "cotton_ginning",
                        "name": _clean_name(addr),
                        "state": cur_state,
                        "district": (row[3] or "").strip().title()
                        if len(row) > 3 else "",
                        "pin": "".join(pins[-1]) if pins else "",
                        "crop": "cotton",
                    })
    return pd.DataFrame(recs)


SOURCES = [parse_cotton_rated_pdf]


def _geocode(df: pd.DataFrame) -> pd.DataFrame:
    pc = pd.read_csv(DATA_RAW / "india_pincodes.csv", dtype={"pincode": str})
    pinmap = {str(r.pincode).strip(): (r.lat, r.lon)
              for r in pc.itertuples(index=False)}
    lat, lon = [], []
    for r in df.itertuples(index=False):
        ll = pinmap.get(str(r.pin).strip()) or get_centroid(r.state, r.district)
        lat.append(ll[0] if ll else None)
        lon.append(ll[1] if ll else None)
    df = df.copy()
    df["lat"], df["lon"] = lat, lon
    return df.dropna(subset=["lat", "lon"])


def main() -> None:
    frames = [fn() for fn in SOURCES]
    df = pd.concat(frames, ignore_index=True)
    df = df[df["name"].str.len() > 0]
    df = _geocode(df)
    df = df.drop_duplicates(subset=["name", "state"])
    df = df[["facility_type", "name", "state", "district", "lat", "lon", "crop"]]
    df.to_csv(OUT_CSV, index=False)
    print(f"wrote {len(df)} rows -> {OUT_CSV}")
    print(df.groupby(["facility_type", "state"]).size().to_string())


if __name__ == "__main__":
    main()
