# UI Foundation + Shell Migration (Phase B1) — Design

**Date:** 2026-06-03
**Status:** Approved (brainstorm complete; awaiting spec review → implementation plan)
**Branch:** `feat/ui-foundation-shell` (proposed)
**Parent effort:** Phase B — UI/UX redesign (`claude_ui_ux_switch_prompt.md`), decomposed into **B1 Foundation+shell → B2 tool-page re-skin → B3 Smart-mode dashboard landing → B4 Reports/Export PDF**. This spec covers **B1 only**.

## 1. Goal, Scope, and Non-Goals

### What it is
B1 lays the **design-system foundation** for the whole Phase B redesign and migrates **only the application shell** to it. It introduces shadcn/ui into the existing Vite app, a CSS-variable design-token layer (the "Earthy agri" palette), a canonical primitive set, and re-skins the shell chrome — header, context bar, intent navigation, tool sub-tabs, mode toggle, and the two shared atoms.

### Who benefits
Every later sub-phase (B2–B4) builds on these tokens and primitives instead of hardcoded `green-800` utility strings, so the redesign becomes a consistent re-skin rather than per-page ad-hoc styling. The user immediately sees a cohesive, warmer agricultural look across the shell.

### The honest core
B1 is a **purely presentational migration**. It changes how the shell *looks*, never what it *does*. Every intent, tool, deep-link, route, prop, and piece of state behaves identically before and after. The diff is confined to: token definitions, dependency additions, build-config aliasing, and className/element-type swaps (raw `<button>`/`<select>` → shadcn primitives, hardcoded `green-*`/`gray-*` → token classes).

### Non-goals (explicitly deferred)
- **No tool-page logic or field-level re-skin** — `CropAdvisor`, `MandiCompare`, `ProfitPlanner`, `FpoBulkDashboard`, `StateMap`, etc. keep their current internals. Deep field-level shadcn adoption is **B2**.
- **No Smart-mode dashboard landing** — that's **B3**.
- **No Reports/Export PDF** — that's **B4**.
- **No dark mode in B1** — tokens are *structured* so a `.dark {}` block is a later drop-in, but no dark theme ships now.
- **No 21st.dev Magic MCP** — canonical shadcn components only for the foundation; Magic is a candidate for richer B2/B3 compositions.
- **No Tailwind major-version bump, no Vite/React swap.**
- **No backend changes** — the 179-test pytest suite is untouched.

## 2. Locked Decisions (from brainstorm)

1. **Approach A** — stay on **Tailwind v3.4.19** + adopt **shadcn/ui** (CLI-style setup, canonical primitives, CSS-variable tokens). *(Rejected: B = upgrade to Tailwind v4 — too much churn for B1; C = hand-rolled components — fights the adopt-shadcn goal.)*
2. **Palette = Earthy agri** — green-700 primary, warm stone-50 / amber-tinted surfaces, stone-800 text, amber/clay accents.
3. **Shell = re-skin the current top-nav** — keep the header + horizontal intent tabs + tool sub-tabs structure. **Not** a sidebar.
4. **Light theme only in B1**; tokens structured for future dark-mode drop-in.
5. **Canonical shadcn components** for the foundation (not Magic MCP).

## 3. Architecture & Dependencies

shadcn/ui is **not** a runtime dependency — it copies component source into the repo, which we then own and restyle via tokens. Setup:

```
npm i class-variance-authority clsx tailwind-merge tailwindcss-animate lucide-react
npm i @radix-ui/react-tabs @radix-ui/react-select @radix-ui/react-dialog @radix-ui/react-slot
```

- **`frontend/components.json`** — shadcn config: style `default`, `rsc: false`, `tsx: false` (this is a JS/JSX project), baseColor **`stone`** (warm-gray family matching the earthy palette; our CSS-var tokens override actual colors, `stone` only governs any un-tokened defaults), aliases `components → @/components`, `utils → @/lib/utils`, `ui → @/components/ui`.
- **Path alias `@` → `src`** added to **both** `frontend/vite.config.js` (`resolve.alias`) and `frontend/jsconfig.json` (`compilerOptions.paths`), so shadcn's `@/components/ui/...` import convention resolves. *This is the only pre-existing build wiring B1 touches.*
- **`frontend/src/lib/utils.js`** — exports `cn(...)` = `twMerge(clsx(inputs))`.
- **`frontend/src/components/ui/`** — new folder holding the primitives.

No build-tool swap. Vite 8 + React 19 unchanged.

## 4. Token Layer (CSS variables → Tailwind)

`frontend/src/index.css` gains a `:root` block of **HSL channel triplets** (shadcn convention — bare `H S% L%` values, no `hsl()` wrapper, so Tailwind can apply opacity modifiers). Earthy agri palette:

```css
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
```

Plus an `@layer base` that applies `bg-background text-foreground` to `body` and a default `border-border`.

`frontend/tailwind.config.js` `theme.extend` maps each token: `colors.primary: 'hsl(var(--primary) / <alpha-value>)'`, …for background/foreground/card/popover/primary/secondary/muted/accent/destructive/border/input/ring; `borderRadius.{lg,md,sm}` derived from `--radius`; add the `tailwindcss-animate` plugin and `darkMode: ["class"]`. **No `.dark {}` block ships in B1.**

## 5. Primitive Set

Seven canonical shadcn primitives copied into `frontend/src/components/ui/`, automatically restyled by the tokens above:

| Primitive | Shell usage in B1 |
|---|---|
| `button.jsx` | nav/action buttons → `variant` `ghost`/`secondary`/`default` |
| `tabs.jsx` | primitive ships now for B2/B3. For the shell nav itself, prefer keeping the existing `<button>` map restyled with token classes + `cn()` (lower-risk, fully behavior-preserving) over forcing `Tabs`, since the active tool renders in `<main>` not in `TabsContent`. Final call is a plan-time decision. |
| `select.jsx` | ContextBar Season select |
| `input.jsx` | primitive lands now; broad field adoption is B2 |
| `card.jsx` | shell surface / `<main>` container framing |
| `dialog.jsx` | primitive only (future LocationPicker map modal) — **not wired in B1** |
| `badge.jsx` | mode/status chips |

The two shared atoms are **re-skinned to tokens, not replaced**:
- `frontend/src/components/ErrorBanner.jsx` → token `destructive`/`destructive-foreground` colors.
- `frontend/src/components/LoadingSpinner.jsx` → token `primary` color.

## 6. Shell Migration (file-by-file, behavior-preserving)

| File | Change |
|---|---|
| `frontend/src/index.css` | add token `:root` + `@layer base` defaults |
| `frontend/tailwind.config.js` | token color map, radius, `tailwindcss-animate`, `darkMode:["class"]` |
| `frontend/vite.config.js`, `frontend/jsconfig.json` | `@` → `src` path alias |
| `frontend/components.json`, `frontend/src/lib/utils.js` | new (shadcn config + `cn()`) |
| `frontend/src/components/ui/*` | new primitives (Section 5) |
| `frontend/src/workspace/Workspace.jsx` | header `bg-green-800`→`bg-primary text-primary-foreground`; intent `<nav>` + tool sub-tab row → shadcn `Tabs`; all `green-*`/`gray-*` → `primary`/`muted-foreground`/`border`. **No change to `INTENTS`, tool wiring, `initialIntent`/`initialTool`, or state.** |
| `frontend/src/workspace/ContextBar.jsx` | `<select>`→shadcn `Select`; `bg-white border-b`→`bg-card border-border`; label/season colors → tokens. Logic, `useWorkspace`, soil-panel toggle untouched. |
| `frontend/src/workspace/ModeToggle.jsx` | keep the custom switch (it works well); recolor `green-*`→`primary`/`muted`. ARIA/behavior unchanged. |
| `frontend/src/workspace/{LocationPicker,SoilPanel,CropPicker}.jsx` | **token recolor only** — structure/logic untouched (field-level shadcn = B2) |
| `frontend/src/components/{ErrorBanner,LoadingSpinner}.jsx` | recolor to tokens |
| `frontend/src/App.jsx` | no logic change; verify token background applies app-wide |

**Hard rule for B1:** zero behavior/prop/routing/state changes. Every intent, tool, sub-tab, deep-link (`DEEP_LINKS`), and Simple/Smart toggle works identically. The diff is purely className + element-type (raw → primitive) swaps.

## 7. Testing & Verification

- **Build gate:** `npm run build` from `frontend/` must be clean (catches alias/import breakage from the `@` resolution).
- **Backend regression sanity:** backend is untouched, but run `venv\Scripts\python.exe -m pytest -p no:asyncio` from `backend/` once to confirm 179 green.
- **Visual smoke in ARC** (locked preference — **not** Chrome; point Playwright MCP at Arc): click through all 3 intents + every sub-tab, toggle Simple/Smart, expand Soil details (Smart mode), confirm tokens render and no layout regressions.
- **Acceptance criteria:**
  - Identical functionality to pre-B1 (all intents/tools/deep-links/mode toggle work).
  - New earthy-agri look applied across the shell via tokens (no hardcoded `green-*` left in migrated shell files).
  - No console errors; `npm run build` green; pytest 179 green.

## 8. Out-of-Scope / Follow-on (recorded, not built in B1)
- **B2** — tool-page field-level re-skin (incl. deferred FPO in-browser Arc smoke), deeper shadcn adoption in `LocationPicker`/`CropPicker`/`SoilPanel` and all tool pages.
- **B3** — Smart-mode dashboard landing.
- **B4** — Reports/Export PDF (also satisfies the policy-brief-PDF PM-CV idea).
- **Dark mode** — drop in a `.dark {}` token block when desired.
- **Push** — the held FPO commit (`7575a07`) + the B1/Phase-B commits are pushed to `origin/master` together **only after Phase B lands** (standing user decision).
