"""Train LSTM price-forecast models for India's major farming states x all their crops.

Resource-safe + RESUMABLE: skips any series whose model already exists, so an
interrupted run (thermal/crash/power) can simply be re-run to continue.

Run (unbuffered so progress streams live):
    venv\\Scripts\\python.exe -u -m models.train_major
"""
import sys
import time

# Windows console/pipe defaults to cp1252, which can't encode Unicode commodity
# names (e.g. Devanagari "हरी मटर"). Force UTF-8 so progress prints never crash.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

from database import query
from config import MODELS_DIR
from models.trainer import train

MIN_RECORDS = 23  # LSTM needs seq(12)+forecast(6)+5

MAJOR_STATES = [
    "Uttar Pradesh", "Madhya Pradesh", "Punjab", "Maharashtra", "Rajasthan",
    "Karnataka", "Gujarat", "Andhra Pradesh", "West Bengal", "Haryana",
    "Telangana", "Tamil Nadu", "Bihar", "Odisha", "Kerala",
]


def _safe_name(state: str, commodity: str) -> str:
    return f"{state}_{commodity}".replace(" ", "_").replace("/", "-")


def _already_trained(state: str, commodity: str) -> bool:
    s = _safe_name(state, commodity)
    return (MODELS_DIR / f"{s}.pt").exists() and (MODELS_DIR / f"{s}_scaler.joblib").exists()


def build_worklist() -> list[tuple[str, str]]:
    df = query("select state, commodity, count(*) n from prices group by state, commodity")
    df = df[df["n"] >= MIN_RECORDS]
    work = []
    for state in MAJOR_STATES:
        comms = sorted(df[df["state"] == state]["commodity"].tolist())
        for c in comms:
            work.append((state, c))
    return work


if __name__ == "__main__":
    work = build_worklist()
    total = len(work)
    print(f"Worklist: {total} series across {len(MAJOR_STATES)} major states", flush=True)

    trained = skipped = failed = 0
    fails: list[str] = []
    t0 = time.time()

    for i, (state, commodity) in enumerate(work, 1):
        tag = f"[{i}/{total}] {state} / {commodity}"
        if _already_trained(state, commodity):
            skipped += 1
            print(f"{tag} -- skip (exists)", flush=True)
            continue
        try:
            print(f"{tag} -- training...", flush=True)
            train(state, commodity, epochs=400)
            trained += 1
        except Exception as e:  # noqa: BLE001 - one bad series must not kill the sweep
            failed += 1
            fails.append(f"{state}/{commodity}: {type(e).__name__}: {e}")
            print(f"{tag} -- FAILED: {type(e).__name__}: {e}", flush=True)

        if i % 25 == 0:
            el = time.time() - t0
            rate = i / el if el else 0
            eta = (total - i) / rate / 60 if rate else 0
            print(f"  ...progress {i}/{total} | trained {trained} skip {skipped} fail {failed} "
                  f"| {el/60:.1f} min elapsed, ~{eta:.0f} min left", flush=True)

    print("\n=== DONE ===", flush=True)
    print(f"trained={trained}  skipped={skipped}  failed={failed}  total={total}", flush=True)
    print(f"elapsed: {(time.time()-t0)/60:.1f} min", flush=True)
    if fails:
        print("\nFailures:", flush=True)
        for f in fails:
            print(" -", f, flush=True)
