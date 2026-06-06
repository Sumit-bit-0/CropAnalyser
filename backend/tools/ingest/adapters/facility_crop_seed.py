"""Loads the committed facility_crop_map taxonomy (crop -> facility_type).
This is the canonical mapping the demand gate reads; tea is intentionally
absent until 'tea' enters the crop catalog WHITELIST."""
import pandas as pd

from config import DATA_RAW
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_crop_map

CSV = DATA_RAW / "facility_crop_map.csv"


class FacilityCropSeed(SourceAdapter):
    source_name = "facility_crop_seed"
    target_table = "facility_crop_map"
    method = "manual"
    source_ref = "data/raw/facility_crop_map.csv"

    def fetch(self):
        return CSV

    def normalize(self, raw) -> pd.DataFrame:
        return pd.read_csv(raw)

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_crop_map(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
