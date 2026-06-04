# Design

Visual system for **Crop Analyser** — "Warm Editorial Agritech". Register: product (see [PRODUCT.md](PRODUCT.md)). Light mode only for now; dark mode is a future drop-in (tokens are structured for it, no `.dark{}` block yet).

This supersedes the Phase B1 token layer in `frontend/src/index.css`. Migration notes are inline per token.

## Theme

A farm-to-market decision tool that reads like a respected publication on Indian agriculture, not a dashboard. Warmth is carried by a **clay accent, serif headlines, and imagery** — never by tinting the body. The body is true paper-off-white so dense data stays high-contrast and scannable, and so the UI sheds the warm-cream "AI-default" read of the previous build. Color strategy: **Restrained** (tinted-neutral surfaces + green primary + clay accent ≤10% of surface).

## Color

Tokens as HSL CSS variables (shadcn convention: space-separated, no `hsl()` wrapper) in `:root`. Hex shown for reference.

| Token | Hex | HSL (`--var`) | Role | vs B1 |
|---|---|---|---|---|
| `--background` | `#FDFDFC` | `60 14% 99%` | Body — true paper off-white | **changed** from warm cream `40 33% 97%` |
| `--foreground` | `#2A2724` | `30 8% 15%` | Ink: headlines + body | darkened from `30 12% 16%` for contrast |
| `--primary` | `#2E6B43` | `142 40% 30%` | Deep green: primary actions, advisor, positive | unchanged |
| `--primary-foreground` | `#FDFDFC` | `60 14% 99%` | Text on green | — |
| `--accent` | `#B5611F` | `26 65% 42%` | Clay: accent + **key numbers** (prices, yields) | brightened from `28 72% 34%` |
| `--accent-foreground` | `#FFFFFF` | `0 0% 100%` | Text on clay | — |
| `--secondary` / panel | `#F4F1EC` | `38 26% 94%` | Warm-stone: context bar, sidebars, table headers | from `36 40% 92%` |
| `--card` | `#FFFFFF` | `0 0% 100%` | Raised content | unchanged |
| `--muted` | `#F4F1EC` | `38 26% 94%` | Muted surface | — |
| `--muted-foreground` | `#6B655C` | `36 8% 39%` | Secondary text (AA on paper) | darkened from `30 8% 42%` |
| `--border` / `--input` | `#E6E1D8` | `39 24% 87%` | Warm hairline | from `30 14% 86%` |
| `--ring` | `#2E6B43` | `142 40% 30%` | Focus ring | unchanged |
| `--destructive` | `#B3261E` | `3 71% 41%` | Errors / revenue loss | — |
| `--destructive-foreground` | `#FDFDFC` | `60 14% 99%` | — | — |
| `--radius` | — | `0.5rem` | — | unchanged |

Semantic mapping: **positive/grown/traditional → primary green**; **key figures + accents → clay**; **loss/error → destructive**; **forecast vs recent tags** distinguished by label + a muted vs accent treatment, never color alone. Accent on inactive states is forbidden (no full-saturation on disabled).

Contrast (verified targets): ink `#2A2724` on paper `#FDFDFC` ≈ 13:1; muted `#6B655C` on paper ≈ 5.0:1 (AA body); white on green `#2E6B43` ≈ 5.1:1; white on clay `#B5611F` ≈ 4.6:1. Placeholders use `--muted-foreground`, not a lighter gray.

## Typography

Two families on a contrast axis (serif display + humanist sans). No third family except optional needs.

- **Display / headings:** **Fraunces** (variable; warm characterful serif), weights 400 + 600, optical sizing on, `text-wrap: balance` on h1–h3. Heading clamp max ≈ 3.5rem; letter-spacing ≥ -0.02em.
- **Body / UI / labels / data:** **Inter**, weights 400/500/600. Prose capped 65–75ch; tables may run denser.
- **All figures:** `font-variant-numeric: tabular-nums` so price/yield columns align and scan.
- Load via Google Fonts `<link>` (not `next/font`). Self-host later if perf needs it.
- Scale: fixed rem (product register), ratio ~1.25. No all-caps body. No tracked-uppercase eyebrow above every section.

Suggested stack:
```css
--font-display: "Fraunces", Georgia, serif;
--font-sans: "Inter", system-ui, -apple-system, sans-serif;
```

## Layout & Spacing

- 8px base spacing rhythm; vary spacing for editorial rhythm (generous around headlines, tight within data).
- Content max-width ~1100px for tool pages; landing sections can go wider.
- Flexbox for 1D, Grid for 2D. Responsive grids without breakpoints: `repeat(auto-fit, minmax(280px, 1fr))`.
- Cards used only when they're the right affordance (raised content over panel); **no nested cards**.
- Two-layer surface: paper `--background` body, warm-stone `--secondary` for the context bar / table headers / sidebars; white `--card` for lifted content.
- Semantic z-index scale: dropdown → sticky → modal-backdrop → modal → toast → tooltip. No arbitrary 9999.

## Shape

Radius `0.5rem` default; inputs/buttons share it. Hairline borders `--border`; **no side-stripe accent borders** (full borders, bg tints, or leading icons/numbers instead).

## Iconography

`lucide-react` (already a dep), single consistent stroke weight. Icons support labels, never replace them as the sole signal.

## Components

From the tokens above; reuse the existing `frontend/src/components/ui/*` shadcn primitives (button, card, badge, input, select, tabs, dialog) and extend with **Table** + **Skeleton**. Every interactive element ships: default / hover / focus / active / disabled / loading. Data screens ship empty + loading (skeleton, not spinner) + error states.

- **Button:** primary (green), secondary (warm-stone outline), ghost; loading spinner inline.
- **Badge:** "traditional" (green), tag/forecast (muted), caution (destructive-tinted).
- **Table:** warm-stone header, tabular-nums body, optional zebra, one highlighted "best" row.
- **Context bar:** sticky, warm-stone, pincode input + GPS button + season Select + Simple/Smart segmented toggle.

## Motion

`framer-motion` (the `motion` lib). State-driven only — 150–250ms, ease-out (quart/quint), no bounce/elastic. Stagger list rows on first reveal (the advisor results). Reveals enhance already-visible content (no visibility gated on transitions). Every animation has a `@media (prefers-reduced-motion: reduce)` crossfade/instant fallback. No page-load choreography on tool screens.

## Imagery

Editorial, documentary photography of Indian farms/markets/produce where used (landing, section breaks). Warm, real, not stock-cheerful. Optional; the system reads complete without imagery.

## Signature screens

1. **Landing** — serif headline stating the decision the tool makes, plainspoken subhead, one CTA "Open the analyser", quiet Grow/Sell/Explore explainer. No gradient hero, no icon-card grid.
2. **Workspace shell** — context bar + three intent tabs (🌱 Grow / 💰 Sell / 📊 Explore) + content.
3. **CropAdvisor "What to grow"** — ranked rows, tradition badge first, yield + trend arrow + "was ~X" anchor, clay tabular ₹/q price tagged (forecast)/(recent), expandable why, honest low-confidence state.
4. **Mandi comparison** — dense table Market | Distance | Modal ₹/q | Net ₹/q, tabular-nums, best row highlighted, honest "sell locally" banner, skeleton + empty states.

## Accessibility

WCAG AA (see PRODUCT.md). Tabular-nums on all data, reduced-motion fallbacks, mobile-first ≥44px touch targets, color never the sole signal, focus-visible rings on `--ring`.

## Anti-references (do not produce)

Gradient text, tracked-uppercase eyebrows on every section, identical icon+heading+text card grids, hero-metric template, glassmorphism-by-default, side-stripe accent borders, cartoon mascots, warm-cream/beige body.
