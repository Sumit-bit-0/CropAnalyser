from database import get_engine, query
from sqlalchemy import text
from tools.ingest import schema, registry, run


def test_registry_lists_all_adapters():
    names = set(registry.ADAPTERS)
    assert {"facility_crop_seed", "isma_sugar", "shc_soil",
            "datagov_mills", "mofpi_units", "state_signature"} <= names


def test_run_adapter_writes_provenance():
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM data_provenance WHERE source_name='facility_crop_seed'"))
    # facility_crop_seed has no network/staging dependency
    rows = run.run_adapter("facility_crop_seed")
    assert rows > 0
    prov = query(
        "SELECT rows_loaded, target_table, method FROM data_provenance "
        "WHERE source_name=? ORDER BY id DESC", ("facility_crop_seed",))
    assert int(prov.iloc[0]["rows_loaded"]) == rows
    assert prov.iloc[0]["target_table"] == "facility_crop_map"
    assert prov.iloc[0]["method"] == "manual"
