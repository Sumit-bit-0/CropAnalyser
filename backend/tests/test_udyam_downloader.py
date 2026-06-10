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


# The native Export-download branch is covered by the supervised live Arc smoke
# (per the ingest README), not offline; here we exercise the scrape fallback.
def test_capture_falls_back_to_scrape_when_no_export(tmp_path):
    content = capture_level2(_NoExportPage(LEVEL2), tmp_path)
    df = pd.read_html(io.StringIO(content))[0]
    assert "Enterprise Name" in df.columns
    assert len(df) == 2  # scraped both rows from the fixture


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
    def locator(self, selector):
        self._last = selector
        return self
    @property
    def first(self):
        return self
    def click(self, *a):
        # both page.click(selector) and page.locator(sel).first.click()
        selector = getattr(self, "_last", a[0] if a else None)
        self._last = None
        self.calls.append(("click", selector))
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
    assert ("click", f"{S}btnSearch") in page.calls
    assert ("click", f"a[href*='cod={PRODUCTS['flour']['nic']}']") in page.calls
    assert ("expect_navigation",) in kinds_tuples(page.calls)
    assert page.calls[1] == ("goto", MAIN)


def kinds_tuples(calls):
    return [c if len(c) == 1 else (c[0],) for c in calls]


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


def test_run_force_refetches_existing(tmp_path, monkeypatch):
    staging = tmp_path / "msme"
    staging.mkdir(parents=True)
    (staging / "flour_bihar.xls").write_text("<table></table>")
    monkeypatch.setattr(dl, "STAGING_DIR", staging)
    monkeypatch.setattr(dl, "MANIFEST", staging / "manifest.csv")
    seen = []
    def fake(state, pkey, *, headless):
        seen.append((state, pkey))
        return dl.stage_file("<table></table>", pkey, state)
    monkeypatch.setattr(dl, "download_slice", fake)
    meta = dl.run(states=["Bihar"], products=["flour"], force=True, headless=True)
    assert ("Bihar", "flour") in seen
    assert meta["skipped"] == 0


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
