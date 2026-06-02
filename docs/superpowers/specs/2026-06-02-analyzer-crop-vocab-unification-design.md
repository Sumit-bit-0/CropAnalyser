# Analyzer Crop-Vocabulary Unification — Design

**Date:** 2026-06-02
**Status:** Approved (design); ready for implementation plan
**Project:** Agri Market Access Analyser (`E:\agri-market-analyser`)

## Goal

Make every analyzer speak **one crop vocabulary** and follow the **crop the user is
actually working with** — the one Crop Advisor recommends, or one the user picks from a
custom picker — instead of each tool exposing its own disjoint commodity list. When a
tool has no real data for the selected crop, it falls back gracefully (real mandi data →
state-level price estimate) with an honest badge, never a dead end.

The concrete trigger: Mandi Comparison offered only 5 commodities (Onion, Potato, Rice,
Tomato, Wheat), so a farmer growing **Maize** — or most vegetables — saw "no data" even
though the data exists elsewhere in the app.

## Why

The app currently runs three mismatched crop vocabularies:

| Source | Where | Count |
|---|---|---|
| `mandi_prices` table | Mandi Comparison | **5** commodities |
| `prices` table | Trends, Profit, CropAnalyser, Forecast | **384** commodities |
| `crop_catalog.py` (`CANONICAL_CROPS`) | Crop Advisor | **36** canonical crops (alias-mapped) |

A crop named in one tool may not exist (or be named differently) in another. The advisor
can recommend Maize, but Mandi can't price it; the picker lists differ tool to tool. This
breaks the core promise of the unified workspace — "set your crop once, see everything
about it." The fix is a single crop-identity source plus a price fallback chain, layered
on the workspace's existing shared `context.crop`.

## Decisions (from brainstorm)

1. **Mandi data:** *merge* the agmarknet dataset into the current source (not replace).
   They are complementary — agmarknet has Wheat but not Onion/Potato/Rice/Tomato; the
   current source has those four. Merge → ~27 commodities with real market-level data.
   (User can supply more commodity datasets later.)
2. **Picker behavior:** show the **full union** (~384 crops), nothing hidden. When real
   mandi data is absent, auto-fall-back to a state-level price estimate with a small
   honest badge.
3. **Crop sync:** changing the shared crop (advisor recommendation or custom pick)
   **auto-loads** every tool live — no extra submit click.
4. **Single source of truth:** extend `analysis/crop_catalog.py` as the crop-identity
   resolver; pull the genuinely reusable pieces (resolver + price fallback) into small,
   testable units rather than burying them.

## Architecture

Three layers, smallest-possible new surface:

```
                      ┌─────────────────────────────────────────┐
  data layer          │ load_mandi.py  (merge 2 source schemas)  │
                      │   current 5-cmdty CSV + agmarknet 23 ──►  │
                      │   mandi_prices  (~27 cmdty, dedup)        │
                      └─────────────────────────────────────────┘
                                        │
  identity layer      ┌─────────────────────────────────────────┐
                      │ crop_catalog.resolve_crop(name)          │
                      │   -> {canonical, display, mandi_name,    │
                      │       prices_name, has_mandi, has_forecast}│
                      │ crop_catalog.list_all_crops() -> union    │
                      └─────────────────────────────────────────┘
                                        │
  fallback layer      ┌─────────────────────────────────────────┐
                      │ price_source.get_market_prices(crop,...)  │
                      │   1 mandi_compare -> source="mandi"       │
                      │   2 else state AVG(prices) -> "state_fallback"│
                      │   3 else -> "none"                         │
                      └─────────────────────────────────────────┘
                                        │
  api / frontend      /mandi/commodities -> union+flags           │
                      /mandi/compare     -> {source, markets, state_avg}
                      ContextBar crop picker (union, searchable) -> setCrop -> live reload
```

No model or scoring logic changes. The advisor's recommendation already lands in
`context.crop`; this design widens that vocabulary and makes the price tools resolve it
through one identity + fallback path.

## Components

### 1. Data layer — `data/load_mandi.py`

Grow `mandi_prices` from 5 → ~27 commodities by ingesting **both** sources.

- Add a second `COLMAP` for the agmarknet schema (`Min Price (Rs./Quintal)`,
  `Market Name`, `State`, `Sl no.`, dates like `05 Apr 2025`); normalize both into the
  existing `mandi_prices` columns (`state, district, market, commodity, variety, grade,
  min/max/modal_price, price_date`).
- Load order: current source first, then append agmarknet.
- **Dedupe** on `(state, district, market, commodity, variety)` keeping the most recent
  `price_date` (protects the Wheat overlap and same-market repeats).
- Store the raw commodity name as-is (no name munging in the data layer); friendly↔raw
  mapping lives in the resolver.
- Indexes unchanged. Source CSVs remain untracked/gitignored; only loader code commits.
- This is a re-ingest: running the loader rebuilds `mandi_prices` from both files.

**Constraint to record in the spec:** agmarknet covers **8 states only** (AP, Gujarat,
Kerala, MP, Punjab, Rajasthan, UP, West Bengal) across 1,386 markets. Crops/states
outside that footprint rely on the state-level fallback.

### 2. Identity layer — `analysis/crop_catalog.py`

The single source of truth for "what is this crop called everywhere."

- Extend the 36 canonical entries with explicit `mandi_name` and `prices_name` where they
  differ from the canonical token (e.g. canonical `Pigeonpea/Arhar` →
  mandi `Arhar (Tur/Red Gram)(Whole)`, prices `Arhar`).
- `resolve_crop(name) -> CropIdentity` works for **any** crop in the union: canonical
  crops use catalog aliases; the other ~348 prices-only commodities resolve to themselves
  with `has_mandi=False`. Returns
  `{canonical, display_name, mandi_name, prices_name, has_mandi, has_forecast}`.
- `list_all_crops() -> list[CropIdentity]`: the deduped union (~384), each tagged with
  per-tool availability flags, used to populate the picker.

### 3. Fallback layer — `analysis/price_source.py` (new)

One module owns the price fallback chain so the logic lives in exactly one place.

- `get_market_prices(crop, lat, lon, state, rate_per_km=0.0, top_k=10) -> dict`:
  1. Resolve crop → `mandi_name`. Call `mandi_compare.compare_markets(...)`. If rows →
     `{source: "mandi", markets: [...]}`.
  2. Else query state-level `AVG(modal_price)` from `prices` for `(state, prices_name)` at
     the latest available period → `{source: "state_fallback", state_avg: <price>,
     markets: []}`.
  3. Else → `{source: "none"}`.
- Mandi uses it now; Profit/Trends may adopt it later (out of scope here).
- State-level fallback yields a single honest number (no distance ranking — `prices` has
  no market/district), matching the "label fallback" decision.

### 4. API — `api/mandi.py`

- `GET /mandi/commodities` → returns the **union** from `list_all_crops()` (with
  availability flags), replacing the `SELECT DISTINCT commodity FROM mandi_prices` list.
- `GET /mandi/compare` → routes through `price_source.get_market_prices`; response gains
  `source` (`"mandi" | "state_fallback" | "none"`) and `state_avg` when fallback. State
  derives from the location context (lat/lon resolve to a state, or the dropdown).

### 5. Frontend

- **Shared crop picker:** widen `WorkspaceContext.crop`'s vocabulary from the trends-only
  list to the union from `/mandi/commodities` (fetched once, cached). A searchable select
  lives in the `ContextBar` (shared across tools); per-tool "change crop" stays for local
  override. Advisor recommendation calls `setCrop(canonical)` → shared crop updates →
  tools auto-refresh.
- **Fallback badge:** `MandiCompare.jsx` reads `source`. `"state_fallback"` → show the
  state-average price with a small badge: *"State-level estimate — no live mandi data for
  this crop in your area."* `"none"` → friendly empty state. `"mandi"` → ranked-markets
  table as today.
- **Other tools** (Profit/Trends/CropAnalyser/Forecast) keep consuming the shared
  `context.crop` they already read — changing crop drives them live; no mandi fallback
  needed there, no regression.

## Data Flow

1. User sets location (pincode/GPS/dropdown) → context holds `{state, district, lat, lon}`.
2. Crop Advisor recommends a crop, or user picks one in the ContextBar union picker →
   `setCrop(crop)`.
3. Active tool re-queries. For Mandi: `GET /mandi/compare?commodity=<crop>&lat&lon` →
   `price_source` resolves identity → tries mandi → falls back to state average.
4. UI renders ranked markets, or the state-estimate card with the fallback badge.

## Error Handling

- Unknown/empty crop → `resolve_crop` returns a self-identity with all flags false;
  `get_market_prices` returns `{source: "none"}`; UI shows the empty state.
- Missing state in context (location not yet set) → fallback can't run; return
  `{source: "none"}` and prompt the user to set location (existing ContextBar affordance).
- Loader: malformed source rows are dropped during cleaning (existing `clean_mandi`
  pattern, extended for the agmarknet schema).

## Testing

**Backend (pytest, `-p no:asyncio`, Docker Postgres up):**
- `resolve_crop`: canonical crop, prices-only commodity, unknown name.
- `list_all_crops`: union size, dedupe, availability flags correct.
- `get_market_prices`: all three branches (mandi hit / state fallback / none).
- `load_mandi`: both source schemas normalize to identical columns; dedupe keeps the
  latest `price_date`.

**Frontend:** no JS test runner — `npm run build` clean + browser smoke: pick Maize →
real mandi data; pick a no-mandi vegetable → state-fallback badge; advisor recommendation
flows into the picker and reloads tools.

## Out of Scope

- Routing Profit/Trends/Forecast through `price_source` (Mandi only for now).
- Net-profit/ha, NDVI, and other backlog items.
- Importing additional commodity datasets beyond agmarknet (user will supply if needed).

## Open Implementation Notes

- Confirm agmarknet date parsing (`%d %b %Y`) and the exact verbose commodity strings to
  encode in the catalog `mandi_name` aliases (read distinct values at implementation
  time).
- Decide the "latest period" rule for the state-level average (most recent year/month
  present for that state+commodity).
