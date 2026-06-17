# Phase 2 — Grow-for-Industry vs Grow-for-Mandi Channel Engine

- **Date:** 2026-06-17
- **Status:** Approved (design) — pending spec review → implementation plan
- **Scope:** Phase 2 of the recommender effort. Builds directly on Phase 1
  (`2026-06-05-recommender-soil-and-demand-gate-design.md`), which shipped the
  soil auto-derivation, the processing-demand gate, and recency decay. This spec
  adds the **selling-channel comparison** (processor vs mandi) and feeds its
  profitability signal back into the recommender as a bounded boost.
- **Approach:** "A — Lean two-channel engine + recommender boost" (comparison-first,
  then boost). Approaches B (FPO third channel + total-profit everywhere) and C
  (MSP reference line only) were considered and deferred — B is the natural
  follow-on once A is live.

## Problem

Phase 1 can down-rank a processing crop when no facility is nearby, but it never
answers the farmer's actual decision: **for the crop I grow, should I sell to a
nearby processor or at the mandi — and which earns more?** There is also no
notion of an assured (MSP/FRP) price anywhere in the system, and a crop with a
profitable nearby industry channel gets no positive recognition in the ranking
(the gate only penalises; it never rewards).

## Goals

- For a `(crop, location)`, compute an apples-to-apples **net-price comparison**
  between a **processor channel** (assured MSP/FRP price + documented premium,
  minus transport to the nearest facility) and a **mandi channel** (best net
  modal price, reusing the existing mandi comparison).
- Surface the winner, the per-quintal margin, an optional total-₹ advantage for
  the farmer's plot, and a plain-language explanation.
- Feed the comparison back into the recommender: a gated crop near a facility
  that **out-pays the mandi** receives a **bounded** ranking boost, complementing
  Phase 1's down-weight.
- Keep every number honest: the premium is an explicit, labeled estimate; an
  unavailable channel is marked unavailable, never silently ₹0.

## Non-goals (Phase 2)

- No FPO/collective third channel (Approach B; the FPO engine already exists and
  can be added later).
- No per-facility actual procurement prices (no reliable public source — that is
  the data trap we are explicitly avoiding).
- No total-profit modeling beyond the optional `margin_per_q × yield × area`
  estimate reusing the existing yield model.
- No retraining of any model.

## Architecture

### File structure

| File | Responsibility |
|---|---|
| `data/raw/msp_frp.csv` (new, committed) | Curated reference: `crop, year, msp_per_quintal, basis`. MSP for the ~23 CACP crops; FRP for sugarcane. Small, official, version-controlled. |
| `backend/analysis/price_reference.py` (new) | Loads the MSP/FRP table; `assured_price(crop, year=None)` applies the documented premium. |
| `backend/analysis/channel_compare.py` (new) | The engine. `compare_channels(...)` composes `price_reference` + `demand_gate.nearest_facility` + `mandi_compare`. |
| `backend/api/compare.py` (new router) | `GET /compare/channels` → the comparison payload. |
| `backend/analysis/fusion.py` (modify) | After the existing proximity gate, add a bounded uplift when the processor channel wins for a gated crop. |
| `frontend/src/...` (workspace) | Two-column comparison card in the existing Phase C "Warm Editorial" workspace. |

The premium is one documented constant in `price_reference.py` (default **+5%**,
conservative), overridable per-crop via an optional `premium_pct` column in the
CSV. The UI always labels it "estimated."

Transport uses a documented `DEFAULT_RATE_PER_KM` constant in `channel_compare.py`
(an estimated ₹/quintal/km, conservative), overridable via the API `rate_per_km`
query param. It must be **non-zero** — `mandi_compare` defaults it to `0.0`, which
would zero out transport and make the net-price comparison meaningless, so the
engine passes its own default rather than relying on the `mandi_compare` default.

### 1. `price_reference.py`

```
assured_price(crop, year=None) -> {
  "available": bool,
  "msp": float | None,            # ₹/quintal, latest year ≤ requested
  "basis": "MSP" | "FRP",
  "premium_pct": float,           # documented estimate (default 5)
  "processor_price": float | None # msp * (1 + premium_pct/100)
}
```
- Loads `data/raw/msp_frp.csv` once into a module dict (same pattern as
  `pincode._load_pincodes`).
- Crop missing from the table → `available: false` (never fabricates a price).
- `year=None` → most recent year on record for that crop.

### 2. `channel_compare.py`

```
compare_channels(crop, lat, lon, *, area_ha=None, year=None, rate_per_km=DEFAULT) -> {
  "crop", "processor", "mandi", "winner", "margin_per_q",
  "total_advantage", "explanation"
}
```

**Processor channel**
- `facility_type` from `demand_gate.gated_crops()` (crop → facility_type).
- `fac = nearest_facility(facility_type, lat, lon)` → `{name, km}` or `None`.
- `processor_price = assured_price(crop).processor_price`.
- `processor_transport = km * rate_per_km`.
- `processor_net = processor_price - processor_transport`.
- If no facility OR no MSP/FRP → `available: false` with reason; never ₹0.

**Mandi channel**
- `compare_markets(crop, lat, lon, rate_per_km)` (existing) → the `is_best_net` row.
- `mandi_net = best.net_price`; carry `market`, `distance_km`, `modal_price`,
  `transport_per_q`.
- No mandi price data → `available: false`, reason "no mandi price".

**Verdict**
- `winner` = higher `net_price` among **available** channels.
- `margin_per_q = processor_net - mandi_net` (sign indicates direction).
- If `area_ha` given and the yield model resolves an expected yield:
  `total_advantage = { area_ha, yield_q_per_ha, value: margin_per_q * yield * area_ha, estimate: true }`.
  Omitted entirely if yield can't be derived.
- Both channels netted identically (price − transport) for an apples-to-apples
  comparison. An unavailable channel never reads as ₹0 — the other channel wins
  honestly.
- `explanation`: one plain-language line, e.g. *"Processor pays ₹2,546/q (MSP +
  est. 5% premium); after 22 km transport nets ₹2,535/q vs the best mandi's
  ₹2,270/q — about ₹265/q more."*

### 3. Recommender boost — `fusion.py`

The existing gate block (multiply gated-crop score by `proximity_factor`,
re-sort, emit far-from-mill caution) is **unchanged**. Layered on top:

- Only for **gated crops, only when coords are present** (bounded extra queries —
  a handful of crops at most).
- When the facility is reasonably near, call `compare_channels(crop, lat, lon)`.
- If `processor_net > mandi_net`: `score *= 1 + BOOST_CAP * normalized_margin`,
  capped at **+15%** (`BOOST_CAP`), so it nudges ranking without overriding the
  agronomic/regional signal.
- Emit a **positive note** into the existing `why`/highlights:
  *"a {facility} is {km} km away and pays ~₹{margin}/q more than the mandi —
  strong grow-for-industry option."*

Net effect: the gate is now two-sided — **down** when no/distant facility
(Phase 1, unchanged), **up** when a nearby facility out-pays the mandi.

### 4. API — `backend/api/compare.py`

- `GET /compare/channels?crop=<name>&lat=<>&lon=<>&area=<optional ha>&year=<optional>`
- Response shape:

```json
{
  "crop": "wheat",
  "processor": { "available": true, "facility": "X Flour Mill", "distance_km": 22.0,
                 "assured_price": 2425, "premium_pct": 5, "processor_price": 2546,
                 "transport_per_q": 11.0, "net_price": 2535.0, "basis": "MSP" },
  "mandi":     { "available": true, "market": "Patna", "distance_km": 60.0,
                 "modal_price": 2300, "transport_per_q": 30.0, "net_price": 2270.0 },
  "winner": "processor",
  "margin_per_q": 265.0,
  "total_advantage": { "area_ha": 1.0, "yield_q_per_ha": 35, "value": 9275, "estimate": true },
  "explanation": "Processor pays ₹2,546/q (MSP + est. 5% premium); after 22 km transport nets ₹2,535/q vs the best mandi's ₹2,270/q — about ₹265/q more."
}
```
- Registered alongside the existing routers (mandi, recommend, …).

### 5. Frontend — comparison card (Phase C workspace)

- Two side-by-side channel columns (**Processor** | **Mandi**), each showing
  price → −transport → **net**; the winning column highlighted in the clay accent.
- Header line = the `explanation`; the **"+X% est. premium"** always labeled as an
  estimate.
- Unavailable channel renders greyed with its reason ("no flour mill nearby"),
  never a fake ₹0.
- Triggered for the selected crop/location in the workspace; reuses the existing
  `/api` client and Warm-Editorial design tokens — no new design system.

## Data to acquire

- **`data/raw/msp_frp.csv`** — MSP for the ~23 CACP-notified crops (latest 2–3
  years for `year` flexibility) + sugarcane FRP. Sourced from CACP/DA&FW published
  tables (researched-and-verified, same discipline as the crop-name work).
  Small enough to commit. The premium is modeled, not sourced.

## Data flow (a comparison)

```
crop + lat/lon ─┬─ price_reference.assured_price(crop) ── MSP/FRP × (1+premium) ─┐
                │                                                                │
                ├─ demand_gate.nearest_facility(type, lat, lon) ── {name, km} ───┤→ processor_net
                │                                                                │
                └─ mandi_compare.compare_markets(crop, lat, lon) ── best net ────┴→ mandi_net
                                                                                  │
                                          winner / margin_per_q / total_advantage ▼
                                                       + plain-language explanation
```

## Error handling / fallbacks

- No facility of the crop's type → processor `available: false`; mandi still answers.
- No mandi price for the crop → mandi `available: false`; processor still answers.
- Both unavailable → `winner: null`, explanation says no comparison possible
  (HTTP 200, honest empty — not a 500).
- Crop missing from `msp_frp.csv` → processor `available: false`, reason
  "no MSP/FRP on record".
- Missing table/data file → existing 503 pattern, never a silent wrong answer.
- No coords → `/compare/channels` returns 400 (inherently location-based); the
  recommender boost is a no-op (mirrors the gate).

## Testing (TDD, keep the existing suite green)

- `price_reference`: known crop → MSP × (1+premium); unknown crop → unavailable;
  premium default + per-crop CSV override; `year` resolution picks latest ≤ requested.
- `channel_compare` (DB mocked): processor wins when near + assured > mandi;
  mandi wins when far/low premium; one channel unavailable → other wins honestly;
  `total_advantage` present only when yield + area resolve; margin math exact.
- `fusion` boost: a gated crop near a profitable facility ranks **above** the same
  crop priced out of it; boost capped at +15%; no coords → no boost; positive note
  emitted; **Phase 1 down-weight regression unchanged**.
- API: `/compare/channels` happy path + each unavailable branch + missing-coords 400.
- Full existing suite stays green.

## Rollout

1. Source + commit `data/raw/msp_frp.csv`.
2. `price_reference.py` + tests.
3. `channel_compare.py` + tests.
4. `compare.py` API router + tests.
5. `fusion.py` boost wiring + tests (incl. Phase 1 regression).
6. Frontend comparison card.
7. Live smoke (Arc): a mill-district crop (processor wins) vs a no-facility crop
   (mandi wins / processor unavailable).
8. Deferred deploy (separate effort): frontend → Vercel, FastAPI → Render,
   Postgres → Neon, with data migrated up.

## Risks / open questions

- **MSP/FRP coverage** — only CACP-notified crops have an assured price; other
  crops simply have no processor channel (honest `unavailable`), which is correct.
- **Premium is modeled, not measured** — mitigated by labeling it an estimate and
  keeping it a small, documented, overridable constant. A wrong premium shifts the
  margin but the comparison structure and transport math stay sound.
- **Boost perf** — `compare_channels` runs only for gated crops with coords; the
  gated set is tiny, so the extra mandi/facility queries are bounded.
- **Mandi data freshness** — inherited from the existing `mandi_prices` table;
  out of scope here.
