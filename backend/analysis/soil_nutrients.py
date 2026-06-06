# backend/analysis/soil_nutrients.py
"""District-level soil nutrients (N, P, K, pH) from the Postgres soil_nutrients
table (loaded by tools/ingest). Lookup by (state, district); fall back to the
state average, then a national average, so every location resolves. Returns
None when the table is empty/absent.

Note: N/P/K are quoted uppercase columns in Postgres, so SELECTs quote them."""
from database import query, table_exists
from analysis.geo import normalize_state

_FIELDS = ("N", "P", "K", "ph")
_SELECT = 'SELECT "N", "P", "K", ph FROM soil_nutrients'


def _avg(df) -> dict:
    return {k: round(float(df[k].dropna().mean()), 2) for k in _FIELDS}


def district_soil(state: str, district: str | None = None):
    """{N,P,K,ph, soil_source}; tiers district -> state -> national. None if no data."""
    if not table_exists("soil_nutrients"):
        return None
    s = normalize_state(state)
    if district:
        hit = query(_SELECT + " WHERE LOWER(state)=LOWER(?) AND LOWER(district)=LOWER(?)",
                    (s, district))
        if not hit.empty:
            return {**_avg(hit), "soil_source": "district"}
    st = query(_SELECT + " WHERE LOWER(state)=LOWER(?)", (s,))
    if not st.empty:
        return {**_avg(st), "soil_source": "state"}
    nat = query(_SELECT)
    if nat.empty:
        return None
    return {**_avg(nat), "soil_source": "national"}
