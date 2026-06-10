# Udyam MSME Downloader Job — Design

**Date:** 2026-06-10
**Status:** Approved (brainstorming) — pending implementation plan
**Repo:** agri-market-analyser
**Depends on:** `web-harvester` (E:\web-harvester) for browser primitives

## Problem

The `msme_udyam.py` ingestion adapter loads food-processing units into
`processing_units` from native Udyam "Product/Activity based MSME Units Detail"
Excel exports staged in `backend/tools/ingest/_staging/msme/`. Today those `.xls`
files are produced **by hand** — a human logs into udyamregistration.gov.in,
selects a state, searches an NIC activity, drills into the unit list, and clicks
Export. Only Bihar + Andhra Pradesh, 5 product slices, exist so far.

This job automates that collection: drive the portal like a human and reproduce
the native export files, so coverage can scale toward all 36 states × 5 products
(flour, rice, dal, oil, cotton) without manual clicking.

## Boundary & placement

The downloader is the **collection** sibling to the existing **ingestion**
adapter. It lives in the agri repo, next to the adapter it feeds:

```
backend/tools/ingest/
  _download/
    __init__.py
    udyam_msme.py          # this job
  adapters/msme_udyam.py   # existing adapter, consumes the output
  _staging/msme/           # output: <product>_<state>.xls + manifest.csv
```

Portal-specific flow logic lives **here, not in web-harvester core** — the core
is deliberately domain-agnostic ("no project logic in core"). The downloader is a
*consumer* of `web_harvester`, not a generic `JobSpec` (the Udyam flow is a
stateful ASP.NET sequence the core's url-driven `EscalationRunner` does not
model).

### Tooling dependency

`web_harvester` is **not yet installed** in the agri environment. The plan must
add it as a tooling/dev dependency: `pip install -e E:/web-harvester` (it pulls
playwright + chromium, already installed in its own env). The import is isolated
inside the live code path so pure functions and their tests need no browser and
no web_harvester import.

## Adapter contract (the deliverable format)

`msme_udyam.py` reads each staged file with `pd.read_html(path)[0]` — the files
are HTML tables saved as `.xls`. It only consumes four columns:

```
Enterprise Name, State, District, Pin Code
```

(native exports also carry SNo., Address, Social Category, Gender — not used).
The manifest maps each file to its ingestion semantics:

```
file,facility_type,crop
flour_bihar.xls,flour_mill,wheat
```

So the downloader's entire deliverable is: **produce an HTML-table `.xls` carrying
at least those four correctly-named columns, and append the manifest row.** The
adapter does all collapse/geocode/load downstream, unchanged.

## Components (each independently testable)

1. **`CONFIG`** — two plain dicts.
   - `STATES`: state display name, selected on the search page by **visible label**
     (not the brittle option index the recon script used).
   - `PRODUCTS`: e.g. `flour → {nic: "10611", search: "flour",
     facility_type: "flour_mill", crop: "wheat"}`, plus rice (`10612`/rice/rice),
     dal (`10613`/pulse/pigeonpeas), oil (`10401`/oil_mill/groundnut), cotton
     (`01632`/cotton ginning). This *is* the matrix; expanding coverage = editing
     these dicts. Semantics mirror `manifest.csv`.

2. **`parse_level2_table(html) -> (headers, rows)`** *(pure)* — locate the unit
   table on a Level-2 page and extract header + data rows. The offline-testable
   heart of the job.

3. **`rows_to_xls_html(headers, rows) -> str`** *(pure)* — emit an HTML `<table>`
   string with the four adapter-required columns guaranteed-named (others padded
   empty if absent), so `pd.read_html` yields the same frame shape as a native
   export.

4. **`download_slice(page, state, product) -> Path | None`** *(live)* — the
   recon-proven sequence:
   1. goto `searchregistration.aspx`
   2. select state by label → wait for the district dropdown to repopulate
      (ASP.NET postback)
   3. fill the NIC search term → click Search
   4. wait for the "MSME Count" results
   5. click the count anchor `a[href*='cod={nic}']` → wait for navigation
   6. wait for Level-2 unit list ("Enterprise Name")
   7. **capture** (dual-path, below) → save `.xls`
   Returns the saved path, or `None` if the combo legitimately has no data.

5. **`stage_file(path, product, state)`** — move/write the file to
   `_staging/msme/<product>_<state>.xls` and **idempotently** append the
   `file,facility_type,crop` row to `manifest.csv` (no duplicate lines on re-run).

6. **`run(states, products, *, headless=False, force=False)`** — orchestrator.
   Loops combos, skips combos whose output `.xls` already exists (resumable)
   unless `force`, isolates per-combo failures, logs done/failed/skipped. A polite
   delay between combos (govt portal). Sequential — no parallelism.

## Capture — dual-path (robust to an open unknown)

Live recon reached Level-2 but did **not** conclusively confirm a native Export
control (its stdout listing wasn't saved). The design does not depend on the
answer:

- **Primary:** locate the export control via web_harvester's export-label
  heuristic → `page.expect_download()` → save the returned `.xls`.
- **Fallback:** `parse_level2_table` → `rows_to_xls_html` → save as `.xls`,
  walking pagination ("next" until exhausted) if Level-2 paginates.

Both yield an HTML-table `.xls` the adapter reads identically. The live smoke
reveals which path fires; if the rendered Level-2 table lacks a column, the
fallback still works because the adapter only needs the four core columns.

## Data flow

```
CONFIG → run() → download_slice() → capture
       → stage_file() → _staging/msme/<product>_<state>.xls + manifest row
       → (later, existing) python -m tools.ingest.run → MsmeUdyam → processing_units
```

## Error handling

- Per-combo isolation: state-label-not-found, district-postback timeout, zero
  results / missing count-anchor (many state×activity combos legitimately have
  none), Level-2 timeout → log and continue to the next combo.
- `detect_gate` (web_harvester) defensively after render; recon found no CAPTCHA,
  but if one appears in headed mode, pause for a human (recognize, never solve).
  Offline tests never hit this.
- Idempotent re-runs via skip-existing; `force` to override.

## Testing (TDD, fully offline)

- **`parse_level2_table`** against a Level-2 HTML **fixture** authored to model
  the real table structure (largest table, header containing "Enterprise Name").
  The saved recon `after_search.html` (Level-1) backs a test of the count-anchor
  locator `a[href*='cod={nic}']`.
- **`rows_to_xls_html`** round-trips through `pd.read_html`; assert the agri
  adapter's `qualify_and_collapse` accepts the result (four columns present).
- **`stage_file`**: tmp dir — file written, manifest appended, idempotent on
  re-run.
- **`run`**: monkeypatched `download_slice` — loops combos, stages, skips
  existing, survives a per-combo exception.

No live portal access is required for the suite to pass. The actual live run
(headed browser, supervised, via Arc per the browser-testing rule) is a separate
follow-on the user triggers — not part of this build.

## Scope decisions (locked)

- **Home:** agri repo, `backend/tools/ingest/_download/udyam_msme.py`.
- **Coverage:** config-driven and expandable to 36×5=180, verified end-to-end on
  the existing real slice (Bihar/AP combos, diffable against the manual exports
  already staged). Scaling to all 180 = config edit + a supervised run.
- **This build:** code + offline tests only. Live run is a separate supervised
  step.

## YAGNI — explicitly out of scope

No T2 vision locator, no generic `JobSpec`, no DB sink (the adapter already loads
the DB), no gate-solving, no parallelism, config as in-module dicts (not external
YAML).

## Follow-ons (not gaps)

1. Supervised **live smoke** with Arc — confirm which capture path fires, validate
   the Level-2 selector against reality, diff output vs the manual Bihar/AP exports.
2. Expand `STATES`/`PRODUCTS` toward full coverage; add the cotton-ginning slice
   (NIC `01632`, currently zero facilities in `processing_units`).
3. Optional: a thin CLI (`python -m tools.ingest._download.udyam_msme --state ... --product ...`).
