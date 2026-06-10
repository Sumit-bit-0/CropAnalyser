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
