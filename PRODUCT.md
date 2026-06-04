# Product

## Register

product

## Users

Two audiences, both primary (the product must serve both without forking the codebase):

**1. Decision-makers in the field — Indian smallholder farmers and FPO (Farmer Producer Organisation) managers.**
Low-to-mid digital fluency, mobile-first, often on low-end Android over patchy rural connectivity. Their context is a real decision with money on the line: *what should I grow this season? where and when do I sell? does pooling our harvest beat selling alone?* The job to be done is to leave with **one clear, trustworthy action**, backed by data that respects what they already know about their land.

**2. Evaluators — PM and Data Analyst recruiters and hiring managers.**
Desktop, skimming in under a minute, judging product sense and data craft. This app is the author's portfolio centerpiece for non-tech PM/DA roles in the agriculture domain. The job to be done is to **believe, fast, that this is a real product** built by someone who understands users and data — not a class project or a chart dump.

## Product Purpose

India farm-to-market **decision tool**. It turns public agriculture data (Agmarknet/eNAM prices, crop production history, ERA5 weather, India Post geo) into concrete decisions across three intents:

- **Grow** — CropAdvisor fuses district tradition, a GPU-trained yield model, seasonal weather fit, and market profitability into ranked, explained crop recommendations (tradition-first).
- **Sell** — mandi comparison, an FPO collective-selling engine (honest pooling-vs-solo arithmetic), price trends, and LSTM price forecasts.
- **Explore** — state map, crop analyser, revenue-loss estimator.

Success: a farmer or FPO manager leaves with a single confident action; an evaluator leaves convinced it is a credible, shippable product.

## Brand Personality

**Warm Editorial Agritech.** Three words: **grounded, confident, editorial.**

Voice is a plainspoken expert — a good agronomist who respects the farmer's generations of experience first, then shows the data that confirms or sharpens it. It explains the *why*, never hypes, and tells the unflattering truth (it will say "sell locally" when pooling doesn't pay). Emotional goal: **trust and calm clarity**, the opposite of dashboard anxiety. It should feel like a respected publication on Indian agriculture, not a software tool.

## Anti-references

- **Generic SaaS / AI-slop marketing**: gradient hero, tiny tracked uppercase eyebrows above every section, endless identical icon + heading + text cards, hero-metric templates.
- **The current "2014 dev-tool" look** this redesign replaces: flat green-800/gray, native `<select>` controls, unstyled tables, warm-cream near-white body with no identity.
- **Fintech-dashboard intimidation**: dense KPI tile walls, navy-and-gold, numbers-as-decoration.
- **Over-gamified agritech**: cartoon mascots, childish illustration, playful-to-the-point-of-untrustworthy.

## Design Principles

1. **Tradition-first, data-second.** Lead with what the farmer already trusts; let data confirm and refine. The interface mirrors the advisor's own logic.
2. **Honest numbers.** Never invent a premium or hide a bad result. Data is tabular, aligned, comparable, and sourced.
3. **One screen, one decision.** Every page resolves to a clear next action, not a wall of charts.
4. **Editorial confidence.** Authority comes from typographic hierarchy and whitespace, not chrome. Design like a publication, not a tool dump.
5. **Two audiences, one build.** Legible and mobile-first enough for a farmer on a cheap phone; polished and credible enough for a recruiter on a laptop — from a single codebase.

## Accessibility & Inclusion

- WCAG **AA**: body text ≥4.5:1, large text ≥3:1, placeholders held to the same body contrast (no washed-out gray on warm near-white — the current failure).
- **Tabular numbers** (`font-variant-numeric: tabular-nums`) on every price, quantity, and metric so columns align and scan.
- **Reduced motion**: every animation has a `prefers-reduced-motion: reduce` crossfade/instant fallback; no blocking page-load choreography.
- **Mobile-first, low-end-aware**: touch targets ≥44px, works over patchy connectivity, no heavy blocking animation on first paint.
- Color is never the sole signal (pair with icon/label/text) for color-blind users.
