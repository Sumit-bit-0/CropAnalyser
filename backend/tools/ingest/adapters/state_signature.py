"""Curated state-signature processing units (coffee curing, coir, spice, jute,
winery, regional oil mills) for the first-pass states. Committed CSV, WHITELIST
crops only — tea units are deferred until 'tea' enters the crop catalog."""
import pandas as pd

from config import DATA_RAW
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

CSV = DATA_RAW / "state_signature_units.csv"


class StateSignature(SourceAdapter):
    source_name = "state_signature"
    target_table = "processing_units"
    method = "manual"
    source_ref = "data/raw/state_signature_units.csv"

    def fetch(self):
        return CSV

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.read_csv(raw)
        df["source"] = self.source_name
        df["source_id"] = df["name"].astype(str).str.strip()
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
