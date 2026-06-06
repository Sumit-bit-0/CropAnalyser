from tools.ingest import schema
from tools.ingest.adapters.shc_soil import ShcSoil


SAMPLE_RECORDS = [
    {"state": "Bihar", "district": "Gopalganj",
     "nitrogen": "270", "phosphorous": "22", "potassium": "210", "ph": "7.4"},
    {"state": "Bihar", "district": "Patna",
     "nitrogen": "", "phosphorous": "", "potassium": "", "ph": ""},  # dropped
]


def test_shc_normalizes_records(monkeypatch):
    schema.ensure_tables()
    a = ShcSoil()
    monkeypatch.setattr(a, "fetch", lambda: SAMPLE_RECORDS)
    df = a.validate(a.normalize(a.fetch()))
    assert list(df["district"]) == ["Gopalganj"]
    assert df.iloc[0]["N"] == 270.0
    assert df.iloc[0]["state"] == "bihar"
    assert df.iloc[0]["source"] == "shc_soil"
    n = a.load(df)
    assert n == 1
