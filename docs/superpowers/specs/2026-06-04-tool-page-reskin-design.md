# Tool-Page Re-skin (Phase B2) — Design

**Date:** 2026-06-04
**Status:** Approved (brainstorm complete; awaiting spec review → implementation plan)
**Branch:** `feat/tool-page-reskin` (proposed)
**Parent effort:** Phase B — UI/UX redesign, decomposed into **B1 Foundation+shell (✅ merged `f9a1b57`) → B2 tool-page re-skin → B3 Smart-mode dashboard landing → B4 Reports/Export PDF**. This spec covers **B2 only**.

## 1. Goal, Scope, and Non-Goals

### What it is
B2 re-skins the 10 tool pages to the design system established in B1 (shadcn/ui primitives + the earthy-agri CSS-variable token layer). It converts the pages' raw elements (native `<select>`/`<input>`, hand-rolled `bg-white border` cards, hardcoded `green-*`/`gray-*` utilities, bare `<table>`s, bright-hex chart/map colors) into shadcn primitives and design tokens, so the whole app — not just the shell — looks cohesive.

### The honest core
B2 is a **behavior-preserving** migration. Every page keeps its exact data fetching, `useWorkspace` wiring, state, props, effects, and conditional logic. Only presentation changes: element-type swaps (raw → shadcn primitive), className token swaps, and data-viz color sourcing. No API calls, request shapes, routes, or computed results change.

### Decisions locked (from brainstorm)
1. **Scope:** all 10 tool pages in ONE B2 spec/plan, executed **pattern-first** — establish the re-skin recipe on a reference page, then apply it page-by-page.
2. **Conversion depth:** full primitive conversion — Card, Button, Select, Input, Badge throughout, plus a new `table` primitive for the Mandi/FPO tables; tokens for everything else.
3. **Data-viz palette:** earthy-retone with preserved semantics, via named constants in a shared `src/lib/chartColors.js` (recharts lines + leaflet markup ramp). NOT left as-is; NOT runtime-wired to CSS vars.
4. **Execution:** Approach A — primitives used inline per page; the ONLY shared wrapper extracted is a tiny `PageHeader` atom (every page repeats it). No speculative wrapper layer (`FormCard`/`DataTable`/etc. rejected).

### Non-goals (deferred)
- **No layout/IA changes** — pages keep their current structure; B2 re-skins, it does not re-arrange.
- **No new wrapper abstraction** beyond `PageHeader`.
- **No Smart-mode dashboard landing** (B3) and **no Reports/PDF** (B4).
- **No dark mode** (tokens already support a future drop-in).
- **No behavior/logic/data change** of any kind.
- **No backend change** — the 179-test pytest suite is untouched.

## 2. Architecture & the re-skin recipe

B2's canonical mapping. The recipe is established on the **CropAdvisor reference page** (Task 1) and applied to every other page unchanged:

| Current pattern | B2 replacement |
|---|---|
| `<h1 text-2xl font-bold text-green-800>` + `<p text-gray-600>` subtitle | `PageHeader` atom (title + optional subtitle + optional icon), token-styled |
| form container `bg-white border rounded-lg shadow-sm` | `<Card>` / `<CardContent>` |
| `bg-green-700 text-white ... hover:bg-green-800` button | shadcn `<Button>` (variant `default`); secondary/link actions → `variant="outline"`/`"ghost"`/`"link"` |
| native `<select>` | shadcn `<Select>` (controlled via `value`/`onValueChange`) |
| native `<input type="number"/"text">` | shadcn `<Input>` |
| result/recommendation cards | `<Card>`; the "best/first" card → `border-primary bg-secondary` accent |
| pills (`Smart Mode`, `Best pick`, rank number, `(est.)`, fallback source) | `<Badge>` (variants `default`/`secondary`/`outline`; advisory → accent treatment) |
| bare `<table>` (Mandi, FPO) | new `<Table>` primitive (`Table/TableHeader/TableBody/TableRow/TableHead/TableCell`); best/highlighted row → `bg-secondary` |
| trend arrows ↗ → ↘ | rising → `text-primary`, falling → `text-destructive`, flat → `text-muted-foreground` |
| amber fallback banners / `⚠` cautions / `(est.)` / existing `text-amber-600` | **`accent` token** (amber/clay) — the one semantic kept warm; advisory banners → `bg-accent/10 border-accent/40` with `text-foreground` body |
| dashed empty states `border-dashed text-gray-400` | inline token recolor → `border-border text-muted-foreground` (no new atom) |
| recharts stroke / leaflet fill hex | imported from `src/lib/chartColors.js` |

**Behavior rule (applies to every task):** no change to data fetching, `useWorkspace` usage, state, props, effects, handlers, conditionals, request params, or computed values. Diff is presentation only.

## 3. New shared pieces (Task 1)

1. **`src/components/ui/table.jsx`** — canonical shadcn `table` primitive, fetched via the CLI (`npx shadcn@latest add table --yes --overwrite`, `components.json` already present from B1). Exports `Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption`. Uses token classes + `cn` from `@/lib/utils`.
2. **`src/lib/chartColors.js`** — named earthy color constants (literal hex, since recharts/leaflet need color strings not Tailwind classes):
   ```js
   export const CHART = {
     farmGate: '#2f6b46',                          // earthy green (≈ --primary)
     market:   '#b4532a',                          // clay/red
     series:  ['#2f6b46', '#b4532a', '#9a7b4f'],   // multi-line (e.g. Forecast actual/forecast)
     trend: { up: '#2f6b46', down: '#b4532a', flat: '#8a8276' },
   }
   // CropAdvisor module breakdown bars — four earthy-distinct categorical tones
   // (replaces the cool bg-emerald/sky/amber/cyan-500 hues)
   export const MODULE_COLORS = {
     suitability: '#2f6b46', // green
     regional:    '#6b8f3a', // olive
     market:      '#c08a2e', // amber/gold
     weather:     '#3f7d7a', // muted teal
   }
   export const MARKUP_RAMP = ['#f5e6c8', '#e8c79a', '#d99a5c', '#c56a36', '#a8472a', '#7c2d12'] // amber → deep clay
   ```
   Consumed by PriceTrend (2 lines), Forecast (series), StateMap `getColor()` (ramp), and CropAdvisor breakdown bars (`MODULE_COLORS`).
3. **`src/components/PageHeader.jsx`** — `export default function PageHeader({ title, subtitle, icon })`; renders a token-styled `<h1>` (+ optional subtitle `<p className="text-muted-foreground">`). The single shared extraction; all 10 pages adopt it. No other wrappers.

## 4. Page-by-page mapping

Each page is one task; all apply the Section 2 recipe. Surface changes noted; behavior identical.

- **CropAdvisor** (Task 1, reference): Goal form → `Card` + `Select` + `Button`; ranked result cards → `Card` (best = `border-primary bg-secondary`); rank/best-pick/mode pills → `Badge`; module breakdown bars recolored (`bg-muted` track; fills use `MODULE_COLORS` from `chartColors.js` via inline `style={{ backgroundColor }}`, replacing the cool `bg-emerald/sky/amber/cyan-500` classes); trend arrows + cautions use the token/accent semantics; empty state recolor; `PageHeader`.
- **CropRecommender (Soil Match):** 7-input soil form → `Card` + `Input`/`Select` + `Button`; results → `Card`/`Badge`; `PageHeader`.
- **MandiCompare:** transport-rate `<input>` → `Input`; `state_fallback` amber banner → accent `Card`; `source==='mandi'` results table → `<Table>` (best-net row `bg-secondary`); source/fallback labels → `Badge`; `PageHeader`. Keeps the auto-load `useEffect` and all `source` branches exactly.
- **ProfitPlanner:** calculator inputs → `Input`/`Select` inside a `Card`; computed figures → `Card` with token emphasis; `PageHeader`.
- **FpoBulkDashboard:** farmer-roster + transport inputs → `Input`; per-member breakdown + plan tables → `<Table>`; honesty / spread-warning / collection-point banners → accent or `secondary` `Card` + `Badge`; `PageHeader`. The deferred FPO in-browser Arc smoke is exercised here during final verification.
- **StateMap:** selected-state detail panel `bg-green-50 border-green-200` → `Card`; `getColor()` ramp → `MARKUP_RAMP`; legend/hint text recolor; `PageHeader`. Leaflet `MapContainer`/`TileLayer`/`GeoJSON` internals unchanged.
- **CropAnalyser:** filter controls → `Select`/`Input`; output region → `Card`/`Table` as fits the existing content; `PageHeader`.
- **RevenueLoss:** filter/calc controls → `Select`/`Input`; output → `Card`; `PageHeader`.
- **PriceTrend:** commodity `<select>` → `Select`; chart wrapped in a `Card`; `<Line stroke>` → `CHART.farmGate` / `CHART.market`; `PageHeader`. `ResponsiveContainer`/`LineChart` structure unchanged.
- **Forecast:** controls → `Select`; forecast/actual `<Line>`s → `CHART.series`; chart in a `Card`; `PageHeader`.

**Folded-in cleanup:** the B1-review ContextBar `Select` accessibility nit — add `id` to the `SelectTrigger` and `htmlFor` to its label in `frontend/src/workspace/ContextBar.jsx`. Tiny shell touch, natural to do in B2.

## 5. Testing & Verification

No frontend unit-test runner exists and B2 is presentational, so the gate is build + behavior-preservation + a final in-Arc visual smoke (matching B1):
- **Per task:** `npm run build` clean after each page.
- **After Task 1 (reference page):** human eyeballs CropAdvisor in **Arc** and approves the recipe before the fan-out tasks proceed.
- **Final:** `npm run build` green; backend `venv\Scripts\python.exe -m pytest -p no:asyncio` → **179 passed** (backend untouched, sanity only); full **in-Arc visual smoke** (per the locked Arc-not-Chrome rule) of all 3 intents × all 10 pages, including the deferred FPO click-through — confirm earthy palette, working controls/charts/map/tables, no console errors, no behavior regressions.
- **Acceptance criteria:**
  - Every tool page renders and functions identically to pre-B2 (same data, controls, results, routes).
  - All 10 pages use shadcn primitives + tokens; no hardcoded `green-*`/`gray-*` left on the tool pages (the only literal colors are the intentional earthy hex in `chartColors.js`).
  - `npm run build` green; pytest 179 green; no console errors in the Arc smoke.

## 6. Out-of-Scope / Follow-on
- **B3** — Smart-mode dashboard landing.
- **B4** — Reports/Export PDF (also satisfies the policy-brief-PDF PM-CV idea).
- **Dark mode** — token `.dark{}` drop-in when desired.
- **Push** — the held FPO commit (`7575a07`) + all B1–B4 commits push to `origin/master` together only after Phase B lands (standing user decision).
