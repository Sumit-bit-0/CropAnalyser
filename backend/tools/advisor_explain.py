"""Explain a CropAdvisor recommendation for any state/district — a diagnostic
that dumps each scorer's contribution so you can sanity-check rankings against
local knowledge.

Run from backend/ as a module:
    venv\\Scripts\\python.exe -m tools.advisor_explain "Bihar" "Begusarai"
    venv\\Scripts\\python.exe -m tools.advisor_explain "Punjab" "Ludhiana" --season Rabi
"""
import argparse
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from analysis.regional_fit import regional_fit_scores
from analysis.market_profitability import market_profitability_scores
from analysis.fusion import recommend
from analysis.crop_catalog import WHITELIST
from database import query


def main() -> None:
    ap = argparse.ArgumentParser(description="Explain a CropAdvisor ranking.")
    ap.add_argument("state")
    ap.add_argument("district", nargs="?", default=None)
    ap.add_argument("--season", default=None)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    st, dt = args.state, args.district

    print(f"\n=== Crops actually grown in {dt or st} (all crops, by production) ===")
    where = "LOWER(state)=LOWER(?)" + (" AND LOWER(district)=LOWER(?)" if dt else "")
    params = (st, dt) if dt else (st,)
    raw = query(f"""SELECT crop, canonical_crop, SUM(production) prod,
                           COUNT(DISTINCT crop_year) yrs
                    FROM district_crop_history WHERE {where}
                    GROUP BY crop, canonical_crop
                    ORDER BY prod DESC NULLS LAST LIMIT 12""",
                params)
    print(raw.to_string(index=False) if not raw.empty else "  (no rows)")

    print("\n=== Regional fit (candidate crops) ===")
    for c, v in sorted(regional_fit_scores(st, dt, args.season).items(),
                       key=lambda kv: kv[1]["score"], reverse=True)[:args.top]:
        if v["score"] > 0:
            print(f"  {c:12s} {v['score']:.3f}  level={v['level']} yrs={v['years_grown']}")

    print("\n=== Market (yield-weighted revenue/ha) ===")
    for c, v in sorted(market_profitability_scores(WHITELIST).items(),
                       key=lambda kv: kv[1]["score"], reverse=True)[:args.top]:
        print(f"  {c:12s} {v['score']:.3f}  ₹{v['recent_price']}/q × yield {v['typical_yield']}")

    print(f"\n=== FINAL ranking (Simple Mode) ===")
    r = recommend(st, dt, season=args.season, top_k=args.top)
    print(f"  weights={r['weights_used']}")
    for i, x in enumerate(r["recommendations"], 1):
        b = {k: round(v, 2) for k, v in x["breakdown"].items()}
        print(f"  {i:2d}. {x['crop']:12s} {x['score']:.3f}  {b}")


if __name__ == "__main__":
    main()
