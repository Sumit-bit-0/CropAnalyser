from database import query
from analysis.summaries import table_exists

def get_available_filters() -> dict:
    # Read distinct values from the tiny summary tables (instant) instead of
    # scanning the 27.6M-row prices table; fall back to live if not built.
    if table_exists("summary_state_markup") and table_exists("summary_crop_markup"):
        states_df = query("SELECT state FROM summary_state_markup ORDER BY state")
        commodities_df = query("SELECT DISTINCT commodity FROM summary_crop_markup ORDER BY commodity")
    else:
        states_df = query("SELECT DISTINCT state FROM prices ORDER BY state")
        commodities_df = query("SELECT DISTINCT commodity FROM prices ORDER BY commodity")
    # Sort in Python (code-point order) so ordering is deterministic and
    # independent of the database's collation (Postgres locale != SQLite BINARY).
    return {
        "states": sorted(states_df["state"].tolist()),
        "commodities": sorted(commodities_df["commodity"].tolist())
    }

def get_price_trend(state: str, commodity: str) -> list[dict]:
    df = query("""
        SELECT year, month,
               AVG(farm_gate_price) AS farm_gate_price,
               AVG(modal_price)     AS modal_price
        FROM prices
        WHERE LOWER(state) = LOWER(?) AND LOWER(commodity) = LOWER(?)
        GROUP BY year, month
        ORDER BY year, month
    """, (state, commodity))
    df["period"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)
    df["farm_gate_price"] = df["farm_gate_price"].round(2)
    df["modal_price"] = df["modal_price"].round(2)
    return df[["period", "farm_gate_price", "modal_price"]].to_dict(orient="records")
