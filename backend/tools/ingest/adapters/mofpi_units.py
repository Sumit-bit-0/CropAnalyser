"""MoFPI food parks / registered food-processing units from a curated staging
CSV (columns facility_type,name,state,district,lat,lon,crop). Manual method."""
import pandas as pd

from config import ROOT
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

STAGING_CSV = ROOT / "backend" / "tools" / "ingest" / "_staging" / "mofpi_units.csv"


class MofpiUnits(SourceAdapter):
    source_name = "mofpi_units"
    target_table = "processing_units"
    method = "manual"
    source_ref = "tools/ingest/_staging/mofpi_units.csv (MoFPI registry)"

    def fetch(self):
        if not STAGING_CSV.exists():
            raise FileNotFoundError(
                f"Staging file missing: {STAGING_CSV}. Save MoFPI units as "
                f"facility_type,name,state,district,lat,lon,crop and re-run."
            )
        return STAGING_CSV

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.read_csv(raw)
        df["source"] = self.source_name
        df["source_id"] = df["name"].astype(str).str.strip()
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
