"""Sugar mills from a curated ISMA-derived staging CSV
(tools/ingest/_staging/isma_sugar.csv with columns name,state,district,lat,lon).
facility_type/crop are constants. Manual method: download is done by hand,
this adapter only normalizes + loads."""
import pandas as pd

from config import ROOT
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

STAGING_CSV = ROOT / "backend" / "tools" / "ingest" / "_staging" / "isma_sugar.csv"


class IsmaSugar(SourceAdapter):
    source_name = "isma_sugar"
    target_table = "processing_units"
    method = "manual"
    source_ref = "tools/ingest/_staging/isma_sugar.csv (ISMA mill list)"

    def fetch(self):
        if not STAGING_CSV.exists():
            raise FileNotFoundError(
                f"Staging file missing: {STAGING_CSV}. Download the ISMA mill "
                f"list, save as name,state,district,lat,lon, then re-run."
            )
        return STAGING_CSV

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.read_csv(raw)
        df["facility_type"] = "sugar_mill"
        df["crop"] = "sugarcane"
        df["source"] = self.source_name
        df["source_id"] = df["name"].astype(str).str.strip()
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
