# UI Foundation + Shell Migration (Phase B1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt shadcn/ui + an earthy-agri CSS-variable token layer on the existing Tailwind v3 + Vite frontend, and re-skin the application shell to it without changing any behavior.

**Architecture:** shadcn/ui copies component source into `frontend/src/components/ui/` (we own it). A `:root` block of HSL design tokens in `index.css` is mapped into `tailwind.config.js` `theme.extend`, so utility classes like `bg-primary` resolve to the earthy palette. The shell components (`Workspace`, `ContextBar`, `ModeToggle`, the location/soil/crop pickers, and the shared `ErrorBanner`/`LoadingSpinner` atoms) are migrated from hardcoded `green-*`/`gray-*` utilities to token classes and shadcn primitives. **Zero behavior/prop/routing/state changes** — the diff is purely className + element-type swaps.

**Tech Stack:** Vite 8, React 19, Tailwind v3.4.19, shadcn/ui (canonical), Radix primitives, class-variance-authority, clsx, tailwind-merge, tailwindcss-animate, lucide-react.

**Testing approach:** This frontend has no unit-test runner, and the spec scopes B1 as a presentational migration (adding vitest is out of scope). The verification gate for every task is a clean `npm run build` plus a behavior-preservation check; a final task runs the backend pytest regression sanity check and an in-**Arc** visual smoke (per the locked browser-testing preference — never Chrome).

**Working directory note:** all `npm`/`git` commands below assume you are in `E:\agri-market-analyser`. Run frontend commands from `E:\agri-market-analyser\frontend`. The branch `feat/ui-foundation-shell` already exists and already contains the design-spec commit (`c9d2b37`).

**Commit rule:** Use targeted `git add <paths>` only — NEVER `git add -A`/`.`/`-u`. NEVER stage the large CSVs or `data/agri.db`. Every commit ends with the trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Do NOT push.

---

## File Structure

**Created:**
- `frontend/src/lib/utils.js` — `cn()` helper (clsx + tailwind-merge).
- `frontend/components.json` — shadcn config.
- `frontend/src/components/ui/{button,card,badge,input,select,tabs,dialog}.jsx` — canonical primitives (fetched via shadcn CLI).

**Modified:**
- `frontend/package.json` / `package-lock.json` — new deps (via `npm i`).
- `frontend/vite.config.js` — `@` → `src` resolve alias.
- `frontend/jsconfig.json` — create with `@` path mapping (does not exist yet).
- `frontend/src/index.css` — token `:root` block + `@layer base` defaults.
- `frontend/tailwind.config.js` — map tokens into `theme.extend`, radius, animate plugin, `darkMode:["class"]`.
- `frontend/src/components/ErrorBanner.jsx`, `LoadingSpinner.jsx` — recolor to tokens.
- `frontend/src/workspace/Workspace.jsx` — header + nav + sub-tabs re-skin.
- `frontend/src/workspace/ContextBar.jsx` — `<select>` → shadcn `Select`, token colors.
- `frontend/src/workspace/ModeToggle.jsx` — recolor.
- `frontend/src/workspace/{LocationPicker,SoilPanel,CropPicker}.jsx` — token recolor only.
- `frontend/src/App.jsx` — verify token background applies (likely no edit needed).

---

## Task 1: Dependencies, path alias, and `cn()` helper

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json` (via npm)
- Modify: `frontend/vite.config.js`
- Create: `frontend/jsconfig.json`
- Create: `frontend/src/lib/utils.js`

- [ ] **Step 1: Install runtime + Radix dependencies**

Run (from `frontend/`):
```bash
npm i class-variance-authority clsx tailwind-merge tailwindcss-animate lucide-react @radix-ui/react-tabs @radix-ui/react-select @radix-ui/react-dialog @radix-ui/react-slot
```
Expected: installs complete, no peer-dep errors that block (React 19 peer warnings are acceptable).

- [ ] **Step 2: Add the `@` → `src` alias to Vite**

Replace `frontend/vite.config.js` with:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
})
```

- [ ] **Step 3: Create `frontend/jsconfig.json` so editors/shadcn resolve `@`**

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create the `cn()` helper**

Create `frontend/src/lib/utils.js`:
```js
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 5: Verify the build is still clean**

Run (from `frontend/`): `npm run build`
Expected: build succeeds (the new alias and deps don't break anything; nothing imports them yet).

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/jsconfig.json frontend/src/lib/utils.js
git commit -m "B1: add shadcn deps, @ path alias, and cn() helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Earthy-agri token layer

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/tailwind.config.js`

- [ ] **Step 1: Add tokens + base layer to `index.css`**

Replace `frontend/src/index.css` with:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 40 33% 97%;       /* warm stone-50 */
    --foreground: 30 12% 16%;       /* stone-800 text */
    --card: 0 0% 100%;
    --card-foreground: 30 12% 16%;
    --popover: 0 0% 100%;
    --popover-foreground: 30 12% 16%;
    --primary: 142 40% 30%;         /* green-700 */
    --primary-foreground: 40 33% 97%;
    --secondary: 36 40% 92%;        /* amber-tinted surface */
    --secondary-foreground: 30 12% 16%;
    --muted: 36 20% 90%;
    --muted-foreground: 30 8% 42%;
    --accent: 32 80% 50%;           /* amber/clay accent */
    --accent-foreground: 30 12% 16%;
    --destructive: 0 72% 45%;
    --destructive-foreground: 40 33% 97%;
    --border: 30 14% 86%;
    --input: 30 14% 86%;
    --ring: 142 40% 30%;
    --radius: 0.5rem;
  }

  * {
    border-color: hsl(var(--border));
  }

  body {
    background-color: hsl(var(--background));
    color: hsl(var(--foreground));
  }
}
```
Note: no `.dark {}` block ships in B1 — tokens are structured so it's a later drop-in.

- [ ] **Step 2: Map tokens into Tailwind**

Replace `frontend/tailwind.config.js` with:
```js
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border) / <alpha-value>)",
        input: "hsl(var(--input) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        primary: {
          DEFAULT: "hsl(var(--primary) / <alpha-value>)",
          foreground: "hsl(var(--primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary) / <alpha-value>)",
          foreground: "hsl(var(--secondary-foreground) / <alpha-value>)",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive) / <alpha-value>)",
          foreground: "hsl(var(--destructive-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT: "hsl(var(--muted) / <alpha-value>)",
          foreground: "hsl(var(--muted-foreground) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          foreground: "hsl(var(--accent-foreground) / <alpha-value>)",
        },
        popover: {
          DEFAULT: "hsl(var(--popover) / <alpha-value>)",
          foreground: "hsl(var(--popover-foreground) / <alpha-value>)",
        },
        card: {
          DEFAULT: "hsl(var(--card) / <alpha-value>)",
          foreground: "hsl(var(--card-foreground) / <alpha-value>)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
```
Note: `require(...)` works here because PostCSS/Tailwind config is loaded in a CommonJS-capable context even with `"type":"module"`; Tailwind resolves the plugin. If the build errors on `require`, change to an import at top: `import tailwindcssAnimate from "tailwindcss-animate"` and `plugins: [tailwindcssAnimate]`.

- [ ] **Step 3: Verify build + tokens compile**

Run (from `frontend/`): `npm run build`
Expected: build succeeds. (If it fails on the `require`, apply the import fallback in Step 2's note, then re-run.)

- [ ] **Step 4: Quick visual confirm the background changed**

Run (from `frontend/`): `npm run dev`, open the app in **Arc** at `http://localhost:5173`.
Expected: page background is now a warm stone tone (not pure white). Stop the dev server after confirming.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css frontend/tailwind.config.js
git commit -m "B1: add earthy-agri CSS-variable token layer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Canonical shadcn primitives + components.json

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/src/components/ui/{button,card,badge,input,select,tabs,dialog}.jsx`

- [ ] **Step 1: Create `frontend/components.json`**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": false,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/index.css",
    "baseColor": "stone",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui"
  }
}
```

- [ ] **Step 2: Fetch the canonical primitives via the shadcn CLI (non-interactive)**

Run (from `frontend/`):
```bash
npx --yes shadcn@latest add button card badge input select tabs dialog --yes --overwrite
```
Expected: creates `src/components/ui/button.jsx`, `card.jsx`, `badge.jsx`, `input.jsx`, `select.jsx`, `tabs.jsx`, `dialog.jsx`. The CLI reads `components.json`, writes JSX (because `tsx:false`), and uses our token classes (because `cssVariables:true`). It may also confirm Radix deps are installed (already added in Task 1).

- [ ] **Step 3: Fallback if the CLI is unavailable/offline**

Only if Step 2 fails: manually create the seven files using the canonical shadcn JSX source for the "default" style from https://ui.shadcn.com/docs/components (button, card, badge, input, select, tabs, dialog), with imports rewritten to `@/lib/utils`. Each must import `cn` from `@/lib/utils` and use token classes (`bg-primary`, `border-input`, `bg-popover`, etc.). Do not invent variants — copy the canonical source verbatim.

- [ ] **Step 4: Smoke-import the primitives so the build type-checks them**

Temporarily verify by building (the files are valid even if unused). Run (from `frontend/`): `npm run build`
Expected: build succeeds with the new primitive files present in the tree.

- [ ] **Step 5: Commit**

```bash
git add frontend/components.json frontend/src/components/ui
git commit -m "B1: add canonical shadcn primitives (button, card, badge, input, select, tabs, dialog)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Re-skin shared atoms to tokens

**Files:**
- Modify: `frontend/src/components/ErrorBanner.jsx`
- Modify: `frontend/src/components/LoadingSpinner.jsx`

- [ ] **Step 1: Recolor `ErrorBanner.jsx` to destructive tokens**

Replace `frontend/src/components/ErrorBanner.jsx` with:
```jsx
export default function ErrorBanner({ message }) {
  return (
    <div className="bg-destructive/10 text-destructive border border-destructive/30 p-4 rounded-md m-4">
      {message}
    </div>
  )
}
```

- [ ] **Step 2: Recolor `LoadingSpinner.jsx` to primary token**

Replace `frontend/src/components/LoadingSpinner.jsx` with:
```jsx
export default function LoadingSpinner() {
  return <div className="flex justify-center py-20 text-primary text-lg">Loading...</div>
}
```

- [ ] **Step 3: Verify build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ErrorBanner.jsx frontend/src/components/LoadingSpinner.jsx
git commit -m "B1: re-skin ErrorBanner and LoadingSpinner to tokens

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Migrate the Workspace shell (header, intent nav, tool sub-tabs)

**Files:**
- Modify: `frontend/src/workspace/Workspace.jsx`

Behavior rule: the `INTENTS` array, all tool imports/wiring, `initialIntent`/`initialTool` props, `pickIntent`, and all state stay **byte-identical**. Only the JSX chrome (header + nav + sub-tab `<div>` + `<main>`) changes className/colors. Keep the nav as restyled `<button>` elements (per spec self-review decision #2 — do NOT force the `Tabs` primitive here, since the active tool renders in `<main>`, not in `TabsContent`).

- [ ] **Step 1: Re-skin the shell JSX**

In `frontend/src/workspace/Workspace.jsx`, replace the `return (...)` block (currently lines ~51-79) with:
```jsx
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="bg-primary text-primary-foreground px-4 md:px-6 py-3 flex items-center justify-between">
        <span className="font-bold">🌾 Agri Market Analyser</span>
        <ModeToggle />
      </header>

      <ContextBar states={states} />

      <nav className="flex gap-2 px-4 md:px-6 pt-3 flex-wrap">
        {INTENTS.map((i) => (
          <button key={i.id} onClick={() => pickIntent(i.id)}
            className={`px-3 py-2 rounded-t-lg text-sm font-medium transition-colors ${i.id === intentId ? 'bg-card border border-b-0 border-border text-primary' : 'bg-secondary text-secondary-foreground hover:bg-muted'}`}>
            {i.label}
          </button>
        ))}
      </nav>
      <div className="flex gap-3 px-4 md:px-6 border-b border-border text-sm">
        {intent.tools.map((t) => (
          <button key={t.id} onClick={() => setToolId(t.id)}
            className={`py-2 transition-colors ${t.id === toolId ? 'text-primary font-semibold border-b-2 border-primary' : 'text-muted-foreground hover:text-primary'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <main className="p-6 flex-1"><Tool /></main>
    </div>
  )
```
Leave everything above the `return` (imports, `INTENTS`, the component's state/handlers) exactly as-is.

- [ ] **Step 2: Verify build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 3: Behavior-preservation check**

Run (from `frontend/`): `npm run dev`, open in **Arc**. Confirm: header is green (primary) with the mode toggle; all three intent tabs switch and reset to their first tool; every sub-tab renders its tool; no console errors. Stop the dev server.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/workspace/Workspace.jsx
git commit -m "B1: re-skin Workspace shell (header, intent nav, tool sub-tabs) to tokens

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Migrate ContextBar (Season → shadcn Select, token colors)

**Files:**
- Modify: `frontend/src/workspace/ContextBar.jsx`

Behavior rule: `useWorkspace`, `season`/`setSeason`, the `mode === 'smart'` soil toggle, and `LocationPicker`/`CropPicker`/`SoilPanel` usage stay identical. Only the wrapper colors and the Season control change.

- [ ] **Step 1: Swap the native `<select>` for shadcn Select and recolor the wrapper**

Replace `frontend/src/workspace/ContextBar.jsx` with:
```jsx
import { useState } from 'react'
import { useWorkspace } from './WorkspaceContext'
import LocationPicker from './LocationPicker'
import SoilPanel from './SoilPanel'
import CropPicker from './CropPicker'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'

const SEASONS = ['Any', 'Kharif', 'Rabi', 'Summer', 'Winter', 'Autumn', 'Whole Year']

export default function ContextBar({ states }) {
  const { season, setSeason, mode } = useWorkspace()
  const [showSoil, setShowSoil] = useState(false)
  return (
    <div className="bg-card border-b border-border px-4 md:px-6 py-3">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <LocationPicker states={states} />
        <CropPicker />
        <label className="text-sm text-foreground">Season
          <Select value={season} onValueChange={setSeason}>
            <SelectTrigger className="mt-1 w-40">
              <SelectValue placeholder="Season" />
            </SelectTrigger>
            <SelectContent>
              {SEASONS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </label>
        {mode === 'smart' && (
          <button type="button" onClick={() => setShowSoil((v) => !v)}
            className="text-sm text-primary hover:text-primary/80 pb-2">
            {showSoil ? '▾' : '▸'} Soil details
          </button>
        )}
      </div>
      {mode === 'smart' && showSoil && <SoilPanel />}
    </div>
  )
}
```
Note: shadcn `Select` is controlled via `value`/`onValueChange` (not `onChange`), and `SelectItem` requires a non-empty string `value` — all seven season values are non-empty, so this is safe.

- [ ] **Step 2: Verify build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 3: Behavior-preservation check**

Run (from `frontend/`): `npm run dev`, open in **Arc**. Confirm: the Season dropdown opens, selecting a season updates state (and any season-dependent tool reflects it), the context bar surface is white-on-stone with a token border. Stop the dev server.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/workspace/ContextBar.jsx
git commit -m "B1: migrate ContextBar Season to shadcn Select and token colors

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Recolor ModeToggle and the location/soil/crop pickers

**Files:**
- Modify: `frontend/src/workspace/ModeToggle.jsx`
- Modify: `frontend/src/workspace/LocationPicker.jsx`
- Modify: `frontend/src/workspace/SoilPanel.jsx`
- Modify: `frontend/src/workspace/CropPicker.jsx`

Behavior rule: recolor only. No structural, prop, state, or logic changes in any of these files.

- [ ] **Step 1: Recolor `ModeToggle.jsx`**

Replace `frontend/src/workspace/ModeToggle.jsx` with:
```jsx
import { useWorkspace } from './WorkspaceContext'

export default function ModeToggle() {
  const { mode, setMode } = useWorkspace()
  const smart = mode === 'smart'
  return (
    <label className="flex items-center gap-2 text-sm select-none">
      <span className={smart ? 'opacity-70' : 'font-semibold'}>Simple</span>
      <button type="button" role="switch" aria-checked={smart} aria-label="Toggle Smart mode"
        onClick={() => setMode(smart ? 'simple' : 'smart')}
        className={`relative w-10 h-5 rounded-full transition ${smart ? 'bg-primary-foreground/40' : 'bg-primary-foreground/20'}`}>
        <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all ${smart ? 'left-5' : 'left-0.5'}`} />
      </button>
      <span className={smart ? 'font-semibold' : 'opacity-70'}>Smart</span>
    </label>
  )
}
```
Note: the toggle sits in the green (`bg-primary`) header, so its track uses `primary-foreground` opacity tints to stay legible on the dark header; the knob stays white.

- [ ] **Step 2: Recolor the three pickers — find-and-replace token mapping**

In each of `frontend/src/workspace/LocationPicker.jsx`, `SoilPanel.jsx`, and `CropPicker.jsx`, apply ONLY these className substitutions (leave all JSX structure, props, hooks, and logic untouched):

| Old class | New class |
|---|---|
| `text-green-700`, `text-green-800`, `text-green-900` | `text-primary` |
| `bg-green-700`, `bg-green-800` | `bg-primary` (text on it → `text-primary-foreground`) |
| `bg-green-50`, `bg-green-100` | `bg-secondary` |
| `border-green-*` | `border-primary` |
| `hover:bg-green-100` | `hover:bg-muted` |
| `hover:text-green-900` | `hover:text-primary/80` |
| `text-gray-500`, `text-gray-600` | `text-muted-foreground` |
| `text-gray-700`, `text-gray-800` | `text-foreground` |
| `bg-white` | `bg-card` |
| `border` / `border-gray-*` (default gray borders) | `border border-border` |
| `bg-red-100` / `text-red-700` (inline errors) | `bg-destructive/10` / `text-destructive` |

If a file contains no `green-`/`gray-`/`red-`/`bg-white` classes, leave it unchanged. Do not add or remove elements.

- [ ] **Step 3: Verify build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 4: Behavior-preservation check**

Run (from `frontend/`): `npm run dev`, open in **Arc**. Confirm: Simple/Smart toggle still flips and the track is legible on the green header; LocationPicker (pincode/GPS/dropdown), CropPicker, and (in Smart mode) the Soil details panel all render and function with the earthy palette. Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/workspace/ModeToggle.jsx frontend/src/workspace/LocationPicker.jsx frontend/src/workspace/SoilPanel.jsx frontend/src/workspace/CropPicker.jsx
git commit -m "B1: recolor ModeToggle and location/soil/crop pickers to tokens

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Final verification (build, App check, pytest regression, Arc smoke)

**Files:**
- Modify (only if needed): `frontend/src/App.jsx`

- [ ] **Step 1: Confirm `App.jsx` needs no change**

Read `frontend/src/App.jsx`. The token background is applied via `body` (Task 2) and the Workspace root `bg-background` (Task 5). If `App.jsx` hardcodes a conflicting background (e.g. `bg-white`/`bg-gray-*` on a wrapping element), recolor it to `bg-background`; otherwise leave it untouched.

- [ ] **Step 2: Clean production build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds, no errors, no unresolved `@/...` imports.

- [ ] **Step 3: Backend regression sanity check**

Ensure Docker Postgres is up (`docker compose -f E:\agri-market-analyser\docker-compose.yml up -d`), then run (from `backend/`):
```bash
venv\Scripts\python.exe -m pytest -p no:asyncio
```
Expected: 179 passed (backend is untouched; this confirms no accidental cross-impact).

- [ ] **Step 4: Full in-Arc visual smoke**

Run (from `frontend/`): `npm run dev`. In **Arc** (point Playwright MCP at Arc; never Chrome), click through: all 3 intents (Grow/Sell/Explore) × every sub-tab; toggle Simple↔Smart; expand Soil details in Smart mode; exercise the FPO Bulk Selling tab under 💰 Sell (the deferred FPO in-browser smoke). Confirm: earthy palette throughout, no layout regressions, no console errors. Stop the dev server.

- [ ] **Step 5: Final commit (only if App.jsx changed in Step 1)**

```bash
git add frontend/src/App.jsx
git commit -m "B1: apply token background at App root

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
If `App.jsx` was unchanged, skip this commit.

---

## Done criteria (from spec §7)
- Identical functionality to pre-B1: every intent, tool, sub-tab, deep-link, and Simple/Smart toggle works.
- New earthy-agri look applied across the shell via tokens; no hardcoded `green-*` left in the migrated shell files.
- No console errors; `npm run build` green; backend pytest 179 green.
- B1 branch `feat/ui-foundation-shell` holds the spec commit + the task commits. **Not pushed** — push happens with the rest of Phase B per the standing user decision.
