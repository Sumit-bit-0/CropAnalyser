from database import get_engine, table_exists
from tools.ingest import schema


def test_ensure_tables_creates_all_four():
    schema.ensure_tables()
    for t in ("processing_units", "soil_nutrients",
              "facility_crop_map", "data_provenance"):
        assert table_exists(t)


def test_ensure_tables_is_idempotent():
    schema.ensure_tables()
    schema.ensure_tables()  # second call must not raise
    assert table_exists("processing_units")
