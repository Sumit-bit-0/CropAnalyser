"""Udyam MSME downloader: drive udyamregistration.gov.in like a human and
reproduce the native "Product/Activity based MSME Units Detail" .xls exports
into _staging/msme/, then append manifest.csv, so the msme_udyam.py adapter
ingests them. Collection sibling to that adapter; portal-specific flow lives
here, not in web_harvester core (consumed only for the browser session).

Live run needs `pip install -e E:/web-harvester`. Pure functions below need no
browser; the live flow imports BrowserSession lazily.
"""
import csv
import html as _html
import logging
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup
from config import ROOT

log = logging.getLogger(__name__)

# Columns the msme_udyam.py adapter consumes (others are optional padding).
REQUIRED_COLS = ["Enterprise Name", "State", "District", "Pin Code"]

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
