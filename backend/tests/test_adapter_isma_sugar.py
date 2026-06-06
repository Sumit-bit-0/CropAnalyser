import pandas as pd
import tools.ingest.adapters.isma_sugar as mod
from tools.ingest.adapters.isma_sugar import IsmaSugar


def test_isma_normalizes_and_validates(tmp_path, monkeypatch):
    csv = tmp_path / "isma_sugar.csv"
    csv.write_text(
        "name,state,district,lat,lon\n"
        "Gopalganj Sugar Mill,Bihar,Gopalganj,26.47,84.43\n"
        "Bad Mill,Bihar,Nowhere,0.0,0.0\n",          # out of bbox -> dropped
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STAGING_CSV", csv)
    a = IsmaSugar()
    df = a.validate(a.normalize(a.fetch()))
    assert list(df["name"]) == ["Gopalganj Sugar Mill"]
    assert df.iloc[0]["facility_type"] == "sugar_mill"
    assert df.iloc[0]["crop"] == "sugarcane"
    assert df.iloc[0]["source"] == "isma_sugar"
