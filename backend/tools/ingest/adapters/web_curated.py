"""Web-sourced "major industry" facilities (official rated lists / trade
association directories) curated into a committed CSV by
data/build_web_curated.py. Currently: cotton ginning (Textiles Committee
star-rated ginning & pressing factories). WHITELIST crops only."""
import pandas as pd

from config import DATA_RAW
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

CSV = DATA_RAW / "web_curated_units.csv"


class WebCurated(SourceAdapter):
    source_name = "web_curated"
    target_table = "processing_units"
    method = "manual"
    source_ref = "data/raw/web_curated_units.csv (see data/build_web_curated.py)"

    def fetch(self):
        if not CSV.exists():
            raise FileNotFoundError(
                f"{CSV} missing. Run: python -m data.build_web_curated")
        return CSV

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.read_csv(raw)
        df["source"] = self.source_name
        df["source_id"] = (df["facility_type"].astype(str) + ":"
                           + df["name"].astype(str).str.strip())
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
