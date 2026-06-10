"""Udyam MSME downloader: drive udyamregistration.gov.in like a human and
reproduce the native "Product/Activity based MSME Units Detail" .xls exports
into _staging/msme/, then append manifest.csv, so the msme_udyam.py adapter
ingests them. Collection sibling to that adapter; portal-specific flow lives
here, not in web_harvester core (consumed only for the browser session).

Live run needs `pip install -e E:/web-harvester`. Pure functions below need no
browser; the live flow imports BrowserSession lazily.
"""
import html as _html

from bs4 import BeautifulSoup

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
