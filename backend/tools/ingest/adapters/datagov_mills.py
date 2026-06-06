"""Rice / flour / oil / dal mills and cold storage from data.gov.in registries.
Each registry resource maps to a facility_type via env config. fetch() is the
only network call. Set DATA_GOV_API_KEY and MILLS_RESOURCE_ID (+ optional
MILLS_FACILITY_TYPE, MILLS_CROP) in .env for the resource being loaded."""
import os

import pandas as pd
import requests

from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

BASE = "https://api.data.gov.in/resource"
TIMEOUT = 30


class DatagovMills(SourceAdapter):
    source_name = "datagov_mills"
    target_table = "processing_units"
    method = "api"
    source_ref = "data.gov.in mill/cold-storage registry"

    def fetch(self):
        key = os.getenv("DATA_GOV_API_KEY")
        resource = os.getenv("MILLS_RESOURCE_ID")
        if not key or not resource:
            raise RuntimeError(
                "DATA_GOV_API_KEY and MILLS_RESOURCE_ID must be set in .env."
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
        df["facility_type"] = os.getenv("MILLS_FACILITY_TYPE", "rice_mill")
        df["crop"] = os.getenv("MILLS_CROP", "rice")
        df["source"] = self.source_name
        if "source_id" not in df.columns:
            df["source_id"] = df.get("name", pd.Series(dtype=str)).astype(str)
        for col in ("name", "state", "district", "lat", "lon"):
            if col not in df.columns:
                df[col] = None
        return df[["facility_type", "name", "state", "district",
                   "lat", "lon", "crop", "source", "source_id"]]

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
