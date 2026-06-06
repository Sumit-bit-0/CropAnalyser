from tools.ingest import schema
from tools.ingest.adapters.state_signature import StateSignature


def test_state_signature_loads_whitelist_crops_only():
    schema.ensure_tables()
    a = StateSignature()
    df = a.validate(a.normalize(a.fetch()))
    assert "tea" not in set(df["crop"])         # tea excluded
    assert "coffee" in set(df["crop"])
    assert df["source"].eq("state_signature").all()
    # every row carries a facility_type and valid coords
    assert df["facility_type"].notna().all()
    n = a.load(df)
    assert n == len(df) and n > 0
