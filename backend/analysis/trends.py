from database import query

def get_available_filters() -> dict:
    states_df = query("SELECT DISTINCT state FROM prices ORDER BY state")
    commodities_df = query("SELECT DISTINCT commodity FROM prices ORDER BY commodity")
    return {
        "states": states_df["state"].tolist(),
        "commodities": commodities_df["commodity"].tolist()
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
