# Udyam MSME Downloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a config-driven job that drives udyamregistration.gov.in like a human and reproduces native "Product/Activity based MSME Units Detail" `.xls` exports into `backend/tools/ingest/_staging/msme/`, so the existing `msme_udyam.py` adapter can ingest them — scaling coverage toward 36 states × 5 products without manual clicking.

**Architecture:** A new `_download/udyam_msme.py` module in the agri repo, sibling to the `adapters/msme_udyam.py` it feeds. Portal-specific flow lives here (not in the domain-agnostic `web_harvester` core, which it consumes only for the browser session). Pure functions (parse, serialize, stage, config) are unit-tested fully offline; the live browser flow is a thin glue layer verified later by a supervised Arc smoke. Dual-path capture (native Export download → fallback to scrape+serialize) makes the build independent of an unconfirmed Export control.

**Tech Stack:** Python 3.11+, pandas (`read_html`), pytest. Live path: `web_harvester.BrowserSession` (Playwright sync, Chromium) — installed editable from `E:\web-harvester`.

---

## File Structure

| Path | Responsibility |
|------|----------------|
| `backend/tools/ingest/_download/__init__.py` | Mark package (empty). |
| `backend/tools/ingest/_download/udyam_msme.py` | The job: `CONFIG`, `parse_level2_table`, `rows_to_xls_html`, `capture_level2`, `navigate_to_level2`, `download_slice`, `stage_file`, `run`, CLI. |
| `backend/tests/test_udyam_downloader.py` | Offline unit tests for all pure + seam functions. |
| `backend/tests/fixtures/udyam_level2_sample.html` | Synthetic Level-2 unit-list page modeling the real table. |

All tests run from `backend/` (its `tests/conftest.py` puts `backend/` on `sys.path`, so imports are `from tools.ingest._download.udyam_msme import ...`). Run command throughout: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -v`.

---

## Task 0: Environment + package skeleton

**Files:**
- Create: `backend/tools/ingest/_download/__init__.py` (empty)

- [ ] **Step 1: Install `web_harvester` editable into the agri env**

Run: `pip install -e E:/web-harvester`
Expected: `Successfully installed web-harvester-...` (pulls in playwright; chromium already installed in its own env, shared cache).

- [ ] **Step 2: Verify the import works**

Run: `python -c "from web_harvester.session import BrowserSession; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Create the package marker**

Create `backend/tools/ingest/_download/__init__.py` as an empty file (one trailing newline).

- [ ] **Step 4: Commit**

```bash
git add backend/tools/ingest/_download/__init__.py
git commit -m "chore: add _download package + web_harvester tooling dep"
```

---

## Task 1: `parse_level2_table` (pure) + fixture

Extract the unit table from a Level-2 page. The real page's largest table holds the units; its header row contains "Enterprise Name". We pick the `<table>` with the most rows and read its header + data cells.

**Files:**
- Create: `backend/tests/fixtures/udyam_level2_sample.html`
- Create: `backend/tools/ingest/_download/udyam_msme.py`
- Test: `backend/tests/test_udyam_downloader.py`

- [ ] **Step 1: Author the fixture**

Create `backend/tests/fixtures/udyam_level2_sample.html` (a header chrome table is included deliberately so the parser must pick the *largest* table, not the first):

```html
<!doctype html>
<html><body>
  <table id="chrome"><tr><td>Ministry of MSME</td></tr></table>
  <table id="ctl00_ContentPlaceHolder1_gvUnits" class="table">
    <tr>
      <th>SNo.</th><th>Enterprise Name</th><th>Address</th>
      <th>State</th><th>District</th><th>Pin Code</th>
      <th>Social Category</th><th>Gender</th>
    </tr>
    <tr>
      <td>1</td><td>Sharma Roller Flour Mills Pvt Ltd</td>
      <td>Industrial Area</td><td>BIHAR</td><td>Patna</td>
      <td>800001</td><td>General</td><td>Male</td>
    </tr>
    <tr>
      <td>2</td><td>Gopalganj Aata Chakki</td>
      <td>Main Road</td><td>BIHAR</td><td>Gopalganj</td>
      <td>841428</td><td>OBC</td><td>Female</td>
    </tr>
  </table>
</body></html>
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_udyam_downloader.py`:

```python
from pathlib import Path

from tools.ingest._download.udyam_msme import parse_level2_table

FIXTURES = Path(__file__).parent / "fixtures"


def _level2_html():
    return (FIXTURES / "udyam_level2_sample.html").read_text(encoding="utf-8")


def test_parse_level2_picks_largest_table_and_reads_rows():
    headers, rows = parse_level2_table(_level2_html())
    assert "Enterprise Name" in headers
    assert headers[1] == "Enterprise Name"
    assert len(rows) == 2
    # row is aligned to headers
    name_idx = headers.index("Enterprise Name")
    assert rows[0][name_idx] == "Sharma Roller Flour Mills Pvt Ltd"
    pin_idx = headers.index("Pin Code")
    assert rows[1][pin_idx] == "841428"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_level2_table'`.

- [ ] **Step 4: Write minimal implementation**

Create `backend/tools/ingest/_download/udyam_msme.py` with the module docstring and this function:

```python
"""Udyam MSME downloader: drive udyamregistration.gov.in like a human and
reproduce the native "Product/Activity based MSME Units Detail" .xls exports
into _staging/msme/, then append manifest.csv, so the msme_udyam.py adapter
ingests them. Collection sibling to that adapter; portal-specific flow lives
here, not in web_harvester core (consumed only for the browser session).

Live run needs `pip install -e E:/web-harvester`. Pure functions below need no
browser; the live flow imports BrowserSession lazily.
"""
from bs4 import BeautifulSoup


def parse_level2_table(html: str) -> tuple[list[str], list[list[str]]]:
    """Return (headers, rows) from the unit list on a Level-2 page.

    The units live in the table with the most rows; its first row is the header.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return [], []
    table = max(tables, key=lambda t: len(t.find_all("tr")))
    trs = table.find_all("tr")
    if not trs:
        return [], []
    headers = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
    rows = []
    for tr in trs[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    return headers, rows
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -v`
Expected: PASS. (`beautifulsoup4` is already a project dep — it backs `web_harvester` extract and agri scrapers.)

- [ ] **Step 6: Commit**

```bash
git add backend/tools/ingest/_download/udyam_msme.py backend/tests/test_udyam_downloader.py backend/tests/fixtures/udyam_level2_sample.html
git commit -m "feat: parse_level2_table extracts unit list from Udyam Level-2 page"
```

---

## Task 2: `rows_to_xls_html` (pure) — adapter-compatible output

Serialize parsed rows to an HTML `<table>` the adapter reads via `pd.read_html`. The four columns the adapter needs (`Enterprise Name, State, District, Pin Code`) must be present and exactly named; if the source headers lack one, emit it empty.

**Files:**
- Modify: `backend/tools/ingest/_download/udyam_msme.py`
- Test: `backend/tests/test_udyam_downloader.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_udyam_downloader.py`:

```python
import io
import pandas as pd

from tools.ingest._download.udyam_msme import rows_to_xls_html
from tools.ingest.adapters.msme_udyam import qualify_and_collapse

ADAPTER_COLS = ["Enterprise Name", "State", "District", "Pin Code"]


def test_rows_to_xls_html_roundtrips_through_read_html():
    headers, rows = parse_level2_table(_level2_html())
    html = rows_to_xls_html(headers, rows)
    df = pd.read_html(io.StringIO(html))[0]
    for col in ADAPTER_COLS:
        assert col in df.columns
    assert len(df) == 2


def test_serialized_output_is_accepted_by_adapter():
    headers, rows = parse_level2_table(_level2_html())
    df = pd.read_html(io.StringIO(rows_to_xls_html(headers, rows)))[0]
    out = qualify_and_collapse(df, "flour_mill", "wheat", min_cluster=5)
    # The strong-named Patna unit survives; the lone Gopalganj chakki does not.
    assert (out["pin"] == "800001").any()
    assert (out["pin"] == "841428").sum() == 0


def test_missing_required_column_is_emitted_empty():
    html = rows_to_xls_html(["Enterprise Name", "Pin Code"],
                            [["Acme Rice Mill", "500001"]])
    df = pd.read_html(io.StringIO(html))[0]
    for col in ADAPTER_COLS:
        assert col in df.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k rows_to_xls -v`
Expected: FAIL — `cannot import name 'rows_to_xls_html'`.

- [ ] **Step 3: Write minimal implementation**

Add to `udyam_msme.py` (import `html` stdlib at top with the others):

```python
import html as _html

# Columns the msme_udyam.py adapter consumes (others are optional padding).
REQUIRED_COLS = ["Enterprise Name", "State", "District", "Pin Code"]


def rows_to_xls_html(headers: list[str], rows: list[list[str]]) -> str:
    """Serialize rows to an HTML <table> string readable by pd.read_html.

    Guarantees REQUIRED_COLS are present and exactly named; any missing one is
    appended as an empty column so the adapter never KeyErrors.
    """
    out_headers = list(headers)
    for col in REQUIRED_COLS:
        if col not in out_headers:
            out_headers.append(col)
    src_index = {h: i for i, h in enumerate(headers)}

    def cell(row: list[str], col: str) -> str:
        i = src_index.get(col)
        return _html.escape(row[i]) if i is not None and i < len(row) else ""

    head = "".join(f"<th>{_html.escape(h)}</th>" for h in out_headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell(r, h)}</td>" for h in out_headers) + "</tr>"
        for r in rows
    )
    return f"<table><tr>{head}</tr>{body}</table>"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k rows_to_xls -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/_download/udyam_msme.py backend/tests/test_udyam_downloader.py
git commit -m "feat: rows_to_xls_html emits adapter-compatible HTML .xls"
```

---

## Task 3: `CONFIG` — the states × products matrix

**Files:**
- Modify: `backend/tools/ingest/_download/udyam_msme.py`
- Test: `backend/tests/test_udyam_downloader.py`

- [ ] **Step 1: Write the failing test**

Append to the test file:

```python
import pandas as pd
from config import DATA_RAW
from tools.ingest._download.udyam_msme import PRODUCTS, STATES


def test_products_match_facility_crop_map():
    fcm = pd.read_csv(DATA_RAW / "facility_crop_map.csv")
    valid = set(zip(fcm["crop"], fcm["facility_type"]))
    for key, p in PRODUCTS.items():
        assert {"nic", "search", "facility_type", "crop"} <= p.keys()
        assert (p["crop"], p["facility_type"]) in valid, key


def test_states_present_and_bihar_known():
    assert "Bihar" in STATES
    assert len(STATES) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k "products or states" -v`
Expected: FAIL — `cannot import name 'PRODUCTS'`.

- [ ] **Step 3: Write minimal implementation**

Add to `udyam_msme.py`. Crop/facility_type values are pinned against `data/raw/facility_crop_map.csv` (wheat→flour_mill, rice→rice_mill, pigeonpeas→dal_mill, mustard→oil_mill, cotton→cotton_ginning). NIC codes from the project's MSME notes (10611 flour, 10612 rice, 10613 dal, 10401 oil, 01632 cotton ginning):

```python
PRODUCTS = {
    "flour":  {"nic": "10611", "search": "flour",  "facility_type": "flour_mill",     "crop": "wheat"},
    "rice":   {"nic": "10612", "search": "rice",   "facility_type": "rice_mill",      "crop": "rice"},
    "dal":    {"nic": "10613", "search": "dal",    "facility_type": "dal_mill",       "crop": "pigeonpeas"},
    "oil":    {"nic": "10401", "search": "oil",    "facility_type": "oil_mill",       "crop": "mustard"},
    "cotton": {"nic": "01632", "search": "cotton", "facility_type": "cotton_ginning", "crop": "cotton"},
}

# State display names, selected on the search page by visible label. Start with
# the two already staged manually; extend toward all 36 by adding names here.
STATES = ["Bihar", "Andhra Pradesh"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k "products or states" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/_download/udyam_msme.py backend/tests/test_udyam_downloader.py
git commit -m "feat: CONFIG matrix (5 products x states) pinned to facility_crop_map"
```

---

## Task 4: `stage_file` — idempotent staging + manifest append

**Files:**
- Modify: `backend/tools/ingest/_download/udyam_msme.py`
- Test: `backend/tests/test_udyam_downloader.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
import csv
from tools.ingest._download import udyam_msme as dl


def test_stage_file_writes_and_appends_manifest(tmp_path, monkeypatch):
    staging = tmp_path / "msme"
    monkeypatch.setattr(dl, "STAGING_DIR", staging)
    monkeypatch.setattr(dl, "MANIFEST", staging / "manifest.csv")

    path = dl.stage_file("<table></table>", "flour", "Bihar")
    assert path.exists()
    assert path.name == "flour_bihar.xls"

    rows = list(csv.DictReader((staging / "manifest.csv").open()))
    assert rows[-1] == {"file": "flour_bihar.xls",
                        "facility_type": "flour_mill", "crop": "wheat"}


def test_stage_file_manifest_is_idempotent(tmp_path, monkeypatch):
    staging = tmp_path / "msme"
    monkeypatch.setattr(dl, "STAGING_DIR", staging)
    monkeypatch.setattr(dl, "MANIFEST", staging / "manifest.csv")
    dl.stage_file("<table></table>", "rice", "Bihar")
    dl.stage_file("<table></table>", "rice", "Bihar")  # re-run
    rows = list(csv.DictReader((staging / "manifest.csv").open()))
    assert sum(r["file"] == "rice_bihar.xls" for r in rows) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k stage_file -v`
Expected: FAIL — `module ... has no attribute 'stage_file'`.

- [ ] **Step 3: Write minimal implementation**

Add to `udyam_msme.py` (add `import csv` and `from pathlib import Path` and `from config import ROOT` at top):

```python
STAGING_DIR = ROOT / "backend" / "tools" / "ingest" / "_staging" / "msme"
MANIFEST = STAGING_DIR / "manifest.csv"
_MANIFEST_HEADER = ["file", "facility_type", "crop"]


def _slug(state: str) -> str:
    return state.strip().lower().replace(" ", "_")


def stage_file(content: str, product: str, state: str) -> Path:
    """Write content to _staging/msme/<product>_<state>.xls and append a
    manifest row (idempotently — never duplicates an existing file row)."""
    p = PRODUCTS[product]
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{product}_{_slug(state)}.xls"
    out = STAGING_DIR / fname
    out.write_text(content, encoding="utf-8")

    existing = []
    if MANIFEST.exists():
        existing = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    if not any(r["file"] == fname for r in existing):
        is_new = not MANIFEST.exists()
        with MANIFEST.open("a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            if is_new:
                w.writerow(_MANIFEST_HEADER)
            w.writerow([fname, p["facility_type"], p["crop"]])
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k stage_file -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/_download/udyam_msme.py backend/tests/test_udyam_downloader.py
git commit -m "feat: stage_file writes .xls + idempotent manifest append"
```

---

## Task 5: `capture_level2` — dual-path capture (fake-page tested)

Try the native Export download first; if there's no export control (or it yields nothing), fall back to scraping + serializing the rendered table. Tested with a minimal fake `page` so no real browser is needed.

**Files:**
- Modify: `backend/tools/ingest/_download/udyam_msme.py`
- Test: `backend/tests/test_udyam_downloader.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from tools.ingest._download.udyam_msme import capture_level2

LEVEL2 = (FIXTURES / "udyam_level2_sample.html").read_text(encoding="utf-8")


class _NoExportPage:
    """A page with no export control: locator(...).count() == 0."""
    def __init__(self, html):
        self._html = html
    def content(self):
        return self._html
    def locator(self, selector):
        return self
    def count(self):
        return 0


class _ExportPage:
    """A page whose export control triggers a real download."""
    def __init__(self, payload):
        self._payload = payload
    def content(self):
        return "<html>ignored</html>"
    def locator(self, selector):
        return self
    def count(self):
        return 1
    def first(self):
        return self


def test_capture_falls_back_to_scrape_when_no_export(tmp_path):
    content = capture_level2(_NoExportPage(LEVEL2), tmp_path)
    df = pd.read_html(io.StringIO(content))[0]
    assert "Enterprise Name" in df.columns
    assert len(df) == 2  # scraped both rows from the fixture
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k capture -v`
Expected: FAIL — `cannot import name 'capture_level2'`.

- [ ] **Step 3: Write minimal implementation**

Add to `udyam_msme.py`. The export control is located by id/text heuristic; if absent we scrape. Keep the primary download path narrow and defensive (the live smoke will confirm the real selector):

```python
# Heuristic selector for a native Export-to-Excel control on Level-2.
_EXPORT_SELECTOR = (
    "a:has-text('Export'), a:has-text('Excel'), "
    "input[value*='Export' i], input[id*='Export' i], img[src*='excel' i]"
)


def capture_level2(page, tmp_dir) -> str:
    """Return HTML-table content for the Level-2 unit list.

    Primary: click a native Export control and read the downloaded file.
    Fallback: scrape the rendered table and serialize it. Both yield content
    pd.read_html can parse.
    """
    try:
        control = page.locator(_EXPORT_SELECTOR)
        if control.count() > 0:
            from pathlib import Path as _P
            with page.expect_download() as dl_info:
                control.first.click()
            download = dl_info.value
            dest = _P(tmp_dir) / "export.xls"
            download.save_as(str(dest))
            return dest.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass  # fall through to scrape

    headers, rows = parse_level2_table(page.content())
    return rows_to_xls_html(headers, rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k capture -v`
Expected: PASS. (The `_ExportPage` class is defined for documentation/future live-path parity; the offline-deterministic assertion exercises the fallback.)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/_download/udyam_msme.py backend/tests/test_udyam_downloader.py
git commit -m "feat: capture_level2 dual-path (native export -> scrape fallback)"
```

---

## Task 6: `navigate_to_level2` — flow glue (call-sequence tested)

Drive the stateful sequence over a duck-typed `page`. We assert the exact call sequence with a recording fake so accidental selector/step changes are caught offline; the real DOM behaviour is confirmed in the live smoke.

**Files:**
- Modify: `backend/tools/ingest/_download/udyam_msme.py`
- Test: `backend/tests/test_udyam_downloader.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from contextlib import contextmanager
from tools.ingest._download.udyam_msme import navigate_to_level2, MAIN, S


class _RecordingPage:
    def __init__(self):
        self.calls = []
    def set_default_timeout(self, ms):
        self.calls.append(("set_default_timeout", ms))
    def goto(self, url, **kw):
        self.calls.append(("goto", url))
    def select_option(self, selector, **kw):
        self.calls.append(("select_option", selector, kw.get("label")))
    def wait_for_function(self, js, **kw):
        self.calls.append(("wait_for_function", js[:18]))
    def fill(self, selector, value):
        self.calls.append(("fill", selector, value))
    def click(self, selector):
        self.calls.append(("click", selector))
    def locator(self, selector):
        self._last = selector
        return self
    @property
    def first(self):
        return self
    def click(self, *a):  # anchor + button share click; record selector path
        self.calls.append(("click", getattr(self, "_last", a[0] if a else None)))
    @contextmanager
    def expect_navigation(self, **kw):
        self.calls.append(("expect_navigation",))
        yield


def test_navigate_issues_expected_sequence():
    page = _RecordingPage()
    navigate_to_level2(page, "Bihar", PRODUCTS["flour"])
    kinds = [c[0] for c in page.calls]
    assert kinds[:2] == ["set_default_timeout", "goto"]
    assert ("select_option", f"{S}ddlPState", "Bihar") in page.calls
    assert ("fill", f"{S}txtsearchNic", "flour") in page.calls
    assert ("expect_navigation",) in kinds_tuples(page.calls)
    assert page.calls[1] == ("goto", MAIN)


def kinds_tuples(calls):
    return [c if len(c) == 1 else (c[0],) for c in calls]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k navigate -v`
Expected: FAIL — `cannot import name 'navigate_to_level2'`.

- [ ] **Step 3: Write minimal implementation**

Add to `udyam_msme.py`. Selectors and the count-anchor pattern come from `scratch/explore_udyam.py` (the recon that reached Level-2):

```python
MAIN = "https://udyamregistration.gov.in/searchregistration.aspx"
S = "#ctl00_ContentPlaceHolder1_"
_NAV_TIMEOUT = 150_000


def navigate_to_level2(page, state: str, product: dict) -> None:
    """Search page -> select state -> NIC search -> click count anchor ->
    Level-2 unit list. Raises if a step's wait times out (caller isolates)."""
    page.set_default_timeout(60_000)
    page.goto(MAIN, wait_until="domcontentloaded")
    page.select_option(f"{S}ddlPState", label=state)
    page.wait_for_function(
        f"document.querySelector('{S}ddlPDistrict')"
        f" && document.querySelector('{S}ddlPDistrict').options.length > 1",
        timeout=30_000)
    page.fill(f"{S}txtsearchNic", product["search"])
    page.click(f"{S}btnSearch")
    page.wait_for_function("/MSME Count/i.test(document.body.innerText)",
                           timeout=30_000)
    anchor = page.locator(f"a[href*='cod={product['nic']}']").first
    with page.expect_navigation(wait_until="domcontentloaded",
                                timeout=_NAV_TIMEOUT):
        anchor.click()
    page.wait_for_function(
        "!!document.body && /Enterprise Name/i.test(document.body.innerText)",
        timeout=_NAV_TIMEOUT)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k navigate -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/_download/udyam_msme.py backend/tests/test_udyam_downloader.py
git commit -m "feat: navigate_to_level2 drives the Udyam search->Level-2 flow"
```

---

## Task 7: `download_slice` + `run` orchestrator

`download_slice` ties navigate + capture + stage for one combo. `run` loops the matrix with skip-existing resumability and per-combo failure isolation. Both are tested by monkeypatching the lower layers — no browser.

**Files:**
- Modify: `backend/tools/ingest/_download/udyam_msme.py`
- Test: `backend/tests/test_udyam_downloader.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_run_skips_existing_and_isolates_failures(tmp_path, monkeypatch):
    staging = tmp_path / "msme"
    staging.mkdir(parents=True)
    (staging / "flour_bihar.xls").write_text("<table></table>")  # already done
    monkeypatch.setattr(dl, "STAGING_DIR", staging)
    monkeypatch.setattr(dl, "MANIFEST", staging / "manifest.csv")

    seen = []

    def fake_download_slice(state, product_key, *, headless):
        seen.append((state, product_key))
        if product_key == "rice":
            raise RuntimeError("level-2 timeout")
        return dl.stage_file("<table></table>", product_key, state)

    monkeypatch.setattr(dl, "download_slice", fake_download_slice)

    meta = dl.run(states=["Bihar"], products=["flour", "rice", "dal"],
                  headless=True)
    # flour skipped (file exists), rice failed, dal done
    assert ("Bihar", "flour") not in seen
    assert meta["done"] == 1
    assert meta["failed"] == 1
    assert meta["skipped"] == 1


def test_download_slice_stages_via_injected_session(tmp_path, monkeypatch):
    staging = tmp_path / "msme"
    monkeypatch.setattr(dl, "STAGING_DIR", staging)
    monkeypatch.setattr(dl, "MANIFEST", staging / "manifest.csv")
    monkeypatch.setattr(dl, "navigate_to_level2", lambda page, s, p: None)
    monkeypatch.setattr(dl, "capture_level2",
                        lambda page, tmp: "<table><tr><th>Enterprise Name</th>"
                                          "</tr><tr><td>X Mill</td></tr></table>")

    class _Sess:
        page = object()
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(dl, "_open_session", lambda headless: _Sess())

    out = dl.download_slice("Bihar", "flour", headless=True)
    assert out.name == "flour_bihar.xls"
    assert out.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k "run_skips or download_slice_stages" -v`
Expected: FAIL — `module ... has no attribute 'download_slice'` / `run`.

- [ ] **Step 3: Write minimal implementation**

Add to `udyam_msme.py` (add `import tempfile` and `import logging` at top; `log = logging.getLogger(__name__)`):

```python
def _open_session(headless: bool):
    """Lazily import web_harvester so pure functions/tests need no browser."""
    from web_harvester.session import BrowserSession
    profile = ROOT / "backend" / "tools" / "ingest" / "_download" / ".profile"
    return BrowserSession(profile_dir=profile, headless=headless)


def download_slice(state: str, product_key: str, *, headless: bool = False) -> Path:
    """Fetch one (state, product) slice and stage it. Returns the .xls path."""
    product = PRODUCTS[product_key]
    with _open_session(headless) as sess:
        navigate_to_level2(sess.page, state, product)
        with tempfile.TemporaryDirectory() as tmp:
            content = capture_level2(sess.page, tmp)
    return stage_file(content, product_key, state)


def _target_exists(product_key: str, state: str) -> bool:
    return (STAGING_DIR / f"{product_key}_{_slug(state)}.xls").exists()


def run(states=None, products=None, *, headless=False, force=False) -> dict:
    """Loop the matrix. Skip combos already staged (unless force); isolate
    per-combo failures. Returns counts."""
    states = states if states is not None else STATES
    products = products if products is not None else list(PRODUCTS)
    done = failed = skipped = 0
    for state in states:
        for pkey in products:
            if not force and _target_exists(pkey, state):
                skipped += 1
                continue
            try:
                download_slice(state, pkey, headless=headless)
                done += 1
            except Exception as exc:  # one bad combo never sinks the run
                log.warning("combo failed: %s/%s: %s", state, pkey, exc)
                failed += 1
    meta = {"done": done, "failed": failed, "skipped": skipped}
    log.info("udyam run: %s", meta)
    return meta
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -k "run_skips or download_slice_stages" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/_download/udyam_msme.py backend/tests/test_udyam_downloader.py
git commit -m "feat: download_slice + run orchestrator (skip-existing, failure isolation)"
```

---

## Task 8: CLI entry point + full-suite verification

**Files:**
- Modify: `backend/tools/ingest/_download/udyam_msme.py`

- [ ] **Step 1: Add a `__main__` CLI**

Append to `udyam_msme.py`:

```python
def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="Download Udyam MSME unit exports into _staging/msme/.")
    ap.add_argument("--state", action="append", dest="states",
                    help="State display name (repeatable). Default: all in STATES.")
    ap.add_argument("--product", action="append", dest="products",
                    choices=list(PRODUCTS),
                    help="Product key (repeatable). Default: all.")
    ap.add_argument("--headless", action="store_true",
                    help="Run Chromium headless (default: headed for supervision).")
    ap.add_argument("--force", action="store_true",
                    help="Re-fetch combos even if the .xls already exists.")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    meta = run(states=args.states, products=args.products,
               headless=args.headless, force=args.force)
    print(meta)


if __name__ == "__main__":
    _main()
```

- [ ] **Step 2: Smoke the CLI wiring (no browser — empty matrix)**

Run: `cd /e/agri-market-analyser/backend && python -m tools.ingest._download.udyam_msme --state Bihar --product flour --headless` then immediately Ctrl-C is NOT needed only if a browser would launch. To verify wiring without launching a browser, instead run:
`python -c "from tools.ingest._download.udyam_msme import _main; _main(['--help'])"`
Expected: argparse help text prints, exit 0.

- [ ] **Step 3: Run the full new suite**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_udyam_downloader.py -v`
Expected: ALL PASS (parse 1, rows_to_xls 3, products/states 2, stage 2, capture 1, navigate 1, run/download_slice 2 = 12 tests).

- [ ] **Step 4: Run the broader ingest suite for no regressions**

Run: `cd /e/agri-market-analyser/backend && python -m pytest tests/test_msme_udyam.py tests/test_udyam_downloader.py -v`
Expected: ALL PASS (existing adapter tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/_download/udyam_msme.py
git commit -m "feat: udyam downloader CLI entry point"
```

---

## Task 9: Document the live-run procedure

**Files:**
- Modify: `backend/tools/ingest/README.md`

- [ ] **Step 1: Append a downloader section to the ingest README**

Add this section to `backend/tools/ingest/README.md`:

```markdown
## Collection: Udyam MSME downloader (`_download/udyam_msme.py`)

Automates the manual Udyam exports that feed the `msme_udyam` adapter.

Setup (once): `pip install -e E:/web-harvester`

Run (headed, supervised — recommended; uses Arc/Chromium):
`cd backend && python -m tools.ingest._download.udyam_msme --state Bihar --product flour`

It drives udyamregistration.gov.in, captures each (state, product) unit list to
`_staging/msme/<product>_<state>.xls`, and appends `manifest.csv`. Then ingest as
usual: `python -m tools.ingest.run`. Re-runs skip already-staged files (`--force`
to override). Expand coverage by adding names to `STATES` in the module.
```

- [ ] **Step 2: Commit**

```bash
git add backend/tools/ingest/README.md
git commit -m "docs: document Udyam downloader live-run procedure"
```

---

## Live smoke (manual follow-on — NOT part of this plan's automated tasks)

After the plan is implemented and all tests pass, the user runs a supervised
headed session with Arc ([[feedback-browser-testing]]):
`cd backend && python -m tools.ingest._download.udyam_msme --state Bihar --product flour`

Verify: (1) which capture path fired (native export vs scrape — check whether
`_EXPORT_SELECTOR` matched), (2) `_staging/msme/flour_bihar.xls` parses via
`pd.read_html` with the four required columns, (3) diff its unit count against the
existing manual `flour_bihar.xls`. Adjust selectors in the module if the live DOM
differs from the recon assumptions, then re-run tests.

---

## Self-Review

- **Spec coverage:** placement (Task 0), `CONFIG` (3), `parse_level2_table` (1),
  `rows_to_xls_html` (2), `download_slice`/`navigate`/`capture` dual-path (5,6,7),
  `stage_file` (4), `run` (7), error isolation (7), tooling dep (0), CLI (8),
  offline TDD against fixture (1–7), live smoke as follow-on (documented). All
  spec sections map to a task.
- **Placeholder scan:** none — every code/test step shows full code.
- **Type consistency:** `parse_level2_table -> (headers, rows)` consumed by
  `rows_to_xls_html(headers, rows)` and `capture_level2`; `REQUIRED_COLS`,
  `PRODUCTS`/`STATES`, `STAGING_DIR`/`MANIFEST`, `_slug`, `S`/`MAIN`,
  `_open_session`/`download_slice`/`run` names are consistent across tasks.
