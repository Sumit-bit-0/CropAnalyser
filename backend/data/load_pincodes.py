"""Aggregate the India Post directory into a per-pincode centroid file.

Source: all_india_pincode_directory_2025.csv (project root, 165,627 office rows;
columns circlename, regionname, divisionname, officename, pincode, officetype,
delivery, district, statename, latitude, longitude). Many office rows have
latitude/longitude == "NA". A pincode has several offices, so we average the
valid office coordinates into a single pincode centroid.

Output: data/raw/india_pincodes.csv (pincode, area, district, state, lat, lon) —
read offline by analysis/pincode.py, mirroring india_district_centroids.csv.

Run from backend/ as a module:
    venv\\Scripts\\python.exe -m data.load_pincodes
    venv\\Scripts\\python.exe -m data.load_pincodes "C:\\path\\to\\directory.csv"
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import config

FIELDNAMES = ["pincode", "area", "district", "state", "lat", "lon"]


def aggregate_pincodes(rows):
    """rows: iterable of dicts (India Post directory). Returns a list of dicts
    with FIELDNAMES, one per pincode, sorted by pincode. Pincodes with no usable
    coordinates are skipped (the resolver falls back to the district centroid)."""
    groups = defaultdict(list)
    for r in rows:
        pin = (r.get("pincode") or "").strip()
        if pin:
            groups[pin].append(r)

    out = []
    for pin, recs in groups.items():
        lats, lons = [], []
        for r in recs:
            la = (r.get("latitude") or "").strip()
            lo = (r.get("longitude") or "").strip()
            if la and lo and la.upper() != "NA" and lo.upper() != "NA":
                try:
                    lats.append(float(la))
                    lons.append(float(lo))
                except ValueError:
                    pass
        if not lats:
            continue
        head = next((r for r in recs
                     if (r.get("officetype") or "").strip().upper() == "HO"), recs[0])
        out.append({
            "pincode": pin,
            "area": (head.get("officename") or "").strip(),
            "district": (recs[0].get("district") or "").strip().title(),
            "state": (recs[0].get("statename") or "").strip().title(),
            "lat": round(sum(lats) / len(lats), 5),
            "lon": round(sum(lons) / len(lons), 5),
        })
    out.sort(key=lambda d: d["pincode"])
    return out


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else config.ROOT / "all_india_pincode_directory_2025.csv"
    with open(src, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    agg = aggregate_pincodes(rows)
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    out_path = config.DATA_RAW / "india_pincodes.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(agg)
    print(f"wrote {len(agg)} pincodes -> {out_path}")


if __name__ == "__main__":
    main()
