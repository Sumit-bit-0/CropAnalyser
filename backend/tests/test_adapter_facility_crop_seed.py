from database import get_engine, query
from sqlalchemy import text
from tools.ingest import schema
from tools.ingest.adapters.facility_crop_seed import FacilityCropSeed


def test_seed_loads_taxonomy():
    schema.ensure_tables()
    a = FacilityCropSeed()
    df = a.validate(a.normalize(a.fetch()))
    # tea must not be present (not in WHITELIST)
    assert "tea" not in set(df["crop"])
    # oilseeds share oil_mill
    oil = df[df["facility_type"] == "oil_mill"]["crop"].tolist()
    assert {"mustard", "groundnut", "soyabean"} <= set(oil)
    n = a.load(df)
    assert n == len(df)
    row = query("SELECT facility_type FROM facility_crop_map WHERE crop=?",
                ("sugarcane",))
    assert row.iloc[0]["facility_type"] == "sugar_mill"
