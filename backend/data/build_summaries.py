"""Build the precomputed summary tables that back the per-state aggregation APIs.

Run after ingesting/updating `prices`:
    venv\\Scripts\\python.exe -m data.build_summaries
"""
import time
from analysis.summaries import build_summaries

if __name__ == "__main__":
    print("Building summary tables (scans the prices table)...", flush=True)
    t0 = time.time()
    counts = build_summaries()
    print(f"Done in {time.time() - t0:.1f}s", flush=True)
    for table, n in counts.items():
        print(f"  {table}: {n} rows", flush=True)
