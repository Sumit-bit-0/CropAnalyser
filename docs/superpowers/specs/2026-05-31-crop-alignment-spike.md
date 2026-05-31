# CropAdvisor Phase 0 — Crop-Name Alignment Spike

**Date:** 2026-05-31
**Status:** DONE. Produced the canonical crop catalog (`backend/analysis/crop_catalog.py`) and the v1 whitelist. This was the prerequisite that decides CropAdvisor's viability.

## Why this spike
CropAdvisor fuses three signals that live in three datasets with **no shared key** and **three different crop vocabularies**. It can only recommend a crop that exists in all three. Before designing weights or building modules, we had to find that intersection. The answer determines what the product can actually do.

## Sources & vocabulary sizes
| Signal | Source | Distinct crops |
|---|---|---|
| Agronomic suitability | `Crop_recommendation.csv` `label` | **22** (lowercase: rice, maize, pigeonpeas…) |
| Regional history | `Crop Production data.csv` `Crop` | **126** (title-case: Arhar/Tur, Gram…) |
| Market prices | `prices.commodity` | **384** (verbose: "Arhar (Tur/Red Gram)(Whole)"…) |
| Market (mandi detail) | `mandi_prices.commodity` | **5** (Onion, Potato, Rice, Tomato, Wheat) |

**Decision — market signal comes from `prices`, not `mandi_prices`.** `mandi_prices` has only 5 commodities; `prices` (27.6M rows, 384 commodities) is the broad table and is also what the 1,985 LSTM price models were trained on. `mandi_prices` stays for the GPS market-compare feature only.

## The v1 whitelist — 20 crops
Suitability (22) is the limiting vocabulary. Mapping each to production + market aliases and keeping only crops present in all three yields **20 canonical crops**:

`apple, banana, blackgram, chickpea, coconut, coffee, cotton, grapes, jute, lentil, maize, mango, mothbeans, mungbean, orange, papaya, pigeonpeas, pomegranate, rice, watermelon`

Encoded in `backend/analysis/crop_catalog.py` as `CANONICAL_CROPS` (canonical → per-source aliases) + `WHITELIST`. `validate()` asserts every alias still exists in its live source — **all 20 pass**. Example mappings that a naive intersection would miss:
- `pigeonpeas` → prod `Arhar/Tur` → market `Arhar (Tur/Red Gram)(Whole)` / `Red Gram`
- `chickpea` → prod `Gram` → market `Bengal Gram (Gram)(Whole)` / `Kabuli Chana`
- `mungbean` → prod `Moong(Green Gram)` → market `Green Gram (Moong)(Whole)`
- `pomegranate` → prod `Pome Granet` (sic) → market `Pomegranate`

### Excluded from v1
- **kidneybeans** — production = `Rajmash Kholar` (Rajma) ✅ but no clean market match in `prices`.
- **muskmelon** — market = `Karbuja (Musk Melon)` ✅ but no production-history crop.

These can return if we add the missing source later.

## Data-availability matrix
Volume per whitelisted crop (after stripping whitespace — see below):

| crop | market rows | mkt states | prod rows | prod states |
|---|--:|--:|--:|--:|
| rice | 1,895,117 | 32 | 15,583 | 33 |
| banana | 627,316 | 32 | 3,209 | 20 |
| maize | 549,517 | 29 | 13,947 | 31 |
| chickpea | 536,330 | 24 | 7,361 | 26 |
| pigeonpeas | 498,311 | 25 | 7,578 | 29 |
| apple | 426,107 | 30 | **4** | **1** |
| cotton | 349,536 | 23 | 4,530 | 26 |
| blackgram | 325,110 | 28 | 9,968 | 28 |
| mungbean | 264,123 | 27 | 10,318 | 26 |
| pomegranate | 208,457 | 25 | **66** | **2** |
| papaya | 186,272 | 29 | 483 | 11 |
| mango | 173,195 | 30 | 449 | 12 |
| coconut | 161,086 | 24 | 1,985 | 13 |
| lentil | 141,679 | 20 | 4,255 | 21 |
| grapes | 138,708 | 29 | 129 | 8 |
| orange | 117,520 | 32 | 271 | 7 |
| watermelon | 100,382 | 30 | **85** | **3** |
| jute | 46,646 | 14 | 1,453 | 13 |
| mothbeans | 42,514 | 19 | 878 | 9 |
| coffee | **6,700** | **6** | **6** | **1** |

**Findings:**
- **Market data is strong for all 20** (≥6.7K rows, ≥6 states).
- **Regional-history depth varies.** Thin-production crops: `apple` (4 rows/1 state), `coffee` (6/1), `pomegranate` (66/2), `watermelon` (85/3), `grapes` (129/8), `orange` (271/7). For these the **Regional Fit module will be weak or unavailable** — the fusion layer must degrade gracefully (drop that module's weight and renormalize, exactly as the design specifies). They still have suitability + market.

## Data-quality finding (must fix on load)
The production CSV has **trailing whitespace** in text columns — `Season` is `"Kharif     "`, and `Crop` values vary too. Unstripped matching reported `coconut` as 0 rows; stripping recovered 1,985. **The `district_crop_history` loader must `.strip()` crop/season/state names**, matching how `load_mandi.py` already cleans data.

## Resolutions to the open questions
- **Crop-name alignment (the blocker):** solved → `crop_catalog.py` is the single source of truth; all CropAdvisor modules import it.
- **India-first vs global:** India-first confirmed — all three sources are India.
- **Suitability model scope:** train on all 22 `Crop_recommendation.csv` labels (more signal), but **gate recommendations to the 20-crop whitelist**.

## Next steps
1. Add a test that runs `crop_catalog.validate()` so the catalog can't silently drift from the data.
2. Build the `district_crop_history` loader (strip names; aggregate area/production/yield by state/district/season/crop) → Regional Fit module.
3. Then Fusion v1 (Regional + Market via `prices`/LSTM + existing suitability model), with graceful degradation for thin-production crops.
