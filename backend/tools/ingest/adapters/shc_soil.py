"""Soil Health Card district macro-nutrients from data.gov.in (keyed API).
fetch() is the only network call; normalize() maps SHC field names to the
soil_nutrients schema. Set DATA_GOV_API_KEY and SHC_RESOURCE_ID in .env."""
import os

import pandas as pd
import requests

from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_soil

BASE = "https://api.data.gov.in/resource"
TIMEOUT = 30

# data.gov.in field -> our column
_FIELD_MAP = {
    "nitrogen": "N", "phosphorous": "P", "potassium": "K", "ph": "ph",
}


class ShcSoil(SourceAdapter):
    source_name = "shc_soil"
    target_table = "soil_nutrients"
    method = "api"
    source_ref = "data.gov.in Soil Health Card resource"

    def fetch(self):
        key = os.getenv("DATA_GOV_API_KEY")
        resource = os.getenv("SHC_RESOURCE_ID")
        if not key or not resource:
            raise RuntimeError(
                "DATA_GOV_API_KEY and SHC_RESOURCE_ID must be set in .env "
                "to fetch Soil Health Card data."
            )
        resp = requests.get(
            f"{BASE}/{resource}",
            params={"api-key": key, "format": "json", "limit": 10000},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("records", [])

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.DataFrame(raw)
        df = df.rename(columns=_FIELD_MAP)
        for col in ("state", "district", "N", "P", "K", "ph"):
            if col not in df.columns:
                df[col] = None
        df["source"] = self.source_name
        return df[["state", "district", "N", "P", "K", "ph", "source"]]

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_soil(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
