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
