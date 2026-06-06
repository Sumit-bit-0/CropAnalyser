import pandas as pd
from sqlalchemy import text

from database import get_engine, query
from tools.ingest import schema, base


class _FakeAdapter(base.SourceAdapter):
    source_name = "fake"
    target_table = "processing_units"
    method = "manual"
    source_ref = "fake.csv"

    def __init__(self, rows):
        self._rows = rows

    def fetch(self):
        return self._rows

    def normalize(self, raw):
        return pd.DataFrame(raw)

    def validate(self, df):
        return df

    def load(self, df):
        return self.delete_by_source_then_insert(df)


def _row(name, source_id):
    return {"facility_type": "sugar_mill", "name": name, "state": "Bihar",
            "district": "Gopalganj", "lat": 26.47, "lon": 84.43,
            "crop": "sugarcane", "source": "fake", "source_id": source_id}


def test_load_then_reload_is_idempotent():
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='fake'"))

    a = _FakeAdapter([_row("M1", "1"), _row("M2", "2")])
    n1 = a.load(a.validate(a.normalize(a.fetch())))
    assert n1 == 2

    a2 = _FakeAdapter([_row("M1", "1"), _row("M2", "2")])
    a2.load(a2.validate(a2.normalize(a2.fetch())))

    cnt = query("SELECT COUNT(*) AS n FROM processing_units WHERE source=?",
                ("fake",)).iloc[0]["n"]
    assert int(cnt) == 2  # not 4 — old rows for this source were replaced

    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='fake'"))
