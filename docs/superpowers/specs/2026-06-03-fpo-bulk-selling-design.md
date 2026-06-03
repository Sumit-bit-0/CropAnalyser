# FPO Collective-Selling Decision Engine — Design (v1)

**Date:** 2026-06-03
**Status:** Approved (brainstorm complete; awaiting spec review → implementation plan)
**Branch:** `feat/fpo-bulk-selling`

## 1. Goal, User, and Benefit Model

### What it is
A **group-level** sell-decision tool for FPO (Farmer Producer Organization) managers. It turns the app from individual crop/price advisory into a collective-selling engine: given a set of member farmers and their harvest quantities, it computes whether **pooling the produce and trucking it together** earns more than each farmer selling alone — and by how much, in rupees.

### Who uses it
An FPO manager (or a lead farmer coordinating a village group) who already knows roughly what their members have to sell and wants a defensible, numbers-backed answer to "should we aggregate, and where do we truck it?"

### The benefit model (the honest core)
The headline number is **`extra_income`**: the extra rupees the group earns by pooling versus selling individually. It is **pure arithmetic on real data** — `mandi_prices` modal prices + real district/state distances + a transport cost the user can see and edit. **No invented premium.**

The original FPO doc drove "extra income" off user sliders (`modal × (negotiation_premium% + individual_discount%) × qty`) and used a pure ₹/km/quintal transport model that gives aggregation *zero* structural benefit. Both are replaced. An optional, **separately-labeled** negotiation-premium slider may be added later as a clearly-marked "what-if" — it is **not** part of the core `extra_income` and is out of scope for v1.

**The two sides of the comparison:**

- **Individual baseline** — each farmer sells where *their own* net is best, carrying their small lot at a per-quintal local rate (shared tempo / commission agent). Summed across all farmers.
- **Aggregated plan** — the pooled total quantity is trucked (fixed hire + per-km) from a central collection point to the single mandi that maximizes pooled net revenue.

```
extra_income = aggregated_rev − Σ individual_rev_i
```

### Why aggregation wins (the mechanism)
Under the individual per-quintal rate, lot size factors out, so each farmer maximizes `(p_m − d·rate)` — distance penalizes them per quintal, so they stay **near**. The FPO, once it pays the truck's fixed hire, faces a marginal per-quintal distance cost of `d · per_km / total_q` — tiny at scale — so it can profitably reach a **farther, higher-priced** mandi. **Aggregation buys cheap reach.** When no farther premium mandi exists, the tool honestly reports little or negative benefit and recommends selling locally.

### Honest scope limit (baked in)
Distance-based optimization only works for the **~27 commodities present in `mandi_prices`** (which carry market-level locations). Any other crop degrades to a state-level average via `price_source.get_market_prices` and the tool **says so** — it does not fabricate distances or a pooling number.

## 2. Architecture & Data Flow

Three new units, each with one job, following existing repo patterns (`api/mandi.py` wraps `price_source`; engine logic stays out of the HTTP layer).

### `backend/analysis/fpo_bulk.py` — the engine (pure, stateless)
- No DB writes, no HTTP, no React. Fully unit-testable by monkeypatching `get_market_prices`.
- **Input:** farmer list `[{lat, lon, state, quantity_q}, ...]`, a `crop`, and a transport config `{truck_capacity_q, fixed_hire_per_truck, per_km_per_truck, per_q_local_rate}`.
- Calls `price_source.get_market_prices(crop, lat, lon, state, rate_per_km=0, top_k=ALL)` to pull candidate markets (`modal_price` + `distance_km`) — `rate_per_km=0` deliberately bypasses the flawed pure-per-q transport model in `mandi_compare`, so the engine applies its **own** truck-amortization math.
  - **`top_k` must be large** (e.g. `200`, effectively all markets). `compare_markets` sorts by distance ascending and truncates to `top_k` when coordinates are supplied, so a small `top_k` would drop the *farther, higher-priced* mandi that aggregation exists to reach. The engine passes a high `top_k` so the candidate set is the full national market list for the crop, not just the nearest few.
- **Output:** a structured plan — per-farmer individual baseline, the pooled aggregated plan, `extra_income`, the chosen mandi, `price_basis` (`"mandi" | "state_fallback" | "none"`), and any `spread_warning`.
- Depends only on `price_source` + `analysis.geo`.

### `backend/api/fpo.py` — thin HTTP adapter
- `POST /api/fpo/bulk-plan` — a Pydantic request model validates the farmer list + crop + optional transport overrides, calls `fpo_bulk.plan_bulk_sale(...)`, returns its dict. No business logic — validation + serialization only.

### `frontend/src/pages/FpoBulkDashboard.jsx` — UI under the "Where & when to sell" workspace tab
- Editable farmer table (add/remove rows: location + quantity), the shared `CropPicker`, transport-config inputs with sane defaults, and a results panel showing individual-vs-pooled + `extra_income`.
- Reads `crop`/coords from `WorkspaceContext`; pre-fills the first row from the active location.
- Honesty banner when `price_basis != "mandi"`; spread warning when present.

### Data flow (one request)
```
FpoBulkDashboard  ──POST farmers[]+crop+truckCfg──▶  /api/fpo/bulk-plan
        │                                                  │
        │                                          fpo_bulk.plan_bulk_sale
        │                                                  │
        │                      ┌───── per farmer ──────────┤
        │                      ▼                           ▼
        │            get_market_prices(rate=0)      pool all quantities,
        │            → modal+distance per mandi      run truck-amortized
        │            → individual best-net/q          best-net for total_q
        │                      └───────────┬──────────────┘
        │                                  ▼
        │                    extra_income = pooled_rev − Σ individual_rev
        ◀────────────── JSON plan + honesty flag ──────────┘
```

**Why this split:** the engine never knows about HTTP or React, so the honesty-critical economic logic is testable in isolation with fabricated price data, and the broken pure-per-q transport model in `mandi_compare` stays quarantined behind `rate_per_km=0`.

## 3. The Algorithm

**Notation:** farmer *i* has quantity `q_i` at `(lat_i, lon_i)`. Candidate mandi *m* has modal price `p_m` and distance `d` from a given origin.

### Individual baseline (per farmer, summed)
```
for farmer i:
    markets_i = get_market_prices(crop, lat_i, lon_i, state_i, rate=0)
    for each market m: net_i_m = q_i·p_m − transport_individual(q_i, d_im)
    individual_rev_i = max_m(net_i_m)
baseline = Σ individual_rev_i

transport_individual(q_i, d) = q_i · d · per_q_local_rate    # no fixed cost
```

### Aggregated plan (pooled)
```
origin   = centroid of farmer locations        # proxy for the FPO collection hub
total_q  = Σ q_i
markets  = get_market_prices(crop, origin.lat, origin.lon, state, rate=0)
for each market m:
    trucks  = ceil(total_q / truck_capacity_q)
    cost_m  = trucks · (fixed_hire_per_truck + d_m · per_km_per_truck)
    net_m   = total_q·p_m − cost_m
aggregated_rev = max_m(net_m)
```

### The headline number
```
extra_income = aggregated_rev − baseline
```

### Stated v1 simplifications (flagged, not hidden)
- **Single pooled origin = farmer centroid.** No multi-stop pickup routing in v1 (that is a vehicle-routing problem). The result panel states "assumes aggregation at a central collection point."
- **State-fallback crops** (outside the ~27 mandi commodities): no distances exist, so truck-amortization cannot run. The engine returns `price_basis: "state_fallback"`, skips optimization, and the UI says distance-optimization isn't available — no fabricated number.

## 4. Edge Cases & Data Limits

| # | Situation | Honest behavior |
|---|-----------|-----------------|
| 1 | `extra_income ≤ 0` (nearest mandi already best, or truck fixed cost > reach gain) | Report plainly: "Pooling doesn't beat selling locally here." Never floored at zero. |
| 2 | State-fallback crop (not in the ~27 mandi commodities) | `price_basis: "state_fallback"`, skip truck optimization, UI banner: only a state average available. No fabricated number. |
| 3 | `source: "none"` (no price at all) | Engine returns no plan + clear message; API responds 200 with `price_basis: "none"`, not a crash. |
| 4 | Single farmer | Truck fixed cost usually makes pooling worse → negative `extra_income` → "No benefit pooling alone." |
| 5 | Farmers spread across huge distances | **Soft warning** (chosen): if max pairwise distance > 200 km, return `spread_warning` but **still compute** the plan; the manager judges feasibility. |
| 6 | Farmer with state but no lat/lon | Require coordinates for every farmer row; the frontend resolves pincode/GPS → coords before submit. Validation rejects rows without coords. |
| 7 | Zero / negative / missing quantity | Pydantic validation rejects with 422. |
| 8 | Many `get_market_prices` calls | Cache candidate markets per distinct rounded `(lat, lon)` within one request — 50 farmers in one village = 1 DB lookup. |

## 5. Testing Strategy

TDD throughout (`venv\Scripts\python.exe -m pytest -p no:asyncio` from `backend/`). The engine is the honesty-critical part and gets exhaustive unit tests; the API and UI are thin.

### `test_fpo_bulk.py` — the engine (monkeypatch `get_market_prices`, fabricate prices + distances)
1. Individual baseline picks the mandi maximizing `(p_m − d·rate)`.
2. **Core win:** pooled load reaches a farther, higher-priced mandi → `extra_income > 0`, and equals `aggregated_rev − Σ individual_rev` exactly (assert the arithmetic).
3. **Honest loss:** nearest mandi already best → `extra_income ≤ 0`, plan says sell locally, no flooring.
4. Single farmer → truck fixed cost makes pooling worse → negative `extra_income`.
5. Truck count: `total_q` > capacity → `ceil` produces multiple trucks, cost scales correctly.
6. State-fallback crop → `price_basis: "state_fallback"`, optimization skipped, no fabricated number.
7. `source: "none"` → no plan, clean message.
8. Spread guard: farmers > 200 km apart → `spread_warning` present, plan still computed.
9. Candidate-market caching: 5 farmers at one rounded coord → `get_market_prices` called once (assert call count).
10. **Truncation guard:** a farther, higher-priced mandi that sits beyond the nearest few markets is still selected for the aggregated plan — the engine's high `top_k` keeps it in the candidate set (fabricate >10 markets with the premium one farthest).

### `test_fpo_api.py` — the HTTP adapter
11. Valid POST → 200 with expected keys (`baseline`, `aggregated_rev`, `extra_income`, `price_basis`, `chosen_mandi`).
12. Missing coords on a row → 422; zero/negative quantity → 422.
13. State-fallback crop → 200 with the banner flag (not an error).

### Frontend (`FpoBulkDashboard.jsx`)
Verified live against the dev server (add/remove rows, submit, results render, honesty banner on a fallback crop), matching how the other workspace pages are checked. No new JS test harness in v1.

## Out of Scope (deferred to later specs)
- Persistence (saving plans, member rosters).
- CSV import of farmer/quantity lists.
- Fair-price / distress-sale signal.
- Optional negotiation-premium "what-if" slider (clearly separated from `extra_income`).
- Multi-stop pickup routing (vehicle-routing optimization).
