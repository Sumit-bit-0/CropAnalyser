"""Food-processing units from manual Udyam/MSME "Product/Activity based MSME
Units Detail" Excel exports (udyamregistration.gov.in -> SearchRegDetail.aspx).

Each export is one (state, NIC-activity) slice. Columns:
    SNo., Enterprise Name, Address, State, District, Pin Code, Social Category, Gender
The files are HTML tables saved as .xls, read with pandas.read_html.

Raw exports carry tens of thousands of micro-units (village aata-chakkis, single
person traders). We keep only "bigger industry" PINs: a PIN is a real processing
hub if it has >=1 industrial-named unit OR a cluster of >=MIN_CLUSTER units of
that activity. Each qualifying PIN collapses to ONE processing_units row,
geocoded by pincode (district-centroid fallback). The proximity gate cares where
the nearest mill is, not how many, so this keeps the table small, clean and
language-agnostic (English Bihar names and local Andhra names alike).

Expand without code changes: drop a new export in _staging/msme/ and add a line
to _staging/msme/manifest.csv (file,facility_type,crop). A new commodity also
needs its crop->facility_type row in facility_crop_map so the gate fires.
"""
import re

import pandas as pd

from config import ROOT, DATA_RAW
from analysis.geo import get_centroid
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

STAGING_DIR = ROOT / "backend" / "tools" / "ingest" / "_staging" / "msme"
MANIFEST = STAGING_DIR / "manifest.csv"

# A name signalling an industrial-scale / incorporated mill (vs a micro chakki).
STRONG_NAME = re.compile(
    r"\b(?:roller|flour\s*mill|rice\s*mill|oil\s*mill|dal\s*mill|solvent|ginn|"
    r"industr|agro|foods?|pvt|private|limited|ltd|llp|corporation|processing|"
    r"exports?|mills)\b", re.I)
MIN_CLUSTER = 5   # a PIN with >=MIN_CLUSTER units of the activity is a real hub


def _strong(names: pd.Series) -> pd.Series:
    return names.astype(str).str.contains(STRONG_NAME)


def qualify_and_collapse(df: pd.DataFrame, facility_type: str, crop: str,
                         min_cluster: int = MIN_CLUSTER) -> pd.DataFrame:
    """Raw export frame -> one row per "bigger industry" PIN.

    A PIN survives if it has >=1 industrial-named unit OR >=min_cluster units.
    The kept row's name is the most descriptive industrial name in the PIN, or a
    synthesized "<District> <crop> milling cluster (<pin>)" when the PIN
    qualified purely on cluster size. lat/lon are filled later (geocode)."""
    df = df.rename(columns=lambda c: str(c).strip())
    df = df[["Enterprise Name", "State", "District", "Pin Code"]].copy()
    df["pin"] = pd.to_numeric(df["Pin Code"], errors="coerce")
    df = df.dropna(subset=["pin"])
    df["pin"] = df["pin"].astype(int).astype(str).str.zfill(6)
    df = df[df["pin"].str.len() == 6]
    df["strong"] = _strong(df["Enterprise Name"])
    rows = []
    for pin, g in df.groupby("pin"):
        if not (g["strong"].any() or len(g) >= min_cluster):
            continue
        state = str(g["State"].mode().iat[0])
        district = str(g["District"].mode().iat[0])
        if g["strong"].any():
            cand = g.loc[g["strong"], "Enterprise Name"].astype(str).str.strip()
            name = cand.loc[cand.str.len().idxmax()][:200]
        else:
            name = f"{district.title()} {crop} milling cluster ({pin})"
        rows.append({"facility_type": facility_type, "name": name,
                     "state": state, "district": district, "crop": crop,
                     "pin": pin})
    return pd.DataFrame(rows, columns=["facility_type", "name", "state",
                                       "district", "crop", "pin"])


def _pin_latlon() -> dict:
    """{pincode -> (lat, lon)} from the bundled offline pincode table."""
    pc = pd.read_csv(DATA_RAW / "india_pincodes.csv", dtype={"pincode": str})
    return {str(r.pincode).strip(): (r.lat, r.lon)
            for r in pc.itertuples(index=False)}


class MsmeUdyam(SourceAdapter):
    source_name = "msme_udyam"
    target_table = "processing_units"
    method = "manual"
    source_ref = ("tools/ingest/_staging/msme/*.xls "
                  "(udyamregistration.gov.in SearchRegDetail.aspx; manifest.csv)")

    def fetch(self):
        if not MANIFEST.exists():
            raise FileNotFoundError(
                f"Manifest missing: {MANIFEST}. Drop Udyam exports in "
                f"{STAGING_DIR} and list them as file,facility_type,crop.")
        man = pd.read_csv(MANIFEST)
        items = []
        for r in man.itertuples(index=False):
            p = STAGING_DIR / str(r.file).strip()
            if not p.exists():
                raise FileNotFoundError(f"Manifest lists missing file: {p}")
            items.append((p, str(r.facility_type).strip(), str(r.crop).strip()))
        return items

    def normalize(self, raw) -> pd.DataFrame:
        frames = [qualify_and_collapse(pd.read_html(path)[0], ftype, crop)
                  for path, ftype, crop in raw]
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["facility_type", "name", "state", "district", "crop", "pin"])
        pinmap = _pin_latlon()
        lat, lon = [], []
        for r in df.itertuples(index=False):
            ll = pinmap.get(r.pin) or get_centroid(r.state, r.district)
            lat.append(ll[0] if ll else None)
            lon.append(ll[1] if ll else None)
        df["lat"], df["lon"] = lat, lon
        df["source"] = self.source_name
        df["source_id"] = df["facility_type"] + ":" + df["pin"]
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
