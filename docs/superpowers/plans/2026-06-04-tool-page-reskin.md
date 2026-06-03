# Tool-Page Re-skin (Phase B2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin all 10 tool pages to the B1 design system (shadcn primitives + earthy-agri tokens), behavior-preserving, pattern-first off a CropAdvisor reference page.

**Architecture:** B1 already added the token layer + primitives (button, card, badge, input, select, tabs, dialog) and the `@`→`src` alias. B2 adds a `table` primitive, a `lib/chartColors.js` palette module, and a `PageHeader` atom, then converts each page's raw elements (`<select>`/`<input>`, `bg-white border` cards, hardcoded `green-*`/`gray-*`, bare `<table>`, bright chart hex) to those primitives/tokens. No data, request, route, state, or logic changes.

**Tech Stack:** React 19, Vite 8, Tailwind v3, shadcn/ui (Card/Button/Select/Input/Badge/Table), recharts, react-leaflet, the earthy CSS-var tokens from B1.

**Testing approach:** No frontend unit-test runner; B2 is presentational. Per-task gate = `npm run build` clean + behavior preservation. After Task 1 a human approves the CropAdvisor reference in **Arc**. Final task runs backend pytest 179 (untouched, sanity) + a full in-**Arc** visual smoke (Arc only, never Chrome).

**Working dir:** run `npm` from `E:\agri-market-analyser\frontend`; run `git` from `E:\agri-market-analyser` (or `git -C E:/agri-market-analyser`). Branch `feat/tool-page-reskin` already exists with the spec commit (`dafc77b`).

**Commit rule:** targeted `git add <paths>` only — NEVER `-A`/`.`/`-u`. Every commit ends with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Do NOT push.

---

## Primitive cheat-sheet (shadcn APIs used throughout)

All primitives live in `@/components/ui/*` and are already present except `table` (added in Task 1). Import only what each page uses.

```jsx
// Card
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
<Card><CardContent className="p-4">…</CardContent></Card>

// Button — variant: default|secondary|outline|ghost|link|destructive ; size: default|sm|lg|icon
import { Button } from '@/components/ui/button'
<Button onClick={…} disabled={…}>Label</Button>
<Button type="button" variant="outline" size="sm">…</Button>

// Select — controlled via value/onValueChange (NOT onChange). SelectItem value must be a non-empty string.
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
<Select value={v} onValueChange={setV}>
  <SelectTrigger className="w-44"><SelectValue placeholder="…" /></SelectTrigger>
  <SelectContent>{opts.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
</Select>

// Input
import { Input } from '@/components/ui/input'
<Input type="number" step="any" value={v} onChange={e => setV(e.target.value)} className="w-28" />

// Badge — variant: default|secondary|destructive|outline
import { Badge } from '@/components/ui/badge'
<Badge variant="secondary">Smart Mode</Badge>

// Table (added Task 1)
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
<Table><TableHeader><TableRow><TableHead>Col</TableHead></TableRow></TableHeader>
  <TableBody><TableRow><TableCell>…</TableCell></TableRow></TableBody></Table>

// PageHeader (added Task 1)
import PageHeader from '@/components/PageHeader'
<PageHeader title="🌱 Crop Advisor" subtitle="Best crops for your field…" />
```

**Empty-state / advisory recolor conventions (memorize):**
- empty/prompt: `border border-dashed border-border rounded-lg … text-muted-foreground`
- advisory/fallback/caution banner: `<Card>` with `border-accent/40 bg-accent/10`; caution text → `text-accent` or `text-foreground`
- trend: rising `text-primary`, falling `text-destructive`, flat `text-muted-foreground`
- "best/first" highlight card: `border-primary bg-secondary`
- table highlighted row: `bg-secondary`

---

## File Structure

**Created (Task 1):**
- `frontend/src/components/ui/table.jsx` — shadcn table primitive (CLI).
- `frontend/src/lib/chartColors.js` — `CHART`, `MODULE_COLORS`, `MARKUP_RAMP` constants.
- `frontend/src/components/PageHeader.jsx` — title/subtitle atom.

**Modified (one page per task):** `frontend/src/pages/{CropAdvisor,CropRecommender,MandiCompare,ProfitPlanner,FpoBulkDashboard,StateMap,CropAnalyser,RevenueLoss,PriceTrend,Forecast}.jsx`, and `frontend/src/workspace/ContextBar.jsx` (a11y nit, Task 11).

---

## Task 1: Foundation + CropAdvisor reference page

**Files:**
- Create: `frontend/src/components/ui/table.jsx`, `frontend/src/lib/chartColors.js`, `frontend/src/components/PageHeader.jsx`
- Modify: `frontend/src/pages/CropAdvisor.jsx`

- [ ] **Step 1: Add the shadcn table primitive**

Run from `frontend/`: `npx --yes shadcn@latest add table --yes --overwrite`
Expected: creates `src/components/ui/table.jsx` exporting `Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption`, importing `cn` from `@/lib/utils`, using token classes. If the CLI clobbers `index.css`/`tailwind.config.js`, revert those two (`git -C E:/agri-market-analyser checkout -- frontend/src/index.css frontend/tailwind.config.js`) — confirm `--primary: 142 40% 30%` still in index.css.

- [ ] **Step 2: Create `frontend/src/lib/chartColors.js`**

```js
export const CHART = {
  farmGate: '#2f6b46',                          // earthy green (≈ --primary)
  market:   '#b4532a',                          // clay/red
  series:  ['#2f6b46', '#b4532a', '#9a7b4f'],   // multi-line
  trend: { up: '#2f6b46', down: '#b4532a', flat: '#8a8276' },
  split: '#8a8276',                             // forecast ReferenceLine
}
// CropAdvisor module breakdown bars — four earthy-distinct categorical tones
export const MODULE_COLORS = {
  suitability: '#2f6b46', // green
  regional:    '#6b8f3a', // olive
  market:      '#c08a2e', // amber/gold
  weather:     '#3f7d7a', // muted teal
}
export const MARKUP_RAMP = ['#f5e6c8', '#e8c79a', '#d99a5c', '#c56a36', '#a8472a', '#7c2d12'] // amber → deep clay
```

- [ ] **Step 3: Create `frontend/src/components/PageHeader.jsx`**

```jsx
export default function PageHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h1 className="text-2xl font-bold text-foreground mb-1">{title}</h1>
      {subtitle && <p className="text-muted-foreground">{subtitle}</p>}
    </div>
  )
}
```

- [ ] **Step 4: Re-skin `frontend/src/pages/CropAdvisor.jsx` (the reference)**

Keep ALL logic above the `return` byte-identical (imports of hooks/api/context, `GOALS`, `submit`, `isSmart`, state). Change only: the MODULES color entries → reference `MODULE_COLORS`; add primitive imports; rewrite the JSX. Replace the file with:

```jsx
import { useState } from 'react'
import { recommendSmart } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { MODULE_COLORS } from '@/lib/chartColors'

const GOALS = [
  ['', 'Balanced'], ['max_profit', 'Max Profit'], ['low_risk', 'Low Risk'],
  ['sustainable', 'Sustainable'], ['water_efficient', 'Water Efficient'],
]
const MODULES = [
  ['suitability', 'Soil/Climate'], ['regional', 'Regional'],
  ['market', 'Market'], ['weather', 'Weather'],
]
const TREND = { rising: '↗', flat: '→', falling: '↘' }
const trendColor = (t) => (t === 'rising' ? 'text-primary' : t === 'falling' ? 'text-destructive' : 'text-muted-foreground')

export default function CropAdvisor() {
  const { state, district, season, lat, lon, mode, soil, setCrop } = useWorkspace()
  const [goal, setGoal] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null); setLoading(true)
    try {
      const body = { state, top_k: 5 }
      if (district?.trim()) body.district = district.trim()
      if (season && season !== 'Any') body.season = season
      if (goal) body.goal = goal
      if (lat != null && lon != null) { body.lat = lat; body.lon = lon }
      if (mode === 'smart' && soil) body.soil = soil
      setResult(await recommendSmart(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed'); setResult(null)
    } finally { setLoading(false) }
  }

  const isSmart = result?.modules_used?.includes('suitability')

  return (
    <div className="max-w-3xl w-full">
      <PageHeader title="🌱 Crop Advisor"
        subtitle="Best crops for your field — regional history, market prices, and live seasonal weather. Switch to Smart mode and add soil details for a sharper agronomic match." />
      {error && <ErrorBanner message={error} />}

      <Card className="mb-6">
        <CardContent className="p-4 flex flex-wrap items-end gap-3">
          <label className="text-sm text-foreground">Goal
            <Select value={goal || 'balanced'} onValueChange={(v) => setGoal(v === 'balanced' ? '' : v)}>
              <SelectTrigger className="mt-1 w-44"><SelectValue placeholder="Balanced" /></SelectTrigger>
              <SelectContent>
                {GOALS.map(([v, l]) => <SelectItem key={v || 'balanced'} value={v || 'balanced'}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          <Button onClick={submit} disabled={loading} size="lg">
            {loading ? 'Analyzing…' : 'Recommend crops'}
          </Button>
          {mode !== 'smart' && (
            <span className="text-xs text-muted-foreground">Simple Mode · turn on Smart for soil suitability</span>
          )}
        </CardContent>
      </Card>

      {!result && !loading && (
        <div className="text-center text-muted-foreground border border-dashed border-border rounded-lg py-10">
          Set your location above, then hit <span className="font-medium text-foreground">Recommend crops</span>.
        </div>
      )}

      {result && (
        <div>
          <p className="text-xs text-muted-foreground mb-3 flex items-center gap-2 flex-wrap">
            <Badge variant={isSmart ? 'default' : 'secondary'}>{isSmart ? 'Smart Mode' : 'Simple Mode'}</Badge>
            <span>{result.method} fusion ·{' '}
            {Object.entries(result.weights_used).map(([m, w]) =>
              `${MODULES.find((x) => x[0] === m)?.[1] || m} ${Math.round(w * 100)}%`).join(' · ')}</span>
          </p>
          <div className="space-y-3">
            {result.recommendations.map((r, i) => (
              <Card key={r.crop} className={i === 0 ? 'border-primary bg-secondary' : ''}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground text-sm font-bold">
                      {i + 1}
                    </span>
                    <span className="font-bold capitalize text-foreground text-lg">{r.crop}</span>
                    {i === 0 && <Badge>Best pick</Badge>}
                    <span className="ml-auto text-xs text-muted-foreground">match {r.score}</span>
                  </div>
                  <Button type="button" variant="link" size="sm" className="px-0 h-auto mb-2"
                    onClick={() => setCrop(r.crop)}>
                    See market &amp; prices for {r.crop} →
                  </Button>
                  {r.traditional?.years_grown > 0 && (
                    <p className="text-sm text-primary font-medium mb-1">
                      ✓ Traditional here — grown {r.traditional.years_grown} yr
                      {r.traditional.years_grown > 1 ? 's' : ''} on record
                      {r.traditional.level === 'state' && ' (state-wide)'}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-foreground mb-2">
                    {r.yield?.predicted_yield != null ? (
                      <span>
                        Predicted yield: <b>~{r.yield.predicted_yield} {r.yield.unit}</b>{' '}
                        <span className={trendColor(r.yield.trend)}>{TREND[r.yield.trend]}</span>
                        {r.yield.traditional_yield != null &&
                          <span className="text-muted-foreground"> (was ~{r.yield.traditional_yield})</span>}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">No reliable yield estimate</span>
                    )}
                    {r.price_outlook?.price != null && (
                      <span>
                        Price outlook: <b>₹{r.price_outlook.price}/q</b>{' '}
                        <span className={trendColor(r.price_outlook.trend)}>{TREND[r.price_outlook.trend]}</span>
                        <span className="text-muted-foreground text-xs">
                          {' '}{r.price_outlook.source === 'forecast' ? '(forecast)' : '(recent)'}
                        </span>
                      </span>
                    )}
                  </div>
                  <div className="space-y-1 mb-3 opacity-80">
                    {MODULES.filter(([m]) => m in r.breakdown).map(([m, label]) => (
                      <div key={m} className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="w-24 shrink-0">{label}</span>
                        <div className="flex-1 h-2.5 bg-muted rounded-full overflow-hidden">
                          <div className="h-2.5 rounded-full"
                            style={{ width: `${Math.round(r.breakdown[m] * 100)}%`, backgroundColor: MODULE_COLORS[m] }} />
                        </div>
                        <span className="w-8 text-right tabular-nums">{Math.round(r.breakdown[m] * 100)}</span>
                      </div>
                    ))}
                  </div>
                  {r.why.map((w) => <p key={w} className="text-sm text-primary">✓ {w}</p>)}
                  {r.cautions.map((c) => <p key={c} className="text-sm text-accent">⚠ {c}</p>)}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

Note: shadcn `SelectItem` forbids an empty-string `value`, so the "Balanced" option (whose real value is `''`) uses the sentinel `'balanced'` in the items and the trigger (`value={goal || 'balanced'}`), while `onValueChange` maps `'balanced'` back to `''` so `goal` state and the API body are unchanged from the original. This exact wiring is already in the code block above.

- [ ] **Step 5: Verify build**

Run from `frontend/`: `npm run build`. Expected: succeeds (CropAdvisor imports the new primitives/atoms/colors — compiles them for real).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/table.jsx frontend/src/lib/chartColors.js frontend/src/components/PageHeader.jsx frontend/src/pages/CropAdvisor.jsx frontend/components.json frontend/package.json frontend/package-lock.json
git commit -m "B2: foundation (table primitive, chartColors, PageHeader) + CropAdvisor reference re-skin" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
(Only stage components.json/package*.json IF the CLI changed them; otherwise omit those paths.)

- [ ] **Step 7: 🚦 HUMAN CHECKPOINT** — STOP. The controller must have the human view CropAdvisor in **Arc** (servers already running on :5173/:8000) and approve the recipe before any fan-out task proceeds.

---

## Task 2: CropRecommender (Soil Match)

**Files:** Modify `frontend/src/pages/CropRecommender.jsx`

Keep logic (imports, `submit`, state, `DEFAULT_SOIL` usage) identical. Replace the file with:

```jsx
import { useState } from 'react'
import { recommendCrop } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import { DEFAULT_SOIL } from '../workspace/SoilPanel'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export default function CropRecommender() {
  const { mode, soil, setMode } = useWorkspace()
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      setResult(await recommendCrop(soil || DEFAULT_SOIL))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed'); setResult(null)
    }
  }

  return (
    <div className="max-w-3xl w-full">
      <PageHeader title="Soil Match"
        subtitle="Pure soil/climate model: enter your soil values in the Soil details panel (Smart mode) above, then match the best crops." />
      {error && <ErrorBanner message={error} />}

      {mode !== 'smart' ? (
        <div className="border border-dashed border-border rounded-lg p-6 text-center text-muted-foreground">
          Turn on <b>Smart</b> mode (top-right) to enter soil details, then come back here.
          <div className="mt-3">
            <Button onClick={() => setMode('smart')} size="sm">Switch to Smart</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="mb-6">
          <Button size="lg">
            Match crops {soil ? '' : '(using defaults — fill Soil details for accuracy)'}
          </Button>
        </form>
      )}

      {result && (
        <div>
          <p className="text-lg mb-3">Best pick for your soil:{' '}
            <span className="font-bold text-primary capitalize">{result.top.crop}</span>{' '}
            ({result.top.confidence_pct}% match)</p>
          <div className="space-y-2">
            {result.recommendations.map((r, i) => (
              <Card key={r.crop} className={i === 0 ? 'border-primary bg-secondary' : ''}>
                <CardContent className="p-3">
                  <div className="flex justify-between text-sm font-medium">
                    <span className="capitalize">{r.crop}</span><span>{r.confidence_pct}%</span>
                  </div>
                  <div className="h-2 bg-muted rounded mt-1">
                    <div className="h-2 bg-primary rounded" style={{ width: `${r.confidence_pct}%` }} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 1: Replace the file** with the above.
- [ ] **Step 2: Build** — `npm run build` from `frontend/`. Expected: succeeds.
- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/CropRecommender.jsx
git commit -m "B2: re-skin CropRecommender (Soil Match)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: MandiCompare

**Files:** Modify `frontend/src/pages/MandiCompare.jsx`

Keep ALL logic (imports, `coords`, `rate` state, the auto-load `useEffect` with its deps, `markets`/`best` derivations, every `source` branch) identical. Replace the JSX presentation: PageHeader; transport `<input>`→`Input`; `state_fallback` banner→accent Card + Badge; results `<table>`→`<Table>` with best row `bg-secondary`. Replace the file with:

```jsx
import { useState, useEffect } from 'react'
import { compareMandis } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

export default function MandiCompare() {
  const { crop, state, lat, lon, area, district } = useWorkspace()
  const coords = lat != null && lon != null ? { lat, lon } : null
  const [rate, setRate] = useState(2)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!crop) { setResult(null); return }
    const params = { commodity: crop, top: 10 }
    if (state) params.state = state
    if (coords) { params.lat = coords.lat; params.lon = coords.lon; params.rate_per_km = Number(rate) }
    let live = true
    compareMandis(params)
      .then((r) => { if (live) { setResult(r); setError(null) } })
      .catch((err) => { if (live) { setError(err.response?.data?.detail || 'Comparison failed'); setResult(null) } })
    return () => { live = false }
  }, [crop, state, lat, lon, rate])

  const markets = result?.markets || []
  const best = markets.find((r) => r.is_best_net)

  return (
    <div className="max-w-4xl w-full">
      <PageHeader title="Mandi Comparison" subtitle="Nearest markets for your crop, with net price after transport." />
      {error && <ErrorBanner message={error} />}

      {!crop && <p className="text-muted-foreground">Pick a crop above to see market prices.</p>}

      {crop && (
        <label className="text-sm inline-block mb-4 text-foreground">Transport ₹/km/quintal
          <Input type="number" step="any" value={rate} onChange={(e) => setRate(e.target.value)} className="mt-1 w-28" />
        </label>
      )}

      {result?.source === 'state_fallback' && (
        <Card className="border-accent/40 bg-accent/10 mb-3">
          <CardContent className="p-4">
            <p className="text-lg">State-level estimate for <b className="capitalize">{result.crop}</b> in {result.state}:{' '}
              <span className="font-bold text-primary">₹{result.state_avg}/q</span></p>
            <p className="text-xs text-accent mt-1">No live mandi data for this crop in your area — showing the state average instead.</p>
          </CardContent>
        </Card>
      )}

      {result?.source === 'none' && (
        <p className="text-muted-foreground">No market or state price data for <b className="capitalize">{crop}</b>.</p>
      )}

      {result?.source === 'mandi' && (
        <>
          {coords ? (
            <p className="text-xs text-muted-foreground mb-3">Using {area || district || 'your location'} ({coords.lat.toFixed(3)}, {coords.lon.toFixed(3)}). Markets ranked by distance.</p>
          ) : (
            <p className="text-xs text-muted-foreground mb-3">Set a pincode or use GPS above to rank markets by distance.</p>
          )}
          {best && (
            <p className="text-lg mb-3">Best net price near you:{' '}
              <span className="font-bold text-primary">{best.market}</span>{' '}
              — ₹{best.net_price}/q{best.distance_km != null ? ` after ~${best.distance_km} km` : ''}.</p>
          )}
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Market</TableHead><TableHead>District</TableHead>
                  <TableHead>Modal ₹/q</TableHead><TableHead>Distance</TableHead>
                  <TableHead>Transport ₹/q</TableHead><TableHead>Net ₹/q</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {markets.map((r, i) => (
                  <TableRow key={i} className={r.is_best_net ? 'bg-secondary font-medium' : ''}>
                    <TableCell>{r.market}</TableCell>
                    <TableCell>{r.district}, {r.state}</TableCell>
                    <TableCell>₹{r.modal_price}</TableCell>
                    <TableCell>{r.distance_km != null ? `${r.distance_km} km` : '—'}</TableCell>
                    <TableCell>₹{r.transport_per_q}</TableCell>
                    <TableCell>₹{r.net_price}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 1: Replace the file.**
- [ ] **Step 2: Build** — `npm run build`. Expected: succeeds (compiles the new `table` primitive for the first time).
- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/MandiCompare.jsx
git commit -m "B2: re-skin MandiCompare (Table primitive, accent fallback)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: ProfitPlanner

**Files:** Modify `frontend/src/pages/ProfitPlanner.jsx`

Keep logic (imports, `filters`/`ref`/`form`/`result` state, `loadPrice`, `submit`, `NUM`, `LABELS`) identical. Map `RISK_COLOR` to token classes; commodity `<select>`→`Select`; inputs→`Input`; result box→`Card`; profit/loss text→token. Replace the file with:

```jsx
import { useState, useEffect } from 'react'
import { planProfit, getPriceReference, getTrendFilters } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const RISK_COLOR = { low: 'bg-primary/15 text-primary', medium: 'bg-accent/15 text-accent',
                     high: 'bg-destructive/15 text-destructive', unknown: 'bg-muted text-muted-foreground' }
const NUM = ['area_acres', 'yield_q_per_acre', 'input_cost', 'labour_cost', 'transport_cost', 'market_price']
const LABELS = { area_acres: 'Area (acres)', yield_q_per_acre: 'Yield (quintal/acre)',
  input_cost: 'Input cost (₹)', labour_cost: 'Labour cost (₹)', transport_cost: 'Transport cost (₹)',
  market_price: 'Market price (₹/quintal)' }

export default function ProfitPlanner() {
  const { state, crop, setCrop } = useWorkspace()
  const [filters, setFilters] = useState({ states: [], commodities: [] })
  const commodity = crop
  const setCommodity = setCrop
  const [ref, setRef] = useState(null)
  const [form, setForm] = useState({ area_acres: 2, yield_q_per_acre: 20, input_cost: 10000,
    labour_cost: 5000, transport_cost: 3000, market_price: 1500 })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { getTrendFilters().then(setFilters).catch(() => {}) }, [])

  const loadPrice = async () => {
    if (!state || !commodity) return
    const r = await getPriceReference(state, commodity)
    setRef(r)
    if (r.latest_price) setForm((f) => ({ ...f, market_price: r.latest_price }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const body = Object.fromEntries(NUM.map((k) => [k, Number(form[k])]))
      setResult(await planProfit(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Calculation failed'); setResult(null)
    }
  }

  return (
    <div className="max-w-3xl w-full">
      <PageHeader title="Profit Planner" subtitle="Estimate profit, break-even price, and selling risk for your crop." />
      {error && <ErrorBanner message={error} />}

      <div className="flex flex-wrap gap-2 items-end mb-4">
        <label className="text-sm text-foreground">Commodity
          <Select value={commodity || ''} onValueChange={setCommodity}>
            <SelectTrigger className="mt-1 w-48"><SelectValue placeholder="—" /></SelectTrigger>
            <SelectContent>{filters.commodities.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
        </label>
        <Button type="button" variant="outline" size="sm" onClick={loadPrice}>Use market price</Button>
        {ref && (
          <span className={`text-xs px-2 py-1 rounded ${RISK_COLOR[ref.risk_level]}`}>
            Price risk: {ref.risk_level}{ref.latest_price ? ` (latest ₹${ref.latest_price}/q)` : ''}
          </span>
        )}
      </div>

      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {NUM.map((k) => (
          <label key={k} className="text-sm text-foreground">{LABELS[k]}
            <Input type="number" step="any" value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="mt-1 w-full" /></label>
        ))}
        <Button className="col-span-2 md:col-span-3" size="lg">Calculate</Button>
      </form>

      {result && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <p className={`text-2xl font-bold ${result.profit >= 0 ? 'text-primary' : 'text-destructive'}`}>
              {result.profit >= 0 ? 'Profit' : 'Loss'}: ₹{Math.abs(result.profit).toLocaleString('en-IN')}
            </p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <span>Revenue: ₹{result.total_revenue.toLocaleString('en-IN')}</span>
              <span>Total cost: ₹{result.total_cost.toLocaleString('en-IN')}</span>
              <span>Break-even price: {result.break_even_price ? `₹${result.break_even_price}/q` : '—'}</span>
              <span>Target sale price: {result.target_sale_price ? `₹${result.target_sale_price}/q` : '—'}</span>
            </div>
            <p className="text-foreground bg-muted rounded p-2">{result.recommendation}</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
```
Note: the original commodity select had an `<option value="">—</option>` empty option; shadcn `SelectItem` cannot use `""`. Drop the empty item (the placeholder `—` covers the no-selection display); `commodity` still initializes from context and all values are non-empty commodity names.

- [ ] **Step 1: Replace the file.**
- [ ] **Step 2: Build** — `npm run build`. Expected: succeeds.
- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/ProfitPlanner.jsx
git commit -m "B2: re-skin ProfitPlanner" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: FpoBulkDashboard

**Files:** Modify `frontend/src/pages/FpoBulkDashboard.jsx`

Keep ALL logic (imports, `DEFAULT_TRANSPORT`, `firstRow`, the location-sync `useEffect`, `setRow`/`addRow`/`removeRow`/`setT`, the pre-flight validation in `submit`, both result branches) identical. Convert: PageHeader; roster `<table>`→`<Table>` with `<Input>` cells; transport `<input>`→`Input`; compute `<button>`→`Button`; remove/add buttons→`Button` variants; amber banner→accent Card; per-member `<table>`→`<Table>`; extra-income/spread token colors. Replace the file with:

```jsx
import { useState, useEffect } from 'react'
import { fpoBulkPlan } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const DEFAULT_TRANSPORT = {
  truck_capacity_q: 100, fixed_hire_per_truck: 2000,
  per_km_per_truck: 30, per_q_local_rate: 2,
}

export default function FpoBulkDashboard() {
  const { crop, state, lat, lon } = useWorkspace()
  const firstRow = { lat: lat ?? '', lon: lon ?? '', state: state || '', quantity_q: '' }
  const [rows, setRows] = useState([firstRow])
  const [transport, setTransport] = useState(DEFAULT_TRANSPORT)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setRows((rs) => {
      const [first, ...rest] = rs
      if (first.lat === '' && first.lon === '' && (lat != null || lon != null)) {
        return [{ ...first, lat: lat ?? '', lon: lon ?? '', state: first.state || state || '' }, ...rest]
      }
      return rs
    })
  }, [lat, lon, state])

  const setRow = (i, key, val) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [key]: val } : r)))
  const addRow = () => setRows((rs) => [...rs, { lat: '', lon: '', state: state || '', quantity_q: '' }])
  const removeRow = (i) => setRows((rs) => rs.filter((_, j) => j !== i))
  const setT = (key, val) => setTransport((t) => ({ ...t, [key]: val }))

  const submit = async () => {
    setError(null)
    const invalid = rows.some((r) => r.lat === '' || r.lon === '' || !(Number(r.quantity_q) > 0))
    if (invalid) {
      setError('Each farmer row needs latitude, longitude, and a positive quantity.')
      setResult(null)
      return
    }
    try {
      const farmers = rows.map((r) => ({
        lat: Number(r.lat), lon: Number(r.lon),
        state: r.state || null, quantity_q: Number(r.quantity_q),
      }))
      const body = {
        crop, farmers,
        transport: Object.fromEntries(
          Object.entries(transport).map(([k, v]) => [k, Number(v)])),
      }
      setResult(await fpoBulkPlan(body))
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail
        : 'Check each farmer row: latitude, longitude, and a positive quantity are required.')
      setResult(null)
    }
  }

  return (
    <div className="max-w-4xl w-full">
      <PageHeader title="FPO Bulk Selling"
        subtitle="Pool members' harvest and see if trucking it together beats selling alone." />
      {error && <ErrorBanner message={error} />}
      {!crop && <p className="text-muted-foreground mb-3">Pick a crop above first.</p>}

      <div className="overflow-x-auto">
        <Table className="mb-3">
          <TableHeader>
            <TableRow>
              <TableHead>Lat</TableHead><TableHead>Lon</TableHead>
              <TableHead>State</TableHead><TableHead>Quantity (q)</TableHead><TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* key by index: rows are append/remove-by-position, no reordering */}
            {rows.map((r, i) => (
              <TableRow key={i}>
                <TableCell><Input className="w-24" value={r.lat} onChange={(e) => setRow(i, 'lat', e.target.value)} /></TableCell>
                <TableCell><Input className="w-24" value={r.lon} onChange={(e) => setRow(i, 'lon', e.target.value)} /></TableCell>
                <TableCell><Input className="w-28" value={r.state} onChange={(e) => setRow(i, 'state', e.target.value)} /></TableCell>
                <TableCell><Input className="w-24" value={r.quantity_q} onChange={(e) => setRow(i, 'quantity_q', e.target.value)} /></TableCell>
                <TableCell>{rows.length > 1 && <Button variant="ghost" size="sm" className="text-destructive" onClick={() => removeRow(i)}>✕</Button>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <Button variant="link" size="sm" className="px-0 mb-4" onClick={addRow}>+ Add farmer</Button>

      <div className="flex gap-3 flex-wrap mb-4 text-sm">
        {Object.keys(DEFAULT_TRANSPORT).map((k) => (
          <label key={k} className="capitalize text-foreground">{k.replace(/_/g, ' ')}
            <Input type="number" step="any" min="0" value={transport[k]} onChange={(e) => setT(k, e.target.value)} className="mt-1 w-32" />
          </label>
        ))}
      </div>

      <Button onClick={submit} disabled={!crop}>Compute plan</Button>

      {result && (
        <div className="mt-5">
          {result.price_basis !== 'mandi' ? (
            <Card className="border-accent/40 bg-accent/10">
              <CardContent className="p-4"><p>{result.message}</p></CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-4">
                {result.spread_warning && (
                  <p className="text-accent text-sm mb-2">⚠ {result.spread_warning}</p>
                )}
                <p className="text-lg mb-1">{result.message}</p>
                <ul className="text-sm text-foreground space-y-1 mt-2">
                  <li>Selling individually: <b>₹{result.baseline}</b></li>
                  <li>Pooled &amp; trucked{result.chosen_mandi ? ` to ${result.chosen_mandi.market}` : ''}: <b>₹{result.aggregated_rev}</b>
                    {result.chosen_mandi ? ` (${result.chosen_mandi.trucks} truck(s), ₹${result.chosen_mandi.transport_cost} transport)` : ''}</li>
                  <li className={result.extra_income > 0 ? 'text-primary font-semibold' : 'text-muted-foreground'}>
                    Extra income from pooling: ₹{result.extra_income}</li>
                </ul>
                <p className="text-xs text-muted-foreground mt-3">
                  Assumes the harvest is aggregated at a central collection point (the members' geographic centre); v1 does not plan multi-stop pickup routes.
                </p>
                {result.per_farmer?.length > 0 && (
                  <div className="overflow-x-auto mt-4">
                    <p className="text-sm font-medium text-foreground mb-1">If each member sold on their own:</p>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Member (lat, lon)</TableHead><TableHead>Qty (q)</TableHead>
                          <TableHead>Best market</TableHead><TableHead>Revenue ₹</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {result.per_farmer.map((f, i) => (
                          <TableRow key={i}>
                            <TableCell>{f.lat}, {f.lon}</TableCell>
                            <TableCell>{f.quantity_q}</TableCell>
                            <TableCell>{f.best_market ?? '—'}</TableCell>
                            <TableCell>₹{f.revenue}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 1: Replace the file.**
- [ ] **Step 2: Build** — `npm run build`. Expected: succeeds.
- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/FpoBulkDashboard.jsx
git commit -m "B2: re-skin FpoBulkDashboard (Table primitive, accent banners)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: StateMap

**Files:** Modify `frontend/src/pages/StateMap.jsx`

Keep ALL logic (data load `useEffect`, `styleFeature`, `onEachFeature`, leaflet `MapContainer`/`TileLayer`/`GeoJSON`) identical. Change: `getColor` reads `MARKUP_RAMP`; detail panel → `Card`; PageHeader. Replace `getColor` and the JSX:

- [ ] **Step 1:** Add import at top: `import PageHeader from '@/components/PageHeader'`, `import { Card, CardContent } from '@/components/ui/card'`, `import { MARKUP_RAMP } from '@/lib/chartColors'`.

- [ ] **Step 2:** Replace the `getColor` function (lines 8–16) with:
```jsx
function getColor(pct) {
  if (pct > 150) return MARKUP_RAMP[5]
  if (pct > 100) return MARKUP_RAMP[4]
  if (pct > 70)  return MARKUP_RAMP[3]
  if (pct > 50)  return MARKUP_RAMP[2]
  if (pct > 30)  return MARKUP_RAMP[1]
  return MARKUP_RAMP[0]
}
```
(The old scale had 7 stops via two thresholds at the low end; `MARKUP_RAMP` has 6 — collapse the bottom two `>15`/else into `MARKUP_RAMP[0]` as shown. The `weight:1, color:'#fff'` GeoJSON stroke stays.)

- [ ] **Step 3:** Replace the `return (...)` block with:
```jsx
  return (
    <div>
      <PageHeader title="Farm-to-Market Markup by State" subtitle="Darker = higher markup. Click a state for details." />
      <div className="flex gap-6">
        <MapContainer center={[22, 82]} zoom={5} style={{ height: '500px', width: '65%' }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org">OpenStreetMap</a>' />
          {geoData && <GeoJSON data={geoData} style={styleFeature} onEachFeature={onEachFeature} />}
        </MapContainer>
        {selected && (
          <Card className="w-64 h-fit">
            <CardContent className="p-4">
              <h3 className="font-bold text-foreground text-lg">{selected.state}</h3>
              <p className="text-sm text-muted-foreground mt-2">
                Avg Markup: <span className="font-bold text-destructive">{selected.avg_markup_pct ?? 'N/A'}%</span>
              </p>
              <p className="text-sm text-muted-foreground">Farm Gate: &#8377;{selected.avg_farm_gate ?? 'N/A'}/q</p>
              <p className="text-sm text-muted-foreground">Market Price: &#8377;{selected.avg_modal ?? 'N/A'}/q</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
```
(Leave the `if (loading) return <LoadingSpinner />` / `if (error) return <ErrorBanner .../>` early returns above unchanged.)

- [ ] **Step 4: Build** — `npm run build`. Expected: succeeds.
- [ ] **Step 5: Commit**
```bash
git add frontend/src/pages/StateMap.jsx
git commit -m "B2: re-skin StateMap (earthy markup ramp, Card panel)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: CropAnalyser

**Files:** Modify `frontend/src/pages/CropAnalyser.jsx`

Keep ALL logic (both `useEffect`s, sort, state) identical. Change: PageHeader; `<select>`→`Select`; bar `Cell` fills → `CHART.market`/`CHART.farmGate`. Replace the file with:

```jsx
import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getCropMarkup, getTrendFilters } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { CHART } from '@/lib/chartColors'

export default function CropAnalyser() {
  const { crop, setCrop } = useWorkspace()
  const selected = crop
  const setSelected = setCrop
  const [crops, setCrops]       = useState([])
  const [data, setData]         = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setCrops(f.commodities)
        if (!crop && f.commodities.length) setCrop(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    setError(null)
    getCropMarkup(selected)
      .then(d => setData([...d].sort((a, b) => b.avg_markup_pct - a.avg_markup_pct)))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selected])

  return (
    <div>
      <PageHeader title="Crop Markup by State" />
      {error && <ErrorBanner message={error} />}
      <Select value={selected || ''} onValueChange={setSelected}>
        <SelectTrigger className="w-48 mb-4"><SelectValue placeholder="Select crop" /></SelectTrigger>
        <SelectContent>{crops.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
      </Select>
      {loading ? <LoadingSpinner /> : (
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={data} layout="vertical" margin={{ left: 100 }}>
            <XAxis type="number" unit="%" />
            <YAxis dataKey="state" type="category" width={100} tick={{ fontSize: 12 }} />
            <Tooltip formatter={v => `${v}%`} />
            <Bar dataKey="avg_markup_pct" name="Markup %">
              {data.map((_, i) => <Cell key={i} fill={i < 5 ? CHART.market : CHART.farmGate} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
```

- [ ] **Step 1: Replace the file.**
- [ ] **Step 2: Build** — `npm run build`. Expected: succeeds.
- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/CropAnalyser.jsx
git commit -m "B2: re-skin CropAnalyser (Select, earthy bar colors)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: RevenueLoss

**Files:** Modify `frontend/src/pages/RevenueLoss.jsx`

Keep ALL logic (data load, sort, `total`) identical. Note: this page has NO workspace context. Change: PageHeader; bar fill → `CHART.market`; `<table>`→`<Table>` (header was `bg-green-800 text-white`, zebra `bg-gray-50`, loss `text-red-600`). Replace the file with:

```jsx
import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getRevenueLoss } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { CHART } from '@/lib/chartColors'

export default function RevenueLoss() {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    getRevenueLoss()
      .then(d => setData([...d].sort((a, b) => b.estimated_loss_cr - a.estimated_loss_cr)))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const total = data.reduce((s, r) => s + r.estimated_loss_cr, 0).toFixed(2)

  return (
    <div>
      <PageHeader title="Estimated Revenue Loss to Farmers"
        subtitle={`Estimated ₹${total} Cr total annual loss across all states (proxy volume model)`} />
      {error && <ErrorBanner message={error} />}
      {loading ? <LoadingSpinner /> : (
        <>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={data.slice(0, 15)}>
              <XAxis dataKey="state" tick={{ fontSize: 10 }} />
              <YAxis unit=" Cr" />
              <Tooltip formatter={v => `₹${v} Cr`} />
              <Bar dataKey="estimated_loss_cr" fill={CHART.market} name="Est. Loss (₹ Cr)" />
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-6 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>State</TableHead><TableHead className="text-center">Avg Gap (₹/q)</TableHead>
                  <TableHead className="text-center">Est. Loss (₹ Cr)</TableHead><TableHead className="text-center">Crops Tracked</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((r) => (
                  <TableRow key={r.state}>
                    <TableCell className="font-medium">{r.state}</TableCell>
                    <TableCell className="text-center">₹{r.avg_gap_per_quintal}</TableCell>
                    <TableCell className="text-center text-destructive font-bold">₹{r.estimated_loss_cr} Cr</TableCell>
                    <TableCell className="text-center">{r.crop_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
```
(The zebra striping is dropped in favor of the Table primitive's default row borders/hover — a deliberate, behavior-neutral simplification.)

- [ ] **Step 1: Replace the file.**
- [ ] **Step 2: Build** — `npm run build`. Expected: succeeds.
- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/RevenueLoss.jsx
git commit -m "B2: re-skin RevenueLoss (Table, earthy bar)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: PriceTrend

**Files:** Modify `frontend/src/pages/PriceTrend.jsx`

Keep ALL logic (both `useEffect`s, `commodity`/`setCommodity` aliases) identical. Change: PageHeader; `<select>`→`Select`; chart wrapped in `Card`; line strokes → `CHART`. Replace the file with:

```jsx
import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { getTrendFilters, getPriceTrend } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { CHART } from '@/lib/chartColors'

export default function PriceTrend() {
  const { state, crop, setCrop } = useWorkspace()
  const [filters, setFilters]     = useState({ states: [], commodities: [] })
  const commodity = crop
  const setCommodity = setCrop
  const [data, setData]           = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setFilters(f)
        if (!crop && f.commodities.length) setCrop(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!state || !commodity) return
    setLoading(true)
    setError(null)
    getPriceTrend(state, commodity)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [state, commodity])

  return (
    <div>
      <PageHeader title="Price Trend Over Time" />
      {error && <ErrorBanner message={error} />}
      <div className="flex gap-4 mb-4">
        <Select value={commodity || ''} onValueChange={setCommodity}>
          <SelectTrigger className="w-48"><SelectValue placeholder="Select commodity" /></SelectTrigger>
          <SelectContent>{filters.commodities.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {loading ? <LoadingSpinner /> : (
        <Card><CardContent className="p-4">
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={data}>
              <XAxis dataKey="period" tick={{ fontSize: 10 }} interval={3} />
              <YAxis unit="₹" />
              <Tooltip formatter={v => `₹${v}`} />
              <Legend />
              <Line type="monotone" dataKey="farm_gate_price" stroke={CHART.farmGate} name="Farm Gate ₹" dot={false} />
              <Line type="monotone" dataKey="modal_price" stroke={CHART.market} name="Market Price ₹" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent></Card>
      )}
    </div>
  )
}
```

- [ ] **Step 1: Replace the file.**
- [ ] **Step 2: Build** — `npm run build`. Expected: succeeds.
- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/PriceTrend.jsx
git commit -m "B2: re-skin PriceTrend (Select, Card, earthy lines)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Forecast

**Files:** Modify `frontend/src/pages/Forecast.jsx`

Keep ALL logic (`avail`/`state`/`commodity` state, `onStateChange`, both `useEffect`s, `splitPeriod`) identical. Change: PageHeader; two `<select>`→`Select`; `ReferenceLine` stroke → `CHART.split`; line strokes → `CHART`. Replace the file with:

```jsx
import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts'
import { getForecastAvailable, getPriceTrend, getForecast } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { CHART } from '@/lib/chartColors'

export default function Forecast() {
  const { state: ctxState } = useWorkspace()
  const [avail, setAvail]         = useState({})
  const [state, setState]         = useState('')
  const [commodity, setCommodity] = useState('')
  const [combined, setCombined]   = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  const states = Object.keys(avail)
  const commodities = avail[state] || []

  useEffect(() => {
    getForecastAvailable()
      .then(map => {
        setAvail(map)
        const states = Object.keys(map)
        const s0 = map[ctxState] ? ctxState : map['Punjab'] ? 'Punjab' : states[0] || ''
        const c0 = s0 ? (map[s0].includes('Wheat') ? 'Wheat' : map[s0][0]) : ''
        setState(s0)
        setCommodity(c0)
      })
      .catch(e => setError(e.message))
  }, [])

  const onStateChange = (s) => {
    setState(s)
    const list = avail[s] || []
    if (!list.includes(commodity)) setCommodity(list[0] || '')
  }

  useEffect(() => {
    if (!state || !commodity) return
    setLoading(true)
    setError(null)
    Promise.all([getPriceTrend(state, commodity), getForecast(state, commodity)])
      .then(([hist, forecast]) => {
        const history = hist.slice(-12).map(r => ({ ...r, is_forecast: false }))
        setCombined([...history, ...forecast])
      })
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [state, commodity])

  const splitPeriod = combined.find(r => r.is_forecast)?.period

  return (
    <div>
      <PageHeader title="Price Forecast (LSTM)"
        subtitle={`Historical (last 12 months) + 6-month LSTM prediction. Dashed line marks forecast start. Only states & crops with a trained model are listed (${states.length} states).`} />
      <div className="flex gap-4 mb-4">
        <Select value={state || ''} onValueChange={onStateChange}>
          <SelectTrigger className="w-44"><SelectValue placeholder="State" /></SelectTrigger>
          <SelectContent>{states.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={commodity || ''} onValueChange={setCommodity}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Commodity" /></SelectTrigger>
          <SelectContent>{commodities.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {error ? (
        <ErrorBanner message={error} />
      ) : loading ? <LoadingSpinner /> : (
        <Card><CardContent className="p-4">
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={combined}>
              <XAxis dataKey="period" tick={{ fontSize: 10 }} />
              <YAxis unit="₹" />
              <Tooltip formatter={v => `₹${v}`} />
              <Legend />
              {splitPeriod && <ReferenceLine x={splitPeriod} stroke={CHART.split} strokeDasharray="4 4" label="Forecast →" />}
              <Line type="monotone" dataKey="farm_gate_price" stroke={CHART.farmGate} name="Farm Gate ₹" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="modal_price" stroke={CHART.market} name="Market Price ₹" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent></Card>
      )}
    </div>
  )
}
```

- [ ] **Step 1: Replace the file.**
- [ ] **Step 2: Build** — `npm run build`. Expected: succeeds.
- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/Forecast.jsx
git commit -m "B2: re-skin Forecast (Selects, Card, earthy lines)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: ContextBar a11y nit + final verification

**Files:** Modify `frontend/src/workspace/ContextBar.jsx`

- [ ] **Step 1: Add `htmlFor`/`id` association to the Season Select.** In `ContextBar.jsx`, the Season control sits inside a `<label className="text-sm text-foreground">Season ... <Select>`. A `<label>` doesn't associate with a Radix trigger button automatically. Change the wrapping `<label>` to a `<div>` with explicit label text and add `id` to the trigger:
  - Replace `<label className="text-sm text-foreground">Season` with:
    ```jsx
    <div className="text-sm text-foreground">
      <label htmlFor="season-trigger">Season</label>
    ```
  - On the `<SelectTrigger ...>`, add `id="season-trigger"`.
  - Change the matching closing `</label>` of that block to `</div>`.
  Leave the `Select value/onValueChange`, the season options, and everything else identical.

- [ ] **Step 2: Build** — `npm run build` from `frontend/`. Expected: succeeds, no unresolved imports.

- [ ] **Step 3: Backend regression sanity.** Ensure Docker Postgres is up (`docker compose -f E:\agri-market-analyser\docker-compose.yml up -d`); from `backend/` run `venv\Scripts\python.exe -m pytest -p no:asyncio`. Expected: **179 passed** (backend untouched). If Docker is unreachable, report it and skip (acceptable — no backend change).

- [ ] **Step 4: Full in-Arc visual smoke.** Controller/human drives this in **Arc** (never Chrome) with dev servers up: visit every page across the 3 intents — 🌱 CropAdvisor, Soil Match; 💰 MandiCompare, ProfitPlanner, FPO Bulk Selling (the deferred FPO click-through); 📊 StateMap, CropAnalyser, RevenueLoss, PriceTrend, Forecast. Confirm: earthy palette + primitives throughout, Selects/Inputs/Buttons/Tables work, charts/map render with earthy colors, no console errors, no behavior regressions.

- [ ] **Step 5: Commit the a11y fix.**
```bash
git add frontend/src/workspace/ContextBar.jsx
git commit -m "B2: associate ContextBar Season label with Select trigger (a11y)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done criteria (from spec §5)
- Every tool page renders and functions identically to pre-B2 (same data/controls/results/routes).
- All 10 pages use shadcn primitives + tokens; no hardcoded `green-*`/`gray-*` left on the tool pages (only intentional earthy hex in `chartColors.js`).
- `npm run build` green; backend pytest 179 green; no console errors in the Arc smoke.
- Branch `feat/tool-page-reskin` holds the spec commit + task commits. **Not pushed** — bundled with the rest of Phase B per the standing user decision.
