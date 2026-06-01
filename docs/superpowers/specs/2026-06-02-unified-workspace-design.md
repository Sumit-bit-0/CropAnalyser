# Unified Workspace — Design

**Date:** 2026-06-02
**Status:** Approved (design); ready for implementation plan
**Project:** Agri Market Access Analyser (`E:\agri-market-analyser`)

## Goal

Replace the current flat 10-page app (10-link navbar + Home card grid, every page
re-asking for location) with a **single chooser-driven workspace**. The user picks a
**farmer intent**, the right tool opens, and a **shared location/context** set once
drives every tool. A **global Simple/Smart switch** reveals advanced controls on the
tools that have them. Location can be set by **pincode**, **GPS**, or **state/district**,
resolving to a precise point that sharpens the weather and mandi features.

This is the "unify all analysers into one window" idea deferred during the Phase 2
weather brainstorm (logged in the ideas backlog). It is a frontend restructuring plus
a small backend addition (pincode resolution + optional precise coords through
`recommend`). No model or scoring logic changes.

## Why

CropAdvisor and the analyser pages each answer part of one question — *what do I grow,
where/when do I sell, what's happening in the market* — but live as 10 disconnected
pages, each independently collecting state/district/season. A farmer doesn't know where
to start, and re-enters location everywhere. Collapsing the tools into a few intents
behind one shared-context workspace makes the product feel like one coherent decision
tool instead of a menu of utilities, and (per user feedback) lowers the top-level
cognitive load.

## Architecture

A single React workspace shell with a persistent context bar, three intent tabs, and
per-intent sub-tabs. Shared state lives in a React Context that every tool reads. The
existing page components are **reused as tool bodies**, refactored to read location/
season/mode from context instead of owning their own inputs.

```
┌─────────────────────────────────────────────────────────┐
│ 🌾 Agri Market Analyser            [ Simple ◯───● Smart ] │  header + global mode
├─────────────────────────────────────────────────────────┤
│ Location: ⦿ Pincode [851101]  ⦿ State/District  📍 GPS    │  persistent CONTEXT BAR
│   → Begusarai, Bihar · 25.42°N 86.13°E ✓   Season [Kharif]│
│   (▸ Soil details — shown only in Smart mode)             │
├─────────────────────────────────────────────────────────┤
│ [ 🌱 What to grow ] [ 💰 Where & when to sell ] [ 📊 Explore ]│  3 INTENT TABS
├─────────────────────────────────────────────────────────┤
│  Advisor | Soil Match                                     │  SUB-TABS (per intent)
│  ┌─────────────────────────────────────────────────────┐ │
│  │   active tool body (reused page, reads context)       │ │  MAIN PANEL
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Intent taxonomy (all 9 surviving tools; Home is absorbed into the shell)

| Intent tab | Sub-tabs (tools) |
|---|---|
| 🌱 **What should I grow?** | Crop Advisor · Soil Match |
| 💰 **Where & when do I sell?** | Mandi Compare · Profit Planner |
| 📊 **Explore the data** | State Map · Crop Analyser · Revenue Loss · Price Trend · Forecast |

"Sell" holds only the two direct selling decisions; the data views (Price Trend,
Forecast) sit under "Explore" alongside Map/Crop Analyser/Revenue Loss.

### Component 1 — Shared context (`frontend/src/workspace/WorkspaceContext.jsx`)

`WorkspaceProvider` + `useWorkspace()` hook exposing one object:

```js
{
  state, district, area, pincode, lat, lon,   // location (area/lat/lon from resolution)
  season, crop,                                // selection
  mode,                                        // 'simple' | 'smart'
  soil,                                        // {N,P,K,temperature,humidity,ph,rainfall} | null
  // setters: setLocation(partial), setSeason, setCrop, setMode, setSoil
}
```

- Initial location default matches today's Advisor default (Punjab / Ludhiana) until the
  user sets one.
- `setLocation` is partial-merge so pincode resolution, GPS, and manual dropdowns all
  write into the same fields.

### Component 2 — Workspace shell (`frontend/src/workspace/Workspace.jsx` + pieces)

- `Workspace.jsx` — renders header (brand + `ModeToggle`), `ContextBar`, the three
  intent tabs, the active intent's sub-tabs, and the active tool body. Tracks
  `activeIntent` + `activeTool` in local state (not context — it's navigation, not data).
- `ContextBar.jsx` — `LocationPicker` + Season select + (Smart only) collapsible
  `SoilPanel`. Always visible above the intent tabs; switching tabs/sub-tabs never
  resets it.
- `LocationPicker.jsx` — three entry methods converging on
  `{state, district, area, lat, lon, pincode}`:
  1. **Manual pincode** — 6-digit input → `resolvePincode(pin)`.
  2. **GPS** — `navigator.geolocation` → `reverseLocate(lat, lon)` (nearest pincode →
     precise area; reuses/extends existing `/geo/locate`).
  3. **State/District dropdowns** — existing controls, fallback when PIN unknown.
  Shows the resolved "District, State · lat/lon" line with a ✓ when set.
- `ModeToggle.jsx` — Simple/Smart switch writing `mode` to context.
- `SoilPanel.jsx` — the 7 soil/climate fields (moved out of CropAdvisor); writes `soil`.

### Component 3 — Tool refactor (reuse existing pages)

Each existing page under `frontend/src/pages/` becomes a tool body that:
- **drops** its own state/district/season `useState` and GPS button (now in `ContextBar`),
- **reads** location/season/mode/soil from `useWorkspace()`,
- **keeps** only its tool-specific inputs (e.g. Profit Planner's quantity & price,
  Price Trend's date range, Crop Analyser's crop pick if not the shared crop).

CropAdvisor specifically: its inline soil toggle moves to the global Smart mode +
`SoilPanel`; in Smart with soil filled it sends `soil` (Smart Mode), otherwise Simple.

### Component 4 — Global Simple/Smart semantics

`mode` from context; Smart only *reveals* extra controls, never breaks a tool:

| | Simple (default) | Smart |
|---|---|---|
| Context bar | location + season | + collapsible Soil panel |
| Crop Advisor | regional+market+weather | + soil suitability; exposes goal/weight controls |
| Profit Planner | headline profit + break-even | + editable cost/yield assumptions |
| Forecast | default horizon | adjustable horizon / confidence band |
| Mandi, Trend, Map, Crop Analyser, Revenue Loss | farmer-friendly defaults | unchanged (switch is a no-op) |

### Component 5 — Pincode resolution (backend)

Follows the existing bundled-CSV pattern in `analysis/geo.py`
(`india_district_centroids.csv`). **Hybrid, offline-first with API fallback:**

- **Tier 1 — offline dataset.** Bundle India Post pincode data at
  `data/raw/india_pincodes.csv` (columns: `pincode, area, district, state, lat, lon`).
  Loaded lazily into a module cache like `_load_district_centroids()`. ~19k pincodes.
  - Forward: `pincode → {state, district, area, lat, lon}`.
  - Reverse (GPS): nearest-pincode by haversine against the table → precise area.
- **Tier 2 — free API fallback.** Only when a pincode is absent from the offline set:
  call `postalpincode.in` (`GET https://api.postalpincode.in/pincode/{pin}`) for
  state/district/area; if it omits coords, approximate from `get_centroid(state,
  district)`. Stdlib `urllib`, short timeout, graceful failure → "not found".

New module `analysis/pincode.py`:
- `resolve_pincode(pin) -> {state, district, area, lat, lon, source}` (source =
  "offline" | "api"), raises/returns None on total miss.
- `nearest_pincode(lat, lon) -> {...}` for reverse GPS.

New API routes (extend `api/geo.py`):
- `GET /api/geo/pincode/{pin}` → forward resolve.
- `GET /api/geo/locate` (existing) → upgraded to return nearest **pincode-level** area
  + coords when the pincode table is present, else current district-level behavior.

### Component 6 — Precise coords through `recommend`

So the precise pincode point sharpens Phase 2 weather and mandi distance:
- `POST /api/recommend/smart` accepts optional `lat` + `lon`. When present, the weather
  module uses them directly instead of `get_centroid(state, district)`. `weather_fit_scores`
  / `fusion.recommend` gain an optional `coords=(lat,lon)` param threaded to
  `seasonal_climate`; absent → unchanged district-centroid path.
- Mandi compare already takes coordinates; the context now feeds the precise point.

## Data flow

1. User sets location (pincode / GPS / dropdown) → resolver fills
   `{state, district, area, lat, lon}` in context.
2. User picks intent tab → sub-tab → tool renders, reading shared context + mode.
3. Tool calls its existing API, now passing shared location (+ precise `lat/lon` where
   the endpoint supports it, + `soil` when Smart & filled).
4. Switching tools/intents preserves all context.

## Migration / routing

- `App.jsx` collapses to a single route `/` → `<Workspace/>`.
- Old routes (`/advisor`, `/recommend`, `/profit`, `/mandi`, `/map`, `/crops`,
  `/trends`, `/revenue`, `/forecast`) become **redirects into the workspace** with the
  correct intent + sub-tab preselected (via query/state), so existing links and
  bookmarks survive.
- `components/NavBar.jsx` and `pages/Home.jsx` are removed.
- Page components stay under `pages/` (reused), refactored as in Component 3.

## Error handling

| Situation | Behavior |
|---|---|
| Pincode not found (offline + API miss) | Inline "couldn't find that PIN — pick your district" |
| GPS denied / unsupported | Fall back to dropdowns; existing message |
| Pincode API down/timeout | Treated as miss → offline result or "not found"; never blocks |
| Weather / forecast / API down | Tools degrade exactly as today (per-module) |
| No location set yet | Tools show the existing empty/default state |

## Testing

- **Backend (pytest):** pincode resolver — offline hit, API fallback path (mocked HTTP),
  bad/short PIN, `nearest_pincode` reverse; the optional `lat/lon` path through
  `recommend` (weather uses passed coords, absent → centroid). Existing 124 tests stay
  green. Tests must stay network-free (mock the API like the weather client does).
- **Frontend:** no JS test runner (matches current project practice) — verification is
  `npm run build` clean + manual live browser check of the workspace (set pincode →
  switch intents/tools → confirm context persists, Smart reveals soil, Advisor runs).

## Out of scope (deferred)

- Phase 3 NDVI; B-v3 net-profit/ha market score (needs CACP cost data).
- Per-tool deep visual redesign — tools keep their current internals beyond the
  context/mode refactor.
- Introducing a JS test framework.
- i18n / multi-language farmer UI.

## Dependencies & config

- No new Python dependency (stdlib `urllib` for the API fallback).
- **Pincode source data — `all_india_pincode_directory_2025.csv`** (project root, 22 MB,
  165,627 office rows). Columns: `circlename, regionname, divisionname, officename,
  pincode, officetype, delivery, district, statename, latitude, longitude`. Covers
  **19,586 distinct pincodes; 19,561 (99.9%) have valid coordinates** — this single file
  provides pincode → district/state **and** coordinates. (`Pincode_Dataset.csv` and
  `pincodes.csv` also on disk are now redundant — no coords — and are ignored.)
- **Build step (loader):** aggregate the directory to one row per pincode — pincode
  centroid = mean of that pincode's non-`NA` office `latitude`/`longitude`; district/
  state from the pincode's rows; `area` = a representative office/town name — written to
  the canonical bundled file `data/raw/india_pincodes.csv`
  (`pincode, area, district, state, lat, lon`), following the
  `india_district_centroids.csv` pattern. The ~25 pincodes with no usable coords fall
  back to the district centroid.
- Frontend: no new dependency (existing React Router + Tailwind).
