"""Audit dataset sufficiency for the yield model (and quick checks on the others).
Run: venv\\Scripts\\python.exe -m tools.data_audit"""
import sys
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from database import query

print("=== district_crop_history: overall ===")
print(query("""SELECT COUNT(*) rows,
   COUNT(*) FILTER (WHERE canonical_crop IS NOT NULL) mapped,
   MIN(crop_year) min_yr, MAX(crop_year) max_yr,
   COUNT(DISTINCT state) states, COUNT(DISTINCT district) districts,
   COUNT(DISTINCT canonical_crop) crops, COUNT(DISTINCT season) seasons
   FROM district_crop_history""").to_string(index=False))

print("\n=== rows per year (mapped only) — is the 2013-2015 holdout big enough? ===")
print(query("""SELECT crop_year, COUNT(*) rows FROM district_crop_history
   WHERE canonical_crop IS NOT NULL GROUP BY crop_year ORDER BY crop_year""").to_string(index=False))

print("\n=== train(<=2012) vs holdout(2013-2015) split sizes ===")
print(query("""SELECT CASE WHEN crop_year<=2012 THEN 'train <=2012' ELSE 'holdout 2013-2015' END seg,
   COUNT(*) rows FROM district_crop_history
   WHERE canonical_crop IS NOT NULL AND crop_year BETWEEN 1997 AND 2015
   GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("\n=== rows per major crop (mapped) ===")
print(query("""SELECT canonical_crop, COUNT(*) rows, COUNT(DISTINCT district) districts,
   COUNT(DISTINCT crop_year) yrs FROM district_crop_history
   WHERE canonical_crop IS NOT NULL GROUP BY canonical_crop ORDER BY rows DESC""").to_string(index=False))

print("\n=== sparsity: years of data per (state,district,crop,season) combo ===")
print(query("""SELECT yrs AS years_in_combo, COUNT(*) AS num_combos FROM (
     SELECT state,district,canonical_crop,season, COUNT(DISTINCT crop_year) yrs
     FROM district_crop_history WHERE canonical_crop IS NOT NULL
     GROUP BY state,district,canonical_crop,season) t
   GROUP BY yrs ORDER BY yrs""").to_string(index=False))

print("\n=== yield sanity: are there absurd outliers per crop? (q/ha = yield*10 for t/ha crops) ===")
print(query("""SELECT canonical_crop,
   ROUND(MIN(crop_yield)::numeric,2) min_y,
   ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY crop_yield)::numeric,2) median_y,
   ROUND(MAX(crop_yield)::numeric,2) max_y
   FROM district_crop_history WHERE canonical_crop IS NOT NULL AND crop_yield>0
   GROUP BY canonical_crop ORDER BY max_y DESC LIMIT 12""").to_string(index=False))
