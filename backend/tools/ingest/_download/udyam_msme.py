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
