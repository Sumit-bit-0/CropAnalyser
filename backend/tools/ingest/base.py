"""SourceAdapter contract + a delete-by-source-then-insert load helper that
makes every adapter idempotent (re-running replaces that source's rows)."""
from abc import ABC, abstractmethod

import pandas as pd
from sqlalchemy import text

from database import get_engine

# Columns persisted per target table (drops any extra helper columns).
_TABLE_COLS = {
    "processing_units": ["facility_type", "name", "state", "district",
                         "lat", "lon", "crop", "source", "source_id"],
    "soil_nutrients": ["state", "district", "N", "P", "K", "ph", "source"],
    "facility_crop_map": ["crop", "facility_type"],
}


class SourceAdapter(ABC):
    source_name: str
    target_table: str
    method: str          # "api" | "manual"
    source_ref: str

    @abstractmethod
    def fetch(self): ...

    @abstractmethod
    def normalize(self, raw) -> pd.DataFrame: ...

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> pd.DataFrame: ...

    @abstractmethod
    def load(self, df: pd.DataFrame) -> int: ...

    def delete_by_source_then_insert(self, df: pd.DataFrame) -> int:
        """Replace this source's existing rows with df. Idempotent."""
        cols = _TABLE_COLS[self.target_table]
        df = df[cols].copy()
        with get_engine().begin() as conn:
            if "source" in cols:
                conn.execute(
                    text(f"DELETE FROM {self.target_table} WHERE source=:s"),
                    {"s": self.source_name},
                )
                df.to_sql(self.target_table, conn, if_exists="append",
                          index=False)
            else:
                # facility_crop_map has no source column: full replace.
                conn.execute(text(f"DELETE FROM {self.target_table}"))
                df.to_sql(self.target_table, conn, if_exists="append",
                          index=False)
        return len(df)
