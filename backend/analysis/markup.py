from database import query

def get_state_markup() -> list[dict]:
    df = query("""
        SELECT state,
               AVG((modal_price - farm_gate_price) / NULLIF(farm_gate_price, 0) * 100) AS avg_markup_pct,
               AVG(farm_gate_price) AS avg_farm_gate,
               AVG(modal_price)     AS avg_modal,
               COUNT(*)             AS record_count
        FROM prices
        GROUP BY state
        ORDER BY avg_markup_pct DESC
    """)
    return df.round(2).to_dict(orient="records")

def get_crop_markup(commodity: str) -> list[dict]:
    df = query("""
        SELECT state,
               AVG((modal_price - farm_gate_price) / NULLIF(farm_gate_price, 0) * 100) AS avg_markup_pct,
               AVG(farm_gate_price) AS avg_farm_gate,
               AVG(modal_price)     AS avg_modal
        FROM prices
        WHERE LOWER(commodity) = LOWER(?)
        GROUP BY state
        ORDER BY avg_markup_pct DESC
    """, (commodity,))
    return df.round(2).to_dict(orient="records")
